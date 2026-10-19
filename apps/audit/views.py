from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.audit.services import get_organization_audit_events
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from core.list_filters import paginate_table


@active_organization_required
@organization_permission_required(BusinessPermissionCode.AUDIT_VIEW)
@require_GET
def audit_log(request: HttpRequest) -> HttpResponse:
    """Display audit events for the authenticated user's active organization."""

    events = get_organization_audit_events(
        user=request.user,
        organization=request.organization,
    )
    page = paginate_table(
        events,
        request,
        sort_fields={},
        default_ordering=("-created_at", "-pk"),
        per_page=25,
    )
    return render(
        request, "audit/log.html", {"events": page.object_list, "page_obj": page}
    )
