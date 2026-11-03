"""Installed Chrome proof against a real Django server and disposable PostgreSQL."""

import json
import os
import subprocess
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.billing import test_mvp03_browser as browser_fixture
from apps.materials.models import Material, UnitCategory, UnitOfMeasure
from apps.organizations.models import MembershipScopeGrant
from apps.organizations.services import set_active_organization
from apps.procurement.commercial_scope_services import define_rfq_commercial_scope
from apps.procurement.rfq_services import add_rfq_line, create_rfq, submit_rfq_for_issue
from apps.procurement.services import (
    add_purchase_request_item,
    approve_purchase_request,
    submit_purchase_request,
)
from apps.procurement.test_mvp04a import RequestJourneyFixture
from apps.projects.models import Project

ROOT = Path(__file__).resolve().parents[1]


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RFQConfigurationBrowserTests(RequestJourneyFixture, StaticLiveServerTestCase):
    serialized_rollback = True
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_configuration_journey_responsive_offline_and_boundaries(self):
        for record, name in (
            (self.organization, "شرکت ساختمانی نمونه"),
            (self.project, "بازسازی کارخانه نوآوران"),
            (self.supplier, "تأمین‌کننده نمونه"),
        ):
            field = "display_name" if record == self.supplier else "name"
            setattr(record, field, name)
            record.save(update_fields=[field])
        kg = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="KG-UX",
            name="کیلوگرم",
            symbol="kg",
            category=UnitCategory.WEIGHT,
        )
        self.unit.name = "متر مکعب"
        self.unit.save(update_fields=["name"])
        materials = [self.material]
        self.material.name = "بتن آماده رده C30"
        self.material.save(update_fields=["name"])
        for index, name in enumerate(("میلگرد آجدار شاخه‌ای", "سیم مفتول")):
            materials.append(
                Material.objects.create(
                    organization=self.organization,
                    code=f"UX-{index}",
                    name=name,
                    unit_of_measure=kg,
                )
            )
        quantities = [Decimal(120), Decimal(8500), Decimal(500)]
        records = {}
        scenarios = []

        def make(name, kind, width, *, count=3, saved=False, actor="owner"):
            pr = self.draft(f"PR-UX-{name}")
            items = [
                add_purchase_request_item(
                    organization=self.organization,
                    actor=self.member,
                    purchase_request=pr,
                    material=material,
                    quantity=quantities[index],
                )
                for index, material in enumerate(materials[:count])
            ]
            submit_purchase_request(
                organization=self.organization, actor=self.member, purchase_request=pr
            )
            approve_purchase_request(
                organization=self.organization,
                actor=self.owner,
                purchase_request=pr,
                reason="نیاز پروژه بررسی شد",
            )
            when = timezone.now() + timedelta(days=5)
            rfq = create_rfq(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                purchase_request=pr,
                rfq_number=f"RFQ-UX-{name}",
                title="استعلام تأمین مصالح فونداسیون",
                closing_at=when,
                earliest_opening_at=when,
            )
            for item in items:
                add_rfq_line(
                    organization=self.organization,
                    actor=self.owner,
                    rfq=rfq,
                    purchase_request_item=item,
                    quantity=item.quantity,
                )
            if saved:
                define_rfq_commercial_scope(
                    organization=self.organization,
                    actor=self.owner,
                    rfq=rfq,
                    version_number=1,
                    expected_revision=0,
                    idempotency_key="saved",
                    scopes=[
                        {
                            "scope_code": f"خرید {index}",
                            "scope_type": "line",
                            "required_quantity": "5",
                            "unit_of_measure_id": str(item.unit_of_measure_id),
                            "lines": [
                                {
                                    "purchase_request_item_id": str(item.pk),
                                    "quantity": "5",
                                }
                            ],
                            "independently_awardable": True,
                            "allows_split_award": False,
                            "allows_alternates": False,
                        }
                        for index, item in enumerate(items)
                    ],
                )
            if kind == "missing":
                submit_rfq_for_issue(
                    organization=self.organization, actor=self.owner, rfq=rfq
                )
            records[name] = rfq
            scenarios.append(
                {
                    "name": name,
                    "kind": kind,
                    "width": width,
                    "actor": actor,
                    "path": reverse("procurement:rfq_detail", args=[rfq.pk]),
                    "groupPath": reverse("procurement:rfq_scope_define", args=[rfq.pk]),
                    "unit": str(self.unit.pk),
                    "count": count,
                }
            )

        for width in (1440, 1024, 390):
            make(f"normal-{width}", "normal", width)
            make(f"group-{width}", "group", width)
        for name, kind, width in (
            ("single", "normal", 1440),
            ("partial", "partial", 390),
            ("split", "split", 1024),
            ("alternate", "alternate", 1440),
            ("validation", "validation", 390),
            ("saved", "saved", 1440),
            ("issue", "issue", 1440),
            ("missing", "missing", 390),
        ):
            make(name, kind, width, count=1, saved=kind == "saved")
        sessions = {}
        for name, actor in (
            ("owner", self.owner),
            ("viewer", self.viewer),
            ("scoped", self.member),
        ):
            self.client = Client()
            self.login(actor)
            sessions[name] = self.client.cookies["sessionid"].value
        membership = self.organization.memberships.get(user=self.member)
        membership.scope_grants.update(revoked_at=timezone.now())
        other = Project.objects.create(
            organization=self.organization, code="OTHER-UX", name="پروژه دیگر"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=other,
            reason="test",
        )
        self.client = Client()
        self.client.force_login(self.outsider)
        session = self.client.session
        set_active_organization(session, self.other_organization)
        session.save()
        sessions["outsider"] = self.client.cookies["sessionid"].value
        for actor in ("viewer", "scoped", "outsider"):
            scenarios.append(
                {
                    "name": actor,
                    "kind": "readonly" if actor == "viewer" else "denied",
                    "width": 390,
                    "actor": actor,
                    "path": reverse(
                        "procurement:rfq_detail", args=[records["single"].pk]
                    ),
                }
            )
        output = ROOT / "output/mvp-04b-ux/browser"
        output.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(
            RFQ_UX_SCENARIOS=json.dumps(scenarios), RFQ_UX_SESSIONS=json.dumps(sessions)
        )
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/rfq_configuration_browser.mjs"),
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
        self.assertEqual(json.loads(result.stdout)["pages"], len(scenarios))
        for scenario in scenarios:
            if scenario["name"] not in records:
                continue
            rfq = records[scenario["name"]]
            rfq.refresh_from_db()
            if scenario["kind"] == "missing":
                self.assertFalse(rfq.scope_definitions.exists())
                self.assertFalse(rfq.versions.exists())
                self.assertEqual(rfq.status, "submitted_for_issue")
                continue
            definition = rfq.scope_definitions.order_by("-revision_number").first()
            self.assertIsNotNone(definition)
            entries = definition.payload["scopes"]
            if scenario["kind"] == "group":
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["scope_type"], "lot")
                self.assertEqual(len(entries[0]["lines"]), 3)
                self.assertEqual(entries[0]["required_quantity"], "1.0000")
                self.assertEqual(
                    sorted(m["quantity"] for m in entries[0]["lines"]),
                    ["120.0000", "500.0000", "8500.0000"],
                )
                self.assertFalse(entries[0]["independently_awardable"])
                self.assertTrue(entries[0]["allows_split_award"])
                self.assertTrue(entries[0]["allows_alternates"])
            else:
                self.assertEqual(len(entries), scenario["count"])
                self.assertTrue(all(s["scope_type"] == "line" for s in entries))
                self.assertTrue(all(s["independently_awardable"] for s in entries))
                if scenario["kind"] in ("partial", "validation", "saved"):
                    self.assertEqual(entries[0]["required_quantity"], "3.2500")
                if scenario["kind"] == "split":
                    self.assertTrue(entries[0]["allows_split_award"])
                if scenario["kind"] == "alternate":
                    self.assertTrue(entries[0]["allows_alternates"])
            if scenario["kind"] == "saved":
                self.assertEqual(rfq.scope_definitions.count(), 2)
                self.assertEqual(
                    rfq.scope_definitions.get(revision_number=1).payload["scopes"][0][
                        "required_quantity"
                    ],
                    "5.0000",
                )
            if scenario["kind"] == "issue":
                self.assertEqual(rfq.status, "issued")
                version = rfq.versions.get()
                self.assertEqual(version.commercial_scope_definition_id, definition.pk)
                self.assertEqual(version.commercial_scopes.count(), 1)
                self.assertEqual(
                    version.invitations.get().supplier_id, self.supplier.pk
                )
