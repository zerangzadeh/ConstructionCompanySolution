"""Read-model integrity, existing journeys and real Chrome reference validation.

All browser records are synthetic and confined to the isolated PostgreSQL test DB.
"""

import copy
import uuid
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.models import ProgressClaim
from apps.billing.services import approve_progress_claim, submit_progress_claim
from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract, ContractAmendment
from apps.organizations.models import Organization, OrganizationSettings
from apps.projects.models import Project
from apps.projects.test_command_center import scoped_reader


class DetailFixture(JourneyFixture):
    def ready(self):
        self.make_fixture(persian=True)
        self.url = reverse("contracts:detail", args=[self.contract.pk])
        self.login(self.owner)

    def rich(self):
        claim = self._claim()
        submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        approve_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=claim,
            reason="Independent browser fixture review",
        )
        claim.refresh_from_db()
        return claim

    def reader(self):
        return scoped_reader(
            self.organization,
            self.project,
            ["contracts.view"],
            username="contract-reader",
        )[0]


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractDetailTests(DetailFixture, TestCase):
    def setUp(self):
        self.ready()

    def test_exact_gross_amounts_and_currency_authority(self):
        claim = self.rich()
        # Conflicting inert legacy currency must never relabel canonical IRR.
        Organization.objects.filter(pk=self.organization.pk).update(currency="USD")
        response = self.client.get(self.url)
        dashboard = response.context["dashboard"]
        self.assertEqual(dashboard["currency"], claim.currency_code)
        self.assertEqual(dashboard["effective"], Decimal(120))
        self.assertEqual(
            [r["value"] for r in dashboard["segments"]],
            [claim.gross_amount, Decimal(0), Decimal(120) - claim.gross_amount],
        )
        self.assertEqual(dashboard["financial_percent"], Decimal("50.0"))
        self.assertIsNone(dashboard["physical_percent"])
        self.assertContains(response, reverse("billing:claim_detail", args=[claim.pk]))

    def test_draft_and_returned_are_not_in_issued_or_approved(self):
        claim = self._claim()
        for status in ("draft", "returned"):
            ProgressClaim.objects.filter(pk=claim.pk).update(status=status)
            dashboard = self.client.get(self.url).context["dashboard"]
            self.assertEqual(
                [s["value"] for s in dashboard["segments"]],
                [Decimal(0), Decimal(0), Decimal(120)],
            )
            self.assertEqual(dashboard["financial_percent"], Decimal(0))
            # A verified measurement already exists: an absent issued claim
            # must not turn that unknown physical rollup into zero progress.
            self.assertIsNone(dashboard["physical_percent"])

    def test_mixed_currency_corrections_and_invalid_denominator_fail_closed(self):
        claim = self.rich()
        for changes in (
            {"currency_code": "USD"},
            {"currency_code": claim.currency_code, "correction_kind": "replacement"},
        ):
            ProgressClaim.objects.filter(pk=claim.pk).update(**changes)
            self.assertFalse(self.client.get(self.url).context["dashboard"]["segments"])
        ProgressClaim.objects.filter(pk=claim.pk).update(correction_kind="ordinary")
        Contract.objects.filter(pk=self.contract.pk).update(contract_value=Decimal(0))
        ContractAmendment.objects.filter(contract=self.contract).update(status="draft")
        self.assertFalse(self.client.get(self.url).context["dashboard"]["segments"])

    def test_restricted_reader_has_no_claim_amounts_links_or_events(self):
        claim = self.rich()
        self.login(self.reader())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["dashboard"]["billing_records"])
        self.assertFalse(response.context["dashboard"]["segments"])
        self.assertNotContains(
            response, reverse("billing:claim_detail", args=[claim.pk])
        )
        self.assertNotContains(response, "contract-financial-chart")
        self.assertEqual(len(response.context["dashboard"]["recent"]), 1)

    def test_payable_no_receivable_journey_and_cross_tenant_contract_denied(self):
        Contract.objects.filter(pk=self.contract.pk).update(direction="payable")
        response = self.client.get(self.url)
        detail = (
            response.content.decode()
            .split('class="contract-detail"', 1)[1]
            .split("</main>", 1)[0]
        )
        self.assertNotIn("/billing/claims/", detail)
        self.assertNotIn("/billing/baselines/", detail)
        other = Organization.objects.create(name="Other", slug="contract-other")
        project = Project.objects.create(organization=other, name="Other", code="OTHER")
        contract = Contract.objects.create(
            organization=other,
            project=project,
            title="Secret",
            contract_number="OTHER",
            counterparty_name="Hidden",
        )
        self.assertEqual(
            self.client.get(
                reverse("contracts:detail", args=[contract.pk])
            ).status_code,
            404,
        )

    def test_authorized_empty_contracts_render_zero_and_real_remaining(self):
        OrganizationSettings.objects.get_or_create(
            organization=self.organization, defaults={"currency": "IRR"}
        )
        reader = self.reader()
        for direction in ("receivable", "payable"):
            with self.subTest(direction=direction):
                contract = Contract.objects.create(
                    organization=self.organization,
                    project=self.project,
                    contract_number="ZERO-" + direction.upper(),
                    title="قرارداد بدون سابقه",
                    counterparty_name=self.party.display_name,
                    party=self.party,
                    direction=direction,
                    contract_type="subcontract" if direction == "payable" else "client",
                    contract_value=Decimal(300),
                    status="completed",
                )
                url = reverse("contracts:detail", args=[contract.pk])
                response = self.client.get(url)
                dashboard = response.context["dashboard"]
                self.assertEqual(
                    [row["value"] for row in dashboard["segments"]],
                    [Decimal(0), Decimal(0), Decimal(300)],
                )
                self.assertEqual(
                    [row["percent"] for row in dashboard["segments"]],
                    [Decimal(0), Decimal(0), Decimal(100)],
                )
                self.assertEqual(dashboard["financial_percent"], Decimal(0))
                self.assertEqual(dashboard["physical_percent"], Decimal(0))
                self.assertEqual(
                    [row["value"] for row in dashboard["kpis"]],
                    [Decimal(300), Decimal(300), Decimal(0), Decimal(0), Decimal(0)],
                )
                self.assertEqual(dashboard["billing_records"], [])
                self.assertNotContains(response, "در دسترس نیست")
                self.login(reader)
                restricted = self.client.get(url).context["dashboard"]
                self.assertIsNone(restricted["financial_percent"])
                self.assertIsNone(restricted["physical_percent"])
                self.assertIsNone(restricted["billing_records"])
                self.assertFalse(restricted["segments"])
                self.login(self.owner)

    def test_missing_authoritative_currency_does_not_use_legacy_default(self):
        self.rich()
        OrganizationSettings.objects.filter(organization=self.organization).delete()
        response = self.client.get(self.url)
        self.assertFalse(response.context["dashboard"]["segments"])
        self.assertEqual(
            response.context["dashboard"]["currency"], "واحد پول تنظیم نشده"
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractDetailBrowserTests(DetailFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/contract-detail-reference/browser"
    )

    def test_reference_matrix(self):
        self.ready()
        claim = self.rich()
        Organization.objects.filter(pk=self.organization.pk).update(
            name="شرکت نمونه · داده آزمون"
        )
        Project.objects.filter(pk=self.project.pk).update(
            name="مجتمع مسکونی باغستان", code="PRJ-02-01"
        )
        Contract.objects.filter(pk=self.contract.pk).update(
            title="قرارداد اجرای تأسیسات مکانیکی و برقی",
            contract_number="CTR-02-01-04",
            counterparty_name="پیمانکاری تأسیسات نیروی شرق",
            contract_value=Decimal(82000000000),
            signed_at="2026-04-17",
            start_date="2026-04-21",
            end_date="2027-04-20",
        )
        ContractAmendment.objects.filter(contract=self.contract).update(
            value_change=Decimal(-14800000000)
        )
        ProgressClaim.objects.filter(pk=claim.pk).update(
            gross_amount=Decimal(55300000000), net_amount=Decimal(50000000000)
        )
        claim.refresh_from_db()
        # Explicit synthetic rich-data records, never seeded into the application DB.
        for number, state in ((2, "draft"), (3, "submitted")):
            row = copy.copy(claim)
            row.pk = uuid.uuid4()
            row.claim_number = number
            row.status = state
            row.gross_amount = Decimal("800000000.1250")
            row.net_amount = Decimal(700000000)
            row.approved_at = None
            row.submitted_at = None
            row.returned_at = None
            row.returned_revision_id = None
            ProgressClaim.objects.bulk_create([row])
        empty = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            title="قرارداد آغازین",
            contract_number="EMPTY",
            counterparty_name="طرف قرارداد نمونه",
            direction="receivable",
        )
        payable = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            title="قرارداد اجرای تأسیسات مکانیکی و برقی",
            contract_number="PAYABLE-01",
            counterparty_name="پیمانکار تأسیسات نمونه",
            direction="payable",
        )
        base = {
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
            "absentText": ["None", "UUID", "receivable", "payable"],
        }
        inspect = lambda expression, description: {
            "inspect": expression,
            "description": description,
        }
        rich_check = "document.querySelectorAll('.cd-kpi').length===4 && document.querySelectorAll('[data-chart-ready]').length===1 && Chart.getChart('contract-financial-chart').data.datasets[0].data[0]===55300000000 && document.querySelectorAll('.cd-claims tbody tr').length===3 && !document.querySelector('.cd-progress-row:first-of-type progress')"
        scenarios = []
        for mobile in (False, True):
            suffix = "390" if mobile else "1440"
            scenarios.extend(
                [
                    {
                        **base,
                        "name": "rich-" + suffix,
                        "path": self.url,
                        "mobile": mobile,
                        "steps": [
                            inspect(
                                rich_check,
                                "relevant KPIs, exact real gross data, 3 records, no fabricated physical progress",
                            )
                        ],
                    },
                    {
                        **base,
                        "name": "little-" + suffix,
                        "path": reverse("contracts:detail", args=[empty.pk]),
                        "mobile": mobile,
                        "steps": [
                            inspect(
                                "document.querySelectorAll('.cd-kpi').length===4 && !document.querySelector('canvas,progress') && !!document.querySelector('#draft-review')",
                                "draft preparation replaces operational zero charts with readiness",
                            )
                        ],
                    },
                    {
                        **base,
                        "name": "payable-" + suffix,
                        "path": reverse("contracts:detail", args=[payable.pk]),
                        "mobile": mobile,
                        "steps": [
                            inspect(
                                "![...document.querySelectorAll('.contract-detail a')].some(a=>/billing\\/(claims|baselines)/.test(a.href))",
                                "payable excludes receivable journey",
                            )
                        ],
                    },
                ]
            )
        scenarios.append(
            {
                **base,
                "name": "rich-no-js",
                "path": self.url,
                "noJS": True,
                "mustText": ["تأییدشده", "55,300,000,000", "در حال بررسی"],
            }
        )
        self.browser(self.owner, scenarios)
        self.browser(
            self.reader(),
            [
                {
                    **base,
                    "name": "restricted-" + str(width),
                    "path": self.url,
                    "mobile": width == 390,
                    "steps": [
                        inspect(
                            "!document.querySelector('canvas, progress') && ![...document.querySelectorAll('.contract-detail a')].some(a=>/billing\\/(claims|baselines)/.test(a.href))",
                            "restricted reader sees neither claims nor baselines nor numeric chart data",
                        )
                    ],
                }
                for width in (1440, 390)
            ],
        )
