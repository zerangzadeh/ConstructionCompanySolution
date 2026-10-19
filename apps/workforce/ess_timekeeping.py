"""Own ESS orchestration; source domains retain every state and calculation."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.timekeeping import services as source
from apps.timekeeping.models import (
    AttendanceCorrectionRequest,
    AttendanceRecord,
    LeaveMissionRequest,
    OvertimeRequest,
    Timesheet,
)

from . import leave_services
from .ess_services import resolve_ess_subject
from .leave_models import LeavePolicyVersion
from .models import EmployeeProjectAssignment

DENIED = "اطلاعات مجاز در این شرکت یافت نشد."
SOURCES = {
    "leave": (LeaveMissionRequest, "employee", P.LEAVE_MISSION_VIEW),
    "attendance": (AttendanceRecord, "employee", P.ATTENDANCE_VIEW),
    "correction": (
        AttendanceCorrectionRequest,
        "attendance__employee",
        P.ATTENDANCE_VIEW,
    ),
    "timesheet": (Timesheet, "employee", P.TIMESHEETS_VIEW),
    "overtime": (OvertimeRequest, "employee", P.OVERTIME_VIEW),
}


def subject(*, actor, organization):
    organization = Organization.objects.get(pk=organization.pk)
    own = resolve_ess_subject(user=actor, organization=organization)
    if own.current_relationship.legacy_employee_id is None:
        raise PermissionDenied(DENIED)
    return organization, own


def own_rows(*, actor, organization, kind):
    organization, own = subject(actor=actor, organization=organization)
    if kind not in SOURCES:
        raise PermissionDenied(DENIED)
    model, employee_field, permission = SOURCES[kind]
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message=DENIED,
        allow_any_scope=True,
    )
    rows = model.objects.filter(
        organization=organization,
        **{employee_field: own.current_relationship.legacy_employee_id},
    )
    if kind == "leave":
        rows = rows.filter(kind="leave")
    if kind == "correction":
        rows = rows.filter(requested_by=actor)
    if kind == "overtime":
        zone = ZoneInfo(organization.settings.timezone)
        relationship = own.current_relationship
        rows = rows.filter(
            starts_at__gte=datetime.combine(
                relationship.effective_start, time.min, tzinfo=zone
            )
        )
        if relationship.effective_end:
            rows = rows.filter(
                ends_at__lt=datetime.combine(
                    relationship.effective_end + timedelta(days=1),
                    time.min,
                    tzinfo=zone,
                )
            )
    if kind != "timesheet":
        prefix = "attendance__" if kind == "correction" else ""
        rows = scope_queryset(
            rows,
            membership=membership,
            project_lookup=prefix + "project",
            site_lookup=prefix + "site",
        )
    else:
        # Check every entry's source scope before exposing a parent timesheet.
        visible_ids = []
        for row in rows.prefetch_related("entries"):
            entries = row.entries.all()
            visible = scope_queryset(
                entries,
                membership=membership,
                project_lookup="project",
                site_lookup="site",
            )
            if entries.count() == visible.count():
                visible_ids.append(row.pk)
        rows = rows.filter(pk__in=visible_ids)
    return rows.order_by("-created_at", "-pk")


def own_record(*, actor, organization, kind, record_id):
    record = (
        own_rows(actor=actor, organization=organization, kind=kind)
        .filter(pk=record_id)
        .first()
    )
    if record is None:
        raise PermissionDenied(DENIED)
    return record


def own_balances(*, actor, organization):
    organization, own = subject(actor=actor, organization=organization)
    today = timezone.localdate(timezone=ZoneInfo(organization.settings.timezone))
    categories = (
        LeavePolicyVersion.objects.filter(
            organization=organization, effective_from__lte=today, effective_to__gt=today
        )
        .values_list("category_code", flat=True)
        .distinct()
    )
    balances = []
    for category in categories:
        try:
            balance = leave_services.balance_as_of(
                organization=organization,
                actor=actor,
                relationship=own.current_relationship,
                category_code=category,
                as_of=today,
            )
        except ValidationError:
            balances.append({"category": category, "state": "unavailable"})
        else:
            balances.append({"category": category, "state": "ready", "source": balance})
    return balances


@transaction.atomic
def create_own_leave(
    *, actor, organization, policy_id, starts_at, ends_at, quantity, reason
):
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    organization, own = subject(actor=actor, organization=organization)
    today = timezone.localdate(timezone=ZoneInfo(organization.settings.timezone))
    policy = LeavePolicyVersion.objects.filter(
        pk=policy_id, organization=organization
    ).first()
    if (
        policy is None
        or leave_services._policy(organization, policy.category_code, today).pk
        != policy.pk
    ):
        raise ValidationError("سیاست مؤثر و مجاز مرخصی در دسترس نیست.")
    request = source.create_leave_mission_request(
        organization=organization,
        actor=actor,
        employee=own.current_relationship.legacy_employee,
        kind="leave",
        category_code=policy.category_code,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason,
        policy_reference=policy.evidence_reference,
    )
    leave_services.reserve_request(
        organization=organization,
        actor=actor,
        relationship=own.current_relationship,
        request=request,
        quantity=quantity,
        effective_on=today,
        source_key=f"ess-request:{request.pk}:reservation",
        evidence_reference=f"native-request:{request.pk}",
        reason=reason,
        own_subject=True,
    )
    return request


@transaction.atomic
def submit_own(*, actor, organization, kind, record_id):
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    record = own_record(
        actor=actor, organization=organization, kind=kind, record_id=record_id
    )
    if kind in {"leave", "overtime"}:
        result = source.submit_time_request(
            organization=organization, actor=actor, request=record
        )
        if kind == "overtime":
            _overtime_identity_audit(
                actor=actor, organization=organization, record=result
            )
        return result
    if kind == "timesheet":
        return source.submit_timesheet(
            organization=organization, actor=actor, timesheet=record
        )
    raise PermissionDenied(DENIED)


def _overtime_identity_audit(
    *, actor: User, organization: Organization, record: OvertimeRequest
) -> None:
    _, own = subject(actor=actor, organization=organization)
    record_audit_event(
        action=AuditAction.TIME_REQUEST_TRANSITIONED,
        organization=organization,
        actor=actor,
        entity_type=record._meta.label_lower,
        entity_id=str(record.pk),
        changes={"state": record.state},
        metadata={
            "origin": "ess_overtime",
            "person_id": str(own.person.pk),
            "relationship_id": str(own.current_relationship.pk),
            "relationship_start": own.current_relationship.effective_start.isoformat(),
            "relationship_end": str(own.current_relationship.effective_end or ""),
            "employee_id": str(record.employee_id),
        },
    )


@transaction.atomic
def create_own_overtime(
    *,
    actor: User,
    organization: Organization,
    starts_at: datetime,
    ends_at: datetime,
    reason: str,
) -> OvertimeRequest:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    organization, own = subject(actor=actor, organization=organization)
    zone = ZoneInfo(organization.settings.timezone)
    relationship = own.current_relationship
    if (
        not timezone.is_aware(starts_at)
        or not timezone.is_aware(ends_at)
        or ends_at <= starts_at
        or timezone.localtime(starts_at, zone).date() < relationship.effective_start
        or (
            relationship.effective_end
            and timezone.localtime(ends_at, zone).date() > relationship.effective_end
        )
    ):
        raise ValidationError("بازه اضافه‌کاری باید در محدوده رابطه کاری مجاز باشد.")
    record = source.create_overtime_request(
        organization=organization,
        actor=actor,
        employee=relationship.legacy_employee,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason,
    )
    _overtime_identity_audit(actor=actor, organization=organization, record=record)
    return record


@transaction.atomic
def correct_own_attendance(
    *, actor, organization, record_id, reason, work_date, check_in_at, check_out_at
):
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    attendance = own_record(
        actor=actor, organization=organization, kind="attendance", record_id=record_id
    )
    return source.request_attendance_correction(
        organization=organization,
        requester=actor,
        attendance=attendance,
        reason=reason,
        replacement_values={
            "work_date": work_date,
            "check_in_at": check_in_at,
            "check_out_at": check_out_at,
        },
    )


@transaction.atomic
def create_own_timesheet(
    *, actor, organization, period_start, period_end, declared_minutes
):
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    organization, own = subject(actor=actor, organization=organization)
    if period_start < own.current_relationship.effective_start or (
        own.current_relationship.effective_end
        and period_end > own.current_relationship.effective_end
    ):
        raise ValidationError("دوره باید در محدوده رابطه کاری باشد.")
    return source.create_timesheet(
        organization=organization,
        actor=actor,
        employee=own.current_relationship.legacy_employee,
        period_start=period_start,
        period_end=period_end,
        declared_minutes=declared_minutes,
    )


@transaction.atomic
def add_own_entry(
    *, actor, organization, record_id, work_date: date, project, site, activity, minutes
):
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    organization, own = subject(actor=actor, organization=organization)
    timesheet = own_record(
        actor=actor, organization=organization, kind="timesheet", record_id=record_id
    )
    assignments = EmployeeProjectAssignment.objects.filter(
        organization=organization,
        employee=own.current_relationship.legacy_employee,
        project=project,
        start_date__lte=work_date,
    ).exclude(status="cancelled")
    assignments = (
        assignments.filter(site=site) if site else assignments.filter(site__isnull=True)
    )
    if not any(
        row.end_date is None or row.end_date >= work_date for row in assignments
    ):
        raise PermissionDenied(DENIED)
    return source.add_timesheet_entry(
        organization=organization,
        actor=actor,
        timesheet=timesheet,
        work_date=work_date,
        project=project,
        site=site,
        activity=activity,
        minutes=minutes,
    )
