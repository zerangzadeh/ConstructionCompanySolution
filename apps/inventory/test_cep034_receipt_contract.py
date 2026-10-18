"""INT-R04 equivalent retries, retained evidence and independent reversals."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from datetime import timezone as datetime_timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from apps.audit.models import AuditAction, AuditEvent
from apps.inventory import tests as inventory_tests
from apps.inventory.models import StockTransaction
from apps.inventory.receipt_contract import (
    fingerprint,
    reconcile_goods_receipt_inventory,
)
from apps.inventory.services import (
    create_stock_transaction,
    create_warehouse,
    get_stock_balance,
    post_stock_transaction,
    reverse_stock_transaction,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationRole,
)
from apps.procurement.models import GoodsReceipt, GoodsReceiptItem
from apps.procurement.services import void_goods_receipt
from apps.procurement.tests import ProcurementFixtureMixin


class ReceiptContractFixture(ProcurementFixtureMixin):
    create_posted_goods_receipt = (
        inventory_tests.InventoryFixtureMixin.create_posted_goods_receipt
    )
    create_and_post = inventory_tests.InventoryFixtureMixin.create_and_post

    def setUp(self):
        super().setUp()
        for organization, user in (
            (self.organization, self.owner),
            (self.organization, self.member),
            (self.organization, self.viewer),
            (self.other_organization, self.outsider),
        ):
            membership = organization.memberships.get(user=user)
            role = OrganizationRole.objects.create(
                code=f"cep034-{user.pk}", name="Explicit isolated test grants"
            )
            permissions = BusinessPermission.objects.filter(is_active=True)
            if user == self.viewer:
                permissions = permissions.filter(code__endswith=".view")
            role.permissions.set(permissions)
            membership.role_definition = role
            membership.save(update_fields=["role_definition"])
            MembershipScopeGrant.objects.create(
                organization=organization,
                membership=membership,
                scope_type=AuthorizationScopeType.ORGANIZATION,
                reason="CEP034 isolated fixture",
            )
        self.central = create_warehouse(
            organization=self.organization,
            actor=self.owner,
            code="central",
            name="Main",
        )
        self.site = create_warehouse(
            organization=self.organization,
            actor=self.owner,
            code="site",
            name="Site",
            project=self.project,
        )
        self.other_warehouse = create_warehouse(
            organization=self.other_organization,
            actor=self.outsider,
            code="other",
            name="Other site",
            project=self.other_project,
        )


class ReceiptFingerprintTests(SimpleTestCase):
    def test_numeric_timezone_and_key_order_equivalence(self):
        now = datetime(2026, 10, 18, tzinfo=UTC)
        self.assertEqual(
            fingerprint({"q": Decimal("8.0000"), "at": now}),
            fingerprint(
                {
                    "at": now.astimezone(datetime_timezone(timedelta(hours=3.5))),
                    "q": Decimal(8),
                }
            ),
        )
        self.assertNotEqual(
            fingerprint({"q": Decimal(8)}), fingerprint({"q": Decimal(9)})
        )


class ReceiptContractTests(ReceiptContractFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.receipt, self.item = self.create_posted_goods_receipt()
        self.arguments = {
            "organization": self.organization,
            "actor": self.owner,
            "transaction_number": "R034",
            "transaction_type": "receipt",
            "material": self.material,
            "unit_of_measure": self.unit,
            "quantity": self.item.quantity,
            "occurred_at": self.receipt.received_at,
            "destination_warehouse": self.site,
            "project": self.project,
            "goods_receipt_item": self.item,
        }

    def accept(self, **changes):
        return create_stock_transaction(**(self.arguments | changes))

    def reconcile(self):
        return reconcile_goods_receipt_inventory(
            organization=self.organization, actor=self.owner, receipt=self.receipt
        )

    def test_equivalent_retry_in_draft_and_posted_state_has_one_target(self):
        target = self.accept()
        self.assertEqual(self.accept(transaction_number=" r034 ").pk, target.pk)
        self.assertEqual(StockTransaction.objects.count(), 1)
        self.assertEqual(self.receipt.status, "posted")
        self.assertEqual(
            get_stock_balance(
                user=self.owner,
                organization=self.organization,
                warehouse=self.site,
                material=self.material,
            ),
            0,
        )
        post_stock_transaction(
            organization=self.organization, actor=self.owner, stock_transaction=target
        )
        self.assertEqual(self.accept().status, "posted")
        self.assertEqual(StockTransaction.objects.count(), 1)
        retained = self.reconcile()["items"][0]["targets"][0]["retained_contract"]
        self.assertEqual(retained["source"]["receipt_item_id"], str(self.item.pk))
        self.assertEqual(
            retained["source"]["purchase_order_version_id"],
            str(self.receipt.purchase_order_version_id),
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.STOCK_TRANSACTION_CREATED
            ).count(),
            1,
        )

    def test_changed_payload_and_changed_source_fail_closed(self):
        original = self.accept()
        for changes in (
            {"destination_warehouse": self.central},
            {"occurred_at": self.receipt.received_at + timedelta(seconds=1)},
            {"transaction_number": "OTHER034"},
            {"quantity": Decimal(9)},
            {"notes": "changed"},
        ):
            with self.assertRaises((ValueError, ValidationError)):
                self.accept(**changes)
        GoodsReceiptItem.objects.filter(pk=self.item.pk).update(quantity=Decimal(9))
        with self.assertRaises(ValueError):
            self.accept(quantity=Decimal(9))
        self.assertEqual(StockTransaction.objects.get().pk, original.pk)

    def test_failure_rolls_back_target_and_retry_revalidates_source(self):
        source_before = GoodsReceipt.objects.filter(pk=self.receipt.pk).values().get()
        original_audit = __import__(
            "apps.inventory.services", fromlist=["record_audit_event"]
        ).record_audit_event

        def fail_created(**kwargs):
            if kwargs["action"] == AuditAction.STOCK_TRANSACTION_CREATED:
                raise IntegrityError("injected after target insert")
            return original_audit(**kwargs)

        with (
            patch(
                "apps.inventory.services.record_audit_event", side_effect=fail_created
            ),
            self.assertRaises(IntegrityError),
        ):
            self.accept()
        self.assertFalse(StockTransaction.objects.exists())
        self.assertEqual(
            GoodsReceipt.objects.filter(pk=self.receipt.pk).values().get(),
            source_before,
        )
        self.assertTrue(
            AuditEvent.objects.filter(action=AuditAction.STOCK_RECEIPT_FAILED).exists()
        )
        GoodsReceipt.objects.filter(pk=self.receipt.pk).update(status="void")
        with self.assertRaises(ValueError):
            self.accept()
        GoodsReceipt.objects.filter(pk=self.receipt.pk).update(status="posted")
        self.assertEqual(self.accept().goods_receipt_item_id, self.item.pk)

    def test_replay_rechecks_permission_scope_tenant_and_related_state(self):
        self.accept()
        with self.assertRaises(PermissionDenied):
            self.accept(organization=self.other_organization, actor=self.outsider)
        with self.assertRaises(PermissionDenied):
            self.accept(actor=self.viewer)
        self.material.is_active = False
        self.material.save()
        with self.assertRaises((ValueError, ValidationError, PermissionDenied)):
            self.accept()
        self.material.is_active = True
        self.material.save()
        MembershipScopeGrant.objects.filter(membership__user=self.owner).delete()
        with self.assertRaises(PermissionDenied):
            self.accept()
        self.assertEqual(StockTransaction.objects.count(), 1)

    def test_retry_rejects_changed_draft_and_suspended_tenant(self):
        target = self.accept()
        StockTransaction.objects.filter(pk=target.pk).update(notes="changed draft")
        with self.assertRaises(ValueError):
            self.accept()
        self.assertFalse(
            self.reconcile()["items"][0]["targets"][0]["target_payload_matches"]
        )
        StockTransaction.objects.filter(pk=target.pk).update(notes="")
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            self.accept()
        self.assertEqual(StockTransaction.objects.count(), 1)

    def test_legacy_target_without_retained_evidence_is_not_retroactively_attested(
        self,
    ):
        # A legacy record is created through the existing model path with no INT-R04 audit.
        StockTransaction.objects.create(
            **{k: v for k, v in self.arguments.items() if k != "actor"},
            created_by=self.owner,
        )
        with self.assertRaises(ValueError):
            self.accept()
        self.assertEqual(StockTransaction.objects.count(), 1)
        self.assertIsNone(
            self.reconcile()["items"][0]["targets"][0]["retained_contract"]
        )

    def test_reversed_occurrence_does_not_reactivate_and_reconciles_lineage(self):
        target = self.accept()
        post_stock_transaction(
            organization=self.organization, actor=self.owner, stock_transaction=target
        )
        reverse = reverse_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=target,
            reversal_number="REV034",
            reason="Explicit Inventory correction",
        )
        self.assertEqual(self.accept().status, "reversed")
        self.assertEqual(StockTransaction.objects.count(), 2)
        trace = self.reconcile()
        row = trace["items"][0]["targets"][0]
        self.assertEqual(row["reversal_id"], str(reverse.pk))
        self.assertTrue(row["target_payload_matches"])
        self.assertEqual(
            get_stock_balance(
                user=self.owner,
                organization=self.organization,
                warehouse=self.site,
                material=self.material,
            ),
            0,
        )
        if path := os.environ.get("CEP034_TRACE_PATH"):
            Path(path).write_text(json.dumps(trace, indent=2), encoding="utf-8")
        void_goods_receipt(
            organization=self.organization,
            actor=self.owner,
            goods_receipt=self.receipt,
            reason="Source correction after stock reversal",
        )
        self.assertEqual(self.reconcile()["source_status"], "void")
        with self.assertRaises(ValueError):
            self.accept()


class ReceiptContractConcurrencyTests(ReceiptContractFixture, TransactionTestCase):
    def test_concurrent_equivalent_acceptance_retains_one_target(self):
        receipt, item = self.create_posted_goods_receipt()
        barrier = Barrier(2)

        def accept(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return create_stock_transaction(
                    organization=self.organization,
                    actor=self.owner,
                    transaction_number="RACE034",
                    transaction_type="receipt",
                    material=self.material,
                    unit_of_measure=self.unit,
                    quantity=item.quantity,
                    occurred_at=receipt.received_at,
                    destination_warehouse=self.site,
                    project=self.project,
                    goods_receipt_item=item,
                ).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, (1, 2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(StockTransaction.objects.count(), 1)


class ReceiptAffectedRegression(ReceiptContractFixture, TestCase):
    # Reuse existing affected assertions with explicit current-authority fixture only.
    test_goods_receipt = inventory_tests.StockTransactionServiceTests.test_goods_receipt_can_enter_inventory_once_and_must_reverse_before_void
    test_draft_posting = inventory_tests.StockTransactionServiceTests.test_draft_does_not_change_balance_and_posting_does
    test_reversal = inventory_tests.StockTransactionServiceTests.test_reversal_adds_opposite_entry_and_preserves_original
