"""Planned assignment dates stay independent of actual termination and identity."""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.organizations.authorization import get_active_membership
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Project
from apps.workforce.field_forms import FieldAssignmentForm
from apps.workforce.field_selectors import FieldContext
from apps.workforce.forms import EmployeeAssignmentForm
from apps.workforce.models import EmployeeProjectAssignment
from apps.workforce.services import (
    assign_employee_to_project,
    transition_project_assignment_status,
)
from apps.workforce.test_mvp02 import make_field_fixture


class AssignmentPlannedEndTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="planned-end-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="شرکت برنامه تخصیص", slug="planned-end"
        )
        self.project, self.site, _team, self.employee, _report = make_field_fixture(
            self.owner, self.organization
        )
        self.target = Project.objects.create(
            organization=self.organization,
            code="PLAN",
            name="پروژه برنامه",
            created_by=self.owner,
        )
        self.client.force_login(self.owner)

    def forms(self, data=None):
        values = {
            "employee": str(self.employee.pk),
            "project": str(self.target.pk),
            **(data or {}),
        }
        return (
            EmployeeAssignmentForm(
                values,
                organization=self.organization,
                membership=get_active_membership(
                    user=self.owner, organization=self.organization
                ),
            ),
            FieldAssignmentForm(
                values,
                organization=self.organization,
                user=self.owner,
                context=FieldContext(),
            ),
        )

    def test_both_forms_keep_responsibility_optional_and_validate_dates(self):
        for form in self.forms({"start_date": "1405/07/09"}):
            with self.subTest(form=type(form).__name__):
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data["role_title"], "")
                self.assertIsNone(form.cleaned_data["planned_end_date"])
                self.assertTrue(form.fields["start_date"].required)
                self.assertFalse(form.fields["role_title"].required)
                self.assertFalse(form.fields["planned_end_date"].required)
                self.assertEqual(
                    form.fields["role_title"].label, "مسئولیت در این پروژه/کارگاه"
                )
                self.assertEqual(form.fields["role_title"].widget.input_type, "text")
        for planned in ("1405/07/09", "1405/07/10"):
            for form in self.forms(
                {"start_date": "1405/07/09", "planned_end_date": planned}
            ):
                self.assertTrue(form.is_valid(), form.errors)
        for form in self.forms(
            {"start_date": "1405/07/09", "planned_end_date": "1405/07/08"}
        ):
            self.assertFalse(form.is_valid())
            self.assertIn("planned_end_date", form.errors)
        for form in self.forms({"planned_end_date": "1405/07/10"}):
            self.assertFalse(form.is_valid())
            self.assertIn("start_date", form.errors)

    def test_past_planned_end_stays_active_and_actual_end_is_independent(self):
        assignment = assign_employee_to_project(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            project=self.target,
            start_date=date(2026, 10, 1),
            planned_end_date=date(2026, 10, 2),
            role_title="مسئول بتن‌ریزی",
        )
        self.assertEqual(assignment.status, "active")
        self.assertIsNone(assignment.end_date)
        self.assertEqual(assignment.planned_end_date, date(2026, 10, 2))
        assignment = transition_project_assignment_status(
            organization=self.organization,
            actor=self.owner,
            assignment=assignment,
            target_status="completed",
            end_date=date(2026, 10, 5),
        )
        self.assertEqual(assignment.status, "completed")
        self.assertEqual(assignment.end_date, date(2026, 10, 5))
        self.assertEqual(assignment.planned_end_date, date(2026, 10, 2))
        self.assertEqual(assignment.role_title, "مسئول بتن‌ریزی")

    def test_model_service_and_database_reject_planned_end_before_start(self):
        count = EmployeeProjectAssignment.objects.count()
        with self.assertRaises(ValueError):
            assign_employee_to_project(
                organization=self.organization,
                actor=self.owner,
                employee=self.employee,
                project=self.target,
                start_date=date(2026, 10, 2),
                planned_end_date=date(2026, 10, 1),
            )
        self.assertEqual(EmployeeProjectAssignment.objects.count(), count)
        assignment = EmployeeProjectAssignment.objects.get(
            employee=self.employee, project=self.project
        )
        assignment.planned_end_date = date(2026, 9, 30)
        with self.assertRaises(ValidationError) as error:
            assignment.full_clean()
        self.assertIn("planned_end_date", error.exception.message_dict)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmployeeProjectAssignment.objects.filter(pk=assignment.pk).update(
                planned_end_date=date(2026, 9, 30)
            )
        assignment.refresh_from_db()
        self.assertIsNone(assignment.planned_end_date)
        assignment.end_date = date(2026, 10, 3)
        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_both_post_entry_points_persist_plan_without_changing_position(self):
        original_position = self.employee.position_id
        for contextual in (False, True):
            project = (
                self.target
                if not contextual
                else Project.objects.create(
                    organization=self.organization,
                    code="CONTEXT-PLAN",
                    name="برنامه کارگاه",
                    created_by=self.owner,
                )
            )
            url = (
                reverse("workforce:field_assign", args=[self.employee.pk])
                if contextual
                else reverse("workforce:assignment_create")
            )
            data = {
                "employee": str(self.employee.pk),
                "project": str(project.pk),
                "role_title": "مسئولیت این تخصیص",
                "start_date": "1405/07/09",
                "planned_end_date": "1405/07/08",
            }
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 200)
            self.assertIn("planned_end_date", response.context["form"].errors)
            self.assertFalse(
                EmployeeProjectAssignment.objects.filter(
                    employee=self.employee, project=project
                ).exists()
            )
            response = self.client.post(url, {**data, "planned_end_date": "1405/07/10"})
            self.assertEqual(response.status_code, 302)
            saved = EmployeeProjectAssignment.objects.get(
                employee=self.employee, project=project
            )
            self.assertEqual(saved.planned_end_date, date(2026, 10, 2))
            self.assertEqual(saved.status, "active")
            self.assertIsNone(saved.end_date)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.position_id, original_position)
