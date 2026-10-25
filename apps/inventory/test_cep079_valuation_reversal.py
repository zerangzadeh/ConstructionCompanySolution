from decimal import Decimal
from unittest.mock import patch

from django.db import models

from apps.inventory import tests as fixtures
from apps.inventory.models import InventoryValuationEvent, StockTransactionType
from apps.inventory.p8_services import (
    finalize_valuation,
    reverse_valuation,
    valuation_reconciliation,
)
from apps.inventory.services import reverse_stock_transaction
from apps.inventory.test_p8_s12_s17 import InventoryValuationAcceptanceTests
from tests.retirement_fixtures import explicit_fixture_roles


class ValuationReversalReconciliationTests(InventoryValuationAcceptanceTests):
    def setUp(self):
        original = fixtures.create_warehouse

        def authorized_fixture(**kwargs):
            explicit_fixture_roles(kwargs["organization"])
            return original(**kwargs)

        with patch.object(fixtures, "create_warehouse", side_effect=authorized_fixture):
            super().setUp()

    def reversed_receipt(self):
        stock = self.create_and_post(
            number="CEP079-RECON",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(1),
            destination=self.central,
            actor=self.owner,
        )
        value = finalize_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=stock,
            source_reference="Synthetic approved test cost",
            source_version="1",
            unit_cost=Decimal(7),
            idempotency_key="CEP079-value",
        )
        reversal = reverse_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=stock,
            reversal_number="CEP079-REV",
            reason="Explicit synthetic correction",
        )
        return value, reversal

    def test_valid_value_reversal_preserves_original_without_false_finding(self):
        original, stock_reversal = self.reversed_receipt()
        reversal = reverse_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=stock_reversal,
            idempotency_key="CEP079-value-reversal",
        )
        result = valuation_reconciliation(
            organization=self.organization, actor=self.owner
        )
        self.assertEqual(result["invalid_valuations"], [])
        self.assertEqual(result["invalid_reversals"], [])
        original.refresh_from_db()
        self.assertEqual(original.value_amount, Decimal(7))
        self.assertEqual(reversal.reversal_of_id, original.pk)

    def test_stock_reversal_without_value_correction_remains_a_gap(self):
        original, _ = self.reversed_receipt()
        result = valuation_reconciliation(
            organization=self.organization, actor=self.owner
        )
        self.assertIn(str(original.pk), result["invalid_valuations"])

    def test_mismatched_value_reversal_cannot_hide_a_gap(self):
        original, stock_reversal = self.reversed_receipt()
        reversal = reverse_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=stock_reversal,
            idempotency_key="CEP079-corrupt-reversal",
        )
        # Simulate corrupt persisted evidence only in this isolated test DB.
        models.QuerySet.update(
            InventoryValuationEvent.objects.filter(pk=reversal.pk),
            value_amount=Decimal(8),
        )
        result = valuation_reconciliation(
            organization=self.organization, actor=self.owner
        )
        self.assertIn(str(original.pk), result["invalid_valuations"])
        self.assertIn(str(reversal.pk), result["invalid_reversals"])
