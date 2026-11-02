"""Bounded UI regression and real installed Chrome verification, no production data."""

import hashlib
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
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
from apps.projects.models import Project, ProjectSite
from apps.timekeeping import services as time
from apps.timekeeping.presentation import record_actions
from apps.workforce import test_mvp02_browser as browser
from apps.workforce.field_presentation import presentation_error
from apps.workforce.field_selectors import FieldContext
from apps.workforce.models import Employee, WorkTeam
from apps.workforce.test_mvp02 import make_field_fixture

EVIDENCE = "output/mvp-02/conformance-20261102"


def fixture(case):
    case.owner = User.objects.create_user(username="conformance-owner")
    case.organization = create_organization_with_owner(
        owner=case.owner, name="شرکت نمونه بنیرا", slug="conformance"
    )
    case.project, case.site, case.team, case.employee, _ = make_field_fixture(
        case.owner, case.organization
    )
    case.calendar = time.create_work_calendar(
        organization=case.organization,
        actor=case.owner,
        code="FIELD",
        name="تقویم کارگاه",
        effective_from=date(2026, 1, 1),
        working_weekdays=[1, 2, 3, 4, 5],
    )


def actor(case, name, codes, site=None):
    user = User.objects.create_user(username=name)
    role = OrganizationRole.objects.create(
        organization=case.organization, code=name, name="ناظر کارگاه"
    )
    role.permissions.add(*BusinessPermission.objects.filter(code__in=codes))
    membership = OrganizationMembership.objects.create(
        organization=case.organization, user=user, role_definition=role, status="active"
    )
    MembershipScopeGrant.objects.create(
        organization=case.organization,
        membership=membership,
        scope_type=AuthorizationScopeType.SITE
        if site
        else AuthorizationScopeType.ORGANIZATION,
        project=site.project if site else None,
        site=site,
    )
    return user


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ConformanceTests(TestCase):
    def setUp(self):
        fixture(self)
        self.client.force_login(self.owner)

    def test_list_query_state_is_allowlisted_and_scoped(self):
        for route in (
            "workforce:field_list",
            "workforce:assignment_list",
            "workforce:work_team_list",
        ):
            response = self.client.get(
                reverse(route),
                {
                    "q": "آزمایشی",
                    "sort": "__invalid",
                    "direction": "desc",
                    "page_filters": "1",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "erp-list-workspace")
            bar = response.context["filter_bar"]
            self.assertTrue(bar["chips"])
            self.assertNotIn("page=", bar["chips"][0]["url"])
            self.assertContains(response, "مرتب‌سازی")
        foreign = User.objects.create_user(username="conformance-foreign")
        org = create_organization_with_owner(
            owner=foreign, name="شرکت دیگر", slug="conformance-other"
        )
        project, _, _, _, _ = make_field_fixture(foreign, org)
        self.assertEqual(
            self.client.get(
                reverse("workforce:field_list"), {"project": project.pk}
            ).status_code,
            404,
        )

    def test_error_translation_keeps_business_explanation_without_internals(self):
        self.assertEqual(
            presentation_error(ValidationError("بازه زمانی همپوشانی دارد.")),
            "بازه زمانی همپوشانی دارد.",
        )
        self.assertNotIn(
            "Employee", presentation_error(ValueError("Employee object (raw-key)"))
        )

    def test_worker_and_assignment_forms_retain_values(self):
        response = self.client.post(
            reverse("workforce:field_create"),
            {
                "first_name": "نام حفظ‌شده",
                "last_name": "آزمون",
                "employee_number": "KEEP",
                "national_id": "invalid",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نام حفظ‌شده")
        self.assertContains(response, "erp-form-section")
        response = self.client.post(
            reverse("workforce:assignment_create"),
            {
                "employee": self.employee.pk,
                "project": self.project.pk,
                "site": self.site.pk,
                "role_title": "مسئولیت حفظ‌شده",
                "start_date": "invalid",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مسئولیت حفظ‌شده")
        self.assertEqual(response.context["form"]["site"].value(), str(self.site.pk))

    def test_state_actions_respect_independent_actor_and_scope(self):
        record = time.capture_attendance(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.project,
            site=self.site,
            calendar=self.calendar,
            work_date=date(2026, 10, 3),
            check_in_at=datetime(2026, 10, 3, 8, tzinfo=UTC),
            check_out_at=datetime(2026, 10, 3, 16, tzinfo=UTC),
        )
        request = SimpleNamespace(user=self.owner, organization=self.organization)
        self.assertEqual(record_actions(request, record, "attendance"), {})
        reviewer = actor(
            self, "conformance-reviewer", ["attendance.view", "attendance.review"]
        )
        request.user = reviewer
        self.assertEqual(
            record_actions(request, record, "attendance")["label"], "قطعی‌سازی حضور"
        )
        wrong_site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="WRONG",
            name="کارگاه دیگر",
            created_by=self.owner,
        )
        restricted = actor(
            self,
            "conformance-scoped",
            ["attendance.view", "attendance.review"],
            site=wrong_site,
        )
        request.user = restricted
        self.assertEqual(record_actions(request, record, "attendance"), {})
        self.client.force_login(restricted)
        self.assertEqual(
            self.client.get(
                reverse("timekeeping:record_detail", args=["attendance", record.pk])
            ).status_code,
            404,
        )

    def test_project_and_shared_implementation_preserved(self):
        baseline = json.loads(
            Path(EVIDENCE, "baseline.json").read_text(encoding="utf-8")
        )
        mismatches = [
            name
            for name, digest in baseline["protected"].items()
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest
        ]
        self.assertEqual(mismatches, [])

    def test_finalized_worker_and_timesheet_actions_match_services(self):
        Employee.objects.filter(pk=self.employee.pk).update(
            status="terminated", termination_date=date(2026, 11, 1)
        )
        response = self.client.get(
            reverse("workforce:field_detail", args=[self.employee.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "ویرایش اطلاعات")
        self.assertNotContains(response, 'name="target_status"')
        sheet = time.create_timesheet(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            period_start=date(2026, 10, 3),
            period_end=date(2026, 10, 3),
            declared_minutes=60,
        )
        time.add_timesheet_entry(
            organization=self.organization,
            actor=self.owner,
            timesheet=sheet,
            work_date=date(2026, 10, 3),
            project=self.project,
            site=self.site,
            minutes=60,
        )
        path = reverse("timekeeping:timesheet_detail", args=[sheet.pk])
        response = self.client.get(path)
        self.assertTrue(response.context["can_submit"])
        time.submit_timesheet(
            organization=self.organization, actor=self.owner, timesheet=sheet
        )
        response = self.client.get(path)
        self.assertFalse(response.context["can_prepare"])
        self.assertFalse(response.context["can_review"])
        self.assertNotContains(response, "data-timesheet-entry")
        reviewer = actor(
            self,
            "frozen-reviewer",
            ["attendance.view", "timesheets.view", "timesheets.review"],
        )
        self.client.force_login(reviewer)
        self.assertTrue(self.client.get(path).context["can_review"])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ConformanceBrowserTests(StaticLiveServerTestCase):
    _fixture_teardown = browser.FieldWorkforceBrowserTests._fixture_teardown

    def _probe(self, actor, scenarios, **kwargs):
        selected = os.environ.get("MVP02_BROWSER_ONLY")
        if selected and not any(
            row["name"] in selected.split(",") for row in scenarios
        ):
            return
        browser.FieldWorkforceBrowserTests._probe(self, actor, scenarios, **kwargs)

    def test_frozen_details_and_policy_aware_review(self):
        fixture(self)
        reviewer = actor(
            self,
            "frozen-reviewer",
            [
                "attendance.view",
                "timesheets.view",
                "timesheets.review",
                "overtime.view",
                "overtime.review",
            ],
        )
        sheet = time.create_timesheet(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            period_start=date(2026, 10, 3),
            period_end=date(2026, 10, 3),
            declared_minutes=60,
        )
        time.add_timesheet_entry(
            organization=self.organization,
            actor=self.owner,
            timesheet=sheet,
            work_date=date(2026, 10, 3),
            project=self.project,
            site=self.site,
            minutes=60,
        )
        time.submit_timesheet(
            organization=self.organization, actor=self.owner, timesheet=sheet
        )
        time.review_timesheet(
            organization=self.organization,
            actor=reviewer,
            timesheet=sheet,
            approve=True,
            reason="بررسی مستقل نمونه",
        )
        start = datetime(2026, 10, 5, 16, tzinfo=UTC)
        overtime = time.create_overtime_request(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.project,
            site=self.site,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            reason="عملیات نمونه",
        )
        time.submit_time_request(
            organization=self.organization, actor=self.owner, request=overtime
        )
        # Retained-history fixture; no production state or transition is changed.
        Employee.objects.filter(pk=self.employee.pk).update(
            status="terminated", termination_date=date(2026, 11, 1)
        )
        owner_rows, reviewer_rows = [], []
        for width in (1440, 1024, 390):
            common = {
                "status": 200,
                "width": width,
                "mobile": width == 390,
                "noJsErrors": True,
                "noHttpErrors": True,
                "screenshot": True,
            }
            owner_rows += [
                {
                    **common,
                    "name": f"frozen-worker-{width}",
                    "path": reverse("workforce:field_detail", args=[self.employee.pk]),
                    "absentText": ["ویرایش اطلاعات"],
                    "steps": [
                        {
                            "inspect": "!document.querySelector('main [name=target_status]')",
                            "description": "finalized worker status control",
                        }
                    ],
                },
                {
                    **common,
                    "name": f"approved-timesheet-{width}",
                    "path": reverse("timekeeping:timesheet_detail", args=[sheet.pk]),
                    "steps": [
                        {
                            "inspect": "!document.querySelector('[data-timesheet-entry]') && !document.querySelector('main form[action*=\"/submit/\"]') && !document.querySelector('main form[action*=\"/review/\"]')",
                            "description": "approved history editable",
                        }
                    ],
                },
            ]
            reviewer_rows.append(
                {
                    **common,
                    "name": f"missing-policy-review-{width}",
                    "path": reverse(
                        "timekeeping:record_detail", args=["overtime", overtime.pk]
                    ),
                    "mustText": ["تأیید به مرجع سیاست مصوب نیاز دارد."],
                    "steps": [
                        {
                            "inspect": "!document.querySelector('main button[value=approve]') && !!document.querySelector('main button[value=reject]')",
                            "description": "unavailable approval exposed",
                        }
                    ],
                }
            )
        self._probe(
            self.owner, owner_rows, evidence_directory=f"{EVIDENCE}/browser/frozen"
        )
        self._probe(
            reviewer,
            reviewer_rows,
            evidence_directory=f"{EVIDENCE}/browser/policy-review",
        )

    def test_principal_surface_and_journeys(self):
        fixture(self)
        reviewer = actor(
            self,
            "conformance-reviewer",
            [
                "attendance.view",
                "attendance.review",
                "attendance.correct",
                "overtime.view",
                "overtime.review",
                "leave_mission.view",
                "leave_mission.review",
                "timesheets.view",
                "timesheets.review",
            ],
        )
        correction_actor = actor(
            self, "conformance-corrector", ["attendance.view", "attendance.correct"]
        )
        self.context = FieldContext(
            project=self.project, site=self.site, employee=self.employee
        )
        scoped = "?" + self.context.query
        # Synthetic pagination fixtures contain no personal data or domain inference.
        Employee.objects.bulk_create(
            [
                Employee(
                    organization=self.organization,
                    employee_number=f"CREW-{i:02d}",
                    first_name="نیروی نمونه",
                    last_name=f"اجرایی {i:02d}",
                    created_by=self.owner,
                )
                for i in range(27)
            ]
        )
        WorkTeam.objects.bulk_create(
            [
                WorkTeam(
                    organization=self.organization,
                    code=f"CREW-{i:02d}",
                    name=f"گروه اجرایی {i:02d}",
                    created_by=self.owner,
                )
                for i in range(27)
            ]
        )
        record = time.capture_attendance(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.project,
            site=self.site,
            calendar=self.calendar,
            work_date=date(2026, 10, 3),
            check_in_at=datetime(2026, 10, 3, 8, tzinfo=UTC),
            check_out_at=datetime(2026, 10, 3, 16, tzinfo=UTC),
        )
        finalized = time.capture_attendance(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.project,
            site=self.site,
            calendar=self.calendar,
            work_date=date(2026, 10, 4),
            check_in_at=datetime(2026, 10, 4, 8, tzinfo=UTC),
            check_out_at=datetime(2026, 10, 4, 16, tzinfo=UTC),
        )
        time.finalize_attendance(
            organization=self.organization, actor=reviewer, attendance=finalized
        )
        finalized.refresh_from_db()
        correction = time.request_attendance_correction(
            organization=self.organization,
            requester=correction_actor,
            attendance=finalized,
            reason="اصلاح نمونه",
            reversal=True,
        )
        start = datetime(2026, 10, 5, 16, tzinfo=UTC)
        overtime = time.create_overtime_request(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.project,
            site=self.site,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            reason="تکمیل بتن‌ریزی",
        )
        mission = time.create_leave_mission_request(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.project,
            site=self.site,
            kind="mission",
            category_code="SITE",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            reason="بازدید کارگاه",
        )
        sheet = time.create_timesheet(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            period_start=date(2026, 10, 3),
            period_end=date(2026, 10, 3),
            declared_minutes=60,
        )
        time.add_timesheet_entry(
            organization=self.organization,
            actor=self.owner,
            timesheet=sheet,
            work_date=date(2026, 10, 3),
            project=self.project,
            site=self.site,
            minutes=60,
        )
        routes = [
            ("workers", reverse("workforce:field_list") + "?page_filters=1"),
            ("worker-create", reverse("workforce:field_create")),
            ("worker-edit", reverse("workforce:field_edit", args=[self.employee.pk])),
            (
                "worker-detail",
                reverse("workforce:field_detail", args=[self.employee.pk]) + scoped,
            ),
            (
                "worker-assign",
                reverse("workforce:field_assign", args=[self.employee.pk]) + scoped,
            ),
            ("assignments", reverse("workforce:assignment_list")),
            ("assignment-create", reverse("workforce:assignment_create") + scoped),
            ("teams", reverse("workforce:work_team_list")),
            ("team-create", reverse("workforce:work_team_create")),
            ("workbench", reverse("timekeeping:workbench") + scoped),
            ("attendance", reverse("timekeeping:attendance_create") + scoped),
            (
                "correction",
                reverse("timekeeping:attendance_correction_create", args=[finalized.pk])
                + scoped,
            ),
            ("leave-mission", reverse("timekeeping:leave_mission_create") + scoped),
            ("overtime", reverse("timekeeping:overtime_create") + scoped),
            ("timesheet-create", reverse("timekeeping:timesheet_create") + scoped),
            (
                "timesheet-detail",
                reverse("timekeeping:timesheet_detail", args=[sheet.pk]) + scoped,
            ),
            ("calendar", reverse("timekeeping:calendar_create")),
            ("holiday", reverse("timekeeping:holiday_create")),
            ("shift", reverse("timekeeping:shift_create")),
            ("shift-break", reverse("timekeeping:shift_break_create")),
            (
                "attendance-detail",
                reverse("timekeeping:record_detail", args=["attendance", record.pk]),
            ),
            (
                "finalized-detail",
                reverse("timekeeping:record_detail", args=["attendance", finalized.pk]),
            ),
            (
                "correction-detail",
                reverse(
                    "timekeeping:record_detail", args=["correction", correction.pk]
                ),
            ),
            (
                "mission-detail",
                reverse("timekeeping:record_detail", args=["leave", mission.pk]),
            ),
            (
                "overtime-detail",
                reverse("timekeeping:record_detail", args=["overtime", overtime.pk]),
            ),
        ]
        presentation_check = r"""(() => {
          const main=document.querySelector('main');
          return !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}|object\s*\(|BusinessPermission|ValidationError|EmployeeProjectAssignment/.test(main.innerText)
            && ![...main.querySelectorAll('a.erp-btn--primary')].some(a=>{const r=a.getBoundingClientRect();return r.left<0 || r.right>innerWidth});
        })()"""
        scenarios = []
        for width in (1440, 1024, 390):
            for name, path in routes:
                scenarios.append(
                    {
                        "name": f"{name}-{width}",
                        "path": path,
                        "status": 200,
                        "width": width,
                        "mobile": width == 390,
                        "noJsErrors": True,
                        "noHttpErrors": True,
                        "steps": [
                            {
                                "inspect": presentation_check,
                                "description": "visible leakage or clipped header CTA",
                            }
                        ],
                        "screenshot": True,
                        "bottomScreenshot": "detail" in name or "create" in name,
                    }
                )
        # Controls render the same domain actions; no scenario invents a transition.
        # Run each viewport as a bounded batch through the existing Chrome probe.
        for width in (1440, 1024, 390):
            self._probe(
                self.owner,
                [row for row in scenarios if row["width"] == width],
                evidence_directory=f"{EVIDENCE}/browser/{width}",
            )
        journeys = [
            {
                "name": "navigation-to-worker",
                "path": "/",
                "status": 200,
                "steps": [
                    {
                        "clickHref": reverse("workforce:field_list"),
                        "afterPath": reverse("workforce:field_list"),
                        "mustText": "نیروهای کار",
                    },
                    {
                        "clickSelector": "main .erp-list-title a",
                        "afterPrefix": "/workforce/field/",
                        "mustText": "مشخصات همکاری",
                    },
                ],
                "screenshot": True,
            },
            {
                "name": "filters-sort-pagination-back-refresh",
                "path": reverse("workforce:field_list") + "?page_filters=1",
                "status": 200,
                "steps": [
                    {
                        "clickSelector": "main .erp-list-pages a[rel=next]",
                        "afterPath": reverse("workforce:field_list"),
                    },
                    {
                        "inspect": "new URL(location.href).searchParams.get('page')==='2'",
                        "description": "pagination URL",
                    },
                    {"history": "back"},
                    {"reload": True},
                    {
                        "fill": {"q": "آزمایشی"},
                        "submit": True,
                        "formSelector": "#list-filter-bar",
                        "afterPath": reverse("workforce:field_list"),
                    },
                    {
                        "inspect": "document.querySelector('.erp-list-filter-summary')?.innerText.includes('آزمایشی') && document.querySelector('#list-filter-bar [name=q]').value==='آزمایشی'",
                        "description": "active search chip",
                    },
                    {
                        "clickSelector": "main th a",
                        "afterPath": reverse("workforce:field_list"),
                    },
                    {
                        "inspect": "new URL(location.href).searchParams.has('sort') && document.querySelector('#list-filter-bar [name=q]').value==='آزمایشی'",
                        "description": "sorting preserves search",
                    },
                ],
                "screenshot": True,
            },
            {
                "name": "worker-validation-retention",
                "path": reverse("workforce:field_create"),
                "status": 200,
                "steps": [
                    {
                        "fill": {
                            "employee_number": "KEEP",
                            "first_name": "نام حفظ‌شده",
                            "last_name": "ورودی",
                            "national_id": "invalid",
                        },
                        "submit": True,
                        "afterPath": reverse("workforce:field_create"),
                        "mustText": "ثبت انجام نشد",
                    },
                    {
                        "inspect": "document.querySelector('[name=first_name]').value==='نام حفظ‌شده'",
                        "description": "worker value lost",
                    },
                ],
                "screenshot": True,
            },
        ]
        journeys += [
            {
                "name": "scoped-attendance-entry",
                "path": reverse("timekeeping:attendance_create") + scoped,
                "status": 200,
                "steps": [
                    {
                        "searchChoice": {
                            "name": "employee",
                            "query": "FIELD-001",
                            "value": str(self.employee.pk),
                        }
                    },
                    {
                        "fill": {
                            "calendar": str(self.calendar.pk),
                            "work_date": "1405/07/28",
                            "check_in_at": "1405/07/28 08:00",
                            "check_out_at": "1405/07/28 16:00",
                        },
                        "submit": True,
                        "afterPath": "/timekeeping/",
                        "mustText": "حضور برای بررسی ثبت شد.",
                    },
                ],
                "screenshot": True,
            },
            {
                "name": "scoped-overtime-entry",
                "path": reverse("timekeeping:overtime_create") + scoped,
                "status": 200,
                "steps": [
                    {
                        "fill": {
                            "starts_at": "1405/07/28 16:00",
                            "ends_at": "1405/07/28 18:00",
                            "reason": "تکمیل عملیات کارگاه",
                        },
                        "submit": True,
                        "afterPath": "/timekeeping/",
                        "mustText": "پیش‌نویس اضافه‌کاری ثبت شد.",
                    }
                ],
                "screenshot": True,
            },
            {
                "name": "scoped-timesheet-and-allocation",
                "path": reverse("timekeeping:timesheet_create") + scoped,
                "status": 200,
                "steps": [
                    {
                        "fill": {
                            "period_start": "1405/07/28",
                            "period_end": "1405/07/28",
                            "declared_minutes": "480",
                        },
                        "submit": True,
                        "afterPrefix": "/timekeeping/timesheets/",
                        "mustText": "جزئیات کارکرد",
                    },
                    {
                        "fill": {"work_date": "1405/07/28", "minutes": "480"},
                        "formSelector": "main form[data-timesheet-entry]",
                        "submit": True,
                        "afterPrefix": "/timekeeping/timesheets/",
                        "mustText": "ردیف تخصیص زمان ثبت شد.",
                    },
                ],
                "screenshot": True,
            },
        ]
        for width in (1440, 1024, 390):
            menus = []
            for route in (
                "workforce:field_list",
                "workforce:assignment_list",
                "workforce:work_team_list",
            ):
                menus.append(
                    {
                        "name": route.split(":")[1] + f"-menu-{width}",
                        "preserveScrollScreenshot": True,
                        "viewportScreenshot": True,
                        "path": reverse(route) + "?page_filters=1",
                        "status": 200,
                        "width": width,
                        "mobile": width == 390,
                        "steps": [
                            {
                                "toggleSelector": "main .erp-list-row-menu summary",
                                "inspect": "(() => {const el=document.querySelector('main .erp-list-row-menu[open] .erp-list-row-menu__items');const r=el.getBoundingClientRect();return r.width>0 && r.left>=0 && r.right<=innerWidth && r.top>=0;})()",
                                "description": "row menu clipped",
                            }
                        ],
                        "screenshot": True,
                        "noJsErrors": True,
                        "noHttpErrors": True,
                    }
                )
            self._probe(
                self.owner,
                menus,
                evidence_directory=f"{EVIDENCE}/browser/menus-{width}",
            )
        self._probe(
            self.owner, journeys, evidence_directory=f"{EVIDENCE}/browser/journeys"
        )
        # Independent reviewer can finalize; own recorder cannot. Test actual UI.
        self._probe(
            reviewer,
            [
                {
                    "name": "independent-attendance-action",
                    "path": reverse(
                        "timekeeping:record_detail", args=["attendance", record.pk]
                    ),
                    "status": 200,
                    "mustText": ["قطعی‌سازی حضور"],
                    "screenshot": True,
                }
            ],
            evidence_directory=f"{EVIDENCE}/browser/reviewer",
        )
        denied = actor(self, "conformance-denied", [])
        self._probe(
            denied,
            [
                {
                    "name": "unauthorized",
                    "path": reverse("workforce:field_list"),
                    "status": 403,
                }
            ],
            evidence_directory=f"{EVIDENCE}/browser/denied",
        )
        foreign = User.objects.create_user(username="conformance-foreign")
        create_organization_with_owner(
            owner=foreign, name="شرکت مستقل", slug="conformance-foreign"
        )
        self._probe(
            foreign,
            [
                {
                    "name": "foreign-worker",
                    "path": reverse("workforce:field_detail", args=[self.employee.pk]),
                    "status": 404,
                },
                {
                    "name": "foreign-context",
                    "path": reverse("timekeeping:workbench") + scoped,
                    "status": 404,
                },
            ],
            evidence_directory=f"{EVIDENCE}/browser/foreign",
        )
        other_project = Project.objects.create(
            organization=self.organization,
            code="OTHER",
            name="پروژه دیگر",
            created_by=self.owner,
        )
        other_site = ProjectSite.objects.create(
            organization=self.organization,
            project=other_project,
            code="OTHER",
            name="کارگاه دیگر",
            created_by=self.owner,
        )
        self._probe(
            self.owner,
            [
                {
                    "name": "mismatched-context",
                    "path": reverse("workforce:field_list")
                    + f"?project={self.project.pk}&site={other_site.pk}",
                    "status": 404,
                }
            ],
            evidence_directory=f"{EVIDENCE}/browser/scope",
        )
