"""Read-only, tenant-scoped identity labels for the authenticated shared shell."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from apps.organizations.authorization import effective_role_assignments
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    OrganizationMembership,
)
from apps.workforce.ess_services import resolve_ess_subject
from apps.workforce.models import (
    Employee,
    EmployeePositionAssignment,
    EmployeeStatus,
    Person,
    PositionAssignmentStatus,
)

_BUILTIN_ROLE_LABELS = {
    MembershipRole.COMPANY_OWNER: "مالک شرکت",
    MembershipRole.COMPANY_MANAGER: "مدیر شرکت",
    MembershipRole.OPERATIONS_MANAGER: "مدیر اجرایی",
    MembershipRole.MEMBER: "عضو",
    MembershipRole.VIEWER: "مشاهده‌گر",
    MembershipRole.TENANT_OWNER: "مالک شرکت",
    MembershipRole.TENANT_ADMIN: "مدیر محلی",
    MembershipRole.TENANT_MANAGER: "مدیر کسب‌وکار",
    MembershipRole.PROJECT_MANAGER: "مدیر پروژه",
    MembershipRole.ACCOUNTANT: "حسابدار",
    MembershipRole.SUPERVISOR: "ناظر",
}


def _role_label(*, code: str, name: str, is_system: bool) -> str:
    """Localize built-in header titles without renaming registered/custom roles."""
    return _BUILTIN_ROLE_LABELS.get(code, name) if is_system else name


@dataclass(frozen=True)
class HeaderIdentity:
    role_label: str
    position_title: str


def _own_position_title(membership: OrganizationMembership) -> str:
    organization = membership.organization
    user = membership.user
    if Person.objects.filter(organization=organization, user=user).exists():
        try:
            subject = resolve_ess_subject(user=user, organization=organization)
        except PermissionDenied:
            return ""
        employee = subject.current_relationship.legacy_employee
    else:
        # Preserve explicit legacy links only before a workforce relationship
        # exists. An expired/ambiguous canonical identity must not fall back.
        employee = Employee.objects.filter(
            organization=organization,
            user=user,
            work_relationships__isnull=True,
        ).first()
    if (
        employee is None
        or employee.organization_id != organization.pk
        or employee.user_id not in (None, user.pk)
        or employee.status != EmployeeStatus.ACTIVE
        or employee.archived_at is not None
    ):
        return ""
    today = timezone.localdate(timezone=ZoneInfo(organization.settings.timezone))
    return (
        EmployeePositionAssignment.objects.filter(
            organization=organization,
            employee=employee,
            status=PositionAssignmentStatus.ACTIVE,
            is_primary=True,
            start_date__lte=today,
            end_date__isnull=True,
            position__organization=organization,
            position__is_active=True,
            position__archived_at__isnull=True,
        )
        .values_list("position__title", flat=True)
        .first()
        or ""
    )


def membership_header_identity(
    *, membership: OrganizationMembership
) -> HeaderIdentity | None:
    """Project an own membership already resolved by get_active_membership.

    These labels confer no permission and never resolve a workforce identity
    through names, usernames, email addresses or employee numbers.
    """
    if (
        membership.status != MembershipStatus.ACTIVE
        or not membership.user.is_active
        or not membership.organization.is_active
    ):
        return None
    if membership.role_assignments.exists():
        role_names = tuple(
            dict.fromkeys(
                _role_label(code=code, name=name, is_system=is_system)
                for code, name, is_system in effective_role_assignments(membership)
                .filter(organization_id=membership.organization_id)
                .filter(
                    Q(role__organization_id=membership.organization_id)
                    | Q(role__organization__isnull=True)
                )
                .order_by("role__name", "role_id")
                .values_list("role__code", "role__name", "role__is_system")
            )
        )
    else:
        role = membership.role_definition
        role_names = (
            (_role_label(code=role.code, name=role.name, is_system=role.is_system),)
            if membership.authorization_migrated_at is None
            and role is not None
            and role.is_active
            and role.organization_id in (None, membership.organization_id)
            else ()
        )
    return HeaderIdentity(
        role_label="، ".join(role_names),
        position_title=_own_position_title(membership),
    )
