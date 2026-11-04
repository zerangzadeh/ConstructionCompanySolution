"""HTTP adapters for existing version-aware domain evidence services."""

from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.documents.evidence import (
    DENIED,
    can_register,
    choice_page,
    eligible_versions,
    picker_source,
    pinned_row,
    references,
    resolve_evidence_source,
    version_label,
)
from apps.documents.evidence_forms import EvidenceRegistrationForm
from apps.documents.evidence_registration import register_evidence as _register
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P


def _safe_request(request):
    if any(
        request.GET.get(name)
        for name in (
            "next",
            "return_url",
            "return_to",
            "organization",
            "organization_id",
            "target_id",
            "target_type",
        )
    ):
        raise PermissionDenied(DENIED)


@never_cache
@active_organization_required
@organization_permission_required(P.DOCUMENTS_VIEW)
@require_GET
def evidence_detail(
    request: HttpRequest, kind: str, source_id: str, version_id: str
) -> HttpResponse:
    _safe_request(request)
    source = resolve_evidence_source(
        user=request.user,
        organization=request.organization,
        kind=kind,
        identifier=source_id,
    )
    status = next(
        (
            status
            for identifier, status in references(source)
            if str(identifier) == str(version_id)
        ),
        None,
    )
    if status is None:
        raise PermissionDenied(DENIED)
    row = pinned_row(
        user=request.user,
        organization=request.organization,
        source=source,
        version_id=version_id,
        status=status,
    )
    return render(
        request, "documents/evidence_detail.html", {"source": source, "row": row}
    )


@never_cache
@active_organization_required
@organization_permission_required(P.DOCUMENTS_VIEW)
@require_GET
def evidence_choices(
    request: HttpRequest, kind: str, source_id: str | None = None
) -> JsonResponse:
    _safe_request(request)
    source = picker_source(
        user=request.user,
        organization=request.organization,
        kind=kind,
        identifier=source_id,
    )
    query = request.GET.get("q", "").strip()[:200]
    try:
        page = max(1, min(int(request.GET.get("page", 1)), 100000))
    except (TypeError, ValueError):
        page = 1
    versions = eligible_versions(
        user=request.user,
        organization=request.organization,
        kind=kind,
        source=source,
        query=query,
    )
    rows, more = choice_page(versions, page=page)
    response = JsonResponse(
        {
            "results": [
                {"value": str(row.pk), "label": version_label(row)} for row in rows
            ],
            "next": request.path + "?" + urlencode({"q": query, "page": page + 1})
            if more
            else None,
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response


@never_cache
@active_organization_required
@organization_permission_required(P.DOCUMENTS_VIEW)
@require_http_methods(["GET", "POST"])
def evidence_register(request: HttpRequest, kind: str, source_id: str) -> HttpResponse:
    _safe_request(request)
    source = resolve_evidence_source(
        user=request.user,
        organization=request.organization,
        kind=kind,
        identifier=source_id,
    )
    if not can_register(
        user=request.user, organization=request.organization, source=source
    ):
        raise PermissionDenied(DENIED)
    form = EvidenceRegistrationForm(
        request.POST if request.method == "POST" else None,
        source=source,
        user=request.user,
        organization=request.organization,
    )
    if request.method == "POST" and form.is_valid():
        try:
            source = _register(
                user=request.user,
                organization=request.organization,
                kind=kind,
                source_id=source_id,
                values=form.cleaned_data,
            )
        except PermissionDenied as exc:
            raise PermissionDenied(DENIED) from exc
        except (ValidationError, IntegrityError, ValueError):
            form.add_error(
                None, "ثبت انجام نشد؛ اطلاعات، وضعیت سابقه و نسخه شاهد را بررسی کنید."
            )
        else:
            messages.success(
                request,
                "رکورد برای بررسی ارسال شد و شواهد انتخاب‌شده ثبت شد."
                if kind in {"safety", "quality"}
                else "نسخه شاهد به سابقه پیوند خورد.",
            )
            return redirect(source.url)
    return render(
        request,
        "documents/evidence_register.html",
        {"form": form, "source": source},
        status=400 if request.method == "POST" else 200,
    )
