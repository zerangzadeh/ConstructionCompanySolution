"""Product Decision 2026-10-22: first-grant and reconciled role boundaries."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.access_services import (
    assign_membership_role,
    assign_platform_admin,
    bootstrap_membership_authorization,
    create_organization_role,
)
from apps.organizations.authorization import (
    has_business_permission,
)
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    PlatformRoleAssignment,
)
from apps.organizations.permission_registry import registered_permission_codes
from apps.organizations.platform_grants import platform_initial_grant
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS
from apps.organizations.role_reconciliation import (
    ROLE_PERMISSION_ADDITIONS,
    UNASSIGNED_PERMISSION_REASONS,
)
from apps.organizations.services import (
    create_organization_by_system_admin,
    create_organization_with_owner,
)
from apps.projects.models import Project, ProjectSite


class ReconciledMatrixTests(SimpleTestCase):
    def test_all_registered_permissions_are_explicitly_represented(self):
        self.assertEqual(
            set().union(*DEFAULT_ROLE_PERMISSIONS.values()),
            set(registered_permission_codes()) - set(UNASSIGNED_PERMISSION_REASONS),
        )

    def test_governance_roles_not_used_as_gap_dump_and_specialist_duties_separate(self):
        self.assertNotIn("tenant_owner", ROLE_PERMISSION_ADDITIONS)
        self.assertNotIn("tenant_admin", ROLE_PERMISSION_ADDITIONS)
        for role in ("tenant_owner", "tenant_admin"):
            for permission in (
                "employment_records.manage",
                "rfq_quotes.open",
                "supplier_portal.invitations_manage",
                "payroll.prepare",
            ):
                self.assertNotIn(permission, DEFAULT_ROLE_PERMISSIONS[role])
        self.assertNotIn(
            "payroll.review", DEFAULT_ROLE_PERMISSIONS["payroll_specialist"]
        )
        self.assertNotIn(
            "payroll.prepare", DEFAULT_ROLE_PERMISSIONS["payroll_reviewer"]
        )
        self.assertNotIn(
            "rfq_quotes.approve_open", DEFAULT_ROLE_PERMISSIONS["rfq_opener"]
        )
        self.assertNotIn("rfq_quotes.open", DEFAULT_ROLE_PERMISSIONS["rfq_custodian"])
        self.assertNotIn(
            "payroll.prepare", DEFAULT_ROLE_PERMISSIONS["hr_administrator"]
        )


class PlatformInitialGrantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser(username="grant-root", password="x")
        cls.platform = User.objects.create_user(username="grant-platform")
        assign_platform_admin(
            actor=cls.root,
            approver=cls.root,
            target=cls.platform,
            reason="Test Platform duty",
        )
        cls.owner = User.objects.create_user(username="grant-owner")
        cls.organization = create_organization_by_system_admin(
            actor=cls.platform,
            owner=cls.owner,
            name="Initial Grant",
            slug="initial-grant",
        )
        cls.target = OrganizationMembership.objects.create(
            organization=cls.organization,
            user=User.objects.create_user(username="grant-target"),
            role="member",
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
            authorization_quarantined_at=timezone.now(),
        )
        cls.project = Project.objects.create(
            organization=cls.organization, code="A", name="Project A"
        )
        cls.other_project = Project.objects.create(
            organization=cls.organization, code="B", name="Project B"
        )
        cls.site = ProjectSite.objects.create(
            organization=cls.organization, project=cls.project, code="S", name="Site"
        )
        cls.role = OrganizationRole.objects.get(code="rfq_opener", organization=None)

    def grant(self, **overrides):
        kwargs = {
            "organization": self.organization,
            "actor": self.platform,
            "membership_id": self.target.pk,
            "role": self.role,
            "scope_type": "project",
            "project": self.project,
            "reason": "Exact Development first-grant control",
        }
        kwargs.update(overrides)
        return platform_initial_grant(**kwargs)

    def assert_no_grant(self):
        self.assertFalse(self.target.role_assignments.exists())
        self.assertFalse(self.target.scope_grants.exists())

    def test_tenant_creation_designates_canonical_owner_without_platform_membership(
        self,
    ):
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )
        self.assertTrue(
            membership.role_assignments.filter(role__code="tenant_owner").exists()
        )
        self.assertTrue(
            membership.scope_grants.filter(scope_type="organization").exists()
        )
        self.assertFalse(
            OrganizationMembership.objects.filter(user=self.platform).exists()
        )
        self.assertFalse(
            has_business_permission(
                user=self.platform,
                organization=self.organization,
                permission="projects.view",
            )
        )

    def test_grant_atomic_audited_and_bounded_without_second_platform_approver(self):
        assignment, scope = self.grant()
        self.target.refresh_from_db()
        self.assertIsNone(self.target.authorization_quarantined_at)
        self.assertIsNone(assignment.assigned_by_id)
        self.assertIsNone(assignment.approved_by_id)
        self.assertEqual(assignment.source, "platform_initial_grant")
        self.assertEqual(scope.project_id, self.project.pk)
        events = list(
            AuditEvent.objects.filter(
                actor=self.platform, metadata__source="platform_initial_grant"
            )
        )
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].correlation_id, events[1].correlation_id)
        self.assertEqual(
            events[0].metadata["target_membership_id"], str(self.target.pk)
        )
        self.assertEqual(events[0].metadata["previous_permissions"], [])
        self.assertEqual(
            set(events[0].metadata["role_permissions"]),
            set(self.role.permissions.values_list("code", flat=True)),
        )
        for project, expected in ((self.project, True), (self.other_project, False)):
            self.assertEqual(
                has_business_permission(
                    user=self.target.user,
                    organization=self.organization,
                    permission="rfq_quotes.open",
                    project=project,
                ),
                expected,
            )
        self.assertFalse(
            OrganizationMembership.objects.filter(user=self.platform).exists()
        )

    def test_superuser_and_staff_do_not_imply_platform_authority(self):
        self.root.is_staff = True
        User.objects.filter(pk=self.owner.pk).update(is_staff=True)
        for actor in (self.root, self.owner):
            with (
                self.subTest(actor=actor.username),
                self.assertRaises(PermissionDenied),
            ):
                self.grant(actor=actor)
        self.assert_no_grant()

    def test_self_grant_denied_even_for_different_tenant_membership(self):
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.platform,
            role="member",
            status="active",
        )
        with self.assertRaises(PermissionDenied):
            self.grant(membership_id=membership.pk)
        self.assertFalse(membership.role_assignments.exists())

    def test_rechecks_revoked_expired_future_and_inactive_platform_authority(self):
        duty = PlatformRoleAssignment.objects.get(user=self.platform)
        for changes in (
            {"revoked_at": timezone.now()},
            {"ends_at": timezone.now() - timedelta(seconds=1)},
            {"starts_at": timezone.now() + timedelta(days=1)},
        ):
            with self.subTest(changes=changes):
                old = {key: getattr(duty, key) for key in changes}
                PlatformRoleAssignment.objects.filter(pk=duty.pk).update(**changes)
                with self.assertRaises(PermissionDenied):
                    self.grant()
                PlatformRoleAssignment.objects.filter(pk=duty.pk).update(**old)
        User.objects.filter(pk=self.platform.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.grant()
        self.assert_no_grant()

    def test_inactive_tenant_membership_and_target_user_rejected_from_fresh_state(self):
        for status in ("suspended", "cancelled", "archived"):
            Organization.objects.filter(pk=self.organization.pk).update(
                status=status,
                archived_at=timezone.now() if status == "archived" else None,
            )
            with self.subTest(status=status), self.assertRaises(PermissionDenied):
                self.grant()
        Organization.objects.filter(pk=self.organization.pk).update(
            status="active", archived_at=None
        )
        OrganizationMembership.objects.filter(pk=self.target.pk).update(
            status="suspended"
        )
        with self.assertRaises(PermissionDenied):
            self.grant()
        OrganizationMembership.objects.filter(pk=self.target.pk).update(status="active")
        User.objects.filter(pk=self.target.user_id).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.grant()
        self.assert_no_grant()

    def test_foreign_membership_role_project_site_and_malformed_ids_denied(self):
        foreign_owner = User.objects.create_user(username="foreign-owner")
        foreign = create_organization_with_owner(
            owner=foreign_owner, name="Foreign", slug="foreign-grant"
        )
        foreign_role = create_organization_role(
            actor=self.platform,
            organization=foreign,
            code="foreign-role",
            name="Foreign role",
            description="Foreign role",
            permissions=["rfq_quotes.open"],
            reason="Foreign role control",
        )
        foreign_project = Project.objects.create(
            organization=foreign, code="F", name="F"
        )
        bad = [
            {"membership_id": foreign.memberships.get().pk},
            {"membership_id": "invalid"},
            {"role": foreign_role},
            {"project": foreign_project},
            {"scope_type": "unknown"},
            {"scope_type": "site", "site": self.site, "project": self.other_project},
            {"scope_type": "organization"},
            {"scope_type": "site"},
        ]
        for kwargs in bad:
            with (
                self.subTest(kwargs=kwargs),
                self.assertRaises((PermissionDenied, ValidationError)),
            ):
                self.grant(**kwargs)
        self.assert_no_grant()

    def test_stale_inactive_role_and_permission_and_empty_reason_rejected(self):
        OrganizationRole.objects.filter(pk=self.role.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.grant()
        OrganizationRole.objects.filter(pk=self.role.pk).update(is_active=True)
        BusinessPermission.objects.filter(code="rfq_quotes.open").update(
            is_active=False
        )
        with self.assertRaises(ValidationError):
            self.grant()
        BusinessPermission.objects.filter(code="rfq_quotes.open").update(is_active=True)
        with self.assertRaises(ValidationError):
            self.grant(reason=" ")
        self.assert_no_grant()

    def test_lawful_tenant_delegation_prevents_initial_grant(self):
        owner_membership = self.organization.memberships.get(user=self.owner)
        owner_role = OrganizationRole.objects.get(code="tenant_owner")
        # Give an existing delegator the exact authority through the test fixture.
        owner_role.permissions.add(*self.role.permissions.all())
        reviewer = OrganizationMembership.objects.create(
            organization=self.organization,
            user=User.objects.create_user(username="tenant-reviewer"),
            role="member",
            status="active",
        )
        bootstrap_membership_authorization(
            membership=reviewer, actor=self.owner, source="test"
        )
        with self.assertRaises(PermissionDenied):
            self.grant()
        self.assert_no_grant()
        assignment = assign_membership_role(
            organization=self.organization,
            actor=self.owner,
            membership_id=self.target.pk,
            role=self.role,
            approver_membership_id=reviewer.pk,
            reason="Ordinary path preserved",
        )
        self.assertEqual(assignment.assigned_by_id, owner_membership.pk)
        self.assertEqual(assignment.approved_by_id, reviewer.pk)

    def test_holder_without_delegation_authority_does_not_block_initial_grant(self):
        holder = OrganizationMembership.objects.create(
            organization=self.organization,
            user=User.objects.create_user(username="grant-holder"),
            role="member",
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=holder,
            role=self.role,
            reason="Existing specialist",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=holder,
            scope_type="project",
            project=self.project,
            reason="Existing specialist",
        )
        self.grant()

    def test_broader_or_unrelated_existing_scopes_fail_closed(self):
        for scope_type, project in (
            ("organization", None),
            ("project", self.other_project),
        ):
            grant = MembershipScopeGrant.objects.create(
                organization=self.organization,
                membership=self.target,
                scope_type=scope_type,
                project=project,
                reason="Existing scope",
            )
            with self.assertRaises(PermissionDenied):
                self.grant()
            grant.delete()
        self.assert_no_grant()

    def test_existing_exact_scope_reused_and_replay_rejected(self):
        scope = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.target,
            scope_type="project",
            project=self.project,
            reason="Existing exact scope",
        )
        _, granted = self.grant()
        self.assertEqual(granted.pk, scope.pk)
        self.assertEqual(self.target.scope_grants.count(), 1)
        with self.assertRaises(ValidationError):
            self.grant()
        self.assertEqual(self.target.role_assignments.count(), 1)

    def test_site_scope_and_organization_scope_use_existing_enforcement(self):
        _, scope = self.grant(scope_type="site", site=self.site)
        self.assertEqual(scope.site_id, self.site.pk)
        self.assertTrue(
            has_business_permission(
                user=self.target.user,
                organization=self.organization,
                permission="rfq_quotes.open",
                project=self.project,
                site=self.site,
            )
        )
        self.assertFalse(
            has_business_permission(
                user=self.target.user,
                organization=self.organization,
                permission="rfq_quotes.open",
                project=self.project,
            )
        )

    def test_audit_failure_rolls_back_role_scope_and_quarantine_completion(self):
        with (
            patch(
                "apps.organizations.platform_grants.record_audit_event",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.grant()
        self.assert_no_grant()
        self.target.refresh_from_db()
        self.assertIsNotNone(self.target.authorization_quarantined_at)

    def test_ordinary_assignment_still_rejects_missing_delegated_permission(self):
        with self.assertRaises(PermissionDenied):
            assign_membership_role(
                organization=self.organization,
                actor=self.owner,
                membership_id=self.target.pk,
                role=self.role,
                approver_membership_id=self.organization.memberships.get(
                    user=self.owner
                ).pk,
                reason="No transfer outside actor authority",
            )
        self.assert_no_grant()

    def test_operator_command_uses_same_service(self):
        output = StringIO()
        call_command(
            "platform_initial_grant",
            actor=self.platform.username,
            organization=str(self.organization.pk),
            membership=str(self.target.pk),
            role=str(self.role.pk),
            scope="project",
            project=str(self.project.pk),
            reason="Operator command control",
            stdout=output,
        )
        self.assertIn("Initial Grant:", output.getvalue())
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.MEMBERSHIP_ROLE_ASSIGNED,
                actor=self.platform,
                metadata__source="platform_initial_grant",
            ).exists()
        )
