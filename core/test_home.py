"""CEP-002 canonical Home authorization and presentation checks."""

from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.models import MembershipStatus, OrganizationMembership
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
)
from core.home import authorized_home_links


class HomeTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="home-owner", password="test-password"
        )
        self.organization = create_organization_with_owner(
            owner=self.user, name="Home Company", slug="home-company"
        )
        self.client.force_login(self.user)

    def test_root_requires_login_and_has_canonical_name(self) -> None:
        self.client.logout()
        self.assertEqual(reverse("home"), "/")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_normal_home_has_context_and_only_links_not_business_facts(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-home-state="normal"')
        self.assertContains(response, "Home Company")
        self.assertContains(response, reverse("projects:list"))
        self.assertContains(response, reverse("accounts:settings"))
        self.assertContains(response, '<html lang="fa" dir="rtl">')
        self.assertContains(response, 'class="erp-mobile-nav lg:hidden"')
        self.assertContains(response, 'href="/"')
        self.assertNotContains(response, "تعداد پروژه‌ها")
        self.assertNotContains(response, "جمع هزینه")

    def test_invalid_selected_organization_is_unauthorized_without_leak(self) -> None:
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = (
            "00000000-0000-0000-0000-000000000001"
        )
        session.save()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'data-home-state="unauthorized"', status_code=403)
        self.assertNotContains(response, "Home Company", status_code=403)

    def test_no_membership_is_empty_and_does_not_expose_workspace(self) -> None:
        OrganizationMembership.objects.filter(user=self.user).update(
            status=MembershipStatus.REVOKED
        )
        response = self.client.get("/")
        self.assertContains(response, 'data-home-state="empty"')
        self.assertNotContains(response, "Home Company")
        self.assertNotContains(response, reverse("projects:list"))

    def test_multiple_memberships_without_active_context(self) -> None:
        other = create_organization_with_owner(
            owner=self.user, name="Other Home Company", slug="other-home-company"
        )
        session = self.client.session
        session.pop(ACTIVE_ORGANIZATION_SESSION_KEY, None)
        session.save()
        response = self.client.get("/")
        self.assertContains(response, 'data-home-state="no_context"')
        self.assertNotContains(response, other.name)
        self.assertNotContains(response, self.organization.name)

    def test_link_selection_denies_missing_membership(self) -> None:
        outsider = User.objects.create_user(username="home-outsider")
        with self.assertRaises(PermissionDenied):
            authorized_home_links(user=outsider, organization=self.organization)

    def test_multi_permission_home_deduplicates_destinations(self) -> None:
        with (
            patch(
                "core.home.membership_permission_codes",
                return_value=frozenset(
                    {"projects.view", "documents.view", "work_items.view"}
                ),
            ),
            patch("core.home.membership_has_scope", return_value=True),
        ):
            workspaces, assigned_work, alerts = authorized_home_links(
                user=self.user, organization=self.organization
            )
        self.assertEqual(
            [link.route for link in workspaces], ["projects:list", "documents:list"]
        )
        self.assertEqual(assigned_work.route, "workflows:workbench")
        self.assertIsNone(alerts)

    def test_scope_removes_business_link_even_with_permission(self) -> None:
        with (
            patch(
                "core.home.membership_permission_codes",
                return_value=frozenset({"projects.view"}),
            ),
            patch("core.home.membership_has_scope", return_value=False),
        ):
            workspaces, assigned_work, alerts = authorized_home_links(
                user=self.user, organization=self.organization
            )
        self.assertEqual((workspaces, assigned_work, alerts), ((), None, None))

    def test_notification_and_work_entries_are_permission_gated(self) -> None:
        with (
            patch(
                "core.home.membership_permission_codes",
                return_value=frozenset(
                    {"work_items.view", "support.notifications_view"}
                ),
            ),
            patch("core.home.membership_has_scope", return_value=True),
        ):
            workspaces, assigned_work, alerts = authorized_home_links(
                user=self.user, organization=self.organization
            )
        self.assertEqual(workspaces, ())
        self.assertEqual(assigned_work.route, "workflows:workbench")
        self.assertEqual(alerts.route, "support:notifications")

    def test_no_authorized_workspace_state(self) -> None:
        with patch("core.views.authorized_home_links", return_value=((), None, None)):
            response = self.client.get("/")
        self.assertContains(response, 'data-home-state="no_workspace"')
        self.assertEqual(response.context["home_workspaces"], ())

    def test_error_state_is_safe(self) -> None:
        with patch(
            "core.views.authorized_home_links", side_effect=RuntimeError("private")
        ):
            response = self.client.get("/")
        self.assertContains(response, 'data-home-state="error"', status_code=503)
        self.assertNotContains(response, "private", status_code=503)

    def test_financial_dashboard_remains_separately_guarded(self) -> None:
        outsider = User.objects.create_user(username="financial-outsider")
        self.client.force_login(outsider)
        response = self.client.get(reverse("financials:dashboard"))
        self.assertNotEqual(response.status_code, 200)
        response = self.client.get(reverse("projects:list"))
        self.assertNotEqual(response.status_code, 200)
