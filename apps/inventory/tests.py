from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.inventory.models import (
    StockTransaction,
    StockTransactionStatus,
    StockTransactionType,
    Warehouse,
)
from apps.inventory.services import (
    archive_warehouse,
    create_stock_transaction,
    create_warehouse,
    get_organization_stock_transactions,
    get_organization_warehouses,
    get_stock_balance,
    post_stock_transaction,
    reverse_stock_transaction,
)
from apps.materials.models import Material, UnitCategory, UnitOfMeasure
from apps.materials.services import archive_material
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
)
from apps.organizations.services import set_active_organization
from apps.parties.models import BusinessParty, PartyKind, PartyRole, PartyRoleType
from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
)
from apps.procurement.services import (
    issue_purchase_order,
    post_goods_receipt,
    void_goods_receipt,
)
from apps.projects.models import Project
from apps.projects.services import archive_project


class InventoryFixtureMixin:
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="inventory-owner")
        self.member = User.objects.create_user(username="inventory-member")
        self.viewer = User.objects.create_user(username="inventory-viewer")
        self.outsider = User.objects.create_user(username="inventory-outsider")
        self.organization = Organization.objects.create(
            name="Inventory Co",
            slug="inventory-co",
        )
        self.other_organization = Organization.objects.create(
            name="Other Inventory Co",
            slug="other-inventory-co",
        )
        for user, role in (
            (self.owner, MembershipRole.COMPANY_OWNER),
            (self.member, MembershipRole.MEMBER),
            (self.viewer, MembershipRole.VIEWER),
        ):
            self.organization.memberships.create(
                user=user,
                role=role,
                status=MembershipStatus.ACTIVE,
            )
        self.other_organization.memberships.create(
            user=self.outsider,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization,
            code="INV-PROJ",
            name="Inventory Project",
        )
        self.other_project = Project.objects.create(
            organization=self.other_organization,
            code="OTHER-PROJ",
            name="Other Project",
        )
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="KG",
            name="Kilogram",
            symbol="kg",
            category=UnitCategory.WEIGHT,
            decimal_places=4,
        )
        self.other_unit = UnitOfMeasure.objects.create(
            organization=self.other_organization,
            code="KG",
            name="Other Kilogram",
            symbol="kg",
            category=UnitCategory.WEIGHT,
            decimal_places=4,
        )
        self.material = Material.objects.create(
            organization=self.organization,
            code="CEMENT",
            name="Cement",
            unit_of_measure=self.unit,
        )
        self.other_material = Material.objects.create(
            organization=self.other_organization,
            code="CEMENT",
            name="Other Cement",
            unit_of_measure=self.other_unit,
        )
        self.central = create_warehouse(
            organization=self.organization,
            actor=self.owner,
            code="central",
            name="Central Warehouse",
        )
        self.site = create_warehouse(
            organization=self.organization,
            actor=self.owner,
            code="site",
            name="Site Warehouse",
            project=self.project,
        )
        self.other_warehouse = create_warehouse(
            organization=self.other_organization,
            actor=self.outsider,
            code="other",
            name="Other Warehouse",
            project=self.other_project,
        )

    def create_and_post(
        self,
        *,
        number: str,
        transaction_type: str,
        quantity: Decimal,
        source: Warehouse | None = None,
        destination: Warehouse | None = None,
        project: Project | None = None,
        goods_receipt_item: GoodsReceiptItem | None = None,
        actor: User | None = None,
    ) -> StockTransaction:
        transaction_record = create_stock_transaction(
            organization=self.organization,
            actor=actor or self.member,
            transaction_number=number,
            transaction_type=transaction_type,
            source_warehouse=source,
            destination_warehouse=destination,
            material=self.material,
            unit_of_measure=self.unit,
            project=project,
            goods_receipt_item=goods_receipt_item,
            quantity=quantity,
            occurred_at=timezone.now(),
        )
        return post_stock_transaction(
            organization=self.organization,
            actor=actor or self.member,
            stock_transaction=transaction_record,
        )

    def create_posted_goods_receipt(self) -> tuple[GoodsReceipt, GoodsReceiptItem]:
        supplier = BusinessParty.objects.create(
            organization=self.organization,
            display_name="Inventory Supplier",
            party_kind=PartyKind.COMPANY,
        )
        PartyRole.objects.create(
            organization=self.organization,
            party=supplier,
            role=PartyRoleType.SUPPLIER,
        )
        order = PurchaseOrder.objects.create(
            organization=self.organization,
            project=self.project,
            supplier=supplier,
            order_number="PO-INV-1",
            order_date=date(2026, 9, 9),
        )
        order_item = PurchaseOrderItem.objects.create(
            organization=self.organization,
            purchase_order=order,
            material=self.material,
            unit_of_measure=self.unit,
            description="Cement",
            quantity=Decimal("8.0000"),
            unit_price=Decimal("100.00"),
        )
        issue_purchase_order(
            organization=self.organization,
            actor=self.owner,
            purchase_order=order,
        )
        order.refresh_from_db()
        receipt = GoodsReceipt.objects.create(
            organization=self.organization,
            purchase_order=order,
            purchase_order_version=order.current_version,
            project=self.project,
            receipt_number="GR-INV-1",
            received_at=timezone.now(),
        )
        item = GoodsReceiptItem.objects.create(
            organization=self.organization,
            goods_receipt=receipt,
            purchase_order_item=order_item,
            material=self.material,
            unit_of_measure=self.unit,
            quantity=Decimal("8.0000"),
        )
        post_goods_receipt(
            organization=self.organization,
            actor=self.member,
            goods_receipt=receipt,
        )
        receipt.refresh_from_db()
        return receipt, item


class WarehouseServiceTests(InventoryFixtureMixin, TestCase):
    def test_management_role_and_tenant_scope_are_enforced(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_warehouse(
                organization=self.organization,
                actor=self.member,
                code="NOPE",
                name="Not Allowed",
            )
        with self.assertRaises(PermissionDenied):
            create_warehouse(
                organization=self.organization,
                actor=self.owner,
                code="CROSS",
                name="Cross Tenant",
                project=self.other_project,
            )

    def test_code_is_canonical_and_creation_is_audited(self) -> None:
        warehouse = create_warehouse(
            organization=self.organization,
            actor=self.owner,
            code="  east depot ",
            name="East Depot",
        )
        self.assertEqual(warehouse.code, "EAST DEPOT")
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.WAREHOUSE_CREATED,
                entity_id=str(warehouse.pk),
            ).exists()
        )

    def test_archive_rejects_nonzero_stock_and_preserves_history(self) -> None:
        self.create_and_post(
            number="ADJ-IN-1",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("5.0000"),
            destination=self.central,
        )
        with self.assertRaisesMessage(ValueError, "موجودی غیرصفر"):
            archive_warehouse(
                organization=self.organization,
                actor=self.owner,
                warehouse=self.central,
            )
        issue = self.create_and_post(
            number="ISSUE-ALL",
            transaction_type=StockTransactionType.ISSUE,
            quantity=Decimal("5.0000"),
            source=self.central,
            project=self.project,
        )
        archived = archive_warehouse(
            organization=self.organization,
            actor=self.owner,
            warehouse=self.central,
        )
        self.assertFalse(archived.is_active)
        self.assertTrue(StockTransaction.objects.filter(pk=issue.pk).exists())

    def test_material_archive_requires_zero_derived_stock(self) -> None:
        self.create_and_post(
            number="MAT-OPENING",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("2.0000"),
            destination=self.central,
        )
        with self.assertRaises(ValueError):
            archive_material(
                organization=self.organization,
                actor=self.owner,
                material=self.material,
            )
        self.create_and_post(
            number="MAT-ISSUE",
            transaction_type=StockTransactionType.ISSUE,
            quantity=Decimal("2.0000"),
            source=self.central,
            project=self.project,
        )
        archived_material = archive_material(
            organization=self.organization,
            actor=self.owner,
            material=self.material,
        )
        self.assertFalse(archived_material.is_active)

    def test_project_archive_requires_archived_warehouses_and_no_drafts(self) -> None:
        with self.assertRaises(ValueError):
            archive_project(
                user=self.owner,
                organization=self.organization,
                project_id=str(self.project.pk),
            )
        archive_warehouse(
            organization=self.organization,
            actor=self.owner,
            warehouse=self.site,
        )
        draft = create_stock_transaction(
            organization=self.organization,
            actor=self.member,
            transaction_number="PROJECT-DRAFT",
            transaction_type=StockTransactionType.ISSUE,
            source_warehouse=self.central,
            material=self.material,
            unit_of_measure=self.unit,
            project=self.project,
            quantity=Decimal("1.0000"),
            occurred_at=timezone.now(),
        )
        with self.assertRaises(ValueError):
            archive_project(
                user=self.owner,
                organization=self.organization,
                project_id=str(self.project.pk),
            )
        draft.delete()
        archive_project(
            user=self.owner,
            organization=self.organization,
            project_id=str(self.project.pk),
        )
        self.project.refresh_from_db()
        self.assertIsNotNone(self.project.deleted_at)


class StockTransactionModelTests(InventoryFixtureMixin, TestCase):
    def test_model_rejects_cross_tenant_and_invalid_movement_shape(self) -> None:
        transaction_record = StockTransaction(
            organization=self.organization,
            transaction_number="BAD-1",
            transaction_type=StockTransactionType.TRANSFER,
            source_warehouse=self.central,
            destination_warehouse=self.other_warehouse,
            material=self.material,
            unit_of_measure=self.unit,
            quantity=Decimal("1.0000"),
            occurred_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            transaction_record.full_clean()
        transaction_record.destination_warehouse = self.central
        with self.assertRaises(ValidationError):
            transaction_record.full_clean()

    def test_posted_details_and_all_deletion_paths_are_blocked(self) -> None:
        transaction_record = self.create_and_post(
            number="IMMUTABLE-1",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("2.0000"),
            destination=self.central,
        )
        transaction_record.quantity = Decimal("3.0000")
        with self.assertRaises(ValidationError):
            transaction_record.save()
        with self.assertRaises(ValidationError):
            transaction_record.delete()
        with self.assertRaises(ValidationError):
            StockTransaction.objects.filter(pk=transaction_record.pk).delete()


class StockTransactionServiceTests(InventoryFixtureMixin, TestCase):
    def test_draft_does_not_change_balance_and_posting_does(self) -> None:
        draft = create_stock_transaction(
            organization=self.organization,
            actor=self.member,
            transaction_number="ADJ-IN-2",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            destination_warehouse=self.central,
            material=self.material,
            unit_of_measure=self.unit,
            quantity=Decimal("4.1250"),
            occurred_at=timezone.now(),
        )
        self.assertEqual(
            get_stock_balance(
                user=self.viewer,
                organization=self.organization,
                warehouse=self.central,
                material=self.material,
            ),
            Decimal("0.0000"),
        )
        posted = post_stock_transaction(
            organization=self.organization,
            actor=self.member,
            stock_transaction=draft,
        )
        self.assertEqual(posted.status, StockTransactionStatus.POSTED)
        self.assertEqual(
            get_stock_balance(
                user=self.viewer,
                organization=self.organization,
                warehouse=self.central,
                material=self.material,
            ),
            Decimal("4.1250"),
        )

    def test_issue_and_transfer_cannot_create_negative_stock(self) -> None:
        draft = create_stock_transaction(
            organization=self.organization,
            actor=self.member,
            transaction_number="ISSUE-NEG",
            transaction_type=StockTransactionType.ISSUE,
            source_warehouse=self.central,
            material=self.material,
            unit_of_measure=self.unit,
            project=self.project,
            quantity=Decimal("1.0000"),
            occurred_at=timezone.now(),
        )
        with self.assertRaisesMessage(ValueError, "منفی شدن موجودی انبار"):
            post_stock_transaction(
                organization=self.organization,
                actor=self.member,
                stock_transaction=draft,
            )
        draft.refresh_from_db()
        self.assertEqual(draft.status, StockTransactionStatus.DRAFT)

    def test_transfer_debits_source_and_credits_destination(self) -> None:
        self.create_and_post(
            number="OPENING-1",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("10.0000"),
            destination=self.central,
        )
        self.create_and_post(
            number="TRANSFER-1",
            transaction_type=StockTransactionType.TRANSFER,
            quantity=Decimal("3.5000"),
            source=self.central,
            destination=self.site,
            project=self.project,
        )
        self.assertEqual(
            get_stock_balance(
                user=self.viewer,
                organization=self.organization,
                warehouse=self.central,
                material=self.material,
            ),
            Decimal("6.5000"),
        )
        self.assertEqual(
            get_stock_balance(
                user=self.viewer,
                organization=self.organization,
                warehouse=self.site,
                material=self.material,
            ),
            Decimal("3.5000"),
        )

    def test_reversal_adds_opposite_entry_and_preserves_original(self) -> None:
        original = self.create_and_post(
            number="ADJ-IN-REV",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("6.0000"),
            destination=self.central,
        )
        reversal = reverse_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=original,
            reversal_number="REV-1",
            reason="Posting error",
        )
        original.refresh_from_db()
        self.assertEqual(original.status, StockTransactionStatus.REVERSED)
        self.assertEqual(reversal.transaction_type, StockTransactionType.REVERSAL)
        self.assertEqual(reversal.source_warehouse, self.central)
        self.assertEqual(reversal.reversal_of, original)
        self.assertEqual(
            get_stock_balance(
                user=self.viewer,
                organization=self.organization,
                warehouse=self.central,
                material=self.material,
            ),
            Decimal("0.0000"),
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.STOCK_TRANSACTION_REVERSED,
                entity_id=str(original.pk),
            ).exists()
        )

    def test_reversal_is_blocked_when_it_would_make_stock_negative(self) -> None:
        receipt = self.create_and_post(
            number="OPENING-CONSUMED",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("5.0000"),
            destination=self.central,
        )
        self.create_and_post(
            number="ISSUE-CONSUMED",
            transaction_type=StockTransactionType.ISSUE,
            quantity=Decimal("4.0000"),
            source=self.central,
            project=self.project,
        )
        with self.assertRaisesMessage(ValueError, "منفی شدن موجودی انبار"):
            reverse_stock_transaction(
                organization=self.organization,
                actor=self.owner,
                stock_transaction=receipt,
                reversal_number="REV-CONSUMED",
                reason="Cannot remove consumed stock",
            )
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, StockTransactionStatus.POSTED)

    def test_reversal_cannot_reopen_stock_in_an_archived_warehouse(self) -> None:
        self.create_and_post(
            number="ARCHIVE-OPENING",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("5.0000"),
            destination=self.central,
        )
        issue = self.create_and_post(
            number="ARCHIVE-ISSUE",
            transaction_type=StockTransactionType.ISSUE,
            quantity=Decimal("5.0000"),
            source=self.central,
            project=self.project,
        )
        archive_warehouse(
            organization=self.organization,
            actor=self.owner,
            warehouse=self.central,
        )

        with self.assertRaisesMessage(ValueError, "انبارهای فعال همین سازمان"):
            reverse_stock_transaction(
                organization=self.organization,
                actor=self.owner,
                stock_transaction=issue,
                reversal_number="ARCHIVE-REVERSAL",
                reason="Late correction",
            )

        issue.refresh_from_db()
        self.assertEqual(issue.status, StockTransactionStatus.POSTED)

    def test_goods_receipt_can_enter_inventory_once_and_must_reverse_before_void(
        self,
    ) -> None:
        receipt, item = self.create_posted_goods_receipt()
        movement = self.create_and_post(
            number="RECEIPT-1",
            transaction_type=StockTransactionType.RECEIPT,
            quantity=item.quantity,
            destination=self.site,
            project=self.project,
            goods_receipt_item=item,
        )
        with self.assertRaises(ValueError):
            create_stock_transaction(
                organization=self.organization,
                actor=self.member,
                transaction_number="RECEIPT-DUP",
                transaction_type=StockTransactionType.RECEIPT,
                destination_warehouse=self.site,
                material=self.material,
                unit_of_measure=self.unit,
                project=self.project,
                goods_receipt_item=item,
                quantity=item.quantity,
                occurred_at=timezone.now(),
            )
        with self.assertRaisesMessage(
            ValueError, "دریافت‌های نهایی‌شده انبار را برگشت دهید"
        ):
            void_goods_receipt(
                organization=self.organization,
                actor=self.owner,
                goods_receipt=receipt,
                reason="Supplier correction",
            )
        reverse_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=movement,
            reversal_number="RECEIPT-REV-1",
            reason="Return receipt before procurement void",
        )
        voided = void_goods_receipt(
            organization=self.organization,
            actor=self.owner,
            goods_receipt=receipt,
            reason="Supplier correction",
        )
        self.assertEqual(voided.status, "void")
        self.assertEqual(
            get_stock_balance(
                user=self.viewer,
                organization=self.organization,
                warehouse=self.site,
                material=self.material,
            ),
            Decimal("0.0000"),
        )

    def test_rbac_and_read_queries_are_tenant_scoped(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_stock_transaction(
                organization=self.organization,
                actor=self.viewer,
                transaction_number="VIEWER-NO",
                transaction_type=StockTransactionType.ADJUSTMENT_IN,
                destination_warehouse=self.central,
                material=self.material,
                unit_of_measure=self.unit,
                quantity=Decimal("1.0000"),
                occurred_at=timezone.now(),
            )
        self.assertEqual(
            list(
                get_organization_warehouses(
                    user=self.viewer,
                    organization=self.organization,
                )
            ),
            [self.central, self.site],
        )
        self.assertEqual(
            get_organization_stock_transactions(
                user=self.viewer,
                organization=self.organization,
            ).count(),
            0,
        )
        with self.assertRaises(PermissionDenied):
            get_organization_warehouses(
                user=self.outsider,
                organization=self.organization,
            )
        with self.assertRaises(PermissionDenied):
            get_stock_balance(
                user=self.viewer,
                organization=self.organization,
                warehouse=self.other_warehouse,
                material=self.material,
            )


class InventoryAdminTests(TestCase):
    def test_inventory_models_are_registered_read_only(self) -> None:
        for model in (Warehouse, StockTransaction):
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(None))
            self.assertFalse(model_admin.has_change_permission(None))
            self.assertFalse(model_admin.has_delete_permission(None))


class InventoryPanelTests(InventoryFixtureMixin, TestCase):
    def test_owner_can_open_scoped_warehouse_pages(self) -> None:
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

        self.assertEqual(
            self.client.get(reverse("inventory:warehouse_list")).status_code, 200
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "inventory:warehouse_detail",
                    kwargs={"warehouse_id": self.central.pk},
                )
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "inventory:warehouse_detail",
                    kwargs={"warehouse_id": self.other_warehouse.pk},
                )
            ).status_code,
            404,
        )

    def test_transaction_list_links_to_scoped_transaction_detail(self) -> None:
        transaction_record = self.create_and_post(
            number="INV-PANEL-001",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("12.5000"),
            destination=self.central,
        )
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

        list_response = self.client.get(reverse("inventory:transaction_list"))
        detail_response = self.client.get(
            reverse(
                "inventory:transaction_detail",
                kwargs={"transaction_id": transaction_record.pk},
            )
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(
            list_response,
            reverse(
                "inventory:transaction_detail",
                kwargs={"transaction_id": transaction_record.pk},
            ),
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, transaction_record.transaction_number)

    def test_transaction_detail_rejects_cross_tenant_uuid(self) -> None:
        other_transaction = StockTransaction.objects.create(
            organization=self.other_organization,
            transaction_number="OTHER-INV-001",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            destination_warehouse=self.other_warehouse,
            material=self.other_material,
            unit_of_measure=self.other_unit,
            quantity=Decimal("2.0000"),
            occurred_at=timezone.now(),
            project=self.other_project,
        )
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

        response = self.client.get(
            reverse(
                "inventory:transaction_detail",
                kwargs={"transaction_id": other_transaction.pk},
            )
        )

        self.assertEqual(response.status_code, 404)
