"""F1 visual and offline evidence against migrated isolated PostgreSQL data."""

import json
import os
import subprocess
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.contracts.services import create_contract
from apps.estimates.services import create_estimate
from apps.procurement.services import create_purchase_request
from apps.procurement.test_mvp04d import ReceiptJourneyFixture
from apps.workforce.test_mvp02 import make_field_fixture
from core.product_surface import url_exposed

ROOT = Path(__file__).resolve().parents[1]


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class OfflineFrontendBrowserTests(ReceiptJourneyFixture, StaticLiveServerTestCase):
    serialized_rollback = True
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_representative_pages_with_external_network_blocked(self):
        contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="F1-C01",
            title="قرارداد سازه آزمایشی",
            counterparty_name="پیمانکار آزمایشی",
            direction="payable",
            contract_value=Decimal(125000000),
        )
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="F1-E01",
            title="برآورد سازه آزمایشی",
        )
        request = create_purchase_request(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            request_number="F1-PR01",
            title="درخواست مصالح آزمایشی",
        )
        order, _item = self.make_order()
        receipt = self.create_receipt(order)
        _project, _site, _team, employee, _report = make_field_fixture(
            self.owner, self.organization
        )
        self.login(self.owner)
        pages = [
            ("login", "accounts:login", [], {"anonymous": True}),
            ("shell", "home", [], {}),
            ("projects-list", "projects:list", [], {}),
            ("project-detail", "projects:detail", [self.project.pk], {}),
            ("contracts-list", "contracts:list", [], {}),
            ("contract-detail", "contracts:detail", [contract.pk], {}),
            ("estimate-detail", "estimates:detail", [estimate.pk], {}),
            ("pr-list", "procurement:request_list", [], {}),
            ("pr-detail", "procurement:request_detail", [request.pk], {}),
            ("rfq-list", "procurement:rfq_list", [], {}),
            ("po-detail", "procurement:order_detail", [order.pk], {}),
            ("grn-detail", "procurement:receipt_detail", [receipt.pk], {}),
            ("inventory", "inventory:transaction_list", [], {}),
            ("workforce", "workforce:field_list", [], {}),
            ("worker-detail", "workforce:field_detail", [employee.pk], {}),
            (
                "worker-form",
                "workforce:field_create",
                [],
                {"lookup": True, "datepicker": True},
            ),
            ("timekeeping", "timekeeping:workbench", [], {}),
        ]
        scenarios = []
        for width in (1440, 1024, 390):
            for name, route, args, options in pages:
                path = reverse(route, args=args)
                self.assertTrue(url_exposed(path), route)
                scenarios.append(
                    {"name": f"{name}-{width}", "path": path, "width": width, **options}
                )
        phase = os.environ.get("F1_PHASE", "offline")
        evidence_root = Path(
            os.environ.get("F1_EVIDENCE_ROOT", ROOT / "output/f1")
        ).resolve()
        self.assertTrue(evidence_root.is_relative_to((ROOT / "output/f1").resolve()))
        evidence = evidence_root / phase
        evidence.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["F1_SESSION"] = self.client.cookies["sessionid"].value
        env["F1_SCENARIOS"] = json.dumps(scenarios)
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/f1_browser.mjs"),
                self.live_server_url,
                str(evidence),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
            check=False,
        )
        (evidence / "command.txt").write_text(
            f"exit={result.returncode}\n{result.stdout}\n{result.stderr}",
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-5000:])
        self.assertEqual(json.loads(result.stdout)["pages"], len(scenarios))
