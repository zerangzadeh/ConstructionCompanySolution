from django.contrib import admin
from django.http import HttpRequest

from apps.quality.models import QualityIssue


@admin.register(QualityIssue)
class QualityIssueAdmin(admin.ModelAdmin):
    list_display = (
        "issue_number",
        "project",
        "identified_at",
        "severity",
        "status",
        "organization",
    )
    list_filter = ("status", "severity", "issue_type", "organization")
    search_fields = (
        "issue_number",
        "description",
        "specification_reference",
        "project__name",
        "organization__name",
    )
    readonly_fields = tuple(field.name for field in QualityIssue._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: QualityIssue | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: QualityIssue | None = None
    ) -> bool:
        return False
