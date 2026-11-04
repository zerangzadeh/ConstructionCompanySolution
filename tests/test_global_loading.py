"""Exercise the real shared shell in installed Chrome, without database writes."""

import os
import subprocess
from pathlib import Path

from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve

from apps.accounts.models import User

ROOT = Path(__file__).resolve().parents[1]


class GlobalLoadingBrowserTests(SimpleTestCase):
    def test_shared_shell_loading_lifecycle(self):
        request = RequestFactory().get("/")
        request.user = User(
            username="visual-fixture", first_name="کاربر", last_name="آزمایشی"
        )
        request.organization = None
        request.resolver_match = resolve("/")
        shell = get_template("base.html").render(
            {"request": request, "product_navigation_groups": []}
        )
        output = ROOT / "output/global-loading"
        output.mkdir(parents=True, exist_ok=True)
        (output / "shell.html").write_text(shell, encoding="utf-8")
        self.addCleanup((output / "shell.html").unlink, missing_ok=True)
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/global_loading_browser.mjs"),
                str(output),
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-5000:])
