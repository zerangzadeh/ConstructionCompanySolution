from django.contrib import admin
from django.http import HttpRequest

from apps.documents.models import Document, DocumentLink, DocumentVersion


class ImmutableAdminMixin:
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object = None) -> bool:
        return False


@admin.register(Document)
class DocumentAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "document_type",
        "reference",
        "organization",
        "current_version",
        "archived_at",
        "created_at",
    )
    list_filter = ("document_type", "organization", "archived_at")
    search_fields = ("title", "reference", "description", "organization__name")
    readonly_fields = (
        "id",
        "organization",
        "document_type",
        "title",
        "reference",
        "description",
        "current_version",
        "created_by",
        "updated_by",
        "archive_reason",
        "archived_at",
        "archived_by",
        "created_at",
        "updated_at",
    )


@admin.register(DocumentVersion)
class DocumentVersionAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = (
        "document",
        "version_number",
        "original_file_name",
        "file_size",
        "organization",
        "created_at",
    )
    list_filter = ("organization", "content_type")
    search_fields = (
        "document__title",
        "original_file_name",
        "sha256",
        "organization__name",
    )
    readonly_fields = (
        "id",
        "organization",
        "document",
        "version_number",
        "original_file_name",
        "file",
        "content_type",
        "file_size",
        "sha256",
        "uploaded_by",
        "created_at",
    )


@admin.register(DocumentLink)
class DocumentLinkAdmin(ImmutableAdminMixin, admin.ModelAdmin):
    list_display = ("document", "target_type", "target", "organization", "created_at")
    list_filter = ("organization",)
    search_fields = (
        "document__title",
        "project__name",
        "contract__contract_number",
        "estimate__estimate_number",
        "payment__payment_number",
    )
    readonly_fields = (
        "id",
        "organization",
        "document",
        "project",
        "contract",
        "estimate",
        "expense",
        "payment",
        "daily_report",
        "created_by",
        "created_at",
    )
