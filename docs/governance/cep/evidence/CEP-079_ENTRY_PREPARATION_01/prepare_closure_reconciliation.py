"""Prepare native signed period-end evidence; never close/reopen the period."""
import hashlib
import json
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
from apps.accounts.models import User
from apps.organizations.models import Organization, BusinessPermissionCode
from apps.organizations.authorization import require_business_permission
from apps.accounting.models import FiscalPeriod, JournalEntry, JournalLine, OpeningBalanceImport, FiscalPeriodControlEvent, JournalNumberSequence
from apps.treasury.models import TreasuryAccount, TreasuryAccountMappingVersion, TreasuryMovement
from apps.accounting.reconciliation import create_manual_opening_reconciliation_run, sign_off_reconciliation_run, verify_signed_reconciliation_run
from apps.accounting.reporting import build_statement, retain_statement
from blocker_closure import write, OUT

assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
assert connection.vendor == "postgresql" and settings.DATABASES["default"]["HOST"] in ("127.0.0.1", "localhost")
if (OUT / "TASK3_RECONCILIATION_FIXTURE.json").exists():
    prior = json.loads((OUT / "TASK3_RECONCILIATION_FIXTURE.json").read_text())
    assert prior["result"] == "ROLLED_BACK_BLOCKED"
    retry_path = OUT / "TASK3_RECONCILIATION_RETRY_PREIMAGE.json"
    retries = json.loads(retry_path.read_text()) if retry_path.exists() else []
    if isinstance(retries, dict):
        retries = [retries]
    write("TASK3_RECONCILIATION_RETRY_PREIMAGE.json", retries + [prior])
org = Organization.objects.get(slug="demo-construction-01", status="active")
maker = User.objects.get(username="account.demo-construction-01.accountant", is_active=True)
checker = User.objects.get(username="account.demo-construction-01.owner", is_active=True)
reopen_checker = User.objects.get(username="uiux.persona.tenant-admin", is_active=True)
period = FiscalPeriod.objects.get(organization=org, fiscal_year__code="CEP079-SYNTHETIC-FY")


def fingerprint():
    return {m._meta.label: hashlib.sha256(json.dumps(list(m.objects.filter(organization=org).order_by(m._meta.pk.name).values()), sort_keys=True, default=str).encode()).hexdigest() for m in (FiscalPeriod, JournalEntry, JournalLine, OpeningBalanceImport, FiscalPeriodControlEvent, JournalNumberSequence, TreasuryAccount, TreasuryAccountMappingVersion, TreasuryMovement)}


before = fingerprint()
result = {"scope": "ENTRY_PREPARATION_ONLY_NO_PERIOD_CLOSE_REOPEN_NO_UAT", "protected_source_fingerprints_before": before}
try:
    with transaction.atomic():
        memberships = {}
        for user, codes in ((maker, (BusinessPermissionCode.ACCOUNTING_PERIODS_CLOSE,)), (checker, (BusinessPermissionCode.ACCOUNTING_PERIODS_CLOSE, BusinessPermissionCode.ACCOUNTING_PERIODS_REOPEN)), (reopen_checker, (BusinessPermissionCode.ACCOUNTING_PERIODS_REOPEN,))):
            memberships[user.username] = {}
            for code in codes:
                member = require_business_permission(user=user, organization=org, permission=code, message="Explicit period fixture permission required")
                memberships[user.username][code] = str(member.pk)
        assert memberships[maker.username] != memberships[checker.username]
        assert period.status == "open" and not period.control_events.exists()
        assert not period.journals.filter(status__in=["draft", "proposed"]).exists()
        assert not period.opening_balance_imports.filter(status__in=["draft", "proposed"]).exists()
        statements = []
        for kind, start in (("trial_balance", period.starts_on), ("balance_sheet", None), ("profit_loss", period.fiscal_year.starts_on)):
            calculated = build_statement(organization=org, actor=maker, kind=kind, starts_on=start, ends_on=period.ends_on)
            retained = retain_statement(organization=org, actor=maker, kind=kind, starts_on=start, ends_on=period.ends_on)
            assert retained.input_hash == calculated.input_hash and retained.result_hash == calculated.result_hash
            if kind == "trial_balance":
                assert retained.debit_total == retained.credit_total and retained.source_line_count > 0
                assert any(line.opening_debit > 0 or line.opening_credit > 0 for line in calculated.lines)
            statements.append({"id": retained.pk, "kind": kind, "source_line_count": retained.source_line_count, "debit_total": retained.debit_total, "credit_total": retained.credit_total, "input_hash": retained.input_hash, "result_hash": retained.result_hash})
        run = create_manual_opening_reconciliation_run(organization=org, actor=maker, cutoff_date=period.ends_on)
        assert run.source_count > 0 and run.posted_count > 0 and run.debit_total > 0 and run.exception_count == 0
        review = sign_off_reconciliation_run(organization=org, actor=checker, run=run, reason="CEP079 entry-only independent synthetic Development period-end evidence; no UAT, Human Sign-off or production acceptance")
        verified = verify_signed_reconciliation_run(organization=org, run=run)
        assert verified.pk == review.pk and run.created_by_id != review.reviewed_by_id
        period.refresh_from_db()
        assert period.status == "open" and not period.control_events.exists()
        assert fingerprint() == before
        result.update({"result": "PREPARED_AND_QUALIFIED", "period_id": period.pk, "period_status": period.status, "period_control_events": 0,
                       "run": {"id": run.pk, "scope": run.scope, "cutoff": run.cutoff_date, "source_count": run.source_count, "journal_count": run.journal_count, "posted_count": run.posted_count, "pending_count": run.pending_count, "exception_count": run.exception_count, "debit_total": run.debit_total, "credit_total": run.credit_total, "input_hash": run.input_hash, "result_hash": run.result_hash},
                       "review": {"id": review.pk, "signed_evidence_hash": review.signed_evidence_hash, "reviewer_membership": review.reviewed_by_id, "creator_membership": run.created_by_id},
                       "statements": statements, "independent_close_reopen_bindings": {"close": {"requester": memberships[maker.username], "approver": memberships[checker.username]}, "reopen": {"requester": memberships[checker.username], "approver": memberships[reopen_checker.username]}},
                       "coverage_limit": "Existing canonical Accounting manual/opening/correction scope and statement source snapshots; no new cross-domain coverage inferred. Nonzero opening balances at cutoff; target future period has no movements. Three pending pre-existing sources outside target period remain unchanged; no unknown-as-zero substitution.",
                       "protected_sources_unchanged": True})
except Exception as exc:
    result.update({"result": "ROLLED_BACK_BLOCKED", "exception": type(exc).__name__, "message": str(exc)})
result["protected_source_fingerprints_after"] = fingerprint()
assert result["protected_source_fingerprints_after"] == before
write("TASK3_RECONCILIATION_FIXTURE.json", result)
print(json.dumps({k: v for k, v in result.items() if k in ("result", "exception", "message", "run", "period_status", "protected_sources_unchanged")}, default=str))
