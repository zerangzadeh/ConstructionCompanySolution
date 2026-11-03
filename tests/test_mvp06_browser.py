"""Real Chrome renders all five outputs and long table continuation to A4."""

import json
import os
import re
import shutil
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as billing_browser
from apps.billing.test_mvp03 import JourneyFixture
from apps.procurement import services as purchasing
from tests.test_mvp06_print import OperationalPrintFixture

ROOT = Path(__file__).resolve().parents[1]


class PrintBrowserMixin:
    serialized_rollback = True
    _fixture_teardown = billing_browser.ContractBillingBrowserTests._fixture_teardown

    def renders(self, name, scenarios):
        self.login(self.owner)
        env = os.environ.copy()
        env["MVP06_SESSION"] = self.client.cookies["sessionid"].value
        env["MVP06_SCENARIOS"] = json.dumps(scenarios)
        directory = ROOT / "output/mvp-06/browser" / name
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/mvp06_browser.mjs"),
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
        for scenario, rendered in zip(scenarios, results):
            pdf = directory / (scenario["name"] + ".pdf")
            info = subprocess.run(
                [shutil.which("pdfinfo"), str(pdf)],
                capture_output=True,
                text=True,
                encoding="utf8",
                check=True,
            ).stdout
            (directory / (scenario["name"] + "-pdfinfo.txt")).write_text(
                info, encoding="utf8"
            )
            pages = int(re.search(r"Pages:\s+(\d+)", info)[1])
            size = re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts \(A4\)", info)
            self.assertIsNotNone(size)
            self.assertAlmostEqual(float(size[1]), 595.28, delta=1)
            self.assertAlmostEqual(float(size[2]), 841.89, delta=1)
            self.assertGreater(pages, 0)
            if scenario.get("multi"):
                self.assertGreater(pages, 1)
            if scenario.get("one"):
                self.assertEqual(pages, 1)
            rendered["pages"] = pages
            # Native Poppler renders every page, so visual acceptance is based on
            # actual pagination, not a continuous browser screenshot.
            subprocess.run(
                [
                    shutil.which("pdftoppm"),
                    "-scale-to",
                    "1400",
                    "-png",
                    str(pdf),
                    str(directory / scenario["name"]),
                ],
                check=True,
                capture_output=True,
                timeout=90,
            )
        (directory / "verification.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf8"
        )


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class BillingPrintBrowserTests(
    PrintBrowserMixin, JourneyFixture, StaticLiveServerTestCase
):
    def test_claim_print_media(self):
        self.make_fixture(persian=True)
        self.organization.name = "شرکت پیمانکاری سازه نمونه"
        self.organization.save(update_fields=["name"])
        self.project.name = "پروژه مجتمع نمونه"
        self.project.save(update_fields=["name"])
        self.manager.first_name = "بازبین"
        self.manager.last_name = "نمونه"
        self.manager.save(update_fields=["first_name", "last_name"])
        from apps.billing import services as billing
        from apps.contracts.services import (
            approve_contract_term_version,
            create_contract_term_version,
        )

        term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 9, 1),
            reason="Synthetic print fixture only",
            insurance_classification=self.insurance_classification,
            retention_rate=Decimal(10),
            retention_cap=Decimal(12),
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=term,
            reason="Independent synthetic print fixture review",
        )
        claim = self._claim()
        billing.submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        billing.approve_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=claim,
            reason="تأیید مستقل نمونه",
        )
        self.renders(
            "billing",
            [
                {
                    "name": "claim-one-page",
                    "path": reverse("billing:claim_detail", args=[claim.pk]),
                    "one": True,
                }
            ],
        )
        baseline = self._baseline(total=Decimal(84))
        for i in range(36):
            billing.add_baseline_item(
                organization=self.organization,
                actor=self.owner,
                baseline=baseline,
                line_key=f"LONG-{i:03d}",
                description=f"عملیات آرماتوربندی و اجرای سازه قطعه {i + 1} بر اساس نقشه‌های مصوب کارگاه با توضیح تکمیلی فارسی",
                unit="متر مکعب",
                planned_quantity=Decimal(1),
                unit_rate=Decimal(1),
                sort_order=i + 1,
            )
        billing.request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=baseline
        )
        baseline = billing.approve_project_baseline(
            organization=self.organization,
            actor=self.manager,
            baseline=baseline,
            reason="مبنای نمونه تأیید شد",
        )
        for item in baseline.items.all():
            record = billing.create_progress_record(
                organization=self.organization,
                actor=self.owner,
                baseline=baseline,
                baseline_item=item,
                period_start=date(2026, 10, 1),
                period_end=date(2026, 10, 31),
                measured_on=date(2026, 10, 19),
                source_type="site_report",
                source_reference="DR-PRINT",
                period_quantity=Decimal("0.5"),
                cumulative_quantity=Decimal(1)
                if item.line_key == "ITEM-01"
                else Decimal("0.5"),
                evidence="Synthetic signed site report",
            )
            billing.request_progress_verification(
                organization=self.organization, actor=self.owner, record=record
            )
            billing.verify_progress_record(
                organization=self.organization,
                actor=self.manager,
                record=record,
                reason="کنترل اندازه‌گیری نمونه",
            )
        long_claim = billing.create_progress_claim(
            organization=self.organization,
            actor=self.owner,
            baseline=baseline,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            measurement_cutoff=date(2026, 10, 31),
        )
        self.renders(
            "billing-long",
            [
                {
                    "name": "claim-multi-page",
                    "path": reverse("billing:claim_detail", args=[long_claim.pk]),
                    "multi": True,
                }
            ],
        )


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class OperationalPrintBrowserTests(
    PrintBrowserMixin, OperationalPrintFixture, StaticLiveServerTestCase
):
    def test_four_outputs_and_multi_page_tables(self):
        sources = self.sources()
        _order, _receipt, report, _expense = sources
        scenarios = [
            {"name": name, "path": path, "mobile": index % 2 == 1}
            for index, (name, path) in enumerate(
                zip(
                    [
                        "po-one-page",
                        "grn-one-page",
                        "daily-one-page",
                        "expenses-one-page",
                    ],
                    self.routes(sources),
                )
            )
        ]
        scenarios[0]["one"] = True
        scenarios[1]["one"] = True
        scenarios[2]["one"] = True
        scenarios[3]["one"] = True
        self.renders("operational", scenarios)
        long_order, first = self.make_order(number="PO-LONG", issued=False)
        lines = [first]
        for i in range(72):
            lines.append(
                purchasing.add_purchase_order_item(
                    organization=self.organization,
                    actor=self.owner,
                    purchase_order=long_order,
                    material=self.material,
                    description=f"اجرای قطعه {i + 1} با مشخصات سفارش خرید و توضیح فارسی بلند",
                    quantity=Decimal("1.25"),
                    unit_price=Decimal("1000000.25"),
                    sort_order=i + 1,
                )
            )
        long_order = purchasing.issue_purchase_order(
            organization=self.organization, actor=self.owner, purchase_order=long_order
        )
        long_receipt = self.create_receipt(long_order, number="GRN-LONG")
        for line in lines:
            self.assertEqual(self.add(long_receipt, line, "1").status_code, 302)
        from apps.daily_reports.services import add_daily_activity
        from apps.expenses.services import create_expense

        for i in range(60):
            add_daily_activity(
                organization=self.organization,
                report_id=str(report.pk),
                actor=self.owner,
                description=f"عملیات روزانه کارگاه بخش {i + 1}؛ شرح فعالیت ثبت‌شده",
                notes="بازدید و کنترل اجرا",
            )
            create_expense(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                description=f"حمل مصالح بخش {i + 1} به کارگاه با شرح بلند برای کنترل چاپ",
                amount=Decimal("1234567.89"),
                incurred_on=date(2026, 11, 3),
                receipt_reference=f"REC-{i:03d}",
            )
        self.renders(
            "long",
            [
                {
                    "name": "po-multi-page",
                    "path": reverse("procurement:order_detail", args=[long_order.pk]),
                    "multi": True,
                },
                {
                    "name": "grn-multi-page",
                    "path": reverse(
                        "procurement:receipt_detail", args=[long_receipt.pk]
                    ),
                    "multi": True,
                },
                {
                    "name": "daily-multi-page",
                    "path": reverse("daily_reports:detail", args=[report.pk]),
                    "multi": True,
                },
                {
                    "name": "expenses-multi-page",
                    "path": reverse("expenses:list"),
                    "multi": True,
                },
            ],
        )
