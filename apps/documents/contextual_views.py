"""Contextual UI for existing DMS creation and additive association only."""

from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.documents.association import (
    CONTEXT_DENIED,
    DOCUMENT_DENIED,
    association_choices,
    document_choice_label,
    link_in_context,
    resolve_association_context,
    upload_in_context,
)
from apps.documents.forms import (
    TARGET_FIELDS,
    ContextualDocumentCreateForm,
    ContextualDocumentLinkForm,
)
from apps.documents.models import DocumentConfidentiality
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode as P


def _context(request, target_type, target_id):
    if any(
        request.GET.get(name)
        for name in (
            "next",
            "return_url",
            "return_to",
            "organization",
            "organization_id",
            "related_to",
            "related_id",
            "target_type",
            "target_id",
        )
    ):
        raise PermissionDenied(CONTEXT_DENIED)
    for name in TARGET_FIELDS:
        if name in request.GET and (
            len(request.GET.getlist(name)) != 1
            or (
                request.GET[name]
                and (name != target_type or request.GET[name] != str(target_id))
            )
        ):
            raise PermissionDenied(CONTEXT_DENIED)
    return resolve_association_context(
        user=request.user,
        organization=request.organization,
        kind=target_type,
        identifier=target_id,
    )


@active_organization_required
@organization_permission_required(P.DOCUMENTS_VIEW)
@organization_permission_required(P.DOCUMENTS_UPLOAD)
@never_cache
@require_http_methods(["GET", "POST"])
def contextual_upload(request, target_type, target_id):
    context = _context(request, target_type, target_id)
    form = ContextualDocumentCreateForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        context=context,
        user=request.user,
        organization=request.organization,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        values = {
            name: data[name]
            for name in (
                "document_type",
                "title",
                "category",
                "reference",
                "description",
                "access_expires_at",
            )
        }
        values["confidentiality"] = (
            data["confidentiality"] or DocumentConfidentiality.INTERNAL
        )
        values["upload"] = data["file"]
        try:
            context, _ = upload_in_context(
                user=request.user,
                organization=request.organization,
                kind=target_type,
                identifier=target_id,
                values=values,
            )
        except PermissionDenied as exc:
            raise PermissionDenied(CONTEXT_DENIED) from exc
        except (ValidationError, IntegrityError, ValueError):
            form.add_error(
                None,
                "اطلاعات سند را بررسی کنید؛ ممکن است شماره مرجع قبلاً ثبت شده باشد.",
            )
        except OSError:
            form.add_error(None, "ذخیره فایل انجام نشد؛ دوباره تلاش کنید.")
        else:
            messages.success(
                request,
                "سند ثبت و پیوند شد. دریافت فایل پس از ارزیابی ایمنی امکان‌پذیر است.",
            )
            return redirect(context.source.url)
    return render(
        request,
        "documents/upload.html",
        {"form": form, "association_context": context},
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@organization_permission_required(P.DOCUMENTS_VIEW)
@organization_permission_required(P.DOCUMENTS_UPLOAD)
@never_cache
@require_http_methods(["GET", "POST"])
def contextual_link(request, target_type, target_id):
    context = _context(request, target_type, target_id)
    form = ContextualDocumentLinkForm(
        request.POST if request.method == "POST" else None,
        context=context,
        user=request.user,
        organization=request.organization,
    )
    if request.method == "POST" and form.is_valid():
        try:
            context, _ = link_in_context(
                user=request.user,
                organization=request.organization,
                kind=target_type,
                identifier=target_id,
                document_id=form.cleaned_data["document"].pk,
            )
        except PermissionDenied as exc:
            raise PermissionDenied(CONTEXT_DENIED) from exc
        except (ValidationError, IntegrityError, ValueError):
            form.add_error("document", DOCUMENT_DENIED)
        else:
            messages.success(request, "سند انتخاب‌شده به این سابقه پیوند شد.")
            return redirect(context.source.url)
    return render(
        request,
        "documents/contextual_link.html",
        {"form": form, "association_context": context},
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@organization_permission_required(P.DOCUMENTS_VIEW)
@organization_permission_required(P.DOCUMENTS_UPLOAD)
@never_cache
@require_GET
def contextual_choices(request, target_type, target_id):
    context = _context(request, target_type, target_id)
    query = request.GET.get("q", "").strip()[:200]
    try:
        page = max(1, min(int(request.GET.get("page", 1)), 100000))
    except (ValueError, TypeError):
        page = 1
    rows, more = association_choices(
        user=request.user,
        organization=request.organization,
        context=context,
        query=query,
        page=page,
    )
    response = JsonResponse(
        {
            "results": [
                {"value": str(row.pk), "label": document_choice_label(row)}
                for row in rows
            ],
            "next": request.path + "?" + urlencode({"q": query, "page": page + 1})
            if more
            else None,
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response
