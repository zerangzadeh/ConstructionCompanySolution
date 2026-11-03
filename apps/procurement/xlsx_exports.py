"""Operational Procurement fields; no quote/confidential payload or new totals."""

from django.db.models import Prefetch, QuerySet
from django.http import FileResponse

from apps.organizations.models import Organization
from core.xlsx import Column as C
from core.xlsx import Sheet, download

from . import models as m

REQUEST_COLUMNS = (
    C("شماره درخواست خرید", "request_number"),
    C("عنوان", "title", 40),
    C("پروژه", "project.name"),
    C("تاریخ نیاز", "required_by"),
    C("وضعیت", "get_status_display"),
)
RFQ_COLUMNS = (
    C("شماره استعلام", "rfq_number"),
    C("عنوان", "title", 40),
    C("پروژه", "project.name"),
    C("درخواست خرید", "purchase_request.request_number"),
    C("نسخه صادرشده", "current_version_number"),
    C("مهلت دریافت", "closing_at"),
    C("وضعیت", "get_status_display"),
)
ORDER_COLUMNS = (
    C("شماره سفارش خرید", "order_number"),
    C("پروژه", "project.name"),
    C("تأمین‌کننده", "supplier.display_name"),
    C("درخواست خرید", "purchase_request.request_number"),
    C(
        "استعلام منبع",
        "source_award.comparison.commercial_scope.rfq_version.rfq.rfq_number",
    ),
    C(
        "نسخه استعلام منبع",
        "source_award.comparison.commercial_scope.rfq_version.version_number",
    ),
    C("نسخه سفارش", "current_version.version_number"),
    C("تاریخ سفارش", "order_date"),
    C("تحویل موردانتظار", "expected_delivery_date"),
    C("وضعیت", "get_status_display"),
    C("مبلغ کل ثبت‌شده", "total_amount"),
)
RECEIPT_COLUMNS = (
    C("شماره رسید کالا", "receipt_number"),
    C("پروژه", "project.name"),
    C("شماره سفارش خرید", "purchase_order.order_number"),
    C("نسخه سفارش مبنا", "purchase_order_version.version_number"),
    C("زمان دریافت", "received_at"),
    C("وضعیت", "get_status_display"),
)
ITEM_COLUMNS = (
    C("مصالح", "material.name"),
    C("شرح ردیف", "description", 48),
    C("واحد", "unit_of_measure.name"),
    C("مقدار", "quantity"),
)


def procurement_download(
    kind: str, records: QuerySet, *, organization: Organization
) -> FileResponse:
    if kind == "request":
        name, columns, relation, model = (
            "درخواست‌های خرید",
            REQUEST_COLUMNS,
            "items",
            m.PurchaseRequestItem,
        )
        line_columns = (
            C("درخواست خرید", "purchase_request.request_number"),
            *ITEM_COLUMNS,
        )
        related = ("material", "unit_of_measure")
    elif kind == "rfq":
        name, columns, relation, model = (
            "استعلام‌های خرید",
            RFQ_COLUMNS,
            "lines",
            m.RequestForQuotationLine,
        )
        line_columns = (C("شماره استعلام", "rfq.rfq_number"), *ITEM_COLUMNS)
        related = ("material", "unit_of_measure")
    elif kind == "order":
        name, columns, relation, model = (
            "سفارش‌های خرید",
            ORDER_COLUMNS,
            "items",
            m.PurchaseOrderItem,
        )
        records = records.select_related(
            "current_version",
            "source_award__comparison__commercial_scope__rfq_version__rfq",
        )
        line_columns = (
            C("سفارش خرید", "purchase_order.order_number"),
            *ITEM_COLUMNS,
            C("قیمت واحد ثبت‌شده", "unit_price"),
            C("مبلغ ردیف ثبت‌شده", "line_total"),
            C("ردیف درخواست خرید", "purchase_request_item.description", 48),
            C(
                "شرح قلم انتخاب تأمین‌کننده",
                "source_award_allocation.award.comparison.commercial_scope.rfq_version_line.description",
                48,
            ),
        )
        related = (
            "material",
            "unit_of_measure",
            "purchase_request_item",
            "source_award_allocation__award__comparison__commercial_scope__rfq_version_line",
        )
    elif kind == "receipt":
        name, columns, relation, model = (
            "رسیدهای کالا",
            RECEIPT_COLUMNS,
            "items",
            m.GoodsReceiptItem,
        )
        records = records.select_related("purchase_order_version")
        line_columns = (
            C("رسید کالا", "goods_receipt.receipt_number"),
            C("ردیف سفارش خرید", "purchase_order_item.description", 48),
            C("مصالح", "material.name"),
            C("واحد", "unit_of_measure.name"),
            C("مقدار دریافت‌شده", "quantity"),
        )
        related = ("material", "unit_of_measure", "purchase_order_item")
    else:
        raise ValueError("Unsupported Procurement export")
    records = list(
        records.prefetch_related(
            Prefetch(
                relation,
                queryset=model.objects.select_related(*related).order_by(
                    *(
                        ("created_at", "pk")
                        if kind == "receipt"
                        else ("sort_order", "pk")
                    )
                ),
            )
        )
    )
    return download(
        name,
        (
            Sheet(name, columns, records),
            Sheet(
                "اقلام",
                line_columns,
                (i for r in records for i in getattr(r, relation).all()),
            ),
        ),
        timezone_name=organization.settings.timezone,
    )
