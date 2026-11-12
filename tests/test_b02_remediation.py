"""Targeted B02 integrity, authorization and journey regressions."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from threading import Barrier
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
)
from apps.projects.forms import WBSNodeForm
from apps.projects.models import Project, ProjectSite, WBSNode
from apps.projects.services import create_wbs_node
from apps.timekeeping.forms import (
    AttendanceCorrectionForm,
    AttendanceForm,
    LeaveMissionForm,
    OvertimeForm,
)
from apps.timekeeping.models import (
    AttendanceAdjustment,
    AttendanceCorrectionRequest,
    AttendanceRecord,
)
from apps.timekeeping.services import (
    capture_attendance,
    create_work_calendar,
    finalize_attendance,
    request_attendance_correction,
    review_attendance_correction,
)
from apps.workforce.models import EmployeeProjectAssignment
from apps.workforce.test_mvp02 import make_field_fixture


class B02Fixture:
    def make_fixture(self):
        self.owner = User.objects.create_user(username="b02-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="شرکت آزمون اصلاحات", slug="b02-remediation"
        )
        self.organization.settings.timezone = "Asia/Tehran"
        self.organization.settings.save(update_fields=["timezone", "updated_at"])
        self.project, self.site, _, self.employee, _ = make_field_fixture(
            self.owner, self.organization
        )
        self.sibling = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="SIBLING",
            name="کارگاه دیگر",
        )
        self.calendar = create_work_calendar(
            organization=self.organization,
            actor=self.owner,
            code="CAL",
            name="تقویم آزمون",
            effective_from=date(2026, 1, 1),
            working_weekdays=[1, 2, 3, 4, 5, 6, 7],
        )
        permissions = [
            "attendance.view",
            "attendance.capture",
            "attendance.review",
            "attendance.correct",
            "leave_mission.view",
            "leave_mission.request",
            "leave_mission.review",
            "overtime.view",
            "overtime.request",
            "overtime.review",
            "projects.view",
            "project_sites.view",
        ]
        self.reviewer, _, _ = self.member("reviewer", permissions)
        self.corrector, _, _ = self.member("corrector", permissions)
        self.zone = ZoneInfo("Asia/Tehran")
        self.day = date(2026, 11, 1)

    def member(self, name, permissions, *, site=None):
        user = User.objects.create_user(username=f"b02-{name}")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code=f"b02-{name}",
            name=name,
            created_by=self.owner,
        )
        granted = BusinessPermission.objects.filter(code__in=permissions)
        assert set(granted.values_list("code", flat=True)) == set(permissions)
        role.permissions.set(granted)
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status="active",
            assigned_by=self.owner,
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Explicit B02 test authority",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="site" if site else "organization",
            project=site.project if site else None,
            site=site,
            reason="Explicit B02 test scope",
        )
        return user, role, membership

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

    def moment(self, hour, minute=0):
        return datetime(2026, 11, 1, hour, minute, tzinfo=self.zone)

    def attendance(self, start=8, end=12, *, site=None, finalized=True):
        record = capture_attendance(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            calendar=self.calendar,
            project=self.project,
            site=site or self.site,
            work_date=self.day,
            check_in_at=self.moment(start),
            check_out_at=self.moment(end),
        )
        if finalized:
            finalize_attendance(
                organization=self.organization,
                actor=self.reviewer,
                attendance=record,
                reconciliation_reason="بررسی مستقل",
            )
            record.refresh_from_db()
        return record

    def correction(self, record, start=8, end=12, *, reversal=False):
        return request_attendance_correction(
            organization=self.organization,
            requester=self.corrector,
            attendance=record,
            reason="اصلاح آزمایشی",
            reversal=reversal,
            replacement_values={
                "work_date": self.day,
                "check_in_at": self.moment(start),
                "check_out_at": self.moment(end),
            }
            if not reversal
            else None,
        )

    def approve(self, correction, approve=True):
        return review_attendance_correction(
            organization=self.organization,
            approver=self.reviewer,
            correction_request=correction,
            approve=approve,
            review_reason="بررسی مستقل",
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class B02RemediationTests(B02Fixture, TestCase):
    def setUp(self):
        self.make_fixture()

    def test_local_datetime_forms_preserve_jalali_and_aware_initial_values(self):
        for form_type, start_name, end_name, extra in (
            (
                AttendanceForm,
                "check_in_at",
                "check_out_at",
                {
                    "calendar": self.calendar.pk,
                    "work_date": "1405/08/10",
                },
            ),
            (
                LeaveMissionForm,
                "starts_at",
                "ends_at",
                {
                    "kind": "mission",
                    "category_code": "TEST",
                    "reason": "آزمون",
                },
            ),
            (
                LeaveMissionForm,
                "starts_at",
                "ends_at",
                {
                    "kind": "leave",
                    "category_code": "TEST",
                    "reason": "آزمون",
                },
            ),
            (OvertimeForm, "starts_at", "ends_at", {"reason": "آزمون"}),
            (
                AttendanceCorrectionForm,
                "replacement_check_in_at",
                "replacement_check_out_at",
                {"kind": "correction", "reason": "آزمون"},
            ),
        ):
            with self.subTest(form=form_type.__name__, extra=extra):
                data = {
                    "employee": self.employee.pk,
                    "project": self.project.pk,
                    "site": self.site.pk,
                    start_name: "1405/08/10 08:00",
                    end_name: "1405/08/10 12:00",
                    **extra,
                }
                form = form_type(data, organization=self.organization, user=self.owner)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(
                    form.cleaned_data[start_name].astimezone(UTC),
                    datetime(2026, 11, 1, 4, 30, tzinfo=UTC),
                )
                self.assertEqual(
                    form.cleaned_data[end_name] - form.cleaned_data[start_name],
                    timedelta(hours=4),
                )
                initial = form_type(
                    organization=self.organization,
                    user=self.owner,
                    initial={start_name: datetime(2026, 11, 1, 4, 30, tzinfo=UTC)},
                )
                self.assertEqual(
                    initial[start_name].value(), self.moment(8).replace(tzinfo=None)
                )
                self.assertIn("1405/08/10 08:00", str(initial[start_name]))
                invalid = {**data, start_name: "1405/08/10 25:61"}
                self.assertFalse(
                    form_type(
                        invalid, organization=self.organization, user=self.owner
                    ).is_valid()
                )

    def test_timezone_boundary_and_dst_validation_follow_configured_zone(self):
        field = OvertimeForm(organization=self.organization).fields["starts_at"]
        self.assertEqual(
            field.clean("2026-11-01 00:15").astimezone(UTC),
            datetime(2026, 10, 31, 20, 45, tzinfo=UTC),
        )
        self.organization.settings.timezone = "America/New_York"
        field = OvertimeForm(organization=self.organization).fields["starts_at"]
        for ambiguous in ("2026-11-01 01:30", "2026-03-08 02:30"):
            with self.subTest(value=ambiguous), self.assertRaises(ValidationError):
                field.clean(ambiguous)
        aware = datetime(2026, 11, 1, 4, 30, tzinfo=UTC)
        self.assertEqual(field.clean(aware), aware)
        missing = OvertimeForm().fields["starts_at"]
        with self.assertRaises(ValidationError):
            missing.clean("2026-11-01 08:00")

    def test_browser_entry_persists_and_displays_tenant_wall_time_after_review(self):
        self.login(self.owner)
        payload = {
            "employee": self.employee.pk,
            "calendar": self.calendar.pk,
            "project": self.project.pk,
            "site": self.site.pk,
            "work_date": "1405/08/10",
            "check_in_at": "1405/08/10 08:00",
            "check_out_at": "1405/08/10 12:00",
        }
        response = self.client.post(reverse("timekeeping:attendance_create"), payload)
        self.assertEqual(response.status_code, 302)
        record = AttendanceRecord.objects.get(organization=self.organization)
        self.assertEqual(record.check_in_at, datetime(2026, 11, 1, 4, 30, tzinfo=UTC))
        self.login(self.reviewer)
        self.client.post(reverse("timekeeping:attendance_finalize", args=[record.pk]))
        detail = self.client.get(
            reverse("timekeeping:record_detail", args=["attendance", record.pk])
        )
        self.assertContains(detail, "1405/08/10 08:00")
        record.refresh_from_db()
        self.assertEqual(record.state, "finalized")
        self.assertEqual(record.check_in_at, datetime(2026, 11, 1, 4, 30, tzinfo=UTC))
        self.assertContains(
            self.client.get(reverse("timekeeping:workbench")), "1405/08/10 08:00"
        )

    def test_correction_overlap_rolls_back_original_adjustment_and_audit(self):
        original = self.attendance()
        self.attendance(13, 15)
        pending = self.correction(original, 8, 14)
        before_audit = AuditEvent.objects.count()
        with self.assertRaises(ValidationError) as error:
            self.approve(pending)
        self.assertIn("هم‌پوشانی", error.exception.messages[0])
        original.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(
            (original.state, original.check_out_at), ("finalized", self.moment(12))
        )
        self.assertEqual(pending.status, "pending")
        self.assertFalse(AttendanceAdjustment.objects.exists())
        self.assertEqual(AuditEvent.objects.count(), before_audit)
        self.assertEqual(AttendanceRecord.objects.count(), 2)

    def test_invalid_attendance_interval_returns_field_error_without_writes(self):
        before_audit = AuditEvent.objects.count()
        self.login(self.owner)
        response = self.client.post(
            reverse("timekeeping:attendance_create"),
            {
                "employee": self.employee.pk,
                "calendar": self.calendar.pk,
                "project": self.project.pk,
                "site": self.site.pk,
                "work_date": "1405/08/10",
                "check_in_at": "1405/08/10 08:00",
                "check_out_at": "1405/08/10 07:00",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("check_out_at", response.context["form"].errors)
        with self.assertRaises(ValidationError):
            self.attendance(8, 7, finalized=False)
        self.assertFalse(AttendanceRecord.objects.exists())
        # Authentication may emit its own event. Attendance mutation emits none.
        self.assertFalse(
            AuditEvent.objects.filter(action="time.attendance_captured").exists()
        )
        self.assertGreaterEqual(AuditEvent.objects.count(), before_audit)

    def test_adjacent_correction_rejection_reversal_and_replay_preserve_history(self):
        original = self.attendance()
        self.attendance(13, 15)
        rejected = self.correction(original, 8, 14)
        self.approve(rejected, approve=False)
        self.assertEqual(
            AttendanceRecord.objects.get(pk=original.pk).state, "finalized"
        )
        valid = self.approve(self.correction(original, 8, 13))
        replacement = valid.adjustment.replacement
        self.assertEqual(replacement.check_out_at, self.moment(13))
        original.refresh_from_db()
        self.assertEqual(
            (original.state, original.check_out_at), ("superseded", self.moment(12))
        )
        with self.assertRaises(ValidationError):
            self.approve(valid)
        reversal = request_attendance_correction(
            organization=self.organization,
            requester=self.owner,
            attendance=replacement,
            reason="برگشت آزمایشی",
            reversal=True,
        )
        self.approve(reversal)
        replacement.refresh_from_db()
        self.assertEqual(replacement.state, "reversed")
        self.assertEqual(AttendanceAdjustment.objects.count(), 2)
        self.assertEqual(self.attendance(8, 12).state, "finalized")

    def test_wrong_reviewer_and_invalid_interval_cannot_commit(self):
        original = self.attendance()
        correction = self.correction(original)
        with self.assertRaises(PermissionDenied):
            review_attendance_correction(
                organization=self.organization,
                approver=self.corrector,
                correction_request=correction,
                approve=True,
                review_reason="خودتأییدی",
            )
        bad = self.correction(original, 12, 8)
        with self.assertRaises(ValidationError):
            self.approve(bad)
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertFalse(AttendanceAdjustment.objects.exists())

    def test_correction_get_and_post_intersect_site_and_tenant_scope(self):
        original = self.attendance(site=self.sibling)
        limited, _, _ = self.member(
            "limited", ["attendance.view", "attendance.correct"], site=self.site
        )
        url = reverse("timekeeping:attendance_correction_create", args=[original.pk])
        self.login(limited)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(
            self.client.post(url, {"kind": "reversal", "reason": "forged"}).status_code,
            404,
        )
        other = User.objects.create_user(username="other-owner")
        create_organization_with_owner(owner=other, name="شرکت دیگر", slug="b02-other")
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertFalse(AttendanceCorrectionRequest.objects.exists())
        self.login(self.corrector)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_wbs_parent_binding_child_persistence_and_foreign_rejection(self):
        parent = create_wbs_node(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            code="ROOT",
            title="والد",
        )
        form = WBSNodeForm(
            {"code": "CHILD", "title": "فرزند", "parent": parent.pk, "sort_order": 1},
            project=self.project,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.login(self.owner)
        url = reverse("projects:wbs_create", args=[self.project.pk])
        response = self.client.post(url, form.data)
        self.assertRedirects(
            response, reverse("projects:controls", args=[self.project.pk])
        )
        child = WBSNode.objects.get(code="CHILD", organization=self.organization)
        self.assertEqual((child.parent, child.project), (parent, self.project))
        other = Project.objects.create(
            organization=self.organization, code="OTHER", name="دیگر"
        )
        foreign = create_wbs_node(
            organization=self.organization,
            project=other,
            actor=self.owner,
            code="OTHER",
            title="دیگر",
        )
        invalid = WBSNodeForm(
            {**form.data, "code": "BAD", "parent": foreign.pk}, project=self.project
        )
        self.assertFalse(invalid.is_valid())
        self.assertIn("parent", invalid.errors)
        with self.assertRaises(PermissionDenied):
            create_wbs_node(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                code="BAD",
                title="غلط",
                parent=foreign,
            )
        self.assertFalse(WBSNode.objects.filter(code="BAD").exists())

    def test_assignment_end_keeps_valid_filters_and_rejects_foreign_context(self):
        assignment = EmployeeProjectAssignment.objects.get(employee=self.employee)
        self.login(self.owner)
        query = {
            "project": str(self.project.pk),
            "site": str(self.site.pk),
            "q": "FIELD",
            "sort": "status",
            "direction": "desc",
            "return_to": "https://example.invalid",
        }
        path = reverse("workforce:assignment_status_change", args=[assignment.pk])
        listing = self.client.get(reverse("workforce:assignment_list"), query)
        self.assertContains(listing, "?project=")
        response = self.client.post(
            path + "?" + urlencode(query),
            {"target_status": "completed", "end_date": "1405/08/20"},
        )
        returned = urlsplit(response.url)
        self.assertEqual(returned.path, reverse("workforce:assignment_list"))
        self.assertEqual(
            parse_qs(returned.query),
            {k: [v] for k, v in query.items() if k != "return_to"},
        )
        self.assertEqual(returned.netloc, "")
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "completed")
        limited, _, _ = self.member(
            "assignment-limited",
            ["project_assignments.view", "project_assignments.change_status"],
            site=self.site,
        )
        self.login(limited)
        self.assertEqual(
            self.client.post(
                path + "?" + urlencode({"site": self.sibling.pk}),
                {"target_status": "cancelled"},
            ).status_code,
            404,
        )

    def test_correction_replacement_link_is_scoped_and_retains_context(self):
        original = self.attendance()
        approved = self.approve(self.correction(original, 8, 13))
        replacement = approved.adjustment.replacement
        self.login(self.reviewer)
        url = reverse("timekeeping:record_detail", args=["correction", approved.pk])
        response = self.client.get(url)
        self.assertContains(response, "مشاهده حضور جایگزین")
        self.assertIn(str(replacement.pk), response.context["replacement_url"])
        self.assertEqual(
            parse_qs(urlsplit(response.context["replacement_url"]).query)["site"],
            [str(self.site.pk)],
        )
        limited, _, _ = self.member(
            "history-limited",
            ["attendance.view", "attendance.correct"],
            site=self.sibling,
        )
        self.login(limited)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(
            self.client.get(
                reverse(
                    "timekeeping:record_detail", args=["attendance", replacement.pk]
                )
            ).status_code,
            404,
        )

    def test_controls_navigation_requires_each_effective_read_permission(self):
        partial, role, _ = self.member(
            "partial", ["projects.view", "project_controls.view"]
        )
        self.login(partial)
        destination = reverse("projects:controls", args=[self.project.pk])
        hub = reverse("projects:detail", args=[self.project.pk])
        self.assertNotContains(self.client.get(hub), f'href="{destination}"')
        self.assertEqual(self.client.get(destination).status_code, 403)
        for permission in ("wbs_nodes.view", "activities.view"):
            role.permissions.add(BusinessPermission.objects.get(code=permission))
        self.assertContains(self.client.get(hub), f'href="{destination}"')
        self.assertEqual(self.client.get(destination).status_code, 200)

    def test_project_list_has_primary_name_link_and_one_explicit_detail_action(self):
        self.login(self.owner)
        response = self.client.get(reverse("projects:list"))
        url = reverse("projects:detail", args=[self.project.pk])
        self.assertContains(response, f'href="{url}"', count=2)
        self.assertContains(
            response,
            f'<td class="erp-list-identifier"><bdi dir="ltr">{self.project.code}</bdi></td>',
            html=True,
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class B02ConcurrencyTests(B02Fixture, TransactionTestCase):
    serialized_rollback = True

    def setUp(self):
        self.make_fixture()

    def race(self, operations):
        barrier = Barrier(2)

        def run(operation):
            close_old_connections()
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                barrier.wait(timeout=10)
                operation()
                return "approved"
            except ValidationError:
                return "conflict"
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, operations))
        self.assertCountEqual(results, ["approved", "conflict"])
        final = list(
            AttendanceRecord.objects.filter(state="finalized").order_by("check_in_at")
        )
        for left, right in pairwise(final):
            self.assertLessEqual(left.check_out_at, right.check_in_at)

    def test_concurrent_corrections_cannot_finalize_overlapping_replacements(self):
        first = self.attendance(8, 10)
        second = self.attendance(13, 15)
        a = self.correction(first, 8, 12)
        b = self.correction(second, 11, 15)
        self.race([lambda: self.approve(a), lambda: self.approve(b)])
        self.assertEqual(AttendanceAdjustment.objects.count(), 1)
        self.assertEqual(
            AttendanceCorrectionRequest.objects.filter(status="pending").count(), 1
        )

    def test_concurrent_finalization_and_correction_share_the_employee_lock(self):
        first = self.attendance(8, 10)
        second = self.attendance(11, 14, finalized=False)
        pending = self.correction(first, 8, 12)
        self.race(
            [
                lambda: self.approve(pending),
                lambda: finalize_attendance(
                    organization=self.organization,
                    actor=self.reviewer,
                    attendance=second,
                ),
            ]
        )

    def test_concurrent_finalizations_cannot_both_commit(self):
        first = self.attendance(8, 12, finalized=False)
        second = self.attendance(11, 14, finalized=False)
        self.race(
            [
                lambda item=item: finalize_attendance(
                    organization=self.organization,
                    actor=self.reviewer,
                    attendance=item,
                    reconciliation_reason="بررسی مستقل",
                )
                for item in (first, second)
            ]
        )
