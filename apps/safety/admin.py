from django.contrib import admin
from django.http import HttpRequest

from apps.safety.models import SafetyIncident


@admin.register(SafetyIncident)
class SafetyIncidentAdmin(admin.ModelAdmin):
    list_display = (
        "incident_number",
        "project",
        "occurred_at",
        "severity",
        "status",
        "organization",
    )
    list_filter = ("status", "severity", "incident_type", "organization")
    search_fields = (
        "incident_number",
        "description",
        "project__name",
        "organization__name",
    )
    readonly_fields = tuple(field.name for field in SafetyIncident._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: SafetyIncident | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: SafetyIncident | None = None
    ) -> bool:
        return False
