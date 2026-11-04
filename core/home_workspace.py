"""Read-only Home presentation, composed exclusively from authorized selectors.

This projection owns no lifecycle, priority, financial or authorization rules.
Counts cover the active organization's visible records, across permitted projects.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.urls import reverse

from apps.accounts.models import User
from apps.contracts.models import ContractStatus
from apps.contracts.services import get_organization_contracts
from apps.daily_reports.services import get_organization_daily_reports
from apps.estimates.services import get_organization_estimates
from apps.organizations.models import Organization
from apps.procurement.models import PurchaseRequestStatus
from apps.procurement.services import get_organization_purchase_requests
from apps.projects.models import ProjectStatus
from apps.projects.services import get_organization_projects
from apps.workflows.registry import registry
from apps.workflows.workbench import build_workbench, decorate_work_items
from core.home import HomeLink
from core.product_surface import route_exposed, workflow_subject_exposed


@dataclass(frozen=True)
class WorkspaceMetric:
    label: str
    value: int
    route: str
    icon: str
    tone: str
    note: str = ""


@dataclass(frozen=True)
class RecentRecord:
    title: str
    family: str
    url: str
    at: datetime
    icon: str


QUICK_ROUTES = (
    ("workflows:my_requests", "notes", "blue"),
    ("workflows:manager_workspace", "briefcase", "green"),
    ("projects:list", "layers", "blue"),
    ("contracts:list", "notes", "violet"),
    ("estimates:list", "file-spreadsheet", "green"),
    ("billing:claim_list", "layers", "blue"),
    ("procurement:request_list", "briefcase", "violet"),
    ("daily_reports:list", "calendar", "green"),
    ("timekeeping:workbench", "clock", "blue"),
    ("documents:list", "notes", "amber"),
)


def build_home_workspace(
    *,
    user: User,
    organization: Organization,
    links: tuple[HomeLink, ...],
    assigned_work: HomeLink | None,
) -> dict[str, Any]:
    """Bounded display data; source services recheck tenant and object scope."""
    allowed = {link.route: link for link in links}
    kpis = []
    recent = []
    summaries = {"operations": [], "commercial": [], "procurement": []}
    status_rows = None
    project_total = 0

    def records(queryset, *, title, family, detail, icon):
        if not route_exposed(detail):
            return
        for record in queryset.order_by("-updated_at", "-pk")[:6]:
            recent.append(
                RecentRecord(
                    title=title(record),
                    family=family,
                    url=reverse(detail, args=[record.pk]),
                    at=record.updated_at,
                    icon=icon,
                )
            )

    sources = (
        (
            "projects:list",
            get_organization_projects,
            "operations",
            "پروژه‌ها",
            "layers",
            "blue",
        ),
        (
            "contracts:list",
            get_organization_contracts,
            "commercial",
            "قراردادها",
            "notes",
            "violet",
        ),
        (
            "daily_reports:list",
            get_organization_daily_reports,
            "operations",
            "گزارش‌های روزانه",
            "calendar",
            "violet",
        ),
        (
            "estimates:list",
            get_organization_estimates,
            "commercial",
            "برآوردها",
            "file-spreadsheet",
            "green",
        ),
        (
            "procurement:request_list",
            get_organization_purchase_requests,
            "procurement",
            "درخواست‌های خرید",
            "briefcase",
            "green",
        ),
    )
    for route, selector, group, label, icon, tone in sources:
        if route not in allowed or not route_exposed(route):
            continue
        try:
            queryset = selector(user=user, organization=organization)
        except PermissionDenied:
            # A navigation permission cannot replace the source's stricter guard.
            allowed.pop(route, None)
            continue
        total = queryset.count()
        summaries[group].append(WorkspaceMetric(label, total, route, icon, tone))
        if route == "projects:list":
            counts = dict(
                queryset.order_by()
                .values("status")
                .annotate(total=Count("pk"))
                .values_list("status", "total")
            )
            project_total = total
            status_rows = (
                tuple(
                    {
                        "status": status,
                        "label": str(status.label),
                        "value": counts.get(status, 0),
                    }
                    for status in ProjectStatus
                )
                if total
                else ()
            )
            kpis.append(
                WorkspaceMetric(
                    "پروژه‌های فعال",
                    counts.get(ProjectStatus.ACTIVE, 0),
                    route,
                    icon,
                    tone,
                    "از پروژه‌های قابل مشاهده شما",
                )
            )
            records(
                queryset,
                title=lambda item: item.name,
                family="پروژه",
                detail="projects:detail",
                icon=icon,
            )
        elif route == "contracts:list":
            kpis.append(
                WorkspaceMetric(
                    "قراردادهای فعال",
                    queryset.filter(status=ContractStatus.ACTIVE).count(),
                    route,
                    icon,
                    tone,
                    "قراردادهای با وضعیت فعال",
                )
            )
            records(
                queryset,
                title=lambda item: item.title,
                family="قرارداد",
                detail="contracts:detail",
                icon=icon,
            )
        elif route == "daily_reports:list":
            kpis.append(
                WorkspaceMetric(
                    label, total, route, icon, tone, "همه گزارش‌های قابل مشاهده"
                )
            )
            records(
                queryset,
                title=lambda item: str(item.project.name),
                family="گزارش روزانه",
                detail="daily_reports:detail",
                icon=icon,
            )
        elif route == "estimates:list":
            records(
                queryset,
                title=lambda item: item.title,
                family="برآورد",
                detail="estimates:detail",
                icon=icon,
            )
        else:
            kpis.append(
                WorkspaceMetric(
                    "درخواست‌های خرید ارسال‌شده",
                    queryset.filter(status=PurchaseRequestStatus.SUBMITTED).count(),
                    route,
                    icon,
                    tone,
                    "با وضعیت ارسال‌شده",
                )
            )
            records(
                queryset,
                title=lambda item: item.title,
                family="درخواست خرید",
                detail="procurement:request_detail",
                icon=icon,
            )

    tasks = None
    task_total = None
    if assigned_work and route_exposed(assigned_work.route):
        try:
            workbench = build_workbench(
                actor=user,
                organization=organization,
                params={},
                exposed_subject_types=frozenset(
                    adapter.subject_type
                    for adapter in registry.subject_adapters.values()
                    if workflow_subject_exposed(
                        adapter.subject_type, adapter.detail_url_name
                    )
                ),
            )
        except PermissionDenied:
            pass
        else:
            task_total = workbench.counts.all_items
            tasks = list(workbench.queryset[:4])
            decorate_work_items(
                tasks,
                membership=workbench.membership,
                permission_codes=workbench.permission_codes,
            )
            kpis.append(
                WorkspaceMetric(
                    "کارهای در انتظار اقدام من",
                    task_total,
                    assigned_work.route,
                    "check-circle",
                    "amber",
                    "کارهای باز و قبول‌شده کارتابل",
                )
            )

    group_labels = {
        "operations": "عملیات پروژه و کارگاه",
        "commercial": "پیمان و برآورد",
        "procurement": "تدارکات و خرید",
    }
    return {
        "kpis": tuple(kpis),
        "quick_links": tuple(
            {"link": allowed[route], "icon": icon, "tone": tone}
            for route, icon, tone in QUICK_ROUTES
            if route in allowed and route_exposed(route)
        )[:6],
        "tasks": tasks,
        "task_total": task_total,
        "recent": tuple(sorted(recent, key=lambda item: item.at, reverse=True)[:6]),
        "status_rows": status_rows,
        "project_total": project_total,
        "charts": [
            {
                "id": "home-project-status",
                "type": "doughnut",
                "unit": "پروژه",
                "rows": status_rows,
            }
        ]
        if status_rows
        else [],
        "summaries": tuple(
            {"key": key, "label": group_labels[key], "rows": rows}
            for key, rows in summaries.items()
            if rows
        ),
    }
