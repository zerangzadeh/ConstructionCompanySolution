from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
    OrganizationStatus,
    PolicyCategory,
    PolicySensitivity,
    PolicyVersionStatus,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_services import (
    apply_tenant_policy_selection,
    approve_tenant_policy_selection,
    create_platform_policy,
    create_platform_policy_version,
    list_tenant_policy_selections,
    publish_platform_policy_version,
    record_policy_source,
    resolve_active_tenant_policy,
)
from apps.organizations.services import create_organization_with_owner


class P1S15PolicyLocalizationTests(TestCase):
    def setUp(self) -> None:
        self.root = User.objects.create_superuser(
            username="p1s15-root", password="x", email="root@example.test"
        )
        self.approver = User.objects.create_superuser(
            username="p1s15-approver", password="x", email="approver@example.test"
        )
        self.platform_admin = User.objects.create_user(
            username="p1s15-platform", password="x"
        )
        assign_platform_admin(
            actor=self.root,
            approver=self.approver,
            target=self.platform_admin,
            reason="P1-S15 test authority",
        )
        self.owner = User.objects.create_user(username="p1s15-owner", password="x")
        self.organization = create_organization_with_owner(
            owner=self.owner,
            name="P1-S15 Tenant",
            slug="p1-s15-tenant",
        )
        self.tenant_admin = self._membership_with_role(
            organization=self.organization,
            username="p1s15-admin",
            role_code=MembershipRole.TENANT_ADMIN,
        )
        self.other_owner = User.objects.create_user(
            username="p1s15-other-owner", password="x"
        )
        self.other_organization = create_organization_with_owner(
            owner=self.other_owner,
            name="Other P1-S15 Tenant",
            slug="other-p1-s15-tenant",
        )
        self.other_admin = self._membership_with_role(
            organization=self.other_organization,
            username="p1s15-other-admin",
            role_code=MembershipRole.TENANT_ADMIN,
        )

    def _membership_with_role(
        self, *, organization, username: str, role_code: str
    ) -> User:
        user = User.objects.create_user(username=username, password="x")
        role = OrganizationRole.objects.get(code=role_code, organization__isnull=True)
        membership = OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=role_code,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=organization,
            membership=membership,
            role=role,
            reason="P1-S15 test role",
        )
        MembershipScopeGrant.objects.create(
            organization=organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="P1-S15 test scope",
        )
        return user

    def _published_operational_version(self):
        policy = create_platform_policy(
            actor=self.platform_admin,
            code="display-calendar-policy",
            name="Display calendar options",
            category=PolicyCategory.DISPLAY_CALENDAR,
            sensitivity=PolicySensitivity.OPERATIONAL,
        )
        version = create_platform_policy_version(
            actor=self.platform_admin,
            policy=policy,
            version=1,
            parameters={"allowed_value": "jalali"},
            effective_from=timezone.localdate() - timedelta(days=1),
            reason="Accepted product display boundary",
        )
        return publish_platform_policy_version(
            actor=self.platform_admin, policy_version=version
        )

    def test_platform_admin_owns_catalog_and_external_source_is_metadata(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_platform_policy(
                actor=self.owner,
                code="forbidden-policy",
                name="Forbidden",
                category=PolicyCategory.OTHER,
                sensitivity=PolicySensitivity.OPERATIONAL,
            )
        source = record_policy_source(
            actor=self.platform_admin,
            issuer="Supplied external issuer",
            title="Supplied source title",
            source_identifier="SRC-TEST-1",
            version="v1",
            applicability="Test-only provenance; no legal assertion.",
        )
        self.assertEqual(source.created_by, self.platform_admin)
        self.assertFalse(User.objects.filter(username=source.issuer).exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.POLICY_SOURCE_RECORDED,
                entity_id=str(source.pk),
            ).exists()
        )

    def test_policy_with_explicit_source_requirement_fails_closed_without_source(
        self,
    ) -> None:
        policy = create_platform_policy(
            actor=self.platform_admin,
            code="regulated-placeholder",
            name="Regulated placeholder",
            category=PolicyCategory.REGULATORY_RULE_SET,
            sensitivity=PolicySensitivity.REGULATORY,
            requires_source_provenance=True,
        )
        version = create_platform_policy_version(
            actor=self.platform_admin,
            policy=policy,
            version=1,
            parameters={"enabled": False},
            effective_from=timezone.localdate(),
            reason="No regulatory facts activated",
        )
        with self.assertRaisesMessage(ValidationError, "سیاست دارای الزام منبع"):
            publish_platform_policy_version(
                actor=self.platform_admin, policy_version=version
            )
        version.refresh_from_db()
        self.assertEqual(version.status, PolicyVersionStatus.DRAFT)
        self.assertFalse(version.review_evidence.exists())
        source = record_policy_source(
            actor=self.platform_admin,
            issuer="Test-only issuer",
            title="Test-only source",
            source_identifier="SRC-SENSITIVE-TEST",
            version="v1",
            applicability="Test provenance only; no legal assertion.",
        )
        version.sources.add(source)
        published = publish_platform_policy_version(
            actor=self.platform_admin, policy_version=version
        )
        self.assertEqual(published.status, PolicyVersionStatus.PUBLISHED)
        self.assertFalse(published.review_evidence.exists())

        tenant_entered_policy = create_platform_policy(
            actor=self.platform_admin,
            code="regulated-source-optional",
            name="Regulated parameter with optional provenance",
            category=PolicyCategory.REGULATORY_RULE_SET,
            sensitivity=PolicySensitivity.REGULATORY,
            requires_source_provenance=False,
        )
        tenant_entered_version = create_platform_policy_version(
            actor=self.platform_admin,
            policy=tenant_entered_policy,
            version=1,
            parameters={"enabled": False},
            effective_from=timezone.localdate(),
            reason="Structure only; no regulated value asserted",
        )
        self.assertEqual(
            publish_platform_policy_version(
                actor=self.platform_admin, policy_version=tenant_entered_version
            ).status,
            PolicyVersionStatus.PUBLISHED,
        )

    def test_permission_catalog_preserves_owner_approval_admin_application(
        self,
    ) -> None:
        owner_role = OrganizationRole.objects.get(
            code=MembershipRole.TENANT_OWNER, organization__isnull=True
        )
        admin_role = OrganizationRole.objects.get(
            code=MembershipRole.TENANT_ADMIN, organization__isnull=True
        )
        manager_role = OrganizationRole.objects.get(
            code=MembershipRole.TENANT_MANAGER, organization__isnull=True
        )
        self.assertTrue(
            owner_role.permissions.filter(
                code=BusinessPermissionCode.TENANT_POLICIES_APPROVE
            ).exists()
        )
        self.assertFalse(
            admin_role.permissions.filter(
                code=BusinessPermissionCode.TENANT_POLICIES_APPROVE
            ).exists()
        )
        self.assertTrue(
            admin_role.permissions.filter(
                code=BusinessPermissionCode.TENANT_POLICIES_APPLY
            ).exists()
        )
        self.assertTrue(
            manager_role.permissions.filter(
                code=BusinessPermissionCode.TENANT_POLICIES_VIEW
            ).exists()
        )
        self.assertFalse(
            manager_role.permissions.filter(
                code=BusinessPermissionCode.TENANT_POLICIES_APPLY
            ).exists()
        )

    def test_float_and_executable_policy_parameters_are_rejected(self) -> None:
        policy = create_platform_policy(
            actor=self.platform_admin,
            code="precision-placeholder",
            name="Precision placeholder",
            category=PolicyCategory.PRECISION,
            sensitivity=PolicySensitivity.ACCOUNTING,
        )
        with self.assertRaises(ValidationError):
            create_platform_policy_version(
                actor=self.platform_admin,
                policy=policy,
                version=1,
                parameters={"scale": 2.5},
                effective_from=timezone.localdate(),
                reason="Rejected imprecise value",
            )
        with self.assertRaises(ValidationError):
            create_platform_policy_version(
                actor=self.platform_admin,
                policy=policy,
                version=1,
                parameters={"script": "return arbitrary_value"},
                effective_from=timezone.localdate(),
                reason="Rejected executable input",
            )

    def test_owner_approves_admin_applies_and_resolution_is_audited(self) -> None:
        version = self._published_operational_version()
        selection = approve_tenant_policy_selection(
            organization=self.organization,
            actor=self.owner,
            policy_version=version,
            reason="Owner selected an allowed platform option",
        )
        with self.assertRaises(PermissionDenied):
            apply_tenant_policy_selection(
                organization=self.organization,
                actor=self.owner,
                selection=selection,
            )
        applied = apply_tenant_policy_selection(
            organization=self.organization,
            actor=self.tenant_admin,
            selection=selection,
        )
        self.assertEqual(applied.status, TenantPolicySelectionStatus.ACTIVE)
        self.assertEqual(
            list(
                list_tenant_policy_selections(
                    organization=self.organization, actor=self.tenant_admin
                )
            ),
            [applied],
        )
        with self.assertRaises(PermissionDenied):
            list_tenant_policy_selections(
                organization=self.organization, actor=self.other_admin
            )
        self.assertEqual(
            resolve_active_tenant_policy(
                organization=self.organization,
                policy_code=version.policy.code,
            ),
            version,
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.TENANT_POLICY_APPROVED,
                entity_id=str(selection.pk),
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.TENANT_POLICY_APPLIED,
                entity_id=str(selection.pk),
            ).exists()
        )

    def test_cross_tenant_and_inactive_tenant_application_are_denied(self) -> None:
        version = self._published_operational_version()
        selection = approve_tenant_policy_selection(
            organization=self.organization,
            actor=self.owner,
            policy_version=version,
            reason="Tenant-owned selection",
        )
        with self.assertRaises(PermissionDenied):
            apply_tenant_policy_selection(
                organization=self.other_organization,
                actor=self.other_admin,
                selection=selection,
            )
        self.organization.status = OrganizationStatus.SUSPENDED
        self.organization.save(update_fields=["status", "updated_at"])
        with self.assertRaises(PermissionDenied):
            apply_tenant_policy_selection(
                organization=self.organization,
                actor=self.tenant_admin,
                selection=selection,
            )

    def test_missing_tenant_policy_resolution_fails_closed(self) -> None:
        with self.assertRaisesMessage(
            ValidationError, "سیاست فعال برای Tenant پیکربندی نشده است"
        ):
            resolve_active_tenant_policy(
                organization=self.organization, policy_code="missing-policy"
            )
