"""Own ESS timekeeping journeys, source delegation and negative boundaries."""

import os
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import (
    BusinessPermission,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.projects.models import Project
from apps.timekeeping import services as source
from apps.timekeeping.models import (
    AttendanceCorrectionRequest,
    AttendanceRecord,
    LeaveMissionRequest,
    Timesheet,
)

from . import ess_timekeeping as service
from . import test_cep023 as fixture
from .ess_timekeeping_forms import EntryForm, LeaveForm
from .models import (
    Employee,
    EmployeeProjectAssignment,
    LeaveBalanceEntry,
    Person,
)


class ESSTimekeepingTests(TestCase):
    policy = fixture.LeaveAuthorityTests.policy
    credit = fixture.LeaveAuthorityTests.credit

    def setUp(self):
        fixture.LeaveAuthorityTests.setUp(self)
        self.employee_user = self.reviewer
        person = self.relationship.person
        person.user = self.employee_user
        person.save()
        self.relationship.refresh_from_db()
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.employee_user
        )
        self.role = membership.role_definition
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.LEAVE_BALANCES_MANAGE)
        )
        self.role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    P.LEAVE_MISSION_VIEW,
                    P.ATTENDANCE_VIEW,
                    P.ATTENDANCE_CORRECT,
                    P.TIMESHEETS_VIEW,
                    P.TIMESHEETS_PREPARE,
                ]
            )
        )
        owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.actor
        )
        for assignment in owner_membership.role_assignments.select_related("role"):
            assignment.role.permissions.add(
                *BusinessPermission.objects.filter(
                    code__in=[
                        P.TIME_CALENDARS_MANAGE,
                        P.ATTENDANCE_CAPTURE,
                        P.ATTENDANCE_REVIEW,
                    ]
                )
            )
        self.project = Project.objects.create(
            organization=self.organization,
            code="OWN-TIME",
            name="پروژه مجاز من",
            created_by=self.actor,
        )
        EmployeeProjectAssignment.objects.create(
            organization=self.organization,
            employee=self.employee,
            project=self.project,
            start_date=self.relationship.effective_start,
            created_by=self.actor,
        )
        self.peer = Employee.objects.create(
            organization=self.organization,
            employee_number="PEER",
            first_name="Peer",
            last_name="Worker",
        )

    def client_for(self, user=None, csrf=False):
        client = Client(enforce_csrf_checks=csrf)
        client.force_login(user or self.employee_user)
        session = client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        return client

    def capture(self, name, response):
        directory = os.environ.get("BONIRA_CEP063_CAPTURE_DIR")
        if directory:
            body = re.sub(
                rb'name="csrfmiddlewaretoken" value="[^"]+"',
                b'name="csrfmiddlewaretoken" value="SYNTHETIC-EVIDENCE"',
                response.content,
            )
            Path(directory, name + ".html").write_bytes(body)

    def leave(self, **changes):
        start = timezone.now() + timedelta(days=2)
        return service.create_own_leave(
            **(
                {
                    "actor": self.employee_user,
                    "organization": self.organization,
                    "policy_id": self.policy_record.pk,
                    "starts_at": start,
                    "ends_at": start + timedelta(hours=4),
                    "quantity": Decimal(240),
                    "reason": "دلیل شخصی درخواست",
                }
                | changes
            )
        )

    def prepared(self):
        self.policy_record = self.policy()
        self.credit()

    def attendance(self, employee=None):
        calendar = source.create_work_calendar(
            organization=self.organization,
            actor=self.actor,
            code="SOURCE",
            name="تقویم",
            effective_from=self.relationship.effective_start,
            working_weekdays=[1, 2, 3, 4, 5, 6, 7],
        )
        now = timezone.now() - timedelta(days=1)
        # Synthetic immutable source fact; ESS never creates an attendance fact.
        return AttendanceRecord.objects.create(
            organization=self.organization,
            employee=employee or self.employee,
            calendar=calendar,
            project=self.project,
            work_date=now.date(),
            check_in_at=now - timedelta(hours=4),
            check_out_at=now,
            source="manual",
            state="finalized",
            captured_by=self.actor,
            finalized_by=self.actor,
            finalized_at=now,
        )

    def test_empty_index_policy_absence_and_rtl_jalali_ui(self):
        response = self.client_for().get(reverse("workforce:ess_timekeeping"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "مرخصی، حضور و کارکرد من")
        self.assertContains(response, "مانده صفر فرض نمی‌شود")
        self.assertContains(response, "سابقه مجازی برای نمایش ثبت نشده است")
        self.assertNotContains(response, "مانده قابل استفاده: ۰")
        self.capture("empty", response)

    def test_create_leave_requires_effective_source_policy_no_orphan_draft(self):
        start = timezone.now() + timedelta(days=2)
        with self.assertRaises(ValidationError):
            service.create_own_leave(
                actor=self.employee_user,
                organization=self.organization,
                policy_id=self.relationship.pk,
                starts_at=start,
                ends_at=start + timedelta(hours=1),
                quantity=Decimal(1),
                reason="No policy",
            )
        self.assertEqual(LeaveMissionRequest.objects.count(), 0)
        self.prepared()
        with self.assertRaises(ValidationError):
            self.leave(quantity=Decimal(1001))
        self.assertEqual(LeaveMissionRequest.objects.count(), 0)

    def test_own_leave_reservation_and_source_submit_without_balance_manager(self):
        self.prepared()
        request = self.leave()
        self.assertEqual(request.employee_id, self.employee.pk)
        self.assertEqual(request.requested_by_id, self.employee_user.pk)
        self.assertEqual(
            LeaveBalanceEntry.objects.filter(
                request=request, kind="reservation"
            ).count(),
            1,
        )
        response = self.client_for().post(
            reverse("workforce:ess_timekeeping_submit", args=["leave", request.pk])
        )
        self.assertEqual(response.status_code, 302)
        request.refresh_from_db()
        self.assertEqual(request.state, "submitted")
        response = self.client_for().get(reverse("workforce:ess_timekeeping"))
        self.assertContains(response, str(request.pk))
        self.assertContains(response, "submitted")
        self.assertNotContains(response, "دلیل شخصی درخواست")
        self.capture("ready", response)
        self.assertEqual(
            self.client_for()
            .get(
                reverse("workforce:ess_timekeeping_detail", args=["leave", request.pk])
            )
            .status_code,
            200,
        )

    def test_cross_tenant_peer_ids_and_unknown_ids_have_same_denial(self):
        self.prepared()
        own = self.leave()
        peer = LeaveMissionRequest.objects.create(
            organization=self.organization,
            employee=self.peer,
            kind="leave",
            category_code="EXPLICIT",
            starts_at=own.starts_at,
            ends_at=own.ends_at,
            reason="PEER_SECRET",
            requested_by=self.actor,
        )
        client = self.client_for()
        denied = []
        for pk in [peer.pk, self.other.pk]:
            response = client.get(
                reverse("workforce:ess_timekeeping_detail", args=["leave", pk])
            )
            self.assertEqual(response.status_code, 403)
            denied.append(response.content)
            self.assertEqual(
                client.post(
                    reverse("workforce:ess_timekeeping_submit", args=["leave", pk])
                ).status_code,
                403,
            )
        self.assertEqual(
            *[
                re.sub(
                    rb'name="csrfmiddlewaretoken" value="[^"]+"',
                    b'name="csrfmiddlewaretoken" value="REDACTED"',
                    body.replace(str(pk).encode(), b"REQUESTED-ID"),
                )
                for body, pk in zip(denied, [peer.pk, self.other.pk], strict=True)
            ]
        )
        self.assertNotIn(b"PEER_SECRET", denied[0])
        self.capture("unauthorized", response)
        self.assertNotContains(
            client.get(reverse("workforce:ess_timekeeping")), str(peer.pk)
        )

    def test_unlinked_inactive_member_and_suspended_tenant_fail_closed(self):
        self.assertEqual(
            self.client_for(self.other_actor)
            .get(reverse("workforce:ess_timekeeping"))
            .status_code,
            403,
        )
        Person.objects.filter(pk=self.relationship.person_id).update(user=None)
        self.assertEqual(
            self.client_for().get(reverse("workforce:ess_timekeeping")).status_code, 403
        )
        Person.objects.filter(pk=self.relationship.person_id).update(
            user=self.employee_user
        )
        Organization.objects.filter(pk=self.organization.pk).update(status="suspended")
        self.assertEqual(
            self.client_for().get(reverse("workforce:ess_timekeeping")).status_code, 403
        )

    def test_mutations_require_post_csrf_and_own_source_permission(self):
        self.prepared()
        request = self.leave()
        url = reverse("workforce:ess_timekeeping_submit", args=["leave", request.pk])
        self.assertEqual(self.client_for().get(url).status_code, 405)
        self.assertEqual(self.client_for(csrf=True).post(url).status_code, 403)
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.LEAVE_MISSION_REQUEST)
        )
        self.assertEqual(self.client_for().post(url).status_code, 403)
        request.refresh_from_db()
        self.assertEqual(request.state, "draft")

    def test_forms_exclude_identity_and_accept_jalali_dates(self):
        self.prepared()
        response = self.client_for().get(
            reverse("workforce:ess_timekeeping_create", args=["leave"])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-jalali-date="datetime"')
        self.assertNotContains(response, 'name="employee"')
        self.assertNotContains(response, 'name="organization"')
        form = LeaveForm(
            {
                "policy_id": str(self.policy_record.pk),
                "starts_at": "1405/08/01 08:00",
                "ends_at": "1405/08/01 12:00",
                "quantity": "240",
                "reason": "درخواست",
            },
            organization=self.organization,
            actor=self.employee_user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.capture("form", response)

    def test_invalid_form_is_explicit_and_does_not_leak_internal_error(self):
        response = self.client_for().post(
            reverse("workforce:ess_timekeeping_create", args=["timesheet"]),
            {
                "period_start": "not-a-date",
                "period_end": "not-a-date",
                "declared_minutes": "-1",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'role="alert"', status_code=400)
        self.assertEqual(Timesheet.objects.count(), 0)
        self.capture("error", response)

    def test_timesheet_create_add_submit_tracks_authoritative_source(self):
        today = timezone.localdate()
        sheet = service.create_own_timesheet(
            actor=self.employee_user,
            organization=self.organization,
            period_start=today,
            period_end=today,
            declared_minutes=120,
        )
        service.add_own_entry(
            actor=self.employee_user,
            organization=self.organization,
            record_id=sheet.pk,
            work_date=today,
            project=self.project,
            site=None,
            activity=None,
            minutes=120,
        )
        response = self.client_for().post(
            reverse("workforce:ess_timekeeping_submit", args=["timesheet", sheet.pk])
        )
        self.assertEqual(response.status_code, 302)
        sheet.refresh_from_db()
        self.assertEqual(sheet.state, "submitted")
        response = self.client_for().get(
            reverse("workforce:ess_timekeeping_detail", args=["timesheet", sheet.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.capture("timesheet", response)

    def test_timesheet_conservation_and_foreign_assignment_fail_closed(self):
        today = timezone.localdate()
        sheet = service.create_own_timesheet(
            actor=self.employee_user,
            organization=self.organization,
            period_start=today,
            period_end=today,
            declared_minutes=120,
        )
        with self.assertRaises(ValidationError):
            service.submit_own(
                actor=self.employee_user,
                organization=self.organization,
                kind="timesheet",
                record_id=sheet.pk,
            )
        foreign = Project.objects.create(
            organization=self.other,
            code="OTHER",
            name="FORBIDDEN",
            created_by=self.other_actor,
        )
        with self.assertRaises(PermissionDenied):
            service.add_own_entry(
                actor=self.employee_user,
                organization=self.organization,
                record_id=sheet.pk,
                work_date=today,
                project=foreign,
                site=None,
                activity=None,
                minutes=120,
            )
        self.assertEqual(sheet.entries.count(), 0)
        form = EntryForm(organization=self.organization, actor=self.employee_user)
        self.assertNotIn(foreign, list(form.fields["project"].queryset))

    def test_attendance_original_and_correction_request_remain_source_owned(self):
        attendance = self.attendance()
        original = list(AttendanceRecord.objects.values())
        request = service.correct_own_attendance(
            actor=self.employee_user,
            organization=self.organization,
            record_id=attendance.pk,
            reason="اصلاح زمان ورود",
            work_date=attendance.work_date,
            check_in_at=attendance.check_in_at + timedelta(minutes=5),
            check_out_at=attendance.check_out_at,
        )
        self.assertEqual(AttendanceCorrectionRequest.objects.count(), 1)
        self.assertEqual(request.status, "pending")
        self.assertEqual(list(AttendanceRecord.objects.values()), original)
        response = self.client_for().get(
            reverse("workforce:ess_timekeeping_detail", args=["correction", request.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pending")

    def test_own_reservation_mode_cannot_be_used_for_peer_relationship(self):
        self.prepared()
        from .leave_services import reserve_request
        from .person_services import create_person, create_work_relationship

        person = create_person(
            organization=self.organization,
            actor=self.actor,
            first_name="Peer",
            last_name="Other",
        )
        relationship = create_work_relationship(
            organization=self.organization,
            actor=self.actor,
            person=person,
            employee_number="PEER",
            effective_start=self.relationship.effective_start,
            legacy_employee=self.peer,
        )
        request = LeaveMissionRequest.objects.create(
            organization=self.organization,
            employee=self.peer,
            kind="leave",
            category_code="EXPLICIT",
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=3),
            reason="PRIVATE",
            requested_by=self.employee_user,
        )
        with self.assertRaises(PermissionDenied):
            reserve_request(
                organization=self.organization,
                actor=self.employee_user,
                relationship=relationship,
                request=request,
                quantity=Decimal(1),
                effective_on=timezone.localdate(),
                source_key="forged",
                evidence_reference="forged",
                reason="forged",
                own_subject=True,
            )

    def test_direct_form_posts_use_own_identity_and_source_status_links(self):
        from core.jalali import format_jalali

        today = timezone.localdate()
        response = self.client_for().post(
            reverse("workforce:ess_timekeeping_create", args=["timesheet"]),
            {
                "period_start": format_jalali(today),
                "period_end": format_jalali(today),
                "declared_minutes": "30",
                "employee": str(self.peer.pk),
                "organization": str(self.other.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        sheet = Timesheet.objects.get()
        self.assertEqual(sheet.employee_id, self.employee.pk)
        response = self.client_for().post(
            reverse(
                "workforce:ess_timekeeping_edit_source", args=["timesheet", sheet.pk]
            ),
            {
                "work_date": format_jalali(today),
                "project": str(self.project.pk),
                "site": "",
                "activity": "",
                "minutes": "30",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(sheet.entries.count(), 1)

    def test_permission_scope_revocation_filters_before_showing_own_sources(self):
        self.prepared()
        request = self.leave()
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.employee_user
        )
        MembershipScopeGrant.objects.filter(membership=membership).delete()
        response = self.client_for().get(
            reverse("workforce:ess_timekeeping_detail", args=["leave", request.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "دلیل شخصی درخواست", status_code=403)

    def test_source_validation_error_is_neutral_and_fail_closed(self):
        with patch.object(
            service,
            "own_rows",
            side_effect=ValidationError("PRIVATE_INTERNAL_SOURCE_DETAIL"),
        ):
            response = self.client_for().get(reverse("workforce:ess_timekeeping"))
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(
            response, "PRIVATE_INTERNAL_SOURCE_DETAIL", status_code=400
        )
