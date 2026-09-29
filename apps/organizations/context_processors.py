from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.organizations.authorization import (
    get_active_membership,
    is_platform_admin,
    membership_has_scope,
    membership_permission_codes,
    permission_supports_object_scope,
)
from apps.organizations.models import BusinessPermissionCode


def business_permissions(request: HttpRequest) -> dict[str, object]:
    """Expose the active role's capability codes to templates once per request."""

    organization = getattr(request, "organization", None)
    permission_codes: set[str] = set()
    if organization is not None and request.user.is_authenticated:
        try:
            membership = get_active_membership(
                user=request.user,
                organization=organization,
            )
        except PermissionDenied:
            pass
        else:
            permission_codes = {
                code
                for code in membership_permission_codes(membership)
                if membership_has_scope(
                    membership,
                    allow_any_scope=permission_supports_object_scope(code),
                )
            }

    return {
        "business_permission_codes": permission_codes,
        "platform_navigation_access": bool(
            request.user.is_authenticated and is_platform_admin(request.user)
        ),
        "can_view_contracts": BusinessPermissionCode.CONTRACTS_VIEW in permission_codes,
        "can_manage_contracts": BusinessPermissionCode.CONTRACTS_CREATE
        in permission_codes,
    }
