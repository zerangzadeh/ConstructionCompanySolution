"""Permission-safe read models for CEP-018 personal and manager workspaces."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.authorization import (
    get_active_membership,
    membership_has_scope,
    membership_permission_codes,
    permission_supports_object_scope,
)
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.timekeeping.models import (
    AttendanceCorrectionRequest,
    LeaveMissionRequest,
    OvertimeRequest,
)
from apps.workforce.models import Employee, EmployeeStatus, WorkRelationship, WorkTeam

REQUEST_PERMISSION_CODES = frozenset(
    {
        BusinessPermissionCode.LEAVE_MISSION_REQUEST,
        BusinessPermissionCode.OVERTIME_REQUEST,
        BusinessPermissionCode.ATTENDANCE_CORRECT,
        BusinessPermissionCode.PERSONAL_DATA_VIEW,
        BusinessPermissionCode.HR_CERTIFICATES_VIEW,
    }
)
MANAGER_PERMISSION_CODES = frozenset(
    {
        BusinessPermissionCode.LEAVE_MISSION_REVIEW,
        BusinessPermissionCode.OVERTIME_REVIEW,
        BusinessPermissionCode.ATTENDANCE_CORRECT,
    }
)


@dataclass(frozen=True, slots=True)
class RequestWorkspaceRow:
    source_type: str
    source_id: object
    source_label: str
    employee_label: str
    status: str
    status_label: str
    occurred_at: object
    source_url: str


@dataclass(frozen=True, slots=True)
class ManagerWorkspaceData:
    teams: tuple[WorkTeam, ...]
    rows: tuple[RequestWorkspaceRow, ...]
    status_counts: tuple[tuple[str, str, int], ...]
    team_member_count: int


def _permission_codes(*, actor: User, organization: Organization) -> frozenset[str]:
    membership = get_active_membership(user=actor, organization=organization)
    return frozenset(
        code
        for code in membership_permission_codes(membership)
        if membership_has_scope(
            membership,
            allow_any_scope=permission_supports_object_scope(code),
        )
    )


def _explicit_employee_ids(
    *, actor: User, organization: Organization, on_date: date | None = None
) -> set[object]:
    """Resolve only explicit User→Person/WorkRelationship or legacy Employee links."""

    effective_date = on_date or timezone.localdate()
    relationship_employee_ids = WorkRelationship.objects.filter(
        organization=organization,
        person__user=actor,
        effective_start__lte=effective_date,
    ).filter(Q(effective_end__isnull=True) | Q(effective_end__gte=effective_date))
    employee_ids = set(
        relationship_employee_ids.exclude(legacy_employee_id__isnull=True).values_list(
            "legacy_employee_id", flat=True
        )
    )
    employee_ids.update(
        Employee.objects.filter(
            organization=organization,
            user=actor,
            status=EmployeeStatus.ACTIVE,
            archived_at__isnull=True,
        ).values_list("pk", flat=True)
    )
    return employee_ids


def _payroll_requests_available(*, actor, organization, codes):
    from apps.workforce.ess_services import has_ess_subject
    return (
        BusinessPermissionCode.PAYROLL_INQUIRIES_VIEW in codes
        and BusinessPermissionCode.PAYROLL_ESS_VIEW in codes
        and has_ess_subject(user=actor, organization=organization)
    )


def _certificate_requests_available(*,actor,organization,codes):
    from apps.workforce.ess_services import has_ess_subject
    return BusinessPermissionCode.HR_CERTIFICATES_VIEW in codes and has_ess_subject(user=actor,organization=organization)


def my_requests_available(*, actor: User, organization: Organization) -> bool:
    try:
        codes = _permission_codes(actor=actor, organization=organization)
    except PermissionDenied:
        return False
    return bool(
        (codes & REQUEST_PERMISSION_CODES
        and _explicit_employee_ids(actor=actor, organization=organization))
        or _payroll_requests_available(actor=actor, organization=organization, codes=codes)
        or _certificate_requests_available(actor=actor,organization=organization,codes=codes)
    )


def manager_workspace_available(*, actor: User, organization: Organization) -> bool:
    try:
        codes = _permission_codes(actor=actor, organization=organization)
    except PermissionDenied:
        return False
    if (
        BusinessPermissionCode.ATTENDANCE_VIEW not in codes
        or not codes & MANAGER_PERMISSION_CODES
    ):
        return False
    return WorkTeam.objects.filter(
        organization=organization,
        lead__user=actor,
        lead__status=EmployeeStatus.ACTIVE,
        lead__archived_at__isnull=True,
        is_active=True,
        archived_at__isnull=True,
    ).exists()


def _source_url(source_type: str, source_id: object, *, allowed: bool) -> str:
    if not allowed:
        return ""
    return f"{reverse('timekeeping:workbench')}#{source_type}-{source_id}"


def _employee_label(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}".strip()


def _leave_rows(queryset, *, source_links: bool) -> list[RequestWorkspaceRow]:
    return [
        RequestWorkspaceRow(
            source_type="leave",
            source_id=item.pk,
            source_label=item.get_kind_display(),
            employee_label=_employee_label(item.employee),
            status=item.state,
            status_label=item.get_state_display(),
            occurred_at=item.updated_at,
            source_url=_source_url("leave", item.pk, allowed=source_links),
        )
        for item in queryset.select_related("employee")
    ]


def _overtime_rows(queryset, *, source_links: bool) -> list[RequestWorkspaceRow]:
    return [
        RequestWorkspaceRow(
            source_type="overtime",
            source_id=item.pk,
            source_label="اضافه‌کاری",
            employee_label=_employee_label(item.employee),
            status=item.state,
            status_label=item.get_state_display(),
            occurred_at=item.updated_at,
            source_url=_source_url("overtime", item.pk, allowed=source_links),
        )
        for item in queryset.select_related("employee")
    ]


def _correction_rows(queryset, *, source_links: bool) -> list[RequestWorkspaceRow]:
    return [
        RequestWorkspaceRow(
            source_type="correction",
            source_id=item.pk,
            source_label=item.get_kind_display(),
            employee_label=_employee_label(item.attendance.employee),
            status=item.status,
            status_label=item.get_status_display(),
            occurred_at=item.updated_at,
            source_url=_source_url("correction", item.pk, allowed=source_links),
        )
        for item in queryset.select_related("attendance__employee")
    ]


def build_my_requests(
    *, actor: User, organization: Organization
) -> tuple[RequestWorkspaceRow, ...]:
    codes = _permission_codes(actor=actor, organization=organization)
    employee_ids = _explicit_employee_ids(actor=actor, organization=organization)
    payroll_allowed = _payroll_requests_available(actor=actor, organization=organization, codes=codes)
    certificate_allowed=_certificate_requests_available(actor=actor,organization=organization,codes=codes)
    if (not employee_ids or not codes & REQUEST_PERMISSION_CODES) and not payroll_allowed and not certificate_allowed:
        raise PermissionDenied(
            "هویت نیروی کار یا مجوز درخواست برای این فضا موجود نیست."
        )

    source_links = BusinessPermissionCode.ATTENDANCE_VIEW in codes
    rows: list[RequestWorkspaceRow] = []
    if BusinessPermissionCode.LEAVE_MISSION_REQUEST in codes:
        rows.extend(
            _leave_rows(
                LeaveMissionRequest.objects.filter(
                    organization=organization,
                    requested_by=actor,
                    employee_id__in=employee_ids,
                ),
                source_links=source_links,
            )
        )
    if BusinessPermissionCode.OVERTIME_REQUEST in codes:
        rows.extend(
            _overtime_rows(
                OvertimeRequest.objects.filter(
                    organization=organization,
                    requested_by=actor,
                    employee_id__in=employee_ids,
                ),
                source_links=source_links,
            )
        )
    if BusinessPermissionCode.ATTENDANCE_CORRECT in codes:
        rows.extend(
            _correction_rows(
                AttendanceCorrectionRequest.objects.filter(
                    organization=organization,
                    requested_by=actor,
                    attendance__employee_id__in=employee_ids,
                ),
                source_links=source_links,
            )
        )
    if payroll_allowed:
        from apps.payroll.ess_services import inquiry_instance, visible_inquiries
        for item in visible_inquiries(actor=actor, organization=organization):
            if item.requested_by_id != actor.pk:
                continue
            instance = inquiry_instance(item)
            if instance is None:
                continue
            latest = item.responses.order_by("-created_at").first()
            rows.append(RequestWorkspaceRow(
                source_type="payroll_inquiry", source_id=item.pk,
                source_label="پرسش حقوق", employee_label=str(item.person),
                status=instance.status, status_label=instance.get_status_display(),
                occurred_at=latest.created_at if latest else item.created_at,
                source_url=reverse("payroll:ess_inquiry_detail", kwargs={"inquiry_id": item.pk}),
            ))
    if BusinessPermissionCode.PERSONAL_DATA_VIEW in codes:
        from apps.workforce.personal_change_services import (
            instance_for,
            visible_requests,
        )

        for item in visible_requests(actor=actor, organization=organization):
            if item.requested_by_id != actor.pk:
                continue
            instance = instance_for(item)
            if instance:
                decision = getattr(item, "decision", None)
                rows.append(
                    RequestWorkspaceRow(
                        source_type="personal_data",
                        source_id=item.pk,
                        source_label="تغییر اطلاعات شخصی",
                        employee_label=f"{item.person.first_name} {item.person.last_name}",
                        status=instance.status,
                        status_label=instance.get_status_display(),
                        occurred_at=decision.created_at if decision else item.created_at,
                        source_url=reverse(
                            "workforce:personal_change_detail",
                            kwargs={"request_id": item.pk},
                        ),
                    )
                )
    if BusinessPermissionCode.HR_CERTIFICATES_VIEW in codes:
        from apps.workforce.certificate_services import (
            instance_for as certificate_instance,
        )
        from apps.workforce.certificate_services import visible_requests as certificates

        for item in certificates(actor=actor, organization=organization):
            if item.requested_by_id != actor.pk:
                continue
            instance = certificate_instance(item)
            cancellation = getattr(item, "cancellation", None)
            generated = getattr(item, "generation", None)
            review = getattr(item, "review", None)
            latest = cancellation or generated or review or item
            state = (
                "cancelled"
                if cancellation
                else "generated"
                if generated
                else review.outcome
                if review
                else instance.status
                if instance
                else "requested"
            )
            label = (
                "لغو ثبت‌شده"
                if cancellation
                else "خروجی ثبت‌شده"
                if generated
                else review.get_outcome_display()
                if review
                else instance.get_status_display()
                if instance
                else "درخواست ثبت‌شده"
            )
            rows.append(
                RequestWorkspaceRow(
                    source_type="certificate",
                    source_id=item.pk,
                    source_label="درخواست گواهی",
                    employee_label=f"{item.person.first_name} {item.person.last_name}",
                    status=state,
                    status_label=label,
                    occurred_at=latest.created_at,
                    source_url=reverse(
                        "workforce:certificate_detail", kwargs={"request_id": item.pk}
                    ),
                )
            )
    # Explicit ESS identity permits own-source status deep links even without the
    # broad back-office Timekeeping view grant. Preserve legacy source behavior.
    from apps.workforce.ess_services import has_ess_subject

    if has_ess_subject(user=actor, organization=organization):
        from apps.workforce.personal_change_services import filter_explicit_request_rows

        rows = list(
            filter_explicit_request_rows(rows=rows, actor=actor, organization=organization)
        )
        from dataclasses import replace

        rows = [
            replace(
                row,
                source_url=reverse(
                    "workforce:ess_request_status",
                    kwargs={"source_type": row.source_type, "source_id": row.source_id},
                ),
            )
            if row.source_type in {"leave", "overtime", "correction"}
            else row
            for row in rows
        ]
    return tuple(sorted(rows, key=lambda row: row.occurred_at, reverse=True))


def build_manager_workspace(
    *, actor: User, organization: Organization
) -> ManagerWorkspaceData:
    codes = _permission_codes(actor=actor, organization=organization)
    if BusinessPermissionCode.ATTENDANCE_VIEW not in codes:
        raise PermissionDenied("مجوز مشاهده منبع برای فضای مدیر موجود نیست.")
    teams = tuple(
        WorkTeam.objects.filter(
            organization=organization,
            lead__user=actor,
            lead__status=EmployeeStatus.ACTIVE,
            lead__archived_at__isnull=True,
            is_active=True,
            archived_at__isnull=True,
        ).order_by("name", "pk")
    )
    if not teams or not codes & MANAGER_PERMISSION_CODES:
        raise PermissionDenied("تخصیص صریح تیم و مجوز بررسی برای فضای مدیر لازم است.")

    employee_ids = set(
        Employee.objects.filter(
            organization=organization,
            work_team__in=teams,
            status=EmployeeStatus.ACTIVE,
            archived_at__isnull=True,
        ).values_list("pk", flat=True)
    )
    rows: list[RequestWorkspaceRow] = []
    if BusinessPermissionCode.LEAVE_MISSION_REVIEW in codes:
        rows.extend(
            _leave_rows(
                LeaveMissionRequest.objects.filter(
                    organization=organization, employee_id__in=employee_ids
                ),
                source_links=True,
            )
        )
    if BusinessPermissionCode.OVERTIME_REVIEW in codes:
        rows.extend(
            _overtime_rows(
                OvertimeRequest.objects.filter(
                    organization=organization, employee_id__in=employee_ids
                ),
                source_links=True,
            )
        )
    if BusinessPermissionCode.ATTENDANCE_CORRECT in codes:
        rows.extend(
            _correction_rows(
                AttendanceCorrectionRequest.objects.filter(
                    organization=organization,
                    attendance__employee_id__in=employee_ids,
                ),
                source_links=True,
            )
        )
    rows.sort(key=lambda row: row.occurred_at, reverse=True)
    counts = Counter((row.status, row.status_label) for row in rows)
    return ManagerWorkspaceData(
        teams=teams,
        rows=tuple(rows),
        status_counts=tuple(
            (status, label, count)
            for (status, label), count in sorted(
                counts.items(), key=lambda item: item[0]
            )
        ),
        team_member_count=len(employee_ids),
    )
