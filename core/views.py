"""Authenticated, neutral application entry."""

import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.organizations.services import get_valid_memberships
from core.home import authorized_home_links

logger = logging.getLogger(__name__)


@login_required
@require_GET
@never_cache
def home(request: HttpRequest) -> HttpResponse:
    """Present authorized destinations without querying domain business facts."""

    if getattr(request, "organization_access_denied", False):
        return render(request, "home.html", {"home_state": "unauthorized"}, status=403)

    organization = getattr(request, "organization", None)
    if organization is None:
        state = (
            "no_context" if get_valid_memberships(request.user).exists() else "empty"
        )
        return render(request, "home.html", {"home_state": state})

    try:
        workspaces, assigned_work, alerts = authorized_home_links(
            user=request.user, organization=organization
        )
    except PermissionDenied:
        return render(request, "home.html", {"home_state": "unauthorized"}, status=403)
    except Exception:
        logger.exception("Canonical Home link resolution failed")
        return render(request, "home.html", {"home_state": "error"}, status=503)

    state = "normal" if workspaces or assigned_work or alerts else "no_workspace"
    return render(
        request,
        "home.html",
        {
            "home_state": state,
            "home_organization": organization,
            "home_workspaces": workspaces,
            "home_assigned_work": assigned_work,
            "home_alerts": alerts,
        },
    )
