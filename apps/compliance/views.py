from __future__ import annotations

import csv
import io
from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Model
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.compliance.forms import (
    CapaForm,
    EvidenceForm,
    FindingForm,
    InspectionForm,
    NcrForm,
    PermitForm,
    QualityTestForm,
    TemplateForm,
    TemplatePublishForm,
    TransitionForm,
)
from apps.compliance.models import (
    CapaAction,
    ComplianceLifecycleEvent,
    ControlProfile,
    Inspection,
    InspectionFinding,
    InspectionTemplate,
    Nonconformance,
    Permit,
    QualityTest,
)
from apps.compliance.services import (
    CAPA_TRANSITIONS,
    FINDING_TRANSITIONS,
    INSPECTION_TRANSITIONS,
    NCR_TRANSITIONS,
    PERMIT_TRANSITIONS,
    TEST_TRANSITIONS,
    compliance_export_rows,
    create_capa,
    create_finding,
    create_inspection,
    create_permit,
    create_template,
    create_test,
    link_evidence,
    promote_finding_to_ncr,
    publish_template_version,
    reconcile_compliance,
    scoped_inspections,
    transition_record,
)
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode

MODEL_MAP: dict[str, type[Model]] = {
    "inspection": Inspection,
    "permit": Permit,
    "test": QualityTest,
    "finding": InspectionFinding,
    "ncr": Nonconformance,
    "capa": CapaAction,
}
TRANSITION_MAP = {
    "inspection": INSPECTION_TRANSITIONS,
    "permit": PERMIT_TRANSITIONS,
    "test": TEST_TRANSITIONS,
    "finding": FINDING_TRANSITIONS,
    "ncr": NCR_TRANSITIONS,
    "capa": CAPA_TRANSITIONS,
}
FORM_MAP = {
    "template": TemplateForm,
    "inspection": InspectionForm,
    "permit": PermitForm,
    "test": QualityTestForm,
    "finding": FindingForm,
    "ncr": NcrForm,
    "capa": CapaForm,
}
LABELS = {
    "template": "الگوی بازرسی",
    "inspection": "بازرسی",
    "permit": "مجوز HSE",
    "test": "آزمون QA/QC",
    "finding": "یافته",
    "ncr": "عدم انطباق رسمی",
    "capa": "CAPA",
}


def _scoped(queryset: Any, request: HttpRequest) -> Any:
    membership = get_active_membership(
        user=request.user, organization=request.organization
    )
    return scope_queryset(
        queryset,
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_VIEW)
@require_GET
def workbench(request: HttpRequest) -> HttpResponse:
    inspections = scoped_inspections(
        organization=request.organization, actor=request.user
    )
    context = {
        "hse_inspections": inspections.filter(profile=ControlProfile.HSE)[:30],
        "qa_inspections": inspections.filter(profile=ControlProfile.QA_QC)[:30],
        "permits": _scoped(
            Permit.objects.filter(organization=request.organization).select_related(
                "project", "site"
            ),
            request,
        )[:30],
        "tests": _scoped(
            QualityTest.objects.filter(
                organization=request.organization
            ).select_related("project", "site"),
            request,
        )[:30],
        "findings": _scoped(
            InspectionFinding.objects.filter(
                organization=request.organization
            ).select_related("project", "site"),
            request,
        )[:30],
        "ncrs": _scoped(
            Nonconformance.objects.filter(
                organization=request.organization
            ).select_related("project", "site"),
            request,
        )[:30],
        "capas": _scoped(
            CapaAction.objects.filter(organization=request.organization).select_related(
                "project", "site"
            ),
            request,
        )[:30],
        "templates": InspectionTemplate.objects.filter(
            organization=request.organization
        ).select_related("current_version")[:30],
    }
    return render(request, "compliance/workbench.html", context)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_EXPORT)
@require_GET
def export_csv(request: HttpRequest) -> HttpResponse:
    rows = compliance_export_rows(
        organization=request.organization,
        actor=request.user,
    )
    stream = io.StringIO()
    fieldnames = [
        "record_type",
        "id",
        "number",
        "profile",
        "status",
        "project_id",
        "site_id",
        "updated_at",
    ]
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    response = HttpResponse(stream.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="compliance-export.csv"'
    return response


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_AUDIT_RECONCILE)
@require_GET
def assurance(request: HttpRequest) -> HttpResponse:
    result = reconcile_compliance(
        organization=request.organization,
        actor=request.user,
    )
    return render(request, "compliance/assurance.html", {"result": result})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_VIEW)
@require_http_methods(["GET", "POST"])
def create_record(request: HttpRequest, kind: str) -> HttpResponse:
    form_class = FORM_MAP.get(kind)
    if form_class is None:
        raise Http404
    kwargs: dict[str, Any] = (
        {"organization": request.organization} if kind not in {"template"} else {}
    )
    form = form_class(request.POST or None, **kwargs)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            if kind == "template":
                record = create_template(
                    organization=request.organization, actor=request.user, **data
                )
            elif kind == "inspection":
                record = create_inspection(
                    organization=request.organization, actor=request.user, **data
                )
            elif kind == "permit":
                record = create_permit(
                    organization=request.organization, actor=request.user, **data
                )
            elif kind == "test":
                record = create_test(
                    organization=request.organization, actor=request.user, **data
                )
            elif kind == "finding":
                record = create_finding(
                    organization=request.organization, actor=request.user, **data
                )
            elif kind == "ncr":
                record = promote_finding_to_ncr(
                    organization=request.organization,
                    actor=request.user,
                    finding_id=str(data["finding"].pk),
                    number=data["number"],
                    description=data["description"],
                )
            else:
                source = data.pop("nonconformance") or data.pop("finding")
                record = create_capa(
                    organization=request.organization,
                    actor=request.user,
                    source=source,
                    **data,
                )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{LABELS[kind]} ثبت شد.")
            if kind == "template":
                return redirect("compliance:template_publish", template_id=record.pk)
            return redirect("compliance:detail", kind=kind, record_id=record.pk)
    return render(
        request, "compliance/form.html", {"form": form, "title": f"ثبت {LABELS[kind]}"}
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_TEMPLATES_PUBLISH)
@require_http_methods(["GET", "POST"])
def template_publish(request: HttpRequest, template_id: str) -> HttpResponse:
    template = get_object_or_404(
        InspectionTemplate, pk=template_id, organization=request.organization
    )
    form = TemplatePublishForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            publish_template_version(
                organization=request.organization,
                actor=request.user,
                template_id=str(template.pk),
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "نسخه تغییرناپذیر الگو منتشر شد.")
            return redirect("compliance:workbench")
    return render(
        request,
        "compliance/form.html",
        {"form": form, "title": f"انتشار نسخه {template.title}"},
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_VIEW)
@require_GET
def record_detail(request: HttpRequest, kind: str, record_id: str) -> HttpResponse:
    model = MODEL_MAP.get(kind)
    if model is None:
        raise Http404
    record = get_object_or_404(model, pk=record_id, organization=request.organization)
    require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.COMPLIANCE_VIEW,
        project=record.project,
        site=record.site,
        allow_site_parent=True,
        message="اجازه مشاهده این رکورد HSE/QA را ندارید.",
    )
    transitions = list(TRANSITION_MAP[kind].get(record.status, set()))
    status_labels = dict(record._meta.get_field("status").flatchoices)
    events = ComplianceLifecycleEvent.objects.filter(
        organization=request.organization,
        entity_type=model._meta.label_lower,
        entity_id=record.pk,
    ).select_related("actor")
    for event in events:
        event.from_label = status_labels.get(event.from_status, "—")
        event.to_label = status_labels.get(event.to_status, "وضعیت ثبت‌شده")
    transition_forms = [
        (
            status_labels.get(status, "وضعیت ثبت‌شده"),
            TransitionForm(
                initial={"expected_status": record.status, "to_status": status}
            ),
        )
        for status in sorted(transitions)
    ]
    return render(
        request,
        "compliance/detail.html",
        {
            "kind": kind,
            "label": LABELS[kind],
            "record": record,
            "transition_forms": transition_forms,
            "events": events,
            "evidence_form": EvidenceForm(organization=request.organization),
        },
    )


@active_organization_required
@require_POST
def record_transition(request: HttpRequest, kind: str, record_id: str) -> HttpResponse:
    model = MODEL_MAP.get(kind)
    if model is None:
        raise Http404
    form = TransitionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "اطلاعات گذار وضعیت معتبر نیست.")
        return redirect("compliance:detail", kind=kind, record_id=record_id)
    try:
        transition_record(
            organization=request.organization,
            actor=request.user,
            model=model,
            record_id=record_id,
            **form.cleaned_data,
        )
    except (PermissionDenied, ValidationError, ValueError, model.DoesNotExist) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "وضعیت با سابقه تغییرناپذیر به‌روزرسانی شد.")
    return redirect("compliance:detail", kind=kind, record_id=record_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.COMPLIANCE_EVIDENCE_LINK)
@require_POST
def evidence_link(request: HttpRequest, kind: str, record_id: str) -> HttpResponse:
    model = MODEL_MAP.get(kind)
    if model is None:
        raise Http404
    record = get_object_or_404(model, pk=record_id, organization=request.organization)
    require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.COMPLIANCE_EVIDENCE_LINK,
        project=record.project,
        site=record.site,
        allow_site_parent=True,
        message="اجازه پیوند شاهد به این رکورد را ندارید.",
    )
    form = EvidenceForm(request.POST, organization=request.organization)
    if form.is_valid():
        try:
            link_evidence(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
                **{kind if kind != "ncr" else "nonconformance": record},
            )
        except (PermissionDenied, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "نسخه دقیق شاهد DMS پیوند شد.")
    else:
        messages.error(request, "نسخه یا کاربرد شاهد معتبر نیست.")
    return redirect("compliance:detail", kind=kind, record_id=record_id)
