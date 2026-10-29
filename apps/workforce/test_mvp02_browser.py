"""Real Chrome A–H verification against an isolated PostgreSQL live server."""

import json
import os
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
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
from apps.timekeeping.models import AttendanceRecord, OvertimeRequest, Timesheet
from apps.timekeeping.services import create_work_calendar
from apps.workforce.field_selectors import FieldContext
from apps.workforce.models import Employee
from apps.workforce.test_mvp02 import make_field_fixture
from core.product_surface import url_exposed


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class FieldWorkforceBrowserTests(StaticLiveServerTestCase):
    def test_assignment_planned_end_visual_followup(self):
        from apps.projects.models import Project, ProjectSite
        from apps.workforce.models import EmployeeProjectAssignment

        owner = User.objects.create_user(username="mvp02-planned-owner")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت برنامه تخصیص", slug="mvp02-planned"
        )
        global_project, global_site, _team, employee, _report = make_field_fixture(owner, organization)
        scenarios, projects = [], []
        contract = """(() => {
            const form=document.querySelector('main form[method=post]');
            const role=form.querySelector('[name=role_title]');
            const planned=form.querySelector('[name=planned_end_date]');
            const start=form.querySelector('[name=start_date]');
            return role.type==='text' && !role.required && !planned.required && start.required
                && form.querySelector('label[for=id_role_title]').textContent.includes('مسئولیت در این پروژه/کارگاه')
                && form.querySelector('label[for=id_planned_end_date]').textContent.includes('تاریخ پایان برنامه‌ریزی‌شده')
                && planned.getAttribute('aria-describedby').includes('id_planned_end_date-help')
                && !form.querySelector('[name=end_date],[name=status]');
        })()"""
        for mobile in (False, True):
            for contextual in (False, True):
                suffix = ("worker-" if contextual else "create-") + ("mobile" if mobile else "desktop")
                project = Project.objects.create(
                    organization=organization, code="PLAN-" + suffix.upper(),
                    name="پروژه برنامه " + suffix, created_by=owner,
                )
                site = ProjectSite.objects.create(
                    organization=organization, project=project, code="SITE",
                    name="کارگاه برنامه", created_by=owner,
                )
                projects.append(project)
                path = (reverse("workforce:field_assign", args=[employee.pk])
                        if contextual else reverse("workforce:assignment_create"))
                url = path + "?" + FieldContext(
                    project=global_project if contextual else project,
                    site=global_site if contextual else site,
                ).query
                selection = [
                    {"searchChoice": {"name": "project", "query": suffix, "value": str(project.pk)}, "expectCleared": ["site"]},
                    {"searchChoice": {"name": "site", "query": "برنامه", "value": str(site.pk)}},
                ] if contextual else [
                    {"searchChoice": {"name": "employee", "query": "FIELD-001", "value": str(employee.pk)}},
                ]
                scenarios += [
                    {"name": "PLAN-form-" + suffix, "path": url, "status": 200, "mobile": mobile,
                     "steps": [{"inspect": contract, "description": "planned/actual distinction and optional responsibility"}], "screenshot": True},
                    {"name": "PLAN-invalid-" + suffix, "path": url, "status": 200, "mobile": mobile,
                     "steps": selection + [
                         {"fill": {"start_date": "1405/07/09", "planned_end_date": "1405/07/08", "role_title": "مسئولیت همین تخصیص"},
                          "submit": True, "afterPath": path, "mustText": "نمی‌تواند پیش از تاریخ شروع باشد"},
                         {"inspect": contract + " && document.querySelector('[name=planned_end_date]').value==='1405/07/08' && document.querySelector('[name=role_title]').value==='مسئولیت همین تخصیص'", "description": "date error or value retention"},
                     ], "screenshot": True},
                    {"name": "PLAN-save-" + suffix, "path": url, "status": 200, "mobile": mobile,
                     "steps": selection + [
                         {"fill": {"start_date": "1405/07/09", "planned_end_date": "1405/07/10", "role_title": "مسئولیت همین تخصیص"},
                          "submit": True,
                          "afterPath": reverse("workforce:field_detail", args=[employee.pk]) if contextual else reverse("workforce:assignment_list"),
                          "mustText": "تخصیص نیروی کار ثبت شد" if contextual else "کارمند به پروژه تخصیص یافت"},
                     ], "screenshot": True},
                ]
        self._probe(owner, scenarios, evidence_directory="output/mvp-02/uiux/planned-end/browser",
                    global_context=(organization, global_project, global_site))
        for project in projects:
            assignment = EmployeeProjectAssignment.objects.get(employee=employee, project=project)
            self.assertEqual(assignment.planned_end_date, date(2026, 10, 2))
            self.assertEqual(assignment.status, "active")
            self.assertIsNone(assignment.end_date)
            self.assertEqual(assignment.role_title, "مسئولیت همین تخصیص")

    def test_work_team_registration_visual_followup(self):
        from apps.workforce.field_services import save_field_employee
        from apps.workforce.models import Department, WorkTeam

        owner = User.objects.create_user(username="mvp02-team-form-owner")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت آزمون گروه کاری", slug="mvp02-team-form"
        )
        project, site, _team, _employee, _report = make_field_fixture(owner, organization)
        Department.objects.bulk_create([
            Department(organization=organization, code=f"DEP-{i}", name=f"واحد {i:02d}")
            for i in range(45)
        ])
        department = Department.objects.create(
            organization=organization, code="DEP-TARGET", name="واحد نهایی اجرا"
        )
        lead = save_field_employee(
            organization=organization, actor=owner, employee_number="LEAD-READY",
            first_name="سرپرست", last_name="آماده", start_date=date(2026, 10, 1),
        )
        path = reverse("workforce:work_team_create")
        listing = reverse("workforce:work_team_list")
        labels = json.dumps(
            ["خانه", "عملیات پروژه و کارگاه", "نیروهای کار", "گروه‌های کاری", "ثبت گروه کاری"],
            ensure_ascii=False, separators=(",", ":"),
        )
        contract = """(() => {
            const form=document.querySelector('main [data-work-team-form]');
            const nav=document.querySelector('main nav[aria-label="مسیر صفحه"]');
            const items=[...nav.querySelectorAll('a,span')];
            const header=document.querySelector('main [aria-labelledby=erp-page-title]');
            return JSON.stringify(items.map(i=>i.textContent.trim()))===""" + json.dumps(labels) + """
              && items.slice(0,-1).every(i=>i.tagName==='A') && items.at(-1).tagName==='SPAN'
              && items.at(-1).getAttribute('aria-current')==='page'
              && header.innerText.includes('گروه کاری در سطح شرکت')
              && !form.querySelector('[name=project],[name=site]')
              && !document.querySelector('main [aria-label="محدوده عملیات"]')
              && document.querySelector('[data-context-project]').value===""" + json.dumps(str(project.pk)) + """
              && document.querySelector('[data-context-site]').value===""" + json.dumps(str(site.pk)) + """
              && form.querySelector('[name=code]').required
              && !form.querySelector('[name=code]').readOnly
              && form.querySelector('button[type=submit]').textContent.trim()==='ثبت'
              && form.querySelector('a.erp-btn--secondary').getAttribute('href')===""" + json.dumps(listing) + """;
        })()"""
        selection = [
            {"searchChoice": {"name": "department", "query": "نهایی", "value": str(department.pk)}},
            {"searchChoice": {"name": "lead", "query": "آماده", "value": str(lead.pk)}},
        ]
        retained = """(() => {
            return ['department','lead'].every(name=>{
                const field=document.querySelector('[name='+name+']');
                const item=field.tomselect.control.querySelector('.item');
                return field.value && item.querySelector('.business-choice-name')
                    && item.querySelector('.business-choice-code');
            });
        })()"""
        scenarios = []
        for mobile in (False, True):
            suffix = "mobile" if mobile else "desktop"
            scenarios += [
                {"name": "TEAMFORM-empty-" + suffix, "path": path, "status": 200, "mobile": mobile,
                 "absentText": ["منابع انسانی", "----------"], "steps": [
                     {"inspect": contract, "description": "team hierarchy or company scope"},
                     {"inspect": """['department','lead'].every((name,i)=>{
                        const f=document.querySelector('[name='+name+']');
                        return f.options[0].textContent===['انتخاب واحد سازمانی','انتخاب سرپرست گروه'][i]
                            && f.tomselect.control_input.placeholder===f.options[0].textContent;
                     })""", "description": "team selector placeholders"},
                 ], "screenshot": True},
                {"name": "TEAMFORM-validation-" + suffix, "path": path, "status": 200, "mobile": mobile,
                 "steps": selection + [
                     {"inspect": "document.querySelector('[data-work-team-form]').noValidate=true", "description": "enable server validation probe"},
                     {"submit": True, "afterPath": path, "mustText": "این فیلد لازم است"},
                     {"inspect": retained, "description": "team choices lost on validation error"},
                     {"inspect": contract, "description": "team scope changed on POST"},
                 ], "screenshot": True},
                {"name": "TEAMFORM-submit-" + suffix, "path": path, "status": 200, "mobile": mobile,
                 "steps": selection + [
                     {"fill": {"code": "VISUAL-" + suffix, "name": "گروه آزمون " + suffix, "description": "گروه در سطح شرکت"},
                      "submit": True, "afterPath": listing, "mustText": "گروه آزمون " + suffix},
                 ], "screenshot": True},
            ]
        self._probe(
            owner, scenarios, evidence_directory="output/mvp-02/uiux/work-team-form/browser",
            global_context=(organization, project, site),
        )
        for suffix in ("desktop", "mobile"):
            team = WorkTeam.objects.get(organization=organization, code="VISUAL-" + suffix.upper())
            self.assertEqual((team.department_id, team.lead_id), (department.pk, lead.pk))

    def test_assignment_form_visual_followup(self):
        from apps.projects.models import Project, ProjectSite

        owner = User.objects.create_user(username="mvp02-assignment-owner")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت آزمون تخصیص", slug="mvp02-assignment"
        )
        project, site, _team, employee, _report = make_field_fixture(owner, organization)
        second = Project.objects.create(
            organization=organization, code="PRJ-SECOND", name="پروژه ساختمان",
            created_by=owner,
        )
        second_site = ProjectSite.objects.create(
            organization=organization, project=second, code="SITE-WEST",
            name="کارگاه غربی", created_by=owner,
        )
        context = FieldContext(project=project, site=site)
        labels = json.dumps(
            ["خانه", "عملیات پروژه و کارگاه", "نیروهای کار",
             "تخصیص نیرو به پروژه و کارگاه", "تخصیص جدید"],
            ensure_ascii=False, separators=(",", ":"),
        )
        hierarchy = """(() => {
            const n=document.querySelector('main nav[aria-label="مسیر صفحه"]');
            const items=[...n.querySelectorAll('a,span')];
            return JSON.stringify(items.map(i=>i.textContent.trim()))===""" + json.dumps(labels) + """
              && items.slice(0,-1).every(i=>i.tagName==='A')
              && items.at(-1).tagName==='SPAN' && items.at(-1).getAttribute('aria-current')==='page';
        })()"""
        secondary = """(() => {
            return ['project','site','employee'].filter(name=>document.querySelector('select[name='+name+']')).every(name=>{
              const t=document.querySelector('select[name='+name+']').tomselect;
              const item=t.control.querySelector('.item');
              const primary=item.querySelector('.business-choice-name');
              const code=item.querySelector('.business-choice-code');
              return primary && code && parseFloat(getComputedStyle(primary).fontSize)>parseFloat(getComputedStyle(code).fontSize)
                && primary.getBoundingClientRect().top<code.getBoundingClientRect().top;
            });
        })()"""
        scenarios = []
        for mobile in (False, True):
            for contextual in (False, True):
                path = (
                    reverse("workforce:field_assign", args=[employee.pk])
                    if contextual else reverse("workforce:assignment_create")
                )
                scenarios.append({
                    "name": ("ASSIGN-worker-" if contextual else "ASSIGN-create-")
                    + ("mobile" if mobile else "desktop"),
                    "path": path + "?" + context.query,
                    "status": 200, "mobile": mobile,
                    "steps": [
                        *([] if contextual else [{"searchChoice": {"name": "employee", "query": "FIELD-001", "value": str(employee.pk)}}]),
                        {"inspect": hierarchy, "description": "assignment create hierarchy"},
                        {"inspect": secondary, "description": "business name prominence"},
                        {"searchChoice": {"name": "project", "query": "ساختمان", "value": str(second.pk)}, "expectCleared": ["site"]},
                        {"searchChoice": {"name": "site", "query": "غربی", "value": str(second_site.pk)}},
                        {"inspect": """(() => {
                            const t=document.querySelector('select[name=site]').tomselect;
                            return Object.keys(t.options).every(v=>!v || v===""" + json.dumps(str(second_site.pk)) + """)
                              && document.querySelector('[name=role_title]').tagName==='INPUT';
                        })()""", "description": "site scope or responsibility changed"},
                        {"inspect": secondary, "description": "remote business label hierarchy"},
                    ], "screenshot": True,
                })
        self._probe(owner, scenarios, evidence_directory="output/mvp-02/uiux/assignment-flow/browser")

    def _fixture_teardown(self):
        from django.core.management import call_command
        from django.db import connections

        # Retired Payments tables intentionally survive their state-only migration.
        # Include their FK dependents in this isolated test database's normal flush.
        for alias in self._databases_names(include_mirrors=False):
            self.assertTrue(
                connections[alias].settings_dict["NAME"].startswith("test_")
            )
            call_command(
                "flush",
                verbosity=0,
                interactive=False,
                database=alias,
                reset_sequences=False,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )

    def _probe(
        self,
        actor,
        scenarios,
        evidence_directory="output/mvp-02/uiux/browser",
        global_context=None,
    ):
        evidence_directory = os.environ.get(
            "MVP02_BROWSER_EVIDENCE_DIRECTORY", evidence_directory
        )
        selected = os.environ.get("MVP02_BROWSER_ONLY")
        if selected:
            scenarios = [row for row in scenarios if row["name"] in selected.split(",")]
        root = Path(__file__).resolve().parents[2]
        self.client.force_login(actor)
        if global_context:
            from apps.organizations.context import set_effective_context
            from apps.organizations.services import set_active_organization

            organization, project, site = global_context
            session = self.client.session
            set_active_organization(session, organization)
            set_effective_context(
                user=actor,
                organization=organization,
                session=session,
                project_id=str(project.pk),
                site_id=str(site.pk),
            )
            session.save()
        env = os.environ.copy()
        env["MVP02_SESSION"] = self.client.cookies["sessionid"].value
        env["MVP02_SCENARIOS"] = json.dumps(scenarios)
        result = subprocess.run(
            [
                "node",
                str(root / "scripts/verification/mvp02_browser.mjs"),
                self.live_server_url,
                str(root / evidence_directory),
                actor.username,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=420,
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stderr or "")[-4000:])
        results = json.loads(result.stdout)
        self.assertEqual(len(results), len(scenarios))
        for row in results:
            for link in row["links"]:
                if link.startswith("/"):
                    self.assertTrue(url_exposed(link), f"{row['name']} exposes {link}")
        if global_context:
            self.assertEqual(self.client.session["active_project_id"], str(project.pk))
            self.assertEqual(self.client.session["active_site_id"], str(site.pk))
            self.assertEqual(
                self.client.session["active_organization_id"], str(organization.pk)
            )

    def test_scenarios_a_through_h(self):
        owner = User.objects.create_user(username="mvp02-browser-owner")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت نمونه کارگاهی بنیرا", slug="mvp02-browser"
        )
        project, site, team, employee, report = make_field_fixture(owner, organization)
        calendar = create_work_calendar(
            organization=organization,
            actor=owner,
            code="FIELD",
            name="تقویم کارگاه آزمایشی",
            effective_from=date(2026, 1, 1),
            working_weekdays=[1, 2, 3, 4, 5],
        )
        context = FieldContext(project=project, site=site)
        worker_context = FieldContext(project=project, site=site, employee=employee)
        field_list = reverse("workforce:field_list") + "?" + context.query
        history = reverse("timekeeping:workbench") + "?" + context.query
        worker = (
            reverse("workforce:field_detail", args=[employee.pk]) + "?" + context.query
        )
        site_list = reverse("projects:site_list", args=[project.pk])
        site_detail = reverse("projects:site_detail", args=[project.pk, site.pk])
        hidden = [
            "/workforce/ess/",
            "/workforce/foundation/",
            "/workforce/departments/",
            "/payroll/",
            "/timekeeping/attendance/import/",
        ]
        self._probe(
            owner,
            [
                {
                    "name": "A-create-non-login-worker",
                    "path": reverse("workforce:field_create"),
                    "status": 200,
                    "steps": [
                        {
                            "searchChoice": {
                                "name": "work_team",
                                "query": "آرماتوربندی",
                                "value": str(team.pk),
                            }
                        },
                        {
                            "fill": {
                                "employee_number": "FIELD-BROWSER-NEW",
                                "first_name": "نیروی",
                                "last_name": "جدید آزمایشی",
                                "national_id": "0013543679",
                                "start_date": "1405/07/28",
                            },
                            "submit": True,
                            "afterPrefix": "/workforce/field/",
                            "mustText": "اطلاعات نیروی کار ثبت شد.",
                        },
                    ],
                    "mustText": ["0013543679", team.name],
                    "screenshot": True,
                },
                {
                    "name": "A-worker-without-login",
                    "path": worker,
                    "status": 200,
                    "mustText": ["1234567891", team.name, "آرماتوربند"],
                    "absentLinks": hidden,
                    "screenshot": True,
                },
                {
                    "name": "B-project-site-workers",
                    "path": reverse("projects:detail", args=[project.pk]),
                    "status": 200,
                    "steps": [
                        {"clickHref": site_list, "afterPath": site_list},
                        {"clickHref": site_detail, "afterPath": site_detail},
                        {
                            "clickHref": field_list,
                            "afterPath": reverse("workforce:field_list"),
                        },
                    ],
                    "mustText": [site.name, employee.last_name],
                    "screenshot": True,
                },
                {
                    "name": "C-report-timekeeping",
                    "path": reverse("daily_reports:detail", args=[report.pk]),
                    "status": 200,
                    "steps": [
                        {
                            "clickHref": history,
                            "afterPath": reverse("timekeeping:workbench"),
                        }
                    ],
                    "mustText": [site.name],
                    "absentLinks": hidden,
                },
                {
                    "name": "D-attendance",
                    "path": reverse("timekeeping:attendance_create")
                    + "?"
                    + worker_context.query,
                    "status": 200,
                    "steps": [
                        {
                            "fill": {
                                "calendar": str(calendar.pk),
                                "work_date": "1405/07/28",
                                "check_in_at": "1405/07/28 08:00",
                                "check_out_at": "1405/07/28 16:00",
                            },
                            "submit": True,
                            "afterPath": "/timekeeping/",
                            "mustText": "حضور برای بررسی ثبت شد.",
                        }
                    ],
                    "mustText": [employee.last_name, "پیش‌نویس"],
                    "screenshot": True,
                },
                {
                    "name": "D-overtime",
                    "path": reverse("timekeeping:overtime_create")
                    + "?"
                    + worker_context.query,
                    "status": 200,
                    "steps": [
                        {
                            "fill": {
                                "starts_at": "1405/07/28 16:00",
                                "ends_at": "1405/07/28 18:00",
                                "reason": "تکمیل آرماتوربندی آزمایشی",
                            },
                            "submit": True,
                            "afterPath": "/timekeeping/",
                            "mustText": "پیش‌نویس اضافه‌کاری ثبت شد.",
                        }
                    ],
                    "mustText": ["اضافه‌کاری", "پیش‌نویس"],
                },
                {
                    "name": "D-timesheet",
                    "path": reverse("timekeeping:timesheet_create")
                    + "?"
                    + worker_context.query,
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
                            "submit": True,
                            "formSelector": "main form.grid",
                            "afterPrefix": "/timekeeping/timesheets/",
                            "mustText": "ردیف تخصیص زمان ثبت شد.",
                        },
                    ],
                    "mustText": [project.name, site.name, "480"],
                    "screenshot": True,
                },
                {
                    "name": "G-surface-home",
                    "path": "/",
                    "status": 200,
                    "mustLinks": ["/workforce/field/"],
                    "absentLinks": hidden,
                },
                {"name": "G-hidden-ess", "path": "/workforce/ess/", "status": 403},
                {
                    "name": "G-hidden-hr",
                    "path": "/workforce/foundation/",
                    "status": 403,
                },
                {
                    "name": "H-list-mobile",
                    "path": field_list,
                    "status": 200,
                    "mobile": True,
                    "screenshot": True,
                },
                {
                    "name": "H-worker-mobile",
                    "path": worker,
                    "status": 200,
                    "mobile": True,
                    "screenshot": True,
                },
                {
                    "name": "H-form-mobile",
                    "path": reverse("workforce:field_edit", args=[employee.pk]),
                    "status": 200,
                    "mobile": True,
                    "screenshot": True,
                },
                {
                    "name": "H-history-mobile",
                    "path": history,
                    "status": 200,
                    "mobile": True,
                    "screenshot": True,
                },
            ],
        )
        self.assertIsNone(Employee.objects.get(pk=employee.pk).user_id)
        created = Employee.objects.get(
            organization=organization, employee_number="FIELD-BROWSER-NEW"
        )
        self.assertIsNone(created.user_id)
        self.assertEqual(
            created.work_relationships.get().person.national_id, "0013543679"
        )
        self.assertEqual(
            AttendanceRecord.objects.filter(organization=organization).count(), 1
        )
        self.assertEqual(
            OvertimeRequest.objects.filter(organization=organization).count(), 1
        )
        self.assertEqual(Timesheet.objects.filter(organization=organization).count(), 1)
        self.assertEqual(Timesheet.objects.get().entries.count(), 1)
        report.refresh_from_db()
        self.assertEqual(report.labor_count, 4)

        reader = User.objects.create_user(username="mvp02-browser-reader")
        role = OrganizationRole.objects.create(
            organization=organization,
            code="mvp02_browser_reader",
            name="خواننده آزمایشی",
        )
        role.permissions.add(BusinessPermission.objects.get(code="projects.view"))
        membership = OrganizationMembership.objects.create(
            organization=organization,
            user=reader,
            role_definition=role,
            status="active",
        )
        MembershipScopeGrant.objects.create(
            organization=organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
        )
        self._probe(
            reader,
            [
                {
                    "name": "E-no-workforce-authority",
                    "path": "/workforce/field/",
                    "status": 403,
                },
                {
                    "name": "E-no-timekeeping-authority",
                    "path": "/timekeeping/",
                    "status": 403,
                },
            ],
        )
        foreign = User.objects.create_user(username="mvp02-browser-foreign")
        create_organization_with_owner(
            owner=foreign, name="شرکت مستقل آزمایشی", slug="mvp02-browser-foreign"
        )
        self._probe(
            foreign,
            [
                {
                    "name": "F-foreign-worker",
                    "path": reverse("workforce:field_detail", args=[employee.pk]),
                    "status": 404,
                },
                {"name": "F-foreign-context", "path": history, "status": 404},
            ],
        )

    def test_uiux_remediation_desktop_mobile_and_cascades(self):
        from apps.projects.models import Project, ProjectSite
        from apps.workforce.field_services import save_field_employee
        from apps.workforce.models import WorkTeam
        from apps.workforce.services import assign_employee_to_project

        owner = User.objects.create_user(username="mvp02-uiux-owner")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت نمونه بنیرا", slug="mvp02-uiux"
        )
        project, site, team, employee, report = make_field_fixture(owner, organization)
        second = Project.objects.create(
            organization=organization,
            code="SECOND",
            name="پروژه ساختمان آزمایشی",
            created_by=owner,
        )
        second_site = ProjectSite.objects.create(
            organization=organization,
            project=second,
            code="WEST",
            name="کارگاه غربی",
            created_by=owner,
        )
        other = save_field_employee(
            organization=organization,
            actor=owner,
            employee_number="OTHER",
            first_name="نیروی",
            last_name="ساختمان",
            start_date=date(2026, 10, 1),
        )
        assign_employee_to_project(
            organization=organization,
            actor=owner,
            employee=other,
            project=second,
            site=second_site,
            start_date=date(2026, 10, 1),
        )
        WorkTeam.objects.bulk_create(
            [
                WorkTeam(
                    organization=organization,
                    code=f"REMOTE-{i}",
                    name=f"اکیپ بتن‌ریزی {i}",
                )
                for i in range(45)
            ]
        )
        from apps.workforce.field_forms import FieldEmployeeForm

        initial_ids = {
            row[0]
            for row in FieldEmployeeForm(organization=organization)
            .fields["work_team"]
            .widget.choices
        }
        remote = next(
            row
            for row in WorkTeam.objects.filter(organization=organization)
            if str(row.pk) not in initial_ids
        )
        calendar = create_work_calendar(
            organization=organization,
            actor=owner,
            code="UIUX",
            name="تقویم کارگاه",
            effective_from=date(2026, 1, 1),
            working_weekdays=[1, 2, 3, 4, 5],
        )
        record = AttendanceRecord.objects.create(
            organization=organization,
            employee=employee,
            project=project,
            site=site,
            calendar=calendar,
            work_date=date(2026, 10, 1),
            state="finalized",
            source="manual",
            captured_by=owner,
            check_in_at=datetime(2026, 10, 1, 5, tzinfo=UTC),
            check_out_at=datetime(2026, 10, 1, 13, tzinfo=UTC),
        )
        sheet = Timesheet.objects.create(
            organization=organization,
            employee=employee,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 1),
            declared_minutes=480,
            prepared_by=owner,
        )
        context = FieldContext(project=project, site=site, employee=employee)
        query = "?" + context.query
        pages = [
            ("worker-list", reverse("workforce:field_list")),
            ("worker-create", reverse("workforce:field_create")),
            ("worker-edit", reverse("workforce:field_edit", args=[employee.pk])),
            ("worker-detail", reverse("workforce:field_detail", args=[employee.pk])),
            ("assignment-list", reverse("workforce:assignment_list")),
            ("assignment-create", reverse("workforce:assignment_create")),
            (
                "worker-assignment",
                reverse("workforce:field_assign", args=[employee.pk]) + query,
            ),
            ("workbench", reverse("timekeeping:workbench") + query),
            ("attendance", reverse("timekeeping:attendance_create") + query),
            ("leave-mission", reverse("timekeeping:leave_mission_create") + query),
            ("overtime", reverse("timekeeping:overtime_create") + query),
            (
                "correction",
                reverse("timekeeping:attendance_correction_create", args=[record.pk])
                + query,
            ),
            ("timesheet", reverse("timekeeping:timesheet_create") + query),
            (
                "allocation",
                reverse("timekeeping:timesheet_detail", args=[sheet.pk]) + query,
            ),
            ("project", reverse("projects:detail", args=[project.pk])),
            ("site", reverse("projects:site_detail", args=[project.pk, site.pk])),
            ("daily-report", reverse("daily_reports:detail", args=[report.pk])),
        ]
        scenarios = []
        for mobile in (False, True):
            for label, path in pages:
                scenarios.append(
                    {
                        "name": "UX-" + label + ("-mobile" if mobile else "-desktop"),
                        "path": path,
                        "status": 200,
                        "mobile": mobile,
                        "screenshot": True,
                        "absentText": ["حداکثر ۴۰ گزینه"],
                    }
                )
        scenarios += [
            {
                "name": "UX-remote-keyboard",
                "path": reverse("workforce:field_create"),
                "status": 200,
                "steps": [
                    {
                        "searchChoice": {
                            "name": "work_team",
                            "query": remote.name,
                            "value": str(remote.pk),
                        },
                        "keyboard": True,
                    }
                ],
                "screenshot": True,
            },
            {
                "name": "UX-project-site-worker-cascade",
                "path": reverse("timekeeping:leave_mission_create") + query,
                "status": 200,
                "steps": [
                    {
                        "searchChoice": {
                            "name": "project",
                            "query": "ساختمان",
                            "value": str(second.pk),
                        },
                        "expectCleared": ["site", "employee"],
                    },
                    {
                        "searchChoice": {
                            "name": "site",
                            "query": "غربی",
                            "value": str(second_site.pk),
                        },
                        "expectCleared": ["employee"],
                    },
                    {
                        "searchChoice": {
                            "name": "employee",
                            "query": "ساختمان",
                            "value": str(other.pk),
                        }
                    },
                    {
                        "inspect": "!document.querySelector('[name=site]').tomselect.options["
                        + repr(str(site.pk))
                        + "] && !document.querySelector('[name=employee]').tomselect.options["
                        + repr(str(employee.pk))
                        + "]",
                        "description": "context contains unrelated options",
                    },
                ],
                "screenshot": True,
            },
            {
                "name": "UX-selected-validation-error",
                "path": reverse("workforce:field_create"),
                "status": 200,
                "steps": [
                    {
                        "searchChoice": {
                            "name": "work_team",
                            "query": remote.name,
                            "value": str(remote.pk),
                        }
                    },
                    {"submit": True, "afterPath": reverse("workforce:field_create")},
                    {
                        "inspect": "document.querySelector('[name=work_team]').value === "
                        + repr(str(remote.pk)),
                        "description": "selected canonical worker team lost after error",
                    },
                ],
                "screenshot": True,
            },
            {
                "name": "UX-no-javascript",
                "path": reverse("workforce:field_edit", args=[employee.pk]),
                "status": 200,
                "noJS": True,
                "steps": [
                    {
                        "fill": {"first_name": "نیروی", "last_name": "آزمایشی"},
                        "submit": True,
                        "afterPrefix": "/workforce/field/",
                    }
                ],
                "mustText": [team.name],
                "screenshot": True,
            },
        ]
        scenarios += [
            {
                "name": "UX-dropdown-desktop",
                "path": reverse("workforce:field_create"),
                "status": 200,
                "steps": [{"openChoice": "work_team"}],
                "screenshot": True,
            },
            {
                "name": "UX-dropdown-mobile",
                "path": reverse("workforce:field_create"),
                "status": 200,
                "mobile": True,
                "steps": [{"openChoice": "work_team"}],
                "screenshot": True,
            },
            {
                "name": "UX-native-complete-catalogue",
                "path": reverse("workforce:field_create") + "?native_choices=1",
                "status": 200,
                "noJS": True,
                "steps": [
                    {
                        "fill": {
                            "employee_number": "NATIVE-BROWSER",
                            "first_name": "نیروی",
                            "last_name": "بدون جاوااسکریپت",
                            "start_date": "1405/07/09",
                            "work_team": str(remote.pk),
                        },
                        "submit": True,
                        "afterPrefix": "/workforce/field/",
                    }
                ],
                "mustText": [remote.name],
                "screenshot": True,
            },
            {
                "name": "UX-htmx-lifecycle",
                "path": reverse("workforce:field_create"),
                "status": 200,
                "steps": [
                    {
                        "inspect": "(() => { const count=document.querySelectorAll('.ts-wrapper').length;document.dispatchEvent(new Event('htmx:afterSwap')); document.dispatchEvent(new Event('htmx:afterSwap')); if(document.querySelectorAll('.ts-wrapper').length!==count) return false;const root=document.querySelector('main form');document.dispatchEvent(new CustomEvent('htmx:beforeCleanupElement',{detail:{elt:root}})); if(root.querySelector('.ts-wrapper')) return false; document.dispatchEvent(new Event('htmx:afterSwap'));return document.querySelectorAll('.ts-wrapper').length===count;})()",
                        "description": "widget lifecycle duplicates controls or fails cleanup",
                    }
                ],
            },
        ]
        scenarios += [
            {
                "name": "UX-lookup-error",
                "path": reverse("workforce:field_create"),
                "status": 200,
                "steps": [
                    {"failedLookup": {"name": "work_team", "query": remote.name}}
                ],
                "screenshot": True,
            },
            {
                "name": "UX-lookup-retry",
                "path": reverse("workforce:field_create"),
                "status": 200,
                "steps": [
                    {
                        "failedLookup": {"name": "work_team", "query": remote.name},
                        "recover": True,
                    }
                ],
                "screenshot": True,
            },
            {
                "name": "UX-scroll-catalogue",
                "path": reverse("workforce:field_create"),
                "status": 200,
                "steps": [{"scrollChoices": "work_team"}],
                "screenshot": True,
            },
        ]
        scenarios += [
            {
                "name": "UX-clear-context-filter",
                "path": reverse("timekeeping:workbench") + query,
                "status": 200,
                "steps": [{"clearChoice": "project"}],
                "screenshot": True,
            },
            {
                "name": "UX-empty-lookup",
                "path": reverse("workforce:field_create"),
                "status": 200,
                "steps": [{"emptyLookup": "work_team"}],
                "screenshot": True,
            },
        ]
        scenarios += [
            {
                "name": "UX-filter-integrated-search",
                "path": reverse("timekeeping:workbench"),
                "status": 200,
                "steps": [
                    {
                        "searchChoice": {
                            "name": "project",
                            "query": "ساختمان",
                            "value": str(second.pk),
                        },
                        "typeOnly": True,
                    }
                ],
                "screenshot": True,
            }
        ]
        self._probe(owner, scenarios)

    def test_workforce_navigation_visual_followup(self):
        from apps.projects.models import Project, ProjectSite
        from apps.workforce.field_services import save_field_employee
        from apps.workforce.services import assign_employee_to_project

        owner = User.objects.create_user(username="mvp02-nav-owner")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت نمونه بنیرا", slug="mvp02-nav"
        )
        project, site, _team, employee, _report = make_field_fixture(
            owner, organization
        )
        candidate = save_field_employee(
            organization=organization,
            actor=owner,
            employee_number="READY",
            first_name="نیروی",
            last_name="آماده تخصیص",
            start_date=date(2026, 10, 1),
        )
        second = Project.objects.create(
            organization=organization,
            code="SECOND",
            name="پروژه ساختمان",
            created_by=owner,
        )
        second_site = ProjectSite.objects.create(
            organization=organization,
            project=second,
            code="WEST",
            name="کارگاه غربی",
            created_by=owner,
        )
        other = save_field_employee(
            organization=organization,
            actor=owner,
            employee_number="OTHER",
            first_name="نیروی",
            last_name="ساختمان",
            start_date=date(2026, 10, 1),
        )
        assign_employee_to_project(
            organization=organization,
            actor=owner,
            employee=other,
            project=second,
            site=second_site,
            start_date=date(2026, 10, 1),
        )
        workforce = reverse("workforce:field_list")
        assignments = reverse("workforce:assignment_list")
        create = reverse("workforce:assignment_create")
        teams = reverse("workforce:work_team_list")
        assignment_context = "?project=" + str(project.pk) + "&site=" + str(site.pk)
        navigation = (
            """(() => {
          const target='"""
            + assignments
            + """';
          const primary=[...document.querySelectorAll('aside a[href],.erp-mobile-nav a[href]')];
          const internal=document.querySelectorAll('main [data-workforce-navigation]');
          const h=document.querySelector('main [data-workforce-header] header[aria-labelledby=erp-page-title]');
          return !primary.some(a=>new URL(a.href).pathname===target) && primary.some(a=>a.textContent.trim()==='نیروهای کار' && a.classList.contains('is-active')) && internal.length===1 && internal[0].querySelectorAll('a').length===3 && internal[0].querySelectorAll('[aria-current=page]').length===1 && h?.nextElementSibling===internal[0] && [...internal[0].querySelectorAll('a')].every(a=>Math.abs(a.getBoundingClientRect().top-internal[0].firstElementChild.getBoundingClientRect().top)<1) && JSON.stringify([...internal[0].querySelectorAll('a')].map(a=>a.textContent.trim()))===JSON.stringify(['نیروها','تخصیص به پروژه و کارگاه','گروه‌های کاری']) && [...document.querySelectorAll('main a.erp-page-header__action')].every(a=>h.contains(a));
        })()"""
        )
        action = """(() => {
          const h=document.querySelector('h1').closest('header'),a=h.querySelector('a.erp-page-header__action'),copy=h.querySelector('.erp-page-header__copy');
          if(!a || !a.textContent.includes('تخصیص جدید')) return false;
          const r=a.getBoundingClientRect(),c=copy.getBoundingClientRect();
          return innerWidth<640 ? r.top>=c.bottom && r.top-c.bottom<=20 : c.left-r.right>=0 && c.left-r.right<=32;
        })()"""

        def breadcrumbs(assignment=False):
            labels = ["خانه", "عملیات پروژه و کارگاه", "نیروهای کار"]
            if assignment:
                labels.append("تخصیص نیرو به پروژه و کارگاه")
            return (
                """(() => {
              const n=document.querySelector('main nav[aria-label="مسیر صفحه"]');
              const items=[...n.querySelectorAll('a,span')];
              return JSON.stringify(items.map(i=>i.textContent.trim()))==="""
                + json.dumps(
                    json.dumps(labels, ensure_ascii=False, separators=(",", ":")),
                    ensure_ascii=False,
                )
                + """ && items[0].getAttribute('href')==='/' && items[1].getAttribute('href')==='/#home-operations' && items.at(-1).tagName==='SPAN' && items.at(-1).getAttribute('aria-current')==='page' && n.querySelectorAll('[aria-current=page]').length===1 && !document.querySelector('header[aria-labelledby=erp-page-title]').innerText.includes('عملیات پروژه و کارگاه')"""
                + (
                    " && items[2].getAttribute('href')===" + json.dumps(workforce)
                    if assignment
                    else ""
                )
                + ";})()"
            )

        scenarios = []
        for mobile in (False, True):
            suffix = "mobile" if mobile else "desktop"
            scenarios += [
                {
                    "name": "NAV-workforce-" + suffix,
                    "path": workforce,
                    "status": 200,
                    "mobile": mobile,
                    "steps": [
                        {
                            "inspect": navigation,
                            "description": "primary/internal workforce hierarchy incorrect",
                        },
                        {
                            "inspect": breadcrumbs(),
                            "description": "Workforce breadcrumb hierarchy incorrect",
                        },
                    ],
                    "mustText": ["بدون تخصیص فعال"],
                    "screenshot": True,
                },
                {
                    "name": "NAV-assignment-" + suffix,
                    "path": workforce,
                    "status": 200,
                    "mobile": mobile,
                    "steps": [
                        {"clickHref": assignments, "afterPath": assignments},
                        {
                            "inspect": navigation,
                            "description": "assignment duplicated in primary navigation",
                        },
                        {
                            "inspect": action,
                            "description": "assignment action detached from title",
                        },
                        {
                            "inspect": breadcrumbs(True),
                            "description": "Assignment breadcrumb hierarchy incorrect",
                        },
                    ],
                    "mustText": [
                        "تخصیص نیرو به پروژه و کارگاه",
                        "تاریخ شروع از",
                        "تاریخ شروع تا",
                    ],
                    "screenshot": True,
                },
                {
                    "name": "NAV-create-" + suffix,
                    "path": assignments + assignment_context,
                    "status": 200,
                    "mobile": mobile,
                    "steps": [
                        {"clickHref": create + assignment_context, "afterPath": create},
                        {
                            "inspect": "document.querySelector('main select[name=project]').value==="
                            + repr(str(project.pk))
                            + " && document.querySelector('main select[name=site]').value==="
                            + repr(str(site.pk)),
                            "description": "validated context lost when opening new assignment",
                        },
                        {
                            "searchChoice": {
                                "name": "employee",
                                "query": "READY",
                                "value": str(candidate.pk),
                            }
                        },
                        {
                            "searchChoice": {
                                "name": "project",
                                "query": "ساختمان",
                                "value": str(second.pk),
                            },
                            "expectCleared": ["site"],
                        },
                        {
                            "searchChoice": {
                                "name": "site",
                                "query": "غربی",
                                "value": str(second_site.pk),
                            }
                        },
                        {
                            "inspect": "document.querySelector('[name=role_title]').tagName==='INPUT'",
                            "description": "responsibility no longer descriptive text",
                        },
                        {
                            "inspect": navigation,
                            "description": "assignment form tab placement differs",
                        },
                    ],
                    "screenshot": True,
                },
                {
                    "name": "NAV-teams-" + suffix,
                    "path": workforce,
                    "status": 200,
                    "mobile": mobile,
                    "steps": [
                        {"clickHref": teams, "afterPath": teams},
                        {
                            "inspect": navigation,
                            "description": "team page has unrelated navigation",
                        },
                    ],
                    "screenshot": True,
                },
            ]
            for label, name, args in (
                ("worker-create", "field_create", []),
                ("worker-detail", "field_detail", [employee.pk]),
                ("worker-edit", "field_edit", [employee.pk]),
                ("worker-assign", "field_assign", [employee.pk]),
                ("team-create", "work_team_create", []),
            ):
                scenarios.append(
                    {
                        "name": "TABS-" + label + "-" + suffix,
                        "path": reverse("workforce:" + name, args=args)
                        + assignment_context,
                        "status": 200,
                        "mobile": mobile,
                        "steps": [
                            {
                                "inspect": navigation,
                                "description": "persistent Workforce tabs not immediately after header",
                            }
                        ],
                        "screenshot": True,
                    }
                )
            for label, path in (("workforce", workforce), ("assignments", assignments)):
                query = "?project=" + str(project.pk) + "&site=" + str(site.pk)
                scenarios.append(
                    {
                        "name": "NAV-cascade-" + label + "-" + suffix,
                        "path": path + query,
                        "status": 200,
                        "mobile": mobile,
                        "steps": [
                            {
                                "searchChoice": {
                                    "name": "project",
                                    "query": "ساختمان",
                                    "value": str(second.pk),
                                },
                                "filterChange": True,
                            },
                            {
                                "inspect": "(() => {const site=document.querySelector('main select[name=site]');return !site.value && [...site.options].filter(o=>o.value).every(o=>o.value==="
                                + repr(str(second_site.pk))
                                + ");})()",
                                "description": "Project change retained stale Site or unrelated options",
                            },
                        ],
                        "screenshot": True,
                    }
                )
        self._probe(
            owner, scenarios, evidence_directory="output/mvp-02/uiux/navigation/browser"
        )

    def test_global_context_and_work_team_filter_followup(self):
        from apps.projects.models import Project, ProjectSite
        from apps.workforce.models import WorkTeam

        owner = User.objects.create_user(username="mvp02-context-owner")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت نمونه بنیرا", slug="mvp02-context"
        )
        project, site, team, _employee, _report = make_field_fixture(
            owner, organization
        )
        second = Project.objects.create(
            organization=organization,
            code="SECOND",
            name="پروژه ساختمان",
            created_by=owner,
        )
        second_site = ProjectSite.objects.create(
            organization=organization,
            project=second,
            code="WEST",
            name="کارگاه غربی",
            created_by=owner,
        )
        filtered_team = WorkTeam.objects.create(
            organization=organization,
            code="FILTERED",
            name="گروه فیلتر",
            created_by=owner,
        )
        global_check = (
            "document.querySelector('[data-context-project]').value==="
            + json.dumps(str(project.pk))
            + " && document.querySelector('[data-context-site]').value==="
            + json.dumps(str(site.pk))
        )

        def local_check(project_id, site_id):
            return (
                global_check
                + " && document.querySelector('main select[name=project]').value==="
                + json.dumps(project_id)
                + " && document.querySelector('main select[name=site]').value==="
                + json.dumps(site_id)
            )

        teams = reverse("workforce:work_team_list")
        team_layout = """(() => {const f=document.querySelector('[data-workforce-team-filters]'), h=document.querySelector('[data-workforce-header] header'),n=document.querySelector('[data-workforce-navigation]');const b=[...document.querySelectorAll('main button')].filter(x=>x.textContent.trim()==='اعمال فیلتر');return !!f && b.length===1 && f.contains(b[0]) && f.querySelector('a').textContent.trim()==='پاک کردن' && h.querySelector('a.erp-page-header__action').textContent.includes('گروه جدید') && h.nextElementSibling===n && !document.querySelector('main').innerText.includes('منابع انسانی') && !document.querySelector('main [data-table-filter-controls]') && ['عملیات پروژه و کارگاه','نیروهای کار','گروه‌های کاری'].every(t=>document.querySelector('main nav[aria-label="مسیر صفحه"]').innerText.includes(t));})()"""
        scenarios = []
        for mobile in (False, True):
            suffix = "mobile" if mobile else "desktop"
            for label, route in (
                ("workers", "field_list"),
                ("assignments", "assignment_list"),
            ):
                path = reverse("workforce:" + route)
                scenarios += [
                    {
                        "name": "CTX-default-" + label + "-" + suffix,
                        "path": path,
                        "status": 200,
                        "mobile": mobile,
                        "steps": [
                            {
                                "inspect": local_check(str(project.pk), str(site.pk)),
                                "description": "global defaults not applied to page filters",
                            }
                        ],
                        "mustText": ["فیلترهای این صفحه"],
                        "screenshot": True,
                    },
                    {
                        "name": "CTX-cascade-" + label + "-" + suffix,
                        "path": path,
                        "status": 200,
                        "mobile": mobile,
                        "steps": [
                            {
                                "searchChoice": {
                                    "name": "project",
                                    "query": "ساختمان",
                                    "value": str(second.pk),
                                },
                                "filterChange": True,
                            },
                            {
                                "inspect": local_check(str(second.pk), "")
                                + " && [...document.querySelector('main select[name=site]').options].filter(o=>o.value).every(o=>o.value==="
                                + json.dumps(str(second_site.pk))
                                + ")",
                                "description": "page cascade changed global context or retained invalid Site",
                            },
                        ],
                        "screenshot": True,
                    },
                    {
                        "name": "CTX-clear-" + label + "-" + suffix,
                        "path": path,
                        "status": 200,
                        "mobile": mobile,
                        "steps": [
                            {"clickHref": path + "?page_filters=1", "afterPath": path},
                            {
                                "inspect": local_check("", ""),
                                "description": "clear silently restored defaults or changed global context",
                            },
                        ],
                        "screenshot": True,
                    },
                ]
            scenarios += [
                {
                    "name": "TEAM-layout-" + suffix,
                    "path": teams,
                    "status": 200,
                    "mobile": mobile,
                    "steps": [
                        {
                            "inspect": team_layout + " && " + global_check,
                            "description": "team header/filter layout incorrect",
                        }
                    ],
                    "screenshot": True,
                },
                {
                    "name": "TEAM-filter-" + suffix,
                    "path": teams,
                    "status": 200,
                    "mobile": mobile,
                    "steps": [
                        {
                            "fill": {"team": filtered_team.name},
                            "waitMs": 650,
                            "inspect": "!new URL(location.href).searchParams.has('team')",
                            "description": "explicit team filter submitted while typing",
                        },
                        {
                            "submit": True,
                            "formSelector": "#work-team-filters",
                            "afterPath": teams,
                        },
                        {
                            "inspect": global_check
                            + " && document.querySelector('main tbody').innerText.includes('گروه فیلتر') && !document.querySelector('main tbody').innerText.includes("
                            + json.dumps(team.code)
                            + ")",
                            "description": "team filter results or global context incorrect",
                        },
                    ],
                    "screenshot": True,
                },
                {
                    "name": "TEAM-clear-" + suffix,
                    "path": teams + "?team=FILTERED",
                    "status": 200,
                    "mobile": mobile,
                    "steps": [
                        {
                            "clickSelector": "[data-workforce-team-filters] a",
                            "afterPath": teams,
                        },
                        {
                            "inspect": global_check
                            + " && !new URL(location.href).searchParams.has('team') && document.querySelector('main tbody').innerText.includes("
                            + json.dumps(team.code)
                            + ")",
                            "description": "team clear failed or changed global context",
                        },
                    ],
                    "screenshot": True,
                },
                {
                    "name": "TEAM-create-" + suffix,
                    "path": reverse("workforce:work_team_create"),
                    "status": 200,
                    "mobile": mobile,
                    "absentText": ["منابع انسانی"],
                    "steps": [
                        {
                            "inspect": global_check,
                            "description": "team creation changed global context",
                        }
                    ],
                    "screenshot": True,
                },
            ]
        self._probe(
            owner,
            scenarios,
            evidence_directory="output/mvp-02/uiux/context-filters/browser",
            global_context=(organization, project, site),
        )
