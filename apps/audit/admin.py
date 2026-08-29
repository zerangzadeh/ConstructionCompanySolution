from django.contrib import admin

from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "action",
        "organization",
        "actor",
        "entity_type",
        "entity_id",
    )
    list_filter = ("action", "created_at")
    search_fields = (
        "entity_id",
        "entity_type",
        "organization__name",
        "actor__username",
    )
    readonly_fields = (
        "id",
        "organization",
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "metadata",
        "created_at",
    )
