from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.forms import OrganizationForm
from apps.organizations.models import (
    BusinessPermission,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.services import create_organization_by_system_admin


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    form = OrganizationForm
    list_display = ("name", "slug", "status", "currency", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("name", "legal_name", "slug")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

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

        organization = create_organization_by_system_admin(
            actor=request.user,
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
    list_display = ("user", "organization", "role_definition", "status", "joined_at")
    list_filter = ("role_definition", "status")
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
        "role_definition",
        "status",
        "expires_at",
        "created_at",
    )
    list_filter = ("role_definition", "status")
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


@admin.register(BusinessPermission)
class BusinessPermissionAdmin(admin.ModelAdmin):
    """Expose the code-owned permission catalogue without allowing ad-hoc codes."""

    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "description")
    readonly_fields = (
        "code",
        "name",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    )

    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_view_permission(
        self, request: HttpRequest, obj: BusinessPermission | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: BusinessPermission | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: BusinessPermission | None = None
    ) -> bool:
        return False


@admin.register(OrganizationRole)
class OrganizationRoleAdmin(admin.ModelAdmin):
    """Let only the system admin compose global roles from implemented permissions."""

    list_display = ("name", "code", "is_active", "is_system", "is_owner", "updated_at")
    list_filter = ("is_active", "is_system", "is_owner")
    search_fields = ("name", "code", "description")
    filter_horizontal = ("permissions",)
    readonly_fields = ("created_by", "updated_by", "created_at", "updated_at")
    fieldsets = (
        (
            "مشخصات نقش",
            {"fields": ("name", "code", "description", "is_active")},
        ),
        (
            "مجوزهای کسب‌وکار",
            {
                "fields": ("permissions",),
                "description": "مجوزهایی را انتخاب کنید که در سرویس‌های سامانه پیاده‌سازی شده‌اند.",
            },
        ),
        (
            "اطلاعات سیستمی",
            {
                "fields": (
                    "is_system",
                    "is_owner",
                    "created_by",
                    "updated_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_view_permission(
        self, request: HttpRequest, obj: OrganizationRole | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_change_permission(
        self, request: HttpRequest, obj: OrganizationRole | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: OrganizationRole | None = None
    ) -> bool:
        return bool(
            request.user.is_superuser
            and obj is not None
            and not obj.is_system
            and not obj.memberships.exists()
            and not obj.invitations.exists()
        )

    def get_readonly_fields(
        self, request: HttpRequest, obj: OrganizationRole | None = None
    ) -> tuple[str, ...]:
        fields = tuple(super().get_readonly_fields(request, obj))
        if obj is not None:
            return fields + ("code", "is_system", "is_owner")
        return fields + ("is_system", "is_owner")

    def save_model(
        self,
        request: HttpRequest,
        obj: OrganizationRole,
        form,
        change: bool,
    ) -> None:
        if not request.user.is_superuser:
            raise PermissionDenied("فقط ادمین سامانه می‌تواند نقش‌ها را مدیریت کند.")
        if change:
            request._previous_role_permissions = set(
                OrganizationRole.objects.get(pk=obj.pk).permissions.values_list(
                    "code", flat=True
                )
            )
        obj.updated_by = request.user
        if not change:
            obj.created_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_audit_event(
            action=AuditAction.ROLE_UPDATED if change else AuditAction.ROLE_CREATED,
            entity_type="organization_role",
            entity_id=obj.pk,
            actor=request.user,
            metadata={"code": obj.code, "name": obj.name, "is_active": obj.is_active},
        )

    def save_related(self, request, form, formsets, change: bool) -> None:
        super().save_related(request, form, formsets, change)
        previous = getattr(request, "_previous_role_permissions", set())
        current = set(form.instance.permissions.values_list("code", flat=True))
        if previous != current:
            record_audit_event(
                action=AuditAction.ROLE_PERMISSIONS_CHANGED,
                entity_type="organization_role",
                entity_id=form.instance.pk,
                actor=request.user,
                metadata={
                    "code": form.instance.code,
                    "previous_permissions": sorted(previous),
                    "new_permissions": sorted(current),
                },
            )

    def delete_model(self, request: HttpRequest, obj: OrganizationRole) -> None:
        if not self.has_delete_permission(request, obj):
            raise PermissionDenied(
                "فقط نقش سفارشیِ استفاده‌نشده توسط ادمین سامانه قابل حذف است."
            )
        record_audit_event(
            action=AuditAction.ROLE_DELETED,
            entity_type="organization_role",
            entity_id=obj.pk,
            actor=request.user,
            metadata={"code": obj.code, "name": obj.name},
        )
        super().delete_model(request, obj)
