"""Claims list scope, real filters and responsive Chrome acceptance evidence."""

from copy import copy
from pathlib import Path
from uuid import uuid4

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.models import ProgressClaim
from apps.billing.test_mvp03 import JourneyFixture
from apps.projects.test_command_center import scoped_reader


class ClaimsFixture(JourneyFixture):
    def setUp(self):
        self.make_fixture(persian=True)
        self.url = reverse("billing:claim_list")
        self.scoped = self.url + f"?contract={self.contract.pk}"
        self.login(self.owner)

    def rows(self):
        first = self._claim()
        rows = []
        for index in range(2, 30):
            row = copy(first)
            row.pk = uuid4()
            row.claim_number = index
            row.status = ("draft", "submitted", "returned", "approved")[index % 4]
            rows.append(row)
        ProgressClaim.objects.bulk_create(rows)
        return first


class ClaimsListTests(ClaimsFixture, TestCase):
    def test_short_trail_retains_contract_context_and_return_link(self):
        from apps.billing.test_mvp03_breadcrumbs import breadcrumb_markup

        self._claim()
        response = self.client.get(self.scoped)
        trail = breadcrumb_markup(response)
        contract_url = reverse("contracts:detail", args=[self.contract.pk])
        self.assertEqual(trail.current, ["span"])
        self.assertIn(reverse("contracts:list"), trail.links)
        self.assertNotIn(contract_url, trail.links)
        self.assertNotIn(
            reverse("projects:detail", args=[self.project.pk]), trail.links
        )
        self.assertContains(response, f'href="{contract_url}"')
        self.assertContains(response, self.project.name)
        self.assertContains(response, self.contract.title, count=1)

    def test_filters_counts_context_and_stable_pagination(self):
        first = self.rows()
        response = self.client.get(self.url)
        self.assertEqual(response.context["page_obj"].paginator.count, 29)
        self.assertEqual(
            sum(x["count"] for x in response.context["status_summary"]), 29
        )
        for query in (
            {"q": "۲۹"},
            {"status": "approved"},
            {"project": self.project.pk},
            {"claim_contract": self.contract.pk},
            {"period": "2026-09-01/2026-09-30"},
        ):
            result = self.client.get(self.url, query)
            self.assertGreater(result.context["page_obj"].paginator.count, 0)
            self.assertTrue(result.context["filter_bar"]["chips"])
        result = self.client.get(
            self.url, {"sort": "number", "direction": "asc", "page": 2}
        )
        self.assertEqual(
            [x.claim_number for x in result.context["claims"]], [26, 27, 28, 29]
        )
        result = self.client.get(self.scoped + "&status=draft")
        self.assertNotIn("project", result.context["filter_bar"]["form"].fields)
        self.assertNotIn("claim_contract", result.context["filter_bar"]["form"].fields)
        self.assertEqual(result.context["filter_bar"]["clear_url"], self.scoped)
        self.assertContains(result, reverse("billing:claim_detail", args=[first.pk]))

    def test_scope_choices_and_counts_cannot_reveal_other_projects(self):
        from apps.contracts.services import create_contract
        from apps.projects.services import create_project

        first = self._claim()
        hidden_project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="HIDDEN",
            name="پروژه خارج از دسترسی",
        )
        hidden_contract = create_contract(
            organization=self.organization,
            actor=self.owner,
            project=hidden_project,
            contract_number="HIDDEN-C",
            title="قرارداد خارج از دسترسی",
            counterparty_name="Client",
            party=self.party,
            direction="receivable",
            status="active",
        )
        hidden = copy(first)
        hidden.pk = uuid4()
        hidden.project = hidden_project
        hidden.contract = hidden_contract
        ProgressClaim.objects.bulk_create([hidden])
        reader, _, _ = scoped_reader(self.organization, self.project, ["claims.view"])
        self.login(reader)
        response = self.client.get(self.url)
        self.assertEqual(response.context["claims"], [first])
        self.assertNotContains(response, hidden_project.name)
        self.assertEqual(sum(x["count"] for x in response.context["status_summary"]), 1)
        for query in (
            {"project": hidden_project.pk},
            {"claim_contract": hidden_contract.pk},
            {"contract": hidden_contract.pk},
        ):
            self.assertEqual(
                self.client.get(self.url, query).context["page_obj"].paginator.count, 0
            )

    def test_invalid_scope_and_restricted_user(self):
        self.rows()
        for query in (
            {"contract": uuid4()},
            {"contract": "bad"},
            {"project": uuid4()},
            {"claim_contract": uuid4()},
            {"period": "bad"},
            {"status": "bad"},
        ):
            result = self.client.get(self.url, query)
            self.assertEqual(result.context["page_obj"].paginator.count, 0)
            self.assertFalse(
                result.context["filter_bar"]["form"].fields.get("project")
                and result.context["filter_bar"]["form"]
                .fields["project"]
                .queryset.exclude(organization=self.organization)
                .exists()
            )
        reader, _, _ = scoped_reader(self.organization, self.project, ["claims.view"])
        self.login(reader)
        response = self.client.get(self.scoped)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_create_claim"])
        self.assertNotContains(response, "صورت‌وضعیت جدید")
        denied, _, _ = scoped_reader(
            self.organization, self.project, [], username="claims-denied"
        )
        self.login(denied)
        self.assertEqual(self.client.get(self.url).status_code, 403)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ClaimsListBrowserTests(ClaimsFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/claims-list-reference/browser"
    )

    @classmethod
    def _fixture_setup(cls):
        from django.db import connections

        super()._fixture_setup()
        cls.seed_contents = connections["default"].creation.serialize_db_to_string()

    def _fixture_teardown(self):
        from django.db import connections

        browser_fixture.ContractBillingBrowserTests._fixture_teardown(self)
        connections["default"].creation.deserialize_db_from_string(self.seed_contents)

    def test_chrome_acceptance(self):
        first = self.rows()
        base = {
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
        }

        def inspect(expression, description):
            return {"inspect": expression, "description": description}

        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "CL-global-desktop",
                    "path": self.url,
                    "mustText": [
                        "صورت‌وضعیت‌ها",
                        "ارسال‌شده برای تأیید",
                        "بازگردانده‌شده برای اصلاح",
                        "تأییدشده",
                    ],
                    "steps": [
                        inspect(
                            "document.querySelectorAll('tbody tr').length===25",
                            "25 rows",
                        )
                    ],
                },
                {**base, "name": "CL-global-mobile", "path": self.url, "mobile": True},
                {
                    **base,
                    "name": "CL-pagination",
                    "path": self.url + "?sort=number&direction=asc",
                    "steps": [
                        {"clickSelector": "[rel=next]", "afterPath": self.url},
                        inspect(
                            "new URLSearchParams(location.search).get('page')==='2' && document.querySelectorAll('tbody tr').length===4",
                            "second page and retained sort",
                        ),
                    ],
                },
                {
                    **base,
                    "name": "CL-row-menu",
                    "path": self.url,
                    "steps": [
                        inspect(
                            "(document.querySelector('.erp-list-row-menu summary').click(), true)",
                            "open row menu",
                        ),
                        inspect(
                            "!!document.querySelector('.erp-list-row-menu[open] a')",
                            "vertical menu opens",
                        ),
                    ],
                },
                {
                    **base,
                    "name": "CL-filtered",
                    "path": self.url + "?status=approved",
                    "steps": [
                        inspect(
                            "document.querySelectorAll('.erp-list-chip').length===1",
                            "status chip",
                        ),
                        {"clickSelector": ".erp-list-clear", "afterPath": self.url},
                    ],
                },
                {
                    **base,
                    "name": "CL-advanced",
                    "path": self.url,
                    "steps": [
                        inspect(
                            "(document.querySelector('[data-more-toggle]').click(), true)",
                            "open advanced filters",
                        ),
                        inspect(
                            "!document.querySelector('[data-more-filters]').hidden",
                            "advanced filters open",
                        ),
                    ],
                },
                {
                    **base,
                    "name": "CL-scoped",
                    "path": self.scoped,
                    "steps": [
                        inspect(
                            "!document.querySelector('#list-filter-bar [name=project]') && !document.querySelector('#list-filter-bar [name=claim_contract]')",
                            "no duplicate contract or project selection",
                        ),
                        {"clickSelector": "[data-filter-apply]", "afterPath": self.url},
                        inspect(
                            f"new URLSearchParams(location.search).get('contract')==='{self.contract.pk}'",
                            "contract retained",
                        ),
                    ],
                },
                {
                    **base,
                    "name": "CL-scoped-mobile-filtered",
                    "path": self.scoped + "&status=draft",
                    "mobile": True,
                },
                {
                    **base,
                    "name": "CL-filtered-empty",
                    "path": self.url + "?q=unmatched",
                },
                {
                    **base,
                    "name": "CL-detail",
                    "path": reverse("billing:claim_detail", args=[first.pk]),
                },
            ],
        )
        reader, _, _ = scoped_reader(self.organization, self.project, ["claims.view"])
        self.browser(
            reader,
            [
                {
                    **base,
                    "name": "CL-restricted",
                    "path": self.scoped,
                    "absentText": ["صورت‌وضعیت جدید"],
                },
                {
                    **base,
                    "name": "CL-restricted-mobile",
                    "path": self.url,
                    "mobile": True,
                    "absentText": ["صورت‌وضعیت جدید"],
                },
            ],
        )
