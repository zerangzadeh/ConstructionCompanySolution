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


def my_requests_available(*, actor: User, organization: Organization) -> bool:
    try:
        codes = _permission_codes(actor=actor, organization=organization)
    except PermissionDenied:
        return False
    return bool(
        codes & REQUEST_PERMISSION_CODES
        and _explicit_employee_ids(actor=actor, organization=organization)
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
    if not employee_ids or not codes & REQUEST_PERMISSION_CODES:
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
