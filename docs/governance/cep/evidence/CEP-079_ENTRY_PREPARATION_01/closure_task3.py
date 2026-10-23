"""Narrow read-only Treasury/Accounting fixture discovery; no UAT transitions."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.conf import settings
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from apps.organizations.models import Organization
from apps.treasury.models import TreasuryAccount, TreasuryAccountMappingVersion
from apps.accounting.models import JournalEntry, FiscalPeriod, ReconciliationRun, ControlAccountMappingVersion
from apps.accounts.models import User
from apps.accounting.reconciliation import inspect_manual_opening_reconciliation
from blocker_closure import write

assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
assert connection.vendor == "postgresql" and settings.DATABASES["default"]["HOST"] in ("127.0.0.1", "localhost")
assert not MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes())
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
    org = Organization.objects.get(slug="demo-construction-01", status="active")
    period = FiscalPeriod.objects.get(organization=org, fiscal_year__code="CEP079-SYNTHETIC-FY")
    actor = User.objects.get(username="account.demo-construction-01.accountant")
    report = inspect_manual_opening_reconciliation(organization=org, actor=actor, cutoff_date=period.ends_on)
    result = {
        "environment": "LOCAL_DEVELOPMENT_POSTGRESQL_MIGRATIONS_CURRENT",
        "accounts": list(TreasuryAccount.objects.filter(organization=org).values("id", "code", "kind", "status", "created_by_id")),
        "mappings": list(TreasuryAccountMappingVersion.objects.filter(organization=org).values("id", "treasury_account_id", "treasury_account__kind", "version", "is_active", "effective_from", "effective_to", "cash_ledger_account_id", "clearing_ledger_account_id", "created_by_id", "approved_by_id", "approval_policy_version_id", "reason")),
        "control_mappings": list(ControlAccountMappingVersion.objects.filter(organization=org).values()),
        "period": {"id": period.pk, "starts_on": period.starts_on, "ends_on": period.ends_on, "status": period.status},
        "period_journals": list(JournalEntry.objects.filter(organization=org, period=period).values("id", "source_key", "status", "accounting_date")),
        "synthetic_journal": list(JournalEntry.objects.filter(organization=org, source_key="CEP079-PREP-01-JOURNAL").values()),
        "existing_reconciliation_runs": list(ReconciliationRun.objects.filter(organization=org, cutoff_date=period.ends_on).values("id", "source_count", "journal_count", "exception_count")),
        "read_only_period_end_report": {"source_count": report.source_count, "journal_count": report.journal_count, "posted_count": report.posted_count, "pending_count": report.pending_count, "debit_total": report.debit_total, "credit_total": report.credit_total, "exceptions": [{"code": e.code, "source_uuid": e.source_uuid} for e in report.exceptions], "tie_out_count": len(report.tie_outs)},
        "mutation": "NONE",
    }
write("TASK3_DISCOVERY.json", result)
print({"accounts": result["accounts"], "mapping_count": len(result["mappings"]), "bank_mapping_count": sum(m["treasury_account__kind"] == "bank" for m in result["mappings"]), "period": result["period"], "report": result["read_only_period_end_report"]})
