"""Actual Chrome checks using a dedicated disposable PostgreSQL database."""

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
    "test_bonira_work_detail_ui_20261103"
)
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.services import reject_progress_record, request_progress_verification
from apps.billing.test_mvp03 import JourneyFixture


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WorkDetailVisualChecks(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    browser_evidence_directory = ROOT / "output/work-record-detail-ui/browser"

    def setUp(self):
        from apps.organizations.catalog_bootstrap import (
            synchronize_authorization_catalog,
        )

        synchronize_authorization_catalog(using="default")

    def _fixture_teardown(self):
        for alias in self._databases_names(include_mirrors=False):
            if (
                connections[alias].settings_dict["NAME"]
                != "test_bonira_work_detail_ui_20261103"
            ):
                raise RuntimeError("Cleanup requires the dedicated work detail test DB")
            call_command(
                "flush",
                database=alias,
                interactive=False,
                verbosity=0,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )

    def test_render_and_navigation(self):
        self.make_fixture(persian=True)
        record = self._verified_record()
        detail = reverse("billing:progress_detail", args=[record.pk])
        geometry = "document.documentElement.scrollWidth<=innerWidth+1 && getComputedStyle(document.querySelector('main')).direction==='rtl' && document.querySelectorAll('main h1').length===1"
        scenarios = []
        for width in (1440, 1024, 390, 320):
            scenarios.append(
                {
                    "name": f"work-verified-{width}",
                    "path": detail,
                    "width": width,
                    "height": 1000,
                    "mobile": width < 640,
                    "status": 200,
                    "screenshot": True,
                    "bottomScreenshot": True,
                    "noJsErrors": True,
                    "noHttpErrors": True,
                    "mustText": [
                        "کارکرد این ثبت",
                        "کارکرد تجمعی تا این ثبت",
                        "نتیجه بررسی",
                    ],
                    "steps": [
                        {
                            "inspect": geometry,
                            "description": "RTL geometry and one page title",
                        },
                        {"toggleSelector": ".measurement-source summary"},
                        {
                            "inspect": "document.querySelector('.measurement-source').open && document.querySelector('.measurement-source').innerText.includes('DR-001')",
                            "description": "Stored evidence is accessible",
                        },
                    ],
                }
            )
        scenarios.append(
            {
                "name": "work-history-return",
                "path": detail,
                "status": 200,
                "steps": [
                    {
                        "clickSelector": ".measurement-detail-heading > a",
                        "afterPath": reverse("billing:progress_list"),
                    },
                    {
                        "inspect": f"new URLSearchParams(location.search).get('contract')==='{self.contract.pk}' && new URLSearchParams(location.search).get('line_key')==='ITEM-01'",
                        "description": "Return retains exact contract and line",
                    },
                ],
            }
        )
        self.browser(self.owner, scenarios)

    def test_pending_rejected(self):
        self.make_fixture(persian=True)
        record = self._record()
        detail = reverse("billing:progress_detail", args=[record.pk])
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        self.browser(
            self.manager,
            [
                {
                    "name": "work-pending-390",
                    "path": detail,
                    "status": 200,
                    "width": 390,
                    "mobile": True,
                    "screenshot": True,
                    "mustText": ["در انتظار بررسی"],
                    "steps": [
                        {
                            "inspect": "!!document.querySelector('#progress-verify-reason')",
                            "description": "Existing decision forms remain available",
                        }
                    ],
                }
            ],
        )
        reject_progress_record(
            organization=self.organization,
            actor=self.manager,
            record=record,
            reason="بررسی مدرک DR-001 نیاز به اصلاح دارد",
        )
        self.browser(
            self.owner,
            [
                {
                    "name": "work-rejected-1440",
                    "path": detail,
                    "status": 200,
                    "screenshot": True,
                    "mustText": ["دلیل رد", "بررسی مدرک DR-001 نیاز به اصلاح دارد"],
                }
            ],
        )


if __name__ == "__main__":
    import pytest

    raise SystemExit(
        pytest.main([__file__, "--reuse-db", "-q", "--tb=short", *sys.argv[1:]])
    )
