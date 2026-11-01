"""Baseline UX and real Chrome verification on isolated PostgreSQL."""

from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.projects.test_command_center import scoped_reader


class BaselineFixture(JourneyFixture):
    def setUp(self):
        self.make_fixture(persian=True)
        self.project.name = "پروژه بیمارستان شمال"
        self.project.save()
        self.url = reverse("billing:baseline_list")
        self.scoped = self.url + f"?contract={self.contract.pk}"
        self.login(self.owner)


class BaselineListTests(BaselineFixture, TestCase):
    def test_empty_single_current_and_history(self):
        response = self.client.get(self.scoped)
        self.assertContains(
            response, "برای این قرارداد هنوز مبنای متره و صورت‌وضعیت ثبت نشده است."
        )
        self.assertNotContains(response, "مبنای جدید")
        first = self._approved_baseline()
        self.assertRedirects(
            self.client.get(self.scoped),
            reverse("billing:baseline_detail", args=[first.pk]),
        )
        versions = self.scoped + "&versions=1"
        self.assertContains(self.client.get(versions), "نسخه جاری")
        second = self._approved_baseline()
        response = self.client.get(self.scoped)
        self.assertEqual(response.context["baselines"], [second, first])
        self.assertContains(response, "جایگزین‌شده")
        self.assertContains(response, "نسخه جاری", count=1)
        self.assertNotContains(response, 'name="contract_filter"')
        self.assertNotContains(response, 'name="project"')
        self.assertIsNone(response.context["filter_bar"])
        detail = self.client.get(reverse("billing:baseline_detail", args=[first.pk]))
        self.assertEqual(detail.context["page_breadcrumbs"][-2]["url"], versions)

    def test_global_filters_sort_and_pagination(self):
        first = self._approved_baseline()
        for _ in range(25):
            self._baseline()
        response = self.client.get(
            self.url, {"status": "approved", "q": self.project.name}
        )
        self.assertEqual(response.context["baselines"], [first])
        self.assertEqual(len(response.context["filter_bar"]["chips"]), 2)
        response = self.client.get(
            self.url, {"sort": "version", "direction": "asc", "page": 2}
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        self.assertEqual(response.context["baselines"][0].version, 26)
        for query in (
            {"status": "bad"},
            {"project": "bad"},
            {"contract_filter": "bad"},
        ):
            self.assertEqual(self.client.get(self.url, query).context["baselines"], [])

    def test_restricted_and_tenant_scope(self):
        self._approved_baseline()
        user, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["baselines.view", "contracts.view"],
            username="baseline-reader",
        )
        self.login(user)
        self.assertEqual(self.client.get(self.scoped).status_code, 302)
        from apps.organizations.models import Organization

        other = Organization.objects.create(name="Other", slug="baseline-other")
        other.memberships.create(user=user, status="active", role="member")
        from apps.organizations.services import set_active_organization

        session = self.client.session
        set_active_organization(session, other)
        session.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        denied, _, _ = scoped_reader(
            self.organization, self.project, [], username="baseline-denied"
        )
        self.login(denied)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_foreign_project_records_and_filter_choices_are_hidden(self):
        from datetime import date

        from apps.billing.services import create_project_baseline
        from apps.contracts.services import create_contract
        from apps.projects.services import create_project

        visible = self._approved_baseline()
        sibling = create_project(
            organization=self.organization,
            actor=self.owner,
            code="HIDDEN",
            name="پروژه خارج از دسترسی",
        )
        hidden_contract = create_contract(
            organization=self.organization,
            actor=self.owner,
            project=sibling,
            contract_number="HIDDEN-C",
            title="قرارداد خارج از دسترسی",
            counterparty_name="Client",
            party=self.party,
            direction="receivable",
            status="active",
        )
        hidden = create_project_baseline(
            organization=self.organization,
            actor=self.owner,
            project=sibling,
            contract=hidden_contract,
            effective_date=date(2026, 9, 1),
        )
        reader, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["baselines.view", "contracts.view"],
            username="limited-baseline",
        )
        self.login(reader)
        response = self.client.get(self.url)
        self.assertEqual(response.context["baselines"], [visible])
        self.assertNotContains(response, hidden_contract.title)
        self.assertEqual(
            self.client.get(self.url, {"project": sibling.pk}).context["baselines"], []
        )
        self.assertEqual(
            self.client.get(
                self.scoped.replace(str(self.contract.pk), str(hidden_contract.pk))
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("billing:baseline_detail", args=[hidden.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self.url, {"contract": "bad"}).status_code, 404
        )
        baseline_only, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["baselines.view"],
            username="baseline-only",
        )
        self.login(baseline_only)
        self.assertEqual(self.client.get(self.scoped).status_code, 302)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BaselineBrowserTests(BaselineFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/baseline-list-reference/browser"
    )

    @classmethod
    def _fixture_setup(cls):
        super()._fixture_setup()
        cls.seed_contents = connections["default"].creation.serialize_db_to_string()

    def _fixture_teardown(self):
        browser_fixture.ContractBillingBrowserTests._fixture_teardown(self)
        connections["default"].creation.deserialize_db_from_string(self.seed_contents)

    def test_reference_journeys(self):
        base = {"status": 200, "screenshot": True}
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "empty-desktop",
                    "path": self.scoped,
                    "mustText": [
                        "برای این قرارداد هنوز مبنای متره و صورت‌وضعیت ثبت نشده است."
                    ],
                    "absentText": ["مبنای جدید"],
                },
                {**base, "name": "empty-mobile", "mobile": True, "path": self.scoped},
            ],
        )
        first = self._approved_baseline()
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "single-redirect",
                    "path": reverse("contracts:detail", args=[self.contract.pk]),
                    "steps": [
                        {
                            "clickHref": self.scoped,
                            "afterPath": reverse(
                                "billing:baseline_detail", args=[first.pk]
                            ),
                        }
                    ],
                    "mustLinks": [self.scoped + "&versions=1"],
                }
            ],
        )
        self._approved_baseline()
        self._baseline()
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "global-desktop",
                    "path": self.url,
                    "mustText": ["مبنای متره و صورت‌وضعیت", "تاریخ اثر"],
                    "steps": [
                        {
                            "fill": {"status": "approved"},
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": self.url,
                        },
                        {
                            "inspect": "document.querySelectorAll('tbody tr').length===1 && !!document.querySelector('[data-filter-chip=status]')",
                            "description": "filter and active chip",
                        },
                        {
                            "clickSelector": "[data-filter-chip=status]",
                            "afterPath": self.url,
                        },
                        {
                            "clickSelector": "th a[href*='sort=version']",
                            "afterPath": self.url,
                        },
                        {
                            "inspect": "new URLSearchParams(location.search).get('sort')==='version'",
                            "description": "version sorting",
                        },
                        {
                            "toggleSelector": ".erp-list-row-menu > summary",
                            "inspect": "document.querySelector('.erp-list-row-menu').open && document.querySelector('.erp-list-row-menu a').target==='_blank' && document.querySelector('.erp-list-row-menu__items').getBoundingClientRect().top>=document.querySelector('.erp-contracts-table').getBoundingClientRect().top",
                            "description": "visible secondary detail action",
                        },
                    ],
                },
                {**base, "name": "global-mobile", "mobile": True, "path": self.url},
                {
                    **base,
                    "name": "versions-desktop",
                    "path": self.scoped,
                    "mustText": ["نسخه جاری", "جایگزین‌شده", "پیش‌نویس"],
                    "steps": [
                        {
                            "inspect": "document.querySelectorAll('tbody tr').length===3 && !document.querySelector('main [name=q]') && !document.querySelector('main [name=contract_filter]')",
                            "description": "versions without duplicate selection",
                        }
                    ],
                },
                {
                    **base,
                    "name": "versions-mobile",
                    "mobile": True,
                    "path": self.scoped,
                },
                {
                    **base,
                    "name": "history-detail",
                    "path": reverse("billing:baseline_detail", args=[first.pk]),
                    "mustText": ["جایگزین‌شده"],
                    "mustLinks": [self.scoped + "&versions=1"],
                },
            ],
        )
        reader, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["baselines.view", "contracts.view"],
            username="baseline-browser-reader",
        )
        self.browser(
            reader,
            [
                {
                    **base,
                    "name": "restricted-project",
                    "path": self.scoped,
                    "absentText": ["مبنای جدید"],
                }
            ],
        )
        denied, _, _ = scoped_reader(
            self.organization, self.project, [], username="baseline-browser-denied"
        )
        self.browser(
            denied,
            [{"name": "denied", "status": 403, "path": self.url, "screenshot": True}],
        )
