from django.contrib import admin
from django.http import HttpRequest

from .models import WorkflowTemplate, WorkflowType


class SystemCatalogAdmin(admin.ModelAdmin):
    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return request.user.is_active and request.user.is_superuser


@admin.register(WorkflowType)
class WorkflowTypeAdmin(SystemCatalogAdmin):
    list_display = ("code", "name", "subject_type", "is_active")
    search_fields = ("code", "name", "subject_type")
    list_filter = ("is_active",)


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(SystemCatalogAdmin):
    list_display = ("code", "name", "workflow_type", "is_active")
    search_fields = ("code", "name", "workflow_type__code")
    list_filter = ("is_active", "workflow_type")
