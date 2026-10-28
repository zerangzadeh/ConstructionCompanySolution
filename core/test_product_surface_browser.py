"""MVP-01 A–G customer surface verification in real desktop/mobile Chrome."""

import json
import os
import subprocess
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from core.product_surface import url_exposed
from core.test_product_surface import (
    create_test_own_leave,
    grant_test_reporting_permission,
)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ProductSurfaceBrowserTests(StaticLiveServerTestCase):
    def _probe(self, actor, scenarios):
        root = Path(__file__).resolve().parent.parent
        self.client.force_login(actor)
        env = os.environ.copy()
        env["MVP01_SESSION"] = self.client.cookies["sessionid"].value
        env["MVP01_SCENARIOS"] = json.dumps(scenarios)
        result = subprocess.run(
            [
                "node",
                str(root / "scripts/verification/mvp01_browser.mjs"),
                self.live_server_url,
                str(root / "output/mvp-01/browser"),
                actor.username,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        results = json.loads(result.stdout)
        self.assertEqual(len(results), len(scenarios))
        for row in results:
            for link in row["links"]:
                if link.startswith("/"):
                    self.assertTrue(url_exposed(link), f"{row['name']} exposes {link}")
        return results

    def test_scenarios_a_through_g(self):
        owner = User.objects.create_user(username="mvp01-browser-admin")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت آزمایشی بنیرا", slug="mvp01-browser"
        )
        grant_test_reporting_permission(owner, organization)
        own_leave = create_test_own_leave(owner, organization)
        groups = ["operations", "claims", "materials", "shared", "foundation"]
        hidden = [
            "/treasury/",
            "/accounting/",
            "/payroll/",
            "/workforce/ess/",
            "/reporting/reconciliations/",
            "/organizations/platform/reference-personas/",
        ]
        self._probe(
            owner,
            [
                {
                    "name": "A-C-home-desktop",
                    "path": "/",
                    "status": 200,
                    "groups": groups,
                    "mustLinks": [
                        "/organizations/members/",
                        "/projects/",
                        "/expenses/",
                        "/timekeeping/",
                    ],
                    "absentLinks": hidden,
                    "screenshot": True,
                },
                {
                    "name": "A-C-home-mobile",
                    "path": "/",
                    "status": 200,
                    "groups": groups,
                    "mobile": True,
                    "absentLinks": hidden,
                    "screenshot": True,
                },
                {"name": "D-hidden-cash", "path": "/treasury/", "status": 403},
                {"name": "E-visible-projects", "path": "/projects/", "status": 200},
                {
                    "name": "F-expenses",
                    "path": "/expenses/",
                    "status": 200,
                    "mustLinks": ["/expenses/draft/create/"],
                    "absentLinks": hidden,
                    "screenshot": True,
                },
                {
                    "name": "F-expense-draft",
                    "path": "/expenses/draft/create/",
                    "status": 200,
                },
                {
                    "name": "G-workforce",
                    "path": "/workforce/",
                    "status": 200,
                    "mustLinks": ["/workforce/assignments/"],
                    "absentLinks": hidden
                    + [
                        "/workforce/foundation/",
                        "/workforce/positions/",
                        "/workforce/departments/",
                    ],
                    "screenshot": True,
                },
                {"name": "G-timekeeping", "path": "/timekeeping/", "status": 200},
                {"name": "G-hidden-ess", "path": "/workforce/ess/", "status": 403},
                {
                    "name": "G-own-timekeeping-status",
                    "path": f"/workforce/ess/requests/leave/{own_leave.pk}/",
                    "status": 200,
                    "mustLinks": ["/workflows/my-requests/"],
                    "absentLinks": hidden,
                },
                {
                    "name": "G-hidden-hr-status",
                    "path": f"/workforce/ess/requests/personal_data/{own_leave.pk}/",
                    "status": 403,
                },
                {
                    "name": "reports",
                    "path": "/reporting/",
                    "status": 200,
                    "absentLinks": hidden,
                },
                {
                    "name": "safety",
                    "path": "/safety/",
                    "status": 200,
                    "absentLinks": ["/compliance/"],
                },
                {
                    "name": "quality",
                    "path": "/quality/",
                    "status": 200,
                    "absentLinks": ["/compliance/"],
                },
            ],
        )
        reader = User.objects.create_user(username="mvp01-browser-reader")
        role = OrganizationRole.objects.create(
            code="mvp01_browser_reader", name="Expense reader"
        )
        role.permissions.add(BusinessPermission.objects.get(code="expenses.view"))
        membership = OrganizationMembership.objects.create(
            organization=organization,
            user=reader,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
        )
        self._probe(
            reader,
            [
                {
                    "name": "B-ordinary-home",
                    "path": "/",
                    "status": 200,
                    "groups": ["operations", "foundation"],
                    "mustLinks": ["/expenses/"],
                    "absentLinks": hidden + ["/projects/", "/organizations/members/"],
                    "screenshot": True,
                },
                {
                    "name": "B-visible-without-permission",
                    "path": "/projects/",
                    "status": 403,
                },
                {"name": "B-exposed-authorized", "path": "/expenses/", "status": 200},
            ],
        )
