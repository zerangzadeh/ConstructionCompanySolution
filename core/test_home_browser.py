"""Optional local Chrome runtime check for CEP-002 responsive Home states."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from apps.accounts.models import User
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
)


class HomeBrowserTests(StaticLiveServerTestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="cep002-browser", password="test")
        self.organization = create_organization_with_owner(
            owner=self.user, name="Browser Test Company", slug="cep002-browser"
        )
        self.client.force_login(self.user)

    def _probe(self, state: str) -> None:
        root = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        env["CEP002_TEST_SESSION"] = self.client.cookies["sessionid"].value
        result = subprocess.run(
            [
                "node",
                str(root / "output" / "cep-002" / "browser_probe.mjs"),
                f"{self.live_server_url}/",
                state,
                str(root / "output" / "cep-002" / "browser"),
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        for size in json.loads(result.stdout):
            self.assertEqual(size["state"], state)
            self.assertEqual(size["lang"], "fa")
            self.assertEqual(size["dir"], "rtl")
            self.assertLessEqual(size["scroll"], size["viewport"] + 1)
            self.assertTrue(size["profile"])
            self.assertTrue(size["mobileNav"])
            if size["label"] == "mobile":
                self.assertTrue(size["mobileNavOpens"])
            if state == "normal":
                self.assertGreater(size["homeLinks"], 0)
                self.assertTrue(size["financialLink"])
            if state in {"empty", "no_context", "unauthorized"}:
                self.assertFalse(size["testOrgVisible"])

    def test_normal_and_safe_states_at_desktop_and_mobile_widths(self) -> None:
        self._probe("normal")
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = (
            "00000000-0000-0000-0000-000000000001"
        )
        session.save()
        self.client.cookies["sessionid"] = session.session_key
        self._probe("unauthorized")
        session.pop(ACTIVE_ORGANIZATION_SESSION_KEY, None)
        session.save()
        self.client.cookies["sessionid"] = session.session_key
        create_organization_with_owner(
            owner=self.user, name="Second Browser Company", slug="cep002-browser-two"
        )
        self._probe("no_context")
        with patch(
            "core.views.authorized_home_links", side_effect=RuntimeError("test")
        ):
            session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
            session.save()
            self.client.cookies["sessionid"] = session.session_key
            self._probe("error")
        empty_user = User.objects.create_user(username="cep002-empty")
        self.client.force_login(empty_user)
        self._probe("empty")
