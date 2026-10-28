"""Destructive contract boundaries and migration-only compatibility."""

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.apps import apps
from django.db import connection, migrations
from django.test import SimpleTestCase, TestCase, override_settings

from apps.organizations.models import BusinessPermission, BusinessPermissionCode

contract = import_module("apps.billing.migrations.0018_retire_legacy_claim_settlements")


class RetirementContractGuardTests(SimpleTestCase):
    @override_settings(SETTINGS_MODULE="config.settings.production")
    def test_production_and_remote_targets_preserve_without_population_gate(self):
        for host in ("localhost", "db", "remote.invalid"):
            with self.subTest(host=host):
                editor = SimpleNamespace(
                    connection=SimpleNamespace(
                        settings_dict={"HOST": host, "NAME": "isolated"},
                        alias="default",
                    )
                )
                historical = Mock()
                historical.get_model.return_value.objects.using.return_value.all.return_value = []
                preparation = import_module(
                    "apps.documents.migrations.0012_legacy_payment_reference_preparation"
                )
                with (
                    patch.object(preparation, "preserve_excluded_sources") as preserve,
                    patch.object(preparation, "preserve_typed_links") as links,
                    patch(
                        "pathlib.Path.read_text",
                        side_effect=AssertionError("No readiness-file gate"),
                    ),
                ):
                    contract.verify_retirement(historical, editor)
                preserve.assert_called_once_with(historical, editor)
                links.assert_called_once_with(historical, editor)

    def test_state_retirement_never_drops_original_records(self):
        payment_contract = import_module(
            "core.retired_payments.migrations.0007_retire_legacy_payment"
        )
        for module in (contract, payment_contract):
            operations = module.Migration.operations
            self.assertFalse(
                any(isinstance(op, migrations.DeleteModel) for op in operations)
            )
            retained = [
                op
                for op in operations
                if isinstance(op, migrations.SeparateDatabaseAndState)
            ]
            self.assertEqual(len(retained), 1)
            self.assertEqual(retained[0].database_operations, [])
            self.assertTrue(
                all(
                    isinstance(op, migrations.DeleteModel)
                    for op in retained[0].state_operations
                )
            )


class RetiredRuntimeContractTests(TestCase):
    def test_legacy_orm_and_permissions_absent_but_treasury_remains(self):
        tables = set(connection.introspection.table_names())
        # Retained raw tables are intentional. Earlier applied Development table
        # removal is not replayed, and removed history is never reconstructed.
        self.assertTrue(
            {
                "treasury_paymentrequest",
                "treasury_treasurymovement",
                "subledgers_settlementallocation",
                "documents_retiredpaymentevidence",
            }
            <= tables
        )
        self.assertEqual(list(apps.get_app_config("payments").get_models()), [])
        self.assertFalse(
            any(code.startswith("payments.") for code in BusinessPermissionCode.values)
        )
        self.assertFalse(
            BusinessPermission.objects.filter(code__startswith="payments.").exists()
        )
