"""Read-only list regressions and real Chrome evidence on isolated PostgreSQL."""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as chrome_fixture
from apps.daily_reports import tests as daily_fixture
from apps.daily_reports.models import DailyReport
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.test_command_center import scoped_reader
from tests.retirement_fixtures import explicit_fixture_roles


def authorized_daily_fixture(test):
    """Retain original domain assertions with explicit current test authority."""
    assert connections["default"].settings_dict["NAME"].startswith("test_")
    original = daily_fixture.create_project

    def authorized_project(**kwargs):
        explicit_fixture_roles(kwargs["organization"])
        return original(**kwargs)

    with patch.object(daily_fixture, "create_project", side_effect=authorized_project):
        daily_fixture.DailyReportServiceTests.setUp(test)
    explicit_fixture_roles(test.other_organization)


class DailyListFixture:
    def setUp(self):
        authorized_daily_fixture(self)
        self.project.name = "ساختمان اداری آفتاب"
        self.project.save()
        self.site.name = "کارگاه اصلی پروژه"
        self.site.save()
        self.phase.name = "عملیات زیرسازی و سازه"
        self.phase.save()
        self.owner.first_name = "علی"
        self.owner.last_name = "رضایی"
        self.owner.save()
        self.url = reverse("daily_reports:list")
        self.login(self.owner)

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

    def report(self, index=0, status="draft", **kwargs):
        # Synthetic test fixtures only, never seed the configured development DB.
        return DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=self.site,
            phase=self.phase,
            reporting_date=date(2026, 9, 30) - timedelta(days=index),
            work_performed="آرماتوربندی و بتن‌ریزی فونداسیون",
            labor_count=12 + index,
            status=status,
            created_by=self.owner,
            **kwargs,
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DailyListTests(DailyListFixture, TestCase):
    def test_summary_filters_jalali_and_legacy_urls(self):
        draft = self.report()
        self.report(1, "submitted")
        self.report(2, "approved")
        response = self.client.get(self.url, {"status": "draft"})
        self.assertEqual(response.context["reports"], [draft])
        self.assertEqual(
            response.context["summary"],
            {
                "total": 3,
                "draft": 1,
                "submitted": 1,
                "approved": 1,
            },
        )
        for query in (
            {"q": "آرماتوربندی", "site_filter": self.site.pk},
            {"project_filter": self.project.pk, "phase_filter": self.phase.pk},
            {
                "project": self.site.name,
                "phase": self.phase.name,
                "author": self.owner.username,
            },
        ):
            self.assertEqual(
                self.client.get(self.url, query).context["page_obj"].paginator.count, 3
            )
        response = self.client.get(
            self.url,
            {
                "reporting_date_from": "۱۴۰۵/۰۷/۰۸",
                "reporting_date_to": "1405/07/08",
            },
        )
        self.assertEqual(response.context["reports"], [draft])
        self.assertEqual(len(response.context["filter_bar"]["chips"]), 2)
        for query in (
            {"status": "invalid"},
            {"project_filter": "bad"},
            {"reporting_date_from": "bad"},
            {"reporting_date_from": "2026-10-01", "reporting_date_to": "2026-09-01"},
        ):
            response = self.client.get(self.url, query)
            self.assertEqual(response.context["reports"], [])
            self.assertTrue(response.context["filter_bar"]["form"].errors)

    def test_stable_sort_pagination_chip_and_context_do_not_mutate_session(self):
        for index in range(27):
            self.report(index)
        before = dict(self.client.session)
        response = self.client.get(
            self.url,
            {
                "site_filter": self.site.pk,
                "sort": "labor_count",
                "direction": "asc",
                "page": 2,
            },
        )
        self.assertEqual(
            [row.labor_count for row in response.context["reports"]], [37, 38]
        )
        self.assertEqual(response.context["summary"]["total"], 27)
        self.assertEqual(dict(self.client.session), before)
        chip = response.context["filter_bar"]["chips"][0]
        self.assertNotIn("page=", chip["url"])
        self.assertNotIn("site_filter=", chip["url"])
        self.assertIn("sort=labor_count", chip["url"])
        self.assertContains(response, "زمینه کاری سراسری")
        self.assertContains(response, "گزارش روزانه جدید")

    def test_permission_scope_and_filter_choices_do_not_leak(self):
        visible = self.report()
        from apps.projects.services import create_project, create_project_site

        hidden_project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="HIDDEN",
            name="پروژه محرمانه",
        )
        hidden_site = create_project_site(
            organization=self.organization,
            project=hidden_project,
            actor=self.owner,
            code="HIDDEN",
            name="کارگاه محرمانه",
        )
        DailyReport.objects.create(
            organization=self.organization,
            project=hidden_project,
            site=hidden_site,
            reporting_date=date(2026, 9, 30),
            work_performed="شرح محرمانه",
            labor_count=99,
        )
        reader, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["daily_reports.view"],
            username="daily-list-reader",
        )
        self.login(reader)
        response = self.client.get(self.url)
        self.assertEqual(response.context["reports"], [visible])
        self.assertEqual(response.context["summary"]["total"], 1)
        self.assertNotContains(response, hidden_project.name)
        self.assertNotContains(response, "گزارش روزانه جدید")
        for query in (
            {"project_filter": hidden_project.pk},
            {"site_filter": hidden_site.pk},
        ):
            self.assertEqual(self.client.get(self.url, query).context["reports"], [])
        self.login(self.other_user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.other_organization.pk)
        session.save()
        response = self.client.get(self.url)
        self.assertEqual(response.context["summary"]["total"], 0)
        self.assertNotContains(response, self.project.name)
        self.login(reader)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.other_organization.pk)
        session.save()
        self.assertNotEqual(self.client.get(self.url).status_code, 200)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    PRODUCT_SURFACE_PROFILE="FULL_ERP",
)
class DailyReportCurrentAuthorityRegressionTests(daily_fixture.DailyReportServiceTests):
    """Exercise the original report contract with current grants in FULL_ERP."""

    def setUp(self):
        authorized_daily_fixture(self)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DailyListChromeTests(DailyListFixture, StaticLiveServerTestCase):
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2]
        / "output/daily-reports-list-reference/browser"
    )

    @classmethod
    def _fixture_setup(cls):
        super()._fixture_setup()
        cls.seed_contents = connections["default"].creation.serialize_db_to_string()

    def _fixture_teardown(self):
        chrome_fixture.ContractBillingBrowserTests._fixture_teardown(self)
        connections["default"].creation.deserialize_db_from_string(self.seed_contents)

    def test_desktop_mobile_interactions_and_empty_states(self):
        base = {
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
        }
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "empty-desktop",
                    "path": self.url,
                    "mustText": ["هنوز گزارش روزانه‌ای ثبت نشده است"],
                },
                {**base, "name": "empty-mobile", "mobile": True, "path": self.url},
            ],
        )
        for index in range(27):
            self.report(index, ("draft", "submitted", "approved")[index % 3])
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "desktop",
                    "path": self.url,
                    "steps": [
                        {
                            "inspect": "document.querySelectorAll('tbody tr').length===25 && document.querySelector('[data-summary=total]').textContent==='27'",
                            "description": "real summary and first page",
                        },
                        {
                            "clickSelector": ".erp-list-pages a[rel=next]",
                            "afterPath": self.url,
                        },
                        {
                            "inspect": "document.querySelectorAll('tbody tr').length===2",
                            "description": "second page",
                        },
                        {
                            "fill": {"status": "submitted"},
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": self.url,
                        },
                        {
                            "inspect": "document.querySelectorAll('tbody tr').length===9 && !!document.querySelector('[data-filter-chip=status]') && (new URLSearchParams(location.search).get('page') || '1')==='1'",
                            "description": "filter resets page with visible chip",
                        },
                        {
                            "clickSelector": "[data-filter-chip=status]",
                            "afterPath": self.url,
                        },
                        {
                            "clickSelector": "th a[href*='sort=labor_count']",
                            "afterPath": self.url,
                        },
                        {
                            "toggleSelector": ".erp-list-row-menu > summary",
                            "inspect": "document.querySelector('.erp-list-row-menu').open && document.querySelector('.erp-list-row-menu__items').getBoundingClientRect().top>=0",
                            "description": "visible row action",
                        },
                    ],
                },
                {**base, "name": "desktop-reference", "path": self.url, "height": 1100},
                {
                    **base,
                    "name": "mobile",
                    "path": self.url,
                    "mobile": True,
                    "steps": [
                        {
                            "inspect": "getComputedStyle(document.querySelector('.daily-summary')).gridTemplateColumns.split(' ').length===2 && getComputedStyle(document.querySelector('tbody tr')).display==='grid'",
                            "description": "responsive KPI and report cards",
                        },
                        {"toggleSelector": "[data-filter-options] > summary"},
                        {
                            "fill": {"status": "approved"},
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": self.url,
                        },
                        {
                            "inspect": "!!document.querySelector('[data-filter-chip=status]') && !document.querySelector('[data-filter-options]').open",
                            "description": "collapsed filters keep active chip visible",
                        },
                    ],
                },
                {
                    **base,
                    "name": "mobile-reference",
                    "path": self.url,
                    "mobile": True,
                    "viewportScreenshot": True,
                },
                {**base, "name": "tablet", "path": self.url, "width": 1024},
                {
                    **base,
                    "name": "narrow-mobile",
                    "path": self.url,
                    "width": 360,
                    "mobile": True,
                },
                {
                    **base,
                    "name": "no-results",
                    "path": self.url + "?q=nomatchingreport",
                    "mustText": ["گزارشی با این فیلترها یافت نشد"],
                },
                {
                    **base,
                    "name": "advanced",
                    "path": self.url,
                    "steps": [
                        {"toggleSelector": "[data-more-toggle]"},
                        {
                            "fill": {
                                "phase_filter": str(self.phase.pk),
                                "reporting_date_from": "1405/07/08",
                                "reporting_date_to": "1405/07/08",
                            },
                            "clickSelector": ".erp-list-more__actions button",
                            "afterPath": self.url,
                        },
                        {
                            "inspect": "document.querySelectorAll('tbody tr').length===1 && document.querySelectorAll('[data-filter-chip]').length===3",
                            "description": "Jalali date and phase filters",
                        },
                    ],
                },
                {**base, "name": "no-javascript", "path": self.url, "noJS": True},
            ],
        )
