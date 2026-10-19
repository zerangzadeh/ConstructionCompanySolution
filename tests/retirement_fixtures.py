"""Explicit test-only role and Treasury configuration for retirement regressions."""

from datetime import date

from django.utils import timezone

from apps.accounting.models import AccountType
from apps.accounting.services import (
    create_account,
    create_fiscal_period,
    create_fiscal_year,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    OrganizationRole,
)
from apps.organizations.policy_specs import (
    ACCOUNTING_INITIAL_POLICY_PARAMETERS,
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
    ACCOUNTING_ROUNDING_POLICY_CODE,
    TREASURY_SELF_APPROVAL_POLICY_CODE,
)
from apps.treasury import tests as treasury_fixture


def explicit_fixture_roles(organization):
    """Modernize only the caller's test fixture, never production authorization."""
    for membership in organization.memberships.all():
        role = membership.role_definition or OrganizationRole.objects.get(
            organization__isnull=True, code=membership.role
        )
        MembershipRoleAssignment.objects.get_or_create(
            organization=organization,
            membership=membership,
            role=role,
            defaults={"reason": "Explicit retirement regression fixture"},
        )
        MembershipScopeGrant.objects.get_or_create(
            organization=organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            defaults={"reason": "Explicit retirement regression fixture scope"},
        )
        membership.authorization_migrated_at = timezone.now()
        membership.save(update_fields=["authorization_migrated_at", "updated_at"])


class CashFixture:
    _member = treasury_fixture.TreasuryFoundationTests._member
    _activate_policy = treasury_fixture.TreasuryFoundationTests._activate_policy
    _bank = treasury_fixture.TreasuryFoundationTests._bank
    post = treasury_fixture.TreasuryFoundationTests._post

    def __init__(self, *, organization, owner):
        self.organization, self.owner = organization, owner
        self.owner_membership = organization.memberships.get(user=owner)
        self.accountant = self._member(
            "retirement-cash-accountant", MembershipRole.ACCOUNTANT
        )
        self.accountant_membership = organization.memberships.get(user=self.accountant)
        for code in (
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
        ):
            self._activate_policy(code, ACCOUNTING_INITIAL_POLICY_PARAMETERS[code])
        self._activate_policy(
            TREASURY_SELF_APPROVAL_POLICY_CODE, {"allow_self_approval": True}
        )
        year = create_fiscal_year(
            organization=organization,
            actor=owner,
            code="RETIREMENT-TEST",
            name="Test fiscal year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            calendar_version=1,
        )
        self.period = create_fiscal_period(
            organization=organization,
            actor=owner,
            fiscal_year=year,
            number=1,
            name="Test period",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        self.cash_gl = create_account(
            organization=organization,
            actor=owner,
            code="RETIRE-CASH",
            name="Test cash",
            account_type=AccountType.ASSET,
            is_posting=True,
        )
        self.clearing_gl = create_account(
            organization=organization,
            actor=owner,
            code="RETIRE-CLEAR",
            name="Test clearing",
            account_type=AccountType.LIABILITY,
            is_posting=True,
        )
        self.bank = self._bank("RETIRE-BANK", "TEST0001234", self.cash_gl)
