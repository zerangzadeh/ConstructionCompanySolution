from typing import ClassVar

from django.contrib import admin
from django.http import HttpRequest

from apps.estimates.models import Estimate, EstimateItem


class EstimateItemInline(admin.TabularInline):
    model = EstimateItem
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = (
        "estimate_number",
        "title",
        "organization",
        "project",
        "phase",
        "status",
    )
    list_filter = ("status", "organization")
    search_fields = (
        "estimate_number",
        "title",
        "project__name",
        "phase__name",
        "organization__name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    inlines: ClassVar = [EstimateItemInline]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Estimate | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Estimate | None = None
    ) -> bool:
        return False
