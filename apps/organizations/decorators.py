from collections.abc import Callable
from functools import wraps
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from apps.organizations.authorization import (
    has_business_permission,
    permission_supports_object_scope,
)
from apps.organizations.models import BusinessPermissionCode


def require_organization_permission(
    request: HttpRequest,
    permission: str | BusinessPermissionCode,
    message: str = "اجازه انجام این عملیات در شرکت فعال را ندارید.",
) -> None:
    """Raise a uniform 403 when the active role lacks one capability."""

    organization = getattr(request, "organization", None)
    if organization is None or not has_business_permission(
        user=request.user,
        organization=organization,
        permission=permission,
        allow_any_scope=permission_supports_object_scope(permission),
    ):
        raise PermissionDenied(message)


def active_organization_required(
    view_func: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """Require an authenticated request with a validated active organization."""

    @wraps(view_func)
    def wrapped(
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if getattr(request, "organization", None) is None:
            if getattr(request, "organization_access_denied", False):
                raise PermissionDenied(
                    "شرکت انتخاب‌شده فعال نیست یا عضویت معتبر وجود ندارد."
                )
            return redirect("organizations:select")
        return view_func(request, *args, **kwargs)

    return wrapped


def organization_permission_required(
    permission: str | BusinessPermissionCode,
    message: str = "اجازه انجام این عملیات در شرکت فعال را ندارید.",
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    """Enforce one tenant capability at the HTTP boundary.

    Apply this below ``active_organization_required`` so the active organization
    has already been resolved from the authenticated membership and session.
    """

    def decorator(
        view_func: Callable[..., HttpResponse],
    ) -> Callable[..., HttpResponse]:
        @wraps(view_func)
        def wrapped(
            request: HttpRequest,
            *args: Any,
            **kwargs: Any,
        ) -> HttpResponse:
            require_organization_permission(request, permission, message)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
