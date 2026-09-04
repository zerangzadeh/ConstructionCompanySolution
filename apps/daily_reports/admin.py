from django.contrib import admin
from django.http import HttpRequest

from apps.daily_reports.models import (
    DailyActivity,
    DailyReport,
    DailyReportEquipmentEntry,
    DailyReportLaborEntry,
    DailyReportMaterialEntry,
    DelayEvent,
)


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "site",
        "phase",
        "reporting_date",
        "status",
        "organization",
    )
    list_filter = ("status", "organization")
    search_fields = (
        "project__name",
        "site__name",
        "work_performed",
        "organization__name",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "submitted_at",
        "approved_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: DailyReport | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: DailyReport | None = None
    ) -> bool:
        return False


@admin.register(DailyReportLaborEntry)
class DailyReportLaborEntryAdmin(admin.ModelAdmin):
    list_display = ("team_name", "worker_count", "hours_worked", "report")
    list_filter = ("organization",)
    search_fields = ("team_name", "report__project__name", "report__site__name")
    readonly_fields = ("id", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: DailyReportLaborEntry | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: DailyReportLaborEntry | None = None
    ) -> bool:
        return False


@admin.register(DailyReportEquipmentEntry)
class DailyReportEquipmentEntryAdmin(admin.ModelAdmin):
    list_display = ("equipment_name", "hours_used", "report")
    list_filter = ("organization",)
    search_fields = ("equipment_name", "report__project__name", "report__site__name")
    readonly_fields = ("id", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: DailyReportEquipmentEntry | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: DailyReportEquipmentEntry | None = None
    ) -> bool:
        return False


@admin.register(DailyReportMaterialEntry)
class DailyReportMaterialEntryAdmin(admin.ModelAdmin):
    list_display = ("material_name", "quantity", "unit", "report")
    list_filter = ("organization", "unit")
    search_fields = ("material_name", "report__project__name", "report__site__name")
    readonly_fields = ("id", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: DailyReportMaterialEntry | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: DailyReportMaterialEntry | None = None
    ) -> bool:
        return False


@admin.register(DailyActivity)
class DailyActivityAdmin(admin.ModelAdmin):
    list_display = ("description", "activity", "report", "organization", "created_at")
    list_filter = ("organization",)
    search_fields = ("description", "activity__code", "report__project__name")
    readonly_fields = ("id", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: DailyActivity | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: DailyActivity | None = None
    ) -> bool:
        return False


@admin.register(DelayEvent)
class DelayEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_on", "category", "report", "activity", "organization")
    list_filter = ("organization", "status")
    search_fields = ("cause", "category", "report__project__name")
    readonly_fields = ("id", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: DelayEvent | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: DelayEvent | None = None
    ) -> bool:
        return False
