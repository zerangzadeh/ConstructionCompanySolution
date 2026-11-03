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
from core.templatetags.product_surface import (
    module_selector_cards,
    module_selector_links,
)
from core.test_product_surface import grant_test_reporting_permission

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
        cards = module_selector_cards(groups, "projects:list", path)
        self.assertEqual(
            rendered.count('class="erp-module-selector__link"'), len(cards)
        )
        for card in cards:
            self.assertIn(f'href="{card["url"]}"', rendered)
            self.assertIn(card["title"], rendered)
        self.assertIn("ماژول‌های بنیرا", rendered)
        self.assertNotIn("بخش‌های سامانه", rendered)
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

    def test_cards_are_only_projections_of_authorized_destinations(self):
        for profile in ("MVP", "FULL_ERP"):
            with override_settings(PRODUCT_SURFACE_PROFILE=profile):
                for codes in (
                    set(),
                    {"projects.view"},
                    {"claims.view"},
                    {"warehouses.view"},
                    {
                        link.permission
                        for group in NAVIGATION_GROUPS
                        for link in group.links
                    },
                ):
                    groups = navigation_groups(codes)
                    source = module_selector_links(
                        groups, "contracts:list", "/contracts/"
                    )
                    cards = module_selector_cards(
                        groups, "contracts:list", "/contracts/"
                    )
                    self.assertTrue(
                        {c["url"] for c in cards} <= {i["url"] for i in source}
                    )
                    self.assertEqual(
                        sum(c["active"] for c in cards),
                        sum(i["active"] for i in source),
                    )
                    self.assertEqual(len({c["key"] for c in cards}), len(cards))
        self.assertEqual(module_selector_cards((), "projects:list", "/projects/"), [])

    def test_each_authorized_child_highlights_its_family(self):
        codes = {link.permission for group in NAVIGATION_GROUPS for link in group.links}
        groups = navigation_groups(codes)
        for group in groups:
            for link in group.links:
                path = reverse(link.route)
                active = [
                    card
                    for card in module_selector_cards(groups, link.route, path)
                    if card["active"]
                ]
                self.assertEqual(len(active), 1)
                self.assertEqual(active[0]["url"], path)
        restricted = navigation_groups({"claims.view"})
        card = next(
            c
            for c in module_selector_cards(restricted, "", "/")
            if c["key"] == "contracts"
        )
        self.assertEqual(card["url"], reverse("billing:claim_list"))


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
        grant_test_reporting_permission(self.owner, self.organization)
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
                    {"label": card["title"], "url": card["url"]}
                    for card in module_selector_cards(groups, route, path)
                ]
                if label == "restricted":
                    self.assertNotIn(
                        reverse("contracts:list"), [x["url"] for x in expected]
                    )
                    self.assertIn(
                        reverse("projects:list"), [x["url"] for x in expected]
                    )
                for width in (1440, 1024, 390):
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
        output = Path(
            os.environ.get(
                "MODULE_SELECTOR_EVIDENCE_DIRECTORY",
                ROOT / "output/module-selector-remediation/browser",
            )
        )
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
        self.assertEqual(json.loads(result.stdout)["pages"], 15)
