"""Retained source scenarios with explicit current test-only authority.

No shared historical fixture, permission default or source workflow is changed.
"""

from unittest.mock import patch

from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.inventory import test_p8_s12_s17 as scenarios
from apps.organizations.models import (
    BusinessPermission,
    OrganizationMembership,
    OrganizationRole,
)


def _explicit_memberships():
    for membership in OrganizationMembership.objects.all():
        role, _ = OrganizationRole.objects.get_or_create(
            organization=membership.organization,
            code="cep047-native-regression",
            defaults={
                "name": "Explicit synthetic native regression authority",
                "created_by": membership.user,
            },
        )
        role.permissions.add(
            *BusinessPermission.objects.exclude(
                code__startswith="accounting_recognition."
            )
        )
        explicit_fixture_authority(membership, role)


class InventoryValuationRegression(scenarios.InventoryValuationAcceptanceTests):
    def setUp(self):
        original = scenarios.InventoryFixtureMixin.setUp

        def current_fixture(instance):
            from apps.inventory import tests as base

            create_warehouse = base.create_warehouse

            def authorized_warehouse(**kwargs):
                _explicit_memberships()
                return create_warehouse(**kwargs)

            with patch.object(
                base, "create_warehouse", side_effect=authorized_warehouse
            ):
                original(instance)

        with patch.object(scenarios.InventoryFixtureMixin, "setUp", current_fixture):
            super().setUp()
        _explicit_memberships()
