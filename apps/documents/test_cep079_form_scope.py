from django.test import TestCase

from apps.accounts.models import User
from apps.contracts.models import Contract
from apps.documents.forms import DocumentTargetForm
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Project


class DocumentTargetScopeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="dms-scope-owner")
        self.org = create_organization_with_owner(
            owner=self.owner, name="DMS scope", slug="dms-scope"
        )
        other = User.objects.create_user(username="dms-other-owner")
        self.foreign = create_organization_with_owner(
            owner=other, name="Foreign DMS", slug="foreign-dms"
        )
        self.user = User.objects.create_user(username="dms-project-reader")
        self.role = OrganizationRole.objects.create(
            organization=self.org, code="dms-project", name="DMS project"
        )
        self.role.permissions.add(BusinessPermission.objects.get(code="projects.view"))
        self.membership = OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            status="active",
            role_definition=self.role,
        )
        MembershipRoleAssignment.objects.create(
            organization=self.org,
            membership=self.membership,
            role=self.role,
            reason="Explicit test role",
        )
        self.allowed = Project.objects.create(organization=self.org, code="A", name="A")
        self.denied = Project.objects.create(organization=self.org, code="B", name="B")
        self.other = Project.objects.create(
            organization=self.foreign, code="C", name="C"
        )
        MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.membership,
            scope_type="project",
            project=self.allowed,
            reason="Only project A",
        )

    def form(self, **kwargs):
        return DocumentTargetForm(organization=self.org, user=self.user, **kwargs)

    def test_project_reader_has_exact_allowed_choices_and_valid_target(self):
        form = self.form(data={"project": str(self.allowed.pk)})
        self.assertEqual(list(form.fields["project"].queryset), [self.allowed])
        self.assertTrue(form.is_valid(), form.errors)

    def test_ungranted_and_foreign_targets_cannot_be_selected(self):
        for target in (self.denied, self.other):
            with self.subTest(target=target.pk):
                form = self.form(data={"project": str(target.pk)})
                self.assertFalse(form.is_valid())
                self.assertIn("project", form.errors)

    def test_missing_permission_cannot_reveal_choices(self):
        self.role.permissions.clear()
        self.assertFalse(self.form().fields["project"].queryset.exists())

    def test_linked_contract_choices_intersect_source_project(self):
        self.role.permissions.add(BusinessPermission.objects.get(code="contracts.view"))
        contracts = [
            Contract.objects.create(
                organization=project.organization,
                project=project,
                contract_number=project.code,
                title=project.code,
                counterparty_name="Synthetic",
                direction="receivable",
                status="active",
            )
            for project in (self.allowed, self.denied, self.other)
        ]
        self.assertEqual(list(self.form().fields["contract"].queryset), contracts[:1])

    def test_inactive_membership_fails_closed(self):
        self.membership.status = "suspended"
        self.membership.save(update_fields=["status"])
        self.assertFalse(self.form().fields["project"].queryset.exists())

    def test_organization_grant_remains_tenant_filtered(self):
        MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.membership,
            scope_type="organization",
            reason="Organization test scope",
        )
        self.assertSetEqual(
            set(self.form().fields["project"].queryset), {self.allowed, self.denied}
        )
