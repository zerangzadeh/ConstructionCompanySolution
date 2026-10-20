"""Bounded, empty-target Development migration rehearsal; no business-data exports."""

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

NEW = "0011_cep065_cashflow_evidence"
OLD = "0010_projectforecastreview_projectforecasttransition_and_more"
assert settings.SETTINGS_MODULE == "config.settings.development"
assert connection.vendor == "postgresql"
assert connection.settings_dict["HOST"] in {"127.0.0.1", "localhost"}


def retention():
    evidence = {}
    for name in (
        "projects.Project", "projects.BudgetVersion", "projects.BudgetAllocation",
        "projects.ProjectCostForecast", "projects.ProjectForecastReview",
        "projects.ProjectForecastTransition", "projects.ProjectCostFact",
        "treasury.TreasuryMovement", "subledgers.Obligation",
        "accounting.JournalEntry", "audit.AuditEvent",
    ):
        rows = list(apps.get_model(name).objects.order_by("pk").values())
        evidence[name] = {"count": len(rows), "sha256": hashlib.sha256(
            json.dumps(rows, default=str, sort_keys=True).encode()).hexdigest()}
    return evidence


plan = MigrationExecutor(connection).migration_plan([("projects", NEW)])
assert [(m.app_label, m.name, reverse) for m, reverse in plan] in (
    [("projects", NEW, False)], []
), "Unexpected migration scope"
before = retention()
call_command("migrate", "projects", NEW, interactive=False)
after_forward = retention()
assert before == after_forward
for model in ("projects.ProjectCashflowSupplement", "projects.ProjectCashflowSnapshot"):
    assert apps.get_model(model).objects.count() == 0, "Never reverse real cash planning evidence"
call_command("migrate", "projects", OLD, interactive=False)
after_reverse = retention()
assert before == after_reverse
call_command("migrate", "projects", NEW, interactive=False)
after_reapply = retention()
assert before == after_reapply
with connection.cursor() as cursor:
    cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname IN ('cashflow_supplement_insert', 'cashflow_supplement_immutable', 'cashflow_snapshot_immutable')")
    assert cursor.fetchone()[0] == 3
result = {
    "database": "configured loopback Development PostgreSQL; no credentials exported",
    "plan": [(m.app_label, m.name, reverse) for m, reverse in plan],
    "retained_sources": before,
    "forward_reverse_reapply_retention": "PASS_EXACT_VALUES_COUNTS_HASHES",
    "target_rows": 0, "immutability_and_insert_guards": 3,
    "production_action": False,
}
Path("docs/governance/cep/evidence/CEP-065_MIGRATION_RETENTION.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8")
print("CEP065 configured Development forward/reverse/reapply: PASS; exact source retention; empty targets.")
