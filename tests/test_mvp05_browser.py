"""Representative real Chrome downloads; files are reopened after completion."""

import json
import os
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from openpyxl import load_workbook

from apps.billing import test_mvp03_browser as chrome
from apps.billing.test_mvp03 import JourneyFixture
from apps.expenses.services import create_expense
from apps.inventory.test_mvp04e import InventoryJourneyFixture
from apps.procurement import test_rfq as rfq_fixture
from tests import test_f2_shared_interactions as interactions
from tests import test_f3_module_selector as modules

ROOT = Path(__file__).resolve().parents[1]


class RegressionEvidenceRoot:
    def __truediv__(self, relative):
        if relative == "output/f2/browser":
            return ROOT / "output/mvp-05/frontend-regression"
        return ROOT / relative


class FrontendInteractionRegressionTests(interactions.SharedInteractionBrowserTests):
    def test_three_surfaces_at_desktop_and_mobile_offline(self):
        with patch.object(interactions, "ROOT", RegressionEvidenceRoot()):
            super().test_three_surfaces_at_desktop_and_mobile_offline()


class ModuleSelectorRegressionTests(modules.ModuleSelectorBrowserTests):
    def test_four_representative_routes_and_restricted_membership_offline(self):
        with patch.dict(
            os.environ,
            {
                "MODULE_SELECTOR_EVIDENCE_DIRECTORY": str(
                    ROOT / "output/mvp-05/module-selector-regression"
                )
            },
        ):
            super().test_four_representative_routes_and_restricted_membership_offline()


class DownloadBrowserMixin:
    serialized_rollback = True
    _fixture_teardown = chrome.ContractBillingBrowserTests._fixture_teardown

    def downloads(self, actor, name, scenarios):
        self.login(actor)
        env = os.environ.copy()
        env["MVP05_SESSION"] = self.client.cookies["sessionid"].value
        env["MVP05_SCENARIOS"] = json.dumps(scenarios)
        directory = ROOT / "output/mvp-05/browser" / name
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/mvp05_browser.mjs"),
                self.live_server_url,
                str(directory),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf8",
            timeout=240,
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-4000:])
        results = json.loads(result.stdout)
        for case in results:
            for download in case["downloads"]:
                workbook = load_workbook(download["filename"])
                self.assertTrue(workbook.active.sheet_view.rightToLeft)
                self.assertGreater(workbook.active.max_row, 1)
                self.assertFalse(
                    any(c.data_type == "f" for s in workbook for row in s for c in row)
                )
        return results


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class BillingDownloadsTests(
    DownloadBrowserMixin, JourneyFixture, StaticLiveServerTestCase
):
    def setUp(self):
        self.make_fixture(persian=True)

    def test_billing_list_and_document_desktop_mobile_download(self):
        claim = self._claim()
        self.downloads(
            self.owner,
            "billing",
            [
                {
                    "name": "list-desktop",
                    "path": reverse("billing:claim_list")
                    + f"?contract={claim.contract_id}",
                },
                {
                    "name": "detail-mobile",
                    "path": reverse("billing:claim_detail", args=[claim.pk]),
                    "width": 390,
                },
            ],
        )


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class OperationalDownloadsTests(
    DownloadBrowserMixin, InventoryJourneyFixture, StaticLiveServerTestCase
):
    def test_all_operational_downloads_and_unauthorized_action_absence(self):
        rfq_fixture.RequestForQuotationServiceTests._draft(self)
        _receipt, source = self.received_source()
        record = self.stock_create(source)
        self.assertEqual(self.stock_post(record).status_code, 302)
        from apps.expenses.models import PlatformExpenseGroup

        PlatformExpenseGroup.objects.get_or_create(
            code="other", defaults={"name": "سایر هزینه‌ها"}
        )
        create_expense(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            description="هزینه تنخواه کارگاه",
            amount=Decimal("1250.25"),
            incurred_on=date(2026, 11, 3),
        )
        routes = [
            "procurement:request_list",
            "procurement:rfq_list",
            "procurement:order_list",
            "procurement:receipt_list",
            "inventory:transaction_list",
            "expenses:list",
        ]
        self.downloads(
            self.owner,
            "operational",
            [
                {
                    "name": route.replace(":", "-"),
                    "path": reverse(route),
                    "width": 390 if index % 2 else 1440,
                }
                for index, route in enumerate(routes)
            ],
        )
        from apps.accounts.models import User

        reader = User.objects.create_user(username="browser-no-export")
        self.organization.memberships.create(
            user=reader, role="viewer", status="active"
        )
        self.downloads(
            reader,
            "denied",
            [
                {"name": route.replace(":", "-"), "path": reverse(route), "status": 403}
                for route in routes
            ],
        )
