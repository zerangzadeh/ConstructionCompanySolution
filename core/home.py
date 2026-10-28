"""Bounded, permission-aware links for the canonical Home entry."""

from dataclasses import dataclass

from apps.accounts.models import User
from apps.organizations.authorization import (
    get_active_membership,
    membership_has_scope,
    membership_permission_codes,
    permission_supports_object_scope,
)
from apps.organizations.models import Organization
from apps.workflows.personal_workspaces import (
    manager_workspace_available,
    my_requests_available,
)
from core.product_surface import navigation_groups, route_exposed


@dataclass(frozen=True)
class HomeLink:
    label: str
    route: str
    permission: str


ASSIGNED_WORK = HomeLink("کارهای ارجاع‌شده", "workflows:workbench", "work_items.view")
ALERTS = HomeLink("اعلان‌ها", "support:notifications", "support.notifications_view")


def authorized_home_links(
    *, user: User, organization: Organization
) -> tuple[tuple[HomeLink, ...], HomeLink | None, HomeLink | None]:
    """Select navigation only from current membership permissions and scope."""

    membership = get_active_membership(user=user, organization=organization)
    effective_codes = {
        code
        for code in membership_permission_codes(membership)
        if membership_has_scope(
            membership,
            allow_any_scope=permission_supports_object_scope(code),
        )
    }
    groups = navigation_groups(
        effective_codes,
        {
            "my_requests_workspace_available": my_requests_available(
                actor=user,
                organization=organization,
            ),
            "manager_workspace_available": manager_workspace_available(
                actor=user,
                organization=organization,
            ),
        },
    )
    workspaces = tuple(
        HomeLink(link.label, link.route, link.permission)
        for group in groups
        for link in group.links
        if (link.permission or link.availability) and link.route != ASSIGNED_WORK.route
    )
    assigned_work = (
        ASSIGNED_WORK
        if ASSIGNED_WORK.permission in effective_codes
        and route_exposed(ASSIGNED_WORK.route)
        else None
    )
    alerts = (
        ALERTS
        if ALERTS.permission in effective_codes and route_exposed(ALERTS.route)
        else None
    )
    return workspaces, assigned_work, alerts
