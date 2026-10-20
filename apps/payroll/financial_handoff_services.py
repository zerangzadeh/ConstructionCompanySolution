from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Decimal,
)
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.timekeeping.models import Timesheet, TimesheetState

from .models import (
    FinancialHandoffAcknowledgement,
    FinancialHandoffFamily,
    FinancialHandoffLine,
    FinancialHandoffProposal,
    FinancialHandoffReconciliation,
    FinancialHandoffReconciliationReview,
    FinancialHandoffRecordKind,
    FinancialHandoffReview,
    PayrollRun,
    PayrollRunKind,
    PayrollRunStatus,
    ResultStatus,
    StatutoryReviewDisposition,
)
from .services import _locked_monetary_policies

PREPARE_PERMISSIONS = {
    FinancialHandoffFamily.LIABILITY: BusinessPermissionCode.PAYROLL_LIABILITY_HANDOFF_PREPARE,
    FinancialHandoffFamily.ACCOUNTING: BusinessPermissionCode.PAYROLL_ACCOUNTING_HANDOFF_PREPARE,
    FinancialHandoffFamily.PAYMENT: BusinessPermissionCode.PAYROLL_PAYMENT_HANDOFF_PREPARE,
    FinancialHandoffFamily.PROJECT_COST: BusinessPermissionCode.PAYROLL_PROJECT_COST_HANDOFF_PREPARE,
}
REVIEW_PERMISSIONS = {
    FinancialHandoffFamily.LIABILITY: BusinessPermissionCode.PAYROLL_LIABILITY_HANDOFF_REVIEW,
    FinancialHandoffFamily.ACCOUNTING: BusinessPermissionCode.PAYROLL_ACCOUNTING_HANDOFF_REVIEW,
    FinancialHandoffFamily.PAYMENT: BusinessPermissionCode.PAYROLL_PAYMENT_HANDOFF_REVIEW,
    FinancialHandoffFamily.PROJECT_COST: BusinessPermissionCode.PAYROLL_PROJECT_COST_HANDOFF_REVIEW,
}
ROUNDING = {
    "half_up": ROUND_HALF_UP,
    "half_even": ROUND_HALF_EVEN,
    "half_down": ROUND_HALF_DOWN,
    "up": ROUND_UP,
    "down": ROUND_DOWN,
    "ceiling": ROUND_CEILING,
    "floor": ROUND_FLOOR,
}


@dataclass(frozen=True)
class LineSpec:
    run_employee: Any
    line_kind: str
    amount: Decimal
    payee_reference: str = ""
    component_reference: str = ""
    result_line: Any = None
    statutory_result: Any = None
    timesheet: Any = None
    timesheet_entry: Any = None
    project: Any = None
    site: Any = None
    activity: Any = None
    allocation_minutes: int | None = None
    lineage: dict[str, Any] | None = None


def _require(*, actor: User, organization: Organization, permission: str) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اجازه این عملیات تحویل مالی حقوق را ندارید.",
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode()
    ).hexdigest()


def _source_snapshot(run: PayrollRun, results: list[Any]) -> dict[str, Any]:
    return {
        "run_id": str(run.pk),
        "run_code": run.code,
        "run_kind": run.kind,
        "run_calculation_digest": run.calculation_digest,
        "run_finalized_at": run.finalized_at.isoformat() if run.finalized_at else None,
        "period_id": str(run.period_id),
        "period_start": run.period.starts_on.isoformat(),
        "period_end": run.period.ends_on.isoformat(),
        "currency": run.currency,
        "precision_policy_version_id": str(run.precision_policy_version_id),
        "rounding_policy_version_id": str(run.rounding_policy_version_id),
        "monetary_policy_snapshot": run.monetary_policy_snapshot,
        "results": [
            {
                "result_id": str(item.pk),
                "employee_id": str(item.employee_id),
                "gross": str(item.gross_amount),
                "deduction": str(item.deduction_amount),
                "reimbursement": str(item.reimbursement_amount),
                "employer": str(item.employer_amount),
                "net": str(item.net_amount),
            }
            for item in results
        ],
    }


def _lineage(
    run: PayrollRun, family: str
) -> tuple[str, FinancialHandoffProposal | None]:
    source_run_id = None
    record_kind = FinancialHandoffRecordKind.ORIGINAL
    if run.kind == PayrollRunKind.REVERSAL:
        source_run_id, record_kind = (
            run.reversal_of_id,
            FinancialHandoffRecordKind.REVERSAL,
        )
    elif run.kind == PayrollRunKind.REPLACEMENT:
        source_run_id, record_kind = (
            run.replaces_id,
            FinancialHandoffRecordKind.REPLACEMENT,
        )
    elif run.predecessor_id:
        source_run_id, record_kind = (
            run.predecessor_id,
            FinancialHandoffRecordKind.CORRECTION,
        )
    if not source_run_id:
        return record_kind, None
    predecessor = FinancialHandoffProposal.objects.filter(
        organization_id=run.organization_id, family=family, run_id=source_run_id
    ).first()
    if predecessor is None:
        raise ValidationError(
            "پیشنهاد پیشین برای زنجیره اصلاح/برگشت/جایگزین موجود نیست."
        )
    return record_kind, predecessor


def _statutory_liability_lines(run: PayrollRun) -> tuple[list[LineSpec], list[str]]:
    lines: list[LineSpec] = []
    exceptions: list[str] = []
    calculations = (
        run.statutory_calculations.filter(
            review__disposition=StatutoryReviewDisposition.ACCEPTED
        )
        .select_related("review")
        .prefetch_related("employee_results__run_employee__employee")
    )
    for calculation in calculations:
        for item in calculation.employee_results.all():
            for label, amount in (
                ("statutory_employee_payable", item.employee_amount),
                (
                    "statutory_employer_payable",
                    item.employer_amount + item.other_amount,
                ),
            ):
                if amount == 0:
                    continue
                lines.append(
                    LineSpec(
                        run_employee=item.run_employee,
                        line_kind=label,
                        amount=amount,
                        statutory_result=item,
                        component_reference=f"{calculation.kind}:v{calculation.revision}",
                        lineage={
                            "calculation_id": str(calculation.pk),
                            "policy_version_id": str(calculation.policy_version_id),
                            "source_digest": item.source_digest,
                        },
                    )
                )
                exceptions.append("MISSING_STATUTORY_PAYEE_AUTHORITY")
    return lines, exceptions


def _project_cost_lines(
    run: PayrollRun, results: list[Any]
) -> tuple[list[LineSpec], list[str]]:
    lines: list[LineSpec] = []
    exceptions: list[str] = []
    quantum = Decimal(str(run.monetary_policy_snapshot["final_quantum"]))
    rounding = ROUNDING.get(
        str(run.monetary_policy_snapshot["rounding_method"]).lower(), ROUND_HALF_UP
    )
    for result in results:
        cost = result.gross_amount + result.employer_amount
        timesheet = (
            Timesheet.objects.select_for_update()
            .filter(
                organization=run.organization,
                employee=result.employee,
                period_start=run.period.starts_on,
                period_end=run.period.ends_on,
                state=TimesheetState.APPROVED,
            )
            .prefetch_related("entries__project", "entries__site", "entries__activity")
            .first()
        )
        entries = list(timesheet.entries.all()) if timesheet else []
        minutes = sum(item.minutes for item in entries)
        if (
            not timesheet
            or not entries
            or minutes != timesheet.declared_minutes
            or minutes <= 0
        ):
            exceptions.append("UNALLOCATED_LABOR_COST")
            lines.append(
                LineSpec(
                    run_employee=result,
                    line_kind="project_cost_unallocated",
                    amount=cost,
                    payee_reference=result.employee.employee_number,
                    lineage={"reason": "missing_or_inconsistent_approved_timesheet"},
                )
            )
            continue
        remaining = cost
        for index, entry in enumerate(entries):
            amount = (
                remaining
                if index == len(entries) - 1
                else (cost * Decimal(entry.minutes) / Decimal(minutes)).quantize(
                    quantum, rounding=rounding
                )
            )
            remaining -= amount
            lines.append(
                LineSpec(
                    run_employee=result,
                    line_kind="project_cost_allocation",
                    amount=amount,
                    payee_reference=result.employee.employee_number,
                    timesheet=timesheet,
                    timesheet_entry=entry,
                    project=entry.project,
                    site=entry.site,
                    activity=entry.activity,
                    allocation_minutes=entry.minutes,
                    lineage={
                        "timesheet_id": str(timesheet.pk),
                        "timesheet_revision": timesheet.revision,
                        "entry_id": str(entry.pk),
                        "minutes": entry.minutes,
                    },
                )
            )
    return lines, exceptions


@transaction.atomic
def prepare_financial_handoff(
    *,
    organization: Organization,
    actor: User,
    run: PayrollRun,
    family: str,
    idempotency_key: str,
    reason: str,
    proposed_accounting_date=None,
    mapping_reference: str = "",
) -> FinancialHandoffProposal:
    if family not in FinancialHandoffFamily.values:
        raise ValidationError("خانواده تحویل مالی معتبر نیست.")
    _require(
        actor=actor, organization=organization, permission=PREPARE_PERMISSIONS[family]
    )
    try:
        run = (
            PayrollRun.objects.select_for_update()
            .select_related("period")
            .get(pk=run.pk, organization=organization)
        )
    except PayrollRun.DoesNotExist as exc:
        raise PermissionDenied("اجرای حقوق متعلق به این Tenant نیست.") from exc
    if run.status != PayrollRunStatus.FINALIZED or not run.finalized_at:
        raise ValidationError("فقط اجرای قطعی حقوق منبع تحویل مالی است.")
    _locked_monetary_policies(run)
    results = list(
        run.employee_results.select_for_update()
        .select_related("employee")
        .prefetch_related("lines__component")
    )
    if not results or any(item.status != ResultStatus.FINALIZED for item in results):
        raise ValidationError("همه نتایج کارکنان باید قطعی باشند.")
    snapshot = _source_snapshot(run, results)
    source_digest = _digest(snapshot)
    existing = FinancialHandoffProposal.objects.filter(
        organization=organization, family=family, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.run_id == run.pk and existing.source_digest == source_digest:
            return existing
        raise ValidationError("کلید تکرارناپذیری با منبع دیگری استفاده شده است.")
    if FinancialHandoffProposal.objects.filter(
        organization=organization, family=family, run=run
    ).exists():
        raise ValidationError("برای این منبع و خانواده قبلاً پیشنهاد ثبت شده است.")
    record_kind, predecessor = _lineage(run, family)
    specs: list[LineSpec] = []
    exceptions: list[str] = []
    if family in {FinancialHandoffFamily.LIABILITY, FinancialHandoffFamily.PAYMENT}:
        line_kind = (
            "employee_payable"
            if family == FinancialHandoffFamily.LIABILITY
            else "payment_proposal"
        )
        for result in results:
            payee = result.employee.employee_number.strip()
            if not payee:
                exceptions.append("MISSING_PAYEE_IDENTITY")
            specs.append(
                LineSpec(
                    run_employee=result,
                    line_kind=line_kind,
                    amount=result.net_amount,
                    payee_reference=payee,
                    project=result.project if family == FinancialHandoffFamily.PAYMENT else None,
                    site=result.site if family == FinancialHandoffFamily.PAYMENT else None,
                    lineage={
                        "result_id": str(result.pk),
                        "calculation_digest": run.calculation_digest,
                    },
                )
            )
        if family == FinancialHandoffFamily.LIABILITY:
            statutory, statutory_exceptions = _statutory_liability_lines(run)
            specs.extend(statutory)
            exceptions.extend(statutory_exceptions)
    elif family == FinancialHandoffFamily.ACCOUNTING:
        for result in results:
            for line in result.lines.all():
                specs.append(
                    LineSpec(
                        run_employee=result,
                        line_kind="accounting_source",
                        amount=line.amount,
                        component_reference=line.component.code,
                        result_line=line,
                        lineage={
                            "result_line_id": str(line.pk),
                            "component_id": str(line.component_id),
                            "rule_version": line.rule_version,
                        },
                    )
                )
        if not mapping_reference.strip():
            exceptions.append("ACCOUNT_MAPPING_NOT_CONFIGURED")
    else:
        specs, exceptions = _project_cost_lines(run, results)
    total = sum((item.amount for item in specs), Decimal(0))
    unallocated = sum(
        (item.amount for item in specs if item.line_kind == "project_cost_unallocated"),
        Decimal(0),
    )
    proposal = FinancialHandoffProposal.objects.create(
        organization=organization,
        family=family,
        run=run,
        record_kind=record_kind,
        predecessor=predecessor,
        idempotency_key=idempotency_key.strip(),
        source_digest=source_digest,
        currency=run.currency,
        precision_policy_version=run.precision_policy_version,
        rounding_policy_version=run.rounding_policy_version,
        monetary_policy_snapshot=run.monetary_policy_snapshot,
        proposed_accounting_date=proposed_accounting_date
        if family == FinancialHandoffFamily.ACCOUNTING
        else None,
        mapping_reference=mapping_reference.strip()
        if family == FinancialHandoffFamily.ACCOUNTING
        else "",
        total_amount=total,
        allocated_amount=total - unallocated,
        unallocated_amount=unallocated,
        has_exceptions=bool(exceptions),
        exception_codes=sorted(set(exceptions)),
        source_snapshot=snapshot,
        reason=reason.strip(),
        prepared_by=actor,
    )
    for index, spec in enumerate(specs):
        lineage = spec.lineage or {}
        digest = _digest(
            {
                "proposal": str(proposal.pk),
                "index": index,
                "kind": spec.line_kind,
                "amount": str(spec.amount),
                "lineage": lineage,
            }
        )
        FinancialHandoffLine.objects.create(
            organization=organization,
            proposal=proposal,
            run_employee=spec.run_employee,
            employee=spec.run_employee.employee,
            result_line=spec.result_line,
            statutory_result=spec.statutory_result,
            timesheet=spec.timesheet,
            timesheet_entry=spec.timesheet_entry,
            project=spec.project,
            site=spec.site,
            activity=spec.activity,
            line_kind=spec.line_kind,
            payee_reference=spec.payee_reference,
            component_reference=spec.component_reference,
            amount=spec.amount,
            allocation_minutes=spec.allocation_minutes,
            source_lineage=lineage,
            content_digest=digest,
        )
    record_audit_event(
        action=AuditAction.PAYROLL_FINANCIAL_HANDOFF_PREPARED,
        entity_type="payroll.FinancialHandoffProposal",
        entity_id=proposal.pk,
        organization=organization,
        actor=actor,
        metadata={
            "family": family,
            "run_id": str(run.pk),
            "source_digest": source_digest,
            "has_exceptions": proposal.has_exceptions,
        },
    )
    return proposal


@transaction.atomic
def review_financial_handoff(
    *,
    organization: Organization,
    actor: User,
    proposal: FinancialHandoffProposal,
    disposition: str,
    reason: str,
) -> FinancialHandoffReview:
    proposal = FinancialHandoffProposal.objects.select_for_update().get(
        pk=proposal.pk, organization=organization
    )
    _require(
        actor=actor,
        organization=organization,
        permission=REVIEW_PERMISSIONS[proposal.family],
    )
    if disposition not in {"accepted", "rejected"} or not reason.strip():
        raise ValidationError("نتیجه و دلیل بررسی الزامی است.")
    review = FinancialHandoffReview.objects.create(
        organization=organization,
        proposal=proposal,
        disposition=disposition,
        reason=reason.strip(),
        reviewed_by=actor,
        reviewed_at=timezone.now(),
    )
    record_audit_event(
        action=AuditAction.PAYROLL_FINANCIAL_HANDOFF_REVIEWED,
        entity_type="payroll.FinancialHandoffReview",
        entity_id=review.pk,
        organization=organization,
        actor=actor,
        metadata={
            "proposal_id": str(proposal.pk),
            "family": proposal.family,
            "disposition": disposition,
        },
    )
    return review


@transaction.atomic
def record_handoff_acknowledgement(
    *,
    organization: Organization,
    actor: User,
    proposal: FinancialHandoffProposal,
    downstream_reference: str,
    downstream_status: str,
    acknowledged_source_digest: str,
    acknowledged_amount: Decimal,
    evidence: dict[str, Any] | None = None,
) -> FinancialHandoffAcknowledgement:
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_PREPARE,
    )
    proposal = FinancialHandoffProposal.objects.select_for_update().get(
        pk=proposal.pk, organization=organization
    )
    acknowledgement = FinancialHandoffAcknowledgement.objects.create(
        organization=organization,
        proposal=proposal,
        downstream_reference=downstream_reference.strip(),
        downstream_status=downstream_status.strip(),
        acknowledged_source_digest=acknowledged_source_digest,
        acknowledged_amount=acknowledged_amount,
        evidence=evidence or {},
        recorded_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYROLL_FINANCIAL_HANDOFF_ACKNOWLEDGED,
        entity_type="payroll.FinancialHandoffAcknowledgement",
        entity_id=acknowledgement.pk,
        organization=organization,
        actor=actor,
        metadata={
            "proposal_id": str(proposal.pk),
            "downstream_reference": downstream_reference,
        },
    )
    return acknowledgement


@transaction.atomic
def reconcile_financial_handoff(
    *,
    organization: Organization,
    actor: User,
    proposal: FinancialHandoffProposal,
    acknowledgement: FinancialHandoffAcknowledgement | None = None,
) -> FinancialHandoffReconciliation:
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_PREPARE,
    )
    proposal = (
        FinancialHandoffProposal.objects.select_for_update()
        .select_related("run__period")
        .get(pk=proposal.pk, organization=organization)
    )
    issues: list[str] = []
    current_results = list(proposal.run.employee_results.select_related("employee"))
    if (
        _digest(_source_snapshot(proposal.run, current_results))
        != proposal.source_digest
    ):
        issues.append("STALE_SOURCE")
    if (
        FinancialHandoffProposal.objects.filter(
            organization=organization, family=proposal.family, run=proposal.run
        )
        .exclude(pk=proposal.pk)
        .exists()
    ):
        issues.append("DUPLICATE_PROPOSAL")
    if (
        proposal.record_kind != FinancialHandoffRecordKind.ORIGINAL
        and not proposal.predecessor_id
    ):
        issues.append("REVERSAL_REPLACEMENT_MISMATCH")
    line_total = sum(proposal.lines.values_list("amount", flat=True), Decimal(0))
    if line_total != proposal.total_amount:
        issues.append("AMOUNT_MISMATCH")
    if proposal.family == FinancialHandoffFamily.PROJECT_COST:
        allocated = sum(
            proposal.lines.exclude(line_kind="project_cost_unallocated").values_list(
                "amount", flat=True
            ),
            Decimal(0),
        )
        unallocated = sum(
            proposal.lines.filter(line_kind="project_cost_unallocated").values_list(
                "amount", flat=True
            ),
            Decimal(0),
        )
        if (
            allocated != proposal.allocated_amount
            or unallocated != proposal.unallocated_amount
        ):
            issues.append("ALLOCATION_MISMATCH")
        duplicated_entries = (
            FinancialHandoffLine.objects.filter(
                organization=organization,
                proposal__family=FinancialHandoffFamily.PROJECT_COST,
                timesheet_entry__isnull=False,
                timesheet_entry_id__in=proposal.lines.filter(
                    timesheet_entry__isnull=False
                ).values("timesheet_entry_id"),
            )
            .exclude(proposal=proposal)
            .exists()
        )
        if duplicated_entries:
            issues.append("DOUBLE_COUNTING_RISK")
    if acknowledgement is None:
        issues.append("MISSING_DOWNSTREAM_ACKNOWLEDGEMENT")
        observed = None
    else:
        acknowledgement = FinancialHandoffAcknowledgement.objects.get(
            pk=acknowledgement.pk, organization=organization, proposal=proposal
        )
        observed = acknowledgement.acknowledged_amount
        if acknowledgement.acknowledged_source_digest != proposal.source_digest:
            issues.append("SOURCE_RESULT_MISMATCH")
        if observed != proposal.total_amount:
            issues.append("AMOUNT_MISMATCH")
    reconciliation = FinancialHandoffReconciliation.objects.create(
        organization=organization,
        proposal=proposal,
        acknowledgement=acknowledgement,
        status="exception" if issues else "matched",
        issue_codes=sorted(set(issues)),
        expected_amount=proposal.total_amount,
        observed_amount=observed,
        evidence={
            "source_digest": proposal.source_digest,
            "line_total": str(line_total),
        },
        prepared_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYROLL_FINANCIAL_HANDOFF_RECONCILED,
        entity_type="payroll.FinancialHandoffReconciliation",
        entity_id=reconciliation.pk,
        organization=organization,
        actor=actor,
        metadata={
            "proposal_id": str(proposal.pk),
            "status": reconciliation.status,
            "issue_codes": reconciliation.issue_codes,
        },
    )
    return reconciliation


@transaction.atomic
def review_handoff_reconciliation(
    *,
    organization: Organization,
    actor: User,
    reconciliation: FinancialHandoffReconciliation,
    disposition: str,
    reason: str,
) -> FinancialHandoffReconciliationReview:
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYROLL_HANDOFF_RECONCILIATION_REVIEW,
    )
    reconciliation = FinancialHandoffReconciliation.objects.select_for_update().get(
        pk=reconciliation.pk, organization=organization
    )
    if disposition not in {"accepted", "rejected"} or not reason.strip():
        raise ValidationError("نتیجه و دلیل بررسی تطبیق الزامی است.")
    return FinancialHandoffReconciliationReview.objects.create(
        organization=organization,
        reconciliation=reconciliation,
        disposition=disposition,
        reason=reason.strip(),
        reviewed_by=actor,
        reviewed_at=timezone.now(),
    )
