"""Inventory movements only; no stock/value calculations."""

from django.db.models import QuerySet
from django.http import FileResponse

from apps.organizations.models import Organization
from core.xlsx import Column as C
from core.xlsx import Sheet, download

from .models import StockTransaction

MOVEMENT_COLUMNS = (
    C("شماره گردش", "transaction_number"),
    C("پروژه", "project.name"),
    C("انبار مبدأ", "source_warehouse.name"),
    C("انبار مقصد", "destination_warehouse.name"),
    C("مصالح", "material.name"),
    C("واحد", "unit_of_measure.name"),
    C("نوع گردش", "get_transaction_type_display"),
    C("مقدار", "quantity"),
    C("زمان وقوع", "occurred_at"),
    C("وضعیت ثبت", "get_status_display"),
    C("مرجع", "reference"),
    C("رسید کالا", "goods_receipt_item.goods_receipt.receipt_number"),
    C("برگشت گردش", "reversal_of.transaction_number"),
    C(
        "رسید کالای گردش اصلی",
        "reversal_of.goods_receipt_item.goods_receipt.receipt_number",
    ),
)


def movements_download(
    records: QuerySet[StockTransaction], *, organization: Organization
) -> FileResponse:
    records = records.select_related(
        "reversal_of__goods_receipt_item__goods_receipt",
        "goods_receipt_item__goods_receipt",
        "unit_of_measure",
    )
    return download(
        "گردش انبار",
        (Sheet("گردش انبار", MOVEMENT_COLUMNS, records.iterator()),),
        timezone_name=organization.settings.timezone,
    )
