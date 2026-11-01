"""Certificate list behavior and real Chrome evidence; isolated PostgreSQL only."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing import test_payable_certificates as payable_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.organizations.models import Organization


class PayableListFixture:
    def setUp(self):
        from apps.organizations.catalog_bootstrap import (
            synchronize_authorization_catalog,
        )
        from apps.workflows.catalog_bootstrap import synchronize_workflow_catalog
        from tests.retirement_fixtures import explicit_fixture_roles

        assert connections["default"].settings_dict["NAME"].startswith("test_")
        synchronize_authorization_catalog(using="default")
        synchronize_workflow_catalog(using="default")
        original = payable_fixture.create_project
        original_party = payable_fixture.create_business_party

        def named_party(**kwargs):
            kwargs["display_name"] = "شرکت سازه گستر جنوب"
            return original_party(**kwargs)

        def authorized_project(**kwargs):
            explicit_fixture_roles(kwargs["organization"])
            return original(**kwargs)

        with (
            patch.object(
                payable_fixture, "create_project", side_effect=authorized_project
            ),
            patch.object(
                payable_fixture, "create_business_party", side_effect=named_party
            ),
        ):
            payable_fixture.PayableCertificateTests.setUp(self)

    _measurement = payable_fixture.PayableCertificateTests._measurement
    _certificate = payable_fixture.PayableCertificateTests._certificate
    _approve = payable_fixture.PayableCertificateTests._approve
    login = JourneyFixture.login

    def make_rows(self):
        self.project.name = "پروژه اجرای سازه"
        self.project.save(update_fields=["name"])
        self._measurement()
        first = self._approve(self._certificate())
        self._measurement(
            measured_on=date(2026, 2, 15),
            period=Decimal("2.0000"),
            cumulative=Decimal("7.0000"),
        )
        second = self._certificate(
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            cutoff=date(2026, 2, 28),
        )
        from apps.billing.payable_services import submit_payable_certificate

        submit_payable_certificate(
            organization=self.organization, actor=self.owner, certificate=second
        )
        self._measurement(
            measured_on=date(2026, 3, 15),
            period=Decimal("1.0000"),
            cumulative=Decimal("8.0000"),
        )
        third = self._certificate(
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            cutoff=date(2026, 3, 31),
        )
        return first, second, third


class PayableListTests(PayableListFixture, TestCase):
    test_existing_calculations = payable_fixture.PayableCertificateTests.test_measurement_calculation_caps_back_charge_and_stable_line
    test_existing_workflow = payable_fixture.PayableCertificateTests.test_workflow_candidacy_sod_immutability_and_audit

    def test_filters_sorting_chips_and_invalid_choices(self):
        first, _second, third = self.make_rows()
        self.login(self.owner)
        url = reverse("billing:payable_certificate_list")
        response = self.client.get(
            url,
            {
                "status": "approved",
                "contract": self.contract.pk,
                "sort": "net",
                "direction": "desc",
            },
        )
        self.assertEqual(list(response.context["certificates"]), [first])
        self.assertEqual(len(response.context["filter_bar"]["chips"]), 2)
        self.assertContains(response, "گواهی‌های پرداخت پیمانکار جزء")
        self.assertContains(response, "⋮", count=1)
        self.assertNotContains(response, "حذف گواهی")
        for query in (
            {"status": "invented"},
            {"contract": "bad-uuid"},
            {
                "contract": Organization.objects.create(
                    name="Other", slug="other-list"
                ).pk
            },
            {"period": "bad"},
            {"number": "9999999999999999999"},
        ):
            response = self.client.get(url, query)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["page_obj"].paginator.count, 0)
        for query, expected in (
            ({"q": "SUB-001"}, 3),
            ({"number": third.certificate_number}, 1),
            ({"period": "2026-02-01/2026-02-28"}, 1),
            ({"q": "missing"}, 0),
        ):
            self.assertEqual(
                self.client.get(url, query).context["page_obj"].paginator.count,
                expected,
            )
        response = self.client.get(url, {"sort": "number", "direction": "desc"})
        self.assertEqual(response.context["certificates"][0], third)

    def test_pagination_retains_filters_and_scope(self):
        for index in range(26):
            year, month = 2026 + index // 12, index % 12 + 1
            self._certificate(
                period_start=date(year, month, 1),
                period_end=date(year, month, 28),
                cutoff=date(year, month, 28),
            )
        self.login(self.owner)
        response = self.client.get(
            reverse("billing:payable_certificate_list"),
            {
                "contract": self.contract.pk,
                "sort": "number",
                "direction": "asc",
                "page": "2",
            },
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        self.assertEqual(len(response.context["certificates"]), 1)
        self.assertEqual(response.context["certificates"][0].certificate_number, 26)
        self.assertIn("sort=number", response.context["pagination_query"])
        self.assertIn(str(self.contract.pk), response.context["pagination_query"])

    def test_existing_scope_permissions_and_create_visibility(self):
        self._certificate()
        from apps.projects.test_command_center import scoped_reader

        denied, _role, _grant = scoped_reader(
            self.organization, self.project, [], username="payable-list-denied"
        )
        self.login(denied)
        self.assertEqual(
            self.client.get(reverse("billing:payable_certificate_list")).status_code,
            403,
        )
        self.login(self.owner)
        with patch(
            "apps.billing.payable_list.has_business_permission", return_value=False
        ):
            response = self.client.get(reverse("billing:payable_certificate_list"))
        self.assertNotContains(response, 'href="/billing/payable-certificates/new/"')
        from apps.billing.payable_services import get_payable_certificates

        other = Organization.objects.create(name="Other", slug="other-list-scope")
        other.memberships.create(user=self.owner, role="company_owner", status="active")
        from tests.retirement_fixtures import explicit_fixture_roles

        explicit_fixture_roles(other)
        self.assertFalse(
            get_payable_certificates(actor=self.owner, organization=other).exists()
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PayableListBrowserTests(PayableListFixture, StaticLiveServerTestCase):
    serialized_rollback = False
    browser = browser_fixture.ContractBillingBrowserTests.browser

    @classmethod
    def _fixture_setup(cls):
        super()._fixture_setup()
        cls.seed_contents = connections["default"].creation.serialize_db_to_string()

    def _fixture_teardown(self):
        # Restore migration seeds into empty tables, preserving published-history
        # guards and making this dedicated test database reusable on another run.
        browser_fixture.ContractBillingBrowserTests._fixture_teardown(self)
        connections["default"].creation.deserialize_db_from_string(self.seed_contents)

    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/payable-list-reference/browser"
    )

    def test_reference_desktop_mobile(self):
        self.make_rows()
        url = reverse("billing:payable_certificate_list")
        base = {
            "status": 200,
            "screenshot": True,
            "mustText": ["گواهی‌های پرداخت پیمانکار جزء"],
            "absentText": ["UUID", "None"],
        }
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "desktop",
                    "path": url,
                    "steps": [
                        {
                            "inspect": "document.querySelectorAll('tbody tr').length===3 && document.querySelectorAll('thead th').length===10 && document.querySelector('.erp-list-identifier bdi').dir==='ltr'",
                            "description": "real source columns, rows and directional isolation",
                        },
                    ],
                },
                {
                    **base,
                    "name": "desktop-menu",
                    "path": url,
                    "steps": [
                        {
                            "toggleSelector": ".erp-list-row-menu > summary",
                            "inspect": "document.querySelector('.erp-list-row-menu').open && document.querySelector('.erp-list-row-menu a').target==='_blank'",
                            "description": "Contracts secondary navigation menu",
                        },
                    ],
                },
                {
                    **base,
                    "name": "desktop-filters",
                    "path": url,
                    "steps": [
                        {
                            "toggleSelector": "[data-more-toggle]",
                            "inspect": "document.querySelector('[data-more-filters]').open",
                            "description": "advanced filters open",
                        },
                        {
                            "fill": {"status": "approved"},
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": url,
                        },
                        {
                            "inspect": "document.querySelectorAll('tbody tr').length===1 && !!document.querySelector('[data-filter-chip=status]')",
                            "description": "approved filter and chip",
                        },
                        {
                            "clickSelector": "[data-filter-chip=status]",
                            "afterPath": url,
                        },
                        {
                            "inspect": "document.querySelectorAll('tbody tr').length===3",
                            "description": "clear chip restores permitted results",
                        },
                        {"clickSelector": "th a[href*='sort=net']", "afterPath": url},
                        {
                            "inspect": "new URLSearchParams(location.search).get('sort')==='net'",
                            "description": "allowlisted sorting",
                        },
                    ],
                },
                {
                    **base,
                    "name": "mobile",
                    "mobile": True,
                    "bottomScreenshot": True,
                    "path": url,
                    "steps": [
                        {
                            "inspect": "getComputedStyle(document.querySelector('tbody tr')).display==='grid' && document.querySelector('tbody tr').getBoundingClientRect().width<innerWidth",
                            "description": "mobile cards fit viewport",
                        },
                    ],
                },
                {
                    **base,
                    "name": "mobile-menu",
                    "mobile": True,
                    "path": url,
                    "steps": [
                        {
                            "toggleSelector": ".erp-list-row-menu > summary",
                            "inspect": "(() => { const r=document.querySelector('.erp-list-row-menu__items').getBoundingClientRect(); return r.left>=0 && r.right<=innerWidth; })()",
                            "description": "mobile menu stays inside viewport",
                        },
                    ],
                },
                {
                    "status": 200,
                    "screenshot": True,
                    "name": "empty-filter",
                    "path": url + "?q=nonexistent",
                },
            ],
        )
