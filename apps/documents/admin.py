from django.contrib import admin
from django.http import HttpRequest

from apps.documents.models import ProjectDocument


@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "document_type",
        "organization",
        "project",
        "payment",
        "file_size",
        "created_at",
    )
    list_filter = ("document_type", "organization")
    search_fields = (
        "title",
        "original_file_name",
        "project__name",
        "payment__payment_number",
        "organization__name",
    )
    readonly_fields = (
        "id",
        "original_file_name",
        "content_type",
        "file_size",
        "sha256",
        "created_at",
        "archived_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: ProjectDocument | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: ProjectDocument | None = None
    ) -> bool:
        return False
