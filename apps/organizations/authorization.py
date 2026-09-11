from django.core.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
)


def _validate_access_context(*, user: User, organization: Organization) -> None:
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("ورود با حساب کاربری فعال الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("شرکت فعال نیست.")


def get_active_membership(
    *, user: User, organization: Organization
) -> OrganizationMembership:
    """Return the active tenant membership used as authorization source of truth."""

    _validate_access_context(user=user, organization=organization)
    try:
        return OrganizationMembership.objects.select_related("role_definition").get(
            user=user,
            organization=organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
        )
    except OrganizationMembership.DoesNotExist as exc:
        raise PermissionDenied("به این شرکت دسترسی ندارید.") from exc


def membership_has_permission(
    membership: OrganizationMembership,
    permission: str | BusinessPermissionCode,
) -> bool:
    if (
        membership.status != MembershipStatus.ACTIVE
        or not membership.role_definition.is_active
    ):
        return False
    return membership.role_definition.permissions.filter(
        code=str(permission),
        is_active=True,
    ).exists()


def has_business_permission(
    *,
    user: User,
    organization: Organization,
    permission: str | BusinessPermissionCode,
) -> bool:
    """Check a global system admin or an active tenant role capability."""

    try:
        _validate_access_context(user=user, organization=organization)
    except PermissionDenied:
        return False
    if user.is_superuser:
        return True
    try:
        membership = get_active_membership(user=user, organization=organization)
    except PermissionDenied:
        return False
    return membership_has_permission(membership, permission)


def require_business_permission(
    *,
    user: User,
    organization: Organization,
    permission: str | BusinessPermissionCode,
    message: str,
) -> OrganizationMembership | None:
    """Deny by default and return the checked membership for scoped workflows."""

    _validate_access_context(user=user, organization=organization)
    if user.is_superuser:
        return None
    membership = get_active_membership(user=user, organization=organization)
    if not membership_has_permission(membership, permission):
        raise PermissionDenied(message)
    return membership
