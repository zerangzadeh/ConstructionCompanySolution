from __future__ import annotations

import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.documents.models import DocumentVersion
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.decorators import active_organization_required
from apps.organizations.models import BusinessPermissionCode
from apps.projects.models import Project
from apps.reporting.models import (
    MetricDefinition,
    ProjectCloseoutCase,
    ProjectCloseoutItemSnapshot,
    ReconciliationException,
    ReconciliationPairDefinition,
)
from apps.reporting.project_closeout import (
    closeout_case_detail,
    closeout_cases,
    coordinate_closeout_case,
    create_closeout_case,
    decide_closeout_case,
    export_closeout_csv,
    link_closeout_evidence,
    reopen_closeout_case,
    run_closeout_assessment,
)
from apps.reporting.reconciliation import (
    execute_reconciliation,
    reconciliation_drillthrough,
    reconciliation_runs,
    record_exception_event,
    replay_reconciliation,
)
from apps.reporting.services import (
    dashboard_results,
    drillthrough_manifest,
    export_dashboard_csv,
    refresh_metric,
)


def _private(response: HttpResponse) -> HttpResponse:
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Vary"] = "Cookie"
    return response


@require_GET
@active_organization_required
def dashboard(request: HttpRequest) -> HttpResponse:
    results = dashboard_results(organization=request.organization, actor=request.user)
    definitions = MetricDefinition.objects.filter(is_active=True).order_by("code")
    return _private(
        render(
            request,
            "reporting/dashboard.html",
            {"results": results, "definitions": definitions},
        )
    )


@require_POST
@active_organization_required
def refresh(request: HttpRequest, metric_code: str) -> HttpResponse:
    project = None
    if request.POST.get("project_id"):
        project = Project.objects.filter(
            organization=request.organization,
            pk=request.POST["project_id"],
            deleted_at__isnull=True,
        ).first()
        if project is None:
            raise PermissionDenied("پروژه در دامنه شرکت فعال یافت نشد.")
    refresh_metric(
        organization=request.organization,
        actor=request.user,
        metric_code=metric_code,
        idempotency_key=request.POST.get("idempotency_key") or str(uuid.uuid4()),
        project=project,
    )
    messages.success(request, "شاخص با موفقیت و بدون تغییر منبع بازسازی شد.")
    return redirect("reporting:dashboard")


@require_GET
@active_organization_required
def drillthrough(request: HttpRequest, result_id: str) -> HttpResponse:
    result = drillthrough_manifest(
        organization=request.organization,
        actor=request.user,
        result_id=result_id,
    )
    return _private(render(request, "reporting/drillthrough.html", {"result": result}))


@require_POST
@active_organization_required
def export_csv(request: HttpRequest) -> HttpResponse:
    manifest, content = export_dashboard_csv(
        organization=request.organization,
        actor=request.user,
        idempotency_key=request.POST.get("idempotency_key") or str(uuid.uuid4()),
        purpose=request.POST.get("purpose", "گزارش مدیریتی"),
    )
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="metrics-{manifest.pk}.csv"'
    )
    return _private(response)


@require_GET
@active_organization_required
def reconciliation_workbench(request: HttpRequest) -> HttpResponse:
    runs = reconciliation_runs(organization=request.organization, actor=request.user)
    # SPEC012 requires explicit workforce context unavailable in this generic form.
    pairs = (
        ReconciliationPairDefinition.objects.filter(is_active=True)
        .exclude(code="attendance_timesheet")
        .order_by("code")
    )
    return _private(
        render(
            request,
            "reporting/reconciliation_workbench.html",
            {"runs": runs, "pairs": pairs},
        )
    )


@require_POST
@active_organization_required
def reconciliation_execute(request: HttpRequest, pair_code: str) -> HttpResponse:
    project = None
    if request.POST.get("project_id"):
        project = Project.objects.filter(
            organization=request.organization,
            pk=request.POST["project_id"],
            deleted_at__isnull=True,
        ).first()
        if project is None:
            raise PermissionDenied("پروژه در دامنه شرکت فعال یافت نشد.")
    execute_reconciliation(
        organization=request.organization,
        actor=request.user,
        pair_code=pair_code,
        idempotency_key=request.POST.get("idempotency_key") or str(uuid.uuid4()),
        project=project,
    )
    messages.success(request, "تطبیق بدون تغییر هیچ منبعی اجرا شد.")
    return redirect("reporting:reconciliation_workbench")


@require_GET
@active_organization_required
def reconciliation_detail(request: HttpRequest, run_id: str) -> HttpResponse:
    run = reconciliation_drillthrough(
        organization=request.organization, actor=request.user, run_id=run_id
    )
    return _private(
        render(request, "reporting/reconciliation_detail.html", {"run": run})
    )


@require_POST
@active_organization_required
def reconciliation_exception_action(
    request: HttpRequest, exception_id: str, action: str
) -> HttpResponse:
    exception = (
        ReconciliationException.objects.filter(
            organization=request.organization, pk=exception_id
        )
        .select_related("run__project")
        .first()
    )
    if exception is None:
        raise PermissionDenied("مغایرت در شرکت فعال یافت نشد.")
    record_exception_event(
        exception=exception,
        actor=request.user,
        action=action,
        reason=request.POST.get("reason", ""),
        operation_key=request.POST.get("operation_key") or str(uuid.uuid4()),
        correction_reference={
            "reference": request.POST.get("correction_reference", "")
        },
    )
    messages.success(request, "رویداد تغییرناپذیر مغایرت ثبت شد.")
    return redirect("reporting:reconciliation_detail", run_id=exception.run_id)


@require_POST
@active_organization_required
def reconciliation_replay(request: HttpRequest, run_id: str) -> HttpResponse:
    run = reconciliation_drillthrough(
        organization=request.organization, actor=request.user, run_id=run_id
    )
    replay_reconciliation(
        original_run=run,
        actor=request.user,
        idempotency_key=request.POST.get("idempotency_key") or str(uuid.uuid4()),
    )
    messages.success(request, "شاهد بازپخش ثبت شد و نتیجه تاریخی تغییر نکرد.")
    return redirect("reporting:reconciliation_detail", run_id=run.pk)


@require_GET
@active_organization_required
def project_closeout_workbench(request: HttpRequest) -> HttpResponse:
    cases = closeout_cases(organization=request.organization, actor=request.user)
    membership = require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=BusinessPermissionCode.PROJECTS_VIEW,
        message="اجازه مشاهده پروژه‌ها را ندارید.",
        allow_any_scope=True,
    )
    projects = scope_queryset(
        Project.objects.filter(
            organization=request.organization, deleted_at__isnull=True
        ),
        membership=membership,
        project_lookup="pk",
        include_site_parent=True,
    ).order_by("name")
    return _private(
        render(
            request,
            "reporting/project_closeout_workbench.html",
            {"cases": cases, "projects": projects},
        )
    )


@require_POST
@active_organization_required
def project_closeout_create(request: HttpRequest) -> HttpResponse:
    project = Project.objects.filter(
        organization=request.organization,
        pk=request.POST.get("project_id"),
        deleted_at__isnull=True,
    ).first()
    if project is None:
        raise PermissionDenied("پروژه در شرکت فعال یافت نشد.")
    case = create_closeout_case(
        organization=request.organization,
        actor=request.user,
        project=project,
        operation_key=request.POST.get("operation_key") or str(uuid.uuid4()),
    )
    messages.success(request, "پرونده هماهنگی اختتام بدون تغییر منبع ایجاد شد.")
    return redirect("reporting:project_closeout_detail", case_id=case.pk)


@require_GET
@active_organization_required
def project_closeout_detail(request: HttpRequest, case_id: str) -> HttpResponse:
    case = closeout_case_detail(
        organization=request.organization, actor=request.user, case_id=case_id
    )
    return _private(
        render(request, "reporting/project_closeout_detail.html", {"case": case})
    )


def _closeout_case_from_request(
    request: HttpRequest, case_id: str
) -> ProjectCloseoutCase:
    case = ProjectCloseoutCase.objects.filter(
        organization=request.organization, pk=case_id
    ).first()
    if case is None:
        raise PermissionDenied("پرونده در شرکت فعال یافت نشد.")
    return case


@require_POST
@active_organization_required
def project_closeout_assess(request: HttpRequest, case_id: str) -> HttpResponse:
    case = _closeout_case_from_request(request, case_id)
    run_closeout_assessment(
        case=case,
        actor=request.user,
        idempotency_key=request.POST.get("idempotency_key") or str(uuid.uuid4()),
        expected_revision=int(request.POST["revision"]),
    )
    messages.success(request, "ارزیابی همگام ثبت شد؛ هیچ منبعی تغییر نکرد.")
    return redirect("reporting:project_closeout_detail", case_id=case.pk)


@require_POST
@active_organization_required
def project_closeout_coordinate(request: HttpRequest, case_id: str) -> HttpResponse:
    case = _closeout_case_from_request(request, case_id)
    coordinate_closeout_case(
        case=case,
        actor=request.user,
        reason=request.POST.get("reason", ""),
        operation_key=request.POST.get("operation_key") or str(uuid.uuid4()),
        details={"material": request.POST.get("material") == "1"},
    )
    messages.success(request, "یادداشت هماهنگی تغییرناپذیر ثبت شد.")
    return redirect("reporting:project_closeout_detail", case_id=case.pk)


@require_POST
@active_organization_required
def project_closeout_decide(
    request: HttpRequest, case_id: str, decision: str
) -> HttpResponse:
    case = _closeout_case_from_request(request, case_id)
    decide_closeout_case(
        case=case,
        actor=request.user,
        decision=decision,
        reason=request.POST.get("reason", ""),
        operation_key=request.POST.get("operation_key") or str(uuid.uuid4()),
        expected_revision=int(request.POST["revision"]),
    )
    messages.success(request, "تصمیم اختتام به‌صورت تغییرناپذیر ثبت شد.")
    return redirect("reporting:project_closeout_detail", case_id=case.pk)


@require_POST
@active_organization_required
def project_closeout_reopen(request: HttpRequest, case_id: str) -> HttpResponse:
    case = _closeout_case_from_request(request, case_id)
    reopen_closeout_case(
        case=case,
        actor=request.user,
        reason=request.POST.get("reason", ""),
        operation_key=request.POST.get("operation_key") or str(uuid.uuid4()),
        expected_revision=int(request.POST["revision"]),
    )
    messages.success(request, "پرونده با حفظ پذیرش تاریخی بازگشایی شد.")
    return redirect("reporting:project_closeout_detail", case_id=case.pk)


@require_POST
@active_organization_required
def project_closeout_evidence(request: HttpRequest, case_id: str) -> HttpResponse:
    case = _closeout_case_from_request(request, case_id)
    document_version = DocumentVersion.objects.filter(
        organization=request.organization, pk=request.POST.get("document_version_id")
    ).first()
    if document_version is None:
        raise PermissionDenied("نسخه سند در شرکت فعال یافت نشد.")
    item = None
    if request.POST.get("item_id"):
        item = ProjectCloseoutItemSnapshot.objects.filter(
            organization=request.organization,
            pk=request.POST["item_id"],
            assessment__case=case,
        ).first()
        if item is None:
            raise PermissionDenied("قلم اختتام در شرکت فعال یافت نشد.")
    link_closeout_evidence(
        case=case,
        actor=request.user,
        document_version=document_version,
        evidence_role=request.POST.get("evidence_role", "closeout_support"),
        item=item,
    )
    messages.success(request, "پین دقیق نسخه سند ثبت شد؛ بایت سند در DMS باقی ماند.")
    return redirect("reporting:project_closeout_detail", case_id=case.pk)


@require_POST
@active_organization_required
def project_closeout_export(request: HttpRequest, case_id: str) -> HttpResponse:
    case = _closeout_case_from_request(request, case_id)
    manifest, content = export_closeout_csv(
        case=case,
        actor=request.user,
        idempotency_key=request.POST.get("idempotency_key") or str(uuid.uuid4()),
        purpose=request.POST.get("purpose", "خروجی کنترل اختتام پروژه"),
    )
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="project-closeout-{manifest.pk}.csv"'
    )
    return _private(response)
