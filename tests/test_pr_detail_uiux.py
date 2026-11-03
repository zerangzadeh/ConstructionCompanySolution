"""Bounded PR-detail real-Chrome evidence on disposable PostgreSQL data."""

import json
import os
import subprocess
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.billing import test_mvp03_browser as browser_fixture
from apps.organizations.models import MembershipScopeGrant
from apps.procurement.rfq_services import create_rfq
from apps.procurement.services import (
    add_purchase_request_item,
    approve_purchase_request,
    create_purchase_request,
    submit_purchase_request,
)
from apps.procurement.test_mvp04a import RequestJourneyFixture
from apps.projects.models import Project

ROOT = Path(__file__).resolve().parents[1]


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PurchaseRequestDetailVisualTests(RequestJourneyFixture, StaticLiveServerTestCase):
    serialized_rollback = True
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_detail_states_journeys_and_shared_frontend(self):
        for row, name in (
            (self.organization, "شرکت ساختمانی نمونه"),
            (self.project, "اجرای سازه بتنی پروژه نمونه"),
            (self.material, "سیمان پرتلند"),
            (self.unit, "کیسه"),
        ):
            row.name = name
            row.save(update_fields=["name"])
        scenarios, drafts, reviews = [], [], []
        for width in (1440, 1024, 390):
            records = {}
            for state in ("draft", "submitted", "approved"):
                record = create_purchase_request(
                    organization=self.organization,
                    project=self.project,
                    actor=self.owner,
                    request_number=f"PR-UX-{state[:1].upper()}-{width}",
                    title="درخواست تأمین سیمان اجرای فونداسیون",
                    required_by=date(2026, 11, 9),
                )
                add_purchase_request_item(
                    organization=self.organization,
                    actor=self.owner,
                    purchase_request=record,
                    material=self.material,
                    quantity=Decimal("17.25"),
                    description="مصالح موردنیاز اجرای فونداسیون",
                )
                if state != "draft":
                    submit_purchase_request(
                        organization=self.organization,
                        actor=self.owner,
                        purchase_request=record,
                    )
                if state == "approved":
                    approve_purchase_request(
                        organization=self.organization,
                        actor=self.owner,
                        purchase_request=record,
                        reason="نیاز پروژه بررسی شد",
                    )
                    record.refresh_from_db()
                    when = timezone.now() + timedelta(days=5)
                    rfq = create_rfq(
                        organization=self.organization,
                        actor=self.owner,
                        project=self.project,
                        purchase_request=record,
                        rfq_number=f"RFQ-UX-{width}",
                        title="استعلام سیمان فونداسیون",
                        closing_at=when,
                        earliest_opening_at=when,
                    )
                records[state] = record
                self.login(self.owner)
                response = self.client.get(self.url(record))
                self.assertEqual(response.status_code, 200)
                scenarios.append(
                    {
                        "name": f"{state}-{width}",
                        "path": self.url(record),
                        "state": state,
                        "width": width,
                        "actor": "owner",
                        "material": str(self.material.pk),
                        "expectedNavigation": [
                            {"label": link.label, "url": reverse(link.route)}
                            for group in response.context["product_navigation_groups"]
                            for link in group.links
                        ],
                        "rfqPath": reverse("procurement:rfq_detail", args=[rfq.pk])
                        if state == "approved"
                        else "",
                    }
                )
            drafts.append(records["draft"])
            reviews.append(records["submitted"])
        sessions = {}
        for name, actor in (("owner", self.owner), ("viewer", self.viewer)):
            self.client = Client()
            self.login(actor)
            sessions[name] = self.client.cookies["sessionid"].value
        for state, record in records.items():
            scenarios.append(
                {
                    "name": f"viewer-{state}-390",
                    "path": self.url(record),
                    "state": state,
                    "width": 390,
                    "actor": "viewer",
                }
            )
        # Existing HTTP boundary evidence plus real browser denials in both scopes.
        self.client = Client()
        self.login(self.member)
        membership = self.organization.memberships.get(user=self.member)
        MembershipScopeGrant.objects.filter(membership=membership).update(
            revoked_at=timezone.now()
        )
        allowed = Project.objects.create(
            organization=self.organization,
            name="پروژه مجاز دیگر",
            code="UX-OTHER",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=allowed,
            reason="Test",
            source="test_fixture",
        )
        sessions["scoped"] = self.client.cookies["sessionid"].value
        self.client = Client()
        self.client.force_login(self.outsider)
        from apps.organizations.services import set_active_organization

        session = self.client.session
        set_active_organization(session, self.other_organization)
        session.save()
        sessions["outsider"] = self.client.cookies["sessionid"].value
        for actor in ("scoped", "outsider"):
            scenarios.append(
                {
                    "name": f"{actor}-denied",
                    "path": self.url(records["approved"]),
                    "width": 390,
                    "actor": actor,
                    "denied": True,
                }
            )
        output = ROOT / "output/mvp-04a-uiux/browser"
        output.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(
            PR_UIUX_SCENARIOS=json.dumps(scenarios),
            PR_UIUX_SESSIONS=json.dumps(sessions),
        )
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/pr_detail_uiux_browser.mjs"),
                self.live_server_url,
                str(output),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=420,
            check=False,
        )
        (output / "command.txt").write_text(
            f"exit={result.returncode}\n{result.stdout}\n{result.stderr}",
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-6000:])
        self.assertEqual(json.loads(result.stdout)["pages"], 14)
        for record in drafts:
            record.refresh_from_db()
            self.assertEqual(record.status, "approved")
            self.assertEqual(record.items.count(), 2)
            self.assertEqual(
                record.items.order_by("created_at").last().quantity, Decimal("8.5")
            )
        for record in reviews:
            record.refresh_from_db()
            self.assertEqual(record.status, "rejected")
