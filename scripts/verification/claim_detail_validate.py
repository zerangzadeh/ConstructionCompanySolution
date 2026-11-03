"""Focused claim-detail visual verification on an isolated PostgreSQL database."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ["BONIRA_BROWSER_LOCAL_ONLY"] = "1"
import django

django.setup()
from django.db import connections

connections["default"].settings_dict["TEST"]["NAME"] = (
    "test_bonira_claim_detail_ui_20261103"
)
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ClaimDetailVisualChecks(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    browser_evidence_directory = ROOT / "output/claim-detail-ui/browser"

    def _fixture_teardown(self):
        # Match the repository's retained Payment FK cleanup policy. This may
        # only flush the dedicated disposable database owned by this runner.
        for alias in self._databases_names(include_mirrors=False):
            if (
                connections[alias].settings_dict["NAME"]
                != "test_bonira_claim_detail_ui_20261103"
            ):
                raise RuntimeError(
                    "Claim detail cleanup requires its dedicated test DB"
                )
            call_command(
                "flush",
                database=alias,
                interactive=False,
                verbosity=0,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )

    def test_claim_detail_responsive_actions_and_navigation(self):
        self.make_fixture(persian=True)
        self.project.name = "بازسازی کارخانه نمونه"
        self.project.save()
        claim = self._claim()
        detail = reverse("billing:claim_detail", args=[claim.pk])
        geometry = "document.documentElement.scrollWidth<=innerWidth+1 && document.querySelectorAll('main h1').length===1 && [...document.querySelectorAll('main .erp-btn')].every(e=>e.getBoundingClientRect().width>0)"
        scenarios = []
        for width in (1440, 1024, 390, 320):
            scenarios.append(
                {
                    "name": f"claim-draft-{width}",
                    "path": detail,
                    "width": width,
                    "mobile": width < 640,
                    "status": 200,
                    "screenshot": True,
                    "bottomScreenshot": True,
                    "noJsErrors": True,
                    "noHttpErrors": True,
                    "mustText": [
                        "ناخالص کارکرد این دوره",
                        "خالص اضافات و کسور این دوره",
                        "آخرین به‌روزرسانی نسخه",
                    ],
                    "steps": [
                        {
                            "inspect": geometry,
                            "description": "RTL page fits viewport with visible actions",
                        }
                    ],
                }
            )
        scenarios.append(
            {
                "name": "claim-draft-no-js",
                "path": detail,
                "width": 390,
                "mobile": True,
                "noJS": True,
                "status": 200,
                "screenshot": True,
                "steps": [
                    {
                        "inspect": geometry,
                        "description": "native links/forms remain available without JS",
                    }
                ],
            }
        )
        scenarios.append(
            {
                "name": "claim-actions",
                "path": detail,
                "status": 200,
                "screenshot": True,
                "steps": [
                    {
                        "clickSelector": "form[action$='/recalculate/'] button",
                        "afterPath": detail,
                        "mustText": "مقادیر و کسور پیش‌نویس به‌روز شد",
                    },
                    {
                        "clickSelector": "form[action$='/submit/'] button",
                        "afterPath": detail,
                        "mustText": "صورت‌وضعیت برای بررسی ارسال شد",
                    },
                    {
                        "inspect": "!document.querySelector(\"form[action$='/recalculate/']\")",
                        "description": "submitted version has no recalculation control",
                    },
                ],
            }
        )
        self.browser(self.owner, scenarios)
        claim.refresh_from_db()
        self.assertEqual(claim.status, "submitted")
        self.browser(
            self.manager,
            [
                {
                    "name": "claim-approval",
                    "path": detail,
                    "status": 200,
                    "screenshot": True,
                    "steps": [
                        {
                            "fill": {"reason": "بازبینی مستقل داده‌های آزمایشی"},
                            "submit": True,
                            "formSelector": "form[action$='/approve/']",
                            "afterPath": detail,
                            "mustText": "این نسخه تأیید و نهایی شده",
                        }
                    ],
                },
                {
                    "name": "claim-approved-mobile",
                    "path": detail,
                    "status": 200,
                    "width": 390,
                    "mobile": True,
                    "screenshot": True,
                    "steps": [
                        {
                            "inspect": geometry,
                            "description": "approved page fits mobile viewport",
                        }
                    ],
                },
            ],
        )
        claim.refresh_from_db()
        self.assertEqual(claim.status, "approved")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "--create-db", "-q", "--tb=short"]))
