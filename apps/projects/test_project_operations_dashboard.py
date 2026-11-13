"""Project operations hierarchy and the authorized Equipment handoff."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.billing.test_mvp03 import JourneyFixture
from apps.equipment.models import Equipment, EquipmentAssignment
from apps.equipment.p8_models import EquipmentUsageLog
from apps.organizations.models import BusinessPermission
from apps.projects.models import Activity, Project, WBSNode
from apps.projects.test_command_center import scoped_reader


class ProjectOperationsDashboardTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture(persian=True)
        from apps.organizations.models import OrganizationSettings

        OrganizationSettings.objects.get_or_create(organization=self.organization)
        self.organization.memberships.get(
            user=self.owner
        ).role_definition.permissions.add(
            *BusinessPermission.objects.filter(is_active=True)
        )
        self.login(self.owner)
        self.detail = reverse("projects:detail", args=[self.project.pk])
        self.sibling = Project.objects.create(
            organization=self.organization, code="OPS-SIBLING", name="پروژه دیگر"
        )

    def equipment_source(self, project, code):
        equipment = Equipment.objects.create(
            organization=self.organization, code=code, name=code, category="ماشین‌آلات"
        )
        assignment = EquipmentAssignment.objects.create(
            organization=self.organization,
            equipment=equipment,
            project=project,
            start_date=timezone.localdate() - timedelta(days=2),
            status="active",
        )
        usage = EquipmentUsageLog.objects.create(
            organization=self.organization,
            equipment=equipment,
            deployment=assignment,
            started_at=timezone.now() - timedelta(hours=2),
            ended_at=timezone.now(),
            runtime_hours=Decimal(2),
            source_key=code,
            created_by=self.owner,
        )
        return equipment, assignment, usage

    def test_hierarchy_rollup_is_scoped_bounded_and_includes_deeper_descendants(self):
        from apps.projects.dashboard import _work_preview
        from apps.projects.services import (
            get_organization_activities,
            get_organization_wbs_nodes,
        )

        root = WBSNode.objects.create(
            organization=self.organization,
            project=self.project,
            code="01",
            title="بسته ریشه",
        )
        child = WBSNode.objects.create(
            organization=self.organization,
            project=self.project,
            parent=root,
            code="01.1",
            title="شاخه قابل مشاهده",
        )
        leaf = WBSNode.objects.create(
            organization=self.organization,
            project=self.project,
            parent=child,
            code="01.1.1",
            title="سطح سوم",
        )
        for index in range(8):
            Activity.objects.create(
                organization=self.organization,
                project=self.project,
                wbs_node=leaf,
                code=f"PREVIEW-{index}",
                name=f"فعالیت {index}",
                status="active" if index == 7 else "planning",
                planned_start_date=timezone.localdate() + timedelta(days=index),
            )
        for code in ["02", "03", "04"]:
            WBSNode.objects.create(
                organization=self.organization,
                project=self.project,
                code=code,
                title=code,
            )
        Activity.objects.create(
            organization=self.organization,
            project=self.project,
            wbs_node=leaf,
            code="ARCHIVED",
            name="فعالیت بایگانی",
            archived_at=timezone.now(),
        )
        nodes = get_organization_wbs_nodes(
            user=self.owner, organization=self.organization, project_id=self.project.pk
        )
        activities = get_organization_activities(
            user=self.owner, organization=self.organization, project_id=self.project.pk
        )
        # Query cost is constant across nodes and activity rows, with no per-row reads.
        with self.assertNumQueries(3):
            work = _work_preview(nodes, activities)
        branch = next(item for item in work["packages"] if item["pk"] == root.pk)
        self.assertEqual(branch["activity_count"], 8)
        self.assertEqual(branch["children"][0]["activity_count"], 8)
        self.assertLessEqual(len(work["packages"]), 3)
        self.assertGreaterEqual(work["more_roots"], 1)
        self.assertEqual(len(work["sample"]), 5)
        self.assertEqual(work["sample"][0].code, "PREVIEW-7")
        self.assertEqual(work["more_activities"], 3)
        response = self.client.get(self.detail)
        self.assertContains(response, "بسته ریشه")
        self.assertContains(response, "شاخه قابل مشاهده")
        self.assertNotContains(response, "فعالیت بایگانی")
        self.assertContains(response, "برنامه فعالیت:")

    def test_recent_full_business_title_and_create_only_actions_are_preserved(self):
        from apps.expenses.services import create_expense

        title = (
            "کنترل مصالح — Supplier inspection / concrete batch — "
            + "بررسی گواهی کیفیت " * 9
        ).strip()
        expense = create_expense(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            description=title,
            amount=Decimal(125000),
            incurred_on=timezone.localdate(),
        )
        before = dict(self.client.session)
        response = self.client.get(self.detail)
        item = next(
            row
            for row in response.context["dashboard"]["recent"]
            if row["kind"] == "هزینه"
        )
        self.assertEqual(item["title"], title)
        self.assertContains(response, "عنوان کامل")
        self.assertContains(response, 'class="project-recent-record__title"')
        expense.refresh_from_db()
        self.assertEqual(expense.description, title)
        self.assertEqual(dict(self.client.session), before)
        actions = response.context["dashboard"]["quick_actions"]
        self.assertEqual({item["kind"] for item in actions}, {"create"})
        self.assertEqual(
            {item["label"] for item in actions}, {"ثبت گزارش روزانه", "ثبت هزینه"}
        )
        html = response.content.decode()
        self.assertLess(
            html.index('id="project-quick-heading"'), html.index('id="recent"')
        )
        self.assertLess(
            html.index('id="recent"'), html.index('id="commercial-summary"')
        )
        self.assertContains(
            response,
            'href="' + reverse("projects:controls", args=[self.project.pk]) + '"',
            count=1,
        )

    def test_recent_timestamp_uses_the_organization_timezone(self):
        from datetime import datetime
        from datetime import timezone as datetime_timezone

        from apps.daily_reports.models import DailyReport
        from apps.projects.models import ProjectSite

        setting = self.organization.settings
        setting.timezone = "Asia/Tehran"
        setting.save(update_fields=["timezone"])
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="CLOCK",
            name="کارگاه زمان",
        )
        report = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=site,
            reporting_date=timezone.localdate(),
            work_performed="گزارش شاهد زمان",
            created_by=self.owner,
        )
        DailyReport.objects.filter(pk=report.pk).update(
            created_at=datetime(2026, 11, 12, 21, 0, tzinfo=datetime_timezone.utc)
        )
        response = self.client.get(self.detail)
        self.assertContains(response, 'datetime="2026-11-13T00:30:00+03:30"')

    def test_workplan_precedes_performance_and_uses_only_scoped_source_counts(self):
        own = WBSNode.objects.create(
            organization=self.organization,
            project=self.project,
            code="OPS",
            title="اجرا",
        )
        foreign_node = WBSNode.objects.create(
            organization=self.organization,
            project=self.sibling,
            code="SECRET",
            title="گره پنهان",
        )
        Activity.objects.create(
            organization=self.organization,
            project=self.project,
            wbs_node=own,
            code="OPS-A",
            name="فعالیت اجرا",
            status="active",
        )
        Activity.objects.create(
            organization=self.organization,
            project=self.sibling,
            wbs_node=foreign_node,
            code="SECRET-A",
            name="فعالیت پنهان",
            status="active",
        )
        response = self.client.get(self.detail)
        work = response.context["dashboard"]["work"]
        self.assertEqual(
            work["nodes"],
            WBSNode.objects.filter(
                project=self.project, archived_at__isnull=True
            ).count(),
        )
        self.assertEqual(work["active"], 1)
        self.assertNotContains(response, "فعالیت پنهان")
        html = response.content.decode()
        self.assertLess(html.index('id="overview"'), html.index('id="workplan"'))
        self.assertLess(html.index('id="workplan"'), html.index('id="progress"'))
        self.assertLess(html.index('id="progress"'), html.index('id="recent"'))
        self.assertContains(
            response,
            reverse("projects:controls", args=[self.project.pk]) + "#activities-title",
        )
        self.assertNotContains(response, 'value="0" max="100"')

    def test_restricted_workplan_does_not_query_or_expose_counts(self):
        user, _, _ = scoped_reader(
            self.organization, self.project, ["projects.view"], username="ops-limited"
        )
        self.login(user)
        with patch(
            "apps.projects.dashboard.get_organization_wbs_nodes",
            side_effect=AssertionError("Unauthorized WBS query"),
        ):
            response = self.client.get(self.detail)
        self.assertIsNone(response.context["dashboard"]["work"])
        self.assertEqual(response.context["dashboard"]["equipment_url"], "")
        self.assertNotContains(
            response, reverse("projects:controls", args=[self.project.pk])
        )

    def test_equipment_filter_export_and_detail_are_bound_to_authorized_assignments(
        self,
    ):
        own, _, _ = self.equipment_source(self.project, "OPS-EQ")
        other, _, _ = self.equipment_source(self.sibling, "OTHER-EQ")
        listing = reverse("equipment:list")
        before = dict(self.client.session)
        response = self.client.get(listing, {"project": self.project.pk})
        self.assertEqual(list(response.context["equipment"]), [own])
        self.assertEqual(dict(self.client.session), before)
        self.assertContains(response, f'name="project" value="{self.project.pk}"')
        self.assertNotContains(response, "OTHER-EQ")
        invalid = self.client.get(
            reverse("equipment:detail", args=[other.pk]), {"project": self.project.pk}
        )
        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(
            self.client.get(listing, {"project": "invalid"}).status_code, 403
        )
        exported = self.client.get(
            listing, {"project": self.project.pk, "format": "xlsx"}
        )
        self.assertEqual(exported.status_code, 200)
        import io

        from openpyxl import load_workbook

        values = str(
            list(
                load_workbook(
                    io.BytesIO(b"".join(exported.streaming_content)), read_only=True
                ).active.values
            )
        )
        self.assertIn("OPS-EQ", values)
        self.assertNotIn("OTHER-EQ", values)

    def test_operations_excludes_other_project_events_even_for_the_same_asset(self):
        own, _, usage = self.equipment_source(self.project, "OPS-SHARED")
        historical = EquipmentAssignment.objects.create(
            organization=self.organization,
            equipment=own,
            project=self.sibling,
            start_date=timezone.localdate() - timedelta(days=10),
            end_date=timezone.localdate() - timedelta(days=5),
            status="completed",
        )
        EquipmentUsageLog.objects.create(
            organization=self.organization,
            equipment=own,
            deployment=historical,
            started_at=timezone.now() - timedelta(days=8, hours=2),
            ended_at=timezone.now() - timedelta(days=8),
            runtime_hours=Decimal(2),
            source_key="OTHER-PROJECT-USAGE",
            created_by=self.owner,
        )
        response = self.client.get(
            reverse("equipment:operations_workbench"),
            {"project": self.project.pk, "equipment": own.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["usage_logs"]), [usage])
        self.assertContains(response, self.detail)

    def test_forged_sibling_and_foreign_context_cannot_expand_project_role(self):
        from apps.organizations.models import Organization

        org = Organization.objects.create(name="Foreign", slug="ops-foreign")
        foreign = Project.objects.create(
            organization=org, code="FOREIGN", name="بیگانه"
        )
        codes = list(
            BusinessPermission.objects.filter(is_active=True).values_list(
                "code", flat=True
            )
        )
        user, _, _ = scoped_reader(
            self.organization, self.project, codes, username="ops-project-reader"
        )
        self.login(user)
        own, _, _ = self.equipment_source(self.project, "PROJECT-ROLE-EQ")
        response = self.client.get(
            reverse("equipment:list"), {"project": self.project.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["equipment"]), [own])
        response = self.client.get(
            reverse("equipment:detail", args=[own.pk]), {"project": self.project.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_change_equipment"])
        self.assertFalse(response.context["can_archive_equipment"])
        response = self.client.get(
            reverse("equipment:list"), {"project": self.project.pk}
        )
        self.assertFalse(response.context["can_create_equipment"])
        self.assertEqual(self.client.get(reverse("equipment:list")).status_code, 403)
        for project in [self.sibling, foreign]:
            for route in ["equipment:list", "equipment:operations_workbench"]:
                with self.subTest(project=project.pk, route=route):
                    self.assertEqual(
                        self.client.get(
                            reverse(route), {"project": project.pk}
                        ).status_code,
                        403,
                    )

    def test_quick_create_initialization_is_authorized_and_does_not_switch_session(
        self,
    ):
        before = dict(self.client.session)
        for route in ["daily_reports:create", "expenses:create"]:
            with self.subTest(route=route):
                response = self.client.get(reverse(route), {"project": self.sibling.pk})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    str(response.context["form"]["project"].value()),
                    str(self.sibling.pk),
                )
                self.assertEqual(dict(self.client.session), before)
        user, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["projects.view", "daily_reports.create", "expenses.create"],
            username="ops-creator",
        )
        self.login(user)
        for route in ["daily_reports:create", "expenses:create"]:
            self.assertEqual(
                self.client.get(
                    reverse(route), {"project": self.sibling.pk}
                ).status_code,
                403,
            )
