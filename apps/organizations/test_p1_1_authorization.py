from datetime import timedelta
from importlib import import_module

from django.apps import apps as django_apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.access_services import (
    archive_organization_role,
    assign_membership_role,
    assign_platform_admin,
    create_organization_role,
    create_protected_operation_version,
    grant_membership_scope,
    prepare_membership_authorization_rollback,
    retire_protected_operation,
    revoke_membership_role,
    revoke_membership_scope,
    update_organization_role,
)
from apps.organizations.authorization import (
    has_business_permission,
    is_platform_admin,
    membership_permission_codes,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
    PlatformRoleAssignment,
    ProtectedOperationCode,
)
from apps.organizations.services import (
    create_organization_account,
    create_organization_with_owner,
)
from apps.projects.models import Project, ProjectSite


class P11AuthorizationTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="p11-owner", password="x")
        self.organization = create_organization_with_owner(
            owner=self.owner,
            name="P1.1 Tenant",
            slug="p11-tenant",
        )
        self.owner_membership = OrganizationMembership.objects.get(
            organization=self.organization,
            user=self.owner,
        )
        self.project_a = Project.objects.create(
            organization=self.organization,
            code="P-A",
            name="Project A",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.project_b = Project.objects.create(
            organization=self.organization,
            code="P-B",
            name="Project B",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.site_a = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project_a,
            code="S-A",
            name="Site A",
        )

    def _membership(self, username: str) -> OrganizationMembership:
        user = User.objects.create_user(username=username, password="x")
        return OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
            authorization_quarantined_at=timezone.now(),
        )

    def _direct_owner(self, username: str) -> OrganizationMembership:
        return self._direct_role(username, MembershipRole.TENANT_OWNER)

    def _direct_role(self, username: str, role_code: str) -> OrganizationMembership:
        membership = self._membership(username)
        role = OrganizationRole.objects.get(code=role_code)
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="test privileged role",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="test organization scope",
        )
        membership.authorization_quarantined_at = None
        membership.save(update_fields=["authorization_quarantined_at"])
        return membership

    def test_initial_owner_bootstrap_is_atomic_and_explicit(self) -> None:
        self.assertTrue(
            self.owner_membership.role_assignments.filter(
                role__code=MembershipRole.TENANT_OWNER,
                revoked_at__isnull=True,
            ).exists()
        )
        self.assertTrue(
            self.owner_membership.scope_grants.filter(
                scope_type=AuthorizationScopeType.ORGANIZATION,
                revoked_at__isnull=True,
            ).exists()
        )
        self.assertIsNotNone(self.owner_membership.authorization_migrated_at)
        self.assertIsNone(self.owner_membership.authorization_quarantined_at)

    def test_multi_role_permissions_are_unioned_and_intersected_with_scope(
        self,
    ) -> None:
        membership = self._membership("p11-multi-role")
        for code in (MembershipRole.ACCOUNTANT, MembershipRole.PROJECT_MANAGER):
            MembershipRoleAssignment.objects.create(
                organization=self.organization,
                membership=membership,
                role=OrganizationRole.objects.get(code=code),
                reason="multi-role test",
            )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project_a,
            reason="project A only",
        )
        codes = membership_permission_codes(membership)
        self.assertIn(BusinessPermissionCode.TREASURY_VIEW, codes)
        self.assertIn(BusinessPermissionCode.ACTIVITIES_CREATE, codes)
        self.assertTrue(
            has_business_permission(
                user=membership.user,
                organization=self.organization,
                permission=BusinessPermissionCode.TREASURY_VIEW,
                project=self.project_a,
            )
        )
        self.assertFalse(
            has_business_permission(
                user=membership.user,
                organization=self.organization,
                permission=BusinessPermissionCode.TREASURY_VIEW,
                project=self.project_b,
            )
        )

    def test_site_scope_allows_site_and_minimal_parent_but_not_sibling_project(
        self,
    ) -> None:
        membership = self._membership("p11-site")
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=OrganizationRole.objects.get(code=MembershipRole.PROJECT_MANAGER),
            reason="site role",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.SITE,
            project=self.project_a,
            site=self.site_a,
            reason="site only",
        )
        self.assertTrue(
            has_business_permission(
                user=membership.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECT_SITES_VIEW,
                project=self.project_a,
                site=self.site_a,
            )
        )
        self.assertTrue(
            has_business_permission(
                user=membership.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                project=self.project_a,
                allow_site_parent=True,
            )
        )
        self.assertFalse(
            has_business_permission(
                user=membership.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                project=self.project_b,
                allow_site_parent=True,
            )
        )

    def test_role_and_scope_expiry_and_revocation_are_rechecked(self) -> None:
        membership = self._membership("p11-expiry")
        role = MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=OrganizationRole.objects.get(code=MembershipRole.PROJECT_MANAGER),
            starts_at=timezone.now() - timedelta(days=2),
            ends_at=timezone.now() - timedelta(days=1),
            reason="expired",
        )
        grant = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project_a,
            starts_at=timezone.now() - timedelta(days=2),
            ends_at=timezone.now() - timedelta(days=1),
            reason="expired",
        )
        self.assertFalse(
            has_business_permission(
                user=membership.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                project=self.project_a,
            )
        )
        role.ends_at = None
        role.revoked_at = timezone.now()
        role.save(update_fields=["ends_at", "revoked_at"])
        grant.ends_at = None
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["ends_at", "revoked_at"])
        self.assertFalse(
            has_business_permission(
                user=membership.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                project=self.project_a,
            )
        )

    def test_role_and_grant_services_require_independent_approval_and_audit(
        self,
    ) -> None:
        approver = self._direct_owner("p11-approver")
        target = self._membership("p11-target")
        assignment = assign_membership_role(
            organization=self.organization,
            actor=self.owner,
            membership_id=target.pk,
            role=MembershipRole.PROJECT_MANAGER,
            approver_membership_id=approver.pk,
            reason="approved assignment",
        )
        grant = grant_membership_scope(
            organization=self.organization,
            actor=self.owner,
            membership_id=target.pk,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project_a,
            approver_membership_id=approver.pk,
            reason="approved scope",
        )
        self.assertIsNone(
            target.__class__.objects.get(pk=target.pk).authorization_quarantined_at
        )
        assignment_event = AuditEvent.objects.get(
            action=AuditAction.MEMBERSHIP_ROLE_ASSIGNED,
            entity_id=str(assignment.pk),
        )
        self.assertEqual(assignment_event.organization, self.organization)
        self.assertEqual(assignment_event.actor, self.owner)
        self.assertEqual(assignment_event.metadata["reason"], "approved assignment")
        self.assertIn("previous_permissions", assignment_event.metadata)
        self.assertIn("new_permissions", assignment_event.metadata)
        revoked_role = revoke_membership_role(
            organization=self.organization,
            actor=self.owner,
            assignment_id=assignment.pk,
            approver_membership_id=approver.pk,
            reason="remove role",
        )
        revoked_scope = revoke_membership_scope(
            organization=self.organization,
            actor=self.owner,
            grant_id=grant.pk,
            approver_membership_id=approver.pk,
            reason="remove scope",
        )
        self.assertIsNotNone(revoked_role.revoked_at)
        self.assertIsNotNone(revoked_scope.revoked_at)
        revocation_event = AuditEvent.objects.get(
            action=AuditAction.MEMBERSHIP_ROLE_REVOKED,
            entity_id=str(assignment.pk),
        )
        self.assertIn("previous_permissions", revocation_event.metadata)
        self.assertIn("new_permissions", revocation_event.metadata)

    def test_self_grant_and_last_owner_revocation_are_denied(self) -> None:
        actor = self._direct_role("p11-admin-actor", MembershipRole.TENANT_ADMIN)
        approver = self._direct_role("p11-admin-approver", MembershipRole.TENANT_ADMIN)
        with self.assertRaises(PermissionDenied):
            grant_membership_scope(
                organization=self.organization,
                actor=self.owner,
                membership_id=self.owner_membership.pk,
                scope_type=AuthorizationScopeType.PROJECT,
                project=self.project_a,
                approver_membership_id=approver.pk,
                reason="self grant",
            )
        owner_assignment = self.owner_membership.role_assignments.get(
            role__code=MembershipRole.TENANT_OWNER
        )
        with self.assertRaises(ValidationError):
            revoke_membership_role(
                organization=self.organization,
                actor=actor.user,
                assignment_id=owner_assignment.pk,
                approver_membership_id=approver.pk,
                reason="would remove final owner",
            )

    def test_single_superuser_can_assign_platform_admin_without_tenant_access(
        self,
    ) -> None:
        superuser = User.objects.create_superuser(
            username="p11-superuser", password="x", email="root@example.test"
        )
        platform_user = User.objects.create_user(username="p11-platform", password="x")
        assign_platform_admin(
            actor=superuser,
            approver=superuser,
            target=platform_user,
            reason="platform operations",
        )
        self.assertTrue(is_platform_admin(platform_user))
        for user in (superuser, platform_user):
            self.assertFalse(
                has_business_permission(
                    user=user,
                    organization=self.organization,
                    permission=BusinessPermissionCode.PROJECTS_VIEW,
                    project=self.project_a,
                )
            )

    def test_platform_admin_self_assignment_is_denied(self) -> None:
        superuser = User.objects.create_superuser(
            username="p11-platform-self", password="x", email="self@example.test"
        )

        with self.assertRaises(PermissionDenied):
            assign_platform_admin(
                actor=superuser,
                approver=superuser,
                target=superuser,
                reason="self assignment",
            )

    def test_platform_admin_owns_protected_operation_lifecycle(self) -> None:
        superuser = User.objects.create_superuser(
            username="p11-protected-root", password="x", email="root@example.test"
        )
        actor = User.objects.create_user(username="p11-protected-admin", password="x")
        assign_platform_admin(
            actor=superuser,
            approver=superuser,
            target=actor,
            reason="protected operation administration",
        )
        item = create_protected_operation_version(
            actor=actor,
            code=ProtectedOperationCode.AUTHORIZATION_POLICY_WEAKEN,
            name="Policy weakening",
            description="Protected",
            reason="versioned change",
        )
        self.assertGreaterEqual(item.version, 2)
        retired = retire_protected_operation(
            actor=actor,
            code=ProtectedOperationCode.AUTHORIZATION_POLICY_WEAKEN,
            reason="catalogue correction",
        )
        self.assertEqual(retired.pk, item.pk)
        self.assertIsNotNone(retired.retired_at)
        with self.assertRaises(PermissionDenied):
            create_protected_operation_version(
                actor=superuser,
                code=ProtectedOperationCode.AUTHORIZATION_POLICY_WEAKEN,
                name="Invalid",
                description="Invalid",
                reason="self approval",
            )

    def test_compatibility_rollback_keeps_scope_restrictions(self) -> None:
        target = self._membership("p11-rollback")
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=target,
            role=OrganizationRole.objects.get(code=MembershipRole.PROJECT_MANAGER),
            reason="rollback role",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=target,
            scope_type=AuthorizationScopeType.PROJECT,
            project=self.project_a,
            reason="rollback scope",
        )
        prepare_membership_authorization_rollback(
            organization=self.organization,
            actor=self.owner,
            membership_id=target.pk,
            reason="compatibility rehearsal",
        )
        target.refresh_from_db()
        self.assertIsNotNone(target.authorization_migrated_at)
        self.assertFalse(
            has_business_permission(
                user=target.user,
                organization=self.organization,
                permission=BusinessPermissionCode.PROJECTS_VIEW,
                project=self.project_b,
            )
        )

    def test_database_rejects_duplicate_unrevoked_role_assignment(self) -> None:
        membership = self._membership("p11-concurrency")
        role = OrganizationRole.objects.get(code=MembershipRole.SUPERVISOR)
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="first writer",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MembershipRoleAssignment.objects.create(
                organization=self.organization,
                membership=membership,
                role=role,
                reason="competing writer",
            )

    def test_cross_tenant_scope_grant_is_rejected(self) -> None:
        other_owner = User.objects.create_user(username="p11-other-owner", password="x")
        other = create_organization_with_owner(
            owner=other_owner,
            name="Other Tenant",
            slug="other-p11-tenant",
        )
        other_project = Project.objects.create(
            organization=other,
            code="OTHER",
            name="Other Project",
        )
        approver = self._direct_owner("p11-cross-approver")
        target = self._membership("p11-cross-target")
        with self.assertRaises(PermissionDenied):
            grant_membership_scope(
                organization=self.organization,
                actor=self.owner,
                membership_id=target.pk,
                scope_type=AuthorizationScopeType.PROJECT,
                project=other_project,
                approver_membership_id=approver.pk,
                reason="cross tenant",
            )

    def test_platform_role_duplicate_write_is_rejected(self) -> None:
        actor = User.objects.create_superuser(
            username="p11-platform-root-1", password="x", email="r1@example.test"
        )
        approver = User.objects.create_superuser(
            username="p11-platform-root-2", password="x", email="r2@example.test"
        )
        target = User.objects.create_user(username="p11-platform-target", password="x")
        assign_platform_admin(
            actor=actor,
            approver=approver,
            target=target,
            reason="first",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlatformRoleAssignment.objects.create(
                user=target,
                role="platform_admin",
                assigned_by=actor,
                approved_by=approver,
                reason="duplicate",
            )


class P11RoleCatalogCloseoutTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="catalog-owner", password="x")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="Catalog Tenant", slug="catalog-tenant"
        )
        self.other_owner = User.objects.create_user(
            username="catalog-other-owner", password="x"
        )
        self.other_organization = create_organization_with_owner(
            owner=self.other_owner, name="Other Catalog Tenant", slug="other-catalog"
        )
        self.root = User.objects.create_superuser(
            username="catalog-root", password="x", email="root@catalog.test"
        )
        self.platform_admin = User.objects.create_user(
            username="catalog-platform", password="x"
        )
        assign_platform_admin(
            actor=self.root,
            approver=self.root,
            target=self.platform_admin,
            reason="role catalogue owner",
        )
        self.permission = BusinessPermission.objects.get(
            code=BusinessPermissionCode.PROJECTS_VIEW
        )

    def _tenant_admin(self) -> User:
        user = User.objects.create_user(username="catalog-tenant-admin", password="x")
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role=MembershipRole.TENANT_ADMIN,
            role_definition=OrganizationRole.objects.get(
                code=MembershipRole.TENANT_ADMIN, organization__isnull=True
            ),
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=membership.role_definition,
            reason="tenant admin test authority",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="tenant admin test scope",
        )
        return user

    def test_platform_admin_manages_global_tenant_and_system_roles_with_audit(
        self,
    ) -> None:
        global_role = create_organization_role(
            actor=self.platform_admin,
            organization=None,
            code="global-reviewer",
            name="Global Reviewer",
            description="global",
            permissions=[self.permission.code],
            reason="global role requested",
        )
        tenant_role = create_organization_role(
            actor=self.platform_admin,
            organization=self.organization,
            code="tenant-reviewer",
            name="Tenant Reviewer",
            description="tenant",
            permissions=[self.permission.code],
            reason="tenant role requested",
        )
        system_role = OrganizationRole.objects.get(
            code=MembershipRole.TENANT_ADMIN, organization__isnull=True
        )
        previous_permissions = sorted(
            system_role.permissions.values_list("code", flat=True)
        )
        update_organization_role(
            actor=self.platform_admin,
            role_id=system_role.pk,
            name="Tenant Admin Updated",
            description=system_role.description,
            permissions=previous_permissions,
            reason="presentation correction",
        )
        archived = archive_organization_role(
            actor=self.platform_admin,
            role_id=tenant_role.pk,
            reason="role retired",
        )
        self.assertFalse(archived.is_active)
        self.assertTrue(global_role.is_active)
        with self.assertRaises(PermissionDenied):
            archive_organization_role(
                actor=self.platform_admin,
                role_id=system_role.pk,
                reason="not allowed",
            )
        event = AuditEvent.objects.get(
            action=AuditAction.ROLE_UPDATED, entity_id=str(system_role.pk)
        )
        self.assertEqual(event.actor, self.platform_admin)
        self.assertEqual(event.metadata["previous_permissions"], previous_permissions)
        self.assertEqual(event.metadata["new_permissions"], previous_permissions)
        self.assertEqual(event.metadata["reason"], "presentation correction")

    def test_tenant_admin_is_limited_to_own_tenant_custom_roles(self) -> None:
        tenant_admin = self._tenant_admin()
        own_role = create_organization_role(
            actor=tenant_admin,
            organization=self.organization,
            code="site-reviewer",
            name="Site Reviewer",
            description="own tenant",
            permissions=[self.permission.code],
            reason="tenant need",
        )
        self.assertEqual(own_role.organization, self.organization)
        with self.assertRaises(PermissionDenied):
            create_organization_role(
                actor=tenant_admin,
                organization=self.other_organization,
                code="cross-tenant-role",
                name="Cross Tenant",
                description="denied",
                permissions=[self.permission.code],
                reason="must fail",
            )
        with self.assertRaises(PermissionDenied):
            update_organization_role(
                actor=tenant_admin,
                role_id=OrganizationRole.objects.get(
                    code=MembershipRole.TENANT_ADMIN, organization__isnull=True
                ).pk,
                name="Forbidden",
                description="denied",
                permissions=[self.permission.code],
                reason="must fail",
            )

    def test_only_active_catalog_permissions_can_be_bound(self) -> None:
        self.permission.is_active = False
        self.permission.save(update_fields=["is_active", "updated_at"])
        with self.assertRaises(ValidationError):
            create_organization_role(
                actor=self.platform_admin,
                organization=None,
                code="inactive-permission-role",
                name="Invalid",
                description="invalid",
                permissions=[self.permission.code],
                reason="must fail",
            )

    def test_tenant_specific_role_cannot_be_assigned_across_tenants(self) -> None:
        other_role = create_organization_role(
            actor=self.platform_admin,
            organization=self.other_organization,
            code="other-tenant-role",
            name="Other Tenant Role",
            description="cross-tenant fixture",
            permissions=[self.permission.code],
            reason="cross-tenant test fixture",
        )
        with self.assertRaises(PermissionDenied):
            create_organization_account(
                organization=self.organization,
                actor=self.owner,
                username="cross-tenant-role-target",
                temporary_password="Strong-Test-Pass-938!",
                role=other_role,
            )

    def test_archival_preserves_assignment_history_and_disables_effective_role(
        self,
    ) -> None:
        role = create_organization_role(
            actor=self.platform_admin,
            organization=self.organization,
            code="archivable-role",
            name="Archivable",
            description="history",
            permissions=[self.permission.code],
            reason="create history fixture",
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=User.objects.create_user(username="catalog-assignee", password="x"),
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        assignment = MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="historical assignment",
        )
        archive_organization_role(
            actor=self.platform_admin, role_id=role.pk, reason="retired role"
        )
        assignment.refresh_from_db()
        self.assertEqual(assignment.role, role)
        self.assertFalse(
            has_business_permission(
                user=membership.user,
                organization=self.organization,
                permission=self.permission.code,
            )
        )

    def test_role_catalog_routes_enforce_platform_and_tenant_boundaries(self) -> None:
        tenant_admin = self._tenant_admin()
        self.client.force_login(tenant_admin)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.post(
            reverse("organizations:role_catalog"),
            {
                "action": "save",
                "code": "ui-tenant-role",
                "name": "نقش کارگاه",
                "description": "نقش آزمایشی",
                "permissions": [str(self.permission.pk)],
                "reason": "نیاز Tenant",
            },
        )
        self.assertRedirects(response, reverse("organizations:role_catalog"))
        self.assertTrue(
            OrganizationRole.objects.filter(
                organization=self.organization, code="ui-tenant-role"
            ).exists()
        )
        self.assertEqual(
            self.client.get(reverse("organizations:platform_role_catalog")).status_code,
            403,
        )
        self.client.force_login(self.platform_admin)
        self.assertEqual(
            self.client.get(reverse("organizations:platform_role_catalog")).status_code,
            200,
        )

    def test_platform_navigation_exposes_all_approved_platform_controls(self) -> None:
        self.client.force_login(self.platform_admin)
        response = self.client.get(reverse("organizations:select"))
        self.assertContains(response, "مدیریت پلتفرم")
        self.assertContains(response, "کاتالوگ نقش‌ها")
        self.assertContains(response, "عملیات حفاظت‌شده")
        self.assertEqual(
            self.client.get(
                reverse("organizations:protected_operation_catalog")
            ).status_code,
            200,
        )
        response = self.client.post(
            reverse("organizations:protected_operation_catalog"),
            {
                "action": "create",
                "code": ProtectedOperationCode.AUTHORIZATION_POLICY_WEAKEN,
                "name": "Policy protection",
                "description": "Platform-owned protection",
                "reason": "catalogue review",
            },
        )
        self.assertRedirects(
            response, reverse("organizations:protected_operation_catalog")
        )

    def test_closeout_migration_bootstraps_active_admin_idempotently(self) -> None:
        migration = import_module(
            "apps.organizations.migrations.0035_p1_1_role_catalog_closeout"
        )
        admin = User.objects.create_user(username="admin", password="x", is_active=True)
        migration.bootstrap_admin_platform_role(django_apps, None)
        migration.bootstrap_admin_platform_role(django_apps, None)
        assignment = PlatformRoleAssignment.objects.get(
            user=admin, role="platform_admin", revoked_at__isnull=True
        )
        self.assertEqual(assignment.assigned_by, admin)
        self.assertEqual(assignment.approved_by, admin)

    def test_closeout_migration_refuses_lossy_role_catalog_rollback(self) -> None:
        migration = import_module(
            "apps.organizations.migrations.0035_p1_1_role_catalog_closeout"
        )
        create_organization_role(
            actor=self.platform_admin,
            organization=self.organization,
            code="rollback-guard-role",
            name="Rollback Guard",
            description="must survive",
            permissions=[self.permission.code],
            reason="rollback guard fixture",
        )
        with self.assertRaisesRegex(RuntimeError, "Unsafe P1.1 role-catalog rollback"):
            migration.reverse_closeout(django_apps, None)
