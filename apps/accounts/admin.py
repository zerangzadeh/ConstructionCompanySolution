from typing import Any, ClassVar

from django import forms
from django.apps import apps
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    ReadOnlyPasswordHashWidget,
    UserChangeForm,
)
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.contrib.auth.models import Group, Permission
from django.db import models
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import AccountStatus, LoginPageSettings, User
from apps.accounts.widgets import RtlClearableFileInput
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationRole,
    OrganizationStatus,
)
from apps.organizations.services import (
    provision_user_for_organization,
    update_organization_membership,
)


class PersianPermissionChoiceField(forms.ModelMultipleChoiceField):
    """Present permission names in Persian without changing stored permissions."""

    _ACTION_LABELS: ClassVar[dict[str, str]] = {
        "add": "افزودن",
        "change": "ویرایش",
        "delete": "حذف",
        "view": "مشاهده",
    }

    def label_from_instance(self, permission: Permission) -> str:
        model_class = permission.content_type.model_class()
        model_label = (
            str(model_class._meta.verbose_name)
            if model_class is not None
            else permission.content_type.model
        )
        app_label = str(
            apps.get_app_config(permission.content_type.app_label).verbose_name
        )
        action = permission.codename.partition("_")[0]
        action_label = self._ACTION_LABELS.get(action)
        permission_label = (
            f"امکان {action_label} {model_label}"
            if action_label is not None
            else permission.name
        )
        return f"{app_label} | {model_label} | {permission_label}"


class PersianPasswordStatusWidget(ReadOnlyPasswordHashWidget):
    """Show password state without exposing password-hash implementation details."""

    template_name = "accounts/widgets/password_status.html"

    def get_context(
        self,
        name: str,
        value: str | None,
        attrs: dict[str, Any] | None,
    ) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        password_is_usable = bool(
            value and not value.startswith(UNUSABLE_PASSWORD_PREFIX)
        )
        context["password_is_usable"] = password_is_usable
        context["button_label"] = (
            "تغییر گذرواژه" if password_is_usable else "تنظیم گذرواژه"
        )
        return context


class PersianUserChangeForm(UserChangeForm):
    account_status = forms.ChoiceField(
        choices=AccountStatus.choices,
        label="وضعیت حساب",
        help_text="کاربر مسدود یا غیرفعال امکان ورود به سامانه را ندارد.",
    )
    # Business access is granted only through an organization membership role.
    # Explicitly shadow Django's inherited direct-permission field so it cannot
    # be submitted to, or persisted through, this form.
    groups = None
    user_permissions = None

    class Meta(UserChangeForm.Meta):
        model = User
        exclude = ("groups", "user_permissions")

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["password"].label = "گذرواژه"
        self.fields["password"].help_text = ""
        self.fields["password"].widget = PersianPasswordStatusWidget()
        self.fields["is_staff"].label = "دسترسی به پنل مدیریت سامانه"
        self.fields["is_staff"].help_text = (
            "اجازه ورود به پنل فنی مدیریت سامانه را می‌دهد و دسترسی عملیاتی "
            "سازمانی ایجاد نمی‌کند."
        )
        self.fields["is_superuser"].label = "دسترسی کامل فنی سامانه"
        self.fields["is_superuser"].help_text = (
            "تمام مجوزهای پنل مدیریت سامانه را بدون نیاز به تخصیص صریح فراهم "
            "می‌کند. فقط برای مدیران فنی مورداعتماد استفاده شود."
        )
        if self.instance.pk:
            self.initial["account_status"] = self.instance.account_status

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        status = self.cleaned_data["account_status"]
        if status == AccountStatus.BLOCKED:
            user.blocked_at = user.blocked_at or timezone.now()
            user.is_active = False
        else:
            user.blocked_at = None
            user.is_active = status == AccountStatus.ACTIVE
        if commit:
            user.save()
            self.save_m2m()
        return user


class PersianUserCreationForm(AdminUserCreationForm):
    """Create an account with an initial organization role."""

    organization = forms.ModelChoiceField(
        label="شرکت",
        queryset=Organization.objects.none(),
        help_text=("عضویت اولیه کاربر فقط در همین شرکت ایجاد می‌شود."),
    )
    role_definition = forms.ModelChoiceField(
        label="نقش سازمانی اولیه",
        queryset=OrganizationRole.objects.none(),
        to_field_name="code",
        help_text=(
            "این مورد سطح دسترسی به سامانه را تعیین می‌کند و سمت شغلی فرد نیست. "
            "با ذخیره، عضویت کاربر فعال و این نقش به آن تخصیص داده می‌شود."
        ),
    )

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "national_id",
            "email",
            "phone_number",
        )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = Organization.objects.filter(
            status=OrganizationStatus.ACTIVE,
            deleted_at__isnull=True,
            archived_at__isnull=True,
        ).order_by("name")
        self.fields["role_definition"].queryset = OrganizationRole.objects.filter(
            is_active=True
        ).order_by("name")


class PersianGroupAdminForm(forms.ModelForm):
    permissions = PersianPermissionChoiceField(
        queryset=Permission.objects.select_related("content_type"),
        required=False,
        label="مجوزها",
        widget=FilteredSelectMultiple("مجوزها", is_stacked=False),
    )

    class Meta:
        model = Group
        fields = "__all__"


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin configuration for the custom username-based user."""

    form = PersianUserChangeForm
    add_form = PersianUserCreationForm
    change_form_template = "admin/accounts/user/change_form.html"
    list_display = (
        "username",
        "national_id",
        "email",
        "account_status_display",
        "is_staff",
        "date_joined",
    )
    list_filter = ("is_active", "blocked_at", "is_staff", "is_superuser")
    search_fields = ("username", "national_id", "email", "first_name", "last_name")
    readonly_fields = (
        "last_login",
        "date_joined",
        "created_at",
        "updated_at",
        "blocked_at",
    )
    fieldsets = (
        (
            "اطلاعات حساب",
            {
                "fields": (
                    "username",
                    "password",
                    "first_name",
                    "last_name",
                    "national_id",
                    "email",
                    "phone_number",
                    "account_status",
                )
            },
        ),
        (
            "دسترسی مدیریتی سامانه",
            {
                "fields": (
                    "is_staff",
                    "is_superuser",
                ),
                "description": (
                    "دسترسی عملیاتی کاربر فقط از نقش عضویت سازمانی او تعیین "
                    "می‌شود. این گزینه‌ها صرفاً برای مدیریت سامانه هستند."
                ),
            },
        ),
        (
            "زمان‌های حساب",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                    "created_at",
                    "updated_at",
                    "blocked_at",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            "اطلاعات حساب و تخصیص اولیه",
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "first_name",
                    "last_name",
                    "national_id",
                    "email",
                    "phone_number",
                    "organization",
                    "role_definition",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    @admin.display(description="وضعیت حساب", ordering="is_active")
    def account_status_display(self, obj: User) -> str:
        return obj.account_status_label

    def _has_tenant_management_access(self, request: HttpRequest) -> bool:
        organization = getattr(request, "organization", None)
        if organization is None:
            return False
        return has_business_permission(
            user=request.user,
            organization=organization,
            permission=BusinessPermissionCode.MEMBERSHIP_VIEW,
        )

    def get_queryset(self, request: HttpRequest) -> QuerySet[User]:
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        organization = getattr(request, "organization", None)
        if organization is None or not self._has_tenant_management_access(request):
            return queryset.none()
        return queryset.filter(
            organization_memberships__organization=organization
        ).distinct()

    def has_view_permission(
        self, request: HttpRequest, obj: User | None = None
    ) -> bool:
        if not super().has_view_permission(request, obj):
            return False
        if request.user.is_superuser:
            return True
        organization = getattr(request, "organization", None)
        if organization is None or not self._has_tenant_management_access(request):
            return False
        return (
            obj is None
            or obj.organization_memberships.filter(organization=organization).exists()
        )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(
        self, request: HttpRequest, obj: User | None = None
    ) -> bool:
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(
        self, request: HttpRequest, obj: User | None = None
    ) -> bool:
        return request.user.is_superuser and super().has_delete_permission(request, obj)

    def save_model(
        self,
        request: HttpRequest,
        obj: User,
        form: PersianUserChangeForm | PersianUserCreationForm,
        change: bool,
    ) -> None:
        previous_status = None
        if change:
            previous = User.objects.get(pk=obj.pk)
            previous_status = previous.account_status
        if not change:
            obj.is_active = False
        super().save_model(request, obj, form, change)
        if not change:
            membership = provision_user_for_organization(
                organization=form.cleaned_data["organization"],
                user=obj,
                actor=request.user,
            )
            update_organization_membership(
                organization=membership.organization,
                actor=request.user,
                membership=membership,
                role=form.cleaned_data["role_definition"],
                status=MembershipStatus.ACTIVE,
            )
            return
        if previous_status is not None and previous_status != obj.account_status:
            record_audit_event(
                action=AuditAction.USER_ACCOUNT_STATUS_CHANGED,
                entity_type="user",
                entity_id=obj.pk,
                actor=request.user,
                metadata={
                    "target_username": obj.username,
                    "previous_status": previous_status,
                    "new_status": obj.account_status,
                },
            )

    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str | None = None,
        form_url: str = "",
        extra_context: dict[str, object] | None = None,
    ):
        if object_id is not None:
            user = self.get_object(request, object_id)
            if user is not None:
                detail_context = self._build_detail_context(request, user)
                extra_context = {**(extra_context or {}), **detail_context}
        return super().changeform_view(request, object_id, form_url, extra_context)

    def _build_detail_context(
        self, request: HttpRequest, user: User
    ) -> dict[str, object]:
        memberships = user.organization_memberships.select_related(
            "organization", "assigned_by"
        )
        if not request.user.is_superuser:
            memberships = memberships.filter(organization=request.organization)
        membership_rows = [
            {
                "membership": membership,
                "role_label": membership.role_label,
                "status_label": membership.get_status_display(),
                "status_class": self._membership_status_class(membership.status),
            }
            for membership in memberships
        ]
        membership_ids = [str(row["membership"].pk) for row in membership_rows]

        event_filter = Q(actor=user) | Q(entity_type="user", entity_id=str(user.pk))
        if membership_ids:
            event_filter |= Q(
                entity_type="organization_membership",
                entity_id__in=membership_ids,
            )
        events = AuditEvent.objects.filter(event_filter)
        if not request.user.is_superuser:
            events = events.filter(organization=request.organization)
        events = events.select_related("organization", "actor").order_by("-created_at")
        last_access_change = events.filter(
            action__in=[
                AuditAction.MEMBERSHIP_ROLE_CHANGED,
                AuditAction.USER_PERMISSIONS_CHANGED,
            ]
        ).first()

        return {
            "detail_user": user,
            "account_status_class": self._account_status_class(user.account_status),
            "can_manage_memberships": request.user.is_superuser,
            "membership_rows": membership_rows,
            "audit_events": events[:25],
            "last_access_change": last_access_change,
        }

    @staticmethod
    def _account_status_class(status: str) -> str:
        return {
            AccountStatus.ACTIVE: "success",
            AccountStatus.INACTIVE: "neutral",
            AccountStatus.BLOCKED: "danger",
        }[status]

    @staticmethod
    def _membership_status_class(status: str) -> str:
        return {
            MembershipStatus.ACTIVE: "success",
            MembershipStatus.PENDING_ROLE: "warning",
            MembershipStatus.SUSPENDED: "warning",
            MembershipStatus.REVOKED: "danger",
        }[status]


admin.site.unregister(Group)


@admin.register(Group)
class PersianGroupAdmin(GroupAdmin):
    form = PersianGroupAdminForm

    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_view_permission(
        self, request: HttpRequest, obj: Group | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_change_permission(
        self, request: HttpRequest, obj: Group | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: Group | None = None
    ) -> bool:
        return request.user.is_superuser


@admin.register(LoginPageSettings)
class LoginPageSettingsAdmin(admin.ModelAdmin):
    """Allow system superusers to maintain the public login presentation."""

    formfield_overrides: ClassVar[
        dict[type[models.Field], dict[str, type[forms.Widget]]]
    ] = {
        models.FileField: {"widget": RtlClearableFileInput},
    }

    fieldsets = (
        (
            "پیام‌های پنل معرفی",
            {
                "fields": (
                    "panel_label",
                    "panel_title",
                    "panel_description",
                    "panel_footer",
                )
            },
        ),
        (
            "تصاویر صفحه ورود",
            {"fields": ("background_image", "panel_image")},
        ),
        (
            "زمان‌ها",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_view_permission(
        self, request: HttpRequest, obj: LoginPageSettings | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser and not LoginPageSettings.objects.exists()

    def has_change_permission(
        self, request: HttpRequest, obj: LoginPageSettings | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: LoginPageSettings | None = None
    ) -> bool:
        return False
