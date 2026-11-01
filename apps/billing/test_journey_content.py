"""Measure baseline table layout across viewports; isolate all synthetic data."""

from pathlib import Path

from django.urls import reverse

from apps.billing import test_journey_navigation as journey_fixture


class BillingJourneyContentBrowserTests(
    journey_fixture.BillingJourneyNavigationBrowserTests
):
    test_all_tabs_global_scoped_empty_single_multiple_and_restricted = None
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/billing-journey-content/browser"
    )

    def test_progress_search_layout_and_submission(self):
        self.make_fixture(persian=True)
        self._claim()
        listing = reverse("billing:progress_list")
        query = f"?contract={self.contract.pk}"
        self.browser(
            self.owner,
            [
                {
                    "name": f"progress-search-{mobile}",
                    "path": listing + query,
                    "status": 200,
                    "mobile": mobile,
                    "screenshot": True,
                    "steps": [
                        {
                            "inspect": "(() => {const input=document.querySelector('#list-filter-bar input[name=q]'),button=document.querySelector('.erp-list-search__submit'),box=input.getBoundingClientRect(),b=button.getBoundingClientRect();return b.width>0 && parseFloat(getComputedStyle(input).paddingInlineStart)>=38 && (innerWidth<768 || Math.abs(box.top-b.top)<10);})()",
                            "description": "visible Search beside padded input",
                        },
                        {
                            "fill": {"q": "unmatched"},
                            "inspect": "true",
                            "description": "search text entered before explicit submit",
                            "formSelector": "#list-filter-bar",
                        },
                        {
                            "clickSelector": ".erp-list-search__submit",
                            "afterPath": listing,
                        },
                        {
                            "inspect": f"new URLSearchParams(location.search).get('contract')==='{self.contract.pk}' && new URLSearchParams(location.search).get('q')==='unmatched' && !!document.querySelector('.erp-list-chip')",
                            "description": "submit retains contract and displays search chip",
                        },
                    ],
                }
                for mobile in (False, True)
            ],
        )

    def test_table_geometry(self):
        self.make_fixture(persian=True)
        claim = self._claim()
        scenarios = []
        for width, height in ((1440, 900), (1920, 2117), (390, 900)):
            scenarios.append(
                {
                    "name": f"baseline-{width}-{height}",
                    "path": reverse(
                        "billing:baseline_detail", args=[claim.baseline_id]
                    ),
                    "status": 200,
                    "width": width,
                    "height": height,
                    "mobile": width == 390,
                    "screenshot": True,
                    "mustText": [
                        "مبنای متره و صورت‌وضعیت — نسخه",
                        *(["مقدار مبنا", "نرخ واحد"] if width >= 768 else []),
                    ],
                    "steps": [
                        {
                            "inspect": "(() => {const head=document.querySelector('main table thead').getBoundingClientRect(),row=document.querySelector('main table tbody tr').getBoundingClientRect();return innerWidth<768 ? getComputedStyle(document.querySelector('main table tbody tr')).display==='grid' && document.documentElement.scrollWidth<=innerWidth+1 : row.top-head.bottom>=-1 && row.top-head.bottom<8 && row.height<150;})()",
                            "description": "first row immediately follows headers, no vertical void",
                        }
                    ],
                }
            )
        for mobile in (False, True):
            scenarios.append(
                {
                    "name": f"progress-{mobile}",
                    "path": reverse("billing:progress_list"),
                    "status": 200,
                    "mobile": mobile,
                    "screenshot": True,
                    "noJsErrors": True,
                    "noHttpErrors": True,
                    "steps": [
                        {
                            "inspect": "document.querySelector('.erp-list-search__submit').getBoundingClientRect().width>0",
                            "description": "visible explicit Search submission",
                        }
                    ],
                    "mustText": ["کارکرد و پیشرفت"]
                    + (["واحد", "مقدار تجمعی"] if not mobile else []),
                    "mustLinks": [
                        reverse(
                            "billing:progress_detail",
                            args=[claim.baseline.progress_records.first().pk],
                        )
                    ],
                }
            )
        scenarios.append(
            {
                "name": "claims-to-baseline-content",
                "path": reverse("billing:claim_list") + f"?contract={self.contract.pk}",
                "status": 200,
                "screenshot": True,
                "traceNavigation": True,
                "steps": [
                    {
                        "clickSelector": "[data-journey-tab=baselines]",
                        "afterPath": reverse(
                            "billing:baseline_detail", args=[claim.baseline_id]
                        ),
                    }
                ],
                "mustText": ["مبنای متره و صورت‌وضعیت — نسخه"],
            }
        )
        self.browser(self.owner, scenarios)


from django.test import TestCase

from apps.billing.test_mvp03 import JourneyFixture


class JourneyContentTests(JourneyFixture, TestCase):
    def test_progress_search_chips_and_clear_retain_contract(self):
        self.make_fixture(persian=True)
        self._claim()
        self.login(self.owner)
        response = self.client.get(
            reverse("billing:progress_list"),
            {"contract": self.contract.pk, "q": self.contract.title},
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(response.context["filter_bar"]["chips"][0]["name"], "q")
        self.assertEqual(
            response.context["filter_bar"]["clear_url"],
            reverse("billing:progress_list") + f"?contract={self.contract.pk}",
        )
        response = self.client.get(
            reverse("billing:progress_list"),
            {"contract": self.contract.pk, "q": "unmatched"},
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertContains(response, "کارکردی با این زمینه و فیلترها یافت نشد.")
