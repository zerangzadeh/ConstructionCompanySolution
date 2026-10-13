from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.organizations.forms import (
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


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    form = OrganizationAdminForm
    list_display = (
        "name",
        "national_id",
        "slug",
        "status",
        "authoritative_currency",
        "created_at",
    )
    list_filter = ("status", "settings__currency")
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
        return False

    @admin.display(description="واحد پول", ordering="settings__currency")
    def authoritative_currency(self, obj: Organization) -> str:
        return obj.settings.currency

    def save_model(
        self,
        request: HttpRequest,
        obj: Organization,
        form: OrganizationAdminForm,
        change: bool,
    ) -> None:
        raise PermissionDenied(
            "ایجاد یا ویرایش Tenant از Django Admin غیرفعال است؛ "
            "از مسیر کنترل‌شده پلتفرم استفاده کنید."
        )

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
    """Legacy membership rows are not mutable or visible through global admin."""

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
        return False

    def has_module_permission(self, request: HttpRequest) -> bool:
        return False

    def has_view_permission(
        self, request: HttpRequest, obj: OrganizationMembership | None = None
    ) -> bool:
        return False

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
        raise PermissionDenied(
            "مدیریت عضویت از Django Admin غیرفعال است؛ از مسیر Tenant استفاده کنید."
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
    """Expose the code-owned role catalogue as read-only platform metadata."""

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

    def get_queryset(self, request: HttpRequest):
        # Tenant custom roles are governed through the tenant role workspace.
        return super().get_queryset(request).filter(organization__isnull=True)

    def has_view_permission(
        self, request: HttpRequest, obj: OrganizationRole | None = None
    ) -> bool:
        return request.user.is_superuser and (
            obj is None or obj.organization_id is None
        )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: OrganizationRole | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: OrganizationRole | None = None
    ) -> bool:
        return False

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
        raise PermissionDenied(
            "کاتالوگ نقش‌های سامانه فقط از طریق migration قابل تغییر است."
        )

    def save_related(self, request, form, formsets, change: bool) -> None:
        raise PermissionDenied(
            "کاتالوگ نقش‌های سامانه فقط از طریق migration قابل تغییر است."
        )

    def delete_model(self, request: HttpRequest, obj: OrganizationRole) -> None:
        raise PermissionDenied(
            "کاتالوگ نقش‌های سامانه فقط از طریق migration قابل تغییر است."
        )
