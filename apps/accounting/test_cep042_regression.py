"""Affected legacy scenarios with explicit current-governance test authority."""

from django.utils import timezone

from apps.fixed_assets import test_p8_s24_s27 as asset_scenarios
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    OrganizationMembership,
    OrganizationRole,
)
from apps.payroll import test_p7_s29_s32_financial_handoffs as payroll_scenarios


def explicit_fixture_authority(membership, role):
    MembershipRoleAssignment.objects.get_or_create(
        organization=membership.organization,
        membership=membership,
        role=role,
        revoked_at__isnull=True,
        defaults={"reason": "CEP042 test-only explicit legacy scenario assignment"},
    )
    MembershipScopeGrant.objects.get_or_create(
        organization=membership.organization,
        membership=membership,
        scope_type=AuthorizationScopeType.ORGANIZATION,
        revoked_at__isnull=True,
        defaults={"reason": "CEP042 test-only explicit legacy scenario scope"},
    )
    OrganizationMembership.objects.filter(pk=membership.pk).update(
        authorization_migrated_at=timezone.now(), authorization_quarantined_at=None
    )


class AssetAffectedRegression(asset_scenarios.P8CostAndFixedAssetTests):
    def setUp(self):
        super().setUp()
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="cep042-asset-test-authority",
            name="Explicit legacy asset test authority",
            created_by=self.owner,
        )
        role.permissions.add(
            *BusinessPermission.objects.exclude(
                code__startswith="accounting_recognition."
            )
        )
        for actor in (self.owner, self.reviewer, self.approver):
            membership = OrganizationMembership.objects.get(
                organization=self.organization, user=actor
            )
            explicit_fixture_authority(membership, role)


class PayrollAffectedRegression(payroll_scenarios.PayrollFinancialHandoffTests):
    def setUp(self):
        super().setUp()
        for actor in (self.actor, self.reviewer):
            membership = OrganizationMembership.objects.get(
                organization=self.organization, user=actor
            )
            explicit_fixture_authority(membership, membership.role_definition)
