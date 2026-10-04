from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime, time
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.models import Activity, Project, ProjectSite
from apps.workforce.models import Employee

from .models import (
    AttendanceAdjustment,
    AttendanceCorrectionRequest,
    AttendanceImportBatch,
    AttendanceImportRow,
    AttendanceReconciliation,
    AttendanceRecord,
    AttendanceSource,
    AttendanceState,
    CalendarHoliday,
    ImportState,
    LaborDistributionPreview,
    LaborDistributionPreviewLine,
    LeaveMissionRequest,
    OvertimeRequest,
    RequestState,
    ShiftBreak,
    ShiftDefinition,
    Timesheet,
    TimesheetEntry,
    TimesheetReview,
    TimesheetState,
    WorkCalendar,
)


def _audit(
    *,
    action: str,
    organization: Organization,
    actor: User,
    entity: Any,
    changes: dict[str, Any] | None = None,
) -> None:
    record_audit_event(
        action=action,
        organization=organization,
        actor=actor,
        entity_type=entity._meta.label_lower,
        entity_id=str(entity.pk),
        changes=changes or {},
    )


def _scope(
    permission: BusinessPermissionCode,
    *,
    organization: Organization,
    actor: User,
    project: Project | None = None,
    site: ProjectSite | None = None,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        site=site,
        message="مجوز یا دامنه لازم برای این عملیات را ندارید.",
    )


def _ensure_tenant(organization: Organization, **objects: Any) -> None:
    for name, obj in objects.items():
        if obj is not None and getattr(obj, "organization_id", None) != organization.pk:
            raise ValidationError({name: "رکورد مرتبط باید متعلق به همین شرکت باشد."})


@transaction.atomic
def create_work_calendar(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    effective_from: date,
    working_weekdays: list[int],
    effective_to: date | None = None,
) -> WorkCalendar:
    _scope(
        BusinessPermissionCode.TIME_CALENDARS_MANAGE,
        organization=organization,
        actor=actor,
    )
    timezone_name = organization.settings.timezone
    WorkCalendar.objects.select_for_update().filter(
        organization=organization, code__iexact=code
    ).exists()
    calendar = WorkCalendar.objects.create(
        organization=organization,
        code=code,
        name=name,
        timezone=timezone_name,
        effective_from=effective_from,
        effective_to=effective_to,
        working_weekdays=working_weekdays,
        created_by=actor,
    )
    _audit(
        action=AuditAction.TIME_CALENDAR_CONFIGURED,
        organization=organization,
        actor=actor,
        entity=calendar,
    )
    return calendar


@transaction.atomic
def add_calendar_holiday(
    *,
    organization: Organization,
    actor: User,
    calendar: WorkCalendar,
    holiday_date: date,
    name: str,
    reason: str,
    source_reference: str = "",
    is_working_override: bool = False,
) -> CalendarHoliday:
    _scope(
        BusinessPermissionCode.TIME_CALENDARS_MANAGE,
        organization=organization,
        actor=actor,
    )
    _ensure_tenant(organization, calendar=calendar)
    WorkCalendar.objects.select_for_update().get(pk=calendar.pk)
    holiday = CalendarHoliday.objects.create(
        organization=organization,
        calendar=calendar,
        date=holiday_date,
        name=name,
        reason=reason,
        source_reference=source_reference,
        is_working_override=is_working_override,
        created_by=actor,
    )
    _audit(
        action=AuditAction.TIME_CALENDAR_CONFIGURED,
        organization=organization,
        actor=actor,
        entity=holiday,
    )
    return holiday


@transaction.atomic
def create_shift(
    *,
    organization: Organization,
    actor: User,
    calendar: WorkCalendar,
    code: str,
    name: str,
    starts_at: time,
    ends_at: time,
    crosses_midnight: bool,
    effective_from: date,
    breaks: Iterable[Mapping[str, Any]] = (),
    effective_to: date | None = None,
) -> ShiftDefinition:
    _scope(
        BusinessPermissionCode.TIME_CALENDARS_MANAGE,
        organization=organization,
        actor=actor,
    )
    _ensure_tenant(organization, calendar=calendar)
    WorkCalendar.objects.select_for_update().get(pk=calendar.pk)
    shift = ShiftDefinition.objects.create(
        organization=organization,
        calendar=calendar,
        code=code,
        name=name,
        starts_at=starts_at,
        ends_at=ends_at,
        crosses_midnight=crosses_midnight,
        effective_from=effective_from,
        effective_to=effective_to,
        created_by=actor,
    )
    intervals: list[tuple[time, time, bool]] = []
    for sequence, data in enumerate(breaks, 1):
        candidate = (
            data["starts_at"],
            data["ends_at"],
            bool(data.get("ends_next_day", False)),
        )
        if candidate in intervals:
            raise ValidationError("بازه استراحت تکراری مجاز نیست.")
        intervals.append(candidate)
        ShiftBreak.objects.create(
            organization=organization,
            shift=shift,
            sequence=sequence,
            starts_at=candidate[0],
            ends_at=candidate[1],
            ends_next_day=candidate[2],
            is_paid=bool(data.get("is_paid", False)),
            created_by=actor,
        )
    _audit(
        action=AuditAction.TIME_CALENDAR_CONFIGURED,
        organization=organization,
        actor=actor,
        entity=shift,
    )
    return shift


@transaction.atomic
def add_shift_break(
    *,
    organization: Organization,
    actor: User,
    shift: ShiftDefinition,
    sequence: int,
    starts_at: time,
    ends_at: time,
    ends_next_day: bool = False,
    is_paid: bool = False,
) -> ShiftBreak:
    _scope(
        BusinessPermissionCode.TIME_CALENDARS_MANAGE,
        organization=organization,
        actor=actor,
    )
    _ensure_tenant(organization, shift=shift)
    ShiftDefinition.objects.select_for_update().get(pk=shift.pk)
    item = ShiftBreak.objects.create(
        organization=organization,
        shift=shift,
        sequence=sequence,
        starts_at=starts_at,
        ends_at=ends_at,
        ends_next_day=ends_next_day,
        is_paid=is_paid,
        created_by=actor,
    )
    _audit(
        action=AuditAction.TIME_CALENDAR_CONFIGURED,
        organization=organization,
        actor=actor,
        entity=item,
    )
    return item


def _attendance_overlap_query(
    *, employee: Employee, check_in_at: datetime, check_out_at: datetime | None
) -> Q:
    end = check_out_at or datetime.max.replace(tzinfo=check_in_at.tzinfo)
    return (
        Q(employee=employee, check_in_at__lt=end)
        & (Q(check_out_at__isnull=True) | Q(check_out_at__gt=check_in_at))
        & ~Q(state__in=[AttendanceState.REVERSED, AttendanceState.SUPERSEDED])
    )


@transaction.atomic
def capture_attendance(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    calendar: WorkCalendar,
    work_date: date,
    check_in_at: datetime,
    check_out_at: datetime | None,
    project: Project | None = None,
    site: ProjectSite | None = None,
    shift: ShiftDefinition | None = None,
    source_reference: str = "",
    exception_code: str = "",
    exception_notes: str = "",
    source: str = AttendanceSource.MANUAL,
) -> AttendanceRecord:
    _scope(
        BusinessPermissionCode.ATTENDANCE_CAPTURE,
        organization=organization,
        actor=actor,
        project=project,
        site=site,
    )
    _ensure_tenant(
        organization,
        employee=employee,
        calendar=calendar,
        project=project,
        site=site,
        shift=shift,
    )
    Employee.objects.select_for_update().get(pk=employee.pk)
    overlaps = (
        AttendanceRecord.objects.select_for_update()
        .filter(organization=organization)
        .filter(
            _attendance_overlap_query(
                employee=employee, check_in_at=check_in_at, check_out_at=check_out_at
            )
        )
    )
    if overlaps.exists():
        exception_code = exception_code or "OVERLAP"
        exception_notes = exception_notes or "بازه با حضور ثبت‌شده دیگری همپوشانی دارد."
    state = (
        AttendanceState.EXCEPTION
        if exception_code or check_out_at is None
        else AttendanceState.DRAFT
    )
    record = AttendanceRecord.objects.create(
        organization=organization,
        employee=employee,
        project=project,
        site=site,
        calendar=calendar,
        shift=shift,
        work_date=work_date,
        check_in_at=check_in_at,
        check_out_at=check_out_at,
        source=source,
        source_reference=source_reference,
        state=state,
        exception_code=exception_code,
        exception_notes=exception_notes,
        captured_by=actor,
    )
    _audit(
        action=AuditAction.TIME_ATTENDANCE_CAPTURED,
        organization=organization,
        actor=actor,
        entity=record,
        changes={"state": state},
    )
    return record


@transaction.atomic
def finalize_attendance(
    *,
    organization: Organization,
    actor: User,
    attendance: AttendanceRecord,
    reconciliation_reason: str = "",
) -> AttendanceRecord:
    attendance = AttendanceRecord.objects.select_for_update().get(
        pk=attendance.pk, organization=organization
    )
    _scope(
        BusinessPermissionCode.ATTENDANCE_REVIEW,
        organization=organization,
        actor=actor,
        project=attendance.project,
        site=attendance.site,
    )
    if attendance.captured_by_id == actor.pk:
        raise PermissionDenied("ثبت‌کننده نمی‌تواند حضور خود را قطعی کند.")
    if (
        attendance.state not in {AttendanceState.DRAFT, AttendanceState.EXCEPTION}
        or attendance.check_out_at is None
    ):
        raise ValidationError("فقط حضور کامل پیش‌نویس یا استثنا قابل قطعی‌سازی است.")
    competing = (
        AttendanceRecord.objects.select_for_update()
        .filter(organization=organization)
        .exclude(pk=attendance.pk)
        .filter(
            _attendance_overlap_query(
                employee=attendance.employee,
                check_in_at=attendance.check_in_at,
                check_out_at=attendance.check_out_at,
            )
        )
    )
    if competing.filter(state=AttendanceState.FINALIZED).exists():
        raise ValidationError("حضور قطعی همپوشان وجود دارد.")
    if (
        attendance.state == AttendanceState.EXCEPTION
        and not reconciliation_reason.strip()
    ):
        raise ValidationError("قطعی‌سازی استثنا به دلیل تطبیق نیاز دارد.")
    AttendanceRecord.objects.filter(pk=attendance.pk).update(
        state=AttendanceState.FINALIZED, finalized_by=actor, finalized_at=timezone.now()
    )
    if reconciliation_reason:
        AttendanceReconciliation.objects.create(
            organization=organization,
            attendance=attendance,
            outcome="resolved",
            reason=reconciliation_reason,
            recorded_by=actor,
        )
    attendance.refresh_from_db()
    _audit(
        action=AuditAction.TIME_ATTENDANCE_FINALIZED,
        organization=organization,
        actor=actor,
        entity=attendance,
    )
    return attendance


@transaction.atomic
def request_attendance_correction(
    *,
    organization: Organization,
    requester: User,
    attendance: AttendanceRecord,
    reason: str,
    reversal: bool = False,
    replacement_values: Mapping[str, Any] | None = None,
) -> AttendanceCorrectionRequest:
    attendance = AttendanceRecord.objects.select_for_update().get(
        pk=attendance.pk, organization=organization
    )
    _scope(
        BusinessPermissionCode.ATTENDANCE_CORRECT,
        organization=organization,
        actor=requester,
        project=attendance.project,
        site=attendance.site,
    )
    if requester.pk in {
        attendance.captured_by_id,
        attendance.finalized_by_id,
    }:
        raise PermissionDenied("درخواست‌کننده اصلاح باید از ثبت/قطعی‌سازی مستقل باشد.")
    if attendance.state != AttendanceState.FINALIZED or not reason.strip():
        raise ValidationError("فقط حضور قطعی با دلیل قابل اصلاح یا برگشت است.")
    values = dict(replacement_values or {})
    request = AttendanceCorrectionRequest.objects.create(
        organization=organization,
        attendance=attendance,
        kind="reversal" if reversal else "correction",
        reason=reason,
        replacement_work_date=None
        if reversal
        else values.get("work_date", attendance.work_date),
        replacement_check_in_at=None
        if reversal
        else values.get("check_in_at", attendance.check_in_at),
        replacement_check_out_at=None
        if reversal
        else values.get("check_out_at", attendance.check_out_at),
        requested_by=requester,
    )
    return request


@transaction.atomic
def review_attendance_correction(
    *,
    organization: Organization,
    approver: User,
    correction_request: AttendanceCorrectionRequest,
    approve: bool,
    review_reason: str,
) -> AttendanceCorrectionRequest:
    correction_request = (
        AttendanceCorrectionRequest.objects.select_for_update()
        .select_related("attendance")
        .get(pk=correction_request.pk, organization=organization)
    )
    attendance = AttendanceRecord.objects.select_for_update().get(
        pk=correction_request.attendance_id
    )
    _scope(
        BusinessPermissionCode.ATTENDANCE_CORRECT,
        organization=organization,
        actor=approver,
        project=attendance.project,
        site=attendance.site,
    )
    if correction_request.requested_by_id == approver.pk:
        raise PermissionDenied("درخواست‌کننده نمی‌تواند اصلاح خود را تأیید کند.")
    if correction_request.status != "pending" or not review_reason.strip():
        raise ValidationError("فقط درخواست در انتظار با دلیل قابل بررسی است.")
    if not approve:
        AttendanceCorrectionRequest.objects.filter(pk=correction_request.pk).update(
            status="rejected",
            reviewed_by=approver,
            reviewed_at=timezone.now(),
            review_reason=review_reason,
        )
        correction_request.refresh_from_db()
        return correction_request
    if attendance.state != AttendanceState.FINALIZED:
        raise ValidationError("حضور مبنا دیگر قطعی و قابل اصلاح نیست.")
    replacement = None
    if correction_request.kind == "correction":
        replacement = AttendanceRecord.objects.create(
            organization=organization,
            employee=attendance.employee,
            project=attendance.project,
            site=attendance.site,
            calendar=attendance.calendar,
            shift=attendance.shift,
            work_date=correction_request.replacement_work_date,
            check_in_at=correction_request.replacement_check_in_at,
            check_out_at=correction_request.replacement_check_out_at,
            source=AttendanceSource.MANUAL,
            source_reference=f"correction:{attendance.pk}",
            state=AttendanceState.FINALIZED,
            exception_notes=correction_request.reason,
            captured_by=correction_request.requested_by,
            finalized_by=approver,
            finalized_at=timezone.now(),
        )
    new_state = (
        AttendanceState.REVERSED
        if correction_request.kind == "reversal"
        else AttendanceState.SUPERSEDED
    )
    AttendanceRecord.objects.filter(pk=attendance.pk).update(state=new_state)
    adjustment = AttendanceAdjustment.objects.create(
        organization=organization,
        attendance=attendance,
        replacement=replacement,
        kind=correction_request.kind,
        reason=correction_request.reason,
        requested_by=correction_request.requested_by,
        approved_by=approver,
        approved_at=timezone.now(),
    )
    _audit(
        action=AuditAction.TIME_ATTENDANCE_CORRECTED,
        organization=organization,
        actor=approver,
        entity=adjustment,
        changes={"original_state": AttendanceState.FINALIZED, "new_state": new_state},
    )
    AttendanceCorrectionRequest.objects.filter(pk=correction_request.pk).update(
        status="approved",
        reviewed_by=approver,
        reviewed_at=timezone.now(),
        review_reason=review_reason,
        adjustment=adjustment,
    )
    correction_request.refresh_from_db()
    return correction_request


@transaction.atomic
def correct_attendance(
    *,
    organization: Organization,
    requester: User,
    approver: User,
    attendance: AttendanceRecord,
    reason: str,
    reversal: bool = False,
    replacement_values: Mapping[str, Any] | None = None,
) -> AttendanceAdjustment:
    correction_request = request_attendance_correction(
        organization=organization,
        requester=requester,
        attendance=attendance,
        reason=reason,
        reversal=reversal,
        replacement_values=replacement_values,
    )
    correction_request = review_attendance_correction(
        organization=organization,
        approver=approver,
        correction_request=correction_request,
        approve=True,
        review_reason="Independent correction approval",
    )
    return correction_request.adjustment


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@transaction.atomic
def import_attendance(
    *,
    organization: Organization,
    actor: User,
    idempotency_key: str,
    source_label: str,
    rows: list[Mapping[str, Any]],
) -> AttendanceImportBatch:
    _scope(
        BusinessPermissionCode.ATTENDANCE_IMPORT, organization=organization, actor=actor
    )
    digest = _canonical_digest(rows)
    existing = (
        AttendanceImportBatch.objects.select_for_update()
        .filter(organization=organization, idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        if existing.source_digest != digest:
            raise ValidationError(
                "کلید idempotency قبلاً با محتوای متفاوت استفاده شده است."
            )
        return existing
    batch = AttendanceImportBatch.objects.create(
        organization=organization,
        idempotency_key=idempotency_key,
        source_label=source_label,
        source_digest=digest,
        imported_by=actor,
    )
    has_exception = False
    for number, raw in enumerate(rows, 1):
        try:
            employee = Employee.objects.get(
                pk=raw["employee_id"], organization=organization
            )
            calendar = WorkCalendar.objects.get(
                pk=raw["calendar_id"], organization=organization
            )
            project = (
                Project.objects.get(pk=raw["project_id"], organization=organization)
                if raw.get("project_id")
                else None
            )
            site = (
                ProjectSite.objects.get(pk=raw["site_id"], organization=organization)
                if raw.get("site_id")
                else None
            )
            record = capture_attendance(
                organization=organization,
                actor=actor,
                employee=employee,
                calendar=calendar,
                work_date=raw["work_date"],
                check_in_at=raw["check_in_at"],
                check_out_at=raw.get("check_out_at"),
                project=project,
                site=site,
                source_reference=str(raw.get("source_reference", number)),
                source=AttendanceSource.IMPORT,
            )
            outcome, code, detail = "created", "", ""
        except (
            KeyError,
            ValidationError,
            PermissionDenied,
            Employee.DoesNotExist,
            WorkCalendar.DoesNotExist,
            Project.DoesNotExist,
            ProjectSite.DoesNotExist,
        ) as exc:
            record, outcome, code, detail = None, "exception", "INVALID_ROW", str(exc)
            has_exception = True
        AttendanceImportRow.objects.create(
            organization=organization,
            batch=batch,
            row_number=number,
            source_reference=str(raw.get("source_reference", number)),
            payload_digest=_canonical_digest(raw),
            outcome=outcome,
            exception_code=code,
            exception_detail=detail,
            attendance=record,
        )
    batch.state = ImportState.EXCEPTION if has_exception else ImportState.COMPLETED
    batch.completed_at = timezone.now()
    batch.save(update_fields=["state", "completed_at", "updated_at"])
    _audit(
        action=AuditAction.TIME_ATTENDANCE_IMPORTED,
        organization=organization,
        actor=actor,
        entity=batch,
        changes={"rows": len(rows), "state": batch.state},
    )
    return batch


def _request_overlap(
    model,
    *,
    organization: Organization,
    employee: Employee,
    starts_at: datetime,
    ends_at: datetime,
    exclude_pk=None,
) -> bool:
    qs = (
        model.objects.select_for_update()
        .filter(
            organization=organization,
            employee=employee,
            starts_at__lt=ends_at,
            ends_at__gt=starts_at,
        )
        .exclude(state__in=[RequestState.REJECTED, RequestState.CANCELLED])
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


@transaction.atomic
def create_leave_mission_request(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    kind: str,
    category_code: str,
    starts_at: datetime,
    ends_at: datetime,
    reason: str,
    project: Project | None = None,
    site: ProjectSite | None = None,
    policy_reference: str = "",
) -> LeaveMissionRequest:
    _scope(
        BusinessPermissionCode.LEAVE_MISSION_REQUEST,
        organization=organization,
        actor=actor,
        project=project,
        site=site,
    )
    _ensure_tenant(organization, employee=employee, project=project, site=site)
    if _request_overlap(
        LeaveMissionRequest,
        organization=organization,
        employee=employee,
        starts_at=starts_at,
        ends_at=ends_at,
    ):
        raise ValidationError("درخواست مرخصی/مأموریت همپوشان وجود دارد.")
    return LeaveMissionRequest.objects.create(
        organization=organization,
        employee=employee,
        project=project,
        site=site,
        kind=kind,
        category_code=category_code,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason,
        policy_reference=policy_reference,
        requested_by=actor,
    )


@transaction.atomic
def create_overtime_request(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    starts_at: datetime,
    ends_at: datetime,
    reason: str,
    project: Project | None = None,
    site: ProjectSite | None = None,
    policy_reference: str = "",
) -> OvertimeRequest:
    _scope(
        BusinessPermissionCode.OVERTIME_REQUEST,
        organization=organization,
        actor=actor,
        project=project,
        site=site,
    )
    _ensure_tenant(organization, employee=employee, project=project, site=site)
    if _request_overlap(
        OvertimeRequest,
        organization=organization,
        employee=employee,
        starts_at=starts_at,
        ends_at=ends_at,
    ):
        raise ValidationError("درخواست اضافه‌کاری همپوشان وجود دارد.")
    return OvertimeRequest.objects.create(
        organization=organization,
        employee=employee,
        project=project,
        site=site,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason,
        policy_reference=policy_reference,
        requested_by=actor,
    )


@transaction.atomic
def submit_time_request(
    *,
    organization: Organization,
    actor: User,
    request: LeaveMissionRequest | OvertimeRequest,
) -> Any:
    request = (
        type(request)
        .objects.select_for_update()
        .get(pk=request.pk, organization=organization)
    )
    permission = (
        BusinessPermissionCode.LEAVE_MISSION_REQUEST
        if isinstance(request, LeaveMissionRequest)
        else BusinessPermissionCode.OVERTIME_REQUEST
    )
    _scope(
        permission,
        organization=organization,
        actor=actor,
        project=request.project,
        site=request.site,
    )
    if request.requested_by_id != actor.pk or request.state != RequestState.DRAFT:
        raise PermissionDenied("فقط سازنده می‌تواند پیش‌نویس را ارسال کند.")
    type(request).objects.filter(pk=request.pk).update(state=RequestState.SUBMITTED)
    request.refresh_from_db()
    _audit(
        action=AuditAction.TIME_REQUEST_TRANSITIONED,
        organization=organization,
        actor=actor,
        entity=request,
        changes={"state": RequestState.SUBMITTED},
    )
    return request


@transaction.atomic
def review_time_request(
    *,
    organization: Organization,
    actor: User,
    request: LeaveMissionRequest | OvertimeRequest,
    approve: bool,
    reason: str,
) -> Any:
    request = (
        type(request)
        .objects.select_for_update()
        .get(pk=request.pk, organization=organization)
    )
    permission = (
        BusinessPermissionCode.LEAVE_MISSION_REVIEW
        if isinstance(request, LeaveMissionRequest)
        else BusinessPermissionCode.OVERTIME_REVIEW
    )
    _scope(
        permission,
        organization=organization,
        actor=actor,
        project=request.project,
        site=request.site,
    )
    if request.requested_by_id == actor.pk:
        raise PermissionDenied("درخواست‌کننده نمی‌تواند درخواست خود را بررسی کند.")
    if request.state != RequestState.SUBMITTED or not reason.strip():
        raise ValidationError("فقط درخواست ارسال‌شده با دلیل قابل بررسی است.")
    if approve and not request.policy_reference.strip():
        raise ValidationError("تأیید بدون مرجع سیاست مصوب مجاز نیست.")
    state = RequestState.APPROVED if approve else RequestState.REJECTED
    type(request).objects.filter(pk=request.pk).update(
        state=state, reviewed_by=actor, reviewed_at=timezone.now(), review_reason=reason
    )
    request.refresh_from_db()
    _audit(
        action=AuditAction.TIME_REQUEST_TRANSITIONED,
        organization=organization,
        actor=actor,
        entity=request,
        changes={"state": state},
    )
    return request


@transaction.atomic
def create_timesheet(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    period_start: date,
    period_end: date,
    declared_minutes: int,
    supersedes: Timesheet | None = None,
    correction_reason: str = "",
) -> Timesheet:
    _scope(
        BusinessPermissionCode.TIMESHEETS_PREPARE,
        organization=organization,
        actor=actor,
    )
    _ensure_tenant(organization, employee=employee, supersedes=supersedes)
    if supersedes:
        supersedes = Timesheet.objects.select_for_update().get(
            pk=supersedes.pk, organization=organization
        )
        if supersedes.state not in {
            TimesheetState.SUBMITTED,
            TimesheetState.APPROVED,
            TimesheetState.REJECTED,
        }:
            raise ValidationError("فقط کارکرد دارای تاریخچه قابل بازنگری است.")
        revision = supersedes.revision + 1
    else:
        revision = 1
    return Timesheet.objects.create(
        organization=organization,
        employee=employee,
        period_start=period_start,
        period_end=period_end,
        revision=revision,
        declared_minutes=declared_minutes,
        prepared_by=actor,
        supersedes=supersedes,
        correction_reason=correction_reason,
    )


@transaction.atomic
def add_timesheet_entry(
    *,
    organization: Organization,
    actor: User,
    timesheet: Timesheet,
    work_date: date,
    project: Project,
    minutes: int,
    site: ProjectSite | None = None,
    activity: Activity | None = None,
    note: str = "",
) -> TimesheetEntry:
    timesheet = Timesheet.objects.select_for_update().get(
        pk=timesheet.pk, organization=organization
    )
    _scope(
        BusinessPermissionCode.TIMESHEETS_PREPARE,
        organization=organization,
        actor=actor,
        project=project,
        site=site,
    )
    _ensure_tenant(organization, project=project, site=site, activity=activity)
    if timesheet.prepared_by_id != actor.pk or timesheet.state != TimesheetState.DRAFT:
        raise PermissionDenied("فقط تهیه‌کننده می‌تواند پیش‌نویس کارکرد را تکمیل کند.")
    return TimesheetEntry.objects.create(
        organization=organization,
        timesheet=timesheet,
        work_date=work_date,
        project=project,
        site=site,
        activity=activity,
        minutes=minutes,
        note=note,
    )


@transaction.atomic
def submit_timesheet(
    *, organization: Organization, actor: User, timesheet: Timesheet
) -> Timesheet:
    timesheet = Timesheet.objects.select_for_update().get(
        pk=timesheet.pk, organization=organization
    )
    _scope(
        BusinessPermissionCode.TIMESHEETS_PREPARE,
        organization=organization,
        actor=actor,
    )
    if timesheet.prepared_by_id != actor.pk or timesheet.state != TimesheetState.DRAFT:
        raise PermissionDenied("فقط تهیه‌کننده می‌تواند پیش‌نویس را ارسال کند.")
    entries = list(
        TimesheetEntry.objects.select_for_update()
        .filter(timesheet=timesheet)
        .order_by()
    )
    total = sum(entry.minutes for entry in entries)
    if not entries or total != timesheet.declared_minutes:
        raise ValidationError(
            "جمع تخصیص ردیف‌ها باید دقیقاً با کل دقیقه اعلام‌شده برابر باشد."
        )
    for entry in entries:
        _scope(
            BusinessPermissionCode.TIMESHEETS_PREPARE,
            organization=organization,
            actor=actor,
            project=entry.project,
            site=entry.site,
        )
    if timesheet.supersedes_id:
        Timesheet.objects.filter(pk=timesheet.supersedes_id).update(
            state=TimesheetState.SUPERSEDED
        )
    Timesheet.objects.filter(pk=timesheet.pk).update(
        state=TimesheetState.SUBMITTED, submitted_by=actor, submitted_at=timezone.now()
    )
    timesheet.refresh_from_db()
    _audit(
        action=AuditAction.TIME_TIMESHEET_SUBMITTED,
        organization=organization,
        actor=actor,
        entity=timesheet,
        changes={"minutes": total},
    )
    return timesheet


@transaction.atomic
def review_timesheet(
    *,
    organization: Organization,
    actor: User,
    timesheet: Timesheet,
    approve: bool,
    reason: str,
) -> TimesheetReview:
    timesheet = Timesheet.objects.select_for_update().get(
        pk=timesheet.pk, organization=organization
    )
    _scope(
        BusinessPermissionCode.TIMESHEETS_REVIEW, organization=organization, actor=actor
    )
    entries = list(
        TimesheetEntry.objects.select_for_update()
        .filter(timesheet=timesheet)
        .order_by()
    )
    for entry in entries:
        _scope(
            BusinessPermissionCode.TIMESHEETS_REVIEW,
            organization=organization,
            actor=actor,
            project=entry.project,
            site=entry.site,
        )
    if actor.pk in {timesheet.prepared_by_id, timesheet.submitted_by_id}:
        raise PermissionDenied(
            "تهیه‌کننده یا ارسال‌کننده نمی‌تواند کارکرد خود را بررسی کند."
        )
    if timesheet.state != TimesheetState.SUBMITTED or not reason.strip():
        raise ValidationError("فقط کارکرد ارسال‌شده با دلیل قابل بررسی است.")
    decision = "approved" if approve else "rejected"
    review = TimesheetReview.objects.create(
        organization=organization,
        timesheet=timesheet,
        decision=decision,
        reason=reason,
        reviewer=actor,
    )
    Timesheet.objects.filter(pk=timesheet.pk).update(
        state=TimesheetState.APPROVED if approve else TimesheetState.REJECTED
    )
    _audit(
        action=AuditAction.TIME_TIMESHEET_REVIEWED,
        organization=organization,
        actor=actor,
        entity=review,
        changes={"decision": decision},
    )
    return review


@transaction.atomic
def generate_labor_distribution_preview(
    *, organization: Organization, actor: User, timesheet: Timesheet
) -> LaborDistributionPreview:
    timesheet = Timesheet.objects.select_for_update().get(
        pk=timesheet.pk, organization=organization
    )
    _scope(
        BusinessPermissionCode.TIMESHEETS_PREVIEW,
        organization=organization,
        actor=actor,
    )
    if timesheet.state != TimesheetState.APPROVED:
        raise ValidationError("پیش‌نمایش فقط از کارکرد تأییدشده ساخته می‌شود.")
    entries = list(
        TimesheetEntry.objects.select_for_update()
        .filter(timesheet=timesheet)
        .order_by()
    )
    total = sum(entry.minutes for entry in entries)
    if total != timesheet.declared_minutes:
        raise ValidationError("توزیع زمان پایسته نیست.")
    for entry in entries:
        _scope(
            BusinessPermissionCode.TIMESHEETS_PREVIEW,
            organization=organization,
            actor=actor,
            project=entry.project,
            site=entry.site,
        )
    preview = LaborDistributionPreview.objects.create(
        organization=organization,
        timesheet=timesheet,
        total_minutes=total,
        generated_by=actor,
    )
    for entry in entries:
        LaborDistributionPreviewLine.objects.create(
            organization=organization,
            preview=preview,
            timesheet_entry=entry,
            project=entry.project,
            site=entry.site,
            activity=entry.activity,
            minutes=entry.minutes,
        )
    if preview.lines.aggregate(total=Sum("minutes"))["total"] != preview.total_minutes:
        raise IntegrityError("پایستگی توزیع زمان نقض شد.")
    _audit(
        action=AuditAction.TIME_DISTRIBUTION_PREVIEWED,
        organization=organization,
        actor=actor,
        entity=preview,
        changes={"minutes": total, "financial_effect": False},
    )
    return preview
