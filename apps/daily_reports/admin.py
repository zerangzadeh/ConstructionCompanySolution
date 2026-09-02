from django.contrib import admin

from apps.daily_reports.models import (
    DailyReport,
    DailyReportEquipmentEntry,
    DailyReportLaborEntry,
    DailyReportMaterialEntry,
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


@admin.register(DailyReportLaborEntry)
class DailyReportLaborEntryAdmin(admin.ModelAdmin):
    list_display = ("team_name", "worker_count", "hours_worked", "report")
    list_filter = ("organization",)
    search_fields = ("team_name", "report__project__name", "report__site__name")
    readonly_fields = ("id", "created_at")


@admin.register(DailyReportEquipmentEntry)
class DailyReportEquipmentEntryAdmin(admin.ModelAdmin):
    list_display = ("equipment_name", "hours_used", "report")
    list_filter = ("organization",)
    search_fields = ("equipment_name", "report__project__name", "report__site__name")
    readonly_fields = ("id", "created_at")


@admin.register(DailyReportMaterialEntry)
class DailyReportMaterialEntryAdmin(admin.ModelAdmin):
    list_display = ("material_name", "quantity", "unit", "report")
    list_filter = ("organization", "unit")
    search_fields = ("material_name", "report__project__name", "report__site__name")
    readonly_fields = ("id", "created_at")
