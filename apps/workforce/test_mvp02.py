from datetime import date
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import User
from apps.daily_reports.models import DailyReport
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Project, ProjectSite
from apps.timekeeping.models import AttendanceRecord, OvertimeRequest, Timesheet
from apps.workforce.field_services import save_field_employee
from apps.workforce.models import Employee, Person, WorkTeam
from apps.workforce.person_services import create_person, create_work_relationship
from apps.workforce.services import (
    assign_employee_to_project,
    create_skill,
    link_employee_account,
    record_employee_qualification,
    record_employee_skill,
)
from core.product_surface import route_exposed


def make_field_fixture(owner, organization):
    project = Project.objects.create(
        organization=organization,
        code="BRIDGE",
        name="پروژه پل آزمایشی",
        created_by=owner,
    )
    site = ProjectSite.objects.create(
        organization=organization,
        project=project,
        code="EAST",
        name="کارگاه شرقی",
        created_by=owner,
    )
    team = WorkTeam.objects.create(
        organization=organization,
        code="CREW-2",
        name="اکیپ آرماتوربندی ۲",
        created_by=owner,
    )
    employee = save_field_employee(
        organization=organization,
        actor=owner,
        employee_number="FIELD-001",
        first_name="نیروی",
        last_name="آزمایشی",
        national_id="1234567891",
        start_date=date(2026, 10, 1),
        work_team=team,
    )
    assign_employee_to_project(
        organization=organization,
        actor=owner,
        employee=employee,
        project=project,
        site=site,
        start_date=date(2026, 10, 1),
        role_title="آرماتوربند",
    )
    skill = create_skill(
        organization=organization,
        actor=owner,
        code="FIELD-REBAR",
        name="آرماتوربندی کارگاهی",
    )
    record_employee_skill(
        organization=organization,
        actor=owner,
        employee=employee,
        skill=skill,
        competency=None,
        proficiency_level=3,
        effective_from=date(2026, 10, 1),
    )
    record_employee_qualification(
        organization=organization,
        actor=owner,
        employee=employee,
        kind="certificate",
        title="گواهی آموزش ایمنی کارگاه آزمایشی",
        issued_on=date(2026, 10, 1),
    )
    report = DailyReport.objects.create(
        organization=organization,
        project=project,
        site=site,
        reporting_date=date(2026, 10, 1),
        work_performed="آرماتوربندی عرشه آزمایشی",
        labor_count=4,
        created_by=owner,
        updated_by=owner,
    )
    return project, site, team, employee, report


class FieldWorkforceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="mvp02-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="شرکت نمونه کارگاهی", slug="mvp02"
        )
        self.project, self.site, self.team, self.employee, self.report = (
            make_field_fixture(self.owner, self.organization)
        )
        self.person = self.employee.work_relationships.get().person
        self.client.force_login(self.owner)
        self.query = urlencode({"project": self.project.pk, "site": self.site.pk})

    def _edit(self, **changes):
        data = {
            "organization": self.organization,
            "actor": self.owner,
            "employee": self.employee,
            "employee_number": self.employee.employee_number,
            "first_name": "نیروی",
            "last_name": "آزمایشی",
            "national_id": self.person.national_id,
            "work_team": self.team,
            "phone_number": "",
        }
        data.update(changes)
        return save_field_employee(**data)

    def _reader(self, *, permission_codes=(), site=None):
        user = User.objects.create_user(username=f"mvp02-reader-{User.objects.count()}")
        role = OrganizationRole.objects.create(
            organization=self.organization, code=user.username, name="کاربر آزمایشی"
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(code__in=permission_codes)
        )
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
            project=site.project if site else None,
            site=site,
        )
        return user

    def test_non_login_identity_and_national_id_edit(self):
        self.assertIsNone(self.employee.user_id)
        self.assertIsNone(self.person.user_id)
        self.assertEqual(self.person.national_id, "1234567891")
        self._edit(national_id="۰۰۱۳۵۴۳۶۷۹")
        self.person.refresh_from_db()
        self.assertEqual(self.person.national_id, "0013543679")

    def test_invalid_national_ids_are_rejected_without_persisting(self):
        for value in ("1111111111", "1234567890", "not-an-id"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self._edit(national_id=value)
        self.person.refresh_from_db()
        self.assertEqual(self.person.national_id, "1234567891")

    def test_skill_and_qualification_display_requires_their_permissions(self):
        url = reverse("workforce:field_detail", args=[self.employee.pk])
        response = self.client.get(url)
        self.assertContains(response, "آرماتوربندی کارگاهی")
        self.assertContains(response, "گواهی آموزش ایمنی کارگاه آزمایشی")
        reader = self._reader(permission_codes=["employees.view"])
        self.client.force_login(reader)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "آرماتوربندی کارگاهی")
        self.assertNotContains(response, "گواهی آموزش ایمنی کارگاه آزمایشی")

    def test_duplicate_is_rejected_and_other_tenant_can_use_same_id(self):
        with self.assertRaises(ValidationError):
            Person.objects.create(
                organization=self.organization,
                first_name="دیگر",
                last_name="نیرو",
                national_id=self.person.national_id,
            )
        other = create_organization_with_owner(
            owner=self.owner, name="شرکت دوم", slug="mvp02-other"
        )
        Person.objects.create(
            organization=other,
            first_name="نیروی",
            last_name="دوم",
            national_id=self.person.national_id,
        )

    def test_database_unique_constraint_and_legacy_preservation(self):
        legacy = Employee.objects.create(
            organization=self.organization,
            employee_number="LEGACY",
            first_name="قدیمی",
            last_name="بدون تاریخ",
        )
        self.assertFalse(legacy.work_relationships.exists())
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Person.objects.bulk_create(
                [
                    Person(
                        organization=self.organization,
                        first_name="دیگر",
                        last_name="نیرو",
                        national_id=self.person.national_id,
                    )
                ]
            )
        legacy.refresh_from_db()
        self.assertIsNone(legacy.hire_date)

    def test_employee_user_link_rejects_conflict_and_user_edits_cannot_drift(self):
        member = self._reader()
        member.national_id = "0013543679"
        member.save()
        with self.assertRaises(ValueError):
            link_employee_account(
                organization=self.organization,
                actor=self.owner,
                employee=self.employee,
                user=member,
            )
        member.national_id = "1234567891"
        member.save()
        link_employee_account(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            user=member,
        )
        member.national_id = "0013543679"
        with self.assertRaises(ValidationError):
            member.save()
        member.refresh_from_db()
        self.assertEqual(member.national_id, "1234567891")
        with self.assertRaises(ValidationError):
            self._edit(national_id="0013543679")

    def test_person_user_and_episode_links_reject_conflicts(self):
        member = self._reader()
        member.national_id = "0013543679"
        member.save()
        self.person.user = member
        with self.assertRaises(ValidationError):
            self.person.save()
        legacy = Employee.objects.create(
            organization=self.organization,
            employee_number="LINKED",
            first_name="حساب",
            last_name="متصل",
            user=member,
        )
        with self.assertRaises(ValidationError):
            create_work_relationship(
                organization=self.organization,
                actor=self.owner,
                person=self.person,
                employee_number="LINKED",
                effective_start=date(2027, 1, 1),
                legacy_employee=legacy,
            )

    def test_effective_user_id_cannot_be_used_for_second_person(self):
        member = self._reader()
        member.national_id = "0013543679"
        member.save()
        create_person(
            organization=self.organization,
            actor=self.owner,
            first_name="متصل",
            last_name="دوم",
            user=member,
        )
        with self.assertRaises(ValidationError):
            self._edit(national_id="0013543679")

    def test_create_and_form_edit_without_account_or_hr(self):
        url = reverse("workforce:field_create")
        response = self.client.post(
            url,
            {
                "employee_number": "NEW-2",
                "first_name": "نیروی",
                "last_name": "تازه",
                "national_id": "0013543679",
                "start_date": "2026-10-02",
            },
        )
        self.assertEqual(response.status_code, 302)
        employee = Employee.objects.get(
            employee_number="NEW-2", organization=self.organization
        )
        self.assertIsNone(employee.user_id)
        person = employee.work_relationships.get().person
        self.assertEqual(person.national_id, "0013543679")
        edit = self.client.post(
            reverse("workforce:field_edit", args=[employee.pk]),
            {
                "first_name": "نیروی",
                "last_name": "ویرایش",
                "national_id": "0013543679",
                "phone_number": "",
            },
        )
        self.assertEqual(edit.status_code, 302)
        person.refresh_from_db()
        self.assertEqual(person.last_name, "ویرایش")

    def test_field_list_detail_context_and_product_surface(self):
        response = self.client.get(reverse("workforce:field_list") + "?" + self.query)
        self.assertContains(response, "آرماتوربند")
        self.assertContains(response, self.team.name)
        self.assertContains(response, self.site.name)
        detail = self.client.get(
            reverse("workforce:field_detail", args=[self.employee.pk])
            + "?"
            + self.query
        )
        self.assertContains(detail, self.person.national_id)
        for name in (
            "field_list",
            "field_create",
            "field_detail",
            "field_edit",
            "field_assign",
            "field_choices",
        ):
            self.assertTrue(route_exposed(f"workforce:{name}"))
        self.assertEqual(
            self.client.get(reverse("workforce:ess_dashboard")).status_code, 403
        )
        self.assertNotContains(detail, "/workforce/foundation/")
        self.assertContains(detail, reverse("timekeeping:attendance_create"))
        self.assertContains(detail, reverse("timekeeping:timesheet_create"))
        self.assertContains(detail, reverse("timekeeping:overtime_create"))

    def test_project_site_daily_report_links_have_no_data_effects(self):
        before = (
            Employee.objects.count(),
            AttendanceRecord.objects.count(),
            Timesheet.objects.count(),
            OvertimeRequest.objects.count(),
        )
        for url in (
            reverse("projects:detail", args=[self.project.pk]),
            reverse("projects:site_detail", args=[self.project.pk, self.site.pk]),
            reverse("daily_reports:detail", args=[self.report.pk]),
        ):
            response = self.client.get(url)
            self.assertContains(
                response, reverse("workforce:field_list") + "?project=", html=False
            )
        self.assertEqual(
            before,
            (
                Employee.objects.count(),
                AttendanceRecord.objects.count(),
                Timesheet.objects.count(),
                OvertimeRequest.objects.count(),
            ),
        )

    def test_permission_and_foreign_tenant_denials(self):
        reader = self._reader()
        self.client.force_login(reader)
        self.assertEqual(
            self.client.get(reverse("workforce:field_list")).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("timekeeping:workbench")).status_code, 403
        )
        with self.assertRaises(PermissionDenied):
            save_field_employee(
                organization=self.organization,
                actor=reader,
                first_name="ممنوع",
                last_name="ممنوع",
                employee_number="DENY",
                start_date=date(2026, 1, 1),
            )
        foreign = User.objects.create_user(username="mvp02-foreign")
        create_organization_with_owner(
            owner=foreign, name="بیگانه", slug="mvp02-foreign"
        )
        self.client.force_login(foreign)
        self.assertEqual(
            self.client.get(
                reverse("workforce:field_detail", args=[self.employee.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("workforce:field_list") + "?" + self.query
            ).status_code,
            404,
        )

    def test_site_scope_context_and_forged_selector(self):
        other_site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="WEST",
            name="کارگاه غربی",
            created_by=self.owner,
        )
        reader = self._reader(
            permission_codes=("attendance.view", "attendance.capture"), site=other_site
        )
        self.client.force_login(reader)
        self.assertEqual(
            self.client.get(
                reverse("timekeeping:workbench") + "?" + self.query
            ).status_code,
            404,
        )
        response = self.client.get(
            reverse("workforce:field_choices", args=["employee"])
        )
        self.assertEqual(response.json()["results"], [])
        response = self.client.get(
            reverse("timekeeping:attendance_create")
            + "?employee="
            + str(self.employee.pk)
        )
        self.assertEqual(response.status_code, 404)

    def test_field_read_intersects_employee_permission_with_site_assignment(self):
        actor = self._reader(permission_codes=("employees.view",), site=self.site)
        self.client.force_login(actor)
        response = self.client.get(reverse("workforce:field_list") + "?" + self.query)
        self.assertContains(response, self.employee.last_name)
        self.assertNotContains(response, reverse("workforce:field_create"))
        self.assertEqual(
            self.client.get(
                reverse("workforce:field_detail", args=[self.employee.pk])
            ).status_code,
            200,
        )
        unassigned = Employee.objects.create(
            organization=self.organization,
            employee_number="PRIVATE",
            first_name="سایر",
            last_name="نیرو",
        )
        self.assertEqual(
            self.client.get(
                reverse("workforce:field_detail", args=[unassigned.pk])
            ).status_code,
            404,
        )

    def test_legacy_national_id_requires_explicit_date(self):
        legacy = Employee.objects.create(
            organization=self.organization,
            employee_number="UNDATED",
            first_name="نیروی",
            last_name="قدیمی",
        )
        with self.assertRaises(ValidationError):
            save_field_employee(
                organization=self.organization,
                actor=self.owner,
                employee=legacy,
                first_name=legacy.first_name,
                last_name=legacy.last_name,
                national_id="0013543679",
            )
        self.assertFalse(legacy.work_relationships.exists())

    def test_contextual_create_requires_explicit_assignment_confirmation(self):
        data = {
            "employee_number": "CTX-NEW",
            "first_name": "نیروی",
            "last_name": "کارگاه",
            "start_date": "2026-10-01",
            "national_id": "0013543679",
        }
        url = reverse("workforce:field_create") + "?" + self.query
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertFalse(Employee.objects.filter(employee_number="CTX-NEW").exists())
        data["assign_here"] = "on"
        self.assertEqual(self.client.post(url, data).status_code, 302)
        worker = Employee.objects.get(
            organization=self.organization, employee_number="CTX-NEW"
        )
        self.assertTrue(
            worker.project_assignments.filter(
                project=self.project, site=self.site
            ).exists()
        )

    def test_choices_are_bounded_and_business_labelled(self):
        response = self.client.get(
            reverse("workforce:field_choices", args=["project"]), {"q": "پل"}
        )
        self.assertEqual(response.json()["results"][0]["label"], f"{self.project.name} · {self.project.code}")
        self.assertIn("no-store", response["Cache-Control"])

    def test_search_finds_catalogue_records_beyond_the_initial_bound(self):
        WorkTeam.objects.bulk_create(
            [
                WorkTeam(
                    organization=self.organization,
                    code=f"SEARCH-CREW-{i}",
                    name=f"اکیپ اجرایی {i}",
                )
                for i in range(50)
            ]
        )
        url = reverse("workforce:field_choices", args=["team"])
        self.assertEqual(len(self.client.get(url).json()["results"]), 40)
        result = self.client.get(url, {"q": "اجرایی 49"}).json()["results"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["label"], "اکیپ اجرایی 49 · SEARCH-CREW-49")

    def test_worker_list_paging_and_query_growth(self):
        url = reverse("workforce:field_list")
        with CaptureQueriesContext(connection) as before:
            self.assertEqual(self.client.get(url).status_code, 200)
        Employee.objects.bulk_create(
            [
                Employee(
                    organization=self.organization,
                    employee_number=f"PAGE-{i}",
                    first_name="نیروی",
                    last_name=f"کارگاه {i}",
                    work_team=self.team,
                )
                for i in range(31)
            ]
        )
        with CaptureQueriesContext(connection) as after:
            response = self.client.get(url)
            self.assertEqual(len(response.context["rows"]), 25)
        self.assertLessEqual(len(after), len(before), (len(before), len(after)))
        self.assertEqual(len(self.client.get(url, {"page": 2}).context["rows"]), 7)
