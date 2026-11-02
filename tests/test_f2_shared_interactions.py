"""Three representative F2 surfaces; real local Chrome and isolated test data."""

import json
import os
import subprocess
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.procurement.models import PurchaseRequest
from apps.procurement.services import (
    add_purchase_request_item,
    create_purchase_request,
)
from apps.procurement.test_mvp04d import ReceiptJourneyFixture
from apps.workforce.test_mvp02 import make_field_fixture
from core.product_surface import url_exposed

ROOT = Path(__file__).resolve().parents[1]


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SharedInteractionBrowserTests(ReceiptJourneyFixture, StaticLiveServerTestCase):
    serialized_rollback = True
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_three_surfaces_at_desktop_and_mobile_offline(self):
        make_field_fixture(self.owner, self.organization)
        self.login(self.owner)
        scenarios = []
        request_ids = []
        for width in (1440, 390):
            record = create_purchase_request(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                request_number=f"F2-PR-{width}",
                title="مصالح آزمایشی F2",
            )
            add_purchase_request_item(
                organization=self.organization,
                actor=self.owner,
                purchase_request=record,
                material=self.material,
                quantity=Decimal(2),
            )
            request_ids.append(record.pk)
            for name, route, args, choice, query, action in (
                (
                    "mvp02-worker",
                    "workforce:field_create",
                    [],
                    "work_team",
                    "آرماتور",
                    False,
                ),
                ("mvp03-contract", "contracts:create", [], "project", "سازه", False),
                (
                    "mvp04-pr",
                    "procurement:request_detail",
                    [record.pk],
                    "material",
                    "سیمان",
                    True,
                ),
            ):
                path = reverse(route, args=args)
                self.assertTrue(url_exposed(path))
                scenarios.append(
                    {
                        "name": f"{name}-{width}",
                        "path": path,
                        "width": width,
                        "choice": choice,
                        "query": query,
                        "action": action,
                    }
                )
        evidence = ROOT / "output/f2/browser"
        evidence.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["F2_SESSION"] = self.client.cookies["sessionid"].value
        env["F2_SCENARIOS"] = json.dumps(scenarios)
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/f2_browser.mjs"),
                self.live_server_url,
                str(evidence),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=240,
            check=False,
        )
        (evidence / "command.txt").write_text(
            f"exit={result.returncode}\n{result.stdout}\n{result.stderr}",
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-5000:])
        self.assertEqual(json.loads(result.stdout)["pages"], 6)
        self.assertEqual(
            list(
                PurchaseRequest.objects.filter(pk__in=request_ids).values_list(
                    "status", flat=True
                )
            ),
            ["submitted", "submitted"],
        )
