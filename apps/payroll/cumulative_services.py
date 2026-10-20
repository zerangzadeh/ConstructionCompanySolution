"""Operational Payroll YTD state from finalized, version-pinned result lines.

This module does not classify taxable or insurable earnings and has no statutory
rate, cap, exemption, or cross-employment authority.
"""

from __future__ import annotations

from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.payroll.models import (
    ComponentKind,
    PayrollCumulativeState,
    PayrollResultLine,
    PayrollRun,
    PayrollRunKind,
    PayrollRunStatus,
    PayrollYearInterval,
    PayrollYearStatus,
)
from apps.payroll.services import _scope
from apps.workforce.models import Employee, WorkRelationship


@transaction.atomic
def create_payroll_year_draft(
    *,
    organization: Organization,
    actor: User,
    code: str,
    starts_on: date,
    ends_on: date,
    reason: str,
) -> PayrollYearInterval:
    """Record explicit reset dates; no calendar or fiscal boundary is inferred."""
    _scope(
        BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
        organization=organization,
        actor=actor,
    )
    Organization.objects.select_for_update().get(pk=organization.pk)
    latest = (
        PayrollYearInterval.objects.filter(organization=organization, code=code.upper())
        .order_by("-version")
        .first()
    )
    previous = (
        PayrollYearInterval.objects.filter(
            organization=organization,
            code=code.upper(),
            status=PayrollYearStatus.APPROVED,
        )
        .order_by("-version")
        .first()
    )
    year = PayrollYearInterval.objects.create(
        organization=organization,
        code=code,
        version=latest.version + 1 if latest else 1,
        starts_on=starts_on,
        ends_on=ends_on,
        predecessor=previous,
        reason=reason.strip(),
        created_by=actor,
    )
    return year


@transaction.atomic
def approve_payroll_year(
    *, organization: Organization, actor: User, year: PayrollYearInterval
) -> PayrollYearInterval:
    _scope(
        BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
        organization=organization,
        actor=actor,
    )
    Organization.objects.select_for_update().get(pk=organization.pk)
    year = PayrollYearInterval.objects.select_for_update().get(
        pk=year.pk, organization=organization
    )
    if year.status != PayrollYearStatus.DRAFT:
        raise ValidationError("Only a draft Payroll year can be approved.")
    predecessor = None
    if year.predecessor_id:
        predecessor = PayrollYearInterval.objects.select_for_update().get(
            pk=year.predecessor_id, organization=organization
        )
        if predecessor.status != PayrollYearStatus.APPROVED:
            raise ValidationError("The predecessor Payroll year is not current.")
    conflict = PayrollYearInterval.objects.filter(
        organization=organization,
        status=PayrollYearStatus.APPROVED,
        starts_on__lte=year.ends_on,
        ends_on__gte=year.starts_on,
    )
    if predecessor:
        conflict = conflict.exclude(pk=predecessor.pk)
    if conflict.exists():
        raise ValidationError("An approved Payroll year already covers these dates.")
    now = timezone.now()
    if predecessor:
        predecessor.status = PayrollYearStatus.SUPERSEDED
        predecessor.superseded_at = now
        predecessor._transition_authorized = True
        try:
            predecessor.save(update_fields=["status", "superseded_at", "updated_at"])
        finally:
            del predecessor._transition_authorized
    year.status = PayrollYearStatus.APPROVED
    year.approved_by = actor
    year.approved_at = now
    year._transition_authorized = True
    try:
        year.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    finally:
        del year._transition_authorized
    record_audit_event(
        action=AuditAction.PAYROLL_YEAR_APPROVED,
        entity_type="payroll_year_interval",
        entity_id=year.pk,
        organization=organization,
        actor=actor,
        metadata={
            "code": year.code,
            "version": year.version,
            "starts_on": year.starts_on.isoformat(),
            "ends_on": year.ends_on.isoformat(),
            "predecessor_id": str(year.predecessor_id) if year.predecessor_id else None,
        },
    )
    return year


def _year_for_run(
    *, organization: Organization, run: PayrollRun
) -> PayrollYearInterval | None:
    years = list(
        PayrollYearInterval.objects.select_for_update().filter(
            organization=organization,
            status=PayrollYearStatus.APPROVED,
            starts_on__lte=run.period.starts_on,
            ends_on__gte=run.period.ends_on,
        )[:2]
    )
    if len(years) > 1:
        raise ValidationError("Payroll-year policy is ambiguous.")
    return years[0] if years else None


def _explicit_work_relationship(
    *, organization: Organization, employee: Employee, effective_on: date
) -> WorkRelationship | None:
    matches = list(
        WorkRelationship.objects.filter(
            organization=organization,
            legacy_employee=employee,
            effective_start__lte=effective_on,
        ).filter(Q(effective_end__isnull=True) | Q(effective_end__gte=effective_on))[:2]
    )
    if len(matches) > 1:
        raise ValidationError(
            "Overlapping explicit WorkRelationship links are ambiguous."
        )
    return matches[0] if matches else None


@transaction.atomic
def record_cumulative_for_run(
    *,
    organization: Organization,
    actor: User,
    run: PayrollRun,
    require_approved_year: bool = True,
) -> int:
    """Append each finalized line once; a reversal line contributes its signed inverse."""
    run = (
        PayrollRun.objects.select_for_update(of=("self",))
        .select_related("period")
        .get(pk=run.pk, organization=organization)
    )
    permission = (
        BusinessPermissionCode.PAYROLL_ADJUST
        if run.status == PayrollRunStatus.REVERSED
        or run.kind == PayrollRunKind.REVERSAL
        else BusinessPermissionCode.PAYROLL_FINALIZE
    )
    _scope(permission, organization=organization, actor=actor)
    if run.status not in {PayrollRunStatus.FINALIZED, PayrollRunStatus.REVERSED}:
        raise ValidationError("Only finalized Payroll source lines may enter YTD.")
    if not run.calculation_digest:
        raise ValidationError("Finalized Payroll source version is required.")
    year = _year_for_run(organization=organization, run=run)
    if year is None:
        if require_approved_year:
            raise ValidationError(
                "An approved versioned tenant Payroll year is required."
            )
        return 0
    lines = list(
        PayrollResultLine.objects.filter(run=run, organization=organization)
        .exclude(component_kind=ComponentKind.INFORMATIONAL)
        .select_related("run_employee__employee", "component")
        .order_by("run_employee_id", "component_id", "sequence", "pk")
    )
    created = 0
    for line in lines:
        if line.component_kind not in {
            ComponentKind.EARNING,
            ComponentKind.ALLOWANCE,
            ComponentKind.DEDUCTION,
            ComponentKind.REIMBURSEMENT,
            ComponentKind.EMPLOYER,
        }:
            raise ValidationError("An approved operational component kind is required.")
        if PayrollCumulativeState.objects.filter(year=year, source_line=line).exists():
            continue
        employee = Employee.objects.select_for_update().get(
            pk=line.run_employee.employee_id, organization=organization
        )
        opening = PayrollCumulativeState.objects.filter(
            year=year,
            employee=employee,
            component=line.component,
            opening_key__isnull=False,
            opening_evidence__reverses__isnull=True,
        ).first()
        if (
            opening
            and run.period.starts_on.isoformat()
            < opening.opening_evidence["cutover_on"]
        ):
            raise ValidationError(
                "Native Payroll overlaps the evidenced opening coverage."
            )
        previous = (
            PayrollCumulativeState.objects.filter(
                year=year, employee=employee, component=line.component
            )
            .order_by("-state_version")
            .first()
        )
        state = PayrollCumulativeState.objects.create(
            organization=organization,
            year=year,
            employee=employee,
            work_relationship=_explicit_work_relationship(
                organization=organization,
                employee=employee,
                effective_on=run.period.ends_on,
            ),
            component=line.component,
            component_kind=line.component_kind,
            state_version=previous.state_version + 1 if previous else 1,
            source_run=run,
            source_line=line,
            source_version=run.calculation_digest,
            effective_on=run.period.ends_on,
            delta=line.amount,
            balance=(previous.balance if previous else 0) + line.amount,
        )
        record_audit_event(
            action=AuditAction.PAYROLL_CUMULATIVE_RECORDED,
            entity_type="payroll_cumulative_state",
            entity_id=state.pk,
            organization=organization,
            actor=actor,
            metadata={
                "year_id": str(year.pk),
                "year_version": year.version,
                "source_run_id": str(run.pk),
                "source_line_id": str(line.pk),
                "source_version": run.calculation_digest,
                "state_version": state.state_version,
                "component_kind": state.component_kind,
                "delta": str(state.delta),
                "balance": str(state.balance),
            },
        )
        created += 1
    return created


def cumulative_balances(
    *,
    organization: Organization,
    actor: User,
    year: PayrollYearInterval,
    employee: Employee,
) -> tuple[PayrollCumulativeState, ...]:
    """Read the latest source-linked balance per component for an explicit year version."""
    _scope(
        BusinessPermissionCode.PAYROLL_RESULTS_VIEW,
        organization=organization,
        actor=actor,
    )
    if (
        year.organization_id != organization.pk
        or employee.organization_id != organization.pk
    ):
        raise PermissionDenied("Payroll cumulative read must remain tenant-scoped.")
    if year.status == PayrollYearStatus.DRAFT:
        raise ValidationError("Draft Payroll-year policy has no cumulative authority.")
    latest: dict[object, PayrollCumulativeState] = {}
    for state in PayrollCumulativeState.objects.filter(
        organization=organization, year=year, employee=employee
    ).order_by("component_id", "-state_version"):
        latest.setdefault(state.component_id, state)
    return tuple(latest.values())
