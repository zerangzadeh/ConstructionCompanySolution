"""Bounded synthetic screenshots, distinct from production/runtime certification."""

import json
import os
import subprocess
from pathlib import Path
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from apps.fixed_assets.test_cep045_workspace import WorkspaceFixture, explicit_reader
from apps.organizations.models import BusinessPermissionCode as P


@skipUnless(
    os.getenv("BONIRA_CEP045_SCREENSHOTS"), "Explicit local screenshot run only"
)
class WorkspaceBrowserTests(WorkspaceFixture, StaticLiveServerTestCase):
    def probe(self, cases):
        root = Path(__file__).resolve().parents[1]
        output = root / "docs/governance/cep/evidence/CEP-045_SCREENSHOTS"
        result = subprocess.run(
            [
                "node",
                str(root / "docs/governance/cep/evidence/CEP-045_BROWSER_PROBE.mjs"),
                self.live_server_url,
                json.dumps(cases),
                str(output),
            ],
            env={
                **os.environ,
                "CEP045_TEST_SESSION": self.client.cookies["sessionid"].value,
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2500:])
        return json.loads(result.stdout)

    def test_desktop_mobile_empty_linked_compatibility_and_denied_screens(self):
        self.link()
        cases = [
            {"name": "home-canonical", "path": "/", "status": 200, "home": True},
            {
                "name": "equipment-desktop",
                "path": reverse("equipment:operations_workbench"),
                "workspace": "WS-15A",
                "status": 200,
            },
            {
                "name": "equipment-mobile",
                "path": reverse("equipment:operations_workbench"),
                "workspace": "WS-15A",
                "status": 200,
                "mobile": True,
            },
            {
                "name": "equipment-link",
                "path": reverse("equipment:detail", args=[self.equipment.pk]),
                "workspace": "WS-15A",
                "status": 200,
            },
            {
                "name": "fixed-assets-desktop",
                "path": reverse("fixed_assets:workbench"),
                "workspace": "WS-15B",
                "status": 200,
            },
            {
                "name": "asset-source-detail",
                "path": reverse("fixed_assets:asset_detail", args=[self.asset.pk]),
                "workspace": "WS-15B",
                "status": 200,
            },
            {
                "name": "compatibility-financials",
                "path": reverse("financials:dashboard"),
                "status": 200,
                "authorities": True,
            },
        ]
        observations = self.probe(cases)
        denied, _, _ = explicit_reader(
            self.organization, "cep045-denied", [P.EQUIPMENT_VIEW]
        )
        self.client.force_login(denied)
        observations += self.probe(
            [
                {
                    "name": "unauthorized-fixed-asset",
                    "path": reverse("fixed_assets:asset_detail", args=[self.asset.pk]),
                    "status": 403,
                }
            ]
        )
        root = Path(__file__).resolve().parents[1]
        (
            root / "docs/governance/cep/evidence/CEP-045_BROWSER_OBSERVATIONS.json"
        ).write_text(
            json.dumps(
                {
                    "environment": "Isolated synthetic StaticLiveServer / local Chrome; no production data",
                    "observations": observations,
                    "production_or_runtime_certification": False,
                },
                indent=2,
            )
            + "\n",
            "utf-8",
        )
