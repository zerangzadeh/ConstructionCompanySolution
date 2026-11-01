"""Reference list navigation and responsive behavior in real Chrome.

Synthetic records stay in the isolated MVP-03 test database. The existing filter
suite covers tenant/permission scope, remote projects, history and invalid input.
"""

from datetime import date
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ReferenceContractListBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/reference-contract-list/browser"
    )

    def test_pagination_sorting_cards_and_filter_disclosures(self):
        self.make_fixture(persian=True)
        Contract.objects.bulk_create(
            [
                Contract(
                    organization=self.organization,
                    project=self.project,
                    contract_number=f"REF-{index:03}",
                    title=f"قرارداد مرجع اجرای سازه {index:03}",
                    counterparty_name="پیمانکار نمونه",
                    direction="payable",
                    status="active",
                    signed_at=date(2026, 10, 1),
                )
                for index in range(31)
            ]
        )
        listing = reverse("contracts:list")
        first_detail = reverse(
            "contracts:detail",
            args=[
                Contract.objects.get(
                    organization=self.organization, contract_number="REF-000"
                ).pk
            ],
        )
        query = "?q=REF&status=active&side=payable&sort=number&direction=asc"
        scoped = query + f"&project_id={self.project.pk}"

        def inspect(expression, description):
            return {"inspect": expression, "description": description}

        base = {
            "status": 200,
            "screenshot": True,
            "absentText": ["receivable", "payable", "UUID", "None"],
        }
        retained = (
            "new URLSearchParams(location.search).get('q')==='REF' && "
            "new URLSearchParams(location.search).get('status')==='active' && "
            "new URLSearchParams(location.search).get('side')==='payable'"
        )
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "REF-pagination-and-sort-desktop",
                    "path": listing + query,
                    "steps": [
                        {"clickSelector": "[rel=next]", "afterPath": listing},
                        inspect(
                            retained
                            + " && new URLSearchParams(location.search).get('page')==='2'"
                            + " && document.querySelectorAll('tbody tr').length===6"
                            + " && document.querySelector('.erp-list-identifier').textContent.includes('REF-025')",
                            "page two retains filters and stable ascending identifiers",
                        ),
                        {
                            "clickSelector": "th a[href*='sort=title']",
                            "afterPath": listing,
                        },
                        inspect(
                            retained
                            + " && !new URLSearchParams(location.search).has('page')"
                            + " && new URLSearchParams(location.search).get('sort')==='title'"
                            + " && document.querySelector('[data-list-sort-summary]').textContent.includes('عنوان قرارداد')",
                            "existing title sorting retains filters and resets pagination",
                        ),
                        {
                            "clickSelector": ".erp-list-title a",
                            "afterPath": first_detail,
                        },
                        {"history": "back"},
                        inspect(
                            retained, "title navigation and browser back retain filters"
                        ),
                    ],
                },
                {
                    **base,
                    "name": "REF-scoped-pagination-mobile",
                    "path": listing + scoped,
                    "mobile": True,
                    "steps": [
                        {"clickSelector": "[rel=next]", "afterPath": listing},
                        inspect(
                            retained
                            + f" && new URLSearchParams(location.search).get('project_id')==='{self.project.pk}'"
                            + " && !document.querySelector('main [name=project]')"
                            + " && getComputedStyle(document.querySelector('tbody tr')).display==='grid'"
                            + " && document.querySelector('tbody tr').getBoundingClientRect().width<innerWidth"
                            + " && document.querySelector('.erp-list-identifier bdi').dir==='ltr'"
                            + " && !document.querySelector('main input[type=checkbox]')",
                            "scoped page two keeps context and renders mobile cards with LTR identifiers",
                        ),
                        {
                            "clickSelector": "[data-filter-chip=status]",
                            "afterPath": listing,
                        },
                        inspect(
                            "!new URLSearchParams(location.search).has('page') && "
                            "!new URLSearchParams(location.search).has('status') && "
                            "new URLSearchParams(location.search).get('side')==='payable'",
                            "one chip removal resets pagination and keeps other filters",
                        ),
                    ],
                },
                {
                    **base,
                    "name": "REF-advanced-open-close-desktop",
                    "path": listing,
                    "steps": [
                        {
                            "toggleSelector": "[data-more-toggle]",
                            "inspect": "document.querySelector('[data-more-filters]').open",
                            "description": "advanced panel opens",
                        },
                        {
                            "toggleSelector": "[data-more-toggle]",
                            "inspect": "!document.querySelector('[data-more-filters]').open",
                            "description": "advanced panel closes",
                        },
                        inspect(
                            "!!document.querySelector('[data-filter-result-count]') && "
                            "!document.querySelector('main input[type=checkbox]') && "
                            "!document.querySelector('main a[href*=export]') && "
                            "!document.querySelector('.erp-list-context').open",
                            "result summary, compact global context and only existing actions",
                        ),
                    ],
                },
            ],
        )
