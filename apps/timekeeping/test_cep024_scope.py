from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Activity, Project, ProjectSite, WBSNode
from apps.workforce.models import Employee

from .forms import TimesheetEntryForm
from .services import add_timesheet_entry, create_timesheet


class Cep024TimekeepingScopeTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="cep024-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="CEP 024 Tenant", slug="cep-024-tenant"
        )
        self.employee = Employee.objects.create(
            organization=self.organization,
            employee_number="CEP024-1",
            first_name="Scope",
            last_name="Worker",
        )
        self.project = Project.objects.create(
            organization=self.organization,
            code="CEP024",
            name="Scoped project",
            created_by=self.owner,
        )
        self.site_a = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="CEP024-A",
            name="Site A",
            created_by=self.owner,
        )
        self.site_b = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="CEP024-B",
            name="Site B",
            created_by=self.owner,
        )
        self.wbs = WBSNode.objects.create(
            organization=self.organization,
            project=self.project,
            code="CEP024-WBS",
            title="Scoped work",
            created_by=self.owner,
        )
        self.activity_a = Activity.objects.create(
            organization=self.organization,
            project=self.project,
            site=self.site_a,
            wbs_node=self.wbs,
            code="CEP024-ACT-A",
            name="Site A activity",
            created_by=self.owner,
        )
        self.sheet = create_timesheet(
            organization=self.organization,
            actor=self.owner,
            employee=self.employee,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 1),
            declared_minutes=60,
        )

    def _scoped_user(self, *, site: ProjectSite, username: str) -> User:
        user = User.objects.create_user(username=username)
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code=f"{username}-role",
            name=username,
            created_by=self.owner,
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    BusinessPermissionCode.TIMESHEETS_PREPARE,
                    BusinessPermissionCode.TIMESHEETS_VIEW,
                ]
            )
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            joined_at=timezone.now(),
            assigned_by=self.owner,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="CEP-024 focused scope",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.SITE,
            project=self.project,
            site=site,
            reason="CEP-024 focused site scope",
        )
        return user

    def _entry_data(self, *, site: ProjectSite | None, activity: Activity | None) -> dict:
        return {
            "work_date": date(2026, 10, 1),
            "project": self.project,
            "site": site,
            "activity": activity,
            "minutes": 60,
        }

    def test_matching_project_site_activity_is_allowed(self) -> None:
        entry = add_timesheet_entry(
            organization=self.organization,
            actor=self.owner,
            timesheet=self.sheet,
            **self._entry_data(site=self.site_a, activity=self.activity_a),
        )

        self.assertEqual(entry.site_id, self.site_a.pk)
        self.assertEqual(entry.activity_id, self.activity_a.pk)

    def test_service_and_model_reject_stale_or_unselected_activity_site(self) -> None:
        for site in (self.site_b, None):
            with self.subTest(site=site), self.assertRaises(ValidationError):
                add_timesheet_entry(
                    organization=self.organization,
                    actor=self.owner,
                    timesheet=self.sheet,
                    **self._entry_data(site=site, activity=self.activity_a),
                )

    def test_form_rejects_invalid_site_activity_cascade(self) -> None:
        form = TimesheetEntryForm(
            data={
                "work_date": "2026-10-01",
                "project": self.project.pk,
                "site": self.site_b.pk,
                "activity": self.activity_a.pk,
                "minutes": 60,
                "note": "",
            },
            organization=self.organization,
            user=self.owner,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("activity", form.errors)

    def test_scoped_actor_and_direct_url_cannot_bypass_site_scope(self) -> None:
        add_timesheet_entry(
            organization=self.organization,
            actor=self.owner,
            timesheet=self.sheet,
            **self._entry_data(site=self.site_a, activity=self.activity_a),
        )
        site_b_actor = self._scoped_user(site=self.site_b, username="cep024-site-b")

        with self.assertRaises(PermissionDenied):
            add_timesheet_entry(
                organization=self.organization,
                actor=site_b_actor,
                timesheet=self.sheet,
                **self._entry_data(site=self.site_a, activity=self.activity_a),
            )
        self.client.force_login(site_b_actor)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("timekeeping:timesheet_detail", args=[self.sheet.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Site A", status_code=404)

    def test_cross_tenant_objects_are_rejected_before_persistence(self) -> None:
        other_owner = User.objects.create_user(username="cep024-other-owner")
        other_organization = create_organization_with_owner(
            owner=other_owner, name="CEP 024 Other", slug="cep-024-other"
        )
        other_project = Project.objects.create(
            organization=other_organization,
            code="OTHER",
            name="Other project",
            created_by=other_owner,
        )

        with self.assertRaises((PermissionDenied, ValidationError)):
            add_timesheet_entry(
                organization=self.organization,
                actor=self.owner,
                timesheet=self.sheet,
                work_date=date(2026, 10, 1),
                project=other_project,
                minutes=60,
            )
