"""Read-only dashboard composition. Source services retain all business authority.

Project Cost remains the authority for recognized amounts. Budget comparison
here describes the visible evidence and does not write financial state.
"""

from decimal import Decimal

from django.db.models import Count
from django.http import HttpRequest
from django.urls import reverse

from apps.contracts.models import ContractStatus
from apps.contracts.services import get_organization_contracts
from apps.daily_reports.services import get_organization_daily_reports
from apps.expenses.services import get_organization_expenses
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.projects.business_hub import project_commercial_summary
from apps.projects.models import Project, ProjectCostFactKind
from apps.projects.services import (
    get_organization_project_sites,
    get_project_cost_projection,
)
from core.business_choices import contextual_url
from core.product_surface import route_exposed


def _budget_comparison(budget: Decimal, actual: Decimal | None) -> dict | None:
    if budget <= 0 or actual is None or actual < 0:
        return None
    scale = max(budget, actual)
    return {
        "remaining": budget - actual,
        "percent": (actual * 100 / budget).quantize(Decimal("0.1")),
        "budget_bar": (budget * 100 / scale).quantize(Decimal("0.01")),
        "actual_bar": (actual * 100 / scale).quantize(Decimal("0.01")),
        "over_budget": actual > budget,
    }


def project_dashboard(request: HttpRequest, project: Project) -> dict:
    """The caller resolves Project through the authenticated, scoped read service."""

    def access(permission, route, *, site_parent=False):
        return route_exposed(route) and has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=project,
            allow_site_parent=site_parent,
        )

    commercial = project_commercial_summary(request, project)
    recent = [
        {
            "kind": item.label,
            "title": item.recent_label,
            "date": item.recent_created_at,
            "status": item.recent_state_code,
            "status_label": item.recent_status,
            "url": item.recent_url,
        }
        for item in commercial
        if item.recent_url
    ]
    currency = request.organization.currency
    currency_label = "ریال" if currency == "IRR" else currency
    kpis = [
        {
            "label": "بودجه تخمینی پروژه",
            "value": project.estimated_budget,
            "unit": currency_label,
            "icon": "layers",
            "tone": "budget",
        }
    ]
    projection = None
    actual = None
    comparison = None
    cost_message = ""
    charts = []
    if access(P.PROJECT_COSTS_VIEW, "projects:detail"):
        projection = get_project_cost_projection(
            organization=request.organization, project=project, actor=request.user
        )
        # Existing projection may include legacy currencies. Never relabel or
        # combine them with the Organization's budget unit for a dashboard chart.
        currencies = {fact.currency for fact in projection.facts}
        has_actual_evidence = any(
            fact.kind
            in {
                ProjectCostFactKind.ACTUAL_RECOGNIZED,
                ProjectCostFactKind.ACTUAL_REVERSAL,
            }
            for fact in projection.facts
        )
        if not has_actual_evidence:
            cost_message = "هنوز هزینه‌ای در سوابق هزینه پروژه ثبت نشده است."
        elif currencies != {currency}:
            cost_message = "واحد پول شواهد هزینه با بودجه پروژه هم‌ارز نیست."
        else:
            actual = projection.actual_cost
            comparison = _budget_comparison(project.estimated_budget, actual)
            if project.estimated_budget <= 0:
                cost_message = "بودجه تخمینی مثبت ثبت نشده است."
            elif actual < 0:
                cost_message = (
                    "خالص هزینه پس از برگشت‌ها منفی است و درصد مصرف نمایش داده نمی‌شود."
                )
        kpis.append(
            {
                "label": "هزینه ثبت‌شده",
                "value": actual,
                "unit": currency_label if actual is not None else "",
                "note": "داده هم‌ارز در دسترس نیست" if actual is None else "",
                "url": "#costs",
                "icon": "coins",
                "tone": "cost",
            }
        )
    contracts = next((item for item in commercial if item.label == "قراردادها"), None)
    contract_rows = []
    if contracts is not None:
        kpis.append(
            {
                "label": "قراردادهای فعال",
                "value": contracts.state_count,
                "unit": "قرارداد",
                "url": contracts.list_url,
                "icon": "document",
                "tone": "contracts",
            }
        )
        counts = dict(
            get_organization_contracts(
                user=request.user, organization=request.organization
            )
            .filter(project=project)
            .order_by()
            .values("status")
            .annotate(total=Count("pk"))
            .values_list("status", "total")
        )
        contract_rows = [
            {"status": status, "label": label, "value": str(counts[status])}
            for status, label in ContractStatus.choices
            if counts.get(status)
        ]
        if contract_rows:
            charts.append(
                {
                    "id": "project-contracts-chart",
                    "type": "doughnut",
                    "rows": contract_rows,
                    "unit": "قرارداد",
                }
            )
    sites_url = ""
    if access(P.PROJECT_SITES_VIEW, "projects:site_list", site_parent=True):
        sites = get_organization_project_sites(
            user=request.user, organization=request.organization, project_id=project.pk
        )
        sites_url = reverse("projects:site_list", args=[project.pk])
        kpis.append(
            {
                "label": "کارگاه‌ها",
                "value": sites.count(),
                "unit": "کارگاه",
                "url": sites_url,
                "icon": "hard-hat",
                "tone": "sites",
            }
        )
    reports_count = None
    for permission, route, loader, kind in (
        (
            P.DAILY_REPORTS_VIEW,
            "daily_reports:detail",
            get_organization_daily_reports,
            "گزارش روزانه",
        ),
        (P.EXPENSES_VIEW, "expenses:detail", get_organization_expenses, "هزینه"),
    ):
        if not access(permission, route):
            continue
        records = loader(user=request.user, organization=request.organization).filter(
            project=project
        )
        if kind == "گزارش روزانه":
            reports_count = records.count()
            kpis.append(
                {
                    "label": "گزارش‌های روزانه",
                    "value": reports_count,
                    "unit": "گزارش",
                    "url": contextual_url(
                        "daily_reports:list", project_filter=project.pk
                    )
                    if route_exposed("daily_reports:list")
                    else "",
                    "icon": "calendar",
                    "tone": "reports",
                }
            )
            records = records.select_related("site")
        for record in records.order_by("-created_at", "pk")[:3]:
            recent.append(
                {
                    "kind": kind,
                    "title": (
                        f"گزارش {record.site.name}"
                        if kind == "گزارش روزانه"
                        else record.description
                    ),
                    "date": record.created_at,
                    "status": record.status,
                    "status_label": record.get_status_display(),
                    "url": reverse(route, args=[record.pk]),
                }
            )
    links = []
    for permission, route, label, icon in (
        (P.EMPLOYEES_VIEW, "workforce:field_list", "نیروهای کار", "users"),
        (P.ATTENDANCE_VIEW, "timekeeping:workbench", "حضور و کارکرد", "clock"),
    ):
        if access(permission, route, site_parent=True):
            links.append(
                {
                    "label": label,
                    "url": contextual_url(route, project=project.pk),
                    "icon": icon,
                }
            )
    can_controls = all(
        access(permission, "projects:controls")
        for permission in (P.PROJECT_CONTROLS_VIEW, P.WBS_NODES_VIEW, P.ACTIVITIES_VIEW)
    )
    return {
        "commercial_summary": commercial,
        "cost_projection": projection,
        "dashboard": {
            "kpis": kpis,
            "charts": charts,
            "currency_label": currency_label,
            "actual_cost": actual,
            "budget_comparison": comparison,
            "cost_message": cost_message,
            "contract_rows": contract_rows,
            "contract_total": contracts.total if contracts else 0,
            "has_contracts_access": contracts is not None,
            "recent": sorted(recent, key=lambda item: item["date"], reverse=True)[:6],
            "quick_links": links,
            "sites_url": sites_url,
            "controls_url": reverse("projects:controls", args=[project.pk])
            if can_controls
            else "",
            "gallery_url": reverse("projects:gallery", args=[project.pk])
            if access(P.DOCUMENTS_VIEW, "projects:gallery")
            else "",
            "can_archive": access(P.PROJECTS_ARCHIVE, "projects:archive"),
            "reports_count": reports_count,
        },
    }
