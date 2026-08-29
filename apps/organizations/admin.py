from django.contrib import admin

from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "currency", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("name", "legal_name", "slug")
    readonly_fields = ("created_at", "updated_at")


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "status", "joined_at")
    list_filter = ("role", "status")
    search_fields = ("user__username", "organization__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "invitee",
        "organization",
        "role",
        "status",
        "expires_at",
        "created_at",
    )
    list_filter = ("role", "status")
    search_fields = ("invitee__username", "organization__name")
    readonly_fields = ("token_hash", "created_at", "updated_at", "accepted_at")
