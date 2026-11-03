"""Release-verification boundaries and current native output regression."""

import json
import os
import subprocess
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from apps.accounts.management.commands import seed_mvp_demo as seed
from apps.billing import test_mvp03_browser as chrome
from apps.daily_reports.models import DailyReport
from apps.procurement.buyer_ui import action_url
from apps.procurement.test_mvp04d import ReceiptJourneyFixture
from apps.procurement.test_mvp04f import ConnectedJourneyFixture
from apps.projects.models import ProjectSite
from tests import test_mvp06_print as print_fixture

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = Path(os.environ.get("MVP08_OUTPUT_ROOT", ROOT / "output/mvp-08"))


class SeedEnvironmentTests(SimpleTestCase):
    def test_duty_extension_rejects_another_database_before_any_seed_write(self):
        with (
            override_settings(
                SETTINGS_MODULE="config.settings.development", DEBUG=True
            ),
            patch.dict(
                seed.connection.settings_dict, HOST="localhost", NAME="test_unrelated"
            ),
            patch.object(seed.Command, "_seed") as mutate,
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "seed_mvp_demo", terms_source="unused", rfq_duty_personas=True
                )
            mutate.assert_not_called()

    def test_production_is_denied_even_with_debug_and_pytest_loaded(self):
        with (
            override_settings(SETTINGS_MODULE="config.settings.production", DEBUG=True),
            patch.object(seed.Command, "_seed") as mutate,
        ):
            with self.assertRaises(CommandError):
                call_command("seed_mvp_demo", terms_source="unused")
            mutate.assert_not_called()

    def test_base_and_custom_settings_fail_closed(self):
        for module in (
            "config.settings.base",
            "custom.development",
            "config.settings.test",
        ):
            with (
                self.subTest(module=module),
                override_settings(SETTINGS_MODULE=module, DEBUG=True),
                self.assertRaises(CommandError),
            ):
                seed.guard_environment()

    def test_remote_database_and_debug_false_are_denied(self):
        with (
            override_settings(
                SETTINGS_MODULE="config.settings.development", DEBUG=False
            ),
            self.assertRaises(CommandError),
        ):
            seed.guard_environment()
        with (
            override_settings(
                SETTINGS_MODULE="config.settings.development", DEBUG=True
            ),
            patch.dict(seed.connection.settings_dict, HOST="production.example.test"),
            self.assertRaises(CommandError),
        ):
            seed.guard_environment()


class VisibleText(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.parts = []
        self.feed(text)

    def handle_data(self, data):
        self.parts.append(data)


class SourcingContextLanguageTests(ConnectedJourneyFixture, TestCase):
    def test_bound_comparison_uses_business_label_and_keeps_foreign_scope_denied(self):
        self.begin()
        self.open_quotes_and_compare()
        self.login(self.owner)
        path = action_url(self.rfq, "prepare_award", comparison=self.comparison.pk)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        visible = " ".join(VisibleText(response.content.decode()).parts)
        self.assertIn("مقایسه:", visible)
        self.assertNotIn("comparison:", visible)
        self.login(self.outsider)
        self.assertIn(self.client.get(path).status_code, (403, 404))
        self.login(self.owner)
        award = self.award()
        order = self.order_from(award, self.supplier)
        print_response = self.client.get(
            reverse("procurement:order_detail", args=[order.pk]) + "?format=print"
        )
        self.assertContains(print_response, "ارز پیشنهاد مبنا")
        self.assertContains(print_response, "IRR")


class DailyReportLeakageTests(ReceiptJourneyFixture, TestCase):
    def test_report_identity_uses_business_context_without_uuid_disclosure(self):
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="MVP08-SCOPE",
            name="کارگاه آزمایشی",
        )
        report = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=site,
            reporting_date=date(2026, 11, 3),
            work_performed="عملیات نمونه",
            created_by=self.owner,
        )
        self.login(self.owner)
        response = self.client.get(reverse("daily_reports:detail", args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        visible = " ".join(VisibleText(response.content.decode()).parts)
        self.assertNotIn("شناسه فنی", visible)
        self.assertNotIn(str(report.pk), visible)
        self.assertIn(self.project.name, visible)
        self.assertIn(site.name, visible)


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class ProcurementOutputBrowserTests(
    print_fixture.OperationalPrintFixture, StaticLiveServerTestCase
):
    serialized_rollback = True
    _fixture_teardown = chrome.ContractBillingBrowserTests._fixture_teardown

    def test_current_po_grn_print_and_positive_stock_download(self):
        # Independent OUTPUT regression fixture, not Journey 3 acceptance.
        # No sourcing bypass is claimed as a substitute for the blocked journey.
        order, receipt, _, _ = self.sources()
        self.assertEqual(self.post(receipt).status_code, 302)
        from apps.inventory.test_mvp04e import InventoryJourneyFixture

        source = receipt.items.get()
        data = InventoryJourneyFixture.stock_payload(self, source)
        response = self.client.post(
            reverse("inventory:transaction_create")
            + f"?goods_receipt_item={source.pk}",
            data,
        )
        self.assertEqual(response.status_code, 302)
        from apps.inventory.models import StockTransaction

        record = StockTransaction.objects.get(transaction_number="IN-001")
        self.assertEqual(
            self.client.post(
                reverse("inventory:transaction_post", args=[record.pk])
            ).status_code,
            302,
        )
        self.login(self.owner)
        env = os.environ.copy()
        env["MVP07_SESSION"] = self.client.cookies["sessionid"].value
        env["MVP07_SCENARIOS"] = json.dumps(
            [
                {"name": "positive-po", "path": reverse("procurement:order_list")},
                {
                    "name": "positive-inventory",
                    "path": reverse("inventory:transaction_list"),
                },
            ]
        )
        directory = OUTPUT_ROOT / "positive-output-regression"
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/mvp07_browser.mjs"),
                self.live_server_url,
                str(directory),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf8",
            timeout=180,
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stderr + result.stdout)[-2200:])
        for case in json.loads(result.stdout):
            for download in case["downloads"]:
                book = load_workbook(download["filename"])
                self.assertTrue(book.active.sheet_view.rightToLeft)
                self.assertGreater(book.active.max_row, 1)
                self.assertFalse(
                    any(
                        c.data_type == "f"
                        for sheet in book
                        for row in sheet
                        for c in row
                    )
                )
        env["MVP06_SESSION"] = env["MVP07_SESSION"]
        env["MVP06_SCENARIOS"] = json.dumps(
            [
                {
                    "name": "po",
                    "path": reverse("procurement:order_detail", args=[order.pk]),
                },
                {
                    "name": "grn",
                    "path": reverse("procurement:receipt_detail", args=[receipt.pk]),
                },
            ]
        )
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/mvp06_browser.mjs"),
                self.live_server_url,
                str(OUTPUT_ROOT / "print-procurement"),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf8",
            timeout=180,
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stderr + result.stdout)[-2200:])
