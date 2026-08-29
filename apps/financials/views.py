from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.financials.services import (
    get_organization_dashboard,
    get_organization_financial_reports,
)
from apps.organizations.decorators import active_organization_required


@active_organization_required
def financial_report(request: HttpRequest) -> HttpResponse:
    reports = get_organization_financial_reports(
        user=request.user,
        organization=request.organization,
    )
    return render(request, "financials/report.html", {"reports": reports})


@active_organization_required
def dashboard(request: HttpRequest) -> HttpResponse:
    summary = get_organization_dashboard(
        user=request.user,
        organization=request.organization,
    )
    return render(request, "financials/dashboard.html", {"summary": summary})
