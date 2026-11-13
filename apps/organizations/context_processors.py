from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.accounts.header_identity import membership_header_identity
from apps.accounts.platform_user_services import user_management_permissions
from apps.inventory.p8_services import inventory_transfer_receiving_available
from apps.organizations.authorization import (
    get_active_membership,
    membership_has_scope,
    membership_permission_codes,
    permission_supports_object_scope,
)
from apps.organizations.context import scoped_context_projects, scoped_context_sites
from apps.organizations.models import BusinessPermissionCode
from apps.organizations.reference_personas import reference_catalogue_enabled
from apps.parties.presentation import GOVERNANCE_PERMISSIONS
from apps.workflows.personal_workspaces import (
    manager_workspace_available,
    my_requests_available,
)
from apps.workforce.ess_services import has_ess_subject
from core.product_surface import (
    is_platform_workspace_route,
    navigation_groups,
    platform_administration_exposed,
    route_exposed,
    surface_profile,
)

PLATFORM_NAVIGATION = (
    ("داشبورد پلتفرم", "platform_dashboard", ("platform_dashboard",), "home"),
    (
        "شرکت‌ها",
        "platform_company_list",
        (
            "create",
            "platform_company_list",
            "platform_company_detail",
            "platform_company_edit",
        ),
        "company",
    ),
    (
        "کاربران سامانه",
        "platform_users",
        (
            "platform_users",
            "platform_user_create",
            "platform_user_detail",
            "platform_user_edit",
        ),
        "id-card",
    ),
    ("مدیران پلتفرم", "platform_administrators", ("platform_administrators",), "users"),
    (
        "نقش‌ها و مجوزها",
        "platform_role_catalog",
        (
            "platform_role_catalog",
            "platform_member_roles",
            "platform_member_authorization",
        ),
        "layers",
    ),
    (
        "تنظیمات پلتفرم",
        "platform_settings",
        ("platform_settings", "protected_operation_catalog", "platform_policy_catalog"),
        "settings",
    ),
    ("فعالیت‌ها و ممیزی", "platform_audit", ("platform_audit",), "notes"),
    ("وضعیت سامانه", "platform_status", ("platform_status",), "activity"),
)

SITE_CONTEXT_NAMESPACES = frozenset(
    {
        "compliance",
        "daily_reports",
        "equipment",
        "inventory",
        "quality",
        "safety",
        "timekeeping",
        "workforce",
    }
)

PROJECT_REQUIRED_MUTATIONS = frozenset(
    {
        "daily_reports:create",
        "estimates:create",
        "expenses:create",
        "expenses:draft_create",
        "quality:create",
        "safety:create",
    }
)


def business_permissions(request: HttpRequest) -> dict[str, object]:
    """Expose the active role's capability codes to templates once per request."""

    organization = getattr(request, "organization", None)
    permission_codes: set[str] = set()
    context_projects = ()
    context_sites = ()
    active_project = getattr(request, "active_project", None)
    active_site = getattr(request, "active_site", None)
    ess_subject_available = False
    my_requests_workspace_available = False
    manager_workspace_entry_available = False
    compliance_workspace_available = False
    inventory_receiving_available = False
    header_identity = None
    if organization is not None and request.user.is_authenticated:
        try:
            membership = get_active_membership(
                user=request.user,
                organization=organization,
            )
        except PermissionDenied:
            pass
        else:
            header_identity = membership_header_identity(membership=membership)
            permission_codes = {
                code
                for code in membership_permission_codes(membership)
                if membership_has_scope(
                    membership,
                    allow_any_scope=permission_supports_object_scope(code),
                )
            }
            inventory_receiving_available = inventory_transfer_receiving_available(
                membership
            )
            compliance_workspace_available = (
                BusinessPermissionCode.COMPLIANCE_VIEW
                in membership_permission_codes(membership)
                and membership_has_scope(membership, allow_any_scope=True)
                and route_exposed("compliance:workbench")
            )
            context_projects = scoped_context_projects(
                user=request.user, organization=organization
            )
            if active_project is not None:
                context_sites = scoped_context_sites(
                    user=request.user,
                    organization=organization,
                    project=active_project,
                )
            ess_subject_available = has_ess_subject(
                user=request.user, organization=organization
            )
            my_requests_workspace_available = my_requests_available(
                actor=request.user, organization=organization
            )
            manager_workspace_entry_available = manager_workspace_available(
                actor=request.user, organization=organization
            )

    resolver_match = getattr(request, "resolver_match", None)
    namespace = resolver_match.namespace if resolver_match else None
    view_name = resolver_match.view_name if resolver_match else None

    groups = (
        navigation_groups(
            permission_codes,
            {
                "my_requests_workspace_available": my_requests_workspace_available,
                "manager_workspace_available": manager_workspace_entry_available,
                "inventory_receiving_only": inventory_receiving_available
                and BusinessPermissionCode.WAREHOUSES_VIEW not in permission_codes,
            },
        )
        if organization is not None and permission_codes
        else ()
    )

    platform_access = platform_administration_exposed(request.user)
    can_view_platform_users = (
        platform_access
        and BusinessPermissionCode.PLATFORM_ADMIN_USERS_VIEW
        in user_management_permissions(request.user)
    )
    current_url_name = resolver_match.url_name if namespace == "organizations" else None
    return {
        "header_identity": header_identity,
        "product_navigation_groups": groups,
        "business_permission_codes": permission_codes,
        "inventory_receiving_available": inventory_receiving_available,
        "compliance_workspace_available": compliance_workspace_available,
        "party_governance_available": BusinessPermissionCode.PARTIES_VIEW
        in permission_codes
        and bool(permission_codes & GOVERNANCE_PERMISSIONS),
        "platform_navigation_access": platform_access,
        "platform_workspace": bool(
            platform_access and view_name and is_platform_workspace_route(view_name)
        ),
        "platform_navigation": [
            (label, f"organizations:{route}", current_url_name in routes, icon)
            for label, route, routes, icon in PLATFORM_NAVIGATION
            if route != "platform_users" or can_view_platform_users
        ]
        if platform_access
        else (),
        "can_view_platform_users": can_view_platform_users,
        "platform_surface_profile": surface_profile() if platform_access else "",
        "reference_persona_catalogue_enabled": reference_catalogue_enabled(),
        "can_view_contracts": BusinessPermissionCode.CONTRACTS_VIEW in permission_codes,
        "can_manage_contracts": BusinessPermissionCode.CONTRACTS_CREATE
        in permission_codes,
        "context_projects": context_projects,
        "context_sites": context_sites,
        "active_project": active_project,
        "active_site": active_site,
        "site_context_relevant": namespace in SITE_CONTEXT_NAMESPACES,
        "context_requires_project": view_name in PROJECT_REQUIRED_MUTATIONS,
        "ess_subject_available": ess_subject_available,
        "my_requests_workspace_available": my_requests_workspace_available,
        "manager_workspace_available": manager_workspace_entry_available,
    }
