from django.contrib import admin
from django.http import HttpRequest

from apps.inventory.models import (
    InventoryCount,
    InventoryCountLine,
    InventoryLot,
    InventoryReservation,
    InventoryReservationAllocation,
    InventorySerial,
    InventoryTransfer,
    InventoryTransferLine,
    MaterialTraceabilityProfile,
    StockTraceAllocation,
    StockTransaction,
    Warehouse,
    WarehouseBin,
)


class ReadOnlyInventoryAdmin(admin.ModelAdmin):
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


@admin.register(Warehouse)
class WarehouseAdmin(ReadOnlyInventoryAdmin):
    list_display = ("code", "name", "project", "organization", "is_active")
    list_filter = ("organization", "project", "is_active")
    search_fields = ("code", "name", "location", "project__code")
    list_select_related = ("project", "organization")


@admin.register(StockTransaction)
class StockTransactionAdmin(ReadOnlyInventoryAdmin):
    list_display = (
        "transaction_number",
        "transaction_type",
        "material",
        "quantity",
        "unit_of_measure",
        "source_warehouse",
        "destination_warehouse",
        "status",
        "organization",
    )
    list_filter = (
        "organization",
        "transaction_type",
        "status",
        "source_warehouse",
        "destination_warehouse",
    )
    search_fields = (
        "transaction_number",
        "material__code",
        "reference",
        "goods_receipt_item__goods_receipt__receipt_number",
    )
    list_select_related = (
        "material",
        "unit_of_measure",
        "source_warehouse",
        "destination_warehouse",
        "project",
        "organization",
    )


for model in (
    WarehouseBin,
    MaterialTraceabilityProfile,
    InventoryLot,
    InventorySerial,
    StockTraceAllocation,
    InventoryReservation,
    InventoryReservationAllocation,
    InventoryCount,
    InventoryCountLine,
    InventoryTransfer,
    InventoryTransferLine,
):
    admin.site.register(model, ReadOnlyInventoryAdmin)
