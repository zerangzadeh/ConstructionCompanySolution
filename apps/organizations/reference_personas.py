"""Read-only projection of approved reference definitions, never access authority."""

import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe

from apps.accounts.models import User
from apps.organizations.authorization import is_platform_admin


def reference_catalogue_enabled() -> bool:
    return bool(settings.DEBUG and settings.REFERENCE_PERSONA_CATALOGUE_ENABLED)


@login_required
@require_safe
def reference_persona_catalogue(request: HttpRequest) -> HttpResponse:
    """Discover reference metadata only; no tenant data or authority inference."""
    if not reference_catalogue_enabled():
        raise Http404
    if not is_platform_admin(request.user):
        raise PermissionDenied
    catalogue = json.loads(
        Path(__file__).with_name("reference_personas.json").read_text(encoding="utf8")
    )
    # Only explicitly mapped synthetic reference identifiers; no tenant records,
    # real names, emails, roles, memberships or account-detail links are loaded.
    mapped = {
        row["documented_identity"]
        for row in catalogue["personas"]
        if row["documented_identity"]
    }
    active_by_alias = dict(
        User.objects.filter(username__in=mapped).values_list("username", "is_active")
    )
    for row in catalogue["personas"]:
        alias = row["documented_identity"]
        row["identity_state"] = (
            "در منبع نگاشت نشده"
            if not alias
            else "حساب نگاشت‌شده یافت نشد"
            if alias not in active_by_alias
            else "حساب نگاشت‌شده فعال است"
            if active_by_alias[alias]
            else "حساب نگاشت‌شده غیرفعال است"
        )
    response = render(
        request, "organizations/reference_personas.html", {"catalogue": catalogue}
    )
    response["Cache-Control"] = "private, no-store"
    return response
