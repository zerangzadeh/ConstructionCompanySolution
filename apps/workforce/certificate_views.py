from datetime import date
from functools import wraps
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.documents.employee_access import get_employee_version_for_download
from apps.organizations.authorization import get_active_membership
from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode as P
from apps.workflows.models import WorkItem, WorkItemStatus
from apps.workflows.runtime import (
    claim_work_item,
    complete_work_item,
    list_member_work_items,
)
from core.jalali import format_jalali

from . import certificate_services as service
from .certificate_forms import CertificateRequestForm
from .own_evidence import build_own_evidence
from .personal_change_forms import DecisionForm


def private(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except PermissionDenied:
            return HttpResponse(
                render_to_string("workforce/ess_unavailable.html"), status=403
            )
        except (ValidationError, ValueError, OSError, RuntimeError):
            return render(request, "workforce/certificate_error.html", status=400)

    return wrapped


@active_organization_required
@require_GET
@private
def evidence(request):
    return render(
        request,
        "workforce/own_evidence.html",
        {
            "evidence": build_own_evidence(
                actor=request.user, organization=request.organization
            )
        },
    )


@active_organization_required
@require_GET
@private
def index(request):
    rows = service.visible_requests(
        actor=request.user, organization=request.organization
    )
    return render(request, "workforce/certificate_index.html", {"rows": rows})


@active_organization_required
@require_http_methods(["GET", "POST"])
@private
def create(request):
    kinds = service.available_types(
        actor=request.user, organization=request.organization
    )
    previous = service.visible_requests(
        actor=request.user, organization=request.organization
    )
    form = CertificateRequestForm(
        request.POST or None, initial={"idempotency_key": str(uuid4())}
    )
    form.fields["type_id"].choices = [(str(k.pk), k.name) for k in kinds]
    form.fields["replaces_id"].choices = [("", "بدون جایگزینی")] + [
        (str(i.pk), i.certificate_type.name + " — " + str(i.pk)[:8])
        for i in previous
        if i.requested_by_id == request.user.pk and getattr(i, "generation", None)
    ]
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data
        values["replaces_id"] = values["replaces_id"] or None
        try:
            item = service.submit_request(
                actor=request.user, organization=request.organization, **values
            )
            return redirect("workforce:certificate_detail", request_id=item.pk)
        except ValidationError:
            form.add_error(
                None, "ثبت درخواست ممکن نشد؛ نوع، سیاست و مسیر مجاز را بررسی کنید."
            )
    return render(
        request,
        "workforce/certificate_form.html",
        {"form": form, "available": bool(kinds)},
    )


@active_organization_required
@require_http_methods(["GET", "POST"])
@private
def detail(request, request_id):
    item = service.get_request(
        actor=request.user, organization=request.organization, request_id=request_id
    )
    member = get_active_membership(user=request.user, organization=request.organization)
    tasks = []
    try:
        tasks = list(
            list_member_work_items(
                actor=request.user, organization=request.organization
            ).filter(
                instance__subject_type=service.SUBJECT, instance__subject_id=item.pk
            )
        )
    except PermissionDenied:
        pass
    task = next(
        (
            t
            for t in tasks
            if t.status == WorkItemStatus.CLAIMED and t.current_assignee_id == member.pk
        ),
        None,
    )
    form = None
    if task:
        form = DecisionForm(
            request.POST or None, initial={"idempotency_key": str(uuid4())}
        )
        form.fields["outcome"].choices = [
            (t.outcome, t.outcome)
            for t in task.step_instance.step_definition.outgoing_transitions.all()
        ]
    if request.method == "POST":
        if not task:
            raise PermissionDenied(service.DENIED)
        service.require(
            actor=request.user,
            organization=request.organization,
            code=P.HR_CERTIFICATES_REVIEW,
        )
        if form.is_valid():
            try:
                complete_work_item(
                    actor=request.user,
                    organization=request.organization,
                    work_item_id=task.pk,
                    outcome=form.cleaned_data["outcome"],
                    idempotency_key=form.cleaned_data["idempotency_key"],
                    command_context={
                        "employee_visible_reason": form.cleaned_data["reason"]
                    },
                )
                return redirect("workforce:certificate_detail", request_id=item.pk)
            except ValidationError:
                form.add_error(
                    None, "تصمیم بررسی اعمال نشد؛ وضعیت و دلیل مجاز را بررسی کنید."
                )
    generated = getattr(item, "generation", None)
    cancelled = getattr(item, "cancellation", None)
    download_url = None
    if generated:
        try:
            version = get_employee_version_for_download(
                user=request.user,
                organization=request.organization,
                document_id=str(generated.document_version.document_id),
                version_id=str(generated.document_version_id),
            )
            download_url = reverse(
                "documents:employee-version-download",
                args=[version.document_id, version.pk],
            )
        except PermissionDenied:
            try:
                service._generator(
                    actor=request.user,
                    organization=request.organization,
                    certificate_type=item.certificate_type,
                )
                from apps.documents.services import (
                    get_document_version_for_download,
                    get_organization_document,
                )

                document = get_organization_document(
                    user=request.user,
                    organization=request.organization,
                    document_id=str(generated.document_version.document_id),
                )
                version = get_document_version_for_download(
                    document=document,
                    version_id=str(generated.document_version_id),
                    actor=request.user,
                )
                download_url = reverse(
                    "documents:version-download", args=[version.document_id, version.pk]
                )
            except PermissionDenied:
                pass
    can_generate = False
    try:
        service._generator(
            actor=request.user,
            organization=request.organization,
            certificate_type=item.certificate_type,
        )
        service.activation(item.certificate_type)
        review = getattr(item, "review", None)
        can_generate = (
            not generated
            and not cancelled
            and (
                not item.certificate_type.review_version_id
                or (review and review.outcome == "accepted")
            )
        )
    except (PermissionDenied, ValidationError):
        pass
    labels = {
        "person.first_name": "نام",
        "person.last_name": "نام خانوادگی",
        "relationship.employee_number": "شماره رابطه کاری",
        "relationship.effective_start": "آغاز رابطه کاری",
        "relationship.effective_end": "پایان رابطه کاری",
    }
    fields = []
    for alias, code in item.certificate_type.source_map.items():
        value = item.source_snapshot["fields"].get(alias)
        if value and code in {
            "relationship.effective_start",
            "relationship.effective_end",
        }:
            value = format_jalali(date.fromisoformat(value))
        fields.append((labels.get(code, "فیلد منبع"), value))
    return render(
        request,
        "workforce/certificate_detail.html",
        {
            "item": item,
            "instance": service.instance_for(item),
            "review": getattr(item, "review", None),
            "generation": generated,
            "cancellation": cancelled,
            "fields": fields,
            "form": form,
            "download_url": download_url,
            "can_generate": can_generate,
            "can_cancel": not cancelled
            and not generated
            and item.requested_by_id == request.user.pk
            and item.certificate_type.cancellation_before_output,
            "claimable": [t for t in tasks if t.status == WorkItemStatus.OPEN],
            "action_key": str(uuid4()),
        },
    )


@active_organization_required
@require_POST
@private
def generate(request, request_id):
    service.generate_certificate(
        actor=request.user, organization=request.organization, request_id=request_id
    )
    return redirect("workforce:certificate_detail", request_id=request_id)


@active_organization_required
@require_POST
@private
def claim(request, request_id, work_item_id):
    item = service.get_request(
        actor=request.user, organization=request.organization, request_id=request_id
    )
    if not WorkItem.objects.filter(
        pk=work_item_id,
        organization=request.organization,
        instance__subject_type=service.SUBJECT,
        instance__subject_id=item.pk,
    ).exists():
        raise PermissionDenied(service.DENIED)
    claim_work_item(
        actor=request.user,
        organization=request.organization,
        work_item_id=work_item_id,
        idempotency_key=request.POST.get("idempotency_key", ""),
    )
    return redirect("workforce:certificate_detail", request_id=item.pk)


@active_organization_required
@require_POST
@private
def cancel(request, request_id):
    service.cancel_request(
        actor=request.user,
        organization=request.organization,
        request_id=request_id,
        reason=request.POST.get("reason", ""),
        idempotency_key=request.POST.get("idempotency_key", ""),
    )
    return redirect("workforce:certificate_detail", request_id=request_id)
