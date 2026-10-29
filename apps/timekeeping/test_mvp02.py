from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import ProjectSite
from apps.workforce.test_mvp02 import make_field_fixture

from .forms import AttendanceForm, TimesheetForm
from .models import AttendanceRecord, OvertimeRequest, Timesheet
from .services import (
    add_timesheet_entry,
    capture_attendance,
    create_overtime_request,
    create_timesheet,
    create_work_calendar,
)


class FieldTimekeepingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="mvp02-time-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="حضور کارگاه نمونه", slug="mvp02-time"
        )
        self.project, self.site, self.team, self.employee, _ = make_field_fixture(
            self.owner, self.organization
        )
        self.calendar = create_work_calendar(
            organization=self.organization,
            actor=self.owner,
            code="FIELD",
            name="تقویم کارگاه نمونه",
            effective_from=date(2026, 1, 1),
            working_weekdays=[1, 2, 3, 4, 5],
        )
        self.client.force_login(self.owner)
        self.url = reverse("timekeeping:workbench")

    def _attendance(self, day):
        tz = ZoneInfo(self.organization.settings.timezone)
        return capture_attendance(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            calendar=self.calendar,
            project=self.project,
            site=self.site,
            work_date=day,
            check_in_at=datetime.combine(day, time(8), tzinfo=tz),
            check_out_at=datetime.combine(day, time(16), tzinfo=tz),
        )

    def test_history_paging_filters_and_stable_query_growth(self):
        first_day = date(2026, 9, 1)
        self._attendance(first_day)
        with CaptureQueriesContext(connection) as before:
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
        for offset in range(1, 32):
            self._attendance(first_day + timedelta(days=offset))
        with CaptureQueriesContext(connection) as after:
            response = self.client.get(self.url)
            self.assertEqual(len(response.context["attendance_records"]), 25)
        self.assertLessEqual(len(after), len(before), (len(before), len(after)))
        response = self.client.get(
            self.url,
            {"attendance_page": 2, "project": self.project.pk, "site": self.site.pk},
        )
        self.assertEqual(len(response.context["attendance_records"]), 7)
        self.assertContains(response, "attendance_page=1")
        response = self.client.get(
            self.url, {"date_from": "2026-09-01", "date_to": "2026-09-03"}
        )
        self.assertEqual(len(response.context["attendance_records"]), 3)
        invalid = self.client.get(self.url, {"date_from": "bad-date"})
        self.assertEqual(list(invalid.context["attendance_records"]), [])

    def test_context_initial_values_business_labels_and_separate_sources(self):
        attendance = self._attendance(date(2026, 10, 1))
        count = AttendanceRecord.objects.count()
        sheet = create_timesheet(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 1),
            declared_minutes=480,
        )
        add_timesheet_entry(
            organization=self.organization,
            actor=self.owner,
            timesheet=sheet,
            work_date=date(2026, 10, 1),
            project=self.project,
            site=self.site,
            minutes=480,
        )
        create_overtime_request(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.project,
            site=self.site,
            starts_at=attendance.check_out_at,
            ends_at=attendance.check_out_at + timedelta(hours=2),
            reason="تکمیل کار بتن‌ریزی آزمایشی",
        )
        response = self.client.get(
            self.url,
            {
                "project": self.project.pk,
                "site": self.site.pk,
                "employee": self.employee.pk,
            },
        )
        self.assertEqual(len(response.context["attendance_records"]), 1)
        self.assertEqual(len(response.context["overtime_requests"]), 1)
        self.assertEqual(len(response.context["timesheets"]), 1)
        self.assertEqual(AttendanceRecord.objects.count(), count)
        self.assertEqual(OvertimeRequest.objects.get().state, "draft")
        self.assertEqual(Timesheet.objects.get().state, "draft")
        for route in ("attendance_create", "timesheet_create", "overtime_create"):
            response = self.client.get(
                reverse(f"timekeeping:{route}"),
                {
                    "project": self.project.pk,
                    "site": self.site.pk,
                    "employee": self.employee.pk,
                },
            )
            self.assertEqual(response.status_code, 200)
            form = response.context["form"]
            self.assertEqual(form.initial["employee"].pk, self.employee.pk)
            self.assertNotContains(response, "WorkCalendar object")
        attendance_form = AttendanceForm(
            organization=self.organization, user=self.owner
        )
        self.assertEqual(
            attendance_form.fields["calendar"].label_from_instance(self.calendar),
            f"{self.calendar.name} · {self.calendar.code}",
        )

    def test_own_empty_timesheets_remain_discoverable(self):
        sheet = create_timesheet(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 1),
            declared_minutes=60,
        )
        response = self.client.get(self.url)
        self.assertIn(sheet, response.context["timesheets"])
        form = TimesheetForm(organization=self.organization, user=self.owner)
        self.assertNotIn(
            str(self.employee.pk),
            " ".join(str(label) for _, label in form.fields["employee"].widget.choices),
        )

    def _reader(self, codes, *, site=None):
        user = User.objects.create_user(username="mvp02-time-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="mvp02-time-reader",
            name="ناظر آزمایشی",
        )
        role.permissions.add(*BusinessPermission.objects.filter(code__in=codes))
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status="active",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.SITE
            if site
            else AuthorizationScopeType.ORGANIZATION,
            project=self.project if site else None,
            site=site,
        )
        return user

    def test_mixed_site_sheet_never_exposes_out_of_scope_entries_or_totals(self):
        sheet = create_timesheet(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 1),
            declared_minutes=120,
        )
        other_site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="OTHER",
            name="کارگاه دیگر",
            created_by=self.owner,
        )
        for site in (self.site, other_site):
            add_timesheet_entry(
                organization=self.organization,
                actor=self.owner,
                timesheet=sheet,
                work_date=date(2026, 10, 1),
                project=self.project,
                site=site,
                minutes=60,
            )
        reader = self._reader(["attendance.view", "timesheets.view"], site=self.site)
        self.client.force_login(reader)
        response = self.client.get(self.url)
        self.assertNotIn(sheet, response.context["timesheets"])
        self.assertEqual(
            self.client.get(
                reverse("timekeeping:timesheet_detail", args=[sheet.pk])
            ).status_code,
            404,
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(
                reverse("timekeeping:timesheet_detail", args=[sheet.pk])
            ).status_code,
            200,
        )

    def test_record_detail_requires_the_source_permission(self):
        attendance = self._attendance(date(2026, 10, 1))
        overtime = create_overtime_request(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.project,
            site=self.site,
            starts_at=attendance.check_out_at,
            ends_at=attendance.check_out_at + timedelta(hours=1),
            reason="تکمیل کار آزمایشی",
        )
        reader = self._reader(["attendance.view"])
        self.client.force_login(reader)
        self.assertEqual(
            self.client.get(
                reverse("timekeeping:record_detail", args=["attendance", attendance.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("timekeeping:record_detail", args=["overtime", overtime.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            list(self.client.get(self.url).context["overtime_requests"]), []
        )

    def test_datetime_history_filters_use_the_organization_timezone(self):
        self.organization.settings.timezone = "Asia/Tehran"
        self.organization.settings.save()
        starts = datetime(2026, 10, 1, 0, 30, tzinfo=ZoneInfo("Asia/Tehran"))
        item = create_overtime_request(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.project,
            site=self.site,
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            reason="آزمایش تاریخ محلی",
        )
        response = self.client.get(
            self.url, {"date_from": "2026-10-01", "date_to": "2026-10-01"}
        )
        self.assertIn(item, response.context["overtime_requests"])
        response = self.client.get(
            self.url, {"date_from": "2026-09-30", "date_to": "2026-09-30"}
        )
        self.assertNotIn(item, response.context["overtime_requests"])
