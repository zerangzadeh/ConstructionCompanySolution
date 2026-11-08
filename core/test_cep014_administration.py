"""Focused CEP-014 administration-surface separation checks."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
)

PLATFORM_ROUTES = (
    "organizations:create",
    "organizations:platform_role_catalog",
    "organizations:protected_operation_catalog",
    "organizations:platform_policy_catalog",
)


class Cep014AdministrationTemplateTests(SimpleTestCase):
    def test_platform_navigation_is_shared_between_desktop_and_mobile(
        self,
    ) -> None:
        template_root = Path(settings.BASE_DIR) / "templates"
        navigation = (template_root / "components" / "navigation_links.html").read_text(
            encoding="utf-8"
        )
        base = (template_root / "base.html").read_text(encoding="utf-8")

        self.assertNotIn('data-nav-id="NAV-042"', navigation)
        self.assertIn('data-nav-id="NAV-042"', base)
        self.assertIn("platform_navigation_access", base)
        self.assertIn("lg:flex", base)
        self.assertEqual(
            base.count('{% include "organizations/platform_navigation.html" %}'), 2
        )

    def test_tenant_administration_remains_in_the_shared_company_navigation(
        self,
    ) -> None:
        from core.product_surface import navigation_groups

        groups = navigation_groups({"company.settings.view"})
        self.assertEqual([g.key for g in groups], ["foundation"])
        self.assertIn(
            "organizations:settings", {link.route for link in groups[0].links}
        )


class Cep014AdministrationRouteTests(TestCase):
    def setUp(self) -> None:
        self.tenant_owner = User.objects.create_user(
            username="cep014-tenant-owner", password="test-password"
        )
        self.organization = create_organization_with_owner(
            owner=self.tenant_owner,
            name="CEP 014 Tenant",
            slug="cep014-tenant",
        )
        self.root = User.objects.create_superuser(
            username="cep014-root", password="test-password", email="root@example.test"
        )
        self.platform_admin = User.objects.create_user(
            username="cep014-platform-admin", password="test-password"
        )
        assign_platform_admin(
            actor=self.root,
            approver=self.root,
            target=self.platform_admin,
            reason="CEP-014 platform boundary test",
        )

    def _activate_tenant(self) -> None:
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

    def test_tenant_owner_can_use_tenant_settings_but_not_platform_catalogue(
        self,
    ) -> None:
        self.client.force_login(self.tenant_owner)
        self._activate_tenant()

        self.assertEqual(
            self.client.get(reverse("organizations:settings")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("organizations:platform_role_catalog")).status_code,
            403,
        )

    @override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP")
    def test_platform_admin_can_use_platform_catalogue_but_has_no_implicit_tenant_access(
        self,
    ) -> None:
        self.client.force_login(self.platform_admin)
        self._activate_tenant()

        self.assertEqual(
            self.client.get(reverse("organizations:platform_role_catalog")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("organizations:platform_policy_catalog")
            ).status_code,
            200,
        )
        response = self.client.get(reverse("organizations:settings"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(str(self.organization.pk), response.content.decode())

    @override_settings(PRODUCT_SURFACE_PROFILE="MVP")
    def test_mvp_platform_admin_can_open_platform_tools_without_a_tenant(self) -> None:
        self.client.force_login(self.platform_admin)
        home = self.client.get(reverse("home"))
        for route in (
            "organizations:platform_dashboard",
            "organizations:platform_company_list",
            "organizations:platform_role_catalog",
            "organizations:platform_settings",
        ):
            self.assertContains(home, f'href="{reverse(route)}"')
        for route in PLATFORM_ROUTES:
            with self.subTest(route=route):
                url = reverse(route)
                self.assertEqual(self.client.get(url).status_code, 200)
        settings_page = self.client.get(reverse("organizations:platform_settings"))
        for route in (
            "organizations:protected_operation_catalog",
            "organizations:platform_policy_catalog",
        ):
            self.assertContains(settings_page, f'href="{reverse(route)}"')
        selector = self.client.get(reverse("organizations:select"))
        self.assertContains(selector, f'href="{reverse("organizations:create")}"')
        for route in ("admin:index", "organizations:reference_personas"):
            with self.subTest(route=route):
                url = reverse(route)
                self.assertNotContains(home, f'href="{url}"')
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotIn(ACTIVE_ORGANIZATION_SESSION_KEY, self.client.session)

    @override_settings(PRODUCT_SURFACE_PROFILE="MVP")
    def test_mvp_platform_tools_require_the_platform_role(self) -> None:
        for user in (self.tenant_owner, self.root):
            self.client.force_login(user)
            self.assertNotContains(
                self.client.get(reverse("home")), 'data-nav-id="NAV-042"'
            )
            for route in PLATFORM_ROUTES:
                with self.subTest(user=user.username, route=route):
                    url = reverse(route)
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url).status_code, 403)
