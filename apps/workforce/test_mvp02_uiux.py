"""Canonical choices, context validation and progressive native form contracts."""

from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Project, ProjectSite
from apps.timekeeping.forms import LeaveMissionForm
from apps.workforce.field_forms import FieldAssignmentForm, FieldEmployeeForm
from apps.workforce.field_selectors import FieldContext
from apps.workforce.field_services import save_field_employee
from apps.workforce.models import WorkTeam
from apps.workforce.test_mvp02 import make_field_fixture


class Controls(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class MVP02SelectorTests(TestCase):
    def test_work_team_form_uses_company_scope_manual_code_and_hierarchy(self):
        from apps.workforce.forms import WorkTeamForm

        self.assertFalse({"project", "site"}.intersection(
            field.name for field in WorkTeam._meta.fields
        ))
        form = WorkTeamForm(organization=self.organization)
        self.assertTrue(form.fields["code"].required)
        self.assertFalse(WorkTeam._meta.get_field("code").has_default())
        for name, placeholder in (
            ("department", "انتخاب واحد سازمانی"),
            ("lead", "انتخاب سرپرست گروه"),
        ):
            self.assertEqual(form.fields[name].empty_label, placeholder)
            self.assertEqual(form.fields[name].widget.choices[0], ("", placeholder))
            self.assertEqual(form.fields[name].widget.attrs["data-placeholder"], placeholder)
        url = reverse("workforce:work_team_create")
        response = self.client.get(url, {"project": str(self.project.pk), "site": str(self.site.pk)})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        trail = html.split('aria-label="مسیر صفحه">', 1)[1].split("</nav>", 1)[0]
        labels = ["خانه", "عملیات پروژه و کارگاه", "نیروهای کار", "گروه‌های کاری", "ثبت گروه کاری"]
        self.assertEqual([trail.index(label) for label in labels], sorted(trail.index(label) for label in labels))
        self.assertIn(f'href="{reverse("workforce:work_team_list")}"', trail)
        self.assertIn('aria-current="page">ثبت گروه کاری</span>', trail)
        self.assertNotContains(response, "منابع انسانی")
        self.assertContains(response, "گروه کاری در سطح شرکت تعریف می‌شود")
        self.assertNotIn('aria-label="محدوده عملیات"', html)
        self.assert_persistent_workforce_tabs(response)
        with self.settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"):
            response = self.client.get(url)
            self.assertNotContains(response, "منابع انسانی")
            self.assertNotContains(response, "data-workforce-header")

    def test_work_team_choices_preserve_tenant_active_masters_and_submission(self):
        from apps.workforce.forms import WorkTeamForm
        from apps.workforce.models import Department

        department = Department.objects.create(organization=self.organization, code="OPS", name="اجرایی")
        inactive = Department.objects.create(organization=self.organization, code="OLD", name="قدیمی", is_active=False)
        foreign_owner = User.objects.create_user(username="foreign-team-form")
        foreign = create_organization_with_owner(owner=foreign_owner, name="شرکت دیگر", slug="foreign-team-form")
        foreign_department = Department.objects.create(organization=foreign, code="OTHER", name="واحد دیگر")
        foreign_employee = save_field_employee(
            organization=foreign, actor=foreign_owner, employee_number="OTHER",
            first_name="سرپرست", last_name="دیگر", start_date=date(2026, 10, 1),
        )
        data = {"code": "ui-team", "name": "گروه اجرایی", "department": str(department.pk), "lead": str(self.employee.pk)}
        for field, value in (("department", foreign_department.pk), ("department", inactive.pk), ("lead", foreign_employee.pk)):
            with self.subTest(field=field, value=value):
                form = WorkTeamForm({**data, field: str(value)}, organization=self.organization)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        for kind, selected in (("department", department), ("team_lead", self.employee)):
            endpoint = reverse("workforce:field_choices", args=[kind])
            response = self.client.get(endpoint, {"project": str(self.second.pk), "site": str(self.site.pk)})
            self.assertEqual(response.status_code, 200)
            results = response.json()["results"]
            self.assertIn(str(selected.pk), [row["value"] for row in results])
            self.assertNotIn(str(foreign_department.pk), [row["value"] for row in results])
            self.assertNotIn(str(foreign_employee.pk), [row["value"] for row in results])
            self.assertNotIn(str(inactive.pk), [row["value"] for row in results])
        url = reverse("workforce:work_team_create")
        before = WorkTeam.objects.count()
        self.assertEqual(self.client.post(url, {**data, "_refresh_choices": "1"}).status_code, 200)
        self.assertEqual(WorkTeam.objects.count(), before)
        self.assertEqual(self.client.post(url, {**data, "code": ""}).status_code, 200)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        team = WorkTeam.objects.get(organization=self.organization, code="UI-TEAM")
        self.assertEqual((team.department_id, team.lead_id), (department.pk, self.employee.pk))
        self.assertEqual(self.client.post(url, {"code": "OPTIONAL", "name": "گروه بدون ساختار"}).status_code, 302)

    def test_work_team_lookup_authority_and_full_catalogue(self):
        from apps.organizations.models import (
            BusinessPermission,
            MembershipScopeGrant,
            OrganizationMembership,
            OrganizationRole,
        )
        from apps.workforce.forms import WorkTeamForm
        from apps.workforce.models import Department

        Department.objects.bulk_create([
            Department(organization=self.organization, code=f"FORM-{i}", name=f"واحد {i:02d}")
            for i in range(65)
        ])
        form = WorkTeamForm(organization=self.organization)
        self.assertEqual(len(form.fields["department"].widget.choices), 41)
        endpoint = reverse("workforce:field_choices", args=["department"])
        first = self.client.get(endpoint).json()
        second = self.client.get(first["next"]).json()
        values = [r["value"] for r in first["results"] + second["results"]]
        self.assertEqual(len(values), len(set(values)))
        self.assertEqual(len(values), 65)
        native = self.client.get(reverse("workforce:work_team_create"), {"native_choices": "1"})
        self.assertEqual(len(list(native.context["form"].fields["department"].widget.choices)), 66)
        selected = Department.objects.get(organization=self.organization, code="FORM-64")
        form = WorkTeamForm({"department": str(selected.pk)}, organization=self.organization)
        self.assertFalse(form.is_valid())
        self.assertIn(str(selected.pk), [v for v, _label in form.fields["department"].widget.choices])
        creator = User.objects.create_user(username="team-only-creator")
        role = OrganizationRole.objects.create(organization=self.organization, code="team_only", name="ثبت گروه")
        role.permissions.add(BusinessPermission.objects.get(code="work_teams.create"))
        membership = OrganizationMembership.objects.create(organization=self.organization, user=creator, role_definition=role, status="active")
        MembershipScopeGrant.objects.create(organization=self.organization, membership=membership, scope_type="organization")
        self.client.force_login(creator)
        self.assertEqual(self.client.get(reverse("workforce:work_team_create")).status_code, 200)
        for kind in ("department", "team_lead"):
            self.assertEqual(self.client.get(reverse("workforce:field_choices", args=[kind])).status_code, 200)
        self.assertEqual(self.client.get(reverse("workforce:field_choices", args=["employee"])).status_code, 403)
        self.assertEqual(self.client.get(reverse("workforce:field_choices", args=["project"])).status_code, 403)
        MembershipScopeGrant.objects.filter(membership=membership).delete()
        MembershipScopeGrant.objects.create(
            organization=self.organization, membership=membership,
            scope_type="project", project=self.project,
        )
        self.assertEqual(self.client.get(reverse("workforce:work_team_create")).status_code, 403)
        for kind in ("department", "team_lead"):
            self.assertEqual(self.client.get(reverse("workforce:field_choices", args=[kind])).status_code, 403)
        MembershipScopeGrant.objects.filter(membership=membership).delete()
        MembershipScopeGrant.objects.create(
            organization=self.organization, membership=membership, scope_type="organization"
        )
        role.permissions.clear()
        for kind in ("department", "team_lead"):
            self.assertEqual(self.client.get(reverse("workforce:field_choices", args=[kind])).status_code, 403)

    def test_contextual_assignment_preserves_open_end_notes_and_end_action(self):
        from apps.workforce.models import EmployeeProjectAssignment

        url = reverse("workforce:field_assign", args=[self.employee.pk])
        data = {
            "project": str(self.second.pk), "site": str(self.second_site.pk),
            "role_title": "مسئول اجرای کارگاه", "notes": "یادداشت تخصیص",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("start_date", response.context["form"].errors)
        response = self.client.post(url, {**data, "start_date": "1405/07/09"})
        self.assertEqual(response.status_code, 302)
        assignment = EmployeeProjectAssignment.objects.get(
            employee=self.employee, project=self.second
        )
        self.assertEqual(assignment.status, "active")
        self.assertIsNone(assignment.end_date)
        self.assertEqual(assignment.notes, data["notes"])
        self.assertEqual(assignment.role_title, data["role_title"])
        response = self.client.post(
            reverse("workforce:assignment_status_change", args=[assignment.pk]),
            {"target_status": "completed", "end_date": "1405/07/10"},
        )
        self.assertEqual(response.status_code, 302)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, "completed")
        self.assertEqual(assignment.end_date, date(2026, 10, 2))

    def test_assignment_creation_hierarchy_names_and_field_order(self):
        from apps.organizations.authorization import get_active_membership
        from apps.workforce.forms import EmployeeAssignmentForm

        form = EmployeeAssignmentForm(
            organization=self.organization,
            membership=get_active_membership(
                user=self.owner, organization=self.organization
            ),
            initial={"project": self.project, "site": self.site},
        )
        self.assertEqual(
            list(form.fields),
            ["employee", "project", "site", "role_title", "start_date", "planned_end_date", "notes"],
        )
        for name in ("employee", "project", "site"):
            self.assertEqual(
                form.fields[name].widget.attrs["data-business-names-primary"], "true"
            )
        contextual = FieldAssignmentForm(
            organization=self.organization, user=self.owner,
            context=FieldContext(),
        )
        self.assertEqual(
            list(contextual.fields), ["project", "site", "role_title", "start_date", "planned_end_date", "notes"]
        )
        for url in (
            reverse("workforce:assignment_create"),
            reverse("workforce:field_assign", args=[self.employee.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                trail = html.split('aria-label="مسیر صفحه">', 1)[1].split("</nav>", 1)[0]
                labels = ["خانه", "عملیات پروژه و کارگاه", "نیروهای کار",
                          "تخصیص نیرو به پروژه و کارگاه", "تخصیص جدید"]
                indexes = [trail.index(label) for label in labels]
                self.assertEqual(indexes, sorted(indexes))
                self.assertIn(
                    f'href="{reverse("workforce:assignment_list")}"', trail
                )
                self.assertIn('aria-current="page">تخصیص جدید</span>', trail)
                header = html.split('aria-labelledby="erp-page-title">', 1)[1].split("</header>", 1)[0]
                self.assertNotIn("عملیات پروژه و کارگاه", header)

    def setUp(self):
        self.owner = User.objects.create_user(username="uiux-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="شرکت آزمون", slug="uiux-tests"
        )
        self.project, self.site, self.team, self.employee, _ = make_field_fixture(
            self.owner, self.organization
        )
        self.second = Project.objects.create(
            organization=self.organization,
            code="SECOND",
            name="پروژه دوم",
            created_by=self.owner,
        )
        self.second_site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.second,
            code="SECOND",
            name="کارگاه دوم",
            created_by=self.owner,
        )
        self.client.force_login(self.owner)

    def test_one_native_submission_control_and_no_separate_search_controls(self):
        pages = [
            reverse("workforce:field_create"),
            reverse("workforce:assignment_create"),
            reverse("timekeeping:leave_mission_create"),
            reverse("timekeeping:workbench"),
        ]
        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                controls = Controls(response.content.decode()).tags
                choices = [
                    a
                    for t, a in controls
                    if t == "select" and "data-business-choice" in a
                ]
                self.assertTrue(choices)
                self.assertEqual(len(choices), len({a["name"] for a in choices}))
                self.assertFalse(
                    any(
                        "data-choice-submit" in a or "data-choice-search" in a
                        for _, a in controls
                    )
                )
                self.assertFalse(
                    any(
                        t == "input" and a.get("name") in {v["name"] for v in choices}
                        for t, a in controls
                    )
                )
                self.assertContains(response, "tom-select.base.min.js")
                self.assertNotContains(response, "حداکثر ۴۰ گزینه")

    def test_project_limits_sites_and_rejects_stale_site_on_submit(self):
        form = FieldAssignmentForm(
            {
                "project": str(self.project.pk),
                "site": str(self.second_site.pk),
                "start_date": "1405/07/09",
            },
            organization=self.organization,
            user=self.owner,
            context=FieldContext(),
        )
        self.assertQuerySetEqual(form.fields["site"].queryset, [self.site])
        self.assertFalse(form.is_valid())
        self.assertIn("site", form.errors)
        empty = FieldAssignmentForm(
            organization=self.organization, user=self.owner, context=FieldContext()
        )
        self.assertFalse(empty.fields["site"].queryset.exists())

    def test_timekeeping_workers_are_limited_to_selected_context(self):
        unassigned = save_field_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="NEW",
            first_name="نیروی",
            last_name="تازه",
            start_date=date(2026, 10, 1),
        )
        form = LeaveMissionForm(
            {
                "project": str(self.project.pk),
                "site": str(self.site.pk),
                "employee": str(unassigned.pk),
            },
            organization=self.organization,
            user=self.owner,
        )
        self.assertQuerySetEqual(form.fields["employee"].queryset, [self.employee])
        self.assertFalse(form.is_valid())
        self.assertIn("employee", form.errors)

    def test_remote_sites_and_workers_fail_closed_for_foreign_context(self):
        foreign_owner = User.objects.create_user(username="foreign-uiux")
        foreign = create_organization_with_owner(
            owner=foreign_owner, name="شرکت دیگر", slug="foreign-uiux"
        )
        project = Project.objects.create(
            organization=foreign,
            code="FOREIGN",
            name="پروژه دیگر",
            created_by=foreign_owner,
        )
        for kind in ("site", "employee", "activity"):
            response = self.client.get(
                reverse("workforce:field_choices", args=[kind]),
                {"project": str(project.pk)},
            )
            self.assertEqual(response.status_code, 404)

    def test_remote_paging_has_no_missing_or_duplicate_choices(self):
        WorkTeam.objects.bulk_create(
            [
                WorkTeam(
                    organization=self.organization, code=f"PAGE-{i}", name=f"اکیپ {i}"
                )
                for i in range(65)
            ]
        )
        url = reverse("workforce:field_choices", args=["team"])
        first = self.client.get(url).json()
        self.assertEqual(len(first["results"]), 40)
        self.assertIsNotNone(first["next"])
        next_url = urlsplit(first["next"])
        second = self.client.get(next_url.path + "?" + next_url.query).json()
        self.assertIsNone(second["next"])
        values = [v["value"] for v in first["results"] + second["results"]]
        self.assertEqual(len(values), 66)
        self.assertEqual(len(values), len(set(values)))
        result = self.client.get(url, {"q": "اکیپ ۶۴"}).json()["results"]
        self.assertEqual(len(result), 1)
        self.assertIn("PAGE-64", result[0]["label"])

    def test_selected_record_after_initial_window_survives_validation_error(self):
        WorkTeam.objects.bulk_create(
            [
                WorkTeam(
                    organization=self.organization, code=f"SELECT-{i}", name=f"اکیپ {i}"
                )
                for i in range(45)
            ]
        )
        selected = WorkTeam.objects.order_by("pk").last()
        form = FieldEmployeeForm(
            {"work_team": str(selected.pk)}, organization=self.organization
        )
        self.assertFalse(form.is_valid())
        controls = Controls(str(form["work_team"])).tags
        self.assertTrue(
            any(
                t == "option" and a.get("value") == str(selected.pk) and "selected" in a
                for t, a in controls
            )
        )
        self.assertIn(selected.name, str(form["work_team"]))

    def test_assignment_creation_keeps_unassigned_workers_selectable(self):
        worker = save_field_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="UNASSIGNED",
            first_name="نیروی",
            last_name="جدید",
            start_date=date(2026, 10, 1),
        )
        response = self.client.get(
            reverse("workforce:field_choices", args=["employee"]),
            {
                "project": str(self.project.pk),
                "site": str(self.site.pk),
                "purpose": "assignment",
                "q": "UNASSIGNED",
            },
        )
        self.assertEqual(
            [v["value"] for v in response.json()["results"]], [str(worker.pk)]
        )

    def test_assignment_filters_use_canonical_ids_and_validate_relationships(self):
        url = reverse("workforce:assignment_list")
        response = self.client.get(
            url,
            {
                "project": str(self.project.pk),
                "site": str(self.site.pk),
                "employee": str(self.employee.pk),
            },
        )
        self.assertEqual(len(response.context["assignments"]), 1)
        response = self.client.get(
            url, {"project": str(self.project.pk), "site": str(self.second_site.pk)}
        )
        self.assertEqual(len(response.context["assignments"]), 0)
        self.assertIn("site", response.context["form"].errors)

    def test_native_fallback_includes_all_authorized_teams_and_refresh_does_not_write(
        self,
    ):
        WorkTeam.objects.bulk_create(
            [
                WorkTeam(
                    organization=self.organization,
                    code=f"NATIVE-{i}",
                    name=f"اکیپ ساده {i}",
                )
                for i in range(45)
            ]
        )
        url = reverse("workforce:field_create") + "?native_choices=1"
        response = self.client.get(url)
        controls = Controls(str(response.context["form"]["work_team"])).tags
        self.assertEqual(len([a for t, a in controls if t == "option"]), 47)
        response = self.client.post(
            url,
            {
                "employee_number": "NATIVE-NEW",
                "first_name": "نیرو",
                "last_name": "آزمون",
                "start_date": "1405/07/09",
                "_refresh_choices": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        from apps.workforce.models import Employee

        self.assertFalse(Employee.objects.filter(employee_number="NATIVE-NEW").exists())

    def test_inactive_existing_team_is_retained_without_exposing_other_inactive_teams(
        self,
    ):
        self.team.is_active = False
        self.team.save(update_fields=["is_active"])
        hidden = WorkTeam.objects.create(
            organization=self.organization,
            code="INACTIVE",
            name="اکیپ غیرفعال",
            is_active=False,
        )
        form = FieldEmployeeForm(
            organization=self.organization,
            employee=self.employee,
            initial={"work_team": self.team},
        )
        self.assertIn(self.team, form.fields["work_team"].queryset)
        self.assertNotIn(hidden, form.fields["work_team"].queryset)
        self.assertIn("غیرفعال", str(form["work_team"]))

    def test_assignment_history_only_permission_cannot_enumerate_unassigned_workers(
        self,
    ):
        from apps.organizations.models import (
            BusinessPermission,
            MembershipScopeGrant,
            OrganizationMembership,
            OrganizationRole,
        )

        worker = save_field_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="UNRELATED",
            first_name="نیروی",
            last_name="نامرتبط",
            start_date=date(2026, 10, 1),
        )
        viewer = User.objects.create_user(username="assignment-only-viewer")
        role = OrganizationRole.objects.create(
            organization=self.organization, code="assignment_only", name="سوابق تخصیص"
        )
        role.permissions.add(
            BusinessPermission.objects.get(code="project_assignments.view")
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=viewer,
            role_definition=role,
            status="active",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="organization",
        )
        self.client.force_login(viewer)
        url = reverse("workforce:field_choices", args=["employee"])
        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.get(url, {"purpose": "assignment_filter"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["value"] for row in response.json()["results"]],
            [str(self.employee.pk)],
        )
        form = self.client.get(reverse("workforce:assignment_list")).context["form"]
        self.assertNotIn(worker, form.fields["employee"].queryset)
        self.assertEqual(
            self.client.get(url, {"purpose": "assignment"}).status_code, 403
        )

    def test_workforce_internal_navigation_replaces_assignment_primary_entry(self):
        from core.product_surface import capability_exposed, route_exposed

        self.assertTrue(capability_exposed("field_workforce"))
        from core.product_surface import NAVIGATION_GROUPS

        master = next(
            link
            for group in NAVIGATION_GROUPS
            for link in group.links
            if link.route == "workforce:field_list"
        )
        self.assertTrue(master.is_active_for("workforce:assignment_list"))
        self.assertTrue(master.is_active_for("workforce:work_team_list"))
        self.assertFalse(master.is_active_for("timekeeping:workbench"))

        for name in ("assignment_list", "assignment_create", "field_assign"):
            self.assertTrue(route_exposed("workforce:" + name))
        paths = [
            reverse("workforce:field_list"),
            reverse("workforce:assignment_list"),
            reverse("workforce:work_team_list"),
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assert_persistent_workforce_tabs(response)
                routes = [
                    link.route
                    for group in response.context["product_navigation_groups"]
                    for link in group.links
                ]
                self.assertNotIn("workforce:assignment_list", routes)
                self.assertIn("workforce:field_list", routes)
                markup = WorkforceNavigationMarkup(response.content.decode())
                self.assertEqual(len(markup.internal_links), 3)
                self.assertEqual(
                    {href.split("?")[0] for href in markup.internal_links}, set(paths)
                )
                self.assertNotIn(
                    reverse("workforce:assignment_list"), markup.primary_links
                )
                self.assertContains(response, 'aria-current="page"')
                self.assertNotContains(response, "تخصیص نیروی پروژه")
                self.assertNotContains(response, "نیروی کار کارگاه")
                if path in paths[:2]:
                    html = response.content.decode()
                    breadcrumb = html.split('aria-label="مسیر صفحه">', 1)[1].split(
                        "</nav>", 1
                    )[0]
                    labels = ["خانه", "عملیات پروژه و کارگاه", "نیروهای کار"]
                    if path == paths[1]:
                        labels.append("تخصیص نیرو به پروژه و کارگاه")
                        self.assertInHTML(
                            '<a class="transition hover:text-blue-700" href="'
                            + paths[0]
                            + '">نیروهای کار</a>',
                            breadcrumb,
                        )
                    positions = [breadcrumb.index(label) for label in labels]
                    self.assertEqual(positions, sorted(positions))
                    self.assertIn('href="/#home-operations"', breadcrumb)
                    self.assertInHTML(
                        '<span class="text-slate-600" aria-current="page">'
                        + labels[-1]
                        + "</span>",
                        breadcrumb,
                    )
                    self.assertEqual(breadcrumb.count('aria-current="page"'), 1)
                    header = html.split('aria-labelledby="erp-page-title">', 1)[
                        1
                    ].split("</header>", 1)[0]
                    self.assertNotIn("عملیات پروژه و کارگاه", header)
        assignment = self.client.get(paths[1])
        self.assertEqual(
            assignment.context["form"].fields["start_date_from"].label, "تاریخ شروع از"
        )
        self.assertEqual(
            assignment.context["form"].fields["start_date_to"].label, "تاریخ شروع تا"
        )
        for name in (
            "field_create",
            "field_detail",
            "field_edit",
            "field_assign",
            "assignment_create",
            "work_team_create",
            "employee_list",
            "employee_create",
            "employee_detail",
        ):
            args = (
                [self.employee.pk]
                if name
                in {"field_detail", "field_edit", "field_assign", "employee_detail"}
                else []
            )
            with self.subTest(page=name):
                response = self.client.get(reverse("workforce:" + name, args=args))
                self.assertEqual(response.status_code, 200)
                self.assert_persistent_workforce_tabs(response)
        with self.settings(PRODUCT_SURFACE_PROFILE="FULL_ERP"):
            for name in ("work_team_list", "work_team_create"):
                response = self.client.get(reverse("workforce:" + name))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "data-workforce-header")

    def assert_persistent_workforce_tabs(self, response):
        html = response.content.decode()
        self.assertEqual(html.count("data-workforce-header"), 1)
        self.assertEqual(html.count("data-workforce-navigation"), 1)
        self.assertRegex(html, r"(?s)</header>\s*<nav[^>]*data-workforce-navigation")
        tabs = html.split("data-workforce-navigation>", 1)[1].split("</nav>", 1)[0]
        labels = ["نیروها", "تخصیص به پروژه و کارگاه", "گروه‌های کاری"]
        self.assertEqual(
            [tabs.index(label) for label in labels],
            sorted(tabs.index(label) for label in labels),
        )
        self.assertEqual(tabs.count('aria-current="page"'), 1)
        header = html.split('aria-labelledby="erp-page-title">', 1)[1].split(
            "</header>", 1
        )[0]

        def action_count(markup):
            return sum(
                tag == "a"
                and "erp-page-header__action" in attrs.get("class", "").split()
                for tag, attrs in Controls(markup).tags
            )

        self.assertEqual(
            action_count(html),
            action_count(header),
        )

    def test_internal_assignment_navigation_preserves_validated_project_site_context(
        self,
    ):
        response = self.client.get(
            reverse("workforce:field_list"),
            {"project": str(self.project.pk), "site": str(self.site.pk)},
        )
        markup = WorkforceNavigationMarkup(response.content.decode())
        from urllib.parse import parse_qs

        url = next(
            url
            for url in markup.internal_links
            if url.startswith(reverse("workforce:assignment_list"))
        )
        self.assertEqual(
            parse_qs(urlsplit(url).query),
            {"project": [str(self.project.pk)], "site": [str(self.site.pk)]},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assert_persistent_workforce_tabs(response)
        self.assertEqual(len(response.context["assignments"]), 1)
        create_url = reverse("workforce:assignment_create") + "?" + urlsplit(url).query
        self.assertContains(response, create_url.replace("&", "&amp;"))
        create = self.client.get(create_url)
        self.assertEqual(create.status_code, 200)
        self.assert_persistent_workforce_tabs(create)
        self.assertEqual(create.context["form"].initial["project"], self.project)
        self.assertEqual(create.context["form"].initial["site"], self.site)
        breadcrumb = (
            response.content.decode()
            .split('aria-label="مسیر صفحه">', 1)[1]
            .split("</nav>", 1)[0]
        )
        self.assertInHTML(
            '<a class="transition hover:text-blue-700" href="'
            + reverse("workforce:field_list")
            + "?"
            + urlsplit(url).query.replace("&", "&amp;")
            + '">نیروهای کار</a>',
            breadcrumb,
        )

    def test_assignment_responsibility_remains_descriptive_text_and_candidates_unassigned(
        self,
    ):
        from django import forms

        from apps.organizations.authorization import get_active_membership
        from apps.workforce.forms import EmployeeAssignmentForm
        from apps.workforce.models import EmployeeProjectAssignment

        field = EmployeeProjectAssignment._meta.get_field("role_title")
        self.assertIsNone(field.remote_field)
        self.assertEqual(field.get_internal_type(), "CharField")
        worker = save_field_employee(
            organization=self.organization,
            actor=self.owner,
            employee_number="AVAILABLE",
            first_name="نیروی",
            last_name="آماده",
            start_date=date(2026, 10, 1),
        )
        form = EmployeeAssignmentForm(
            organization=self.organization,
            membership=get_active_membership(
                user=self.owner, organization=self.organization
            ),
            initial={"project": self.project, "site": self.site},
        )
        self.assertIn(worker, form.fields["employee"].queryset)
        self.assertIsInstance(form.fields["role_title"].widget, forms.TextInput)
        self.assertQuerySetEqual(form.fields["site"].queryset, [self.site])
        response = self.client.get(reverse("workforce:field_list"))
        self.assertContains(response, "erp-badge erp-badge--neutral")
        self.assertContains(response, "بدون تخصیص فعال")

    def test_internal_navigation_and_direct_routes_preserve_permissions(self):
        from apps.organizations.models import (
            BusinessPermission,
            MembershipScopeGrant,
            OrganizationMembership,
            OrganizationRole,
        )

        reader = User.objects.create_user(username="workforce-only-nav-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="workforce_nav_reader",
            name="خواننده نیروها",
        )
        role.permissions.add(BusinessPermission.objects.get(code="employees.view"))
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=reader,
            role_definition=role,
            status="active",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="organization",
        )
        self.client.force_login(reader)
        response = self.client.get(reverse("workforce:field_list"))
        self.assertEqual(response.status_code, 200)
        links = WorkforceNavigationMarkup(response.content.decode()).internal_links
        self.assertEqual(links, [reverse("workforce:field_list")])
        self.assertEqual(
            self.client.get(reverse("workforce:assignment_list")).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("workforce:assignment_create")).status_code, 403
        )
        self.assertEqual(
            self.client.get(
                reverse("workforce:field_assign", args=[self.employee.pk])
            ).status_code,
            403,
        )
        role.permissions.set(
            [BusinessPermission.objects.get(code="project_assignments.view")]
        )
        response = self.client.get(reverse("workforce:assignment_list"))
        self.assertEqual(response.status_code, 200)
        breadcrumb = (
            response.content.decode()
            .split('aria-label="مسیر صفحه">', 1)[1]
            .split("</nav>", 1)[0]
        )
        self.assertInHTML("<span>نیروهای کار</span>", breadcrumb)
        self.assertNotIn('href="' + reverse("workforce:field_list") + '"', breadcrumb)
        self.assertNotIn('href="/#home-operations"', breadcrumb)

    def test_global_context_initializes_filters_without_becoming_page_state(self):
        from apps.organizations.context import set_effective_context
        from apps.organizations.services import set_active_organization

        session = self.client.session
        set_active_organization(session, self.organization)
        set_effective_context(
            user=self.owner,
            organization=self.organization,
            session=session,
            project_id=str(self.project.pk),
            site_id=str(self.site.pk),
        )
        session.save()
        for name in ("field_list", "assignment_list"):
            url = reverse("workforce:" + name)
            for query, expected_project, expected_site in (
                ({}, self.project, self.site),
                (
                    {"project": str(self.second.pk), "site": str(self.second_site.pk)},
                    self.second,
                    self.second_site,
                ),
                (
                    {"project": str(self.second.pk), "page_filters": "1"},
                    self.second,
                    None,
                ),
                ({"page_filters": "1"}, None, None),
                ({"project": "", "site": ""}, None, None),
            ):
                with self.subTest(page=name, query=query):
                    response = self.client.get(url, query)
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.context["form"].is_valid())
                    cleaned = response.context["form"].cleaned_data
                    self.assertEqual(cleaned.get("project"), expected_project)
                    self.assertEqual(cleaned.get("site"), expected_site)
                    self.assertEqual(
                        self.client.session["active_project_id"], str(self.project.pk)
                    )
                    self.assertEqual(
                        self.client.session["active_site_id"], str(self.site.pk)
                    )
                    self.assertEqual(
                        self.client.session["active_organization_id"],
                        str(self.organization.pk),
                    )
                    self.assertContains(response, "فیلترهای این صفحه")
                    self.assertNotContains(response, 'aria-label="محدوده عملیات"')
            invalid = self.client.get(
                url, {"project": self.second.pk, "site": self.site.pk}
            )
            if name == "field_list":
                self.assertEqual(invalid.status_code, 404)
            else:
                self.assertIn("site", invalid.context["form"].errors)
                self.assertFalse(invalid.context["assignments"])

    def test_work_team_filters_and_hierarchy_are_local_and_compact(self):
        url = reverse("workforce:work_team_list")
        for query in ({}, {"team": "no matching team"}):
            response = self.client.get(url, query)
            html = response.content.decode()
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "منابع انسانی")
            breadcrumb = html.split('aria-label="مسیر صفحه">', 1)[1].split("</nav>", 1)[
                0
            ]
            labels = ["خانه", "عملیات پروژه و کارگاه", "نیروهای کار", "گروه‌های کاری"]
            self.assertEqual(
                [breadcrumb.index(label) for label in labels],
                sorted(breadcrumb.index(label) for label in labels),
            )
            controls = html.split("data-workforce-team-filters>", 1)[1].split(
                "</form>", 1
            )[0]
            self.assertIn("اعمال فیلتر", controls)
            self.assertIn("پاک کردن", controls)
            self.assertEqual(html.count("اعمال فیلتر"), 1)
            self.assertNotIn('id="work-team-filters-row"', html)
            for name in ("team", "department", "lead"):
                self.assertIn('name="' + name + '"', controls)
            self.assert_persistent_workforce_tabs(response)
        self.assertNotContains(
            self.client.get(reverse("workforce:work_team_create")), "منابع انسانی"
        )


class WorkforceNavigationMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.sections = []
        self.internal_links = []
        self.primary_links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("aside", "nav"):
            self.sections.append((tag, attrs))
        if tag == "a":
            if any("data-workforce-navigation" in attrs for _, attrs in self.sections):
                self.internal_links.append(attrs.get("href"))
            if any(
                tag == "aside" or "erp-mobile-nav" in attrs.get("class", "")
                for tag, attrs in self.sections
            ):
                self.primary_links.append(attrs.get("href"))

    def handle_endtag(self, tag):
        if tag in ("aside", "nav") and self.sections:
            self.sections.pop()
