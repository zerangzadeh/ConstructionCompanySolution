"""Home real-data, source-guard and scope regression coverage."""

from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.contracts.models import Contract
from apps.daily_reports.models import DailyReport
from apps.organizations.services import (
    create_organization_with_owner,
    set_active_organization,
)
from apps.procurement.tests import ProcurementFixtureMixin
from apps.projects.models import Project, ProjectSite, ProjectStatus
from apps.projects.test_command_center import scoped_reader
from apps.workflows import test_workbench as workbench_fixture
from apps.workflows.workbench import build_workbench


class HomeWorkspaceFixture(ProcurementFixtureMixin):
    _submitted_request = workbench_fixture.WorkbenchTests._submitted_request

    def setUp(self):
        super().setUp()
        self.owner.first_name = "کاربر نمونه"
        self.owner.save(update_fields=["first_name"])
        self.organization.name = "شرکت نمونه بنیرا"
        self.organization.save(update_fields=["name"])
        self.project.name = "پروژه نمونه ساحلی"
        self.project.status = ProjectStatus.ACTIVE
        self.project.save()
        for status in ProjectStatus:
            if status != ProjectStatus.ACTIVE:
                Project.objects.create(
                    organization=self.organization,
                    code=f"HOME-{status}",
                    name=f"پروژه {status.label}",
                    status=status,
                )
        self.hidden_project = Project.objects.create(
            organization=self.organization, code="HIDDEN", name="خارج از محدوده پروژه"
        )
        Project.objects.create(
            organization=self.organization,
            code="DELETED",
            name="پروژه حذف‌شده",
            deleted_at=timezone.now(),
        )
        self.contract = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            contract_number="HOME-C",
            title="قرارداد اجرای سازه",
            counterparty_name="طرف نمونه",
            status="active",
        )
        Contract.objects.create(
            organization=self.organization,
            project=self.hidden_project,
            contract_number="HIDDEN-C",
            title="قرارداد خارج از محدوده",
            counterparty_name="طرف نمونه",
            status="active",
        )
        Contract.objects.create(
            organization=self.other_organization,
            project=self.other_project,
            contract_number="OTHER-C",
            title="قرارداد سازمان دیگر",
            counterparty_name="نمونه",
            status="active",
        )
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="HOME-S",
            name="کارگاه نمونه",
        )
        self.report = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=site,
            reporting_date=date(2026, 11, 3),
            work_performed="اجرای سازه",
        )
        self.request_record = self._submitted_request("HOME-PR")
        self.reader, self.reader_role, self.reader_grant = scoped_reader(
            self.organization,
            self.project,
            [
                "projects.view",
                "contracts.view",
                "daily_reports.view",
                "work_items.view",
            ],
            username="home-scoped-reader",
        )
        self.login(self.owner)

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class HomeWorkspaceTests(HomeWorkspaceFixture, TestCase):
    def test_counts_chart_and_workbench_use_real_visible_sources(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.context["workspace"]
        self.assertEqual(data["project_total"], 6)
        self.assertEqual(
            {row["status"]: row["value"] for row in data["status_rows"]},
            {"planning": 2, "active": 1, "on_hold": 1, "completed": 1, "cancelled": 1},
        )
        metrics = {item.route: item.value for item in data["kpis"]}
        self.assertEqual(metrics["contracts:list"], 2)
        self.assertEqual(metrics["daily_reports:list"], 1)
        self.assertEqual(metrics["procurement:request_list"], 1)
        self.assertEqual(
            data["task_total"],
            build_workbench(
                actor=self.owner, organization=self.organization, params={}
            ).counts.all_items,
        )
        self.assertGreater(data["task_total"], 0)
        self.assertNotContains(response, "قرارداد سازمان دیگر")
        self.assertNotContains(response, "پروژه حذف‌شده")
        self.assertContains(response, "chartjs-4.6.1/chart.umd.min.js")

    def test_project_scope_applies_to_counts_chart_recent_records_and_links(self):
        self.login(self.reader)
        response = self.client.get("/")
        data = response.context["workspace"]
        self.assertEqual(data["project_total"], 1)
        self.assertEqual(sum(row["value"] for row in data["status_rows"]), 1)
        self.assertEqual(
            {item.route: item.value for item in data["kpis"]}["contracts:list"], 1
        )
        self.assertNotContains(response, "خارج از محدوده")
        self.assertNotContains(response, "قرارداد سازمان دیگر")
        self.assertNotContains(response, 'data-home-metric="procurement:request_list"')
        self.assertFalse(data["tasks"])

    def test_recent_records_use_actual_timestamps_and_readable_destinations(self):
        data = self.client.get("/").context["workspace"]
        self.assertLessEqual(len(data["recent"]), 6)
        self.assertEqual(
            [r.at for r in data["recent"]],
            sorted([r.at for r in data["recent"]], reverse=True),
        )
        for item in data["recent"]:
            self.assertEqual(self.client.get(item.url).status_code, 200, item.url)
        for item in data["tasks"]:
            self.assertEqual(
                self.client.get(item.source_url).status_code, 200, item.source_url
            )

    def test_source_denial_cannot_be_overridden_by_navigation(self):
        with patch(
            "core.home_workspace.get_organization_projects",
            side_effect=PermissionDenied,
        ):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["workspace"]["status_rows"])
        self.assertNotContains(response, 'data-home-metric="projects:list"')

    def test_empty_organization_has_truthful_zero_counts_and_no_donut(self):
        empty = create_organization_with_owner(
            owner=self.owner, name="سازمان خالی نمونه", slug="home-empty"
        )
        session = self.client.session
        set_active_organization(session, empty)
        session.save()
        response = self.client.get("/")
        data = response.context["workspace"]
        self.assertEqual(data["project_total"], 0)
        self.assertFalse(data["charts"])
        self.assertTrue(all(metric.value == 0 for metric in data["kpis"]))
        self.assertContains(response, "پروژه‌ای برای نمایش وجود ندارد.")
        self.assertNotContains(response, self.project.name)

    def test_active_organization_switch_replaces_all_home_data(self):
        other = create_organization_with_owner(
            owner=self.owner, name="شرکت دوم نمونه", slug="home-switch"
        )
        Project.objects.create(
            organization=other,
            code="SWITCH",
            name="پروژه سازمان دوم",
            status="completed",
        )
        session = self.client.session
        set_active_organization(session, other)
        session.save()
        response = self.client.get("/")
        self.assertEqual(response.context["workspace"]["project_total"], 1)
        self.assertContains(response, "پروژه سازمان دوم")
        self.assertNotContains(response, self.contract.title)
        self.assertNotContains(response, self.project.name)

    def test_product_surface_hides_project_facts_and_chart(self):
        from core.product_surface import route_exposed

        with patch(
            "core.home_workspace.route_exposed",
            side_effect=lambda route: (
                False if route.startswith("projects:") else route_exposed(route)
            ),
        ):
            response = self.client.get("/")
        self.assertIsNone(response.context["workspace"]["status_rows"])
        self.assertFalse(
            any(
                item.family == "پروژه"
                for item in response.context["workspace"]["recent"]
            )
        )

    def test_all_home_destinations_remain_authorized(self):
        data = self.client.get("/").context["workspace"]
        for metric in data["kpis"]:
            self.assertEqual(
                self.client.get(reverse(metric.route)).status_code, 200, metric.route
            )
        for quick in data["quick_links"]:
            self.assertEqual(
                self.client.get(reverse(quick["link"].route)).status_code,
                200,
                quick["link"].route,
            )
