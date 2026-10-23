"""Independent F-128 selector, redisplay and unchanged write-authority controls."""

import re
from datetime import date, timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import Project, ProjectSite
from apps.workforce.forms import EmployeeTrainingRecordForm
from apps.workforce.models import Employee, EmployeeTrainingRecord
from apps.workforce.services import (
    create_training_requirement,
    record_employee_training,
)


class TrainingRequirementSelectorScopeTests(TestCase):
    @classmethod
    def member(cls, user, organization, role, organization_scope=False):
        member = OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=role,
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=organization,
            membership=member,
            role=OrganizationRole.objects.get(code=role),
            reason="Disposable F128 test",
        )
        if organization_scope:
            MembershipScopeGrant.objects.create(
                organization=organization,
                membership=member,
                scope_type="organization",
                reason="Disposable F128 organization control",
            )
        return member

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="F128 tenant", slug="f128")
        cls.other = Organization.objects.create(name="F128 foreign", slug="f128-x")
        for org in (cls.org, cls.other):
            OrganizationSettings.objects.create(organization=org, currency="IRR")
        cls.user = User.objects.create_user(username="f128-limited")
        cls.owner = User.objects.create_user(username="f128-owner")
        cls.foreign = User.objects.create_user(username="f128-foreign")
        cls.site_user = User.objects.create_user(username="f128-site")
        cls.viewer = User.objects.create_user(username="f128-viewer")
        cls.limited = cls.member(cls.user, cls.org, "project_manager")
        cls.owner_member = cls.member(cls.owner, cls.org, "company_owner", True)
        cls.foreign_member = cls.member(cls.foreign, cls.other, "company_owner", True)
        cls.site_member = cls.member(cls.site_user, cls.org, "operations_manager")
        cls.viewer_member = cls.member(cls.viewer, cls.org, "viewer", True)
        cls.projects = {}
        for key in "ABCDX":
            project = Project.objects.create(
                organization=cls.other if key == "X" else cls.org,
                code=f"F128-P-{key}",
                name=f"F128 Project {key}",
            )
            cls.projects[key] = project
            if key in "AB":
                MembershipScopeGrant.objects.create(
                    organization=cls.org,
                    membership=cls.limited,
                    scope_type="project",
                    project=project,
                    reason="Disposable F128 A/B",
                )
        site = ProjectSite.objects.create(
            organization=cls.org,
            project=cls.projects["A"],
            code="F128-SITE",
            name="F128 site",
        )
        MembershipScopeGrant.objects.create(
            organization=cls.org,
            membership=cls.site_member,
            scope_type="site",
            project=cls.projects["A"],
            site=site,
            reason="Disposable F128 site control",
        )
        cls.employee = Employee.objects.create(
            organization=cls.org,
            employee_number="F128-EMP",
            first_name="Synthetic",
            last_name="Employee",
        )
        cls.requirements = {}
        for key in "ABCDXOIY":
            org = cls.other if key == "X" else cls.org
            requirement = create_training_requirement(
                organization=org,
                actor=cls.foreign if key == "X" else cls.owner,
                project=cls.projects.get(key),
                code=f"F128-REQ-{key}",
                name=f"F128 distinctive requirement {key}",
            )
            if key == "I":
                requirement.is_active = False
                requirement.save()
            if key == "Y":
                requirement.archived_at = timezone.now()
                requirement.save()
            cls.requirements[key] = requirement

    def setUp(self):
        self.login(self.user)

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def form(self, data=None, membership="default"):
        return EmployeeTrainingRecordForm(
            data,
            organization=self.org,
            membership=self.limited if membership == "default" else membership,
        )

    def payload(self, key="B"):
        return {
            "employee": str(self.employee.pk),
            "requirement": str(self.requirements[key].pk),
            "occurred_on": "1405/07/30",
            "outcome": "attended",
            "notes": "F128 synthetic control",
        }

    def state(self):
        return (
            list(EmployeeTrainingRecord.objects.order_by("pk").values()),
            list(AuditEvent.objects.order_by("pk").values()),
        )

    def assert_choices(self, form, allowed="ABO"):
        self.assertSetEqual(
            set(form.fields["requirement"].queryset),
            {self.requirements[k] for k in allowed},
        )

    def assert_safe(self, response, allowed="ABO"):
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assert_choices(form, allowed)
        body = response.content.decode()
        body = re.sub(r'<input[^>]*name="next"[^>]*>', "", body)
        body = re.sub(r'href="[^"]*[?&](?:amp;)?next=[^"]*"', "", body)
        for key, requirement in self.requirements.items():
            if key not in allowed:
                self.assertNotIn(str(requirement.pk), body)
                self.assertNotIn(requirement.name, body)
                self.assertNotIn(requirement.code, body)
        return form

    def test_get_and_untrusted_query_preserve_only_authorized_project_choices(self):
        self.assert_safe(self.client.get(reverse("workforce:training_record_create")))
        for key in "CDX":
            with self.subTest(key=key):
                self.assert_safe(
                    self.client.get(
                        reverse("workforce:training_record_create"),
                        {"requirement": self.requirements[key].pk},
                    )
                )

    def test_organization_choices_include_projectless_and_exclude_foreign_lifecycle(
        self,
    ):
        self.login(self.owner)
        self.assert_safe(
            self.client.get(reverse("workforce:training_record_create")), "ABCDO"
        )

    def test_site_only_never_inherits_parent_project_choice(self):
        self.login(self.site_user)
        self.assert_safe(
            self.client.get(reverse("workforce:training_record_create")), "O"
        )
        before = self.state()
        for key in "ABCDX":
            with self.subTest(key=key):
                form = self.assert_safe(
                    self.client.post(
                        reverse("workforce:training_record_create"), self.payload(key)
                    ),
                    "O",
                )
                self.assertIn("requirement", form.errors)
                self.assertEqual(self.state(), before)

    def test_manipulated_inactive_archived_foreign_and_malformed_post_rejected(self):
        before = self.state()
        for key in "CDXIY":
            with self.subTest(key=key):
                form = self.assert_safe(
                    self.client.post(
                        reverse("workforce:training_record_create"), self.payload(key)
                    )
                )
                self.assertIn("requirement", form.errors)
                self.assertEqual(self.state(), before)
        form = self.assert_safe(
            self.client.post(
                reverse("workforce:training_record_create"),
                self.payload() | {"requirement": "not-a-uuid"},
            )
        )
        self.assertIn("requirement", form.errors)
        self.assertEqual(self.state(), before)

    def test_every_required_field_failure_redisplays_without_protected_metadata(self):
        before = self.state()
        for name, field in self.form().fields.items():
            if field.required:
                with self.subTest(field=name):
                    data = self.payload()
                    data.pop(name)
                    form = self.assert_safe(
                        self.client.post(
                            reverse("workforce:training_record_create"), data
                        )
                    )
                    self.assertIn(name, form.errors)
                    self.assertEqual(self.state(), before)

    def test_real_stricter_write_gate_stays_unchanged_for_visible_b_and_projectless(
        self,
    ):
        before = self.state()
        for key in "BO":
            with self.subTest(key=key):
                form = self.assert_safe(
                    self.client.post(
                        reverse("workforce:training_record_create"), self.payload(key)
                    )
                )
                self.assertIn("اجازه", str(form.non_field_errors()))
                self.assertEqual(self.state(), before)

    def test_service_failure_redisplay_retains_scoping(self):
        before = self.state()
        with patch(
            "apps.workforce.views.record_employee_training",
            side_effect=ValueError("F128 service validation control"),
        ):
            form = self.assert_safe(
                self.client.post(
                    reverse("workforce:training_record_create"), self.payload()
                )
            )
        self.assertIn("F128 service validation control", str(form.non_field_errors()))
        self.assertEqual(self.state(), before)

    def test_missing_wrong_tenant_and_invalid_membership_fail_closed(self):
        for membership in (None, object(), self.foreign_member):
            with self.subTest(membership=type(membership).__name__):
                for data in (None, self.payload()):
                    self.assert_choices(self.form(data, membership), "")

    def test_absent_grants_and_permission_do_not_reveal_even_projectless_entries(self):
        self.limited.scope_grants.update(revoked_at=timezone.now())
        self.assert_choices(self.form(), "")
        self.assertEqual(
            self.client.get(reverse("workforce:training_record_create")).status_code,
            403,
        )
        self.assert_choices(self.form(membership=self.viewer_member), "")
        self.login(self.viewer)
        self.assertEqual(
            self.client.get(reverse("workforce:training_record_create")).status_code,
            403,
        )

    def test_revoked_grant(self):
        self.limited.scope_grants.filter(project=self.projects["A"]).update(
            revoked_at=timezone.now()
        )
        self.assert_choices(self.form(), "BO")

    def test_expired_grant(self):
        now = timezone.now()
        self.limited.scope_grants.filter(project=self.projects["A"]).update(
            starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1)
        )
        self.assert_choices(self.form(), "BO")

    def test_future_grant(self):
        self.limited.scope_grants.filter(project=self.projects["A"]).update(
            starts_at=timezone.now() + timedelta(days=1)
        )
        self.assert_choices(self.form(), "BO")

    def test_inactive_membership(self):
        self.limited.status = "inactive"
        self.limited.save(update_fields=["status"])
        self.assert_choices(self.form(), "")

    def test_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assert_choices(self.form(), "")

    def test_suspended_tenant(self):
        self.org.status = "suspended"
        self.org.save(update_fields=["status"])
        self.assert_choices(self.form(), "")

    def test_revoked_role_fails_closed(self):
        self.limited.role_assignments.update(revoked_at=timezone.now())
        self.assert_choices(self.form(), "")
        self.assertEqual(
            self.client.get(reverse("workforce:training_record_create")).status_code,
            403,
        )

    def test_employee_master_and_catalogue_ordering_unchanged(self):
        form = self.form()
        self.assertSetEqual(set(form.fields["employee"].queryset), {self.employee})
        self.assertEqual(form.fields["requirement"].queryset.query.order_by, ())
        self.assertEqual(
            list(form.fields["requirement"].queryset),
            [self.requirements[k] for k in "ABO"],
        )

    def test_direct_services_reject_unauthorized_actors_and_cross_tenant(self):
        before = self.state()
        for actor, keys in (
            (self.user, "ABCDXO"),
            (self.site_user, "ABCDXO"),
            (self.owner, "X"),
        ):
            for key in keys:
                with self.subTest(actor=actor.username, key=key):
                    with self.assertRaises(PermissionDenied):
                        record_employee_training(
                            organization=self.org,
                            actor=actor,
                            employee=self.employee,
                            requirement=self.requirements[key],
                            occurred_on=date(2026, 10, 22),
                            outcome="attended",
                        )
                    self.assertEqual(self.state(), before)

    def test_authorized_project_and_projectless_posts_create_one_record_and_audit(self):
        self.login(self.owner)
        for key in "BO":
            with self.subTest(key=key):
                count = EmployeeTrainingRecord.objects.count()
                audits = AuditEvent.objects.filter(
                    action=AuditAction.EMPLOYEE_TRAINING_RECORDED
                ).count()
                response = self.client.post(
                    reverse("workforce:training_record_create"), self.payload(key)
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(EmployeeTrainingRecord.objects.count(), count + 1)
                self.assertEqual(
                    AuditEvent.objects.filter(
                        action=AuditAction.EMPLOYEE_TRAINING_RECORDED
                    ).count(),
                    audits + 1,
                )
                record = EmployeeTrainingRecord.objects.get(
                    organization=self.org, requirement=self.requirements[key]
                )
                self.assertEqual(record.recorded_by, self.owner)
                self.assertEqual(record.employee, self.employee)
                self.assertEqual(record.occurred_on, date(2026, 10, 22))
                record.notes = "silent mutation"
                with self.assertRaises(ValidationError):
                    record.save()
