"""Bounded preparation adapters over existing Procurement receipt services."""

from datetime import datetime
from decimal import Decimal

from django.db import transaction

from apps.accounts.models import User
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.procurement import models as m
from apps.procurement import services as s
from apps.procurement.receipt_ui import quantity_rows, receipt_readiness
from core.identifiers import canonicalize_upper_identifier


@transaction.atomic
def prepare_receipt(
    *,
    organization: Organization,
    actor: User,
    purchase_order: m.PurchaseOrder,
    receipt_number: str,
    received_at: datetime,
    notes: str = "",
) -> m.GoodsReceipt:
    """Serialize header retries on their PO without adding a lifecycle state."""
    order = m.PurchaseOrder.objects.select_for_update().get(
        pk=purchase_order.pk,
        organization=organization,
        project__deleted_at__isnull=True,
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=P.GOODS_RECEIPTS_CREATE,
        project=order.project,
        message="مجوز ثبت رسید این پروژه را ندارید.",
    )
    existing = m.GoodsReceipt.objects.filter(
        organization=organization,
        receipt_number=canonicalize_upper_identifier(receipt_number),
    ).first()
    if existing:
        if (
            existing.purchase_order_id != order.pk
            or existing.purchase_order_version_id != order.current_version_id
            or existing.received_at != received_at
            or existing.notes != notes.strip()
        ):
            raise ValueError(
                "این شماره رسید قبلاً با اطلاعات دیگری ثبت شده است؛ رسید موجود را بررسی کنید."
            )
        return existing
    return s.create_goods_receipt(
        organization=organization,
        actor=actor,
        purchase_order=order,
        receipt_number=receipt_number,
        received_at=received_at,
        notes=notes,
    )


@transaction.atomic
def prepare_receipt_line(
    *,
    organization: Organization,
    actor: User,
    goods_receipt: m.GoodsReceipt,
    purchase_order_item: m.PurchaseOrderItem,
    quantity: Decimal,
    notes: str = "",
) -> m.GoodsReceiptItem:
    """Re-read the posted sum under the original receipt → order lock order."""
    receipt = m.GoodsReceipt.objects.select_for_update().get(
        pk=goods_receipt.pk, organization=organization
    )
    order = m.PurchaseOrder.objects.select_for_update().get(
        pk=receipt.purchase_order_id, organization=organization
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=P.GOODS_RECEIPT_ITEMS_ADD,
        project=order.project,
        message="مجوز ورود اقلام رسید این پروژه را ندارید.",
    )
    if receipt.status != "draft":
        raise ValueError("فقط اقلام رسید پیش‌نویس قابل افزودن هستند.")
    error = receipt_readiness(order)
    if error:
        raise ValueError(error)
    row = next(
        (
            r
            for r in quantity_rows(order, receipt=receipt)
            if r["line"].source_item_id == purchase_order_item.pk
        ),
        None,
    )
    if not row or row["item"]:
        raise ValueError("ردیف در اقلام مجاز این رسید نیست یا قبلاً افزوده شده است.")
    if quantity > row["remaining"]:
        raise ValueError("مقدار این دریافت نمی‌تواند از باقی‌مانده سفارش بیشتر باشد.")
    return s.add_goods_receipt_item(
        organization=organization,
        actor=actor,
        goods_receipt=receipt,
        purchase_order_item=purchase_order_item,
        quantity=quantity,
        notes=notes,
    )
