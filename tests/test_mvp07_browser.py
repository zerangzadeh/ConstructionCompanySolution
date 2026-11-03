"""Installed Chrome: P1 downloads, bounded before/after UX and foundations."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from openpyxl import load_workbook

from apps.billing import test_mvp03_browser as cleanup
from core.jalali import format_jalali
from tests import test_f3_module_selector as modules
from tests import test_f4_frontend_conformance as foundation
from tests.test_mvp07_xlsx import DAY, P1Fixture

ROOT = Path(__file__).resolve().parents[1]


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class P1ChromeTests(P1Fixture, StaticLiveServerTestCase):
    serialized_rollback = True
    _fixture_teardown = cleanup.ContractBillingBrowserTests._fixture_teardown

    def test_downloads_all_targets_and_allocation_date_presentation(self):
        phase = os.environ.get("MVP07_UX_PHASE", "after")
        scenarios = []
        for width in (1440, 1024, 390):
            for index, route in enumerate(self.routes()):
                if phase in ("before", "usability") and index != 4:
                    continue
                case = {
                    "name": f"surface-{index}-{width}",
                    "path": route,
                    "width": width,
                }
                if phase in ("before", "usability"):
                    case.update(observeOnly=True)
                if index == 4:
                    # Existing global date presentation already converts this.
                    case.update(
                        contains=format_jalali(DAY),
                        excludes="2026",
                        headerCheck="before" if phase == "before" else "after",
                    )
                scenarios.append(case)
            for index in (3, 4):
                scenarios.append(
                    {
                        "name": f"empty-{index}-{width}",
                        "path": self.routes()[index] + "?equipment=NOTFOUND",
                        "width": width,
                        "observeOnly": True,
                        "clearFilters": phase != "before",
                        "contains": "ثبت نشده است"
                        if phase == "before"
                        else "نتیجه‌ای با این فیلترها یافت نشد",
                    }
                )
        self.login(self.owner)
        env = {
            **os.environ,
            "MVP07_SESSION": self.client.cookies["sessionid"].value,
            "MVP07_SCENARIOS": json.dumps(scenarios),
        }
        directory = ROOT / "output/mvp-07/browser" / phase
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
            encoding="utf-8",
            timeout=240,
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-5000:])
        results = json.loads(result.stdout)
        checks = []
        for case in results:
            for file in case["downloads"]:
                workbook = load_workbook(file["filename"])
                self.assertTrue(all(s.sheet_view.rightToLeft for s in workbook))
                self.assertTrue(
                    all(c.data_type != "f" for s in workbook for row in s for c in row)
                )
                self.assertGreater(workbook.active.max_row, 1)
                checks.append(
                    {
                        "filename": file["filename"],
                        "sheets": workbook.sheetnames,
                        "rows": [s.max_row - 1 for s in workbook],
                        "rtl": True,
                        "formulas": 0,
                    }
                )
                workbook.close()
        (directory / "workbook-integrity.json").write_text(
            json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
        )


class EvidenceRoot:
    def __truediv__(self, relative):
        return ROOT / (
            "output/mvp-07/f4" if relative == "output/f4/browser" else relative
        )


class CurrentFoundationTests(foundation.SharedFrontendConformanceTests):
    def test_shared_frontend_together_at_both_widths_offline(self):
        with patch.object(foundation, "ROOT", EvidenceRoot()):
            super().test_shared_frontend_together_at_both_widths_offline()


class CurrentModuleSelectorTests(modules.ModuleSelectorBrowserTests):
    def test_four_representative_routes_and_restricted_membership_offline(self):
        with patch.dict(
            os.environ,
            {
                "MODULE_SELECTOR_EVIDENCE_DIRECTORY": str(
                    ROOT / "output/mvp-07/after-module-selector"
                )
            },
        ):
            super().test_four_representative_routes_and_restricted_membership_offline()
