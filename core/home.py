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


@dataclass(frozen=True)
class HomeLink:
    label: str
    route: str
    permission: str


WORKSPACE_LINKS = (
    HomeLink("پروژه‌ها", "projects:list", "projects.view"),
    HomeLink("اسناد", "documents:list", "documents.view"),
    HomeLink("قراردادها", "contracts:list", "contracts.view"),
    HomeLink("تدارکات", "procurement:request_list", "purchase_requests.view"),
    HomeLink("فضای مالی قدیمی", "financials:dashboard", "financials.view"),
)
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
    workspaces = tuple(
        link for link in WORKSPACE_LINKS if link.permission in effective_codes
    )
    assigned_work = (
        ASSIGNED_WORK if ASSIGNED_WORK.permission in effective_codes else None
    )
    alerts = ALERTS if ALERTS.permission in effective_codes else None
    return workspaces, assigned_work, alerts
