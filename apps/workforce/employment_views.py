from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.organizations.decorators import active_organization_required

from .employment_services import own_employment_history


@active_organization_required
@require_GET
def employment_history(request):
    try:
        history = own_employment_history(
            actor=request.user, organization=request.organization
        )
        response = render(
            request, "workforce/employment_history.html", {"history": history}
        )
    except PermissionDenied:
        response = render(request, "workforce/ess_unavailable.html", status=403)
    except ValidationError:
        response = render(
            request,
            "workforce/employment_history.html",
            {"history_error": True},
            status=400,
        )
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Cookie"
    return response
