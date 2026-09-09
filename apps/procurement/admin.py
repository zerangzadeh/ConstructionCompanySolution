from django.contrib import admin
from django.http import HttpRequest

from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
)


class ReadOnlyProcurementAdmin(admin.ModelAdmin):
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(ReadOnlyProcurementAdmin):
    list_display = (
        "request_number",
        "title",
        "project",
        "status",
        "required_by",
        "organization",
    )
    list_filter = ("organization", "project", "status")
    search_fields = ("request_number", "title", "project__code")
    list_select_related = ("project", "organization", "created_by", "approved_by")


@admin.register(PurchaseRequestItem)
class PurchaseRequestItemAdmin(ReadOnlyProcurementAdmin):
    list_display = (
        "purchase_request",
        "material",
        "quantity",
        "unit_of_measure",
        "organization",
    )
    list_filter = ("organization", "unit_of_measure")
    search_fields = (
        "purchase_request__request_number",
        "material__code",
        "description",
    )
    list_select_related = (
        "purchase_request",
        "material",
        "unit_of_measure",
        "organization",
    )


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(ReadOnlyProcurementAdmin):
    list_display = (
        "order_number",
        "project",
        "supplier",
        "order_date",
        "status",
        "organization",
    )
    list_filter = ("organization", "project", "supplier", "status")
    search_fields = ("order_number", "project__code", "supplier__display_name")
    list_select_related = (
        "project",
        "supplier",
        "purchase_request",
        "organization",
    )


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(ReadOnlyProcurementAdmin):
    list_display = (
        "purchase_order",
        "material",
        "quantity",
        "unit_of_measure",
        "unit_price",
        "organization",
    )
    list_filter = ("organization", "unit_of_measure")
    search_fields = ("purchase_order__order_number", "material__code", "description")
    list_select_related = (
        "purchase_order",
        "purchase_request_item",
        "material",
        "unit_of_measure",
        "organization",
    )


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(ReadOnlyProcurementAdmin):
    list_display = (
        "receipt_number",
        "purchase_order",
        "project",
        "received_at",
        "status",
        "organization",
    )
    list_filter = ("organization", "project", "status")
    search_fields = ("receipt_number", "purchase_order__order_number", "project__code")
    list_select_related = ("purchase_order", "project", "organization")


@admin.register(GoodsReceiptItem)
class GoodsReceiptItemAdmin(ReadOnlyProcurementAdmin):
    list_display = (
        "goods_receipt",
        "purchase_order_item",
        "material",
        "quantity",
        "unit_of_measure",
        "organization",
    )
    list_filter = ("organization", "unit_of_measure")
    search_fields = ("goods_receipt__receipt_number", "material__code")
    list_select_related = (
        "goods_receipt",
        "purchase_order_item",
        "material",
        "unit_of_measure",
        "organization",
    )
