"""Optional bundled-browser qualification against a disposable local test server."""

import os
import subprocess
from pathlib import Path
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from .closing_models import FiscalYearClosing
from .test_fiscal_year_closing import YearEndFixture


@skipUnless(os.environ.get("BONIRA_QA_NODE"), "Bundled browser runtime not selected")
class FiscalYearClosingBrowserTests(YearEndFixture, StaticLiveServerTestCase):
    def test_persian_maker_checker_reconciliation_and_reopen_in_browser(self):
        self._activity()
        self._period_close()
        for user, name in (
            (self.owner, "تهیه‌کننده آزمون"),
            (self.reviewer, "بررسی‌کننده مستقل"),
            (self.reopener, "تأییدکننده بازگشایی"),
        ):
            user.first_name = name
            user.save(update_fields=["first_name"])
        root = Path(__file__).resolve().parents[2]
        environment = os.environ.copy()
        environment.update(
            {
                "BONIRA_QA_URL": self.live_server_url,
                "BONIRA_QA_MAKER": self._client(self.owner).cookies["sessionid"].value,
                "BONIRA_QA_CHECKER": self._client(self.reviewer)
                .cookies["sessionid"]
                .value,
                "BONIRA_QA_REOPENER": self._client(self.reopener)
                .cookies["sessionid"]
                .value,
                "BONIRA_QA_SOURCE": str(self.year.pk),
                "BONIRA_QA_TARGET": str(self.target.pk),
                "BONIRA_QA_REQUESTER": str(self.owner_membership.pk),
                "BONIRA_QA_OUTPUT": str(root / "docs/validation/fiscal-year-closing"),
            }
        )
        result = subprocess.run(
            [
                environment["BONIRA_QA_NODE"],
                str(root / "scripts/qualify_fiscal_year_closing.cjs"),
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        closing = FiscalYearClosing.objects.get()
        self.assertEqual(closing.status, "reversed")
        self.assertEqual(closing.reconciliation["opening_status"], "PASS")
        self.assertEqual(closing.reconciliation["reversal_status"], "PASS")
        import json

        evidence = {
            "environment": "disposable local Development PostgreSQL test server",
            "status": "PASS",
            "annual_result": str(closing.annual_result),
            "source_snapshot_hash": closing.source_snapshot["hash"],
            "final_snapshot_hash": closing.final_snapshot["hash"],
            "reconciliation": closing.reconciliation,
            "source_closing_journal": str(closing.closing_journal_id),
            "target_opening_journal": str(closing.opening_journal_id),
            "closing_reversal": str(closing.closing_reversal_id),
            "opening_reversal": str(closing.opening_reversal_id),
            "final_permanent_balances": closing.final_snapshot["balances"],
            "transition_count": closing.events.count(),
        }
        (
            root / "docs/validation/fiscal-year-closing/accounting-qualification.json"
        ).write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )
