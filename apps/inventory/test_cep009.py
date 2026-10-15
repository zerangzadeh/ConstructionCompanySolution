from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.inventory.models import (
    StockTransaction,
    StockTransactionStatus,
    StockTransactionType,
)
from apps.inventory.services import (
    _lock_warehouse_ids,
    _stock_balance_value,
    create_stock_transaction,
    get_stock_balance,
    post_stock_transaction,
)
from apps.inventory.tests import InventoryFixtureMixin
from apps.organizations.models import Organization


class InventoryBalanceQueryTests(InventoryFixtureMixin, TestCase):
    def test_warehouse_locks_follow_uuid_order_for_either_direction(self) -> None:
        with CaptureQueriesContext(connection) as captured:
            locked = _lock_warehouse_ids(
                organization=self.organization,
                warehouse_ids={self.site.pk, self.central.pk},
            )
        self.assertEqual(list(locked), sorted([self.site.pk, self.central.pk]))
        self.assertEqual(len(captured), 2)
        for query, warehouse_id in zip(captured, sorted(locked), strict=True):
            self.assertIn("FOR UPDATE", query["sql"].upper())
            self.assertIn(warehouse_id.hex, query["sql"])

    def test_single_scoped_aggregate_preserves_transfer_and_reversal_history(
        self,
    ) -> None:
        opening = self.create_and_post(
            number="CEP009-OPENING",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("10.0000"),
            destination=self.central,
        )
        # A reversed original remains in the ledger alongside its reversal.
        from apps.inventory.services import reverse_stock_transaction

        reverse_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=opening,
            reversal_number="CEP009-REVERSAL",
            reason="Query equivalence",
        )
        self.create_and_post(
            number="CEP009-SECOND-OPENING",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("10.0000"),
            destination=self.central,
        )
        self.create_and_post(
            number="CEP009-TRANSFER",
            transaction_type=StockTransactionType.TRANSFER,
            quantity=Decimal("3.0000"),
            source=self.central,
            destination=self.site,
            project=self.project,
        )
        with CaptureQueriesContext(connection) as captured:
            balance = _stock_balance_value(
                organization=self.organization,
                warehouse=self.central,
                material=self.material,
            )
        self.assertEqual(len(captured), 1)
        self.assertIn("SUM", captured[0]["sql"].upper())
        self.assertEqual(balance, Decimal("7.0000"))
        self.assertEqual(
            get_stock_balance(
                user=self.viewer,
                organization=self.organization,
                warehouse=self.site,
                material=self.material,
            ),
            Decimal("3.0000"),
        )
        self.assertEqual(
            _stock_balance_value(
                organization=self.other_organization,
                warehouse=self.central,
                material=self.material,
            ),
            Decimal("0.0000"),
        )


class InventoryTransferLockOrderTests(InventoryFixtureMixin, TransactionTestCase):
    serialized_rollback = True

    def test_opposing_transfers_post_once_without_lost_update(self) -> None:
        for number, warehouse in (
            ("CEP009-START-A", self.central),
            ("CEP009-START-B", self.site),
        ):
            self.create_and_post(
                number=number,
                transaction_type=StockTransactionType.ADJUSTMENT_IN,
                quantity=Decimal("5.0000"),
                destination=warehouse,
                project=warehouse.project,
                actor=self.owner,
            )
        barrier = Barrier(2)

        def move(number: str, source_id: object, destination_id: object) -> None:
            close_old_connections()
            try:
                organization = Organization.objects.get(pk=self.organization.pk)
                actor = User.objects.get(pk=self.owner.pk)
                source = type(self.central).objects.get(pk=source_id)
                destination = type(self.central).objects.get(pk=destination_id)
                barrier.wait(timeout=10)
                draft = create_stock_transaction(
                    organization=organization,
                    actor=actor,
                    transaction_number=number,
                    transaction_type=StockTransactionType.TRANSFER,
                    source_warehouse=source,
                    destination_warehouse=destination,
                    project=source.project or destination.project,
                    material=self.material,
                    unit_of_measure=self.unit,
                    quantity=Decimal("2.0000"),
                    occurred_at=timezone.now(),
                )
                post_stock_transaction(
                    organization=organization, actor=actor, stock_transaction=draft
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (
                pool.submit(move, "CEP009-A-B", self.central.pk, self.site.pk),
                pool.submit(move, "CEP009-B-A", self.site.pk, self.central.pk),
            )
            for future in futures:
                future.result(timeout=30)
        self.assertEqual(
            StockTransaction.objects.filter(
                organization=self.organization,
                transaction_number__in=["CEP009-A-B", "CEP009-B-A"],
                status=StockTransactionStatus.POSTED,
            ).count(),
            2,
        )
        for warehouse in (self.central, self.site):
            self.assertEqual(
                get_stock_balance(
                    user=self.viewer,
                    organization=self.organization,
                    warehouse=warehouse,
                    material=self.material,
                ),
                Decimal("5.0000"),
            )
