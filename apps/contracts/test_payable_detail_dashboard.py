"""Payable Contract Detail source composition, independent permissions and Chrome."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.models import PayableCertificate
from apps.billing.payable_services import (
    approve_payable_certificate,
    create_payable_certificate,
    create_payable_measurement,
    decide_payable_measurement,
    submit_payable_certificate,
    submit_payable_measurement,
)
from apps.contracts.services import (
    add_contract_item,
    approve_contract_term_version,
    create_contract,
    create_contract_term_version,
    transition_contract_status,
)
from apps.contracts.test_detail_dashboard import DetailFixture
from apps.projects.test_command_center import scoped_reader


def organization_reader(org, project, permissions, *, username):
    user, _role, grant = scoped_reader(org, project, permissions, username=username)
    grant.scope_type, grant.project = "organization", None
    grant.save()
    return user


class PayableDetailFixture(DetailFixture):
    def prepare_payable(self):
        self.ready()
        self.approver = organization_reader(
            self.organization,
            self.project,
            [
                "contract_terms.approve",
                "payable_measurements.verify",
                "payable_certificates.approve",
                "payable_certificates.view",
                "work_items.claim",
                "work_items.act",
            ],
            username="payable-independent-approver",
        )
        self.payable = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="CD-PAY-01",
            title="قرارداد پیمانکاری آزمایشی نما",
            counterparty_name=self.party.display_name,
            party=self.party,
            direction="payable",
            contract_type="subcontract",
            contract_value=Decimal(1000),
        )
        item = add_contract_item(
            organization=self.organization,
            actor=self.owner,
            contract=self.payable,
            description="اجرای نمای آزمایشی",
            quantity=Decimal("10.0000"),
            unit_price=Decimal(100),
        )
        self.payable = transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=self.payable,
            status="active",
        )
        term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.payable,
            effective_from=date(2026, 7, 1),
            reason="Explicit isolated test terms",
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.approver,
            term_version=term,
            reason="Independent test approval",
        )
        cumulative = Decimal(0)
        self.certificates = []
        for month, quantity in (
            (7, Decimal("2.0000")),
            (8, Decimal("3.0000")),
            (9, Decimal("1.0000")),
        ):
            cumulative += quantity
            measurement = create_payable_measurement(
                organization=self.organization,
                actor=self.owner,
                contract_item=item,
                measured_on=date(2026, month, 15),
                period_quantity=quantity,
                cumulative_quantity=cumulative,
                evidence_reference=f"CD-TEST-{month}",
            )
            submit_payable_measurement(
                organization=self.organization,
                actor=self.owner,
                measurement=measurement,
            )
            decide_payable_measurement(
                organization=self.organization,
                actor=self.approver,
                measurement=measurement,
                approved=True,
                reason="Independent test measurement",
            )
            certificate = create_payable_certificate(
                organization=self.organization,
                actor=self.owner,
                contract=self.payable,
                period_start=date(2026, month, 1),
                period_end=date(2026, month, 28),
                measurement_cutoff=date(2026, month, 28),
            )
            submit_payable_certificate(
                organization=self.organization,
                actor=self.owner,
                certificate=certificate,
            )
            if month < 9:
                approve_payable_certificate(
                    organization=self.organization,
                    actor=self.approver,
                    certificate=certificate,
                    reason="Independent test approval",
                )
            certificate.refresh_from_db()
            self.certificates.append(certificate)
        self.payable_url = reverse("contracts:detail", args=[self.payable.pk])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PayableContractDetailTests(PayableDetailFixture, TestCase):
    def setUp(self):
        self.prepare_payable()

    def test_scoped_payable_amounts_links_and_events(self):
        # A readable receivable claim must not be mixed into this payable contract.
        claim = self.rich()
        response = self.client.get(self.payable_url)
        self.assertEqual(response.status_code, 200)
        dashboard = response.context["dashboard"]
        self.assertEqual(
            [r["value"] for r in dashboard["segments"]],
            [Decimal(500), Decimal(100), Decimal(400)],
        )
        self.assertEqual(dashboard["financial_percent"], Decimal("50.0"))
        self.assertEqual([r["number"] for r in dashboard["billing_records"]], [3, 2, 1])
        self.assertEqual(
            [Decimal(r["value"]) for r in dashboard["chart_rows"]],
            [Decimal(500), Decimal(100), Decimal(400)],
        )
        self.assertFalse(dashboard["show_baselines"])
        self.assertTrue(dashboard["show_billing"])
        for certificate in self.certificates:
            self.assertContains(
                response,
                reverse("billing:payable_certificate_detail", args=[certificate.pk]),
            )
        self.assertNotIn(
            reverse("billing:claim_detail", args=[claim.pk]),
            response.content.decode().split('class="contract-detail"', 1)[1],
        )
        self.assertTrue(
            all(
                "/billing/payable-certificates/" in event["url"]
                for event in dashboard["recent"]
            )
        )
        self.assertIsNone(dashboard["physical_percent"])

    def test_payable_permission_is_independent_of_receivable_permission(self):
        denied = organization_reader(
            self.organization,
            self.project,
            ["contracts.view", "claims.view"],
            username="receivable-only-reader",
        )
        self.login(denied)
        response = self.client.get(self.payable_url)
        self.assertIsNone(response.context["dashboard"]["billing_records"])
        self.assertFalse(response.context["dashboard"]["chart_rows"])
        self.assertEqual(len(response.context["dashboard"]["recent"]), 1)
        for certificate in self.certificates:
            self.assertNotContains(
                response,
                reverse("billing:payable_certificate_detail", args=[certificate.pk]),
            )
        allowed = organization_reader(
            self.organization,
            self.project,
            ["contracts.view", "payable_certificates.view"],
            username="payable-only-reader",
        )
        self.login(allowed)
        self.assertEqual(
            len(
                self.client.get(self.payable_url).context["dashboard"][
                    "billing_records"
                ]
            ),
            3,
        )

    def test_existing_selector_scope_gate_is_preserved(self):
        reader, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["contracts.view", "payable_certificates.view"],
            username="project-payable-reader",
        )
        self.login(reader)
        response = self.client.get(self.payable_url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["dashboard"]["billing_records"])
        self.assertFalse(response.context["dashboard"]["chart_rows"])
        self.assertEqual(len(response.context["dashboard"]["recent"]), 1)

    def test_payable_incompatible_currency_or_correction_does_not_fabricate_totals(
        self,
    ):
        certificate = self.certificates[0]
        for changes in (
            {"currency_code": "USD"},
            {
                "currency_code": certificate.currency_code,
                "correction_kind": "replacement",
            },
        ):
            PayableCertificate.objects.filter(pk=certificate.pk).update(**changes)
            response = self.client.get(self.payable_url)
            self.assertFalse(response.context["dashboard"]["segments"])
            self.assertIsNone(response.context["dashboard"]["financial_percent"])
            self.assertEqual(len(response.context["dashboard"]["billing_records"]), 3)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PayableContractDetailBrowserTests(PayableDetailFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2]
        / "output/contract-detail-reference/payable-connection/browser"
    )

    def test_payable_and_restricted_desktop_mobile(self):
        self.prepare_payable()
        base = {
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
        }
        check = "document.querySelectorAll('.cd-claims tbody tr').length===3 && Chart.getChart('contract-financial-chart').data.datasets.map(d=>d.data[0]).join(',')==='500,100,400' && document.querySelector('progress').value===50 && ![...document.querySelectorAll('.contract-detail a')].some(a=>/billing\\/(claims|baselines)/.test(a.href)) && [...document.querySelectorAll('.cd-claims tbody a')].every(a=>a.href.includes('/billing/payable-certificates/'))"
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "payable-rich-" + str(width),
                    "path": self.payable_url,
                    "mobile": width == 390,
                    "mustText": ["آخرین صورت‌وضعیت‌های پرداختنی"],
                    "steps": [
                        {
                            "inspect": check,
                            "description": "payable records and exact 500/100/400 proportions; independent of receivable paths",
                        }
                    ],
                }
                for width in (1440, 390)
            ],
        )
        restricted = organization_reader(
            self.organization,
            self.project,
            ["contracts.view", "claims.view"],
            username="restricted-payable-browser",
        )
        self.browser(
            restricted,
            [
                {
                    **base,
                    "name": "payable-restricted-" + str(width),
                    "path": self.payable_url,
                    "mobile": width == 390,
                    "steps": [
                        {
                            "inspect": "!document.querySelector('canvas, progress, .cd-claims tbody') && ![...document.querySelectorAll('.contract-detail a')].some(a=>a.href.includes('/billing/payable-certificates/'))",
                            "description": "payable source data, events and routes denied without its permission",
                        }
                    ],
                }
                for width in (1440, 390)
            ],
        )
