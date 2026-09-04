from django.contrib import admin
from django.http import HttpRequest

from apps.parties.models import BusinessParty, PartyContact, PartyRole


class ReadOnlyTenantAdmin(admin.ModelAdmin):
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: object | None = None
    ) -> bool:
        return False


@admin.register(BusinessParty)
class BusinessPartyAdmin(ReadOnlyTenantAdmin):
    list_display = ("display_name", "party_kind", "organization", "archived_at")
    list_filter = ("party_kind", "organization")
    search_fields = ("display_name", "legal_name", "tax_identifier")


@admin.register(PartyRole)
class PartyRoleAdmin(ReadOnlyTenantAdmin):
    list_display = ("party", "role", "organization", "is_active")
    list_filter = ("role", "organization", "is_active")


@admin.register(PartyContact)
class PartyContactAdmin(ReadOnlyTenantAdmin):
    list_display = ("party", "contact_type", "value", "organization", "is_primary")
    list_filter = ("contact_type", "organization", "is_primary")
