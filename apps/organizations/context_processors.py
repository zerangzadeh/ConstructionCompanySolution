from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.organizations.authorization import (
    get_active_membership,
    is_platform_admin,
    membership_has_scope,
    membership_permission_codes,
    permission_supports_object_scope,
)
from apps.organizations.context import scoped_context_projects, scoped_context_sites
from apps.organizations.models import BusinessPermissionCode
from apps.parties.presentation import GOVERNANCE_PERMISSIONS
from apps.workflows.personal_workspaces import (
    manager_workspace_available,
    my_requests_available,
)
from apps.workforce.ess_services import has_ess_subject

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
    if organization is not None and request.user.is_authenticated:
        try:
            membership = get_active_membership(
                user=request.user,
                organization=organization,
            )
        except PermissionDenied:
            pass
        else:
            permission_codes = {
                code
                for code in membership_permission_codes(membership)
                if membership_has_scope(
                    membership,
                    allow_any_scope=permission_supports_object_scope(code),
                )
            }
            compliance_workspace_available = (
                BusinessPermissionCode.COMPLIANCE_VIEW
                in membership_permission_codes(membership)
                and membership_has_scope(membership, allow_any_scope=True)
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

    return {
        "business_permission_codes": permission_codes,
        "compliance_workspace_available": compliance_workspace_available,
        "party_governance_available": BusinessPermissionCode.PARTIES_VIEW
        in permission_codes
        and bool(permission_codes & GOVERNANCE_PERMISSIONS),
        "platform_navigation_access": bool(
            request.user.is_authenticated and is_platform_admin(request.user)
        ),
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
