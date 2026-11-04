"""Read-only dashboard composition. Source services retain all business authority.

No progress rollup, cost recognition, currency conversion or financial remainder
is defined here. Decimal values remain exact strings through JSON serialization.
"""

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
from core.product_surface import route_exposed


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
    kpis = [
        {
            "label": "بودجه تخمینی پروژه",
            "value": project.estimated_budget,
            "unit": request.organization.currency,
            "note": "مبلغ ثبت‌شده در مشخصات پروژه",
            "icon": "layers",
            "tone": "budget",
        }
    ]
    projection = None
    comparable = False
    cost_rows = []
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
        comparable = has_actual_evidence and currencies == {
            request.organization.currency
        }
        cost_rows = [{"label": "بودجه تخمینی", "value": str(project.estimated_budget)}]
        if comparable:
            cost_rows.append(
                {"label": "هزینه ثبت‌شده", "value": str(projection.actual_cost)}
            )
        kpis.append(
            {
                "label": "هزینه ثبت‌شده",
                "value": projection.actual_cost if comparable else None,
                "unit": request.organization.currency if comparable else "",
                "note": "پوشش ناقص؛ کل هزینه پروژه نیست"
                if comparable
                else "شواهد هم‌ارز کافی ثبت نشده است",
                "icon": "coins",
                "tone": "cost",
            }
        )
        if comparable:
            charts.append(
                {
                    "id": "project-cost-chart",
                    "type": "bar",
                    "rows": cost_rows,
                    "unit": request.organization.currency,
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
                "note": "از قراردادهای قابل مشاهده پروژه",
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
            .values("status")
            .annotate(total=Count("pk"))
            .values_list("status", "total")
        )
        contract_rows = [
            {"label": label, "value": str(counts.get(status, 0))}
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
    links = []
    if access(P.PROJECT_SITES_VIEW, "projects:site_list", site_parent=True):
        sites = get_organization_project_sites(
            user=request.user, organization=request.organization, project_id=project.pk
        )
        url = reverse("projects:site_list", args=[project.pk])
        kpis.append(
            {
                "label": "کارگاه‌ها",
                "value": sites.count(),
                "unit": "کارگاه",
                "note": "در محدوده دسترسی شما",
                "url": url,
                "icon": "hard-hat",
                "tone": "sites",
            }
        )
        links.append({"label": "کارگاه‌ها", "url": url})
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
                    "note": "سوابق قابل مشاهده پروژه",
                    "icon": "calendar",
                    "tone": "reports",
                }
            )
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
    for permission, route, label in (
        (P.EMPLOYEES_VIEW, "workforce:field_list", "نیروهای کار"),
        (P.ATTENDANCE_VIEW, "timekeeping:workbench", "حضور و کارکرد"),
    ):
        if access(permission, route, site_parent=True):
            links.append(
                {"label": label, "url": f"{reverse(route)}?project={project.pk}"}
            )
    can_controls = access(P.PROJECT_CONTROLS_VIEW, "projects:controls")
    if can_controls:
        links.append(
            {
                "label": "ساختار شکست و فعالیت‌ها",
                "url": reverse("projects:controls", args=[project.pk]),
            }
        )
    if access(P.DOCUMENTS_VIEW, "projects:gallery"):
        links.append(
            {
                "label": "اسناد و گالری",
                "url": reverse("projects:gallery", args=[project.pk]),
            }
        )
    return {
        "commercial_summary": commercial,
        "cost_projection": projection,
        "dashboard": {
            "kpis": kpis,
            "charts": charts,
            "cost_rows": cost_rows,
            "cost_comparable": comparable,
            "contract_rows": contract_rows,
            "contract_total": contracts.total if contracts else 0,
            "has_contracts_access": contracts is not None,
            "recent": sorted(recent, key=lambda item: item["date"], reverse=True)[:6],
            "quick_links": links,
            "can_controls": can_controls,
            "can_archive": access(P.PROJECTS_ARCHIVE, "projects:archive"),
            "reports_count": reports_count,
        },
    }
