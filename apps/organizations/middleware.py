from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    resolve_active_organization,
    resolve_session_organization,
    set_active_organization,
)


class OrganizationMiddleware:
    """Attach the authenticated user's active organization to each request."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.organization = None
        request.organization_access_denied = False

        if request.user.is_authenticated:
            had_selected_organization = (
                ACTIVE_ORGANIZATION_SESSION_KEY in request.session
            )
            organization = resolve_session_organization(
                request.user,
                request.session,
            )
            request.organization_access_denied = bool(
                had_selected_organization and organization is None
            )

            if (
                organization is None
                and not had_selected_organization
                and ACTIVE_ORGANIZATION_SESSION_KEY not in request.session
            ):
                organization = resolve_active_organization(request.user)
                if organization is not None:
                    set_active_organization(request.session, organization)

            request.organization = organization

        return self.get_response(request)
