"""Fail-closed HTTP exposure guard; domain/service calls are unaffected."""

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

from core.product_surface import route_exposed


class ProductSurfaceMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if route_exposed(
            request.resolver_match.view_name, view_kwargs, user=request.user
        ):
            return (
                None  # Original authentication, tenant, scope and service guards run.
            )
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        # Deny routes outside the configured surface before invoking their views.
        raise PermissionDenied("این صفحه در دسترس نیست.")
