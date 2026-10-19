"""Thin, tenant-scoped UI adapters over the existing workflow lifecycle."""

import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.organizations.decorators import (
    active_organization_required,
    require_organization_permission,
)
from apps.organizations.models import BusinessPermissionCode as P

from . import services
from .administration import configuration_payload, visible_versions
from .administration_forms import DefinitionForm, DraftForm, LifecycleForm
from .models import WorkflowVersionStatus
from .registry import registry

PREFIX = "workflows/administration/"
ACTIONS = {
    "validate": (P.WORKFLOWS_CHANGE_DRAFT, "اعتبارسنجی"),
    "publish": (P.WORKFLOWS_PUBLISH, "انتشار"),
    "retire": (P.WORKFLOWS_RETIRE, "بازنشستگی"),
    "supersede": (P.WORKFLOWS_PUBLISH, "جایگزینی نسخهٔ منتشرشده"),
    "new-draft": (P.WORKFLOWS_CHANGE_DRAFT, "ایجاد نسخهٔ پیش‌نویس"),
}


def _safe_message(message: str) -> str:
    if message in {
        "هدف مسیریابی وجود ندارد یا معتبر نیست.",
        "هدف مسیریابی متعلق به سازمان دیگری است.",
        "هدف مسیریابی فعال نیست.",
    }:
        return "هدف مسیریابی در این شرکت معتبر نیست."
    return message


def _version(request, version_id):
    return get_object_or_404(
        visible_versions(actor=request.user, organization=request.organization),
        pk=version_id,
    )


@active_organization_required
@require_GET
def definition_list(request: HttpRequest) -> HttpResponse:
    versions = visible_versions(actor=request.user, organization=request.organization)
    return render(request, PREFIX + "list.html", {"versions": versions})


@active_organization_required
@require_http_methods(["GET", "POST"])
def definition_create(request: HttpRequest) -> HttpResponse:
    require_organization_permission(request, P.WORKFLOWS_VIEW)
    require_organization_permission(request, P.WORKFLOWS_CREATE)
    form = DefinitionForm(
        request.POST if request.method == "POST" else None,
        organization=request.organization,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            version = services.create_workflow_draft(
                actor=request.user,
                organization=request.organization,
                workflow_type_code=data["workflow_type"].code,
                code=data["code"],
                name=data["name"],
                description=data["description"],
                scope=data["scope"],
            )
        except (ValidationError, IntegrityError):
            form.add_error(None, "تعریف با این مشخصات معتبر نیست یا قبلاً ثبت شده است.")
        else:
            return redirect("workflows:version_detail", version_id=version.pk)
    return render(
        request,
        PREFIX + "form.html",
        {"form": form, "page_title": "ایجاد تعریف گردش‌کار"},
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@require_GET
def version_detail(request: HttpRequest, version_id) -> HttpResponse:
    version = _version(request, version_id)
    configuration = configuration_payload(version)
    siblings = visible_versions(
        actor=request.user, organization=request.organization
    ).filter(definition=version.definition)
    return render(
        request,
        PREFIX + "detail.html",
        {
            "version": version,
            "siblings": siblings,
            "configuration": configuration,
            "configuration_text": json.dumps(
                configuration, ensure_ascii=False, indent=2
            ),
            "validation_report": [
                {**issue, "message": _safe_message(issue["message"])}
                for issue in version.validation_report
            ],
            "has_published": siblings.filter(status="published").exists(),
        },
    )


@active_organization_required
@require_http_methods(["GET", "POST"])
def version_edit(request: HttpRequest, version_id) -> HttpResponse:
    require_organization_permission(request, P.WORKFLOWS_CHANGE_DRAFT)
    version = _version(request, version_id)
    if version.status != WorkflowVersionStatus.DRAFT:
        raise PermissionDenied("تنها پیش‌نویس قابل ویرایش است.")
    form = DraftForm(
        request.POST if request.method == "POST" else None,
        workflow_type_code=version.definition.workflow_type.code,
        organization=request.organization,
        initial={
            "configuration": configuration_payload(version),
            "change_summary": version.change_summary,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.edit_workflow_draft(
                actor=request.user,
                organization=request.organization,
                version_id=version.pk,
                configuration=form.cleaned_data["configuration"],
                change_summary=form.cleaned_data["change_summary"],
            )
        except ValidationError as exc:
            form.add_error(
                None, ValidationError([_safe_message(m) for m in exc.messages])
            )
        else:
            return redirect("workflows:version_detail", version_id=version.pk)
    return render(
        request,
        PREFIX + "form.html",
        {
            "form": form,
            "version": version,
            "page_title": "ویرایش پیش‌نویس گردش‌کار",
            "registered_step_types": sorted(registry.step_types),
            "registered_resolvers": sorted(registry.routing_resolvers),
        },
        status=400 if request.method == "POST" else 200,
    )


@active_organization_required
@require_http_methods(["GET", "POST"])
def version_action(request: HttpRequest, version_id, action: str) -> HttpResponse:
    if action not in ACTIONS:
        raise Http404
    permission, title = ACTIONS[action]
    require_organization_permission(request, permission)
    version = _version(request, version_id)
    form = LifecycleForm(
        request.POST if request.method == "POST" else None,
        needs_reason=action in {"retire", "supersede"},
    )
    if request.method == "POST" and form.is_valid():
        kwargs = {"actor": request.user, "organization": request.organization}
        try:
            if action == "new-draft":
                version = services.create_draft_version(
                    **kwargs,
                    definition_id=version.definition_id,
                    change_summary=form.cleaned_data["reason"],
                )
            elif action == "supersede":
                replaced = (
                    visible_versions(**kwargs)
                    .filter(definition=version.definition, status="published")
                    .first()
                )
                if replaced is None:
                    raise ValidationError("نسخهٔ منتشرشده‌ای برای جایگزینی وجود ندارد.")
                version = services.supersede_workflow_version(
                    **kwargs,
                    new_version_id=version.pk,
                    replaced_version_id=replaced.pk,
                    reason=form.cleaned_data["reason"],
                )
            elif action == "retire":
                services.retire_workflow_version(
                    **kwargs, version_id=version.pk, reason=form.cleaned_data["reason"]
                )
            elif action == "validate":
                report = services.validate_workflow_draft(
                    **kwargs, version_id=version.pk
                )
                if report:
                    messages.error(
                        request, "اعتبارسنجی نیازمند اصلاح است؛ گزارش را ببینید."
                    )
            else:
                services.publish_workflow_version(**kwargs, version_id=version.pk)
        except ValidationError as exc:
            form.add_error(
                None, ValidationError([_safe_message(m) for m in exc.messages])
            )
        else:
            return redirect("workflows:version_detail", version_id=version.pk)
    return render(
        request,
        PREFIX + "form.html",
        {"form": form, "version": version, "page_title": title},
        status=400 if request.method == "POST" else 200,
    )
