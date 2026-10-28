"""Product exposure only: never grants permission, scope, or domain authority.

MVP is the default. FULL_ERP is an explicit deployment/test setting for internal
regression verification, never a request, session, role, or customer switch.
Unclassified capabilities/namespaces fail closed, including in FULL_ERP.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import Resolver404, resolve


@dataclass(frozen=True)
class Capability:
    key: str
    mvp: bool
    namespaces: tuple[str, ...] = ()
    routes: tuple[str, ...] = ()


CAPABILITIES = (
    Capability("entry", True, ("accounts",), ("home", "global_search")),
    Capability("projects", True, ("projects",)),
    Capability("daily_reports", True, ("daily_reports",)),
    Capability("timekeeping", True, ("timekeeping",)),
    Capability("equipment", True, ("equipment",)),
    Capability("expenses", True, ("expenses",)),
    Capability("safety", True, ("safety",)),
    Capability("quality", True, ("quality",)),
    Capability("contracts", True, ("contracts", "billing", "estimates")),
    Capability("procurement", True, ("procurement", "materials", "inventory")),
    Capability("shared", True, ("parties", "documents", "workflows", "audit")),
    Capability("organization", True, ("organizations",)),
    Capability(
        "field_workforce",
        True,
        routes=tuple(
            f"workforce:{name}"
            for name in (
                "employee_list",
                "employee_create",
                "employee_detail",
                "employee_profile_image",
                "employee_profile_image_update",
                "employee_status_change",
                "employee_archive",
                "work_team_list",
                "work_team_create",
                "work_team_archive",
                "assignment_list",
                "assignment_create",
                "assignment_sites",
                "assignment_status_change",
            )
        ),
    ),
    Capability("operational_reports", True, routes=("reporting:dashboard",)),
    Capability("full_hr", False, ("workforce",)),
    Capability(
        "internal_reporting",
        False,
        ("reporting",),
        (
            "projects:cost_reconciliation",
            "projects:cost_reconciliation_export",
        ),
    ),
    Capability(
        "technical_administration",
        False,
        ("admin",),
        tuple(
            f"organizations:{name}"
            for name in (
                "create",
                "platform_role_catalog",
                "protected_operation_catalog",
                "platform_policy_catalog",
                "reference_personas",
                "tenant_policy_configuration",
                "configuration_profiles",
            )
        )
        + tuple(
            f"expenses:platform_group_{name}"
            for name in (
                "list",
                "create",
                "detail",
                "archive",
            )
        ),
    ),
    Capability(
        "finance",
        False,
        (
            "accounting",
            "treasury",
            "subledgers",
            "financials",
            "fixed_assets",
        ),
    ),
    Capability("payroll", False, ("payroll",)),
    Capability("commercial", False, ("commercial",)),
    Capability("compliance", False, ("compliance", "partner_qualification")),
    Capability("support", False, ("support", "knowledge")),
)

_BY_KEY = {capability.key: capability for capability in CAPABILITIES}
_BY_NAMESPACE = {
    namespace: capability.key
    for capability in CAPABILITIES
    for namespace in capability.namespaces
}
_BY_ROUTE = {
    route: capability.key for capability in CAPABILITIES for route in capability.routes
}


def surface_profile() -> str:
    profile = settings.PRODUCT_SURFACE_PROFILE
    if profile not in {"MVP", "FULL_ERP"}:
        raise ImproperlyConfigured("Unknown product surface profile.")
    return profile


def capability_exposed(key: str) -> bool:
    profile = surface_profile()
    capability = _BY_KEY.get(key)
    return capability is not None and (capability.mvp or profile == "FULL_ERP")


def route_capability(view_name: str, route_kwargs: dict | None = None) -> str:
    # Existing My Requests owns these narrow source-status links. They retain
    # explicit Person/WorkRelationship and source-ownership authorization; the
    # generic ESS route must not expose payroll or personal-data sources.
    if view_name == "workforce:ess_request_status" and (route_kwargs or {}).get(
        "source_type"
    ) in {"leave", "overtime", "correction"}:
        return "timekeeping"
    return _BY_ROUTE.get(view_name) or _BY_NAMESPACE.get(
        view_name.partition(":")[0], ""
    )


def route_exposed(view_name: str, route_kwargs: dict | None = None) -> bool:
    return capability_exposed(route_capability(view_name, route_kwargs))


def url_exposed(url: str) -> bool:
    """Filter local dynamic source links, including query strings/fragments."""
    parts = urlsplit(str(url))
    if parts.scheme or parts.netloc or not parts.path.startswith("/"):
        return False
    try:
        match = resolve(parts.path)
        return route_exposed(match.view_name, match.kwargs)
    except Resolver404:
        return False


def workflow_subject_exposed(subject_type: str, detail_route: str = "") -> bool:
    return route_exposed(detail_route or f"{subject_type.partition('.')[0]}:subject")


def personal_source_exposed(source_type: str) -> bool:
    routes = {
        "leave": "timekeeping:record_detail",
        "overtime": "timekeeping:record_detail",
        "correction": "timekeeping:record_detail",
        "payroll_inquiry": "payroll:ess_inquiry_detail",
        "personal_data": "workforce:personal_change_detail",
        "certificate": "workforce:certificate_detail",
    }
    return route_exposed(routes.get(source_type, ""))


# The current mixed reporting dashboard has two operational source families.
# Financial projections, manifests, reconciliation, refresh/export workspaces
# retain their existing internal contracts without becoming MVP entry points.
OPERATIONAL_METRICS = frozenset({"procurement_cycle_time", "inventory_quantity_value"})


def metric_exposed(code: str) -> bool:
    return surface_profile() == "FULL_ERP" or code in OPERATIONAL_METRICS


@dataclass(frozen=True)
class NavigationLink:
    label: str
    route: str
    permission: str = ""
    availability: str = ""


@dataclass(frozen=True)
class NavigationGroup:
    key: str
    label: str
    links: tuple[NavigationLink, ...]


# One destination catalogue shared by desktop, mobile, and Home. Permissions
# remain existing business codes; availability is evidence from existing guards.
NAVIGATION_GROUPS = (
    NavigationGroup(
        "operations",
        "عملیات پروژه و کارگاه",
        (
            NavigationLink("پروژه‌ها", "projects:list", "projects.view"),
            NavigationLink("کارگاه‌ها", "projects:all_site_list", "project_sites.view"),
            NavigationLink(
                "گزارش‌های روزانه", "daily_reports:list", "daily_reports.view"
            ),
            NavigationLink(
                "نیروی کار پروژه", "workforce:employee_list", "employees.view"
            ),
            NavigationLink(
                "تخصیص نیروی پروژه",
                "workforce:assignment_list",
                "project_assignments.view",
            ),
            NavigationLink("حضور و زمان", "timekeeping:workbench", "attendance.view"),
            NavigationLink(
                "تجهیزات عملیاتی",
                "equipment:operations_workbench",
                "equipment_operations.view",
            ),
            NavigationLink("فهرست تجهیزات", "equipment:list", "equipment.view"),
            NavigationLink("هزینه‌ها و تنخواه", "expenses:list", "expenses.view"),
            NavigationLink("ایمنی", "safety:list", "safety_incidents.view"),
            NavigationLink("کیفیت", "quality:list", "quality_issues.view"),
        ),
    ),
    NavigationGroup(
        "claims",
        "پیمان، متره و صورت‌وضعیت",
        (
            NavigationLink("برآورد و فهرست‌بها", "estimates:list", "estimates.view"),
            NavigationLink("قراردادها", "contracts:list", "contracts.view"),
            NavigationLink("صورت‌وضعیت و صورتحساب", "billing:claim_list", "claims.view"),
        ),
    ),
    NavigationGroup(
        "materials",
        "تدارکات، مصالح و انبار",
        (
            NavigationLink(
                "درخواست‌های خرید", "procurement:request_list", "purchase_requests.view"
            ),
            NavigationLink(
                "استعلام و انتخاب تأمین‌کننده", "procurement:rfq_list", "rfqs.view"
            ),
            NavigationLink(
                "سفارش‌های خرید", "procurement:order_list", "purchase_orders.view"
            ),
            NavigationLink(
                "رسید کالا", "procurement:receipt_list", "goods_receipts.view"
            ),
            NavigationLink("مصالح و کالا", "materials:material_list", "materials.view"),
            NavigationLink("انبار", "inventory:warehouse_list", "warehouses.view"),
        ),
    ),
    NavigationGroup(
        "shared",
        "کارتابل، اسناد و گزارش‌ها",
        (
            NavigationLink("وظایف من", "workflows:workbench", "work_items.view"),
            NavigationLink(
                "درخواست‌های من",
                "workflows:my_requests",
                availability="my_requests_workspace_available",
            ),
            NavigationLink(
                "فضای مدیر",
                "workflows:manager_workspace",
                availability="manager_workspace_available",
            ),
            NavigationLink("طرف‌های تجاری", "parties:list", "parties.view"),
            NavigationLink("اسناد", "documents:list", "documents.view"),
            NavigationLink("گردش‌کارها", "workflows:definition_list", "workflows.view"),
            NavigationLink(
                "گزارش‌های عملیاتی",
                "reporting:dashboard",
                "reporting.metric_result.view",
            ),
        ),
    ),
    NavigationGroup(
        "foundation",
        "تنظیمات و مدیریت دسترسی",
        (
            NavigationLink("پروفایل کاربر", "accounts:settings"),
            NavigationLink("انتخاب شرکت", "organizations:select"),
            NavigationLink(
                "تنظیمات شرکت", "organizations:settings", "company.settings.view"
            ),
            NavigationLink(
                "اعضا و دسترسی‌ها", "organizations:members", "membership.view"
            ),
            NavigationLink(
                "نقش‌های شرکت", "organizations:role_catalog", "authorization_roles.view"
            ),
            NavigationLink("سوابق فعالیت", "audit:log", "audit.view"),
        ),
    ),
)


def navigation_groups(
    codes: set[str] | frozenset[str],
    availability: dict[str, bool] | None = None,
) -> tuple[NavigationGroup, ...]:
    availability = availability or {}
    groups = []
    for group in NAVIGATION_GROUPS:
        links = tuple(
            link
            for link in group.links
            if (
                (not link.permission or link.permission in codes)
                and (
                    not link.availability or availability.get(link.availability, False)
                )
                and route_exposed(link.route)
                and not (
                    link.route == "equipment:list"
                    and "equipment_operations.view" in codes
                )
            )
        )
        if links:
            groups.append(NavigationGroup(group.key, group.label, links))
    return tuple(groups)
