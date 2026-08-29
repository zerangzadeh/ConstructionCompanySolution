from collections.abc import Callable
from functools import wraps
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


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
            return redirect("organizations:select")
        return view_func(request, *args, **kwargs)

    return wrapped
