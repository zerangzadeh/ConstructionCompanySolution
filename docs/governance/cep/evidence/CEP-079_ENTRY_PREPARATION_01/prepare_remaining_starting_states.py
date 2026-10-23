"""Independent canonical fixture groups; no UAT scenario or Product remediation."""
import ast
import hashlib
import json
import os
import sys
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership
from apps.accounting.models import JournalEntry
from apps.treasury import services as treasury
from apps.treasury.models import TreasuryAccount

OUT = Path(__file__).parent
assert not (OUT / "REMAINING_STARTING_STATES.json").exists()
assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
assert connection.vendor == "postgresql" and settings.DATABASES["default"]["HOST"] in ("127.0.0.1", "localhost")
# Reuse only our inspected local helper definitions, never their top-level mutations.
tree = ast.parse((OUT / "prepare_financial_starting_states.py").read_text(encoding="utf-8"))
exec(compile(ast.Module(body=[x for x in tree.body if isinstance(x, ast.FunctionDef)], type_ignores=[]), "<local_fixture_helpers>", "exec"))
org = Organization.objects.get(slug="demo-construction-01", status="active")
maker = User.objects.get(username="account.demo-construction-01.accountant", is_active=True)
checker = User.objects.get(username="account.demo-construction-01.owner", is_active=True)
member = OrganizationMembership.objects.get(organization=org, user=maker, status="active")
sample_journal = JournalEntry.objects.get(organization=org, source_key="CEP079-PREP-01-JOURNAL")
day, period = sample_journal.accounting_date, sample_journal.period
note = "CEP079-PREP-01 isolated synthetic Development fixture, no regulatory/statutory authority or UAT acceptance."
records, outcomes = [], []
before = snapshot()
(OUT / "REMAINING_DATA_BEFORE.json").write_text(json.dumps(before), encoding="utf-8")


def group(name, build):
    index = len(records)
    try:
        with transaction.atomic():
            build()
        outcomes.append({"group": name, "result": "PREPARED", "records": records[index:]})
    except Exception as exc:
        del records[index:]
        outcomes.append({"group": name, "result": "ROLLED_BACK", "exception": type(exc).__name__, "message": str(exc)})


def cash_sources():
    from apps.procurement.models import PurchaseOrder
    account = TreasuryAccount.objects.get(organization=org, code="WCD-CASH", status="active")
    movement("CEP079-PREP-01-RECEIPT", "receipt", account)
    supplier = PurchaseOrder.objects.get(organization=org, order_number="CEP079-PREP-01-READY").supplier
    request = treasury.create_payment_request(
        organization=org, actor=maker, kind="vendor_advance", amount=Decimal("1"),
        purpose=note, idempotency_key="CEP079-PREP-01-ADVANCE", party=supplier,
    )
    treasury.submit_payment_request(organization=org, actor=maker, request=request, reason=note)
    treasury.decide_payment_request(organization=org, actor=checker, request=request, approve=True, reason=note)
    # Vendor advances link at native release; origin_request is reserved for
    # Payroll/reimbursement source validation by the existing domain contract.
    cash = movement("CEP079-PREP-01-ADVANCE-CASH", "disbursement", account, None, supplier)
    treasury.release_payment_request(organization=org, actor=checker, request=request, movement=cash, reason=note)
    keep(request, "New synthetic released request; existing accepted request untouched")
    keep(treasury.open_advance(organization=org, actor=checker, request=request), "New open synthetic advance; reversal starting state")


def ap_source():
    from apps.subledgers.models import SupplierInvoiceMatch
    from apps.subledgers.supplier_invoice_handoffs import handoff_supplier_invoice_match
    match = SupplierInvoiceMatch.objects.get(organization=org, invoice_version__invoice__invoice_number="CEP079-PREP-01-INVOICE")
    keep(handoff_supplier_invoice_match(
        organization=org, actor=maker, match=match,
        idempotency_key="CEP079-PREP-01-AP", effective_date=day, reason=note,
    ), "New source-owned AP obligation under existing control-account mapping; no settlement or GL policy added")


def fiscal_source():
    from apps.accounting import services as accounting
    from apps.accounting.models import FiscalYear, FiscalPeriod
    source = FiscalYear.objects.get(organization=org, code="FY-1405")
    existing_period = FiscalPeriod.objects.filter(fiscal_year=source).order_by("starts_on").first()
    year = keep(accounting.create_fiscal_year(
        organization=org, actor=maker, code="CEP079-SYNTHETIC-FY",
        name="CEP079 synthetic future interval; not a statutory calendar determination",
        starts_on=source.starts_on.replace(year=source.starts_on.year + 1),
        ends_on=source.ends_on.replace(year=source.ends_on.year + 1),
        calendar_version=source.calendar_version,
    ), "Isolated explicit synthetic interval using existing calendar-version contract; no current fiscal period changed")
    keep(accounting.create_fiscal_period(
        organization=org, actor=maker, fiscal_year=year, number=1,
        name="CEP079 isolated close/reopen fixture",
        starts_on=existing_period.starts_on.replace(year=existing_period.starts_on.year + 1),
        ends_on=existing_period.ends_on.replace(year=existing_period.ends_on.year + 1),
    ), "New empty period for protected close/reopen; accepted periods untouched")


def stock_destination():
    from apps.inventory.services import create_warehouse
    from apps.projects.models import Project
    actor = User.objects.get(username="cep078.synthetic.operations", is_active=True)
    keep(create_warehouse(
        organization=org, actor=actor,
        project=Project.objects.get(organization=org, code="PRJ-01-01"),
        code="CEP079-PREP-01-DEST", name="CEP079 isolated transfer destination", location=note,
    ), "Dedicated destination; no old warehouse used as a mutable target")


def payroll_source():
    from apps.payroll import services as payroll
    from apps.payroll.models import EmploymentPayConfiguration, PayrollPeriod, PayrollRule
    from apps.timekeeping import services as timekeeping
    from apps.timekeeping.models import TimesheetEntry
    employee_config = EmploymentPayConfiguration.objects.filter(organization=org, status="active").select_related("employee").get()
    prior = PayrollPeriod.objects.get(organization=org, code="WAVE-C-EXAMPLE")
    test_day = prior.ends_on + timedelta(days=1)
    assert not PayrollRule.objects.filter(organization=org, status="active", requires_statutory_authority=True).exists()
    time_actor = User.objects.get(username="uiux.wavec.time", is_active=True)
    payroll_actor = User.objects.get(username="uiux.wavec.payroll", is_active=True)
    entry = TimesheetEntry.objects.filter(organization=org, timesheet__employee=employee_config.employee).select_related("project", "site", "activity").first()
    assert entry is not None, "No approved qualified source employee/project/site/activity exemplar"
    sheet = keep(timekeeping.create_timesheet(
        organization=org, actor=time_actor, employee=employee_config.employee,
        period_start=test_day, period_end=test_day, declared_minutes=entry.minutes,
    ), "New isolated synthetic day; existing explicit employee and context links retained")
    keep(timekeeping.add_timesheet_entry(
        organization=org, actor=time_actor, timesheet=sheet, work_date=test_day,
        project=entry.project, site=entry.site, activity=entry.activity,
        minutes=entry.minutes, note=note,
    ), "Existing source quantity copied as a fictional work fact, not a rate/rule")
    timekeeping.submit_timesheet(organization=org, actor=time_actor, timesheet=sheet)
    timekeeping.review_timesheet(organization=org, actor=checker, timesheet=sheet, approve=True, reason=note)
    new_period = keep(payroll.create_period(
        organization=org, actor=payroll_actor, code="CEP079-PREP-01-PAY-PERIOD",
        name="CEP079 synthetic non-statutory day", starts_on=test_day, ends_on=test_day,
        cutoff_at=timezone.make_aware(datetime.combine(test_day, time(23, 59))),
    ), "New synthetic period within existing effective pay configuration and non-statutory rules")
    run = keep(payroll.create_run(
        organization=org, actor=payroll_actor, period=new_period, code="CEP079-PREP-01-PAY",
        idempotency_key="CEP079-PREP-01-PAY", employees=[employee_config.employee],
    ), "New run; existing payroll history remains untouched")
    from apps.payroll.timesheet_inputs import record_timesheet_input
    for rule in PayrollRule.objects.filter(organization=org, status="active"):
        if rule.evidence.get("timesheet_input_mapping"):
            keep(record_timesheet_input(
                organization=org, actor=payroll_actor, run=run, timesheet=sheet, rule=rule,
            ), "Existing approved Timesheet-to-Payroll producer; no manual quantity substitution")
    payroll.lock_run_inputs(organization=org, actor=payroll_actor, run=run)
    payroll.calculate_run(organization=org, actor=payroll_actor, run=run)
    payroll.submit_run_for_review(organization=org, actor=payroll_actor, run=run)
    payroll.approve_run(organization=org, actor=checker, run=run)
    payroll.finalize_run(organization=org, actor=checker, run=run)
    run.refresh_from_db()
    next(record for record in records if record["id"] == str(run.pk))["status"] = run.status


for name, build in [("Native cash/advance", cash_sources), ("AP source", ap_source),
                    ("Disposable fiscal close/reopen", fiscal_source),
                    ("Inventory destination", stock_destination), ("Non-statutory Payroll source", payroll_source)]:
    group(name, build)
after = snapshot()
(OUT / "REMAINING_DATA_AFTER.json").write_text(json.dumps(after), encoding="utf-8")
delta = {label: {"changed_or_missing_existing": [key for key, val in old.items() if after[label].get(key) != val], "new": [key for key in after[label] if key not in old]} for label, old in before.items()}
delta = {label: value for label, value in delta.items() if any(value.values())}
result = {"groups": outcomes, "data_changes": delta, "no_uat_scenarios_executed": True,
          "no_policy_authority_role_or_statutory_changes": True,
          "bank_gap": "No active bank account. No invented bank-to-GL mapping or changes to existing accounts.",
          "retention": "Retain identified new synthetic Development records; no raw deletion or accepted source reversal."}
(OUT / "REMAINING_STARTING_STATES.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps([{"group": g["group"], "result": g["result"], "message": g.get("message")} for g in outcomes], ensure_ascii=True))
