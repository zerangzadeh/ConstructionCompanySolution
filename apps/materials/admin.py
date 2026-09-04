from django.contrib import admin
from django.http import HttpRequest

from apps.materials.models import Material, MaterialCategory, UnitOfMeasure


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "symbol",
        "organization",
        "is_active",
        "archived_at",
    )
    list_filter = ("category", "organization", "is_active")
    search_fields = ("code", "name", "symbol")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: UnitOfMeasure | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: UnitOfMeasure | None = None
    ) -> bool:
        return False


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "parent",
        "organization",
        "is_active",
        "archived_at",
    )
    list_filter = ("organization", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: MaterialCategory | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: MaterialCategory | None = None
    ) -> bool:
        return False


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "unit_of_measure",
        "organization",
        "is_active",
    )
    list_filter = ("organization", "category", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at", "updated_at")
    list_select_related = ("category", "unit_of_measure", "organization")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Material | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Material | None = None
    ) -> bool:
        return False
