from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.organizations.authorization import get_active_membership
from apps.organizations.models import BusinessPermissionCode


def business_permissions(request: HttpRequest) -> dict[str, object]:
    """Expose the active role's capability codes to templates once per request."""

    organization = getattr(request, "organization", None)
    permission_codes: set[str] = set()
    if organization is not None and request.user.is_authenticated:
        if request.user.is_superuser and request.user.is_active:
            permission_codes = set(BusinessPermissionCode.values)
        else:
            try:
                membership = get_active_membership(
                    user=request.user,
                    organization=organization,
                )
            except PermissionDenied:
                pass
            else:
                permission_codes = set(
                    membership.role_definition.permissions.filter(
                        is_active=True
                    ).values_list("code", flat=True)
                )

    return {
        "business_permission_codes": permission_codes,
        "can_view_contracts": BusinessPermissionCode.CONTRACTS_VIEW in permission_codes,
        "can_manage_contracts": BusinessPermissionCode.CONTRACTS_CREATE
        in permission_codes,
    }
