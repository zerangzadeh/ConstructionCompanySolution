"""Executed inside the isolated Linux app: current release and changed boundaries."""

import hashlib
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
sys.path.insert(0, "/app")

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test.runner import DiscoverRunner

OUT = Path("/evidence")


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str) + "\n")


def main():
    assert settings.DATABASES["default"]["NAME"] == "pe_readiness_20261028"
    assert settings.DATABASES["default"]["HOST"] == "db"
    assert settings.DATABASES["default"]["OPTIONS"]["sslmode"] == "verify-full"
    action = sys.argv[1]
    if action == "migrate":
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        write(
            "MIGRATION_PLAN.json",
            [{"app": m.app_label, "name": m.name, "backwards": b} for m, b in plan],
        )
        assert len(plan) == 6 and all(not backwards for _, backwards in plan)
        call_command("migrate", interactive=False, verbosity=1)
        executor = MigrationExecutor(connection)
        assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
        call_command("makemigrations", check=True, dry_run=True, verbosity=1)
        call_command("check", deploy=True, fail_level="WARNING")
    elif action == "row-fingerprints":
        # Preserve every pre-existing row, including catalogs, not just row counts.
        from psycopg import sql

        result = {}
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
            tables = [r[0] for r in cursor.fetchall()]
            for table in tables:
                cursor.execute(
                    sql.SQL("SELECT row_to_json(t)::text FROM {} t").format(
                        sql.Identifier("public", table)
                    )
                )
                result[table] = sorted(
                    hashlib.sha256(r[0].encode()).hexdigest() for r in cursor.fetchall()
                )
        write(sys.argv[2] + ".json", result)
    elif action == "catalog-delta":
        import psycopg
        from psycopg import sql

        db = settings.DATABASES["default"]
        options = dict(
            db["OPTIONS"],
            host=db["HOST"],
            port=db["PORT"],
            user=db["USER"],
            password=db["PASSWORD"],
        )
        result = {}
        with (
            psycopg.connect(**options, dbname="pe_source") as old,
            psycopg.connect(**options, dbname=db["NAME"]) as new,
        ):
            for table in (
                "organizations_businesspermission",
                "organizations_organizationrole",
            ):
                query = sql.SQL("SELECT row_to_json(t) FROM {} t").format(
                    sql.Identifier(table)
                )
                before = {str(row[0]["id"]): row[0] for row in old.execute(query)}
                after = {str(row[0]["id"]): row[0] for row in new.execute(query)}
                assert set(before) <= set(after), "Catalog records removed"
                fields = {}
                for key, row in before.items():
                    for field, value in row.items():
                        if value != after[key][field]:
                            fields[field] = fields.get(field, 0) + 1
                result[table] = {
                    "existing_records": len(before),
                    "new_records": len(after) - len(before),
                    "changed_fields": fields,
                }
        write("CATALOG_DELTA.json", result)
        assert all(
            set(item["changed_fields"]) <= {"updated_at"} for item in result.values()
        ), "Unexplained semantic catalog change"
    elif action == "tests":
        settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = (
            "test_pe_readiness_qualified_20261028"
        )
        # Only changed financial/statutory boundaries and Linux operations compatibility.
        labels = [
            "apps.accounting.test_fiscal_year_closing.FiscalYearClosingTests.test_profit_loss_zero_and_balanced_permanent_carry",
            "apps.accounting.test_fiscal_year_closing.FiscalYearClosingTests.test_idempotency_for_prepare_close_and_opening",
            "apps.accounting.test_fiscal_year_closing.FiscalYearClosingTests.test_roll_reversal_reclose_and_new_version",
            "apps.accounting.test_fiscal_year_closing.FiscalYearClosingTests.test_self_approval_and_self_acceptance_denied",
            "apps.accounting.test_fiscal_year_closing.FiscalYearClosingTests.test_cross_tenant_pair_and_configuration_are_denied",
            "apps.accounting.test_fiscal_year_closing.FiscalYearClosingMigrationTests",
            "apps.accounting.test_fiscal_year_closing.FiscalYearClosingConcurrencyTests",
            "apps.payroll.test_cep069.AdoptedStatutoryTests.test_annual_ytd_subtracts_prior_withholding",
            "apps.payroll.test_cep069.AdoptedStatutoryTests.test_unmapped_and_conditional_components_reject",
            "apps.payroll.test_cep069.AdoptedStatutoryTests.test_context_tenant_permission_immutability",
            "apps.payroll.test_cep069.AdoptedStatutoryTests.test_governance_rejects_missing_source_dates_and_production",
            "apps.payroll.test_cep069.AdoptedStatutoryTests.test_explicit_source_linked_activation_and_calculation_snapshot",
            "tests.test_operations.OperationsTests",
        ]
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
        # Only this disposable test process; HTTPS is checked on real Gunicorn separately.
        settings.SECURE_SSL_REDIRECT = False
        log = io.StringIO()
        with redirect_stdout(log), redirect_stderr(log):
            runner = DiscoverRunner(
                verbosity=2, interactive=False, keepdb=True, stream=log
            )
            failures = runner.run_tests(labels)
        (OUT / "CURRENT_BOUNDARY_TESTS.txt").write_text(log.getvalue())
        write(
            "CURRENT_BOUNDARY_TESTS.json",
            {
                "labels": labels,
                "failed": failures,
                "environment": "Linux CPython3.11.17/PostgreSQL18.6 TLS disposable test DB",
                "production_action": False,
            },
        )
        assert failures == 0, (
            "Current release boundary tests failed; see retained evidence"
        )
    else:
        raise ValueError("Unknown probe")


if __name__ == "__main__":
    main()
