from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.daily_reports.models import DailyReportStatus
from apps.daily_reports.services import (
    add_daily_activity,
    add_daily_report_equipment_entry,
    add_daily_report_labor_entry,
    add_daily_report_material_entry,
    add_delay_event,
    approve_daily_report,
    create_daily_report,
    get_organization_daily_report,
    get_organization_daily_reports,
    submit_daily_report,
)
from apps.materials.services import (
    create_material,
    create_material_category,
    create_unit_of_measure,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import ProjectPhaseStatus
from apps.projects.services import (
    create_activity,
    create_project,
    create_project_phase,
    create_project_site,
    create_wbs_node,
)


class DailyReportServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="daily-report-owner",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="daily-report-other-user",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Daily Report Company",
            slug="daily-report-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Daily Report Company",
            slug="other-daily-report-company",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_user,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-DAILY",
            name="Daily report project",
        )
        self.site = create_project_site(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            code="SITE-DAILY",
            name="Daily report worksite",
        )
        self.phase = create_project_phase(
            organization=self.organization,
            site=self.site,
            actor=self.owner,
            code="PH-DAILY",
            name="Foundation works",
            status=ProjectPhaseStatus.ACTIVE,
        )

    def create_report(self):
        return create_daily_report(
            organization=self.organization,
            project=self.project,
            site=self.site,
            actor=self.owner,
            reporting_date=date(2026, 8, 30),
            work_performed="Completed foundation reinforcement.",
            labor_count=12,
            safety_notes="Morning toolbox talk completed.",
        )

    def test_create_report_is_tenant_scoped_and_audited(self) -> None:
        report = self.create_report()

        self.assertEqual(report.status, DailyReportStatus.DRAFT)
        self.assertEqual(report.organization, self.organization)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DAILY_REPORT_CREATED,
                organization=self.organization,
                entity_id=str(report.pk),
            ).exists()
        )

    def test_report_rejects_cross_tenant_project(self) -> None:
        other_project = self.other_organization.projects.create(
            code="P-OTHER-DAILY",
            name="Other project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        with self.assertRaises(PermissionDenied):
            create_daily_report(
                organization=self.organization,
                project=other_project,
                site=self.site,
                actor=self.owner,
                reporting_date=date(2026, 8, 30),
                work_performed="Unauthorized project report.",
            )

    def test_report_list_and_detail_exclude_other_tenant(self) -> None:
        report = self.create_report()
        other_project = self.other_organization.projects.create(
            code="P-OTHER-DAILY-2",
            name="Other project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        """ self.other_organization.memberships.create(
            user=self.other_user,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        ) """
        other_site = create_project_site(
            organization=self.other_organization,
            project=other_project,
            actor=self.other_user,
            code="SITE-OTHER",
            name="Other worksite",
        )
        other_report = create_daily_report(
            organization=self.other_organization,
            project=other_project,
            site=other_site,
            actor=self.other_user,
            reporting_date=date(2026, 8, 30),
            work_performed="Other tenant report.",
        )

        reports = get_organization_daily_reports(
            user=self.owner,
            organization=self.organization,
        )
        self.assertEqual(list(reports), [report])
        with self.assertRaises(PermissionDenied):
            get_organization_daily_report(
                user=self.owner,
                organization=self.organization,
                report_id=str(other_report.pk),
            )

    def test_submitted_report_can_be_approved_once(self) -> None:
        report = self.create_report()

        submitted_report = submit_daily_report(
            organization=self.organization,
            report_id=str(report.pk),
            actor=self.owner,
        )
        approved_report = approve_daily_report(
            organization=self.organization,
            report_id=str(report.pk),
            actor=self.owner,
        )

        self.assertEqual(submitted_report.status, DailyReportStatus.SUBMITTED)
        self.assertIsNotNone(submitted_report.submitted_at)
        self.assertEqual(approved_report.status, DailyReportStatus.APPROVED)
        self.assertEqual(approved_report.approved_by, self.owner)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DAILY_REPORT_APPROVED,
                entity_id=str(report.pk),
            ).exists()
        )
        with self.assertRaisesMessage(
            ValueError,
            "Only submitted daily reports can be approved.",
        ):
            approve_daily_report(
                organization=self.organization,
                report_id=str(report.pk),
                actor=self.owner,
            )

    def test_viewer_cannot_create_report(self) -> None:
        viewer = User.objects.create_user(
            username="daily-report-viewer",
            password="test-password",
        )
        self.organization.memberships.create(
            user=viewer,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )

        with self.assertRaises(PermissionDenied):
            create_daily_report(
                organization=self.organization,
                project=self.project,
                site=self.site,
                actor=viewer,
                reporting_date=date(2026, 8, 31),
                work_performed="Unauthorized report.",
            )

    def test_list_and_create_views_are_tenant_scoped(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        self.other_organization.projects.create(
            code="P-HIDDEN-DAILY",
            name="Hidden daily project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        response = self.client.get(reverse("daily_reports:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, "Hidden daily project")

        response = self.client.post(
            reverse("daily_reports:create"),
            {
                "project": str(self.project.pk),
                "site": str(self.site.pk),
                "reporting_date": "2026-08-30",
                "weather_conditions": "Clear",
                "labor_count": "8",
                "work_performed": "Prepared the site.",
                "progress_summary": "On track.",
                "issues_and_delays": "",
                "safety_notes": "No incidents.",
                "quality_notes": "Inspection passed.",
            },
        )
        report = self.organization.daily_reports.get()
        self.assertRedirects(
            response,
            reverse("daily_reports:detail", kwargs={"report_id": report.pk}),
        )

    def test_report_rejects_site_from_another_project(self) -> None:
        other_project = self.organization.projects.create(
            code="P-SECOND-DAILY",
            name="Second project",
            created_by=self.owner,
            updated_by=self.owner,
        )
        other_site = create_project_site(
            organization=self.organization,
            project=other_project,
            actor=self.owner,
            code="SITE-SECOND",
            name="Second worksite",
        )

        with self.assertRaises(PermissionDenied):
            create_daily_report(
                organization=self.organization,
                project=self.project,
                site=other_site,
                actor=self.owner,
                reporting_date=date(2026, 8, 31),
                work_performed="Invalid worksite assignment.",
            )

    def test_report_optionally_scopes_to_an_active_worksite_phase(self) -> None:
        report = create_daily_report(
            organization=self.organization,
            project=self.project,
            site=self.site,
            phase=self.phase,
            actor=self.owner,
            reporting_date=date(2026, 8, 31),
            work_performed="Completed concrete foundation pour.",
        )

        self.assertEqual(report.phase, self.phase)
        event = AuditEvent.objects.get(
            action=AuditAction.DAILY_REPORT_CREATED,
            entity_id=str(report.pk),
        )
        self.assertEqual(event.metadata["phase_id"], str(self.phase.pk))

    def test_report_rejects_phase_from_another_worksite(self) -> None:
        other_project = self.organization.projects.create(
            code="P-PHASE-OTHER",
            name="Other phase project",
            created_by=self.owner,
            updated_by=self.owner,
        )
        other_site = create_project_site(
            organization=self.organization,
            project=other_project,
            actor=self.owner,
            code="SITE-PHASE-OTHER",
            name="Other phase worksite",
        )
        other_phase = create_project_phase(
            organization=self.organization,
            site=other_site,
            actor=self.owner,
            code="PH-PHASE-OTHER",
            name="Other foundation works",
            status=ProjectPhaseStatus.ACTIVE,
        )

        with self.assertRaises(PermissionDenied):
            create_daily_report(
                organization=self.organization,
                project=self.project,
                site=self.site,
                phase=other_phase,
                actor=self.owner,
                reporting_date=date(2026, 8, 31),
                work_performed="Invalid phase assignment.",
            )

    def test_draft_report_accepts_operational_entries_and_locks_on_submit(self) -> None:
        report = self.create_report()

        labor_entry = add_daily_report_labor_entry(
            organization=self.organization,
            report_id=str(report.pk),
            actor=self.owner,
            team_name="Concrete crew",
            worker_count=6,
            hours_worked=Decimal("7.50"),
        )
        equipment_entry = add_daily_report_equipment_entry(
            organization=self.organization,
            report_id=str(report.pk),
            actor=self.owner,
            equipment_name="Concrete pump",
            hours_used=Decimal("4.25"),
        )
        material_entry = add_daily_report_material_entry(
            organization=self.organization,
            report_id=str(report.pk),
            actor=self.owner,
            material_name="Ready-mix concrete",
            quantity=Decimal("18.5000"),
            unit="m³",
        )

        self.assertEqual(labor_entry.organization, self.organization)
        self.assertEqual(equipment_entry.report, report)
        self.assertEqual(material_entry.quantity, Decimal("18.5000"))
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DAILY_REPORT_LABOR_ADDED,
                entity_id=str(labor_entry.pk),
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DAILY_REPORT_EQUIPMENT_ADDED,
                entity_id=str(equipment_entry.pk),
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DAILY_REPORT_MATERIAL_ADDED,
                entity_id=str(material_entry.pk),
            ).exists()
        )

        submit_daily_report(
            organization=self.organization,
            report_id=str(report.pk),
            actor=self.owner,
        )
        with self.assertRaisesMessage(
            ValueError,
            "Only draft daily reports can be updated.",
        ):
            add_daily_report_material_entry(
                organization=self.organization,
                report_id=str(report.pk),
                actor=self.owner,
                material_name="Cement",
                quantity=Decimal("2.0000"),
                unit="bag",
            )

    def test_structured_entries_validate_master_scope_and_preserve_material_snapshots(
        self,
    ) -> None:
        unit = create_unit_of_measure(
            organization=self.organization,
            actor=self.owner,
            code="M3",
            name="Cubic metre",
            symbol="m³",
            category="volume",
            decimal_places=3,
        )
        category = create_material_category(
            organization=self.organization,
            actor=self.owner,
            code="CONC",
            name="Concrete",
        )
        material = create_material(
            organization=self.organization,
            actor=self.owner,
            code="RMX",
            name="Ready-mix concrete",
            category=category,
            unit_of_measure=unit,
        )
        node = create_wbs_node(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            code="01",
            title="Foundation",
        )
        activity = create_activity(
            organization=self.organization,
            project=self.project,
            wbs_node=node,
            actor=self.owner,
            code="POUR",
            name="Pour concrete",
            site=self.site,
            phase=self.phase,
            unit_of_measure=unit,
            planned_quantity=Decimal("50.0000"),
        )
        report = create_daily_report(
            organization=self.organization,
            project=self.project,
            site=self.site,
            phase=self.phase,
            actor=self.owner,
            reporting_date=date(2026, 8, 31),
            work_performed="Concrete placement.",
        )
        material_entry = add_daily_report_material_entry(
            organization=self.organization,
            report_id=str(report.pk),
            actor=self.owner,
            material_name="ignored",
            quantity=Decimal("12.5000"),
            unit="ignored",
            material=material,
        )
        daily_activity = add_daily_activity(
            organization=self.organization,
            report_id=str(report.pk),
            actor=self.owner,
            activity=activity,
            description="",
            quantity=Decimal("12.5000"),
            progress_percent=Decimal("25.00"),
        )
        delay = add_delay_event(
            organization=self.organization,
            report_id=str(report.pk),
            actor=self.owner,
            activity=activity,
            occurred_on=date(2026, 8, 31),
            cause="Pump failure",
            duration_hours=Decimal("1.50"),
        )
        self.assertEqual(material_entry.material_name, material.name)
        self.assertEqual(material_entry.unit, "m³")
        self.assertEqual(daily_activity.description, activity.name)
        self.assertEqual(delay.activity, activity)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DAILY_ACTIVITY_ADDED,
                entity_id=str(daily_activity.pk),
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.DELAY_EVENT_ADDED, entity_id=str(delay.pk)
            ).exists()
        )

    def test_structured_entries_are_locked_after_submission_and_reject_cross_project_activity(
        self,
    ) -> None:
        report = self.create_report()
        other_project = self.other_organization.projects.create(
            code="OTHER", name="Other"
        )
        other_site = self.other_organization.project_sites.create(
            project=other_project, code="OTHER-SITE", name="Other site"
        )
        other_node = create_wbs_node(
            organization=self.other_organization,
            project=other_project,
            actor=self.other_user,
            code="01",
            title="Other",
        )
        other_activity = create_activity(
            organization=self.other_organization,
            project=other_project,
            wbs_node=other_node,
            actor=self.other_user,
            code="OTHER-ACT",
            name="Other activity",
            site=other_site,
        )
        with self.assertRaises(PermissionDenied):
            add_daily_activity(
                organization=self.organization,
                report_id=str(report.pk),
                actor=self.owner,
                activity=other_activity,
                description="Other",
            )
        submit_daily_report(
            organization=self.organization, report_id=str(report.pk), actor=self.owner
        )
        with self.assertRaisesMessage(
            ValueError, "Only draft daily reports can be updated."
        ):
            add_delay_event(
                organization=self.organization,
                report_id=str(report.pk),
                actor=self.owner,
                occurred_on=date(2026, 8, 30),
                cause="Late delivery",
            )
