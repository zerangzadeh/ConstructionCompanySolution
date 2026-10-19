from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.financials.services import (
    get_organization_dashboard,
    get_organization_financial_reports,
)
from apps.organizations.decorators import (
    active_organization_required,
    organization_permission_required,
)
from apps.organizations.models import BusinessPermissionCode
from core.financial_navigation import authorized_financial_authorities


def _sort_financial_reports(request: HttpRequest, reports):
    sort_keys = {
        "project": lambda report: report.project.name.casefold(),
        "approved_estimate_total": lambda report: report.approved_estimate_total,
        "recorded_expense_total": lambda report: report.recorded_expense_total,
        "variance": lambda report: report.variance,
        "receipt_total": lambda report: report.receipt_total,
        "disbursement_total": lambda report: report.disbursement_total,
        "net_cash_flow": lambda report: report.net_cash_flow,
    }
    key = sort_keys.get(request.GET.get("sort", "").strip())
    if key is None:
        return reports
    return sorted(
        reports,
        key=key,
        reverse=request.GET.get("direction", "asc").strip().lower() == "desc",
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FINANCIALS_VIEW)
def financial_report(request: HttpRequest) -> HttpResponse:
    reports = get_organization_financial_reports(
        user=request.user,
        organization=request.organization,
    )
    reports = _sort_financial_reports(request, reports)
    return render(
        request,
        "financials/report.html",
        {
            "reports": reports,
            "financial_authorities": authorized_financial_authorities(
                user=request.user, organization=request.organization
            ),
            "workspace_observed_at": timezone.now(),
        },
    )


@active_organization_required
@organization_permission_required(BusinessPermissionCode.FINANCIALS_VIEW)
def dashboard(request: HttpRequest) -> HttpResponse:
    summary = get_organization_dashboard(
        user=request.user,
        organization=request.organization,
    )
    return render(
        request,
        "financials/dashboard.html",
        {
            "summary": summary,
            "financial_authorities": authorized_financial_authorities(
                user=request.user, organization=request.organization
            ),
            "workspace_observed_at": timezone.now(),
        },
    )
