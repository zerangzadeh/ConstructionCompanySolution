"""MVP-05 tests use a dedicated clone, never the configured Development DB."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

import pytest
from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase
from psycopg import sql

if os.environ.get("MVP05_REGRESSION") == "1":
    # The reusable clone lacks historical data-migration catalog rows. Restore
    # only those fixtures, inside each Billing test transaction, as MVP-03 does.
    from importlib import import_module

    from django.apps import apps

    from apps.billing import tests as billing_tests

    billing_setup = billing_tests.ProjectBaselineWorkflowTests.setUp

    def seeded_billing_setup(self):
        if (
            connections["default"].settings_dict["NAME"]
            != "test_bonira_mvp05_reg_20261103"
        ):
            raise RuntimeError(
                "Billing catalog fixtures require the regression test DB"
            )
        for migration, seed in (
            (
                "0018_project_baseline_compatibility_catalog",
                "seed_project_baseline_catalog",
            ),
            (
                "0019_progress_verification_compatibility_catalog",
                "seed_progress_catalog",
            ),
            (
                "0020_progress_claim_approval_compatibility_catalog",
                "seed_progress_claim_catalog",
            ),
        ):
            getattr(import_module("apps.workflows.migrations." + migration), seed)(
                apps, None
            )
        billing_setup(self)

    billing_tests.ProjectBaselineWorkflowTests.setUp = seeded_billing_setup

    # Reuse the fixture-only assignment adapter from MVP-04F's accepted runner.
    from apps.procurement.test_p5_s10_admissibility import AdmissibilityFixtureMixin
    from apps.procurement.test_p5_s11_comparison_award import (
        P5S11TwoRevisionFixtureMixin,
    )

    def assigned_actor(original):
        def wrapped(self, *args, **kwargs):
            actor = original(self, *args, **kwargs)
            self.establish_test_membership_authority(
                self.organization.memberships.get(user=actor)
            )
            return actor

        return wrapped

    for fixture in (AdmissibilityFixtureMixin, P5S11TwoRevisionFixtureMixin):
        fixture._make_actor = assigned_actor(fixture._make_actor)

TEST_DATABASE = (
    "test_bonira_mvp05_reg_20261103"
    if os.environ.get("MVP05_REGRESSION") == "1"
    else "test_bonira_mvp05_20261103"
)
connection = connections["default"]
with connection.cursor() as cursor:
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [TEST_DATABASE])
    if cursor.fetchone() is None:
        cursor.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(TEST_DATABASE),
                sql.Identifier("test_bonira_module_selector_clone_20261103"),
            )
        )
connection.settings_dict["TEST"]["NAME"] = TEST_DATABASE
original_setup = TransactionTestCase._fixture_setup.__func__


@classmethod
def isolated_setup(cls):
    for alias in cls._databases_names(include_mirrors=False):
        target = connections[alias]
        if cls.serialized_rollback and hasattr(target, "_test_serialized_contents"):
            if target.settings_dict["NAME"] != TEST_DATABASE:
                raise RuntimeError("Fixture reset requires MVP-05 isolated DB")
            call_command(
                "flush",
                database=alias,
                interactive=False,
                verbosity=0,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )
    original_setup(cls)


TransactionTestCase._fixture_setup = isolated_setup


class FailureEvidence:
    def pytest_collection_modifyitems(self, items):
        for item in items:
            cls = getattr(item, "cls", None)
            if (
                cls
                and hasattr(cls, "evidence_root")
                and not cls.__module__.startswith("test_mvp05")
            ):
                cls.evidence_root = ROOT / "output/mvp-05/affected" / cls.__name__
                cls.evidence_root.mkdir(parents=True, exist_ok=True)

    def pytest_runtest_logreport(self, report):
        if report.failed:
            directory = ROOT / "output/mvp-05/failures"
            directory.mkdir(parents=True, exist_ok=True)
            name = report.nodeid.replace("/", "_").replace(":", "_")
            (directory / f"{name}.txt").write_text(
                str(report.longrepr), encoding="utf8"
            )


raise SystemExit(
    pytest.main(
        sys.argv[1:] or ["tests/test_mvp05_xlsx.py", "--reuse-db", "-q"],
        plugins=[FailureEvidence()],
    )
)
