from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from apps.payments.models import Payment
from apps.projects.models import (
    Activity,
    Project,
    ProjectCostFact,
    ProjectSite,
    WBSNode,
)
from apps.subledgers.models import Obligation
from apps.treasury.models import TreasuryMovement
from apps.workforce.models import Employee

from .models import (
    AttendanceRecord,
    AttendanceState,
    LaborDistributionPreview,
    LeaveMissionRequest,
    OvertimeRequest,
    ShiftBreak,
    TimesheetState,
)
from .services import (
    add_timesheet_entry,
    capture_attendance,
    correct_attendance,
    create_leave_mission_request,
    create_overtime_request,
    create_shift,
    create_timesheet,
    create_work_calendar,
    finalize_attendance,
    generate_labor_distribution_preview,
    import_attendance,
    review_time_request,
    review_timesheet,
    submit_time_request,
    submit_timesheet,
)

TIME_PERMISSION_CODES = [
    code
    for code in BusinessPermissionCode.values
    if code.split(".", 1)[0]
    in {"time_calendars", "attendance", "leave_mission", "overtime", "timesheets"}
]


class P7TimekeepingTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="time-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="Time Tenant", slug="time-tenant"
        )
        self.organization.settings.timezone = "Asia/Tehran"
        self.organization.settings.save(update_fields=["timezone", "updated_at"])
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_number="T-001",
            first_name="Time",
            last_name="Worker",
        )
        self.project = Project.objects.create(
            organization=self.organization,
            code="TIME",
            name="Time Project",
            created_by=self.owner,
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="SITE",
            name="Time Site",
            created_by=self.owner,
        )
        self.calendar = create_work_calendar(
            organization=self.organization,
            actor=self.owner,
            code="MAIN",
            name="Main calendar",
            effective_from=date(2026, 1, 1),
            working_weekdays=[1, 2, 3, 4, 5, 6],
        )
        self.reviewer = self._member("reviewer")
        self.corrector = self._member("corrector")
        self.approver = self._member("approver")
        self.zone = ZoneInfo("Asia/Tehran")

    def _member(self, username: str) -> User:
        user = User.objects.create_user(username=username)
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code=f"time-{username}",
            name=username,
            created_by=self.owner,
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(code__in=TIME_PERMISSION_CODES)
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
            assigned_by=self.owner,
        )
        return user

    def _attendance(self):
        return capture_attendance(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            calendar=self.calendar,
            project=self.project,
            site=self.site,
            work_date=date(2026, 2, 1),
            check_in_at=datetime(2026, 2, 1, 22, 0, tzinfo=self.zone),
            check_out_at=datetime(2026, 2, 2, 6, 0, tzinfo=self.zone),
        )

    def test_s06_tenant_timezone_cross_midnight_and_explicit_breaks(self) -> None:
        shift = create_shift(
            organization=self.organization,
            actor=self.owner,
            calendar=self.calendar,
            code="NIGHT",
            name="Night",
            starts_at=time(22, 0),
            ends_at=time(6, 0),
            crosses_midnight=True,
            effective_from=date(2026, 1, 1),
            breaks=[
                {
                    "starts_at": time(1, 0),
                    "ends_at": time(1, 30),
                    "ends_next_day": True,
                    "is_paid": False,
                }
            ],
        )
        start, end = shift.interval_for(date(2026, 2, 1))
        self.assertEqual((end - start).total_seconds(), 8 * 3600)
        self.assertEqual(ShiftBreak.objects.get(shift=shift).ends_next_day, True)
        with self.assertRaises(ValidationError):
            create_shift(
                organization=self.organization,
                actor=self.owner,
                calendar=self.calendar,
                code="BAD",
                name="Bad",
                starts_at=time(22, 0),
                ends_at=time(6, 0),
                crosses_midnight=False,
                effective_from=date(2026, 1, 1),
            )

    def test_s07_attendance_is_tenant_safe_sod_immutable_and_corrected_by_history(
        self,
    ) -> None:
        record = self._attendance()
        with self.assertRaises(PermissionDenied):
            finalize_attendance(
                organization=self.organization,
                actor=self.owner,
                attendance=record,
            )
        record = finalize_attendance(
            organization=self.organization,
            actor=self.reviewer,
            attendance=record,
        )
        record.exception_notes = "mutated"
        with self.assertRaises(ValidationError):
            record.save()
        adjustment = correct_attendance(
            organization=self.organization,
            requester=self.corrector,
            approver=self.approver,
            attendance=record,
            reason="Verified missed exit event",
            replacement_values={
                "check_out_at": datetime(2026, 2, 2, 5, 45, tzinfo=self.zone)
            },
        )
        record.refresh_from_db()
        self.assertEqual(record.state, AttendanceState.SUPERSEDED)
        self.assertEqual(adjustment.replacement.state, AttendanceState.FINALIZED)
        other_owner = User.objects.create_user(username="other-time-owner")
        other = create_organization_with_owner(
            owner=other_owner, name="Other Time", slug="other-time"
        )
        with self.assertRaises((PermissionDenied, ValidationError)):
            capture_attendance(
                organization=other,
                actor=other_owner,
                employee=self.employee,
                calendar=self.calendar,
                work_date=date(2026, 2, 3),
                check_in_at=datetime(2026, 2, 3, 8, tzinfo=self.zone),
                check_out_at=datetime(2026, 2, 3, 16, tzinfo=self.zone),
            )

    def test_project_and_site_scope_restricts_capture(self) -> None:
        scoped_user = User.objects.create_user(username="site-capturer")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="site-capturer",
            name="Site capturer",
            created_by=self.owner,
        )
        role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.ATTENDANCE_CAPTURE
            )
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=scoped_user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
            assigned_by=self.owner,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Focused site duty",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.SITE,
            project=self.project,
            site=self.site,
            reason="Time capture for one site",
        )
        other_project = Project.objects.create(
            organization=self.organization,
            code="OTHER",
            name="Other project",
            created_by=self.owner,
        )
        other_site = ProjectSite.objects.create(
            organization=self.organization,
            project=other_project,
            code="OTHER",
            name="Other site",
            created_by=self.owner,
        )
        capture_attendance(
            organization=self.organization,
            actor=scoped_user,
            employee=self.employee,
            calendar=self.calendar,
            project=self.project,
            site=self.site,
            work_date=date(2026, 2, 4),
            check_in_at=datetime(2026, 2, 4, 8, tzinfo=self.zone),
            check_out_at=datetime(2026, 2, 4, 16, tzinfo=self.zone),
        )
        with self.assertRaises(PermissionDenied):
            capture_attendance(
                organization=self.organization,
                actor=scoped_user,
                employee=self.employee,
                calendar=self.calendar,
                project=other_project,
                site=other_site,
                work_date=date(2026, 2, 5),
                check_in_at=datetime(2026, 2, 5, 8, tzinfo=self.zone),
                check_out_at=datetime(2026, 2, 5, 16, tzinfo=self.zone),
            )

    def test_s08_s09_requests_overlap_sod_and_policy_gate(self) -> None:
        leave = create_leave_mission_request(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            kind="leave",
            category_code="CONFIGURED",
            starts_at=datetime(2026, 3, 1, 8, tzinfo=self.zone),
            ends_at=datetime(2026, 3, 1, 12, tzinfo=self.zone),
            reason="Request",
        )
        # CEP-023 supersedes free-text-only leave approval with source allocation.
        with self.assertRaises(ValidationError):
            submit_time_request(
                organization=self.organization, actor=self.owner, request=leave
            )
        with self.assertRaises(ValidationError):
            review_time_request(
                organization=self.organization,
                actor=self.reviewer,
                request=leave,
                approve=True,
                reason="No policy",
            )
        leave.policy_reference = "PO-POLICY-001"
        LeaveMissionRequest.objects.filter(pk=leave.pk).update(
            policy_reference=leave.policy_reference
        )
        leave.refresh_from_db()
        with self.assertRaises(ValidationError):
            submit_time_request(
                organization=self.organization, actor=self.owner, request=leave
            )
        overtime = create_overtime_request(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            starts_at=datetime(2026, 3, 2, 18, tzinfo=self.zone),
            ends_at=datetime(2026, 3, 2, 20, tzinfo=self.zone),
            reason="Request",
            policy_reference="PO-OT-001",
        )
        with self.assertRaises(ValidationError):
            create_overtime_request(
                organization=self.organization,
                actor=self.owner,
                employee=self.employee,
                starts_at=datetime(2026, 3, 2, 19, tzinfo=self.zone),
                ends_at=datetime(2026, 3, 2, 21, tzinfo=self.zone),
                reason="Overlap",
            )
        submit_time_request(
            organization=self.organization, actor=self.owner, request=overtime
        )
        with self.assertRaises(PermissionDenied):
            review_time_request(
                organization=self.organization,
                actor=self.owner,
                request=overtime,
                approve=True,
                reason="self review",
            )
        self.assertEqual(OvertimeRequest.objects.count(), 1)

    def test_s10_import_is_idempotent_and_retains_exceptions(self) -> None:
        rows = [
            {
                "employee_id": self.employee.pk,
                "calendar_id": self.calendar.pk,
                "project_id": self.project.pk,
                "site_id": self.site.pk,
                "work_date": date(2026, 4, 1),
                "check_in_at": datetime(2026, 4, 1, 8, tzinfo=self.zone),
                "check_out_at": datetime(2026, 4, 1, 16, tzinfo=self.zone),
                "source_reference": "ROW-1",
            },
            {"source_reference": "BROKEN"},
        ]
        batch = import_attendance(
            organization=self.organization,
            actor=self.owner,
            idempotency_key="IMPORT-1",
            source_label="normalized-test",
            rows=rows,
        )
        same = import_attendance(
            organization=self.organization,
            actor=self.owner,
            idempotency_key="IMPORT-1",
            source_label="normalized-test",
            rows=rows,
        )
        self.assertEqual(batch.pk, same.pk)
        self.assertEqual(batch.rows.filter(outcome="exception").count(), 1)
        with self.assertRaises(ValidationError):
            import_attendance(
                organization=self.organization,
                actor=self.owner,
                idempotency_key="IMPORT-1",
                source_label="changed",
                rows=[],
            )

    def test_s11_s12_conservation_immutability_review_and_non_posting_preview(
        self,
    ) -> None:
        wbs = WBSNode.objects.create(
            organization=self.organization,
            project=self.project,
            code="WBS",
            title="Work",
            created_by=self.owner,
        )
        activity = Activity.objects.create(
            organization=self.organization,
            project=self.project,
            wbs_node=wbs,
            site=self.site,
            code="ACT",
            name="Activity",
            created_by=self.owner,
        )
        sheet = create_timesheet(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 1),
            declared_minutes=480,
        )
        add_timesheet_entry(
            organization=self.organization,
            actor=self.owner,
            timesheet=sheet,
            work_date=date(2026, 5, 1),
            project=self.project,
            site=self.site,
            activity=activity,
            minutes=420,
        )
        with self.assertRaises(ValidationError):
            submit_timesheet(
                organization=self.organization, actor=self.owner, timesheet=sheet
            )
        sheet.declared_minutes = 420
        sheet.save(update_fields=["declared_minutes", "updated_at"])
        sheet = submit_timesheet(
            organization=self.organization, actor=self.owner, timesheet=sheet
        )
        with self.assertRaises(ValidationError):
            sheet.declared_minutes = 400
            sheet.save()
        review_timesheet(
            organization=self.organization,
            actor=self.reviewer,
            timesheet=sheet,
            approve=True,
            reason="Allocation reviewed",
        )
        sheet.refresh_from_db()
        self.assertEqual(sheet.state, TimesheetState.APPROVED)
        no_effect_before = (
            ProjectCostFact.objects.count(),
            JournalEntry.objects.count(),
            Obligation.objects.count(),
            TreasuryMovement.objects.count(),
            Payment.objects.count(),
        )
        preview = generate_labor_distribution_preview(
            organization=self.organization, actor=self.approver, timesheet=sheet
        )
        self.assertEqual(preview.total_minutes, 420)
        self.assertEqual(preview.lines.get().minutes, 420)
        self.assertEqual(preview.policy_gate, "RATE_AND_PROJECT_COST_POLICY_UNRESOLVED")
        self.assertEqual(AttendanceRecord.objects.count(), 0)
        self.assertEqual(LaborDistributionPreview.objects.count(), 1)
        self.assertEqual(
            no_effect_before,
            (
                ProjectCostFact.objects.count(),
                JournalEntry.objects.count(),
                Obligation.objects.count(),
                TreasuryMovement.objects.count(),
                Payment.objects.count(),
            ),
        )

    def test_persian_workbench_is_reachable_from_navigation(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("timekeeping:workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "حضور، درخواست‌ها و کارکرد")
        self.assertContains(response, "پیش‌نمایش فقط دقیقه‌ها")
