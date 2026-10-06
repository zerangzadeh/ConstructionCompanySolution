from __future__ import annotations

import uuid

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.organizations.decorators import active_organization_required
from apps.projects.models import Project
from apps.reporting.models import MetricDefinition
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
    return _private(
        render(request, "reporting/drillthrough.html", {"result": result})
    )


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
    response["Content-Disposition"] = f'attachment; filename="metrics-{manifest.pk}.csv"'
    return _private(response)
