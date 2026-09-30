from django.contrib import admin
from django.http import HttpRequest

from apps.parties.models import (
    BusinessParty,
    PartyAlias,
    PartyClassification,
    PartyClassificationAssignment,
    PartyContact,
    PartyIdentitySnapshot,
    PartyRepresentative,
    PartyRestriction,
    PartyRole,
)


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


@admin.register(PartyIdentitySnapshot)
class PartyIdentitySnapshotAdmin(ReadOnlyTenantAdmin):
    readonly_fields = ("id", "recorded_at")
    list_display = ("party", "sequence", "organization", "recorded_at")
    list_filter = ("organization", "party_kind")
    search_fields = ("display_name", "legal_name", "tax_identifier")


@admin.register(PartyRestriction)
class PartyRestrictionAdmin(ReadOnlyTenantAdmin):
    list_display = (
        "party",
        "scope",
        "code",
        "effect",
        "effective_from",
        "effective_until",
        "revoked_at",
    )
    list_filter = ("organization", "scope", "effect")


@admin.register(PartyAlias)
class PartyAliasAdmin(ReadOnlyTenantAdmin):
    list_display = ("party", "alias_type", "value", "organization", "created_at")
    list_filter = ("organization", "alias_type")
    search_fields = ("value", "normalized_value")


@admin.register(PartyClassification)
class PartyClassificationAdmin(ReadOnlyTenantAdmin):
    list_display = ("name", "code", "kind", "organization", "archived_at")
    list_filter = ("organization", "kind")


@admin.register(PartyClassificationAssignment)
class PartyClassificationAssignmentAdmin(ReadOnlyTenantAdmin):
    list_display = ("party", "classification", "assigned_at", "revoked_at")
    list_filter = ("organization",)


@admin.register(PartyRepresentative)
class PartyRepresentativeAdmin(ReadOnlyTenantAdmin):
    list_display = (
        "party",
        "full_name",
        "authority",
        "effective_from",
        "effective_until",
        "revoked_at",
    )
    list_filter = ("organization", "authority")
