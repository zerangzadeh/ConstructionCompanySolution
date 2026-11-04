"""Read-model integrity and isolation for Projects List / Command Center."""

import json
from datetime import date
from html.parser import HTMLParser
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract
from apps.daily_reports.models import DailyReport
from apps.estimates.services import create_estimate
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationRole,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects import test_p4_budget_preparation as budget_fixture
from apps.projects import test_p4_integrated_cost as cost_fixture
from apps.projects.models import (
    Project,
    ProjectCostFactKind,
    ProjectCostMeasure,
    ProjectSite,
)
from tests.retirement_fixtures import explicit_fixture_roles


class ChartParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.data = ""

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "project-dashboard-data":
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.data += data


def chart_payload(response):
    parser = ChartParser()
    parser.feed(response.content.decode())
    return json.loads(parser.data)


def scoped_reader(organization, project, permissions, *, username="dashboard-reader"):
    user = User.objects.create_user(username=username)
    role = OrganizationRole.objects.create(
        organization=organization, code=username, name="خواننده پروژه"
    )
    role.permissions.add(*BusinessPermission.objects.filter(code__in=permissions))
    membership = organization.memberships.create(
        user=user, status="active", role_definition=role
    )
    MembershipRoleAssignment.objects.create(
        organization=organization,
        membership=membership,
        role=role,
        reason="Explicit test authority",
    )
    grant = MembershipScopeGrant.objects.create(
        organization=organization,
        membership=membership,
        scope_type="project",
        project=project,
        reason="Explicit test scope",
    )
    return user, role, grant


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CommandCenterTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture(persian=True)
        self.login(self.owner)
        self.project.name = "پروژه مرجع ساحلی"
        self.project.start_date = date(2026, 10, 1)
        self.project.save()
        self.detail = reverse("projects:detail", args=[self.project.pk])

    def test_status_summary_uses_all_authorized_projects_before_filter_and_pagination(
        self,
    ):
        listing = reverse("projects:list")
        Project.objects.bulk_create(
            [
                Project(
                    organization=self.organization,
                    code=f"PAGE-{i}",
                    name=f"پروژه {i}",
                    status="active",
                )
                for i in range(30)
            ]
        )
        for status in ("on_hold", "completed", "cancelled"):
            Project.objects.create(
                organization=self.organization, code=status, name=status, status=status
            )
        Project.objects.create(
            organization=self.organization,
            code="DELETED",
            name="حذف‌شده",
            status="active",
            deleted_at=timezone.now(),
        )
        other = Organization.objects.create(name="Other", slug="summary-other")
        Project.objects.create(
            organization=other, code="FOREIGN", name="بیگانه", status="active"
        )
        response = self.client.get(listing)
        expected = {
            "planning": "1",
            "active": "30",
            "on_hold": "1",
            "completed": "1",
            "cancelled": "1",
        }
        rows = response.context["project_status_rows"]
        self.assertEqual({row["status"]: row["value"] for row in rows}, expected)
        self.assertEqual(response.context["project_total"], 34)
        self.assertLess(len(response.context["projects"]), 34)
        payload = chart_payload(response)
        self.assertEqual(payload[0]["rows"], rows)
        filtered = self.client.get(
            listing, {"q": "no-match", "status": "completed", "page": "2"}
        )
        self.assertEqual(filtered.context["project_total"], 34)
        self.assertEqual(chart_payload(filtered), payload)
        self.assertNotContains(response, "خروجی اکسل")
        self.assertNotContains(response, ">چاپ<")
        user, _, _ = scoped_reader(self.organization, self.project, ["projects.view"])
        self.login(user)
        response = self.client.get(listing)
        self.assertEqual(response.context["project_total"], 1)
        self.assertEqual(
            {
                row["status"]: row["value"]
                for row in response.context["project_status_rows"]
            },
            {**dict.fromkeys(expected, "0"), "planning": "1"},
        )
        self.project.deleted_at = timezone.now()
        self.project.save(update_fields=["deleted_at"])
        response = self.client.get(listing)
        self.assertEqual(response.context["project_total"], 0)
        self.assertEqual(chart_payload(response), [])
        self.assertNotContains(response, '<canvas id="projects-status-chart"')
        self.assertContains(response, "هنوز پروژه‌ای برای نمایش نمودار وجود ندارد.")

    def test_list_search_chips_dates_and_scope(self):
        listing = reverse("projects:list")
        for query in (
            {"q": "ساحلی"},
            {"q": self.project.code},
            {"start_date_from": "2026-10-01"},
        ):
            response = self.client.get(listing, query)
            self.assertEqual(response.context["projects"], [self.project])
            self.assertEqual(response.context["filter_bar"]["active_count"], 1)
        response = self.client.get(listing, {"status": "invalid"})
        self.assertEqual(response.context["projects"], [])
        self.assertContains(response, "وضعیت معتبر انتخاب کنید.")
        response = self.client.get(listing, {"start_date_from": "bad"})
        self.assertEqual(response.context["projects"], [])
        user, _, _ = scoped_reader(self.organization, self.project, ["projects.view"])
        Project.objects.create(
            organization=self.organization, code="SIBLING", name="پروژه پنهان"
        )
        self.login(user)
        response = self.client.get(listing)
        self.assertEqual(response.context["projects"], [self.project])
        self.assertNotContains(response, "پروژه پنهان")
        self.assertNotContains(response, "پروژه جدید")

    def test_dashboard_sources_commercial_links_and_no_inferred_progress(self):
        create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            estimate_number="CENTER-E",
            title="برآورد ساحلی",
        )
        self._claim()
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="CENTER-S",
            name="کارگاه ساحلی",
        )
        DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=site,
            reporting_date=date(2026, 10, 1),
            work_performed="اجرای سازه",
            created_by=self.owner,
        )
        before = dict(self.client.session)
        response = self.client.get(self.detail)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(dict(self.client.session), before)
        self.assertEqual(
            [item.total for item in response.context["commercial_summary"]], [1, 1, 1]
        )
        self.assertEqual(response.context["dashboard"]["reports_count"], 1)
        self.assertContains(response, "آخرین موارد ثبت‌شده")
        self.assertContains(response, "کارگاه ساحلی")
        payload = chart_payload(response)
        contract_chart = next(
            item for item in payload if item["id"] == "project-contracts-chart"
        )
        self.assertEqual(contract_chart["rows"], [{"label": "فعال", "value": "1"}])
        self.assertNotIn("progress", str(payload))
        self.assertContains(
            response, "پیشرفت برنامه‌ای و واقعی قابل اتکای پروژه ثبت نشده است"
        )
        self.assertNotContains(response, '<canvas id="project-cost-chart"')
        self.assertContains(response, "پوشش ناقص")

    def test_restricted_metrics_never_load_or_leak_and_context_is_isolated(self):
        user, role, grant = scoped_reader(
            self.organization, self.project, ["projects.view"]
        )
        self.login(user)
        with patch(
            "apps.projects.dashboard.get_project_cost_projection",
            side_effect=AssertionError("Unauthorized cost load"),
        ):
            response = self.client.get(self.detail)
        self.assertEqual(response.context["commercial_summary"], ())
        self.assertEqual(response.context["dashboard"]["charts"], [])
        self.assertIsNone(response.context["cost_projection"])
        self.assertEqual(len(response.context["dashboard"]["kpis"]), 1)
        self.assertNotContains(response, "project-contracts-chart")
        self.assertNotContains(response, "هزینه ثبت‌شده")
        self.assertNotContains(response, 'id="commercial-summary"')
        self.assertEqual(chart_payload(response), [])
        role.permissions.add(BusinessPermission.objects.get(code="contracts.view"))
        response = self.client.get(self.detail)
        self.assertEqual(len(response.context["commercial_summary"]), 1)
        self.assertFalse(response.context["commercial_summary"][0].create_url)
        sibling = Project.objects.create(
            organization=self.organization, code="SECRET", name="داده پنهان"
        )
        grant.project = sibling
        grant.save()
        self.assertEqual(self.client.get(self.detail).status_code, 403)
        foreign_org = Organization.objects.create(name="Other", slug="center-other")
        foreign = Project.objects.create(
            organization=foreign_org, code="FOREIGN", name="پروژه بیگانه"
        )
        self.assertEqual(
            self.client.get(reverse("projects:detail", args=[foreign.pk])).status_code,
            403,
        )

    def test_surface_hidden_sources_and_links_are_omitted(self):
        with (
            patch("apps.projects.dashboard.route_exposed", return_value=False),
            patch("apps.projects.business_hub.route_exposed", return_value=False),
        ):
            response = self.client.get(self.detail)
        self.assertEqual(response.context["dashboard"]["charts"], [])
        self.assertEqual(response.context["dashboard"]["quick_links"], [])
        self.assertEqual(response.context["commercial_summary"], ())
        self.assertIsNone(response.context["cost_projection"])

    def test_sibling_and_foreign_records_do_not_enter_charts_or_recent(self):
        sibling = Project.objects.create(
            organization=self.organization, code="SIBLING", name="دیگر"
        )
        Contract.objects.create(
            organization=self.organization,
            project=sibling,
            contract_number="SECRET",
            title="قرارداد پنهان",
            counterparty_name="محرمانه",
            status="active",
        )
        response = self.client.get(self.detail)
        self.assertNotContains(response, "قرارداد پنهان")
        self.assertEqual(response.context["commercial_summary"][1].total, 1)
        empty = self.client.get(reverse("projects:detail", args=[sibling.pk]))
        self.assertContains(empty, "شواهد هم‌ارز کافی")


class CostEvidenceFixture:
    _draft = cost_fixture.IntegratedProjectCostTests._draft
    _classify_and_submit = cost_fixture.IntegratedProjectCostTests._classify_and_submit
    _contract = cost_fixture.IntegratedProjectCostTests._contract
    _fact = cost_fixture.IntegratedProjectCostTests._fact

    def make_cost_fixture(self):
        # Reuse the real accepted-budget / producer workflow with explicit
        # current role assignments, instead of relying on legacy role fields.
        create_project = budget_fixture.create_project

        def authorized_project(**kwargs):
            explicit_fixture_roles(kwargs["organization"])
            return create_project(**kwargs)

        with patch.object(
            budget_fixture, "create_project", side_effect=authorized_project
        ):
            cost_fixture.IntegratedProjectCostTests.setUp(self)
        self.organization.currency = "IRR"
        self.organization.save()
        self.client.force_login(self.preparer)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CommandCenterCostTests(CostEvidenceFixture, TestCase):
    def setUp(self):
        self.make_cost_fixture()

    def test_commitment_evidence_does_not_fabricate_a_zero_actual_cost(self):
        source = self._contract(ProjectCostMeasure.COMMITMENT)
        self._fact(
            source,
            ProjectCostFactKind.COMMITMENT_AUTHORIZED,
            "50.00",
            "CENTER-COMMITMENT",
        )
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertFalse(response.context["dashboard"]["cost_comparable"])
        self.assertNotIn(
            "project-cost-chart", [chart["id"] for chart in chart_payload(response)]
        )
        self.assertIsNone(response.context["dashboard"]["kpis"][1]["value"])

    def test_exact_projection_and_currency_guard_without_legacy_budget_substitution(
        self,
    ):
        source = self._contract(ProjectCostMeasure.ACTUAL)
        self._fact(
            source, ProjectCostFactKind.ACTUAL_RECOGNIZED, "123.45", "CENTER-COST"
        )
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        chart = next(
            item
            for item in chart_payload(response)
            if item["id"] == "project-cost-chart"
        )
        self.assertEqual(
            chart["rows"],
            [
                {"label": "بودجه تخمینی", "value": "999.00"},
                {"label": "هزینه ثبت‌شده", "value": "123.45"},
            ],
        )
        self.assertFalse(response.context["cost_projection"].coverage_complete)
        self.assertContains(response, "پوشش ناقص")
        self.assertNotEqual(chart["rows"][1]["value"], str(self.project.actual_budget))
        # Legacy currency mismatch is a read-model guard, never a conversion.
        self.organization.currency = "USD"
        self.organization.save()
        response = self.client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertFalse(response.context["dashboard"]["cost_comparable"])
        self.assertNotIn(
            "project-cost-chart", [item["id"] for item in chart_payload(response)]
        )
