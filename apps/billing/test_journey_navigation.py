"""Journey tab destinations, contextual baseline routing and real Chrome traces."""

from html.parser import HTMLParser
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.projects.test_command_center import scoped_reader


class JourneyLinks(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.links = {}
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "data-journey-tab" in attrs:
            self.links[attrs["data-journey-tab"]] = attrs["href"]


class JourneyNavigationTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture(persian=True)
        self.login(self.owner)
        self.contract_query = f"?contract={self.contract.pk}"

    def assert_tabs(self, response, scoped):
        if response.resolver_match.url_name in (
            "claim_list",
            "progress_list",
            "progress_detail",
        ):
            self.assertEqual(JourneyLinks(response).links, {})
            self.assertNotContains(response, "data-billing-navigation")
            return
        expected = {
            tab: reverse(f"billing:{route}_list")
            + (self.contract_query if scoped else "")
            for tab, route in (
                ("claims", "claim"),
                ("baselines", "baseline"),
                ("progress", "progress"),
            )
        }
        if scoped:
            expected["baselines"] = (
                reverse("contracts:detail", args=[self.contract.pk])
                + "?section=quantities&pane=basis"
            )
        self.assertEqual(JourneyLinks(response).links, expected)

    def test_zero_one_and_multiple_baseline_routing_and_all_tabs(self):
        baseline_url = reverse("billing:baseline_list") + self.contract_query
        self.assert_tabs(self.client.get(baseline_url), True)
        self.assertContains(
            self.client.get(baseline_url),
            "برای این قرارداد هنوز مبنای متره و صورت‌وضعیت ثبت نشده است.",
        )
        claim = self._claim()
        result = self.client.get(baseline_url, follow=True)
        self.assertEqual(
            result.redirect_chain,
            [(reverse("billing:baseline_detail", args=[claim.baseline_id]), 302)],
        )
        self.assert_tabs(result, True)
        self.assert_tabs(
            self.client.get(reverse("billing:claim_detail", args=[claim.pk])), True
        )
        self._baseline()
        result = self.client.get(baseline_url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context["page_obj"].paginator.count, 2)
        self.assert_tabs(result, True)
        for route in ("claim_list", "baseline_list", "progress_list"):
            self.assert_tabs(self.client.get(reverse(f"billing:{route}")), False)
            self.assert_tabs(
                self.client.get(reverse(f"billing:{route}") + self.contract_query), True
            )

    def test_tab_permissions_remain_separate(self):
        claim = self._claim()
        reader, _, _ = scoped_reader(self.organization, self.project, ["claims.view"])
        self.login(reader)
        result = self.client.get(reverse("billing:claim_list") + self.contract_query)
        self.assertEqual(JourneyLinks(result).links, {})
        self.assertEqual(
            self.client.get(
                reverse("billing:baseline_list") + self.contract_query
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("billing:progress_list") + self.contract_query
            ).status_code,
            403,
        )
        # A record-authorized baseline reader retains context without contracts.view.
        baseline_reader, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["baselines.view"],
            username="journey-baseline-only",
        )
        self.login(baseline_reader)
        result = self.client.get(
            reverse("billing:baseline_list") + self.contract_query, follow=True
        )
        self.assertEqual(result.resolver_match.view_name, "billing:baseline_detail")
        self.assertEqual(
            JourneyLinks(result).links,
            {"baselines": reverse("billing:baseline_list") + self.contract_query},
        )
        self.assertEqual(result.context["baseline"].pk, claim.baseline_id)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BillingJourneyNavigationBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2]
        / "output/billing-journey-navigation/browser"
    )

    @classmethod
    def _fixture_setup(cls):
        super()._fixture_setup()
        cls.seed_contents = connections["default"].creation.serialize_db_to_string()

    def _fixture_teardown(self):
        browser_fixture.ContractBillingBrowserTests._fixture_teardown(self)
        connections["default"].creation.deserialize_db_from_string(self.seed_contents)

    def test_all_tabs_global_scoped_empty_single_multiple_and_restricted(self):
        self.make_fixture(persian=True)
        claims = reverse("billing:claim_list")
        baselines = reverse("billing:baseline_list")
        progress = reverse("billing:progress_list")
        query = f"?contract={self.contract.pk}"
        base = {
            "status": 200,
            "screenshot": True,
            "traceNavigation": True,
            "noJsErrors": True,
            "noHttpErrors": True,
        }

        def cycle(name, start, baseline_destination, *, scoped=False, mobile=False):
            suffix = query if scoped else ""
            steps = []
            from_claims_list = start == claims + suffix
            if from_claims_list and scoped:
                steps += [
                    {
                        "inspect": "!document.querySelector('[data-billing-navigation]')",
                        "description": "Claims list is a focused collection",
                    },
                    {
                        "clickSelector": ".erp-list-scope a",
                        "afterPath": reverse(
                            "contracts:detail", args=[self.contract.pk]
                        ),
                    },
                    {
                        "clickSelector": '[data-contract-hub-navigation] a[href*="section=quantities"]',
                        "afterPath": reverse(
                            "contracts:detail", args=[self.contract.pk]
                        ),
                    },
                ]
            elif from_claims_list:
                start = baselines
            for tab, destination in (
                ("baselines", baseline_destination),
                ("progress", progress),
            ):
                selector = f"[data-journey-tab={tab}]"
                if scoped and tab == "baselines":
                    destination = reverse("contracts:detail", args=[self.contract.pk])
                    if from_claims_list:
                        selector = '.cd-quantity-tabs a[href*="pane=basis"]'
                if scoped and tab == "progress":
                    selector = '.cd-quantity-tabs a[href*="/billing/progress/"]'
                steps.append(
                    {
                        "clickSelector": selector,
                        "afterPath": destination,
                    }
                )
                steps.append(
                    {
                        "inspect": (
                            "!!document.querySelector('[data-contract-quantities]') && new URLSearchParams(location.search).get('pane')==='basis'"
                            if scoped and tab == "baselines"
                            else f"!document.querySelector('[data-billing-navigation]') && location.pathname==={progress!r} && location.search==={suffix!r}"
                            if tab == "progress"
                            else f"document.querySelector('[data-journey-tab={tab}]').getAttribute('aria-current')==='page' && document.querySelector('[data-journey-tab=claims]').getAttribute('href')==={claims + suffix!r} && !/\\/billing\\/claims\\/[^/?]+\\//.test(location.pathname)"
                        ),
                        "description": "correct destination, active tab and contract context; no Claim Detail",
                    }
                )
            return {
                **base,
                "name": name,
                "path": start,
                "mobile": mobile,
                "steps": steps,
            }

        claim = None
        for stage in ("empty", "single", "multiple"):
            if stage == "single":
                claim = self._claim()
            if stage == "multiple":
                self._baseline()
            target = (
                reverse("billing:baseline_detail", args=[claim.baseline_id])
                if stage == "single"
                else baselines
            )
            scenarios = []
            for mobile in (False, True):
                device = "mobile" if mobile else "desktop"
                scenarios.extend(
                    [
                        cycle(
                            f"{stage}-global-{device}", claims, baselines, mobile=mobile
                        ),
                        cycle(
                            f"{stage}-scoped-{device}",
                            claims + query,
                            target,
                            scoped=True,
                            mobile=mobile,
                        ),
                    ]
                )
            if claim:
                scenarios.append(
                    cycle(
                        f"{stage}-from-claim-detail",
                        reverse("billing:claim_detail", args=[claim.pk]),
                        target,
                        scoped=True,
                    )
                )
            self.browser(self.owner, scenarios)
        reader, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["claims.view", "baselines.view", "progress.view", "contracts.view"],
            username="journey-reader",
        )
        self.browser(
            reader,
            [
                cycle("restricted-scoped", claims + query, baselines, scoped=True),
                cycle("restricted-global-mobile", claims, baselines, mobile=True),
            ],
        )
