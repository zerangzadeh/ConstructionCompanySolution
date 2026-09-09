from django.contrib import admin
from django.http import HttpRequest

from apps.organizations.forms import OrganizationForm
from apps.organizations.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationSettings,
)
from apps.organizations.services import create_organization_with_owner


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    form = OrganizationForm
    list_display = ("name", "slug", "status", "currency", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("name", "legal_name", "slug")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return super().has_add_permission(request)

    def save_model(
        self,
        request: HttpRequest,
        obj: Organization,
        form: OrganizationForm,
        change: bool,
    ) -> None:
        """Create new tenants through the service that establishes ownership."""

        if change:
            super().save_model(request, obj, form, change)
            return

        organization = create_organization_with_owner(
            owner=request.user,
            name=form.cleaned_data["name"],
            legal_name=form.cleaned_data["legal_name"],
            slug=form.cleaned_data["slug"],
            timezone_name=form.cleaned_data["timezone"],
            currency=form.cleaned_data["currency"],
        )
        obj.pk = organization.pk
        obj._state.adding = False

    def has_change_permission(
        self, request: HttpRequest, obj: Organization | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Organization | None = None
    ) -> bool:
        return False


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "status", "joined_at")
    list_filter = ("role", "status")
    search_fields = ("user__username", "organization__name")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: OrganizationMembership | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: OrganizationMembership | None = None
    ) -> bool:
        return False


@admin.register(OrganizationSettings)
class OrganizationSettingsAdmin(admin.ModelAdmin):
    list_display = ("organization", "timezone", "currency", "fiscal_year_start_month")
    search_fields = ("organization__name", "organization__slug")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: OrganizationSettings | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: OrganizationSettings | None = None
    ) -> bool:
        return False


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

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: OrganizationInvitation | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: OrganizationInvitation | None = None
    ) -> bool:
        return False
