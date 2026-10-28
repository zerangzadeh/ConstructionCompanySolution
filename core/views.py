"""Authenticated, neutral application entry."""

import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.organizations.decorators import active_organization_required
from apps.organizations.services import get_valid_memberships
from core.home import authorized_home_links
from core.product_surface import NAVIGATION_GROUPS, NavigationGroup
from core.search import search_active_organization

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
    routes = {link.route for link in workspaces}
    if assigned_work:
        routes.add(assigned_work.route)
    groups = tuple(
        NavigationGroup(
            group.key,
            group.label,
            tuple(link for link in group.links if link.route in routes),
        )
        for group in NAVIGATION_GROUPS
        if any(link.route in routes for link in group.links)
    )
    return render(
        request,
        "home.html",
        {
            "home_state": state,
            "home_organization": organization,
            "home_workspaces": workspaces,
            "home_assigned_work": assigned_work,
            "home_alerts": alerts,
            "home_groups": groups,
        },
    )


@active_organization_required
@require_GET
@never_cache
def global_search(request: HttpRequest) -> HttpResponse:
    """Render only source-authorized results for the governed safe-family allowlist."""

    search = search_active_organization(
        actor=request.user,
        organization=request.organization,
        query=request.GET.get("q", ""),
    )
    return render(request, "core/global_search.html", {"search": search})
