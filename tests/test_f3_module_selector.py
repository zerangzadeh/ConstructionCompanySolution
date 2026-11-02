"""Bounded shared-navigation tests using canonical filtered destinations."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.template import Context, Template
from django.test import Client, SimpleTestCase, override_settings
from django.urls import resolve, reverse

from apps.accounts.models import User
from apps.billing import test_mvp03_browser as browser_fixture
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationRole,
)
from apps.procurement.test_mvp04d import ReceiptJourneyFixture
from core.product_surface import NAVIGATION_GROUPS, navigation_groups, url_exposed
from core.templatetags.product_surface import module_selector_links

ROOT = Path(__file__).resolve().parents[1]


class ModuleSelectorPresentationTests(SimpleTestCase):
    def test_only_canonical_filtered_links_and_labels_are_rendered(self):
        codes = {"projects.view", "accounting.view", "payroll.view"}
        groups = navigation_groups(codes)
        path = reverse("projects:list")
        rendered = Template('{% include "components/module_selector.html" %}').render(
            Context(
                {
                    "request": SimpleNamespace(path=path, resolver_match=resolve(path)),
                    "product_navigation_groups": groups,
                }
            )
        )
        links = [link for group in groups for link in group.links]
        self.assertEqual(
            rendered.count('class="erp-module-selector__link"'), len(links)
        )
        for link in links:
            self.assertIn(f'href="{reverse(link.route)}"', rendered)
            self.assertIn(link.label, rendered)
        for route in ("contracts:list", "treasury:workbench", "payroll:workbench"):
            self.assertNotIn(f'href="{reverse(route)}"', rendered)
        self.assertEqual(rendered.count('aria-current="page"'), 1)

    def test_current_route_alias_and_longest_authorized_parent_path(self):
        codes = {link.permission for group in NAVIGATION_GROUPS for link in group.links}
        groups = navigation_groups(codes)
        for route, args, expected in (
            ("projects:detail", [uuid4()], "projects:list"),
            ("contracts:detail", [uuid4()], "contracts:list"),
            ("procurement:request_detail", [uuid4()], "procurement:request_list"),
            ("workforce:field_detail", [uuid4()], "workforce:field_list"),
            ("workforce:work_team_list", [], "workforce:field_list"),
        ):
            with self.subTest(route=route):
                items = module_selector_links(groups, route, reverse(route, args=args))
                active = [item["link"].route for item in items if item["active"]]
                self.assertEqual(active, [expected])
        # A denied destination never acquires a label/link through path matching.
        restricted = navigation_groups({"projects.view"})
        items = module_selector_links(
            restricted, "contracts:list", reverse("contracts:list")
        )
        self.assertFalse(any(item["active"] for item in items))

    def test_empty_navigation_has_no_fabricated_destination(self):
        self.assertEqual(module_selector_links((), "projects:list", "/projects/"), [])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ModuleSelectorBrowserTests(ReceiptJourneyFixture, StaticLiveServerTestCase):
    serialized_rollback = True
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_four_representative_routes_and_restricted_membership_offline(self):
        restricted = User.objects.create_user(username="f3-project-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="f3-project-reader",
            name="Project reader",
        )
        role.permissions.add(BusinessPermission.objects.get(code="projects.view"))
        membership = self.organization.memberships.create(
            user=restricted, role_definition=role, status=MembershipStatus.ACTIVE
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
        )
        scenarios = []
        sessions = {}
        for label, actor in (("owner", self.owner), ("restricted", restricted)):
            # force_login on a client already holding another actor's session
            # invalidates that session; each browser actor needs its own client.
            self.client = Client()
            self.login(actor)
            sessions[label] = self.client.cookies["sessionid"].value
            routes = (
                ["projects:list"]
                if label == "restricted"
                else [
                    "projects:list",
                    "contracts:list",
                    "procurement:request_list",
                    "workforce:field_list",
                ]
            )
            for route in routes:
                path = reverse(route)
                self.assertTrue(url_exposed(path))
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                groups = response.context["product_navigation_groups"]
                expected = [
                    {"label": link.label, "url": reverse(link.route)}
                    for group in groups
                    for link in group.links
                ]
                if label == "restricted":
                    self.assertNotIn(
                        reverse("contracts:list"), [x["url"] for x in expected]
                    )
                    self.assertIn(
                        reverse("projects:list"), [x["url"] for x in expected]
                    )
                for width in (1440, 390):
                    scenarios.append(
                        {
                            "name": f"{label}-{route.replace(':', '-')}-{width}",
                            "path": path,
                            "width": width,
                            "actor": label,
                            "expected": expected,
                            "active": path,
                            "navigateTo": reverse("contracts:list")
                            if label == "owner" and route == "projects:list"
                            else "",
                        }
                    )
        output = ROOT / "output/f3/browser"
        output.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["F3_SESSIONS"] = json.dumps(sessions)
        env["F3_SCENARIOS"] = json.dumps(scenarios)
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/f3_browser.mjs"),
                self.live_server_url,
                str(output),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=240,
            check=False,
        )
        (output / "command.txt").write_text(
            f"exit={result.returncode}\n{result.stdout}\n{result.stderr}",
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-6000:])
        self.assertEqual(json.loads(result.stdout)["pages"], 10)
