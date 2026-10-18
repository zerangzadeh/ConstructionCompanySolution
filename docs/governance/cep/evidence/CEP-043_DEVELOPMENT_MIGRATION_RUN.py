"""Only the authorized CEP043 additive local-development migrations."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.apps import apps
from django.conf import settings
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.subledgers.services import _canonical_hash

assert os.environ["DJANGO_SETTINGS_MODULE"] == "config.settings.development"
assert settings.DEBUG and connection.vendor == "postgresql"
assert connection.settings_dict["HOST"] in {"127.0.0.1", "localhost", "::1"}
assert not connection.settings_dict["NAME"].startswith("test_")
targets = [
    ("organizations", "0121_cep043_payroll_ap_permissions"),
    ("subledgers", "0006_cep043_payroll_ap"),
]
executor = MigrationExecutor(connection)
plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
assert all(not backwards for _, backwards in plan)
planned = [(m.app_label, m.name) for m, _ in plan]
assert set(planned).issubset(set(targets)), "Unrelated pending migrations; stop"
new_labels = {
    "subledgers.PayrollAPEnrollment",
    "subledgers.PayrollAPEnrollmentEvent",
    "subledgers.PayrollAPDraft",
    "subledgers.PayrollAPOperation",
    "subledgers.PayrollAPReversal",
}


def snapshot():
    result, seen = {}, set()
    for model in apps.get_models(include_auto_created=True):
        if (
            model._meta.label in new_labels
            or model._meta.proxy
            or not model._meta.managed
            or model._meta.app_label in {"contenttypes", "auth", "admin", "sessions"}
            or model._meta.db_table in seen
        ):
            continue
        seen.add(model._meta.db_table)
        rows = model._base_manager.order_by(model._meta.pk.name)
        if model._meta.label == "organizations.BusinessPermission":
            rows = rows.exclude(code__startswith="subledgers_payroll.")
        values = list(rows.values())
        result[model._meta.label] = {
            "count": len(values),
            "sha256": _canonical_hash(values),
        }
    return result


with transaction.atomic():
    before = snapshot()
    executor.migrate(targets)
    after = snapshot()
    assert before == after, "Existing business history or grants changed; rollback"
    for label in new_labels:
        assert apps.get_model(label).objects.count() == 0
    permission = apps.get_model("organizations.BusinessPermission")
    assert (
        permission.objects.filter(
            code__startswith="subledgers_payroll.", is_active=True
        ).count()
        == 4
    )
    grants = apps.get_model("organizations.OrganizationRole").permissions.through
    assert not grants.objects.filter(
        businesspermission__code__startswith="subledgers_payroll."
    ).exists()
    assert not MigrationExecutor(connection).migration_plan(targets)

result = {
    "authorities": [
        "HUMAN-CEP043-PERSISTENCE-20261018",
        "HUMAN-CEP043-LIFECYCLE-20261018",
    ],
    "settings_module": "config.settings.development",
    "database_vendor": "postgresql",
    "host_is_loopback": True,
    "migrations_applied": [".".join(t) for t in planned],
    "before": before,
    "after": after,
    "all_existing_business_tables_and_grants_preserved": True,
    "new_tables_empty": True,
    "default_enrollment_or_backfill": False,
    "implicit_new_grants": False,
    "production": False,
    "git_writes": False,
}
Path(__file__).with_name("CEP-043_DEVELOPMENT_MIGRATION.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({k: v for k, v in result.items() if k not in {"before", "after"}}))
