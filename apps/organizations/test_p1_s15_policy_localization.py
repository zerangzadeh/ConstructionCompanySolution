from datetime import timedelta
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.authorization import membership_permission_codes
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
    PlatformPolicyVersionSource,
    PolicySourceBasis,
    PolicyVersionStatus,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_services import (
    apply_tenant_policy_selection,
    create_platform_policy,
    create_platform_policy_version,
    deactivate_platform_policy,
    link_policy_version_source,
    publish_platform_policy_version,
    record_policy_source,
    resolve_active_tenant_policy,
    retire_platform_policy_version,
    select_tenant_policy_version,
)
from apps.organizations.policy_specs import (
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
    initial_accounting_policy_parameters,
    validate_policy_for_consumer,
)
from apps.organizations.services import create_organization_with_owner


class AccountingPolicyFoundationTests(TestCase):
    def setUp(self) -> None:
        self.root = User.objects.create_superuser(
            username="policy-root", password="x", email="root@example.test"
        )
        approver = User.objects.create_superuser(
            username="policy-approver", password="x", email="approver@example.test"
        )
        self.platform_admin = User.objects.create_user(username="policy-platform", password="x")
        assign_platform_admin(
            actor=self.root,
            approver=approver,
            target=self.platform_admin,
            reason="Policy foundation test authority",
        )
        self.owner = User.objects.create_user(username="policy-owner", password="x")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="Policy Tenant", slug="policy-tenant"
        )
        self.tenant_admin = self._tenant_admin("policy-admin")

    def _tenant_admin(self, username: str) -> User:
        user = User.objects.create_user(username=username, password="x")
        role = OrganizationRole.objects.get(
            code=MembershipRole.TENANT_ADMIN, organization__isnull=True
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role=MembershipRole.TENANT_ADMIN,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Policy test role",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Policy test scope",
        )
        return user

    def _activate_client(self, user: User) -> None:
        self.client.force_login(user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

    def _policy(self):
        return create_platform_policy(
            actor=self.platform_admin,
            code=ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            reason="Initialize closed accounting policy definition.",
        )

    def _published_policy_version(self, *, effective_from):
        policy = self._policy()
        draft = create_platform_policy_version(
            actor=self.platform_admin,
            policy=policy,
            version=1,
            parameters=initial_accounting_policy_parameters(
                ACCOUNTING_MONEY_PRECISION_POLICY_CODE
            ),
            effective_from=effective_from,
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            reason="Create policy version for Tenant selection tests.",
        )
        return publish_platform_policy_version(
            actor=self.platform_admin,
            policy_version=draft,
            reason="Publish policy version for Tenant selection tests.",
        )

    def test_only_closed_catalog_codes_and_exact_approved_values_are_accepted(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_platform_policy(
                actor=self.owner,
                code=ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
                reason="Forbidden",
            )
        with self.assertRaisesMessage(ValidationError, "کاتالوگ کد-محور"):
            create_platform_policy(
                actor=self.platform_admin,
                code="arbitrary-policy",
                reason="Forbidden",
            )
        policy = self._policy()
        with self.assertRaisesMessage(ValidationError, "دقیقاً با قرارداد"):
            create_platform_policy_version(
                actor=self.platform_admin,
                policy=policy,
                version=1,
                parameters={},
                effective_from=timezone.localdate(),
                source_basis=PolicySourceBasis.PRODUCT_DEFINED,
                reason="Incomplete parameters are forbidden.",
            )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PLATFORM_POLICY_CREATED, entity_id=str(policy.pk)
            ).exists()
        )

    def test_retroactive_version_is_rejected_before_any_value_validation(self) -> None:
        policy = self._policy()
        with self.assertRaisesMessage(ValidationError, "تاریخ گذشته"):
            create_platform_policy_version(
                actor=self.platform_admin,
                policy=policy,
                version=1,
                parameters={"unapproved": "value"},
                effective_from=timezone.localdate() - timedelta(days=1),
                source_basis=PolicySourceBasis.PRODUCT_DEFINED,
                reason="Retroactive policy prohibited.",
            )

    def test_accounting_consumer_requires_the_closed_policy_contract(self) -> None:
        policy = SimpleNamespace(
            code=ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            name="دقت پول حسابداری",
            category="precision",
            sensitivity="accounting",
            tenant_selectable=True,
        )
        version = SimpleNamespace(
            policy=policy,
            parameters=initial_accounting_policy_parameters(
                ACCOUNTING_MONEY_PRECISION_POLICY_CODE
            ),
        )
        with self.assertRaisesMessage(ValidationError, "کد سیاست با قرارداد"):
            validate_policy_for_consumer(
                policy_version=version,
                consumer="accounting.journal.submit",
                expected_policy_code="accounting-rounding",
            )

        unknown = SimpleNamespace(policy=SimpleNamespace(code="unknown-policy"), parameters={})
        with self.assertRaisesMessage(ValidationError, "کاتالوگ کد-محور"):
            validate_policy_for_consumer(
                policy_version=unknown, consumer="accounting.journal.submit"
            )

    def test_lifecycle_and_source_immutability_with_a_test_only_contract(self) -> None:
        # The lifecycle contract uses the actual closed Product Owner values; no
        # test-only financial values are introduced.
        policy = self._policy()
        version = create_platform_policy_version(
            actor=self.platform_admin,
            policy=policy,
            version=1,
            parameters=initial_accounting_policy_parameters(
                ACCOUNTING_MONEY_PRECISION_POLICY_CODE
            ),
            effective_from=timezone.localdate(),
            source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
            reason="Exercise lifecycle controls only.",
        )
        source = record_policy_source(
            actor=self.platform_admin,
            issuer="Test authority",
            title="Test source",
            source_identifier="POLICY-TEST-1",
            version="1",
            applicability="Test provenance only.",
            reason="Lifecycle source evidence.",
        )
        link = link_policy_version_source(
            actor=self.platform_admin,
            policy_version=version,
            source=source,
            reason="Link before publication.",
        )
        published = publish_platform_policy_version(
            actor=self.platform_admin,
            policy_version=version,
            reason="Publish lifecycle test version.",
        )
        with self.assertRaises(ValidationError):
            PlatformPolicyVersionSource.objects.create(
                policy_version=published,
                source=source,
                linked_by=self.platform_admin,
                reason="Forbidden post-publication mutation.",
            )
        selection = select_tenant_policy_version(
            organization=self.organization,
            actor=self.tenant_admin,
            policy_version=published,
            reason="Tenant selection.",
        )
        applied = apply_tenant_policy_selection(
            organization=self.organization,
            actor=self.tenant_admin,
            selection=selection,
        )
        self.assertEqual(applied.status, TenantPolicySelectionStatus.ACTIVE)
        other_owner = User.objects.create_user(username="other-policy-owner", password="x")
        other_organization = create_organization_with_owner(
            owner=other_owner,
            name="Other policy tenant",
            slug="other-policy-tenant",
        )
        with self.assertRaises(ValidationError):
            resolve_active_tenant_policy(
                organization=other_organization, policy_code=policy.code
            )
        version_id = published.pk
        retire_platform_policy_version(
            actor=self.platform_admin,
            policy_version=published,
            reason="Retire without rewriting history.",
        )
        published.refresh_from_db()
        self.assertEqual(published.pk, version_id)
        self.assertEqual(published.status, PolicyVersionStatus.RETIRED)
        with self.assertRaises(ValidationError):
            resolve_active_tenant_policy(
                organization=self.organization, policy_code=policy.code
            )
        deactivate_platform_policy(
            actor=self.platform_admin,
            policy=policy,
            reason="Deactivate policy catalogue entry.",
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PLATFORM_POLICY_SOURCE_LINKED, entity_id=str(link.pk)
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PLATFORM_POLICY_VERSION_RETIRED,
                entity_id=str(version_id),
            ).exists()
        )

    def test_policy_ui_exposes_only_safe_catalog_and_empty_tenant_state(self) -> None:
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("organizations:platform_policy_catalog")).status_code,
            403,
        )
        self.client.force_login(self.platform_admin)
        platform_page = self.client.get(reverse("organizations:platform_policy_catalog"))
        self.assertEqual(platform_page.status_code, 200)
        self.assertContains(platform_page, "ثبت تعریف")
        self.assertNotContains(platform_page, "انتشار نسخه")
        self.assertEqual(
            self.client.post(
                reverse("organizations:platform_policy_catalog"),
                {"code": ACCOUNTING_MONEY_PRECISION_POLICY_CODE},
            ).status_code,
            302,
        )
        platform_page = self.client.get(reverse("organizations:platform_policy_catalog"))
        self.assertContains(platform_page, "مقادیر فقط از نسخهٔ منتشرشده قابل اعمال‌اند.")

        self._activate_client(self.tenant_admin)
        tenant_page = self.client.get(
            reverse("organizations:tenant_policy_configuration")
        )
        self.assertEqual(tenant_page.status_code, 200)
        self.assertContains(tenant_page, "نسخه قابل انتخابی وجود ندارد.")
        self.assertNotContains(tenant_page, 'name="policy_version_id"', html=False)

    def test_tenant_policy_ui_keeps_future_version_read_only(self) -> None:
        future_version = self._published_policy_version(
            effective_from=timezone.localdate() + timedelta(days=1)
        )

        self._activate_client(self.tenant_admin)
        tenant_page = self.client.get(
            reverse("organizations:tenant_policy_configuration")
        )

        self.assertEqual(tenant_page.status_code, 200)
        self.assertNotContains(tenant_page, 'name="policy_version_id"', html=False)
        self.assertContains(tenant_page, "نسخه‌های منتشرشدهٔ آینده")
        self.assertContains(tenant_page, future_version.policy.name)
        self.assertEqual(tenant_page.context["ready_versions"], [])
        self.assertEqual(tenant_page.context["upcoming_versions"], [future_version])

    def test_tenant_admin_uses_apply_permission_not_legacy_approval_permission(self) -> None:
        published = self._published_policy_version(effective_from=timezone.localdate())
        legacy_permission = BusinessPermission.objects.get(
            code=BusinessPermissionCode.TENANT_POLICIES_APPROVE
        )
        tenant_admin_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.tenant_admin
        )
        owner_membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.owner
        )

        self.assertFalse(legacy_permission.is_active)
        self.assertIn(
            BusinessPermissionCode.TENANT_POLICIES_APPLY,
            membership_permission_codes(tenant_admin_membership),
        )
        self.assertNotIn(
            BusinessPermissionCode.TENANT_POLICIES_APPROVE,
            membership_permission_codes(tenant_admin_membership),
        )
        self.assertNotIn(
            BusinessPermissionCode.TENANT_POLICIES_APPROVE,
            membership_permission_codes(owner_membership),
        )

        selection = select_tenant_policy_version(
            organization=self.organization,
            actor=self.tenant_admin,
            policy_version=published,
            reason="Tenant Admin selects the effective version.",
        )
        self.assertEqual(selection.status, TenantPolicySelectionStatus.APPROVED)
        with self.assertRaises(PermissionDenied):
            select_tenant_policy_version(
                organization=self.organization,
                actor=self.owner,
                policy_version=published,
                reason="Tenant Owner has no separate approval route.",
            )
