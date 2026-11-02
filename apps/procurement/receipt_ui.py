"""Read-only projections of Procurement's pinned receipt evidence."""

from decimal import Decimal
from urllib.parse import urlencode

from django.db.models import Q, Sum
from django.urls import reverse

from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import BusinessPermissionCode as P
from apps.procurement import models as m
from apps.procurement.request_ui import permitted
from core.product_surface import route_exposed


def receipt_orders(request):
    membership = require_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.GOODS_RECEIPTS_CREATE,
        allow_any_scope=True,
        message="مجوز ثبت رسید کالا را ندارید.",
    )
    return scope_queryset(
        m.PurchaseOrder.objects.filter(
            organization=request.organization,
            project__deleted_at__isnull=True,
        ),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "supplier", "current_version")


def receipt_readiness(order):
    if order.status != "issued":
        return "دریافت کالا فقط برای سفارش صادرشده و باز امکان‌پذیر است."
    if not order.current_version_id:
        return "نسخه صادرشده سفارش برای دریافت کالا در دسترس نیست."
    if not order.current_version.lines.exists():
        return "سفارش صادرشده ردیف قابل دریافت ندارد."
    return ""


def quantity_rows(order, *, receipt=None):
    """Use the same posted-line sum and pinned quantities as post_goods_receipt.

    Other posted receipts are live evidence, not an invented historical cutoff.
    Draft quantities do not reserve or consume an order's remaining quantity.
    """
    version = receipt.purchase_order_version if receipt else order.current_version
    if version is None:
        return []
    posted = m.GoodsReceiptItem.objects.filter(
        organization=order.organization,
        goods_receipt__purchase_order=order,
        goods_receipt__status="posted",
    )
    if receipt:
        posted = posted.exclude(goods_receipt=receipt)
    totals = dict(
        posted.values("purchase_order_item_id")
        .annotate(total=Sum("quantity"))
        .values_list("purchase_order_item_id", "total")
    )
    current = (
        {
            i.purchase_order_item_id: i
            for i in receipt.items.select_related("material", "unit_of_measure")
        }
        if receipt
        else {}
    )
    rows = []
    for line in version.lines.select_related(
        "source_item", "material", "unit_of_measure"
    ).order_by("sort_order", "created_at"):
        item = current.get(line.source_item_id)
        other = totals.get(line.source_item_id, Decimal(0))
        quantity = item.quantity if item else Decimal(0)
        posted_current = (
            quantity if receipt and receipt.status == "posted" else Decimal(0)
        )
        rows.append(
            {
                "line": line,
                "item": item,
                "ordered": line.quantity,
                "previous": other,
                "current": quantity,
                "remaining": line.quantity - other - posted_current,
                "after_current": line.quantity - other - quantity,
                "cumulative": other + posted_current,
            }
        )
    return rows


def receipt_context(request, receipt, **overrides):
    order = receipt.purchase_order
    rows = quantity_rows(order, receipt=receipt)
    can = lambda code: (
        request.organization.status == "active"
        and permitted(request, code, receipt.project)
    )
    dependencies = receipt.items.filter(
        organization=request.organization,
        stock_transactions__status="posted",
        stock_transactions__transaction_type="receipt",
    ).exists()
    inventory_rows = []
    if (
        receipt.status == "posted"
        and can(P.STOCK_TRANSACTIONS_CREATE)
        and route_exposed("inventory:transaction_create")
    ):
        from apps.inventory.forms import StockTransactionForm
        from apps.organizations.authorization import get_active_membership

        form = StockTransactionForm(
            organization=request.organization,
            membership=get_active_membership(
                user=request.user, organization=request.organization
            ),
        )
        eligible = set(
            form.fields["goods_receipt_item"]
            .queryset.filter(goods_receipt=receipt)
            .values_list("pk", flat=True)
        )
        for row in rows:
            item = row["item"]
            if (
                item
                and item.pk in eligible
                and form.fields["material"]
                .queryset.filter(pk=item.material_id)
                .exists()
                and form.fields["destination_warehouse"]
                .queryset.filter(Q(project=receipt.project) | Q(project__isnull=True))
                .exists()
            ):
                inventory_rows.append(
                    {
                        "item": item,
                        "url": reverse("inventory:transaction_create")
                        + "?"
                        + urlencode({"goods_receipt_item": str(item.pk)}),
                    }
                )
    return {
        "goods_receipt": receipt,
        "quantity_rows": rows,
        "can_view_order": permitted(request, P.PURCHASE_ORDERS_VIEW, receipt.project),
        "can_add_item": receipt.status == "draft"
        and not receipt_readiness(order)
        and can(P.GOODS_RECEIPT_ITEMS_ADD)
        and any(not r["item"] and r["remaining"] > 0 for r in rows),
        "can_post": receipt.status == "draft"
        and not receipt_readiness(order)
        and any(r["item"] for r in rows)
        and all(r["after_current"] >= 0 for r in rows)
        and can(P.GOODS_RECEIPTS_POST),
        "can_void": receipt.status == "posted"
        and can(P.GOODS_RECEIPTS_VOID)
        and not dependencies,
        "void_blocked": receipt.status == "posted" and dependencies,
        "inventory_rows": inventory_rows,
        "receipt_history": order.goods_receipts.filter(
            organization=request.organization
        )
        .select_related("purchase_order_version")
        .order_by("received_at", "created_at"),
        "stock_evidence": receipt.items.filter(organization=request.organization)
        .select_related("material")
        .prefetch_related("stock_transactions")
        if permitted(request, P.STOCK_TRANSACTIONS_VIEW, receipt.project)
        else [],
        **overrides,
    }
