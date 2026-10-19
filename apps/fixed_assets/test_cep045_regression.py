"""Existing read/workspace scenarios with explicit current test authority."""

from unittest.mock import patch

from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.equipment import tests as equipment_scenarios
from apps.expenses.models import LegacyExpenseCategory, PlatformExpenseGroup
from apps.financials import tests as financial_scenarios
from apps.organizations.models import OrganizationMembership


class ExplicitLegacyFixture:
    def setUp(self):
        original_save = OrganizationMembership.save

        def assigned_save(membership, *args, **kwargs):
            result = original_save(membership, *args, **kwargs)
            explicit_fixture_authority(membership, membership.role_definition)
            return result

        with patch.object(OrganizationMembership, "save", assigned_save):
            super().setUp()


class EquipmentServiceRegression(
    ExplicitLegacyFixture, equipment_scenarios.EquipmentServiceTests
):
    pass


class EquipmentPanelRegression(
    ExplicitLegacyFixture, equipment_scenarios.EquipmentPanelTests
):
    pass


class FinancialReadRegression(
    ExplicitLegacyFixture, financial_scenarios.FinancialReportTests
):
    def setUp(self):
        super().setUp()
        PlatformExpenseGroup.objects.get_or_create(
            code=LegacyExpenseCategory.OTHER,
            defaults={"name": "Synthetic regression expense group", "is_active": True},
        )
