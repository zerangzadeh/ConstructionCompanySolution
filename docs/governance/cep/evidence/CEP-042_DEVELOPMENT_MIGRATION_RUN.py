"""Bounded, repeatable CEP-042 local-development schema execution evidence."""

import json
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402
from django.db.migrations.executor import MigrationExecutor  # noqa: E402

from apps.accounting.recognition_sources import digest  # noqa: E402

assert os.environ["DJANGO_SETTINGS_MODULE"] == "config.settings.development"
assert settings.DEBUG is True
assert connection.vendor == "postgresql"
assert connection.settings_dict["HOST"] in {"127.0.0.1", "localhost", "::1"}
assert not connection.settings_dict["NAME"].startswith("test_")

targets = [
    ("organizations", "0120_cep042_recognition_permissions"),
    ("accounting", "0013_cep042_recognition_mapping"),
]
executor = MigrationExecutor(connection)
plan = executor.migration_plan(targets)
planned = [(migration.app_label, migration.name) for migration, backwards in plan]
assert all(not backwards for _, backwards in plan)
assert set(planned).issubset(set(targets)), planned

labels = (
    "accounting.Account",
    "accounting.ControlAccountMappingVersion",
    "accounting.FiscalYear",
    "accounting.FiscalPeriod",
    "accounting.JournalEntry",
    "accounting.JournalLine",
    "treasury.PaymentRequest",
    "treasury.TreasuryMovement",
    "treasury.TreasuryAccountMappingVersion",
    "subledgers.Obligation",
    "expenses.Expense",
    "expenses.ExpenseAllocation",
    "payroll.PayrollRun",
    "payroll.PayrollRunEmployee",
    "payroll.PayrollResultLine",
    "inventory.InventoryValuationEvent",
    "inventory.StockTransaction",
    "fixed_assets.AssetTransaction",
    "fixed_assets.DepreciationRun",
    "fixed_assets.DepreciationLine",
    "projects.ProjectCostFact",
    "audit.AuditEvent",
)


def snapshot():
    result = {}
    for label in labels:
        rows = list(apps.get_model(label).objects.order_by("pk").values())
        result[label] = {"count": len(rows), "sha256": digest(rows)}
    through = apps.get_model("organizations.OrganizationRole").permissions.through
    grants = list(through.objects.order_by("pk").values())
    result["role_grants"] = {"count": len(grants), "sha256": digest(grants)}
    catalog = list(
        apps.get_model("organizations.BusinessPermission")
        .objects.exclude(code__startswith="accounting_recognition.")
        .order_by("pk")
        .values()
    )
    result["preexisting_permission_catalog"] = {
        "count": len(catalog),
        "sha256": digest(catalog),
    }
    return result


before = snapshot()
executor.migrate(targets)
after = snapshot()
assert before == after, "Existing history or grants changed"
assert not MigrationExecutor(connection).migration_plan(targets)
assert apps.get_model("accounting.RecognitionMappingVersion").objects.count() == 0
assert apps.get_model("accounting.RecognitionMappingApproval").objects.count() == 0
assert apps.get_model("accounting.SourceRecognitionDraft").objects.count() == 0
assert (
    apps.get_model("organizations.BusinessPermission")
    .objects.filter(code__startswith="accounting_recognition.", is_active=True)
    .count()
    == 4
)
result = {
    "authority": "HUMAN-CEP042-PERSISTENCE-20261018",
    "settings_module": "config.settings.development",
    "database_vendor": "postgresql",
    "host_is_loopback": True,
    "migrations_applied": [".".join(item) for item in planned],
    "before": before,
    "after": after,
    "existing_history_and_grants_preserved": True,
    "new_mapping_approval_and_effect_tables_empty": True,
    "implicit_mapping_defaults_or_backfill": False,
    "production": False,
    "git_writes": False,
}
Path(__file__).with_name("CEP-042_DEVELOPMENT_MIGRATION.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({key: value for key, value in result.items() if key not in {"before", "after"}}))
