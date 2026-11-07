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
                    "mustText": ["سوابق کارکرد"]
                    + (["واحد", "کارکرد تجمعی تا این تاریخ"] if not mobile else []),
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
                "name": "contract-to-claims-content",
                "path": reverse("contracts:detail", args=[self.contract.pk]),
                "status": 200,
                "screenshot": True,
                "traceNavigation": True,
                "steps": [
                    {
                        "clickSelector": ".cd-claims .cd-footer",
                        "afterPath": reverse("billing:claim_list"),
                    },
                    {
                        "inspect": "!document.querySelector('[data-billing-navigation]')",
                        "description": "Claims collection has no sibling-workspace tabs",
                    },
                ],
                "mustText": ["صورت‌وضعیت‌ها", self.contract.title],
            }
        )
        self.browser(self.owner, scenarios)


from django.test import TestCase

from apps.billing.test_mvp03 import JourneyFixture


class JourneyContentTests(JourneyFixture, TestCase):
    def test_measurement_detail_exposes_original_values_evidence_and_scoped_return(
        self,
    ):
        self.make_fixture(persian=True)
        record = self._verified_record()
        self.login(self.owner)
        response = self.client.get(reverse("billing:progress_detail", args=[record.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-billing-navigation")
        for label in (
            "کارکرد این ثبت",
            "کارکرد تجمعی تا این ثبت",
            "مقدار مبنای قلم",
            "زمان بررسی",
            record.verification_reason,
            record.source_reference,
        ):
            self.assertContains(response, label)
        self.assertEqual(
            response.context["progress_record"].period_quantity, record.period_quantity
        )
        self.assertEqual(
            response.context["progress_record"].cumulative_quantity,
            record.cumulative_quantity,
        )
        self.assertIn(f"contract={self.contract.pk}", response.context["history_url"])
        self.assertIn("line_key=ITEM-01", response.context["history_url"])
        self.assertNotContains(response, "بازگشت به سوابق کارکرد این قلم")
        self.assertEqual(
            response.context["page_breadcrumbs"][-2]["url"],
            response.context["history_url"],
        )
        from apps.projects.test_command_center import scoped_reader

        reader, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["progress.view"],
            username="detail-only-reader",
        )
        self.login(reader)
        independent = self.client.get(
            reverse("billing:progress_detail", args=[record.pk])
        )
        self.assertEqual(independent.status_code, 200)
        self.assertNotIn(
            'method="post"',
            independent.content.decode().split('class="measurement-detail"', 1)[1],
        )
        self.assertNotContains(
            independent, reverse("contracts:detail", args=[self.contract.pk])
        )

    def test_line_description_search_and_line_context_use_authorized_sources(self):
        self.make_fixture(persian=True)
        record = self._verified_record()
        self.login(self.owner)
        path = reverse("billing:progress_list")
        result = self.client.get(path, {"contract": self.contract.pk, "q": "Concrete"})
        self.assertEqual(list(result.context["progress_records"]), [record])
        self.assertContains(result, "مقدار کارکرد دوره")
        self.assertContains(result, "کارکرد تجمعی تا این تاریخ")
        self.assertContains(result, "جزئیات کارکرد ثبت‌شده")
        self.assertContains(result, "سوابق همین قلم")
        empty = self.client.get(
            path,
            {
                "contract": self.contract.pk,
                "line_key": record.baseline_item.line_key,
                "q": "not-matching-any-line",
            },
        )
        self.assertEqual(empty.context["page_obj"].paginator.count, 0)
        self.assertEqual(empty.context["selected_line_record"], record)
        self.assertContains(empty, "همه اقلام این قرارداد")
        invalid = self.client.get(
            path, {"contract": "invalid", "line_key": record.baseline_item.line_key}
        )
        self.assertIsNone(invalid.context["selected_line_record"])
        self.assertEqual(invalid.context["page_obj"].paginator.count, 0)

    def test_progress_search_chips_and_clear_retain_contract(self):
        self.make_fixture(persian=True)
        self._claim()
        self.login(self.owner)
        response = self.client.get(
            reverse("billing:progress_list"),
            {"contract": self.contract.pk, "q": self.contract.title},
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertNotContains(response, "data-billing-navigation")
        self.assertContains(response, "بازگشت به مقادیر و بهای قرارداد")
        self.assertEqual(response.context["selected_contract"], self.contract)
        self.assertEqual(
            response.context["page_breadcrumbs"][-1]["label"],
            "سوابق کارکرد",
        )
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
        global_result = self.client.get(reverse("billing:progress_list"))
        self.assertIsNone(global_result.context["selected_contract"])
        self.assertNotContains(global_result, "data-billing-navigation")
        from apps.projects.test_command_center import scoped_reader

        reader, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["progress.view"],
            username="history-only-reader",
        )
        self.login(reader)
        independent = self.client.get(
            reverse("billing:progress_list"), {"contract": self.contract.pk}
        )
        self.assertEqual(independent.status_code, 200)
        self.assertEqual(independent.context["page_obj"].paginator.count, 1)
        self.assertIsNone(independent.context["selected_contract"])
        self.assertNotContains(independent, "بازگشت به مقادیر و بهای قرارداد")
