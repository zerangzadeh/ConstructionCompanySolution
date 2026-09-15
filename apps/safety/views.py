from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from apps.safety.forms import (
    ClosureForm,
    CorrectiveActionForm,
    ResolutionForm,
    SafetyIncidentAssignmentForm,
    SafetyIncidentForm,
)
from apps.safety.models import (
    SafetyIncidentSeverity,
    SafetyIncidentStatus,
    SafetyIncidentType,
)
from apps.safety.services import (
    assign_safety_incident,
    close_safety_incident,
    create_safety_incident,
    get_organization_safety_incident,
    get_organization_safety_incidents,
    resolve_safety_incident,
    review_safety_incident,
    start_corrective_action,
)
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SAFETY_INCIDENTS_VIEW)
@require_GET
def incident_list(request: HttpRequest) -> HttpResponse:
    incidents = get_organization_safety_incidents(
        user=request.user, organization=request.organization
    )
    incidents = apply_table_filters(
        incidents,
        request,
        text_fields={
            "number": ("incident_number",),
            "project": ("project__name", "site__name"),
        },
        choice_fields={
            "incident_type": ("incident_type", SafetyIncidentType.values),
            "severity": ("severity", SafetyIncidentSeverity.values),
            "status": ("status", SafetyIncidentStatus.values),
        },
        date_fields={"occurred_at": "occurred_at__date"},
    )
    return render(
        request,
        "safety/list.html",
        {
            "incidents": incidents,
            "filters": build_table_filters(
                request,
                [
                    {"name": "number", "kind": "text", "label": "شماره"},
                    {"name": "project", "kind": "text", "label": "پروژه"},
                    {
                        "name": "incident_type",
                        "kind": "select",
                        "label": "نوع",
                        "choices": SafetyIncidentType.choices,
                    },
                    {
                        "name": "severity",
                        "kind": "select",
                        "label": "شدت",
                        "choices": SafetyIncidentSeverity.choices,
                    },
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": SafetyIncidentStatus.choices,
                    },
                    {"name": "occurred_at", "kind": "date_range", "label": "زمان وقوع"},
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SAFETY_INCIDENTS_CREATE)
def incident_create(request: HttpRequest) -> HttpResponse:
    form = SafetyIncidentForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            incident = create_safety_incident(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("safety:detail", incident_id=incident.pk)
    return render(request, "safety/create.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SAFETY_INCIDENTS_VIEW)
@require_GET
def incident_detail(request: HttpRequest, incident_id: str) -> HttpResponse:
    incident = get_organization_safety_incident(
        user=request.user,
        organization=request.organization,
        incident_id=incident_id,
    )
    return render(
        request,
        "safety/detail.html",
        {
            "incident": incident,
            "assignment_form": SafetyIncidentAssignmentForm(
                organization=request.organization
            ),
            "corrective_form": CorrectiveActionForm(),
            "resolution_form": ResolutionForm(),
            "closure_form": ClosureForm(),
        },
    )


def _transition_response(
    *,
    request: HttpRequest,
    incident_id: str,
    operation: object,
    form: object | None = None,
) -> HttpResponse:
    if form is not None and not form.is_valid():
        messages.error(request, "اطلاعات عملیات را بررسی کنید.")
        return redirect("safety:detail", incident_id=incident_id)
    try:
        kwargs = form.cleaned_data if form is not None else {}
        operation(
            organization=request.organization,
            actor=request.user,
            incident_id=incident_id,
            **kwargs,
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "وضعیت حادثه ایمنی به‌روزرسانی شد.")
    return redirect("safety:detail", incident_id=incident_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SAFETY_INCIDENTS_REVIEW)
@require_POST
def incident_review(request: HttpRequest, incident_id: str) -> HttpResponse:
    return _transition_response(
        request=request, incident_id=incident_id, operation=review_safety_incident
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SAFETY_INCIDENTS_REVIEW)
@require_POST
def incident_assign(request: HttpRequest, incident_id: str) -> HttpResponse:
    return _transition_response(
        request=request,
        incident_id=incident_id,
        operation=assign_safety_incident,
        form=SafetyIncidentAssignmentForm(
            request.POST, organization=request.organization
        ),
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SAFETY_INCIDENTS_MANAGE)
@require_POST
def corrective_action_start(request: HttpRequest, incident_id: str) -> HttpResponse:
    return _transition_response(
        request=request,
        incident_id=incident_id,
        operation=start_corrective_action,
        form=CorrectiveActionForm(request.POST),
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SAFETY_INCIDENTS_MANAGE)
@require_POST
def incident_resolve(request: HttpRequest, incident_id: str) -> HttpResponse:
    return _transition_response(
        request=request,
        incident_id=incident_id,
        operation=resolve_safety_incident,
        form=ResolutionForm(request.POST),
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.SAFETY_INCIDENTS_CLOSE)
@require_POST
def incident_close(request: HttpRequest, incident_id: str) -> HttpResponse:
    return _transition_response(
        request=request,
        incident_id=incident_id,
        operation=close_safety_incident,
        form=ClosureForm(request.POST),
    )
