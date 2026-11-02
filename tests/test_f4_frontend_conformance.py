"""F4: four representative surfaces with all shared enhancements together."""

import json
import os
import subprocess
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.billing import test_mvp03_browser as browser_fixture
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationRole,
)
from apps.procurement.models import PurchaseRequest
from apps.procurement.services import add_purchase_request_item, create_purchase_request
from apps.procurement.test_mvp04d import ReceiptJourneyFixture
from apps.workforce.test_mvp02 import make_field_fixture
from core.product_surface import route_exposed, url_exposed

ROOT = Path(__file__).resolve().parents[1]


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SharedFrontendConformanceTests(ReceiptJourneyFixture, StaticLiveServerTestCase):
    serialized_rollback = True
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_shared_frontend_together_at_both_widths_offline(self):
        make_field_fixture(self.owner, self.organization)
        requests = []
        for width in (1440, 390):
            record = create_purchase_request(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                request_number=f"F4-PR-{width}",
                title="مصالح آزمایشی F4",
            )
            add_purchase_request_item(
                organization=self.organization,
                actor=self.owner,
                purchase_request=record,
                material=self.material,
                quantity=Decimal(2),
            )
            requests.append(record)
        reader = User.objects.create_user(username="f4-project-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="f4-project-reader",
            name="Project reader",
        )
        role.permissions.add(BusinessPermission.objects.get(code="projects.view"))
        membership = self.organization.memberships.create(
            user=reader, role_definition=role, status=MembershipStatus.ACTIVE
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
        )
        sessions, scenarios = {}, []
        for actor_name, actor in (("owner", self.owner), ("restricted", reader)):
            self.client = Client()
            self.login(actor)
            sessions[actor_name] = self.client.cookies["sessionid"].value
            if actor_name == "restricted":
                self.assertEqual(
                    self.client.get(reverse("contracts:create")).status_code, 403
                )
            for width, record in zip((1440, 390), requests, strict=True):
                pages = [
                    ("projects", "projects:list", [], "", "", "projects:list", False)
                ]
                if actor_name == "owner":
                    pages += [
                        (
                            "mvp02-worker",
                            "workforce:field_create",
                            [],
                            "work_team",
                            "آرماتور",
                            "workforce:field_list",
                            False,
                        ),
                        (
                            "mvp03-contract",
                            "contracts:create",
                            [],
                            "project",
                            "سازه",
                            "contracts:list",
                            False,
                        ),
                        (
                            "mvp04-pr",
                            "procurement:request_detail",
                            [record.pk],
                            "material",
                            "سیمان",
                            "procurement:request_list",
                            True,
                        ),
                    ]
                for name, route, args, choice, query, active, action in pages:
                    path = reverse(route, args=args)
                    self.assertTrue(url_exposed(path))
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    expected = [
                        {"label": link.label, "url": reverse(link.route)}
                        for group in response.context["product_navigation_groups"]
                        for link in group.links
                    ]
                    if actor_name == "restricted":
                        self.assertNotIn(
                            reverse("contracts:list"), [x["url"] for x in expected]
                        )
                    scenarios.append(
                        {
                            "name": f"{actor_name}-{name}-{width}",
                            "path": path,
                            "actor": actor_name,
                            "width": width,
                            "choice": choice,
                            "query": query,
                            "active": reverse(active),
                            "action": action,
                            "expected": expected,
                        }
                    )
        for route in (
            "accounting:dashboard",
            "payroll:workbench",
            "workforce:foundation",
        ):
            self.assertFalse(route_exposed(route))
        output = ROOT / "output/f4/browser"
        output.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["F4_SESSIONS"], env["F4_SCENARIOS"] = (
            json.dumps(sessions),
            json.dumps(scenarios),
        )
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/f4_browser.mjs"),
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
        self.assertEqual(
            list(
                PurchaseRequest.objects.filter(
                    pk__in=[r.pk for r in requests]
                ).values_list("status", flat=True)
            ),
            ["submitted", "submitted"],
        )
