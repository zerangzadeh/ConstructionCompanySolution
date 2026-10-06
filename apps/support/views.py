from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.documents.models import DocumentConfidentiality
from apps.organizations.authorization import has_business_permission
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
    require_organization_permission,
)
from apps.organizations.models import BusinessPermissionCode
from apps.support.forms import (
    CaseAssignmentForm,
    CaseTransitionForm,
    SupportEvidenceForm,
)
from apps.support.models import (
    SupportAccessRequest,
    SupportCase,
    SupportEvidence,
)
from apps.support.services import (
    acknowledge_notification,
    assign_case,
    calendar_projection,
    confirm_access,
    create_case,
    link_evidence,
    list_notifications,
    request_access,
    revoke_access,
    transition_case,
)


@never_cache
@require_GET
@active_organization_required
def workbench(request):
    organization = request.organization
    surface = request.resolver_match.url_name
    required_permissions = {
        "workbench": BusinessPermissionCode.SUPPORT_CASE_VIEW,
        "notifications": BusinessPermissionCode.SUPPORT_NOTIFICATIONS_VIEW,
        "calendar": BusinessPermissionCode.SUPPORT_CALENDAR_VIEW,
        "cases": BusinessPermissionCode.SUPPORT_CASE_VIEW,
        "access": BusinessPermissionCode.SUPPORT_ACCESS_REQUEST,
    }
    require_organization_permission(request, required_permissions[surface])
    return render(
        request,
        "support/workbench.html",
        {
            "surface": surface,
            "notifications": list_notifications(
                organization=organization, actor=request.user
            )
            if surface in {"workbench", "notifications"}
            else [],
            "cases": SupportCase.objects.filter(
                organization=organization, requester=request.user
            )
            if surface in {"workbench", "cases"}
            else SupportCase.objects.none(),
            "calendar": calendar_projection(
                organization=organization, actor=request.user
            )
            if surface == "calendar"
            else [],
            "access_requests": SupportAccessRequest.objects.filter(
                organization=organization, requested_by=request.user
            )
            if surface == "access"
            else SupportAccessRequest.objects.none(),
        },
    )


@never_cache
@require_GET
@active_organization_required
@organization_permission_required(BusinessPermissionCode.SUPPORT_CASE_VIEW)
def case_detail(request, case_id):
    can_view_sensitive = has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.SUPPORT_EVIDENCE_SENSITIVE_VIEW,
    )
    evidence_queryset = SupportEvidence.objects.select_related(
        "document", "document_version"
    )
    if not can_view_sensitive:
        evidence_queryset = evidence_queryset.filter(
            document__confidentiality=DocumentConfidentiality.INTERNAL
        )
    case = (
        SupportCase.objects.filter(pk=case_id, organization=request.organization)
        .select_related("requester", "assignee")
        .prefetch_related("events", Prefetch("evidence", queryset=evidence_queryset))
        .first()
    )
    if case is None:
        raise Http404
    status_labels = {
        "open": "باز",
        "triaged": "بررسی اولیه",
        "in_progress": "در حال رسیدگی",
        "awaiting_requester": "در انتظار درخواست‌کننده",
        "resolved": "حل‌شده",
        "closed": "بسته‌شده",
    }
    return render(
        request,
        "support/case_detail.html",
        {
            "case": case,
            "status_label": status_labels.get(case.status, "نامشخص"),
            "assignment_form": CaseAssignmentForm(
                organization=request.organization, current_status=case.status
            ),
            "transition_form": CaseTransitionForm(current_status=case.status),
            "evidence_form": SupportEvidenceForm(
                organization=request.organization,
                can_view_sensitive=can_view_sensitive,
            ),
        },
    )


@require_POST
@active_organization_required
def acknowledge(request, notification_id):
    acknowledge_notification(
        organization=request.organization,
        actor=request.user,
        notification_id=notification_id,
    )
    return redirect("support:notifications")


@require_POST
@active_organization_required
def case_create(request):
    create_case(
        organization=request.organization,
        requester=request.user,
        category=request.POST.get("category", "general"),
        summary=request.POST.get("summary", ""),
        priority=request.POST.get("priority", "normal"),
    )
    return redirect("support:cases")


@require_POST
@active_organization_required
def case_transition(request, case_id):
    form = CaseTransitionForm(
        request.POST, current_status=request.POST.get("expected_status", "")
    )
    if form.is_valid():
        try:
            transition_case(
                organization=request.organization,
                actor=request.user,
                case_id=case_id,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValidationError, SupportCase.DoesNotExist) as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "وضعیت درخواست ثبت شد.")
    else:
        messages.error(request, "اطلاعات اقدام معتبر نیست.")
    return redirect("support:case_detail", case_id=case_id)


@require_POST
@active_organization_required
def case_assign(request, case_id):
    form = CaseAssignmentForm(
        request.POST,
        organization=request.organization,
        current_status=request.POST.get("expected_status", ""),
    )
    if form.is_valid():
        try:
            assign_case(
                organization=request.organization,
                actor=request.user,
                case_id=case_id,
                assignee=form.cleaned_data["assignee"],
                expected_status=form.cleaned_data["expected_status"],
            )
        except (PermissionDenied, ValidationError, SupportCase.DoesNotExist) as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "مسئول رسیدگی تعیین شد.")
    else:
        messages.error(request, "مسئول انتخاب‌شده معتبر نیست.")
    return redirect("support:case_detail", case_id=case_id)


@require_POST
@active_organization_required
def case_evidence(request, case_id):
    form = SupportEvidenceForm(
        request.POST,
        organization=request.organization,
        can_view_sensitive=has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=BusinessPermissionCode.SUPPORT_EVIDENCE_SENSITIVE_VIEW,
        ),
    )
    if form.is_valid():
        try:
            link_evidence(
                organization=request.organization,
                actor=request.user,
                case_id=case_id,
                document_version=form.cleaned_data["document_version"],
            )
        except (PermissionDenied, ValidationError, SupportCase.DoesNotExist) as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "نسخه دقیق سند به درخواست پیوند شد.")
    else:
        messages.error(request, "سند و نسخه انتخاب‌شده معتبر نیستند.")
    return redirect("support:case_detail", case_id=case_id)


@require_POST
@active_organization_required
def access_request(request):
    from django.utils.dateparse import parse_datetime

    request_access(
        organization=request.organization,
        actor=request.user,
        purpose=request.POST["purpose"],
        scope=request.POST["scope"],
        expires_at=parse_datetime(request.POST["expires_at"]),
    )
    return redirect("support:access")


@require_POST
@active_organization_required
def access_revoke(request, request_id):
    revoke_access(
        organization=request.organization, actor=request.user, request_id=request_id
    )
    return redirect("support:access")


@require_POST
@active_organization_required
def access_confirm(request, request_id, platform=False):
    confirm_access(
        organization=request.organization,
        actor=request.user,
        request_id=request_id,
        platform=platform,
    )
    return redirect("support:access")
