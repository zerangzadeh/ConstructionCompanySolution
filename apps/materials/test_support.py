"""Authorization fixtures for Materials regression tests.

The historical tests predate explicit effective-role and scope enforcement.
These helpers make the test actor's intended tenant-owner authority explicit
without changing the authorization model under test.
"""

from apps.accounts.models import User
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)


def grant_material_test_owner(
    *, organization: Organization, user: User, code: str
) -> OrganizationMembership:
    """Give a fixture owner explicit active tenant scope and catalog permissions."""

    role = OrganizationRole.objects.create(code=code, name=code)
    role.permissions.set(BusinessPermission.objects.filter(is_active=True))
    membership = OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=MembershipRole.COMPANY_OWNER,
        role_definition=role,
        status=MembershipStatus.ACTIVE,
    )
    MembershipScopeGrant.objects.create(
        organization=organization,
        membership=membership,
        scope_type=AuthorizationScopeType.ORGANIZATION,
        reason="Materials regression fixture",
    )
    return membership
