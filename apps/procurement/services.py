from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.materials.models import Material, UnitOfMeasure
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.parties.models import BusinessParty, PartyRoleType
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
from apps.projects.models import Project
from core.identifiers import canonicalize_upper_identifier

_REQUEST_ROLES = {
    MembershipRole.OWNER,
    MembershipRole.ADMIN,
    MembershipRole.MANAGER,
    MembershipRole.MEMBER,
}
_MANAGEMENT_ROLES = {
    MembershipRole.OWNER,
    MembershipRole.ADMIN,
    MembershipRole.MANAGER,
}


def _get_active_role(*, organization: Organization, user: User) -> str:
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    try:
        return organization.memberships.get(
            user=user, status=MembershipStatus.ACTIVE
        ).role
    except organization.memberships.model.DoesNotExist as exc:
        raise PermissionDenied("You do not have access to this organization.") from exc


def _require_role(
    *, organization: Organization, actor: User, allowed_roles: set[str], message: str
) -> str:
    role = _get_active_role(organization=organization, user=actor)
    if role not in allowed_roles:
        raise PermissionDenied(message)
    return role


def _validate_project(*, organization: Organization, project: Project) -> None:
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")


def _validate_material(
    *,
    organization: Organization,
    material: Material,
    unit_of_measure: UnitOfMeasure | None = None,
) -> UnitOfMeasure:
    unit = unit_of_measure or material.unit_of_measure
    if (
        material.organization_id != organization.pk
        or unit.organization_id != organization.pk
        or material.unit_of_measure_id != unit.pk
        or not material.is_active
        or material.archived_at is not None
        or not unit.is_active
        or unit.archived_at is not None
    ):
        raise PermissionDenied(
            "The material and unit must be active records in this organization."
        )
    return unit


def _validate_supplier(*, organization: Organization, supplier: BusinessParty) -> None:
    if supplier.organization_id != organization.pk or supplier.archived_at is not None:
        raise PermissionDenied("The supplier does not belong to this organization.")
    if not supplier.roles.filter(
        organization=organization,
        role=PartyRoleType.SUPPLIER,
        is_active=True,
    ).exists():
        raise ValueError("The selected party must have an active supplier role.")


def _save_validated(instance: object, message: str) -> None:
    try:
        instance.full_clean()
        instance.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(message) from exc


def _get_locked_request(
    *, organization: Organization, purchase_request: PurchaseRequest
) -> PurchaseRequest:
    try:
        request = PurchaseRequest.objects.select_for_update().get(
            pk=purchase_request.pk, organization=organization
        )
    except PurchaseRequest.DoesNotExist as exc:
        raise PermissionDenied(
            "Purchase request not found in this organization."
        ) from exc
    _validate_project(organization=organization, project=request.project)
    return request


def _get_locked_order(
    *, organization: Organization, purchase_order: PurchaseOrder
) -> PurchaseOrder:
    try:
        order = (
            PurchaseOrder.objects.select_for_update()
            .select_related("project", "supplier", "purchase_request")
            .get(pk=purchase_order.pk, organization=organization)
        )
    except PurchaseOrder.DoesNotExist as exc:
        raise PermissionDenied(
            "Purchase order not found in this organization."
        ) from exc
    _validate_project(organization=organization, project=order.project)
    return order


def _get_locked_receipt(
    *, organization: Organization, goods_receipt: GoodsReceipt
) -> GoodsReceipt:
    try:
        receipt = (
            GoodsReceipt.objects.select_for_update()
            .select_related("purchase_order", "project")
            .get(pk=goods_receipt.pk, organization=organization)
        )
    except GoodsReceipt.DoesNotExist as exc:
        raise PermissionDenied("Goods receipt not found in this organization.") from exc
    return receipt


@transaction.atomic
def create_purchase_request(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    request_number: str,
    title: str,
    required_by: date | None = None,
    notes: str = "",
) -> PurchaseRequest:
    _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_REQUEST_ROLES,
        message="You cannot create purchase requests in this organization.",
    )
    _validate_project(organization=organization, project=project)
    normalized_number = canonicalize_upper_identifier(request_number)
    if not normalized_number or not title.strip():
        raise ValueError("Request number and title are required.")
    request = PurchaseRequest(
        organization=organization,
        project=project,
        request_number=normalized_number,
        title=title.strip(),
        required_by=required_by,
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(request, "Purchase request data is invalid.")
    record_audit_event(
        action=AuditAction.PURCHASE_REQUEST_CREATED,
        entity_type="purchase_request",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={
            "request_number": request.request_number,
            "project_id": str(project.pk),
        },
    )
    return request


@transaction.atomic
def add_purchase_request_item(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    material: Material,
    quantity: Decimal,
    unit_of_measure: UnitOfMeasure | None = None,
    description: str = "",
    sort_order: int = 0,
) -> PurchaseRequestItem:
    role = _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_REQUEST_ROLES,
        message="You cannot edit purchase requests in this organization.",
    )
    request = _get_locked_request(
        organization=organization, purchase_request=purchase_request
    )
    if request.status != PurchaseRequestStatus.DRAFT:
        raise ValueError("Only draft purchase requests can have items changed.")
    if role not in _MANAGEMENT_ROLES and request.created_by_id != actor.pk:
        raise PermissionDenied("You cannot edit this purchase request.")
    unit = _validate_material(
        organization=organization,
        material=material,
        unit_of_measure=unit_of_measure,
    )
    if quantity <= Decimal(0):
        raise ValueError("Requested quantity must be positive.")
    item = PurchaseRequestItem(
        organization=organization,
        purchase_request=request,
        material=material,
        unit_of_measure=unit,
        description=description.strip() or material.name,
        quantity=quantity,
        sort_order=sort_order,
        created_by=actor,
    )
    _save_validated(item, "Purchase request item data is invalid.")
    request.updated_by = actor
    request.save(update_fields=["updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.PURCHASE_REQUEST_ITEM_ADDED,
        entity_type="purchase_request_item",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        metadata={
            "purchase_request_id": str(request.pk),
            "material_id": str(material.pk),
            "quantity": str(item.quantity),
        },
    )
    return item


@transaction.atomic
def submit_purchase_request(
    *, organization: Organization, actor: User, purchase_request: PurchaseRequest
) -> PurchaseRequest:
    role = _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_REQUEST_ROLES,
        message="You cannot submit purchase requests in this organization.",
    )
    request = _get_locked_request(
        organization=organization, purchase_request=purchase_request
    )
    if role not in _MANAGEMENT_ROLES and request.created_by_id != actor.pk:
        raise PermissionDenied("You cannot submit this purchase request.")
    if request.status != PurchaseRequestStatus.DRAFT:
        raise ValueError("Only draft purchase requests can be submitted.")
    if not request.items.exists():
        raise ValueError("A purchase request must have at least one item.")
    request.status = PurchaseRequestStatus.SUBMITTED
    request.submitted_at = timezone.now()
    request.updated_by = actor
    request.save(update_fields=["status", "submitted_at", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.PURCHASE_REQUEST_SUBMITTED,
        entity_type="purchase_request",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": PurchaseRequestStatus.DRAFT},
    )
    return request


@transaction.atomic
def decide_purchase_request(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    approve: bool,
    reason: str = "",
) -> PurchaseRequest:
    _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_MANAGEMENT_ROLES,
        message="You cannot approve purchase requests in this organization.",
    )
    request = _get_locked_request(
        organization=organization, purchase_request=purchase_request
    )
    if request.status != PurchaseRequestStatus.SUBMITTED:
        raise ValueError("Only submitted purchase requests can be decided.")
    if not approve and not reason.strip():
        raise ValueError("A rejection reason is required.")
    request.status = (
        PurchaseRequestStatus.APPROVED if approve else PurchaseRequestStatus.REJECTED
    )
    request.approved_at = timezone.now() if approve else None
    request.approved_by = actor if approve else None
    request.decision_reason = reason.strip()
    request.updated_by = actor
    request.save(
        update_fields=[
            "status",
            "approved_at",
            "approved_by",
            "decision_reason",
            "updated_by",
            "updated_at",
        ]
    )
    action = (
        AuditAction.PURCHASE_REQUEST_APPROVED
        if approve
        else AuditAction.PURCHASE_REQUEST_REJECTED
    )
    record_audit_event(
        action=action,
        entity_type="purchase_request",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={
            "previous_status": PurchaseRequestStatus.SUBMITTED,
            "status": request.status,
            "reason": request.decision_reason,
        },
    )
    return request


def approve_purchase_request(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    reason: str = "",
) -> PurchaseRequest:
    return decide_purchase_request(
        organization=organization,
        actor=actor,
        purchase_request=purchase_request,
        approve=True,
        reason=reason,
    )


def reject_purchase_request(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    reason: str = "",
) -> PurchaseRequest:
    return decide_purchase_request(
        organization=organization,
        actor=actor,
        purchase_request=purchase_request,
        approve=False,
        reason=reason,
    )


@transaction.atomic
def cancel_purchase_request(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    reason: str,
) -> PurchaseRequest:
    role = _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_REQUEST_ROLES,
        message="You cannot cancel purchase requests in this organization.",
    )
    request = _get_locked_request(
        organization=organization, purchase_request=purchase_request
    )
    if role not in _MANAGEMENT_ROLES and request.created_by_id != actor.pk:
        raise PermissionDenied("You cannot cancel this purchase request.")
    if request.status not in {
        PurchaseRequestStatus.DRAFT,
        PurchaseRequestStatus.SUBMITTED,
    }:
        raise ValueError("Only draft or submitted purchase requests can be cancelled.")
    if not reason.strip():
        raise ValueError("A cancellation reason is required.")
    previous_status = request.status
    request.status = PurchaseRequestStatus.CANCELLED
    request.decision_reason = reason.strip()
    request.updated_by = actor
    request.save(
        update_fields=["status", "decision_reason", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.PURCHASE_REQUEST_CANCELLED,
        entity_type="purchase_request",
        entity_id=request.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "reason": reason.strip()},
    )
    return request


def get_organization_purchase_requests(
    *, user: User, organization: Organization
) -> QuerySet[PurchaseRequest]:
    _get_active_role(organization=organization, user=user)
    return PurchaseRequest.objects.filter(
        organization=organization, project__deleted_at__isnull=True
    ).select_related("project", "created_by", "approved_by", "updated_by")


def get_organization_purchase_request(
    *, user: User, organization: Organization, purchase_request_id: str
) -> PurchaseRequest:
    try:
        return (
            get_organization_purchase_requests(user=user, organization=organization)
            .prefetch_related("items__material", "items__unit_of_measure")
            .get(pk=purchase_request_id)
        )
    except PurchaseRequest.DoesNotExist as exc:
        raise PermissionDenied(
            "Purchase request not found in this organization."
        ) from exc


@transaction.atomic
def create_purchase_order(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    supplier: BusinessParty,
    order_number: str,
    order_date: date,
    purchase_request: PurchaseRequest | None = None,
    expected_delivery_date: date | None = None,
    notes: str = "",
) -> PurchaseOrder:
    _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_MANAGEMENT_ROLES,
        message="You cannot create purchase orders in this organization.",
    )
    _validate_project(organization=organization, project=project)
    _validate_supplier(organization=organization, supplier=supplier)
    if purchase_request is not None:
        request = _get_locked_request(
            organization=organization, purchase_request=purchase_request
        )
        if request.project_id != project.pk:
            raise PermissionDenied("Purchase request does not belong to this project.")
        if request.status != PurchaseRequestStatus.APPROVED:
            raise ValueError("Only approved purchase requests can be ordered.")
    normalized_number = canonicalize_upper_identifier(order_number)
    if not normalized_number:
        raise ValueError("Order number is required.")
    order = PurchaseOrder(
        organization=organization,
        project=project,
        purchase_request=purchase_request,
        supplier=supplier,
        order_number=normalized_number,
        order_date=order_date,
        expected_delivery_date=expected_delivery_date,
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(order, "Purchase order data is invalid.")
    record_audit_event(
        action=AuditAction.PURCHASE_ORDER_CREATED,
        entity_type="purchase_order",
        entity_id=order.pk,
        organization=organization,
        actor=actor,
        metadata={
            "order_number": order.order_number,
            "project_id": str(project.pk),
            "supplier_id": str(supplier.pk),
            "purchase_request_id": str(purchase_request.pk)
            if purchase_request
            else None,
        },
    )
    return order


@transaction.atomic
def add_purchase_order_item(
    *,
    organization: Organization,
    actor: User,
    purchase_order: PurchaseOrder,
    material: Material,
    quantity: Decimal,
    unit_price: Decimal,
    unit_of_measure: UnitOfMeasure | None = None,
    purchase_request_item: PurchaseRequestItem | None = None,
    description: str = "",
    sort_order: int = 0,
) -> PurchaseOrderItem:
    _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_MANAGEMENT_ROLES,
        message="You cannot edit purchase orders in this organization.",
    )
    order = _get_locked_order(organization=organization, purchase_order=purchase_order)
    if order.status != PurchaseOrderStatus.DRAFT:
        raise ValueError("Only draft purchase orders can have items changed.")
    unit = _validate_material(
        organization=organization,
        material=material,
        unit_of_measure=unit_of_measure,
    )
    if quantity <= Decimal(0) or unit_price < Decimal(0):
        raise ValueError("Order quantity must be positive and price non-negative.")
    if purchase_request_item is not None:
        try:
            request_item = PurchaseRequestItem.objects.select_for_update().get(
                pk=purchase_request_item.pk,
                organization=organization,
                purchase_request=order.purchase_request,
            )
        except PurchaseRequestItem.DoesNotExist as exc:
            raise PermissionDenied(
                "Request item does not belong to the linked request."
            ) from exc
        if request_item.material_id != material.pk:
            raise ValueError("Order material must match the request item.")
        already_ordered = PurchaseOrderItem.objects.filter(
            purchase_request_item=request_item,
            purchase_order__status__in={
                PurchaseOrderStatus.DRAFT,
                PurchaseOrderStatus.ISSUED,
                PurchaseOrderStatus.COMPLETED,
            },
        ).exclude(purchase_order=order).aggregate(total=Sum("quantity"))[
            "total"
        ] or Decimal(0)
        current_ordered = order.items.filter(
            purchase_request_item=request_item
        ).aggregate(total=Sum("quantity"))["total"] or Decimal(0)
        if already_ordered + current_ordered + quantity > request_item.quantity:
            raise ValueError("Ordered quantity cannot exceed the requested quantity.")
    item = PurchaseOrderItem(
        organization=organization,
        purchase_order=order,
        purchase_request_item=purchase_request_item,
        material=material,
        unit_of_measure=unit,
        description=description.strip() or material.name,
        quantity=quantity,
        unit_price=unit_price,
        sort_order=sort_order,
    )
    _save_validated(item, "Purchase order item data is invalid.")
    order.updated_by = actor
    order.save(update_fields=["updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.PURCHASE_ORDER_ITEM_ADDED,
        entity_type="purchase_order_item",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        metadata={
            "purchase_order_id": str(order.pk),
            "material_id": str(material.pk),
            "quantity": str(item.quantity),
            "unit_price": str(item.unit_price),
            "line_total": str(item.line_total),
        },
    )
    return item


@transaction.atomic
def issue_purchase_order(
    *, organization: Organization, actor: User, purchase_order: PurchaseOrder
) -> PurchaseOrder:
    _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_MANAGEMENT_ROLES,
        message="You cannot issue purchase orders in this organization.",
    )
    order = _get_locked_order(organization=organization, purchase_order=purchase_order)
    if order.status != PurchaseOrderStatus.DRAFT:
        raise ValueError("Only draft purchase orders can be issued.")
    _validate_supplier(organization=organization, supplier=order.supplier)
    if not order.items.exists():
        raise ValueError("A purchase order must have at least one item.")
    order.status = PurchaseOrderStatus.ISSUED
    order.issued_at = timezone.now()
    order.issued_by = actor
    order.updated_by = actor
    order.save(
        update_fields=["status", "issued_at", "issued_by", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.PURCHASE_ORDER_ISSUED,
        entity_type="purchase_order",
        entity_id=order.pk,
        organization=organization,
        actor=actor,
        metadata={"total_amount": str(order.total_amount)},
    )
    return order


@transaction.atomic
def cancel_purchase_order(
    *,
    organization: Organization,
    actor: User,
    purchase_order: PurchaseOrder,
    reason: str,
) -> PurchaseOrder:
    _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_MANAGEMENT_ROLES,
        message="You cannot cancel purchase orders in this organization.",
    )
    order = _get_locked_order(organization=organization, purchase_order=purchase_order)
    if order.status not in {PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.ISSUED}:
        raise ValueError("Only draft or issued purchase orders can be cancelled.")
    if not reason.strip():
        raise ValueError("A cancellation reason is required.")
    if order.goods_receipts.filter(status=GoodsReceiptStatus.POSTED).exists():
        raise ValueError("An order with posted receipts cannot be cancelled.")
    previous_status = order.status
    order.status = PurchaseOrderStatus.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancellation_reason = reason.strip()
    order.updated_by = actor
    order.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancellation_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PURCHASE_ORDER_CANCELLED,
        entity_type="purchase_order",
        entity_id=order.pk,
        organization=organization,
        actor=actor,
        metadata={"previous_status": previous_status, "reason": reason.strip()},
    )
    return order


def get_organization_purchase_orders(
    *, user: User, organization: Organization
) -> QuerySet[PurchaseOrder]:
    _get_active_role(organization=organization, user=user)
    return PurchaseOrder.objects.filter(
        organization=organization, project__deleted_at__isnull=True
    ).select_related(
        "project", "supplier", "purchase_request", "created_by", "issued_by"
    )


def get_organization_purchase_order(
    *, user: User, organization: Organization, purchase_order_id: str
) -> PurchaseOrder:
    try:
        return (
            get_organization_purchase_orders(user=user, organization=organization)
            .prefetch_related(
                "items__material", "items__unit_of_measure", "goods_receipts"
            )
            .get(pk=purchase_order_id)
        )
    except PurchaseOrder.DoesNotExist as exc:
        raise PermissionDenied(
            "Purchase order not found in this organization."
        ) from exc


@transaction.atomic
def create_goods_receipt(
    *,
    organization: Organization,
    actor: User,
    purchase_order: PurchaseOrder,
    receipt_number: str,
    received_at: datetime,
    notes: str = "",
) -> GoodsReceipt:
    _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_REQUEST_ROLES,
        message="You cannot receive goods in this organization.",
    )
    order = _get_locked_order(organization=organization, purchase_order=purchase_order)
    if order.status != PurchaseOrderStatus.ISSUED:
        raise ValueError("Goods can only be received against an issued order.")
    if timezone.is_naive(received_at):
        raise ValueError("Receipt time must be timezone-aware.")
    normalized_number = canonicalize_upper_identifier(receipt_number)
    if not normalized_number:
        raise ValueError("Receipt number is required.")
    receipt = GoodsReceipt(
        organization=organization,
        purchase_order=order,
        project=order.project,
        receipt_number=normalized_number,
        received_at=received_at,
        notes=notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(receipt, "Goods receipt data is invalid.")
    record_audit_event(
        action=AuditAction.GOODS_RECEIPT_CREATED,
        entity_type="goods_receipt",
        entity_id=receipt.pk,
        organization=organization,
        actor=actor,
        metadata={
            "purchase_order_id": str(order.pk),
            "receipt_number": receipt.receipt_number,
        },
    )
    return receipt


@transaction.atomic
def add_goods_receipt_item(
    *,
    organization: Organization,
    actor: User,
    goods_receipt: GoodsReceipt,
    purchase_order_item: PurchaseOrderItem,
    quantity: Decimal,
    notes: str = "",
) -> GoodsReceiptItem:
    _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_REQUEST_ROLES,
        message="You cannot edit goods receipts in this organization.",
    )
    receipt = _get_locked_receipt(
        organization=organization, goods_receipt=goods_receipt
    )
    if receipt.status != GoodsReceiptStatus.DRAFT:
        raise ValueError("Only draft goods receipts can have items changed.")
    try:
        order_item = PurchaseOrderItem.objects.select_for_update().get(
            pk=purchase_order_item.pk,
            organization=organization,
            purchase_order=receipt.purchase_order,
        )
    except PurchaseOrderItem.DoesNotExist as exc:
        raise PermissionDenied(
            "Order item does not belong to the receipt order."
        ) from exc
    if quantity <= Decimal(0):
        raise ValueError("Received quantity must be positive.")
    item = GoodsReceiptItem(
        organization=organization,
        goods_receipt=receipt,
        purchase_order_item=order_item,
        material=order_item.material,
        unit_of_measure=order_item.unit_of_measure,
        quantity=quantity,
        notes=notes.strip(),
        created_by=actor,
    )
    _save_validated(item, "Goods receipt item data is invalid.")
    receipt.updated_by = actor
    receipt.save(update_fields=["updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.GOODS_RECEIPT_ITEM_ADDED,
        entity_type="goods_receipt_item",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        metadata={
            "goods_receipt_id": str(receipt.pk),
            "purchase_order_item_id": str(order_item.pk),
            "quantity": str(item.quantity),
        },
    )
    return item


def _order_is_fully_received(order: PurchaseOrder) -> bool:
    received = {
        row["purchase_order_item_id"]: row["total"]
        for row in GoodsReceiptItem.objects.filter(
            goods_receipt__purchase_order=order,
            goods_receipt__status=GoodsReceiptStatus.POSTED,
        )
        .values("purchase_order_item_id")
        .annotate(total=Sum("quantity"))
    }
    return order.items.exists() and all(
        received.get(item.pk, Decimal(0)) >= item.quantity for item in order.items.all()
    )


@transaction.atomic
def post_goods_receipt(
    *, organization: Organization, actor: User, goods_receipt: GoodsReceipt
) -> GoodsReceipt:
    _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_REQUEST_ROLES,
        message="You cannot post goods receipts in this organization.",
    )
    receipt = _get_locked_receipt(
        organization=organization, goods_receipt=goods_receipt
    )
    order = _get_locked_order(
        organization=organization, purchase_order=receipt.purchase_order
    )
    if receipt.status != GoodsReceiptStatus.DRAFT:
        raise ValueError("Only draft goods receipts can be posted.")
    if order.status != PurchaseOrderStatus.ISSUED:
        raise ValueError("The purchase order is not open for receipt.")
    items = list(
        receipt.items.select_related("purchase_order_item").select_for_update()
    )
    if not items:
        raise ValueError("A goods receipt must have at least one item.")
    for item in items:
        already_received = GoodsReceiptItem.objects.filter(
            purchase_order_item=item.purchase_order_item,
            goods_receipt__status=GoodsReceiptStatus.POSTED,
        ).aggregate(total=Sum("quantity"))["total"] or Decimal(0)
        if already_received + item.quantity > item.purchase_order_item.quantity:
            raise ValueError("Received quantity cannot exceed ordered quantity.")
    receipt.status = GoodsReceiptStatus.POSTED
    receipt.posted_at = timezone.now()
    receipt.posted_by = actor
    receipt.updated_by = actor
    receipt.save(
        update_fields=["status", "posted_at", "posted_by", "updated_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.GOODS_RECEIPT_POSTED,
        entity_type="goods_receipt",
        entity_id=receipt.pk,
        organization=organization,
        actor=actor,
        metadata={"purchase_order_id": str(order.pk)},
    )
    if _order_is_fully_received(order):
        order.status = PurchaseOrderStatus.COMPLETED
        order.updated_by = actor
        order.save(update_fields=["status", "updated_by", "updated_at"])
        record_audit_event(
            action=AuditAction.PURCHASE_ORDER_COMPLETED,
            entity_type="purchase_order",
            entity_id=order.pk,
            organization=organization,
            actor=actor,
            metadata={"goods_receipt_id": str(receipt.pk)},
        )
    return receipt


@transaction.atomic
def void_goods_receipt(
    *,
    organization: Organization,
    actor: User,
    goods_receipt: GoodsReceipt,
    reason: str,
) -> GoodsReceipt:
    _require_role(
        organization=organization,
        actor=actor,
        allowed_roles=_MANAGEMENT_ROLES,
        message="You cannot void goods receipts in this organization.",
    )
    receipt = _get_locked_receipt(
        organization=organization, goods_receipt=goods_receipt
    )
    order = _get_locked_order(
        organization=organization, purchase_order=receipt.purchase_order
    )
    if receipt.status != GoodsReceiptStatus.POSTED:
        raise ValueError("Only posted goods receipts can be voided.")
    if not reason.strip():
        raise ValueError("A void reason is required.")
    receipt.status = GoodsReceiptStatus.VOID
    receipt.voided_at = timezone.now()
    receipt.voided_by = actor
    receipt.void_reason = reason.strip()
    receipt.updated_by = actor
    receipt.save(
        update_fields=[
            "status",
            "voided_at",
            "voided_by",
            "void_reason",
            "updated_by",
            "updated_at",
        ]
    )
    if order.status == PurchaseOrderStatus.COMPLETED and not _order_is_fully_received(
        order
    ):
        order.status = PurchaseOrderStatus.ISSUED
        order.updated_by = actor
        order.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.GOODS_RECEIPT_VOIDED,
        entity_type="goods_receipt",
        entity_id=receipt.pk,
        organization=organization,
        actor=actor,
        metadata={"purchase_order_id": str(order.pk), "reason": reason.strip()},
    )
    return receipt


def get_organization_goods_receipts(
    *, user: User, organization: Organization
) -> QuerySet[GoodsReceipt]:
    _get_active_role(organization=organization, user=user)
    return GoodsReceipt.objects.filter(
        organization=organization, project__deleted_at__isnull=True
    ).select_related(
        "purchase_order", "project", "created_by", "posted_by", "voided_by"
    )


def get_organization_goods_receipt(
    *, user: User, organization: Organization, goods_receipt_id: str
) -> GoodsReceipt:
    try:
        return (
            get_organization_goods_receipts(user=user, organization=organization)
            .prefetch_related(
                "items__purchase_order_item",
                "items__material",
                "items__unit_of_measure",
            )
            .get(pk=goods_receipt_id)
        )
    except GoodsReceipt.DoesNotExist as exc:
        raise PermissionDenied("Goods receipt not found in this organization.") from exc
