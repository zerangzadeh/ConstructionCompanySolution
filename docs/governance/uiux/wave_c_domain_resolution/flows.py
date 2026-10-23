"""Canonical synthetic Development journeys for PD-WC-D01..05; no role edits."""
from configure import *  # noqa: F403
from decimal import Decimal

from django.db.models import Sum
from apps.accounting.models import FiscalPeriod
from apps.accounting.reporting import retain_statement
from apps.commercial.models import TenderBid
from apps.commercial.services import create_tender_bid, transition_tender_bid
from apps.payroll import services as payroll
from apps.payroll.financial_handoff_services import prepare_financial_handoff
from apps.payroll.models import PayrollRun, PayrollRule
from apps.payroll.timesheet_inputs import record_timesheet_input
from apps.procurement.models import PurchaseOrder, GoodsReceiptItem
from apps.subledgers.models import SupplierInvoiceVersion, Obligation, SettlementAllocation
from apps.subledgers.services import prepare_supplier_invoice, submit_supplier_invoice, decide_supplier_invoice, run_supplier_invoice_match, allocate_settlement
from apps.subledgers.supplier_invoice_handoffs import handoff_supplier_invoice_match
from apps.timekeeping import services as timekeeping
from apps.timekeeping.models import Timesheet
from apps.treasury.models import TreasuryMovement
from apps.treasury.services import create_movement, submit_movement, approve_and_post_movement


def flows():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    org = Organization.objects.get(slug="demo-construction-01")
    maker = User.objects.get(username="account.demo-construction-01.accountant")
    checker = User.objects.get(username="account.demo-construction-01.owner")
    member = org.memberships.get(user=maker)
    today = timezone.localdate()
    period = FiscalPeriod.objects.get(organization=org, status="open", starts_on__lte=today, ends_on__gte=today)
    with transaction.atomic():
        # Reuse an explicitly labelled Development receipt; do not edit its PO or stock.
        order = PurchaseOrder.objects.get(organization=org, order_number="B05-RUNTIME-PO-A")
        lines = []
        for line in order.current_version.lines.all():
            accepted = GoodsReceiptItem.objects.filter(purchase_order_item=line.source_item, goods_receipt__status="posted").aggregate(total=Sum("quantity"))["total"]
            assert accepted and accepted <= line.quantity
            lines.append({"kind": "goods", "purchase_order_version_line": line, "quantity": accepted, "unit_price": line.unit_price, "description": LABEL})
        invoice = SupplierInvoiceVersion.objects.filter(organization=org, idempotency_key="wcd-invoice").first()
        if invoice is None:
            invoice = prepare_supplier_invoice(organization=org, actor=maker, supplier=order.supplier, project=order.project, invoice_number="WCD-INV", invoice_date=today, due_date=today, lines=lines, idempotency_key="wcd-invoice")
            submit_supplier_invoice(organization=org, actor=maker, invoice_version=invoice)
            decide_supplier_invoice(organization=org, actor=checker, invoice_version=invoice, approve=True, reason=LABEL)
        match = run_supplier_invoice_match(organization=org, actor=maker, invoice_version=invoice, idempotency_key="wcd-match")
        assert match.status == "matched"
        obligation = handoff_supplier_invoice_match(organization=org, actor=maker, match=match, idempotency_key="wcd-ap")
        cash = TreasuryAccount.objects.get(organization=org, code="WCD-CASH")
        movements = {}
        for kind, amount in [("receipt", obligation.original_amount * 2), ("disbursement", obligation.original_amount)]:
            key = "wcd-" + kind
            movement = TreasuryMovement.objects.filter(organization=org, idempotency_key=key).first()
            if movement is None:
                movement = create_movement(organization=org, actor=maker, kind=kind, movement_date=today, amount=amount, description=LABEL, idempotency_key=key, account=cash, project=order.project, party=order.supplier if kind == "disbursement" else None)
                submit_movement(organization=org, actor=maker, movement=movement, reason=LABEL)
                movement = approve_and_post_movement(organization=org, actor=checker, movement=movement, accounting_preparer=member, period=period, reason=LABEL)
            movements[kind] = movement
        allocation = allocate_settlement(organization=org, actor=maker, obligation=obligation, movement=movements["disbursement"], amount=obligation.original_amount / 2, effective_date=today, reason=LABEL, idempotency_key="wcd-partial-allocation")
        statement = retain_statement(organization=org, actor=maker, kind="trial_balance", ends_on=today)
        result = {"label": LABEL, "invoice": str(invoice.pk), "match": str(match.pk), "obligation": str(obligation.pk), "movement": str(movements["disbursement"].pk), "allocation": str(allocation.pk), "statement": str(statement.pk), "posted_statement_source_lines": statement.source_line_count}
    save("FINANCIAL_FLOW.json", result)

    with transaction.atomic():
        actor = User.objects.get(username="uiux.wavec.commercial")
        tender = TenderBid.objects.filter(organization=org, opportunity_code="WCD-TENDER").first()
        if tender is None:
            tender = create_tender_bid(organization=org, actor=actor, opportunity_code="WCD-TENDER", title="نمونه توسعه — ثبت وضعیت مناقصه", description=LABEL, project=order.project, reason=LABEL)
            for state in ["submitted", "under_review", "lost"]:
                transition_tender_bid(organization=org, actor=actor, tender_id=tender.pk, target=state, reason=LABEL, submission_reference="WCD-SYNTHETIC-SUBMISSION", result_reference="WCD-SYNTHETIC-RECORDED-OUTCOME")
    save("TENDER_FLOW.json", {"tender": str(tender.pk), "label": LABEL, "no_award_or_contract_effect": True})

    with transaction.atomic():
        actor = User.objects.get(username="uiux.wavec.payroll")
        run = PayrollRun.objects.get(organization=org, code="WAVE-C-EXAMPLE")
        if run.status == "draft":
            payroll.lock_run_inputs(organization=org, actor=actor, run=run)
            payroll.calculate_run(organization=org, actor=actor, run=run)
            payroll.submit_run_for_review(organization=org, actor=actor, run=run)
            payroll.approve_run(organization=org, actor=checker, run=run)
            payroll.finalize_run(organization=org, actor=checker, run=run)
        proposals = {}
        for family in ["liability", "accounting", "payment"]:
            proposal = prepare_financial_handoff(organization=org, actor=actor, run=run, family=family, idempotency_key="wcd-handoff-" + family, reason=LABEL)
            proposals[family] = {"id": str(proposal.pk), "exceptions": proposal.exception_codes}
        employee = run.employee_results.get().employee
        config = employee.pay_configurations.filter(status="active").first() if hasattr(employee, "pay_configurations") else None
        # Existing approved Development employment configuration declares 1 IRR/hour.
        from apps.payroll.models import EmploymentPayConfiguration
        config = EmploymentPayConfiguration.objects.get(organization=org, employee=employee, status="active")
        assert config.rate_unit == "hour" and config.base_rate == Decimal("1")
        time_actor = User.objects.get(username="uiux.wavec.time")
        sheet = Timesheet.objects.filter(organization=org, employee=employee, period_start=run.period.starts_on, period_end=run.period.ends_on).first()
        if sheet is None:
            sheet = timekeeping.create_timesheet(organization=org, actor=time_actor, employee=employee, period_start=run.period.starts_on, period_end=run.period.ends_on, declared_minutes=60)
            timekeeping.add_timesheet_entry(organization=org, actor=time_actor, timesheet=sheet, work_date=run.period.ends_on, project=order.project, minutes=60, note=LABEL)
            timekeeping.submit_timesheet(organization=org, actor=time_actor, timesheet=sheet)
            timekeeping.review_timesheet(organization=org, actor=checker, timesheet=sheet, approve=True, reason=LABEL)
        rule = PayrollRule.objects.filter(organization=org, code="WCD-TIMESHEET").first()
        if rule is None:
            component = payroll.create_component(organization=org, actor=actor, code="WCD-TIME", name="کارکرد نمونه توسعه", kind="earning", net_effect="add")
            rule = payroll.create_rule(organization=org, actor=actor, component=component, code="WCD-TIMESHEET", name="کارکرد تأییدشده با نرخ موجود", sequence=20, method="quantity_times_rate", rate_source="employment", effective_from=today, source_reference="PD-WC-D02 " + LABEL, evidence={"classification": LABEL, "timesheet_input_mapping": {"version": 1, "quantity_unit": "hour"}})
            payroll.activate_rule(organization=org, actor=actor, rule=rule)
        variable = payroll.create_run(organization=org, actor=actor, period=run.period, code="WCD-VARIABLE", kind="off_cycle", idempotency_key="wcd-variable", employees=[employee])
        item = record_timesheet_input(organization=org, actor=actor, run=variable, timesheet=sheet, rule=rule)
    save("PAYROLL_FLOW.json", {"fixed_run": str(run.pk), "variable_run": str(variable.pk), "timesheet": str(sheet.pk), "rule": str(rule.pk), "input": str(item.pk), "quantity": str(item.quantity), "unit": "hour", "rate_from_existing_configuration": True, "proposals": proposals, "statutory_successful_output": "OUT_OF_WAVE_C_UNVALIDATED_PD-WC-D03"})
    print("Canonical Financial, Tender and Payroll flows complete")


if __name__ == "__main__":
    flows()
