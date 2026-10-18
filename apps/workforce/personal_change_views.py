"""Own request presentation with source reauthorization on every URL/action."""

from functools import wraps
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.organizations.authorization import get_active_membership
from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode as P
from apps.workflows.models import WorkItemStatus
from apps.workflows.personal_workspaces import build_my_requests
from apps.workflows.runtime import claim_work_item, list_member_work_items

from . import personal_change_services as service
from .ess_services import resolve_ess_subject
from .models import PersonalDataEnrollment
from .personal_change_forms import ChangeForm, DecisionForm


def private(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except PermissionDenied:
            return HttpResponse(
                render_to_string("workforce/ess_unavailable.html"), status=403
            )
        except ValidationError:
            return render(request, "workforce/personal_change_error.html", status=400)

    return wrapper


@active_organization_required
@require_GET
@private
def requests(request):
    resolve_ess_subject(user=request.user, organization=request.organization)
    rows = build_my_requests(actor=request.user, organization=request.organization)
    return render(request, "workforce/personal_change_requests.html", {"rows": rows})


@active_organization_required
@require_GET
@private
def request_status(request, source_type, source_id):
    subject = resolve_ess_subject(user=request.user, organization=request.organization)
    rows = build_my_requests(actor=request.user, organization=request.organization)
    row = next(
        (
            r
            for r in rows
            if r.source_type == source_type and str(r.source_id) == str(source_id)
        ),
        None,
    )
    if row is None:
        raise PermissionDenied(service.DENIED)
    # Source membership/request ownership was checked by its registered adapter;
    # additionally require an explicit Person/relationship, never User heuristics.
    return render(
        request,
        "workforce/personal_change_status.html",
        {"row": row, "person": subject.person},
    )


@active_organization_required
@require_http_methods(["GET", "POST"])
@private
def create(request):
    service.require(
        actor=request.user,
        organization=request.organization,
        code=P.PERSONAL_DATA_REQUEST,
    )
    service._own(actor=request.user, organization=request.organization)
    form = ChangeForm(request.POST or None, initial={"idempotency_key": str(uuid4())})
    policies = (
        PersonalDataEnrollment.objects.filter(
            organization=request.organization, workflow_version__status="published"
        )
        .order_by("family", "source_field", "-version")
        .distinct("family", "source_field")
    )
    form.fields["enrollment_id"].choices = [(str(p.pk), str(p)) for p in policies]
    if request.method == "POST" and form.is_valid():
        try:
            item = service.submit_change(
                actor=request.user,
                organization=request.organization,
                **form.cleaned_data,
            )
            return redirect("workforce:personal_change_detail", request_id=item.pk)
        except ValidationError:
            form.add_error(
                None,
                "ثبت درخواست ممکن نشد؛ مقدار، ثبت فیلد و مسیر مسئول مجاز را بررسی کنید.",
            )
    return render(request, "workforce/personal_change_form.html", {"form": form})


@active_organization_required
@require_GET
@private
def inbox(request):
    rows = [
        (item, service.instance_for(item))
        for item in service.visible_requests(
            actor=request.user, organization=request.organization
        )
    ]
    return render(request, "workforce/personal_change_inbox.html", {"rows": rows})


@active_organization_required
@require_http_methods(["GET", "POST"])
@private
def detail(request, request_id):
    item = service.get_request(
        actor=request.user, organization=request.organization, request_id=request_id
    )
    instance = service.instance_for(item)
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
    member = get_active_membership(user=request.user, organization=request.organization)
    assigned = next(
        (
            t
            for t in tasks
            if t.status == WorkItemStatus.CLAIMED and t.current_assignee_id == member.pk
        ),
        None,
    )
    form = None
    if assigned:
        form = DecisionForm(
            request.POST or None, initial={"idempotency_key": str(uuid4())}
        )
        form.fields["outcome"].choices = [
            (t.outcome, t.outcome)
            for t in assigned.step_instance.step_definition.outgoing_transitions.all()
        ]
    if request.method == "POST":
        if not form:
            raise PermissionDenied(service.DENIED)
        if form.is_valid():
            try:
                service.decide_change(
                    actor=request.user,
                    organization=request.organization,
                    request_id=item.pk,
                    work_item_id=assigned.pk,
                    **form.cleaned_data,
                )
                return redirect("workforce:personal_change_detail", request_id=item.pk)
            except ValidationError:
                form.add_error(
                    None,
                    "تصمیم اعمال نشد؛ وضعیت، دلیل یا تغییر هم‌زمان منبع را بررسی کنید.",
                )
    return render(
        request,
        "workforce/personal_change_detail.html",
        {
            "item": item,
            "instance": instance,
            "decision": getattr(item, "decision", None),
            "form": form,
            "claimable": [t for t in tasks if t.status == WorkItemStatus.OPEN],
            "cancel_allowed": item.requested_by_id == request.user.pk
            and item.enrollment.cancellation_allowed
            and instance
            and instance.status == "active",
            "action_key": str(uuid4()),
            "current_step": tasks[0].step_instance.step_definition.name
            if tasks
            else None,
        },
    )


@active_organization_required
@require_POST
@private
def claim(request, request_id, work_item_id):
    item = service.get_request(
        actor=request.user, organization=request.organization, request_id=request_id
    )
    from apps.workflows.models import WorkItem

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
    return redirect("workforce:personal_change_detail", request_id=item.pk)


@active_organization_required
@require_POST
@private
def cancel(request, request_id):
    service.cancel_change(
        actor=request.user,
        organization=request.organization,
        request_id=request_id,
        reason=request.POST.get("reason", ""),
        idempotency_key=request.POST.get("idempotency_key", ""),
    )
    return redirect("workforce:personal_change_detail", request_id=request_id)
