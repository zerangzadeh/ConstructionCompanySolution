"""Real Chrome coverage for direction-aware Contract to Billing navigation."""

from datetime import date
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.contracts.models import Contract
from core.jalali import format_jalali

from . import test_mvp03_browser as browser_fixture
from .models import ProgressClaim
from .test_mvp03 import JourneyFixture


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractDirectionBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2]
        / "output/mvp-03/contract-direction-remediation/browser"
    )

    def test_direction_filters_and_create_journeys(self):
        self.make_fixture(persian=True)
        self.project.name = "پروژه نمونه سازه"
        self.project.save()
        record = self._verified_record()
        payable = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            party=self.party,
            contract_number="PAYABLE-TEST",
            title="قرارداد پرداختنی نمونه",
            direction="payable",
            status="active",
            counterparty_name=self.party.display_name,
        )
        contract = reverse("contracts:detail", args=[self.contract.pk])
        payable_detail = reverse("contracts:detail", args=[payable.pk])
        listing = reverse("billing:claim_list")
        scoped = listing + f"?contract={self.contract.pk}"
        create = reverse("billing:claim_create")
        contextual_create = create + f"?contract={self.contract.pk}"
        base = {"status": 200, "screenshot": True}

        def dates(month):
            return {
                name: format_jalali(date(2026, month, day))
                for name, day in (
                    ("period_start", 1),
                    ("period_end", 30),
                    ("measurement_cutoff", 30),
                )
            }

        def no_create():
            return {
                "inspect": "![...document.querySelectorAll('main a[href]')].some(a=>a.pathname==='/billing/claims/new/')",
                "description": "no receivable create action",
            }

        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "DIR-01-receivable-entry",
                    "path": contract,
                    "mustLinks": [scoped, contextual_create],
                },
                {
                    **base,
                    "name": "DIR-02-contract-new-claim",
                    "path": contract,
                    "steps": [{"clickHref": contextual_create, "afterPath": create}],
                    "mustText": [self.contract.title, "صورت‌وضعیت جدید"],
                },
                {
                    **base,
                    "name": "DIR-03-contextual-list-desktop",
                    "path": scoped,
                    "mustLinks": [contextual_create, contract],
                    "absentText": ["جست‌وجوی قرارداد یا پروژه"],
                    "steps": [
                        {
                            "inspect": "!!document.querySelector('main [name=status]') && !document.querySelector('main [name=q]')",
                            "description": "status retained; irrelevant search removed",
                        }
                    ],
                },
                {
                    **base,
                    "name": "DIR-04-contextual-list-mobile",
                    "path": scoped,
                    "mobile": True,
                    "mustLinks": [contextual_create, contract],
                },
                {
                    **base,
                    "name": "DIR-05-filter-retains-contract",
                    "path": scoped,
                    "steps": [
                        {
                            "fill": {"status": "draft"},
                            "clickSelector": "form[aria-label='فیلتر صورت‌وضعیت‌ها'] button",
                            "afterPath": listing,
                        },
                        {
                            "inspect": f"new URLSearchParams(location.search).get('contract')==='{self.contract.pk}' && new URLSearchParams(location.search).get('status')==='draft'",
                            "description": "status submission retains contract",
                        },
                    ],
                    "mustLinks": [scoped, contextual_create],
                },
                {
                    **base,
                    "name": "DIR-06-clear-retains-contract",
                    "path": scoped + "&status=approved",
                    "steps": [
                        {"clickHref": scoped, "afterPath": listing},
                        {
                            "inspect": f"location.search==='?contract={self.contract.pk}'",
                            "description": "clear filters retains contract",
                        },
                    ],
                    "mustLinks": [contextual_create],
                },
                {
                    **base,
                    "name": "DIR-07-list-create-success",
                    "path": scoped,
                    "steps": [
                        {"clickHref": contextual_create, "afterPath": create},
                        {
                            "fill": dates(9),
                            "submit": True,
                            "afterPrefix": "/billing/claims/",
                            "mustText": "پیش‌نویس صورت‌وضعیت",
                        },
                    ],
                    "mustText": ["وضعیت و اقدام بعدی"],
                },
                {
                    **base,
                    "name": "DIR-08-payable-desktop",
                    "path": payable_detail,
                    "absentLinks": [
                        create + f"?contract={payable.pk}",
                        listing + f"?contract={payable.pk}",
                        reverse("billing:baseline_list") + f"?contract={payable.pk}",
                    ],
                    "absentText": ["صورت‌وضعیت جدید"],
                    "steps": [no_create()],
                },
                {
                    **base,
                    "name": "DIR-09-payable-mobile",
                    "path": payable_detail,
                    "mobile": True,
                    "absentText": ["صورت‌وضعیت جدید"],
                    "steps": [no_create()],
                },
                {
                    **base,
                    "name": "DIR-10-payable-context-list",
                    "path": listing + f"?contract={payable.pk}",
                    "absentText": ["صورت‌وضعیت جدید", "جست‌وجوی قرارداد یا پروژه"],
                    "steps": [no_create()],
                },
                {
                    **base,
                    "name": "DIR-11-invalid-context",
                    "path": listing + "?contract=invalid",
                    "absentText": ["صورت‌وضعیت جدید"],
                    "steps": [no_create()],
                },
                {
                    **base,
                    "name": "DIR-12-direct-list",
                    "path": listing,
                    "mustLinks": [create],
                    "mustText": ["جست‌وجوی قرارداد یا پروژه"],
                },
                {
                    **base,
                    "name": "DIR-13-direct-create-success",
                    "path": listing,
                    "steps": [
                        {"clickHref": create, "afterPath": create},
                        {
                            "searchChoice": {
                                "name": "contract",
                                "query": self.contract.contract_number,
                                "value": str(self.contract.pk),
                            }
                        },
                        {
                            "searchChoice": {
                                "name": "baseline",
                                "query": self.contract.title,
                                "value": str(record.baseline_id),
                            }
                        },
                        {
                            "fill": dates(10),
                            "submit": True,
                            "afterPrefix": "/billing/claims/",
                            "mustText": "پیش‌نویس صورت‌وضعیت",
                        },
                    ],
                },
            ],
        )
        self.assertEqual(
            ProgressClaim.objects.filter(contract=self.contract).count(), 2
        )
        self.assertFalse(ProgressClaim.objects.filter(contract=payable).exists())

        Contract.objects.filter(pk=self.contract.pk).update(status="completed")
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "DIR-14-inactive-contract",
                    "path": contract,
                    "steps": [no_create()],
                },
                {
                    **base,
                    "name": "DIR-15-inactive-context-list",
                    "path": scoped,
                    "steps": [no_create()],
                },
            ],
        )
