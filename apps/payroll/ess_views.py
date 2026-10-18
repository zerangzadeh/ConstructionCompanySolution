"""Thin ESS adapters; no salary calculations or independent inquiry states."""

import json
from functools import wraps
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
)
from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode as P
from apps.workflows.models import WorkflowTransitionDefinition, WorkItemStatus
from apps.workflows.runtime import claim_work_item, list_member_work_items

from . import ess_services as services
from .ess_forms import InquiryForm, ResponseForm
from .models import PayrollInquiryCategory


def private_surface(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except PermissionDenied:
            return HttpResponse(
                render_to_string("workforce/ess_unavailable.html"), status=403
            )
        except ValidationError:
            return render(request, "payroll/ess_error.html", status=400)

    return wrapped


@active_organization_required
@require_GET
@private_surface
def history(request):
    slips = services.own_payroll_history(
        actor=request.user, organization=request.organization
    )
    return render(request, "payroll/ess_history.html", {"payslips": slips})


@active_organization_required
@require_GET
@private_surface
def payslip(request, payslip_id):
    slip = services.own_payslip(
        actor=request.user, organization=request.organization, payslip_id=payslip_id
    )
    own = services.own_payroll_history(
        actor=request.user, organization=request.organization
    )
    lineage = [
        item
        for item in own
        if item.pk != slip.pk
        and (item.run.replaces_id == slip.run_id or slip.run.replaces_id == item.run_id)
    ]
    can_export = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.PAYROLL_ESS_EXPORT,
        project=slip.run_employee.project,
        site=slip.run_employee.site,
    )
    return render(
        request,
        "payroll/payslip.html",
        {
            "payslip": slip,
            "data": slip.presentation_snapshot,
            "ess_mode": True,
            "ess_export_url": reverse("payroll:ess_payslip_export", args=[slip.pk]),
            "ess_can_export": can_export,
            "ess_lineage": lineage,
        },
    )


@active_organization_required
@require_POST
@private_surface
def export(request, payslip_id):
    slip = services.own_payslip(
        actor=request.user,
        organization=request.organization,
        payslip_id=payslip_id,
        export=True,
    )
    response = HttpResponse(
        json.dumps(slip.presentation_snapshot, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="payslip-{slip.pk}.json"'
    return response


@active_organization_required
@require_GET
@private_surface
def inquiries(request):
    rows = [
        (item, services.inquiry_instance(item))
        for item in services.visible_inquiries(
            actor=request.user, organization=request.organization
        )
    ]
    return render(request, "payroll/ess_inquiries.html", {"rows": rows})


def _inquiry_form(request):
    slips = services.own_payroll_history(
        actor=request.user, organization=request.organization
    )
    services._require(
        actor=request.user,
        organization=request.organization,
        code=P.PAYROLL_INQUIRIES_REQUEST,
    )
    # Latest version of each explicitly registered category; never seed a list.
    categories = (
        PayrollInquiryCategory.objects.filter(
            organization=request.organization, workflow_version__status="published"
        )
        .order_by("code", "-version")
        .distinct("code")
    )
    form = InquiryForm(request.POST or None, initial={"idempotency_key": str(uuid4())})
    form.fields["payslip_id"].choices = [
        (str(item.pk), f"{item.run.period.name} — {item.number}") for item in slips
    ]
    form.fields["category_id"].choices = [
        (str(item.pk), item.name) for item in categories
    ]
    from apps.documents.services import (
        get_document_version_for_download,
        get_organization_documents,
    )

    choices = []
    try:
        for document in get_organization_documents(
            user=request.user, organization=request.organization
        ):
            try:
                version = get_document_version_for_download(
                    document=document,
                    version_id=str(document.current_version_id),
                    actor=request.user,
                )
                choices.append((str(version.pk), document.title))
            except PermissionDenied:
                continue
    except PermissionDenied:
        pass
    form.fields["document_version_ids"].choices = choices
    return form


@active_organization_required
@require_http_methods(["GET", "POST"])
@private_surface
def inquiry_create(request):
    form = _inquiry_form(request)
    if request.method == "POST" and form.is_valid():
        try:
            item = services.submit_inquiry(
                actor=request.user,
                organization=request.organization,
                **form.cleaned_data,
            )
            return redirect("payroll:ess_inquiry_detail", inquiry_id=item.pk)
        except ValidationError:
            form.add_error(
                None, "ثبت پرسش ممکن نشد؛ دسته، فیش و مسیر پاسخ‌گویی را بررسی کنید."
            )
    return render(request, "payroll/ess_inquiry_form.html", {"form": form})


def _handler_item(request, inquiry):
    try:
        membership = get_active_membership(
            user=request.user, organization=request.organization
        )
        return (
            list_member_work_items(
                actor=request.user, organization=request.organization
            )
            .filter(
                instance__subject_type=services.SUBJECT,
                instance__subject_id=inquiry.pk,
                current_assignee=membership,
                status=WorkItemStatus.CLAIMED,
            )
            .first()
        )
    except PermissionDenied:
        return None


@active_organization_required
@require_http_methods(["GET", "POST"])
@private_surface
def inquiry_detail(request, inquiry_id):
    item = services.get_inquiry(
        actor=request.user, organization=request.organization, inquiry_id=inquiry_id
    )
    instance = services.inquiry_instance(item)
    work_item = _handler_item(request, item)
    form = None
    if work_item:
        step = work_item.step_instance.step_definition
        transitions = WorkflowTransitionDefinition.objects.filter(
            version=instance.version, source_step=step
        )
        choices = [
            (t.outcome, t.outcome)
            for t in transitions
            if (t.domain_command or step.domain_command) == "payroll.inquiry.respond"
        ]
        form = ResponseForm(
            request.POST or None, initial={"idempotency_key": str(uuid4())}
        )
        form.fields["outcome"].choices = choices
    if request.method == "POST":
        if not form:
            raise PermissionDenied(services.DENIED)
        if form.is_valid():
            try:
                services.respond_inquiry(
                    actor=request.user,
                    organization=request.organization,
                    inquiry_id=item.pk,
                    work_item_id=work_item.pk,
                    **form.cleaned_data,
                )
                return redirect("payroll:ess_inquiry_detail", inquiry_id=item.pk)
            except ValidationError:
                form.add_error(
                    None, "ثبت پاسخ ممکن نشد؛ وضعیت و مسیر مجاز را بررسی کنید."
                )
    claimable = []
    if work_item is None:
        try:
            claimable = list(
                list_member_work_items(
                    actor=request.user, organization=request.organization
                ).filter(
                    instance__subject_type=services.SUBJECT,
                    instance__subject_id=item.pk,
                    status=WorkItemStatus.OPEN,
                )
            )
        except PermissionDenied:
            pass
    attachments = []
    from apps.documents.services import (
        get_document_version_for_download,
        get_organization_document,
    )

    for link in item.evidence_links.select_related("document", "document_version"):
        try:
            document = get_organization_document(
                user=request.user,
                organization=request.organization,
                document_id=str(link.document_id),
            )
            version = get_document_version_for_download(
                document=document,
                version_id=str(link.document_version_id),
                actor=request.user,
            )
            attachments.append((document, version))
        except PermissionDenied:
            continue
    return render(
        request,
        "payroll/ess_inquiry_detail.html",
        {
            "inquiry": item,
            "instance": instance,
            "responses": item.responses.order_by("created_at"),
            "form": form,
            "attachments": attachments,
            "claimable": claimable,
            "claim_key": str(uuid4()),
        },
    )


@active_organization_required
@require_POST
@private_surface
def inquiry_claim(request, inquiry_id, work_item_id):
    item = services.get_inquiry(
        actor=request.user, organization=request.organization, inquiry_id=inquiry_id
    )
    from apps.workflows.models import WorkItem

    if not WorkItem.objects.filter(
        pk=work_item_id,
        organization=request.organization,
        instance__subject_type=services.SUBJECT,
        instance__subject_id=item.pk,
    ).exists():
        raise PermissionDenied(services.DENIED)
    claim_work_item(
        actor=request.user,
        organization=request.organization,
        work_item_id=work_item_id,
        idempotency_key=request.POST.get("idempotency_key", ""),
    )
    return redirect("payroll:ess_inquiry_detail", inquiry_id=item.pk)
