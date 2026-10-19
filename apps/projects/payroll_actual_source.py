"""INT-B08 finalized allocated Payroll evidence; no calculation or target write."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied

from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.payroll.financial_handoff_services import _digest, _source_snapshot
from apps.payroll.models import FinancialHandoffProposal, PayrollRun
from apps.timekeeping.models import Timesheet, TimesheetEntry

from .actual_sources import (
    SOURCE_MODELS,
    ActualRejected,
    NativeActualSource,
    _read_permission,
    _row,
    _same_tenant,
)
from .services import _stable_payload_hash

KEY = "pcp-payr-actual"


def read_payroll_actual(*, organization, actor, source_id) -> NativeActualSource:
    """Called inside read_native_actual's atomic snapshot/target transaction.

    A finalized/reversed historical proposal is read evidence, never authority
    to infer a date, cost class, employee mapping, partial adjustment or payment.
    """
    _read_permission(actor, organization, P.PAYROLL_RESULTS_VIEW)
    if not any(
        has_business_permission(user=actor, organization=organization, permission=code)
        for code in (
            P.PAYROLL_PROJECT_COST_HANDOFF_PREPARE,
            P.PAYROLL_PROJECT_COST_HANDOFF_REVIEW,
            P.PAYROLL_HANDOFF_RECONCILIATION_PREPARE,
            P.PAYROLL_HANDOFF_RECONCILIATION_REVIEW,
        )
    ):
        raise PermissionDenied("Payroll source-family access is required.")
    proposal = FinancialHandoffProposal.objects.select_for_update().get(
        organization=organization, pk=source_id, family="project_cost"
    )
    run = PayrollRun.objects.select_for_update().get(
        organization=organization, pk=proposal.run_id
    )
    review = proposal.review
    _same_tenant(organization, proposal, run, review, run.period)
    if (
        review.disposition != "accepted"
        or proposal.has_exceptions
        or proposal.exception_codes
    ):
        raise ActualRejected("approved_allocated_payroll_proposal_required")
    if (
        run.status not in {"finalized", "reversed"}
        or not run.finalized_at
        or not run.calculation_digest
    ):
        raise ActualRejected("finalized_payroll_source_required")
    results = list(run.employee_results.select_for_update().select_related("employee"))
    _same_tenant(organization, *results, *(item.employee for item in results))
    if not results or any(
        item.status not in {"finalized", "reversed"} for item in results
    ):
        raise ActualRejected("finalized_payroll_results_required")
    if (
        _digest(_source_snapshot(run, results)) != proposal.source_digest
        or proposal.currency != run.currency
        or proposal.monetary_policy_snapshot != run.monetary_policy_snapshot
        or proposal.precision_policy_version_id != run.precision_policy_version_id
        or proposal.rounding_policy_version_id != run.rounding_policy_version_id
    ):
        raise ActualRejected("payroll_source_version_or_policy_mismatch")
    lines = list(
        proposal.lines.select_for_update(of=("self",))
        .select_related(
            "run_employee__employee",
            "project",
            "site",
            "activity",
        )
        .order_by("pk")
    )
    if (
        not lines
        or proposal.unallocated_amount != 0
        or proposal.allocated_amount != proposal.total_amount
        or sum((line.amount for line in lines), Decimal(0)) != proposal.total_amount
    ):
        raise ActualRejected("conserved_payroll_allocation_required")
    sheets = {
        sheet.pk: sheet
        for sheet in Timesheet.objects.select_for_update()
        .filter(organization=organization, pk__in={line.timesheet_id for line in lines})
        .order_by("pk")
    }
    entries = {
        entry.pk: entry
        for entry in TimesheetEntry.objects.select_for_update()
        .filter(
            organization=organization,
            pk__in={line.timesheet_entry_id for line in lines},
        )
        .order_by("pk")
    }
    for line in lines:
        _same_tenant(organization, line, line.run_employee, line.run_employee.employee)
        _same_tenant(
            organization, *(item for item in (line.site, line.activity) if item)
        )
        if (
            line.line_kind != "project_cost_allocation"
            or line.run_employee.run_id != run.pk
            or line.employee_id != line.run_employee.employee_id
            or not line.project_id
            or not line.timesheet_id
            or not line.timesheet_entry_id
        ):
            raise ActualRejected("explicit_payroll_cost_line_required")
        sheet, entry = (
            sheets.get(line.timesheet_id),
            entries.get(line.timesheet_entry_id),
        )
        if sheet is None or entry is None:
            raise ActualRejected("payroll_approved_time_dimension_mismatch")
        _same_tenant(organization, sheet, entry, line.project)
        _read_permission(actor, organization, P.PAYROLL_RESULTS_VIEW, line.project)
        if (
            sheet.state != "approved"
            or sheet.employee_id != line.employee_id
            or sheet.period_start != run.period.starts_on
            or sheet.period_end != run.period.ends_on
            or entry.timesheet_id != sheet.pk
            or entry.project_id != line.project_id
            or entry.site_id != line.site_id
            or entry.activity_id != line.activity_id
            or (line.site_id and line.site.project_id != line.project_id)
            or (line.activity_id and line.activity.project_id != line.project_id)
            or entry.minutes != line.allocation_minutes
            or line.source_lineage.get("timesheet_revision") != sheet.revision
            or line.source_lineage.get("entry_id") != str(entry.pk)
        ):
            raise ActualRejected("payroll_approved_time_dimension_mismatch")
    operation, predecessor, prerequisite = "recognize", "", ""
    if proposal.record_kind == "reversal":
        if run.kind != "reversal" or not run.reversal_of_id:
            raise ActualRejected("explicit_payroll_inverse_required")
        predecessor = proposal.predecessor
        if predecessor is None or predecessor.run_id != run.reversal_of_id:
            raise ActualRejected("payroll_inverse_predecessor_mismatch")
        _same_tenant(organization, predecessor, predecessor.run)
        if proposal.total_amount != -predecessor.total_amount:
            raise ActualRejected("exact_payroll_inverse_required")
        operation = "reverse"
    elif proposal.record_kind == "replacement":
        predecessor = proposal.predecessor
        if (
            run.kind != "replacement"
            or predecessor is None
            or predecessor.run_id != run.replaces_id
        ):
            raise ActualRejected("explicit_payroll_replacement_required")
        _same_tenant(organization, predecessor, predecessor.run)
        inverse_run = PayrollRun.objects.get(
            organization=organization,
            pk=run.predecessor_id,
            kind="reversal",
            reversal_of_id=run.replaces_id,
            status="finalized",
        )
        prerequisite = FinancialHandoffProposal.objects.get(
            organization=organization,
            run=inverse_run,
            family="project_cost",
            record_kind="reversal",
            predecessor=predecessor,
            review__disposition="accepted",
            has_exceptions=False,
        ).pk
        operation = "replace_reversed"
    elif (
        proposal.record_kind != "original"
        or run.kind not in {"regular", "off_cycle"}
        or proposal.predecessor_id
    ):
        # No implicit treatment of signed adjustment economics as a full replacement.
        raise ActualRejected("approved_payroll_adjustment_mapping_required")
    predecessor_id = str(predecessor.pk) if predecessor else ""
    evidence = {
        "proposal": _row(proposal),
        "run": _row(run),
        "review": _row(review),
        "allocations": [_row(line) for line in lines],
        "payroll": {
            "run_id": str(run.pk),
            "calculation_digest": run.calculation_digest,
            "period_id": str(run.period_id),
            "source_digest": proposal.source_digest,
            "precision_policy_version_id": str(run.precision_policy_version_id),
            "rounding_policy_version_id": str(run.rounding_policy_version_id),
            "allocation_line_ids": [str(line.pk) for line in lines],
            "predecessor_id": predecessor_id,
            "required_reversal_source_id": str(prerequisite),
        },
    }
    return NativeActualSource(
        KEY,
        SOURCE_MODELS[KEY],
        str(proposal.pk),
        _stable_payload_hash(evidence),
        evidence,
        proposal.total_amount,
        proposal.currency,
        "",
        run.status == "finalized",
        operation,
        predecessor_id,
        str(prerequisite),
    )
