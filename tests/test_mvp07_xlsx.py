"""Real HTTP XLSX representations: source versions, filters and access boundaries."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import User
from apps.daily_reports.models import (
    DailyActivity,
    DailyReport,
    DailyReportEquipmentEntry,
    DailyReportLaborEntry,
    DailyReportMaterialEntry,
    DelayEvent,
)
from apps.equipment.models import Equipment, EquipmentAssignment
from apps.equipment.p8_models import EquipmentUsageLog
from apps.estimates.models import Estimate, EstimateItem, EstimateRevision
from apps.organizations.models import (
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationRole,
    OrganizationStatus,
)
from apps.procurement.test_mvp04d import ReceiptJourneyFixture
from apps.projects.models import Project, ProjectSite
from apps.timekeeping.models import (
    AttendanceRecord,
    OvertimeRequest,
    Timesheet,
    TimesheetEntry,
    WorkCalendar,
)
from apps.workforce.test_mvp02 import make_field_fixture
from tests.test_mvp05_xlsx import WorkbookAssertions

DAY = date(2026, 11, 3)
START = datetime(2026, 11, 3, 5, 0, tzinfo=UTC)


class P1Fixture(ReceiptJourneyFixture):
    def setUp(self):
        super().setUp()
        settings = self.organization.settings
        settings.timezone = "Asia/Tehran"
        settings.save(update_fields=["timezone"])
        self.field_project, self.site, _, self.employee, self.report = (
            make_field_fixture(self.owner, self.organization)
        )
        self.estimate = Estimate.objects.create(
            organization=self.organization,
            project=self.field_project,
            estimate_number="EST-007",
            title="برآورد پی",
            created_by=self.owner,
        )
        self.revision = EstimateRevision.objects.create(
            organization=self.organization, estimate=self.estimate, revision_number=1
        )
        self.line = EstimateItem.objects.create(
            organization=self.organization,
            estimate=self.estimate,
            revision=self.revision,
            description="=1+1",
            quantity=Decimal("1.2345"),
            unit_price=Decimal("125.67"),
            unit_of_measure=self.unit,
        )
        self.estimate.current_revision = self.revision
        self.estimate.save()
        old = EstimateRevision.objects.create(
            organization=self.organization, estimate=self.estimate, revision_number=2
        )
        EstimateItem.objects.create(
            organization=self.organization,
            estimate=self.estimate,
            revision=old,
            description="ردیف نسخه دیگر",
            quantity=1,
            unit_price=999,
        )
        DailyActivity.objects.create(
            organization=self.organization,
            report=self.report,
            description="عملیات پی",
            quantity=Decimal("1.2345"),
            unit_of_measure=self.unit,
            progress_percent=Decimal("12.50"),
        )
        DailyReportLaborEntry.objects.create(
            organization=self.organization,
            report=self.report,
            team_name="اکیپ نمونه",
            worker_count=3,
            hours_worked=Decimal("7.5"),
        )
        DailyReportEquipmentEntry.objects.create(
            organization=self.organization,
            report=self.report,
            equipment_name="جرثقیل",
            hours_used=Decimal("2.25"),
        )
        DailyReportMaterialEntry.objects.create(
            organization=self.organization,
            report=self.report,
            material_name="مصالح قدیمی",
            quantity=Decimal("3.125"),
            unit="متر",
        )
        DelayEvent.objects.create(
            organization=self.organization,
            report=self.report,
            occurred_on=DAY,
            cause="توقف حمل",
            duration_hours=Decimal("1.25"),
        )
        calendar = WorkCalendar.objects.create(
            organization=self.organization,
            code="P1",
            name="تقویم نمونه",
            timezone="Asia/Tehran",
            effective_from=DAY,
            working_weekdays=[1, 2, 3, 4, 5],
            created_by=self.owner,
        )
        self.attendance = AttendanceRecord.objects.create(
            organization=self.organization,
            employee=self.employee,
            project=self.field_project,
            site=self.site,
            calendar=calendar,
            work_date=DAY,
            check_in_at=START,
            check_out_at=START + timedelta(hours=8),
            source="manual",
            captured_by=self.owner,
        )
        self.overtime = OvertimeRequest.objects.create(
            organization=self.organization,
            employee=self.employee,
            project=self.field_project,
            site=self.site,
            starts_at=START + timedelta(hours=8),
            ends_at=START + timedelta(hours=9),
            reason="تکمیل بتن‌ریزی",
            requested_by=self.owner,
        )
        self.timesheet = Timesheet.objects.create(
            organization=self.organization,
            employee=self.employee,
            period_start=DAY,
            period_end=DAY,
            declared_minutes=480,
            prepared_by=self.owner,
        )
        self.entry = TimesheetEntry.objects.create(
            organization=self.organization,
            timesheet=self.timesheet,
            project=self.field_project,
            site=self.site,
            work_date=DAY,
            minutes=480,
            note="@SUM(A1)",
        )
        self.equipment = Equipment.objects.create(
            organization=self.organization,
            code="EQ-007",
            name="جرثقیل نمونه",
            category="بالابر",
            ownership_type="owned",
            acquired_on=DAY,
        )
        self.assignment = EquipmentAssignment.objects.create(
            organization=self.organization,
            equipment=self.equipment,
            project=self.field_project,
            site=self.site,
            start_date=DAY,
            purpose="حمل مصالح",
        )
        self.usage = EquipmentUsageLog.objects.create(
            organization=self.organization,
            equipment=self.equipment,
            deployment=self.assignment,
            operator=self.employee,
            started_at=START,
            ended_at=START + timedelta(hours=2),
            runtime_hours=Decimal("1.125"),
            source_key="test-internal-key-do-not-export",
            created_by=self.owner,
        )
        self.login(self.owner)

    def routes(self):
        return [
            reverse(name)
            for name in (
                "daily_reports:list",
                "estimates:list",
                "timekeeping:workbench",
                "equipment:list",
                "equipment:assignment_list",
                "equipment:operations_workbench",
            )
        ]

    def reader(self, codes, *, project=None, site=None):
        actor = User.objects.create_user(username=f"p1-reader-{User.objects.count()}")
        role = OrganizationRole.objects.create(
            organization=self.organization, code=actor.username, name="کاربر نمونه"
        )
        role.permissions.add(*BusinessPermission.objects.filter(code__in=codes))
        member = self.organization.memberships.create(
            user=actor, role_definition=role, status="active"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="site" if site else "project" if project else "organization",
            project=project,
            site=site,
        )
        return actor


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class P1ExportTests(WorkbookAssertions, P1Fixture, TestCase):
    def test_daily_all_six_sheets_values_filters_and_empty(self):
        from apps.daily_reports.xlsx_exports import REPORT_COLUMNS

        wb = self.workbook(self.routes()[0], rows=1)
        self.assertEqual(
            wb.sheetnames,
            [
                "گزارش‌های روزانه",
                "فعالیت‌ها",
                "نیروی انسانی",
                "تجهیزات",
                "مصالح",
                "تأخیرها",
            ],
        )
        self.assertEqual(
            [c.value for c in wb.active[1]], [c.label for c in REPORT_COLUMNS]
        )
        self.assertEqual(wb.active["D2"].data_type, "d")
        self.assertEqual(wb["فعالیت‌ها"]["G2"].value, 1.2345)
        self.assertEqual(wb["مصالح"]["E2"].value, "مصالح قدیمی")
        self.assertEqual(wb["مصالح"]["G2"].value, "متر")
        empty = self.workbook(self.routes()[0], {"q": "غیرموجود"}, rows=0)
        self.assertTrue(all(sheet.max_row == 1 for sheet in empty))
        self.workbook(self.routes()[0], {"reporting_date_from": "bad"}, rows=0)
        self.workbook(self.routes()[0], {"site_filter": self.site.pk}, rows=1)
        self.workbook(self.routes()[0], {"reporting_date_from": "2026-11-03"}, rows=0)

    def test_estimate_current_revision_model_owned_amount_and_legacy(self):
        from apps.estimates.services import approve_estimate

        approve_estimate(actor=self.owner, estimate=self.estimate)
        wb = self.workbook(self.routes()[1], rows=1)
        self.estimate.refresh_from_db()
        self.assertEqual(wb.active["I2"].value, float(self.estimate.total_amount))
        self.assertEqual(wb["ردیف‌های برآورد"].max_row, 2)
        self.assertEqual(wb["ردیف‌های برآورد"]["D2"].value, "=1+1")
        self.assertEqual(wb["ردیف‌های برآورد"]["D2"].data_type, "s")
        self.assertEqual(wb["ردیف‌های برآورد"]["H2"].value, float(self.line.line_total))
        self.assertEqual(wb.active["J2"].data_type, "d")
        self.workbook(self.routes()[1], {"number": "not-found"}, rows=0)
        legacy = Estimate.objects.create(
            organization=self.organization,
            project=self.field_project,
            estimate_number="LEGACY",
            title="قدیمی",
        )
        item = EstimateItem.objects.create(
            organization=self.organization,
            estimate=legacy,
            quantity=2,
            unit_price=3,
            description="قدیمی",
            unit="متر",
        )
        wb = self.workbook(self.routes()[1], {"number": "LEGACY"}, rows=1)
        self.assertEqual(wb.active["I2"].value, float(item.line_total))
        self.assertEqual(wb["ردیف‌های برآورد"]["E2"].value, "متر")

    def test_timekeeping_separate_sources_native_values_and_tenant_timezone(self):
        wb = self.workbook(self.routes()[2], rows=1)
        self.assertEqual(wb.sheetnames, ["حضور", "کارکرد", "توزیع زمان", "اضافه‌کاری"])
        self.assertEqual(wb["حضور"]["E2"].value.hour, 8)
        self.assertEqual(wb["حضور"]["E2"].value.minute, 30)
        self.assertEqual(wb["کارکرد"]["E2"].value, 480)
        self.assertEqual(wb["توزیع زمان"]["I2"].value, 480)
        self.assertEqual(wb["توزیع زمان"]["J2"].value, "@SUM(A1)")
        self.assertEqual(wb["اضافه‌کاری"]["D2"].data_type, "d")
        self.workbook(self.routes()[2], {"date_from": "2026-11-04"}, rows=0)
        self.workbook(self.routes()[2], {"date_from": "invalid"}, rows=0)
        self.workbook(
            self.routes()[2],
            {"project": self.field_project.pk, "site": self.site.pk},
            rows=1,
        )

    def test_equipment_operational_sources_and_filters(self):
        wb = self.workbook(self.routes()[3], rows=1)
        self.assertEqual(wb.active["J2"].data_type, "d")
        self.workbook(self.routes()[3], {"equipment": "missing"}, rows=0)
        self.workbook(self.routes()[4], {"project": self.field_project.name}, rows=1)
        self.workbook(self.routes()[4], {"start_date_from": "2026-11-04"}, rows=0)
        wb = self.workbook(self.routes()[5], rows=1)
        self.assertEqual(wb.active["G2"].value, 1.125)
        self.assertEqual(wb.active["E2"].data_type, "d")
        self.assertNotIn(self.usage.source_key, str(list(wb.active.values)))

    def test_full_dataset_before_pagination_and_query_growth(self):
        DailyReport.objects.bulk_create(
            [
                DailyReport(
                    organization=self.organization,
                    project=self.field_project,
                    site=self.site,
                    reporting_date=DAY + timedelta(days=i + 1),
                    work_performed="گزارش نمونه",
                )
                for i in range(31)
            ]
        )
        wb = self.workbook(self.routes()[0], {"page": 2}, rows=32)
        self.assertEqual(wb.active.max_row, 33)
        with CaptureQueriesContext(connection) as small:
            self.workbook(self.routes()[1], rows=1)
        Estimate.objects.bulk_create(
            [
                Estimate(
                    organization=self.organization,
                    project=self.field_project,
                    estimate_number=f"B-{i}",
                    title="نمونه",
                )
                for i in range(31)
            ]
        )
        with CaptureQueriesContext(connection) as large:
            self.workbook(self.routes()[1], {"page": 2}, rows=32)
        self.assertLessEqual(len(large), len(small) + 2)

    def test_missing_permissions_anonymous_foreign_tenant_and_tenant_lifecycle(self):
        actor = self.reader([])
        self.login(actor)
        for route in self.routes():
            self.assertEqual(
                self.client.get(route, {"format": "xlsx"}).status_code, 403
            )
        self.login(self.outsider)
        for route in self.routes():
            response = self.client.get(route, {"format": "xlsx"})
            if response.status_code == 200:
                wb = self.workbook(route, rows=0)
                self.assertTrue(all(sheet.max_row == 1 for sheet in wb))
            else:
                self.assertEqual(response.status_code, 403)
        self.client.logout()
        for route in self.routes():
            self.assertIn(
                self.client.get(route, {"format": "xlsx"}).status_code, (302, 403)
            )
        self.login(self.owner)
        self.organization.status = OrganizationStatus.CANCELLED
        self.organization.save(update_fields=["status"])
        for route in self.routes():
            self.assertIn(
                self.client.get(route, {"format": "xlsx"}).status_code, (302, 403)
            )

    def test_site_scope_filters_foreign_ids_and_child_history_scope(self):
        other = Project.objects.create(
            organization=self.organization, code="OUT", name="خارج از دامنه"
        )
        site = ProjectSite.objects.create(
            organization=self.organization, project=other, code="OUT", name="خارج"
        )
        codes = [
            "daily_reports.view",
            "estimates.view",
            "attendance.view",
            "timesheets.view",
            "overtime.view",
            "equipment_assignments.view",
            "equipment_operations.view",
        ]
        actor = self.reader(codes, project=other, site=site)
        self.login(actor)
        for route in (
            self.routes()[0],
            self.routes()[1],
            self.routes()[2],
            self.routes()[4],
        ):
            wb = self.workbook(route, rows=0)
            self.assertTrue(all(sheet.max_row == 1 for sheet in wb))
        # Operational evidence is organization-authority only in the catalog.
        self.assertEqual(
            self.client.get(self.routes()[5], {"format": "xlsx"}).status_code, 403
        )
        self.workbook(
            self.routes()[0], {"project_filter": self.field_project.pk}, rows=0
        )
        self.login(self.owner)
        self.workbook(self.routes()[1], {"contract": "not-a-uuid"}, rows=0)
        member = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=member).delete()
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="site",
            project=self.field_project,
            site=self.site,
        )
        TimesheetEntry.objects.create(
            organization=self.organization,
            timesheet=self.timesheet,
            project=other,
            site=site,
            work_date=DAY,
            minutes=1,
        )
        wb = self.workbook(self.routes()[2], rows=1)
        self.assertEqual(wb["کارکرد"].max_row, 1)
        self.assertEqual(wb["توزیع زمان"].max_row, 1)

    def test_per_source_permission_absence_and_read_only(self):
        actor = self.reader(["attendance.view"])
        self.login(actor)
        with CaptureQueriesContext(connection) as queries:
            wb = self.workbook(self.routes()[2], rows=1)
        for name in ("کارکرد", "توزیع زمان", "اضافه‌کاری"):
            self.assertEqual(wb[name].max_row, 1)
        writes = [
            q["sql"]
            for q in queries
            if q["sql"].split()[0].upper() in ("UPDATE", "INSERT", "DELETE")
            and "django_session" not in q["sql"]
        ]
        self.assertEqual(writes, [])

    def test_equipment_filtered_empty_and_genuine_empty_remain_distinct(self):
        for route in (self.routes()[3], self.routes()[4]):
            response = self.client.get(route, {"equipment": "NOTFOUND"})
            self.assertContains(response, "نتیجه‌ای با این فیلترها یافت نشد")
            self.assertContains(response, f'href="{route}" data-empty-clear-filters')
            self.assertNotContains(response, "ثبت نشده است")
            restored = self.client.get(route)
            self.assertContains(restored, self.equipment.name)
            self.assertNotContains(restored, "data-empty-clear-filters")
        self.login(self.outsider)
        response = self.client.get(self.routes()[3])
        self.assertContains(response, "هنوز تجهیزی ثبت نشده است")
        self.assertNotContains(response, "data-empty-clear-filters")

    def test_timekeeping_and_equipment_export_complete_filtered_pages(self):
        records = []
        for offset in range(1, 28):
            records.append(
                AttendanceRecord(
                    organization=self.organization,
                    employee=self.employee,
                    project=self.field_project,
                    site=self.site,
                    calendar=self.attendance.calendar,
                    work_date=DAY + timedelta(days=offset),
                    check_in_at=START + timedelta(days=offset),
                    source="manual",
                    captured_by=self.owner,
                )
            )
        AttendanceRecord.objects.bulk_create(records)
        sheets = [
            Timesheet(
                organization=self.organization,
                employee=self.employee,
                period_start=DAY + timedelta(days=offset),
                period_end=DAY + timedelta(days=offset),
                declared_minutes=1,
                prepared_by=self.owner,
            )
            for offset in range(1, 28)
        ]
        Timesheet.objects.bulk_create(sheets)
        TimesheetEntry.objects.bulk_create(
            [
                TimesheetEntry(
                    organization=self.organization,
                    timesheet=sheet,
                    project=self.field_project,
                    site=self.site,
                    work_date=sheet.period_start,
                    minutes=1,
                )
                for sheet in sheets
            ]
        )
        OvertimeRequest.objects.bulk_create(
            [
                OvertimeRequest(
                    organization=self.organization,
                    employee=self.employee,
                    project=self.field_project,
                    site=self.site,
                    starts_at=START + timedelta(days=offset),
                    ends_at=START + timedelta(days=offset, hours=1),
                    reason="کار تکمیلی",
                    requested_by=self.owner,
                )
                for offset in range(1, 28)
            ]
        )
        wb = self.workbook(
            self.routes()[2],
            {
                "attendance_page": 2,
                "timesheet_page": 2,
                "overtime_page": 2,
                "project": self.field_project.pk,
            },
            rows=28,
        )
        self.assertTrue(all(sheet.max_row == 29 for sheet in wb))
        equipment = [
            Equipment(
                organization=self.organization,
                code=f"PAGED-{offset}",
                name="جرثقیل صفحه‌بندی",
                category="بالابر",
            )
            for offset in range(27)
        ]
        Equipment.objects.bulk_create(equipment)
        EquipmentAssignment.objects.bulk_create(
            [
                EquipmentAssignment(
                    organization=self.organization,
                    equipment=item,
                    project=self.field_project,
                    site=self.site,
                    start_date=DAY,
                )
                for item in equipment
            ]
        )
        self.workbook(self.routes()[3], {"page": 2, "equipment": "جرثقیل"}, rows=28)
        self.workbook(self.routes()[4], {"page": 2, "equipment": "جرثقیل"}, rows=28)
        EquipmentUsageLog.objects.bulk_create(
            [
                EquipmentUsageLog(
                    organization=self.organization,
                    equipment=self.equipment,
                    deployment=self.assignment,
                    started_at=START + timedelta(days=offset),
                    ended_at=START + timedelta(days=offset, hours=2),
                    runtime_hours=Decimal("1.125"),
                    source_key=f"paged-usage-{offset}",
                    created_by=self.owner,
                )
                for offset in range(1, 52)
            ]
        )
        self.workbook(self.routes()[5], rows=52)
        response = self.client.get(
            self.routes()[2], {"attendance_page": 2, "project": self.field_project.pk}
        )
        import re
        from html import unescape
        from urllib.parse import parse_qs, urlsplit

        href = unescape(
            re.search(r'href="([^"]+)" data-xlsx-export', response.content.decode())[1]
        )
        query = parse_qs(urlsplit(href).query)
        self.assertEqual(query["project"], [str(self.field_project.pk)])
        self.assertEqual(query["format"], ["xlsx"])
        self.assertNotIn("attendance_page", query)
