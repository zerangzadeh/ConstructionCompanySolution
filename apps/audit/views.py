from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.audit.services import get_organization_audit_events
from apps.organizations.decorators import active_organization_required


@active_organization_required
@require_GET
def audit_log(request: HttpRequest) -> HttpResponse:
    """Display audit events for the authenticated user's active organization."""

    events = get_organization_audit_events(
        user=request.user,
        organization=request.organization,
    )
    return render(request, "audit/log.html", {"events": events})
