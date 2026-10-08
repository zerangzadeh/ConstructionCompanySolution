"""Prepare deterministic, tenant-valid bindings for the P10-S20 calibration only."""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")


def main() -> int:
    import django

    django.setup()
    from django.utils import timezone

    from apps.accounting.models import JournalEntry
    from apps.billing.models import BaselineItem, ProgressClaim, ProgressRecord, ProjectBaseline
    from apps.compliance.models import Inspection, InspectionTemplate
    from apps.compliance.services import create_inspection, create_template, publish_template_version
    from apps.contracts.models import Contract, ContractTermVersion
    from apps.daily_reports.field_models import FieldObservation
    from apps.daily_reports.field_services import create_field_observation
    from apps.daily_reports.models import DailyReport
    from apps.documents.models import Document, DocumentVersion
    from apps.expenses.models import Expense
    from apps.inventory.models import StockTransaction, Warehouse
    from apps.materials.models import Material
    from apps.organizations.models import (
        MembershipRole,
        MembershipStatus,
        OrganizationMembership,
        PlatformPolicyVersion,
    )
    from apps.parties.models import PartyIdentitySnapshot
    from apps.payroll.models import PayrollPeriod, PayrollRun, PayrollRunEmployee, Payslip
    from apps.procurement.models import GoodsReceipt, PurchaseOrder, PurchaseRequest
    from apps.projects.models import Activity, Project, ProjectPhase, ProjectSite
    from apps.reporting.models import MetricResult, ProjectCloseoutCase, ReconciliationRun
    from apps.reporting.services import refresh_metric
    from apps.reporting.reconciliation import execute_reconciliation
    from apps.reporting.project_closeout import create_closeout_case
    from apps.workforce.models import Employee
    from apps.workflows.models import WorkItem

    membership = (
        OrganizationMembership.objects.filter(
            status=MembershipStatus.ACTIVE,
            role=MembershipRole.COMPANY_OWNER,
            user__is_active=True,
            user__must_change_password=False,
            organization__status="active",
        )
        .select_related("organization", "user")
        .order_by("organization_id")
        .first()
    )
    if membership is None:
        raise RuntimeError("No calibration-suitable active owner membership")
    organization, actor = membership.organization, membership.user
    project = Project.objects.filter(organization=organization, deleted_at__isnull=True).first()
    site = ProjectSite.objects.filter(organization=organization, project=project, is_active=True).first()
    phase = ProjectPhase.objects.filter(organization=organization, site=site).first()
    activity = Activity.objects.filter(organization=organization, project=project).first()
    if not all((project, site, phase, activity)):
        raise RuntimeError("Project/site/phase/activity calibration relationship is incomplete")

    observation = FieldObservation.objects.filter(
        organization=organization, title="P10-S20 calibration observation"
    ).first()
    if observation is None:
        observation = create_field_observation(
            organization=organization,
            actor=actor,
            project=project,
            site=site,
            phase=phase,
            activity=activity,
            kind="work_front",
            title="P10-S20 calibration observation",
            summary="Non-certification calibration binding.",
            structured_payload={"calibration": True},
            captured_at=timezone.now(),
            operation_key=UUID("5ef2cfcc-3ac3-4cb4-8ce5-78d93362e81f"),
        )

    inspection = Inspection.objects.filter(
        organization=organization, number="P10-S20-CAL"
    ).first()
    if inspection is None:
        template = InspectionTemplate.objects.filter(
            organization=organization, code="P10-S20-CAL"
        ).first()
        if template is None:
            template = create_template(
                organization=organization,
                actor=actor,
                profile="hse",
                code="P10-S20-CAL",
                title="P10-S20 calibration template",
            )
        version = template.current_version or publish_template_version(
            organization=organization,
            actor=actor,
            template_id=str(template.pk),
            checklist=[{"id": "cal", "required": False, "type": "pass_fail"}],
            required_evidence=[],
            outcome_rules={"failed_item": "failed"},
            source_references=[{"source": "P10-S20 calibration", "version": "1"}],
        )
        inspection = create_inspection(
            organization=organization,
            actor=actor,
            project=project,
            site=site,
            profile="hse",
            number="P10-S20-CAL",
            template_version=version,
            title="P10-S20 calibration inspection",
            inspector=actor,
            operation_key=UUID("7614a67b-9e25-4a71-a430-f95e34e96d68"),
        )

    metric = MetricResult.objects.filter(organization=organization).first()
    if metric is None:
        metric = refresh_metric(
            organization=organization,
            actor=actor,
            metric_code="approved_budget",
            idempotency_key="p10-s20-calibration-metric",
            project=project,
        )
    reconciliation = ReconciliationRun.objects.filter(organization=organization).first()
    if reconciliation is None:
        reconciliation = execute_reconciliation(
            organization=organization,
            actor=actor,
            pair_code="estimate_budget",
            idempotency_key="p10-s20-calibration-reconciliation",
            project=project,
        )
    closeout = ProjectCloseoutCase.objects.filter(organization=organization, project=project).first()
    if closeout is None:
        closeout = create_closeout_case(
            organization=organization,
            actor=actor,
            project=project,
            operation_key="p10-s20-calibration-closeout",
        )

    contract = Contract.objects.filter(organization=organization, project=project).first()
    if contract is None:
        contract = Contract.objects.filter(organization=organization).select_related("project").first()
        project = contract.project
    baseline, _ = ProjectBaseline.objects.get_or_create(
        organization=organization,
        contract=contract,
        version=9001,
        defaults={
            "project": project,
            "effective_date": date(2026, 10, 7),
            "contract_value_snapshot": Decimal("1000.00"),
            "effective_ceiling": Decimal("1000.00"),
            "status": "approved",
            "approved_by": actor,
            "approved_at": timezone.now(),
            "approval_reason": "P10-S20 calibration binding",
            "created_by": actor,
            "updated_by": actor,
        },
    )
    baseline_item, _ = BaselineItem.objects.get_or_create(
        organization=organization,
        baseline=baseline,
        line_key="P10-S20-CAL",
        defaults={
            "description": "Calibration item",
            "unit": "unit",
            "planned_quantity": Decimal("10"),
            "unit_rate": Decimal("100"),
            "planned_value": Decimal("1000"),
        },
    )
    progress, _ = ProgressRecord.objects.get_or_create(
        organization=organization,
        baseline_item=baseline_item,
        source_reference="P10-S20-CAL",
        defaults={
            "baseline": baseline,
            "period_start": date(2026, 10, 1),
            "period_end": date(2026, 10, 7),
            "measured_on": date(2026, 10, 7),
            "source_type": "site_report",
            "evidence": "Calibration binding",
            "period_quantity": Decimal("1"),
            "cumulative_quantity": Decimal("1"),
            "status": "submitted",
            "submitted_by": actor,
            "submitted_at": timezone.now(),
            "created_by": actor,
            "updated_by": actor,
        },
    )
    term, _ = ContractTermVersion.objects.get_or_create(
        organization=organization,
        contract=contract,
        version=9001,
        defaults={
            "effective_from": date(2026, 10, 1),
            "status": "approved",
            "reason": "P10-S20 calibration binding",
            "created_by": actor,
            "approved_by": actor,
            "approved_at": timezone.now(),
            "approval_reason": "Calibration only",
        },
    )
    policy = PlatformPolicyVersion.objects.filter(status="published").first()
    identity = PartyIdentitySnapshot.objects.filter(organization=organization).first()
    if policy is None or identity is None:
        raise RuntimeError("Existing policy/party identity calibration source is unavailable")
    claim, _ = ProgressClaim.objects.get_or_create(
        organization=organization,
        contract=contract,
        claim_number=9001,
        revision_number=1,
        defaults={
            "project": project,
            "baseline": baseline,
            "period_start": date(2026, 10, 1),
            "period_end": date(2026, 10, 7),
            "measurement_cutoff": date(2026, 10, 7),
            "contract_term_version": term,
            "regulatory_rule_version": policy,
            "party_identity_snapshot": identity,
            "currency_code": "IRR",
            "gross_amount": Decimal("100"),
            "net_amount": Decimal("100"),
            "created_by": actor,
            "updated_by": actor,
        },
    )

    employee = Employee.objects.filter(organization=organization).first()
    payroll_period, _ = PayrollPeriod.objects.get_or_create(
        organization=organization,
        code="P10-S20-CAL",
        defaults={
            "name": "P10-S20 calibration",
            "starts_on": date(2026, 10, 1),
            "ends_on": date(2026, 10, 7),
            "cutoff_at": timezone.now(),
            "created_by": actor,
        },
    )
    payroll_run, _ = PayrollRun.objects.get_or_create(
        organization=organization,
        code="P10-S20-CAL",
        defaults={
            "period": payroll_period,
            "idempotency_key": "p10-s20-calibration-payroll",
            "created_by": actor,
            "currency": "IRR",
        },
    )
    run_employee, _ = PayrollRunEmployee.objects.get_or_create(
        organization=organization,
        run=payroll_run,
        employee=employee,
        defaults={"status": "calculated", "gross_amount": 100, "net_amount": 100},
    )
    payslip, _ = Payslip.objects.get_or_create(
        organization=organization,
        run_employee=run_employee,
        defaults={
            "run": payroll_run,
            "number": "P10-S20-CAL",
            "issued_at": timezone.now(),
            "content_digest": "0" * 64,
            "presentation_snapshot": {"calibration": True},
        },
    )

    purchase_request = PurchaseRequest.objects.filter(organization=organization).first()
    purchase_order = PurchaseOrder.objects.filter(organization=organization).first()
    receipt = GoodsReceipt.objects.filter(organization=organization).first()
    warehouse = Warehouse.objects.filter(organization=organization).first()
    stock_transaction = StockTransaction.objects.filter(organization=organization).first()
    daily_report = DailyReport.objects.filter(organization=organization).first()
    document = Document.objects.filter(organization=organization).first()
    version = DocumentVersion.objects.filter(document=document).first()
    expense = Expense.objects.filter(organization=organization).first()
    journal = JournalEntry.objects.filter(organization=organization).first()
    work_item = WorkItem.objects.filter(organization=organization).order_by("created_at").first()
    material = Material.objects.filter(organization=organization).first()
    required = [purchase_request, purchase_order, receipt, warehouse, stock_transaction, daily_report, document, version, expense, journal, work_item, material]
    if any(item is None for item in required):
        raise RuntimeError("An existing frozen-candidate binding source is unavailable")

    bindings = {
        "membership_id": str(membership.pk),
        "organization_id": str(organization.pk),
        "user_id": str(actor.pk),
        "objects": {
            "project_id": str(project.pk), "site_id": str(site.pk), "phase_id": str(phase.pk),
            "activity_id": str(activity.pk), "request_id": str(purchase_request.pk),
            "order_id": str(purchase_order.pk), "receipt_id": str(receipt.pk),
            "warehouse_id": str(warehouse.pk), "transaction_id": str(stock_transaction.pk),
            "observation_id": str(observation.pk), "report_id": str(daily_report.pk),
            "record_id": str(inspection.pk), "document_id": str(document.pk),
            "version_id": str(version.pk), "expense_id": str(expense.pk),
            "work_item_id": str(work_item.pk), "record_progress_id": str(progress.pk),
            "claim_id": str(claim.pk), "baseline_id": str(baseline.pk),
            "journal_id": str(journal.pk), "run_id": str(payroll_run.pk),
            "payslip_id": str(payslip.pk), "result_id": str(metric.pk),
            "reconciliation_run_id": str(reconciliation.pk), "case_id": str(closeout.pk),
            "material_id": str(material.pk),
        },
    }
    output = ROOT / "output" / "p10_s20_calibration" / "calibration_bindings.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bindings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
