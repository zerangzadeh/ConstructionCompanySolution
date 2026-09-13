from django.contrib import admin
from django.http import HttpRequest

from apps.equipment.models import Equipment, EquipmentAssignment, MaintenanceRecord


class ReadOnlyEquipmentAdmin(admin.ModelAdmin):
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


@admin.register(Equipment)
class EquipmentAdmin(ReadOnlyEquipmentAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "ownership_type",
        "status",
        "organization",
    )
    list_filter = ("organization", "category", "ownership_type", "status")
    search_fields = ("code", "name", "serial_number", "registration_number")
    list_select_related = ("organization",)


@admin.register(EquipmentAssignment)
class EquipmentAssignmentAdmin(ReadOnlyEquipmentAdmin):
    list_display = (
        "equipment",
        "project",
        "site",
        "start_date",
        "end_date",
        "status",
        "organization",
    )
    list_filter = ("organization", "project", "site", "status")
    search_fields = ("equipment__code", "equipment__name", "project__code")
    list_select_related = ("equipment", "project", "site", "organization")


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(ReadOnlyEquipmentAdmin):
    list_display = (
        "record_number",
        "equipment",
        "maintenance_type",
        "scheduled_date",
        "status",
        "cost",
        "organization",
    )
    list_filter = ("organization", "maintenance_type", "status", "scheduled_date")
    search_fields = ("record_number", "equipment__code", "summary")
    list_select_related = (
        "equipment",
        "project",
        "site",
        "provider",
        "organization",
    )
