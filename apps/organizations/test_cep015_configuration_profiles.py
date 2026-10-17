"""CEP-015 profile suggestions and explicit per-key policy application."""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.configuration_profiles import (
    MATRIX_VERSION,
    apply_profile_suggestion,
    preview_configuration_profile,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationMembership,
    OrganizationRole,
    PolicySourceBasis,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_services import (
    create_platform_policy,
    create_platform_policy_version,
    publish_platform_policy_version,
)
from apps.organizations.policy_specs import PROJECT_BUDGET_RESPONSE_POLICY_CODE
from apps.organizations.services import create_organization_with_owner


class ConfigurationProfileTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="profile-owner", password="x")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="Profile Tenant", slug="profile-tenant"
        )
        self.admin = User.objects.create_user(username="profile-admin", password="x")
        role = OrganizationRole.objects.get(
            code=MembershipRole.TENANT_ADMIN, organization__isnull=True
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.admin,
            role=MembershipRole.TENANT_ADMIN,
            role_definition=role,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Configuration profile test role",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Configuration profile test scope",
        )

    def _publish_response(self, value: str = "WARNING") -> None:
        root = User.objects.create_superuser(
            username="profile-root", password="x", email="root@example.test"
        )
        approver = User.objects.create_superuser(
            username="profile-approver",
            password="x",
            email="approver@example.test",
        )
        platform_admin = User.objects.create_user(
            username="profile-platform", password="x"
        )
        assign_platform_admin(
            actor=root,
            approver=approver,
            target=platform_admin,
            reason="Configuration profile policy fixture",
        )
        policy = create_platform_policy(
            actor=platform_admin,
            code=PROJECT_BUDGET_RESPONSE_POLICY_CODE,
            reason="Product Decision-02 budget response contract",
        )
        draft = create_platform_policy_version(
            actor=platform_admin,
            policy=policy,
            version=1,
            parameters={"response": value},
            effective_from=timezone.localdate(),
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            reason="Published budget response fixture",
        )
        publish_platform_policy_version(
            actor=platform_admin,
            policy_version=draft,
            reason="Publish budget response fixture",
        )

    def test_preview_is_inert_and_exact_for_all_profiles(self) -> None:
        for profile in ("Small", "Standard", "Enterprise"):
            suggestions = preview_configuration_profile(profile)
            self.assertEqual(
                [(item.key, item.value) for item in suggestions],
                [
                    ("project_controls.budget_overrun.response", "WARNING"),
                    ("project_controls.budget_overrun.override_enabled", False),
                    ("leave.accrual_preset", "POLICY_DEFINED"),
                ],
            )
        self.assertFalse(TenantPolicySelection.objects.exists())

    def test_invalid_and_policy_absent_input_fails_closed(self) -> None:
        with self.assertRaises(ValidationError):
            preview_configuration_profile("Unknown")
        for key in (
            "project_controls.budget_overrun.response",
            "leave.accrual_preset",
            "unknown.key",
        ):
            with self.assertRaises(ValidationError):
                apply_profile_suggestion(
                    organization=self.organization,
                    actor=self.admin,
                    profile="Small",
                    key=key,
                    reason="Explicit tenant choice",
                )
        self.assertFalse(TenantPolicySelection.objects.exists())

    def test_explicit_application_is_versioned_and_audited(self) -> None:
        self._publish_response()
        key = "project_controls.budget_overrun.response"
        first = apply_profile_suggestion(
            organization=self.organization,
            actor=self.admin,
            profile="Standard",
            key=key,
            reason="Approved tenant configuration",
        )
        self.assertEqual(first.status, TenantPolicySelectionStatus.ACTIVE)
        event = AuditEvent.objects.get(
            organization=self.organization,
            action=AuditAction.TENANT_POLICY_APPLIED,
            entity_id=str(first.pk),
        )
        profile_audit = event.metadata["configuration_profile"]
        self.assertEqual(profile_audit["matrix_version"], MATRIX_VERSION)
        self.assertEqual(profile_audit["old_value"], None)
        self.assertEqual(profile_audit["new_value"], "WARNING")
        self.assertEqual(profile_audit["actor_id"], str(self.admin.pk))
        self.assertEqual(profile_audit["effective_time"], first.applied_at.isoformat())

        second = apply_profile_suggestion(
            organization=self.organization,
            actor=self.admin,
            profile="Enterprise",
            key=key,
            reason="Reaffirm approved tenant configuration",
        )
        first.refresh_from_db()
        self.assertEqual(first.status, TenantPolicySelectionStatus.SUPERSEDED)
        self.assertEqual(second.supersedes_id, first.pk)
        second_event = AuditEvent.objects.get(
            organization=self.organization,
            action=AuditAction.TENANT_POLICY_APPLIED,
            entity_id=str(second.pk),
        )
        self.assertEqual(
            second_event.metadata["configuration_profile"]["old_value"], "WARNING"
        )

    def test_preview_ui_never_applies_policy(self) -> None:
        self.client.force_login(self.admin)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("organizations:configuration_profiles"), {"profile": "Small"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "project_controls.budget_overrun.response")
        self.assertFalse(TenantPolicySelection.objects.exists())
