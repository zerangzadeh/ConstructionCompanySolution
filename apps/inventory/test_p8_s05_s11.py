from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.inventory.models import (
    InventoryCountStatus,
    InventoryReservation,
    InventoryTransferStatus,
    ReservationStatus,
    StockTraceAllocation,
    StockTransactionType,
    TraceabilityMode,
    TraceAllocationDirection,
    TransferExceptionCode,
    WarehouseBin,
)
from apps.inventory.p8_services import (
    TraceAllocationSpec,
    TransferLineSpec,
    accept_inventory_transfer,
    activate_reservation,
    add_stock_trace_allocation,
    approve_inventory_count,
    backfill_legacy_unlocated_allocations,
    create_inventory_count,
    create_inventory_lot,
    create_inventory_transfer,
    create_reservation,
    create_traceability_profile,
    create_warehouse_bin,
    dispatch_inventory_transfer,
    expire_due_reservations,
    freeze_inventory_count,
    inventory_reconciliation,
    mark_transfer_in_transit,
    post_inventory_count,
    record_counted_quantity,
    set_trace_quality_status,
    submit_inventory_count,
)
from apps.inventory.services import (
    create_stock_transaction,
    get_stock_balance,
    post_stock_transaction,
    reverse_stock_transaction,
)
from apps.inventory.tests import InventoryFixtureMixin
from apps.organizations.models import MembershipRole, MembershipStatus
from apps.organizations.services import set_active_organization
from apps.payroll.models import PayrollRun
from apps.projects.models import ProjectCostFact


class InventoryCustodyServiceTests(InventoryFixtureMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.controller = User.objects.create_user(username="inventory-controller")
        self.organization.memberships.create(
            user=self.controller,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )

    def _draft(
        self,
        *,
        number: str,
        transaction_type: str,
        quantity: str,
        source=None,
        destination=None,
        actor=None,
    ):
        return create_stock_transaction(
            organization=self.organization,
            actor=actor or self.owner,
            transaction_number=number,
            transaction_type=transaction_type,
            source_warehouse=source,
            destination_warehouse=destination,
            material=self.material,
            unit_of_measure=self.unit,
            project=(
                source.project
                if source and source.project_id
                else self.project
                if transaction_type == StockTransactionType.ISSUE
                else None
            ),
            quantity=Decimal(quantity),
            occurred_at=timezone.now(),
        )

    def test_versioned_lot_expiry_gate_and_reversal_lineage(self) -> None:
        bin_record = create_warehouse_bin(
            organization=self.organization,
            actor=self.owner,
            warehouse=self.central,
            code="A-01",
            name="A-01",
        )
        create_traceability_profile(
            organization=self.organization,
            actor=self.owner,
            material=self.material,
            mode=TraceabilityMode.LOT,
            expiry_controlled=True,
            effective_from=timezone.now() - timedelta(minutes=1),
            reason="Risk profile",
        )
        good_lot = create_inventory_lot(
            organization=self.organization,
            actor=self.owner,
            material=self.material,
            lot_code="LOT-GOOD",
            expires_on=timezone.localdate() + timedelta(days=30),
        )
        expired_lot = create_inventory_lot(
            organization=self.organization,
            actor=self.owner,
            material=self.material,
            lot_code="LOT-OLD",
            expires_on=timezone.localdate() - timedelta(days=1),
        )
        for number, lot in (("IN-GOOD", good_lot), ("IN-OLD", expired_lot)):
            movement = self._draft(
                number=number,
                transaction_type=StockTransactionType.ADJUSTMENT_IN,
                quantity="2",
                destination=self.central,
            )
            add_stock_trace_allocation(
                organization=self.organization,
                actor=self.owner,
                stock_transaction=movement,
                direction=TraceAllocationDirection.DESTINATION,
                spec=TraceAllocationSpec(Decimal(2), bin=bin_record, lot=lot),
            )
            post_stock_transaction(
                organization=self.organization,
                actor=self.owner,
                stock_transaction=movement,
            )

        expired_issue = self._draft(
            number="OUT-OLD",
            transaction_type=StockTransactionType.ISSUE,
            quantity="1",
            source=self.central,
        )
        add_stock_trace_allocation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=expired_issue,
            direction=TraceAllocationDirection.SOURCE,
            spec=TraceAllocationSpec(Decimal(1), bin=bin_record, lot=expired_lot),
        )
        with self.assertRaisesMessage(ValueError, "منقضی"):
            post_stock_transaction(
                organization=self.organization,
                actor=self.owner,
                stock_transaction=expired_issue,
            )

        issue = self._draft(
            number="OUT-GOOD",
            transaction_type=StockTransactionType.ISSUE,
            quantity="1",
            source=self.central,
        )
        add_stock_trace_allocation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=issue,
            direction=TraceAllocationDirection.SOURCE,
            spec=TraceAllocationSpec(Decimal(1), bin=bin_record, lot=good_lot),
        )
        issue = post_stock_transaction(
            organization=self.organization, actor=self.owner, stock_transaction=issue
        )
        reversal = reverse_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=issue,
            reversal_number="REV-OUT-GOOD",
            reason="Correction",
        )
        copied = reversal.trace_allocations.get()
        self.assertEqual(copied.direction, TraceAllocationDirection.DESTINATION)
        self.assertEqual(copied.lot, good_lot)
        with self.assertRaises(ValidationError):
            copied.delete()
        quarantined = set_trace_quality_status(
            organization=self.organization,
            actor=self.owner,
            trace=good_lot,
            status="quarantined",
            reason="Quality hold",
        )
        self.assertEqual(quarantined.status, "quarantined")

    def test_reservation_prevents_overallocation_and_is_tenant_scoped(self) -> None:
        self.create_and_post(
            number="OPENING-RES",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(10),
            destination=self.central,
            actor=self.owner,
        )
        first = create_reservation(
            organization=self.organization,
            actor=self.owner,
            reservation_number="RES-1",
            project=self.project,
            warehouse=self.central,
            material=self.material,
            quantity=Decimal(6),
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        first = activate_reservation(
            organization=self.organization,
            actor=self.owner,
            reservation=first,
            allocations=[TraceAllocationSpec(Decimal(6))],
        )
        self.assertEqual(first.status, ReservationStatus.ACTIVE)
        second = create_reservation(
            organization=self.organization,
            actor=self.owner,
            reservation_number="RES-2",
            project=self.project,
            warehouse=self.central,
            material=self.material,
            quantity=Decimal(5),
        )
        with self.assertRaisesMessage(ValueError, "کافی نیست"):
            activate_reservation(
                organization=self.organization,
                actor=self.owner,
                reservation=second,
                allocations=[TraceAllocationSpec(Decimal(5))],
            )
        self.assertEqual(
            expire_due_reservations(organization=self.organization, actor=self.owner),
            1,
        )
        first.refresh_from_db()
        self.assertEqual(first.status, ReservationStatus.EXPIRED)
        with self.assertRaises(PermissionDenied):
            create_reservation(
                organization=self.other_organization,
                actor=self.owner,
                reservation_number="CROSS-TENANT",
                project=self.other_project,
                warehouse=self.other_warehouse,
                material=self.other_material,
                quantity=Decimal(1),
            )

    def test_count_requires_independent_approval_and_posts_linked_adjustment(
        self,
    ) -> None:
        self.create_and_post(
            number="OPENING-COUNT",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(5),
            destination=self.central,
            actor=self.owner,
        )
        count = create_inventory_count(
            organization=self.organization,
            actor=self.owner,
            count_number="COUNT-1",
            warehouse=self.central,
        )
        count = freeze_inventory_count(
            organization=self.organization, actor=self.owner, inventory_count=count
        )
        line = count.lines.get()
        record_counted_quantity(
            organization=self.organization,
            actor=self.owner,
            line=line,
            counted_quantity=Decimal(7),
            variance_reason="Verified recount",
        )
        count = submit_inventory_count(
            organization=self.organization, actor=self.owner, inventory_count=count
        )
        with self.assertRaises(PermissionDenied):
            approve_inventory_count(
                organization=self.organization, actor=self.owner, inventory_count=count
            )
        count = approve_inventory_count(
            organization=self.organization,
            actor=self.controller,
            inventory_count=count,
        )
        count = post_inventory_count(
            organization=self.organization,
            actor=self.controller,
            inventory_count=count,
        )
        self.assertEqual(count.status, InventoryCountStatus.POSTED)
        self.assertIsNotNone(count.lines.get().adjustment_transaction_id)
        self.assertEqual(
            get_stock_balance(
                user=self.owner,
                organization=self.organization,
                warehouse=self.central,
                material=self.material,
            ),
            Decimal(7),
        )

    def test_two_sided_transfer_conserves_quantity_and_is_retry_safe(self) -> None:
        self.create_and_post(
            number="OPENING-TRANSFER",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(5),
            destination=self.central,
            actor=self.owner,
        )
        transfer = create_inventory_transfer(
            organization=self.organization,
            actor=self.owner,
            transfer_number="MOVE-1",
            source_warehouse=self.central,
            destination_warehouse=self.site,
            lines=[TransferLineSpec(self.material, Decimal(3))],
        )
        transfer = dispatch_inventory_transfer(
            organization=self.organization,
            actor=self.owner,
            inventory_transfer=transfer,
        )
        with self.assertRaises(ValueError):
            dispatch_inventory_transfer(
                organization=self.organization,
                actor=self.owner,
                inventory_transfer=transfer,
            )
        transfer = mark_transfer_in_transit(
            organization=self.organization,
            actor=self.owner,
            inventory_transfer=transfer,
        )
        with self.assertRaises(PermissionDenied):
            accept_inventory_transfer(
                organization=self.organization,
                actor=self.owner,
                inventory_transfer=transfer,
                outcomes={
                    transfer.lines.get().pk: (
                        Decimal(3),
                        TransferExceptionCode.NONE,
                        "",
                    )
                },
            )
        transfer = accept_inventory_transfer(
            organization=self.organization,
            actor=self.controller,
            inventory_transfer=transfer,
            outcomes={
                transfer.lines.get().pk: (
                    Decimal(3),
                    TransferExceptionCode.NONE,
                    "",
                )
            },
        )
        self.assertEqual(transfer.status, InventoryTransferStatus.ACCEPTED)
        self.assertEqual(
            get_stock_balance(
                user=self.owner,
                organization=self.organization,
                warehouse=self.central,
                material=self.material,
            ),
            Decimal(2),
        )
        self.assertEqual(
            get_stock_balance(
                user=self.owner,
                organization=self.organization,
                warehouse=self.site,
                material=self.material,
            ),
            Decimal(3),
        )

    def test_legacy_backfill_is_explicit_idempotent_and_has_no_downstream_effect(
        self,
    ) -> None:
        before = (
            JournalEntry.objects.count(),
            ProjectCostFact.objects.count(),
            PayrollRun.objects.count(),
        )
        self.create_and_post(
            number="LEGACY-IN",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(4),
            destination=self.central,
            actor=self.owner,
        )
        self.assertEqual(
            backfill_legacy_unlocated_allocations(
                organization=self.organization, actor=self.owner
            ),
            1,
        )
        self.assertEqual(
            backfill_legacy_unlocated_allocations(
                organization=self.organization, actor=self.owner
            ),
            0,
        )
        allocation = StockTraceAllocation.objects.get()
        self.assertTrue(allocation.is_legacy_unknown)
        self.assertTrue(allocation.bin.is_legacy_unlocated)
        self.assertEqual(
            (
                JournalEntry.objects.count(),
                ProjectCostFact.objects.count(),
                PayrollRun.objects.count(),
            ),
            before,
        )
        result = inventory_reconciliation(
            organization=self.organization, user=self.owner
        )
        self.assertEqual(result["allocation_mismatches"], [])
        self.assertEqual(result["unallocated_positions"], [])
        self.assertEqual(result["legacy_unknown_allocations"], 1)
        self.assertEqual(
            WarehouseBin.objects.filter(is_legacy_unlocated=True).count(), 1
        )
        self.assertEqual(InventoryReservation.objects.count(), 0)

    def test_persian_custody_workbench_is_tenant_scoped(self) -> None:
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()
        response = self.client.get(reverse("inventory:custody_workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "کنترل مقدار و امانت موجودی")
        self.assertNotContains(response, self.other_warehouse.name)


class InventoryCustodyConcurrencyTests(InventoryFixtureMixin, TransactionTestCase):
    serialized_rollback = True

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        for alias in cls._databases_names(include_mirrors=False):
            db_connection = connections[alias]
            serialized = getattr(db_connection, "_test_serialized_contents", None)
            if serialized:
                db_connection.creation.deserialize_db_from_string(serialized)

    def setUp(self) -> None:
        super().setUp()
        self.controller = User.objects.create_user(username="p8-controller")
        self.reviewer = User.objects.create_user(username="p8-reviewer")
        for user in (self.controller, self.reviewer):
            self.organization.memberships.create(
                user=user,
                role=MembershipRole.COMPANY_MANAGER,
                status=MembershipStatus.ACTIVE,
            )

    def test_competing_transfer_dispatch_posts_once(self) -> None:
        self.create_and_post(
            number="RACE-OPENING",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(5),
            destination=self.central,
            actor=self.owner,
        )
        transfer = create_inventory_transfer(
            organization=self.organization,
            actor=self.owner,
            transfer_number="RACE-MOVE",
            source_warehouse=self.central,
            destination_warehouse=self.site,
            lines=[TransferLineSpec(self.material, Decimal(2))],
        )
        barrier = Barrier(2)

        def dispatch(actor_id) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                dispatch_inventory_transfer(
                    organization=type(self.organization).objects.get(
                        pk=self.organization.pk
                    ),
                    actor=User.objects.get(pk=actor_id),
                    inventory_transfer=type(transfer).objects.get(pk=transfer.pk),
                )
                return "dispatched"
            except (PermissionDenied, ValidationError, ValueError):
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(dispatch, (self.owner.pk, self.controller.pk)))
        self.assertEqual(outcomes.count("dispatched"), 1)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, InventoryTransferStatus.DISPATCHED)
        self.assertEqual(transfer.lines.get().dispatch_transaction_id is not None, True)

    def test_competing_count_post_creates_one_adjustment(self) -> None:
        self.create_and_post(
            number="COUNT-RACE-OPENING",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(5),
            destination=self.central,
            actor=self.owner,
        )
        count = create_inventory_count(
            organization=self.organization,
            actor=self.owner,
            count_number="COUNT-RACE",
            warehouse=self.central,
        )
        count = freeze_inventory_count(
            organization=self.organization, actor=self.owner, inventory_count=count
        )
        record_counted_quantity(
            organization=self.organization,
            actor=self.owner,
            line=count.lines.get(),
            counted_quantity=Decimal(6),
            variance_reason="race check",
        )
        count = submit_inventory_count(
            organization=self.organization, actor=self.owner, inventory_count=count
        )
        count = approve_inventory_count(
            organization=self.organization,
            actor=self.controller,
            inventory_count=count,
        )
        barrier = Barrier(2)

        def post(actor_id) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                post_inventory_count(
                    organization=type(self.organization).objects.get(
                        pk=self.organization.pk
                    ),
                    actor=User.objects.get(pk=actor_id),
                    inventory_count=type(count).objects.get(pk=count.pk),
                )
                return "posted"
            except (PermissionDenied, ValidationError, ValueError):
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(post, (self.controller.pk, self.reviewer.pk)))
        self.assertEqual(outcomes.count("posted"), 1)
        count.refresh_from_db()
        self.assertEqual(count.status, InventoryCountStatus.POSTED)
        self.assertEqual(count.lines.exclude(adjustment_transaction=None).count(), 1)


class P8MigrationRoundTripTests(TransactionTestCase):
    serialized_rollback = True

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        for alias in cls._databases_names(include_mirrors=False):
            db_connection = connections[alias]
            serialized = getattr(db_connection, "_test_serialized_contents", None)
            if serialized:
                db_connection.creation.deserialize_db_from_string(serialized)

    def test_inventory_expansion_rolls_back_and_reapplies(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([("inventory", "0001_initial")])
        self.assertNotIn(
            "inventory_inventoryreservation", connection.introspection.table_names()
        )
        executor = MigrationExecutor(connection)
        executor.migrate(
            [("inventory", "0002_inventorycount_inventoryreservation_and_more")]
        )
        self.assertIn(
            "inventory_inventoryreservation", connection.introspection.table_names()
        )
