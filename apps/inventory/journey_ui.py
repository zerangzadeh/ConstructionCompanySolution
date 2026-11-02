"""Scoped presentation of Inventory facts; services retain posting authority."""

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from apps.inventory.forms import StockTransactionForm
from apps.inventory.models import StockTransaction
from apps.inventory.services import get_stock_balance
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode as P
from apps.procurement.models import GoodsReceiptItem
from apps.procurement.request_ui import permitted


def source_label(item):
    return f"{item.goods_receipt.receipt_number} · {item.material.name} · {item.quantity} {item.unit_of_measure.name} · {item.goods_receipt.project.name}"


def warehouse_label(warehouse):
    return f"{warehouse.name} · {warehouse.code} · {warehouse.project.name if warehouse.project_id else 'انبار مرکزی'}"


def receipt_sources(request, *, unused=False):
    membership = require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.STOCK_TRANSACTIONS_CREATE,
        allow_any_scope=True,
        message="مجوز ثبت ورود به انبار را ندارید.",
    )
    records = scope_queryset(
        GoodsReceiptItem.objects.filter(
            organization=request.organization,
            goods_receipt__status="posted",
            goods_receipt__purchase_order_version__isnull=False,
            goods_receipt__project__deleted_at__isnull=True,
        ),
        membership=membership,
        project_lookup="goods_receipt__project_id",
    ).select_related(
        "goods_receipt__project",
        "goods_receipt__purchase_order",
        "material",
        "unit_of_measure",
    )
    return records.filter(stock_transactions__isnull=True) if unused else records


def compatible_warehouses(request, source):
    form = StockTransactionForm(
        organization=request.organization,
        membership=get_active_membership(
            user=request.user, organization=request.organization
        ),
    )
    return (
        form.fields["destination_warehouse"]
        .queryset.filter(
            Q(project=source.goods_receipt.project) | Q(project__isnull=True)
        )
        .select_related("project")
    )


def inventory_error(exc):
    """Translate service failures without displaying internal contract details."""
    text = "؛ ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
    if any(
        token in text
        for token in (
            "Stock receipt",
            "retained contract",
            "Receipt occurrence",
            "Receipt history",
        )
    ):
        return "اطلاعات این ورود با رسید کالا یا سابقه ورود قبلی هم‌خوان نیست. ورود ثبت‌شده را بررسی کنید؛ ورود دوباره با اطلاعات متفاوت مجاز نیست."
    if "Stock transaction data" in text:
        return "اطلاعات گردش معتبر نیست یا شماره و منبع آن قبلاً استفاده شده است."
    if (
        any(
            token in text
            for token in (
                "UUID",
                "idempotency",
                "workflow",
                "Workflow",
                "trace",
                "Trace",
                "Receipt ",
            )
        )
        or "object (" in text
    ):
        return "شرایط ثبت این گردش کامل نیست؛ منبع، وضعیت گردش و اختیار اقدام را بررسی کنید."
    return text


def movement_context(request, record, **overrides):
    source_record = record.reversal_of if record.reversal_of_id else record
    source = source_record.goods_receipt_item
    active = request.organization.status == "active"
    can = lambda code: active and permitted(request, code, record.project)
    balance_rows = []
    if can(P.STOCK_BALANCES_VIEW):
        for warehouse in (record.source_warehouse, record.destination_warehouse):
            if warehouse:
                try:
                    balance = get_stock_balance(
                        user=request.user,
                        organization=request.organization,
                        warehouse=warehouse,
                        material=record.material,
                    )
                except PermissionDenied:
                    continue
                balance_rows.append(
                    {
                        "warehouse": warehouse,
                        "quantity": balance,
                        "can_view": permitted(
                            request, P.WAREHOUSES_VIEW, warehouse.project
                        ),
                    }
                )
    reversal = StockTransaction.objects.filter(
        organization=request.organization, reversal_of=record
    ).first()
    return {
        "transaction": record,
        "source_item": source,
        "can_view_grn": bool(source)
        and permitted(request, P.GOODS_RECEIPTS_VIEW, source.goods_receipt.project),
        "can_post": record.status == "draft" and can(P.STOCK_TRANSACTIONS_POST),
        "can_reverse": record.status == "posted"
        and record.transaction_type != "reversal"
        and can(P.STOCK_TRANSACTIONS_REVERSE),
        "balance_rows": balance_rows,
        "reversal": reversal,
        **overrides,
    }
