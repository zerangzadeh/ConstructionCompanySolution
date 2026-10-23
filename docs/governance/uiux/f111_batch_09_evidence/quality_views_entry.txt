from collections.abc import Callable

from django import forms
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
from apps.quality.forms import (
    ClosureForm,
    CorrectiveActionForm,
    QualityIssueAssignmentForm,
    QualityIssueForm,
    VerificationForm,
    VerificationSubmissionForm,
)
from apps.quality.models import (
    QualityIssueSeverity,
    QualityIssueStatus,
    QualityIssueType,
)
from apps.quality.services import (
    assign_quality_issue,
    close_quality_issue,
    create_quality_issue,
    get_organization_quality_issue,
    get_organization_quality_issues,
    review_quality_issue,
    start_quality_corrective_action,
    submit_quality_issue_for_verification,
    verify_quality_issue,
)
from core.list_filters import (
    apply_table_filters,
    build_table_filters,
    has_active_table_filters,
    paginate_table,
    table_pagination_query,
)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.QUALITY_ISSUES_VIEW)
@require_GET
def issue_list(request: HttpRequest) -> HttpResponse:
    issues = get_organization_quality_issues(
        user=request.user, organization=request.organization
    )
    issues = apply_table_filters(
        issues,
        request,
        text_fields={
            "number": ("issue_number",),
            "project": ("project__name", "site__name"),
        },
        choice_fields={
            "issue_type": ("issue_type", QualityIssueType.values),
            "severity": ("severity", QualityIssueSeverity.values),
            "status": ("status", QualityIssueStatus.values),
        },
        date_fields={"identified_at": "identified_at__date"},
    )
    page = paginate_table(
        issues,
        request,
        sort_fields={
            "number": "issue_number",
            "project": "project__name",
            "issue_type": "issue_type",
            "severity": "severity",
            "status": "status",
            "identified_at": "identified_at",
        },
        default_ordering=("-identified_at", "-created_at", "pk"),
    )
    return render(
        request,
        "quality/list.html",
        {
            "issues": page.object_list,
            "page_obj": page,
            "pagination_query": table_pagination_query(request),
            "filters": build_table_filters(
                request,
                [
                    {"name": "number", "kind": "text", "label": "شماره"},
                    {"name": "project", "kind": "text", "label": "پروژه"},
                    {
                        "name": "issue_type",
                        "kind": "select",
                        "label": "نوع",
                        "choices": QualityIssueType.choices,
                    },
                    {
                        "name": "severity",
                        "kind": "select",
                        "label": "شدت",
                        "choices": QualityIssueSeverity.choices,
                    },
                    {
                        "name": "status",
                        "kind": "select",
                        "label": "وضعیت",
                        "choices": QualityIssueStatus.choices,
                    },
                    {
                        "name": "identified_at",
                        "kind": "date_range",
                        "label": "زمان شناسایی",
                    },
                ],
            ),
            "has_active_filters": has_active_table_filters(request),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.QUALITY_ISSUES_CREATE)
def issue_create(request: HttpRequest) -> HttpResponse:
    form = QualityIssueForm(request.POST or None, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        try:
            issue = create_quality_issue(
                organization=request.organization,
                actor=request.user,
                **form.cleaned_data,
            )
        except (PermissionDenied, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("quality:detail", issue_id=issue.pk)
    return render(request, "quality/create.html", {"form": form})


@active_organization_required
@organization_permission_required(BusinessPermissionCode.QUALITY_ISSUES_VIEW)
@require_GET
def issue_detail(request: HttpRequest, issue_id: str) -> HttpResponse:
    issue = get_organization_quality_issue(
        user=request.user,
        organization=request.organization,
        issue_id=issue_id,
    )
    return render(
        request,
        "quality/detail.html",
        {
            "issue": issue,
            "assignment_form": QualityIssueAssignmentForm(
                organization=request.organization
            ),
            "corrective_form": CorrectiveActionForm(),
            "submission_form": VerificationSubmissionForm(),
            "verification_form": VerificationForm(),
            "closure_form": ClosureForm(),
        },
    )


def _transition_response(
    *,
    request: HttpRequest,
    issue_id: str,
    operation: Callable[..., object],
    form: forms.Form | None = None,
) -> HttpResponse:
    if form is not None and not form.is_valid():
        messages.error(request, "اطلاعات عملیات را بررسی کنید.")
        return redirect("quality:detail", issue_id=issue_id)
    try:
        kwargs = form.cleaned_data if form is not None else {}
        operation(
            organization=request.organization,
            actor=request.user,
            issue_id=issue_id,
            **kwargs,
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "وضعیت مسئله کیفیت به‌روزرسانی شد.")
    return redirect("quality:detail", issue_id=issue_id)


@active_organization_required
@organization_permission_required(BusinessPermissionCode.QUALITY_ISSUES_REVIEW)
@require_POST
def issue_review(request: HttpRequest, issue_id: str) -> HttpResponse:
    return _transition_response(
        request=request, issue_id=issue_id, operation=review_quality_issue
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.QUALITY_ISSUES_REVIEW)
@require_POST
def issue_assign(request: HttpRequest, issue_id: str) -> HttpResponse:
    return _transition_response(
        request=request,
        issue_id=issue_id,
        operation=assign_quality_issue,
        form=QualityIssueAssignmentForm(
            request.POST, organization=request.organization
        ),
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.QUALITY_ISSUES_MANAGE)
@require_POST
def corrective_action_start(request: HttpRequest, issue_id: str) -> HttpResponse:
    return _transition_response(
        request=request,
        issue_id=issue_id,
        operation=start_quality_corrective_action,
        form=CorrectiveActionForm(request.POST),
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.QUALITY_ISSUES_MANAGE)
@require_POST
def issue_submit_for_verification(request: HttpRequest, issue_id: str) -> HttpResponse:
    return _transition_response(
        request=request,
        issue_id=issue_id,
        operation=submit_quality_issue_for_verification,
        form=VerificationSubmissionForm(request.POST),
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.QUALITY_ISSUES_VERIFY)
@require_POST
def issue_verify(request: HttpRequest, issue_id: str) -> HttpResponse:
    return _transition_response(
        request=request,
        issue_id=issue_id,
        operation=verify_quality_issue,
        form=VerificationForm(request.POST),
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.QUALITY_ISSUES_CLOSE)
@require_POST
def issue_close(request: HttpRequest, issue_id: str) -> HttpResponse:
    return _transition_response(
        request=request,
        issue_id=issue_id,
        operation=close_quality_issue,
        form=ClosureForm(request.POST),
    )
