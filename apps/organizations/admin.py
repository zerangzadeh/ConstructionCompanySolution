from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.forms import (
    ORGANIZATION_PROFILE_FIELDS,
    OrganizationAdminForm,
    OrganizationMembershipForm,
)
from apps.organizations.models import (
    BusinessPermission,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.permission_catalog import permission_group_label
from apps.organizations.services import (
    create_organization_by_system_admin,
    update_organization_membership,
    update_organization_settings,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    form = OrganizationAdminForm
    list_display = (
        "name",
        "national_id",
        "slug",
        "status",
        "currency",
        "created_at",
    )
    list_filter = ("status", "currency")
    search_fields = (
        "name",
        "legal_name",
        "slug",
        "registration_number",
        "national_id",
        "economic_code",
    )
    readonly_fields = (
        "status",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
        "archived_at",
        "deleted_at",
    )
    fieldsets = (
        (
            "مشخصات پایه شرکت",
            {
                "fields": (
                    "name",
                    "legal_name",
                    "slug",
                    "registration_number",
                    "national_id",
                    "economic_code",
                )
            },
        ),
        (
            "اطلاعات تماس و نشانی",
            {
                "fields": (
                    "phone",
                    "email",
                    "website",
                    "province",
                    "city",
                    "address",
                    "postal_code",
                )
            },
        ),
        (
            "تنظیمات محلی و مالی",
            {
                "fields": (
                    "logo",
                    "language",
                    "settings_timezone",
                    "default_currency",
                    "fiscal_year_start_month",
                    "fiscal_year_start_day",
                )
            },
        ),
        (
            "شماره‌گذاری",
            {
                "fields": (
                    "project_code_prefix",
                    "contract_code_prefix",
                    "site_code_prefix",
                    "document_code_prefix",
                )
            },
        ),
        (
            "وضعیت و تاریخچه",
            {
                "fields": (
                    "status",
                    "archived_at",
                    "deleted_at",
                    "created_by",
                    "updated_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def save_model(
        self,
        request: HttpRequest,
        obj: Organization,
        form: OrganizationAdminForm,
        change: bool,
    ) -> None:
        """Persist both admin form sections through the tenant services."""

        if change:
            update_organization_settings(
                organization=obj,
                updated_by=request.user,
                timezone_name=form.cleaned_data["settings_timezone"],
                currency=form.cleaned_data["default_currency"],
                fiscal_year_start_month=form.cleaned_data["fiscal_year_start_month"],
                fiscal_year_start_day=form.cleaned_data["fiscal_year_start_day"],
                language=form.cleaned_data["language"],
                project_code_prefix=form.cleaned_data["project_code_prefix"],
                contract_code_prefix=form.cleaned_data["contract_code_prefix"],
                site_code_prefix=form.cleaned_data["site_code_prefix"],
                document_code_prefix=form.cleaned_data["document_code_prefix"],
                logo=form.cleaned_data["logo"],
                profile_data={
                    field_name: form.cleaned_data[field_name]
                    for field_name in ORGANIZATION_PROFILE_FIELDS
                },
            )
            obj.refresh_from_db()
            return

        organization = create_organization_by_system_admin(
            actor=request.user,
            owner=request.user,
            name=form.cleaned_data["name"],
            legal_name=form.cleaned_data["legal_name"],
            slug=form.cleaned_data["slug"],
            registration_number=form.cleaned_data["registration_number"],
            national_id=form.cleaned_data["national_id"],
            economic_code=form.cleaned_data["economic_code"],
            phone=form.cleaned_data["phone"],
            email=form.cleaned_data["email"],
            website=form.cleaned_data["website"],
            province=form.cleaned_data["province"],
            city=form.cleaned_data["city"],
            address=form.cleaned_data["address"],
            postal_code=form.cleaned_data["postal_code"],
            timezone_name=form.cleaned_data["settings_timezone"],
            currency=form.cleaned_data["default_currency"],
            logo=form.cleaned_data["logo"],
            language=form.cleaned_data["language"],
            fiscal_year_start_month=form.cleaned_data["fiscal_year_start_month"],
            fiscal_year_start_day=form.cleaned_data["fiscal_year_start_day"],
            project_code_prefix=form.cleaned_data["project_code_prefix"],
            contract_code_prefix=form.cleaned_data["contract_code_prefix"],
            site_code_prefix=form.cleaned_data["site_code_prefix"],
            document_code_prefix=form.cleaned_data["document_code_prefix"],
        )
        obj.pk = organization.pk
        obj._state.adding = False

    def has_change_permission(
        self, request: HttpRequest, obj: Organization | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: Organization | None = None
    ) -> bool:
        return False


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    """Allow only system admins to manage a user's scoped business access."""

    form = OrganizationMembershipForm
    list_display = (
        "user",
        "organization",
        "role_definition",
        "status",
        "assigned_by",
        "joined_at",
    )
    list_filter = ("role_definition", "status")
    search_fields = ("user__username", "organization__name")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: OrganizationMembership | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: OrganizationMembership | None = None
    ) -> bool:
        return False

    def get_form(
        self,
        request: HttpRequest,
        obj: OrganizationMembership | None = None,
        **kwargs: object,
    ) -> type[forms.ModelForm]:
        """Permit a system admin to assign the owner role when appropriate."""

        form_class = super().get_form(request, obj, **kwargs)

        class SystemOrganizationMembershipForm(form_class):
            def __init__(self, *args: object, **form_kwargs: object) -> None:
                form_kwargs["allow_owner_role"] = True
                super().__init__(*args, **form_kwargs)

        return SystemOrganizationMembershipForm

    def save_model(
        self,
        request: HttpRequest,
        obj: OrganizationMembership,
        form: OrganizationMembershipForm,
        change: bool,
    ) -> None:
        if not change:  # Defensive: creation is intentionally disabled.
            return
        update_organization_membership(
            organization=obj.organization,
            actor=request.user,
            membership=obj,
            role=form.cleaned_data["role_definition"],
            status=form.cleaned_data["status"],
        )


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


class BusinessPermissionChoiceField(forms.ModelMultipleChoiceField):
    """Display the tenant permission catalog grouped by business area."""

    def label_from_instance(self, permission: BusinessPermission) -> str:
        group = permission_group_label(permission.code)
        return f"{group} | {permission.name} | {permission.code}"


class OrganizationRoleAdminForm(forms.ModelForm):
    permissions = BusinessPermissionChoiceField(
        label="کاتالوگ مجوزهای سازمانی",
        queryset=BusinessPermission.objects.filter(is_active=True).order_by("code"),
        required=False,
        widget=FilteredSelectMultiple("مجوزهای سازمانی", is_stacked=False),
        help_text=(
            "هر گزینه یک عملیات واقعی و کنترل‌شده در محدوده شرکت فعال است. "
            "برای یافتن حوزه یا کد مجوز از جست‌وجوی فهرست استفاده کنید."
        ),
    )

    class Meta:
        model = OrganizationRole
        fields = "__all__"


@admin.register(OrganizationRole)
class OrganizationRoleAdmin(admin.ModelAdmin):
    """Let only the system admin compose global roles from implemented permissions."""

    form = OrganizationRoleAdminForm
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
                "description": (
                    "مجوزها بر اساس مدل یا حوزه کسب‌وکار و عملیات قابل استفاده "
                    "گروه‌بندی شده‌اند و در سرویس‌های tenant-aware اعمال می‌شوند."
                ),
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
