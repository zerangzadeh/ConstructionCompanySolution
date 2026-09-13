from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.materials.models import Material, UnitCategory, UnitOfMeasure
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
    GoodsReceiptStatus,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseRequestStatus,
)
from apps.procurement.services import (
    add_goods_receipt_item,
    add_purchase_order_item,
    add_purchase_request_item,
    approve_purchase_request,
    create_goods_receipt,
    create_purchase_order,
    create_purchase_request,
    get_organization_goods_receipts,
    get_organization_purchase_orders,
    get_organization_purchase_requests,
    issue_purchase_order,
    post_goods_receipt,
    reject_purchase_request,
    submit_purchase_request,
    void_goods_receipt,
)
from apps.projects.models import Project


class ProcurementFixtureMixin:
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="procurement-owner")
        self.member = User.objects.create_user(username="procurement-member")
        self.viewer = User.objects.create_user(username="procurement-viewer")
        self.outsider = User.objects.create_user(username="procurement-outsider")
        self.organization = Organization.objects.create(
            name="Procurement Co", slug="procurement-co"
        )
        self.other_organization = Organization.objects.create(
            name="Other Procurement Co", slug="other-procurement-co"
        )
        for user, role in (
            (self.owner, MembershipRole.COMPANY_OWNER),
            (self.member, MembershipRole.MEMBER),
            (self.viewer, MembershipRole.VIEWER),
        ):
            self.organization.memberships.create(
                user=user, role=role, status=MembershipStatus.ACTIVE
            )
        self.other_organization.memberships.create(
            user=self.outsider,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization, code="PROC", name="Procurement Project"
        )
        self.other_project = Project.objects.create(
            organization=self.other_organization,
            code="OTHER",
            name="Other Project",
        )
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="EA",
            name="Each",
            symbol="ea",
            category=UnitCategory.COUNT,
        )
        self.other_unit = UnitOfMeasure.objects.create(
            organization=self.other_organization,
            code="EA",
            name="Other Each",
            symbol="ea",
            category=UnitCategory.COUNT,
        )
        self.material = Material.objects.create(
            organization=self.organization,
            code="MAT-1",
            name="Cement",
            unit_of_measure=self.unit,
        )
        self.other_material = Material.objects.create(
            organization=self.other_organization,
            code="MAT-1",
            name="Other Cement",
            unit_of_measure=self.other_unit,
        )
        self.supplier = BusinessParty.objects.create(
            organization=self.organization,
            display_name="Supplier",
            party_kind=PartyKind.COMPANY,
        )
        PartyRole.objects.create(
            organization=self.organization,
            party=self.supplier,
            role=PartyRoleType.SUPPLIER,
        )
        self.other_supplier = BusinessParty.objects.create(
            organization=self.other_organization,
            display_name="Other Supplier",
            party_kind=PartyKind.COMPANY,
        )
        PartyRole.objects.create(
            organization=self.other_organization,
            party=self.other_supplier,
            role=PartyRoleType.SUPPLIER,
        )

    def create_approved_request(
        self, quantity: Decimal = Decimal("10.0000")
    ) -> tuple[PurchaseRequest, PurchaseRequestItem]:
        request = create_purchase_request(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            request_number="pr-001",
            title="Site materials",
        )
        item = add_purchase_request_item(
            organization=self.organization,
            actor=self.member,
            purchase_request=request,
            material=self.material,
            quantity=quantity,
        )
        submit_purchase_request(
            organization=self.organization,
            actor=self.member,
            purchase_request=request,
        )
        approve_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=request,
        )
        return request, item

    def create_issued_order(
        self, quantity: Decimal = Decimal("10.0000")
    ) -> tuple[PurchaseOrder, PurchaseOrderItem]:
        request, request_item = self.create_approved_request(quantity)
        order = create_purchase_order(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            supplier=self.supplier,
            order_number="po-001",
            order_date=date(2026, 9, 9),
            purchase_request=request,
        )
        item = add_purchase_order_item(
            organization=self.organization,
            actor=self.owner,
            purchase_order=order,
            purchase_request_item=request_item,
            material=self.material,
            quantity=quantity,
            unit_price=Decimal("12.34"),
        )
        issue_purchase_order(
            organization=self.organization,
            actor=self.owner,
            purchase_order=order,
        )
        return order, item


class ProcurementModelTests(ProcurementFixtureMixin, TestCase):
    def test_models_reject_cross_tenant_and_mismatched_relationships(self) -> None:
        request = PurchaseRequest.objects.create(
            organization=self.organization,
            project=self.project,
            request_number="PR-MODEL",
            title="Model request",
        )
        invalid_records = (
            PurchaseRequest(
                organization=self.organization,
                project=self.other_project,
                request_number="BAD",
                title="Bad request",
            ),
            PurchaseRequestItem(
                organization=self.organization,
                purchase_request=request,
                material=self.other_material,
                unit_of_measure=self.other_unit,
                description="Bad item",
                quantity=Decimal(1),
            ),
            PurchaseOrder(
                organization=self.organization,
                project=self.project,
                supplier=self.other_supplier,
                order_number="BAD",
                order_date=date(2026, 9, 9),
            ),
        )
        for record in invalid_records:
            with (
                self.subTest(model=record.__class__.__name__),
                self.assertRaises(ValidationError),
            ):
                record.save()

    def test_quantities_prices_and_canonical_units_are_validated(self) -> None:
        request = PurchaseRequest.objects.create(
            organization=self.organization,
            project=self.project,
            request_number="PR-VALID",
            title="Validation request",
        )
        with self.assertRaises(ValidationError):
            PurchaseRequestItem.objects.create(
                organization=self.organization,
                purchase_request=request,
                material=self.material,
                unit_of_measure=self.unit,
                description="Invalid quantity",
                quantity=Decimal(0),
            )
        with self.assertRaises(ValidationError):
            PurchaseRequestItem.objects.create(
                organization=self.organization,
                purchase_request=request,
                material=self.material,
                unit_of_measure=self.other_unit,
                description="Invalid unit",
                quantity=Decimal(1),
            )

    def test_issued_order_and_posted_receipt_details_are_immutable(self) -> None:
        order, order_item = self.create_issued_order()
        order.notes = "Changed terms"
        with self.assertRaises(ValidationError):
            order.save()
        order_item.quantity = Decimal(2)
        with self.assertRaises(ValidationError):
            order_item.save()

        receipt = create_goods_receipt(
            organization=self.organization,
            actor=self.member,
            purchase_order=order,
            receipt_number="GR-001",
            received_at=timezone.now(),
        )
        receipt_item = add_goods_receipt_item(
            organization=self.organization,
            actor=self.member,
            goods_receipt=receipt,
            purchase_order_item=order_item,
            quantity=Decimal(5),
        )
        post_goods_receipt(
            organization=self.organization,
            actor=self.member,
            goods_receipt=receipt,
        )
        receipt.notes = "Changed receipt"
        with self.assertRaises(ValidationError):
            receipt.save()
        receipt_item.quantity = Decimal(4)
        with self.assertRaises(ValidationError):
            receipt_item.save()


class ProcurementServiceTests(ProcurementFixtureMixin, TestCase):
    def test_request_workflow_is_role_controlled_and_audited(self) -> None:
        request = create_purchase_request(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            request_number="pr-100",
            title="Concrete materials",
        )
        add_purchase_request_item(
            organization=self.organization,
            actor=self.member,
            purchase_request=request,
            material=self.material,
            quantity=Decimal("3.5000"),
        )
        submitted = submit_purchase_request(
            organization=self.organization,
            actor=self.member,
            purchase_request=request,
        )
        with self.assertRaises(PermissionDenied):
            approve_purchase_request(
                organization=self.organization,
                actor=self.member,
                purchase_request=submitted,
            )
        approved = approve_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=submitted,
        )
        self.assertEqual(approved.status, PurchaseRequestStatus.APPROVED)
        self.assertEqual(approved.approved_by, self.owner)
        self.assertEqual(
            list(
                AuditEvent.objects.filter(entity_id=str(request.pk)).values_list(
                    "action", flat=True
                )
            ),
            [
                AuditAction.PURCHASE_REQUEST_APPROVED,
                AuditAction.PURCHASE_REQUEST_SUBMITTED,
                AuditAction.PURCHASE_REQUEST_CREATED,
            ],
        )

    def test_rejection_requires_reason_and_is_terminal(self) -> None:
        request, _ = self.create_approved_request()
        with self.assertRaises(ValueError):
            reject_purchase_request(
                organization=self.organization,
                actor=self.owner,
                purchase_request=request,
                reason="Not possible",
            )

        second = create_purchase_request(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            request_number="PR-REJECT",
            title="Reject me",
        )
        add_purchase_request_item(
            organization=self.organization,
            actor=self.member,
            purchase_request=second,
            material=self.material,
            quantity=Decimal(1),
        )
        submit_purchase_request(
            organization=self.organization,
            actor=self.member,
            purchase_request=second,
        )
        with self.assertRaises(ValueError):
            reject_purchase_request(
                organization=self.organization,
                actor=self.owner,
                purchase_request=second,
            )
        rejected = reject_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=second,
            reason="Budget unavailable",
        )
        self.assertEqual(rejected.status, PurchaseRequestStatus.REJECTED)

    def test_purchase_order_requires_approved_request_and_supplier_role(self) -> None:
        request = create_purchase_request(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            request_number="PR-DRAFT",
            title="Draft request",
        )
        with self.assertRaises(ValueError):
            create_purchase_order(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                supplier=self.supplier,
                order_number="PO-DRAFT",
                order_date=date(2026, 9, 9),
                purchase_request=request,
            )
        non_supplier = BusinessParty.objects.create(
            organization=self.organization,
            display_name="Not Supplier",
            party_kind=PartyKind.COMPANY,
        )
        approved, _ = self.create_approved_request()
        with self.assertRaises(ValueError):
            create_purchase_order(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                supplier=non_supplier,
                order_number="PO-NO-SUPPLIER",
                order_date=date(2026, 9, 9),
                purchase_request=approved,
            )

    def test_order_amount_is_decimal_and_request_cannot_be_over_ordered(self) -> None:
        request, request_item = self.create_approved_request(Decimal(5))
        order = create_purchase_order(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            supplier=self.supplier,
            order_number="PO-TOTAL",
            order_date=date(2026, 9, 9),
            purchase_request=request,
        )
        item = add_purchase_order_item(
            organization=self.organization,
            actor=self.owner,
            purchase_order=order,
            purchase_request_item=request_item,
            material=self.material,
            quantity=Decimal("3.2500"),
            unit_price=Decimal("2.35"),
        )
        self.assertEqual(item.line_total, Decimal("7.64"))
        self.assertEqual(order.total_amount, Decimal("7.64"))
        with self.assertRaises(ValueError):
            add_purchase_order_item(
                organization=self.organization,
                actor=self.owner,
                purchase_order=order,
                purchase_request_item=request_item,
                material=self.material,
                quantity=Decimal(2),
                unit_price=Decimal("2.35"),
            )

    def test_receipts_complete_order_without_creating_inventory(self) -> None:
        order, order_item = self.create_issued_order()
        first = create_goods_receipt(
            organization=self.organization,
            actor=self.member,
            purchase_order=order,
            receipt_number="GR-1",
            received_at=timezone.now(),
        )
        add_goods_receipt_item(
            organization=self.organization,
            actor=self.member,
            goods_receipt=first,
            purchase_order_item=order_item,
            quantity=Decimal(4),
        )
        post_goods_receipt(
            organization=self.organization,
            actor=self.member,
            goods_receipt=first,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrderStatus.ISSUED)

        second = create_goods_receipt(
            organization=self.organization,
            actor=self.member,
            purchase_order=order,
            receipt_number="GR-2",
            received_at=timezone.now(),
        )
        add_goods_receipt_item(
            organization=self.organization,
            actor=self.member,
            goods_receipt=second,
            purchase_order_item=order_item,
            quantity=Decimal(6),
        )
        post_goods_receipt(
            organization=self.organization,
            actor=self.member,
            goods_receipt=second,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrderStatus.COMPLETED)

    def test_receipt_cannot_exceed_order_and_void_reopens_order(self) -> None:
        order, order_item = self.create_issued_order(Decimal(5))
        receipt = create_goods_receipt(
            organization=self.organization,
            actor=self.member,
            purchase_order=order,
            receipt_number="GR-FULL",
            received_at=timezone.now(),
        )
        add_goods_receipt_item(
            organization=self.organization,
            actor=self.member,
            goods_receipt=receipt,
            purchase_order_item=order_item,
            quantity=Decimal(5),
        )
        post_goods_receipt(
            organization=self.organization,
            actor=self.member,
            goods_receipt=receipt,
        )
        voided = void_goods_receipt(
            organization=self.organization,
            actor=self.owner,
            goods_receipt=receipt,
            reason="Delivery rejected",
        )
        order.refresh_from_db()
        self.assertEqual(voided.status, GoodsReceiptStatus.VOID)
        self.assertEqual(order.status, PurchaseOrderStatus.ISSUED)
        self.assertTrue(GoodsReceiptItem.objects.filter(goods_receipt=receipt).exists())

        excessive = create_goods_receipt(
            organization=self.organization,
            actor=self.member,
            purchase_order=order,
            receipt_number="GR-EXCESS",
            received_at=timezone.now(),
        )
        add_goods_receipt_item(
            organization=self.organization,
            actor=self.member,
            goods_receipt=excessive,
            purchase_order_item=order_item,
            quantity=Decimal(6),
        )
        with self.assertRaises(ValueError):
            post_goods_receipt(
                organization=self.organization,
                actor=self.member,
                goods_receipt=excessive,
            )
        excessive.refresh_from_db()
        self.assertEqual(excessive.status, GoodsReceiptStatus.DRAFT)

    def test_reads_and_mutations_are_tenant_scoped(self) -> None:
        request, _ = self.create_approved_request()
        with self.assertRaises(PermissionDenied):
            get_organization_purchase_requests(
                user=self.outsider, organization=self.organization
            )
        with self.assertRaises(PermissionDenied):
            create_purchase_order(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                supplier=self.other_supplier,
                order_number="PO-CROSS",
                order_date=date(2026, 9, 9),
                purchase_request=request,
            )
        self.assertEqual(
            list(
                get_organization_purchase_requests(
                    user=self.viewer, organization=self.organization
                )
            ),
            [request],
        )
        self.assertFalse(
            get_organization_purchase_orders(
                user=self.viewer, organization=self.organization
            )
            .filter(organization=self.other_organization)
            .exists()
        )
        self.assertFalse(
            get_organization_goods_receipts(
                user=self.viewer, organization=self.organization
            )
            .filter(organization=self.other_organization)
            .exists()
        )

    def test_viewer_cannot_mutate_procurement(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_purchase_request(
                organization=self.organization,
                actor=self.viewer,
                project=self.project,
                request_number="PR-NO",
                title="Forbidden",
            )


class ProcurementAdminTests(TestCase):
    def test_procurement_admin_is_read_only(self) -> None:
        request = RequestFactory().get("/admin/")
        for model in (
            PurchaseRequest,
            PurchaseRequestItem,
            PurchaseOrder,
            PurchaseOrderItem,
            GoodsReceipt,
            GoodsReceiptItem,
        ):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))


class ProcurementPanelTests(ProcurementFixtureMixin, TestCase):
    def test_owner_can_open_scoped_procurement_pages(self) -> None:
        request = create_purchase_request(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            request_number="PR-PANEL",
            title="Panel request",
        )
        foreign_request = create_purchase_request(
            organization=self.other_organization,
            actor=self.outsider,
            project=self.other_project,
            request_number="PR-FOREIGN",
            title="Foreign request",
        )
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

        self.assertEqual(
            self.client.get(reverse("procurement:request_list")).status_code, 200
        )
        self.assertEqual(
            self.client.get(
                reverse("procurement:request_detail", kwargs={"request_id": request.pk})
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "procurement:request_detail",
                    kwargs={"request_id": foreign_request.pk},
                )
            ).status_code,
            404,
        )
