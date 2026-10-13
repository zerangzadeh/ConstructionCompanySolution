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

    def get_queryset(self, request):
        # Platform audit records are separate from tenant audit workspaces.
        return super().get_queryset(request).filter(organization__isnull=True)

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and (
            obj is None or obj.organization_id is None
        )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
