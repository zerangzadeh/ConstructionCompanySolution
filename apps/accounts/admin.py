from typing import ClassVar

from django import forms
from django.apps import apps
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Group, Permission
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import AccountStatus, User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
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


class PersianUserChangeForm(UserChangeForm):
    account_status = forms.ChoiceField(
        choices=AccountStatus.choices,
        label="وضعیت حساب",
        help_text="کاربر مسدود یا غیرفعال امکان ورود به سامانه را ندارد.",
    )
    user_permissions = PersianPermissionChoiceField(
        queryset=Permission.objects.select_related("content_type"),
        required=False,
        label="مجوزهای کاربر",
        help_text="مجوزهای اختصاصی این کاربر را انتخاب کنید.",
        widget=FilteredSelectMultiple("مجوزها", is_stacked=False),
    )

    class Meta(UserChangeForm.Meta):
        model = User

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
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
    change_form_template = "admin/accounts/user/change_form.html"
    list_display = (
        "username",
        "email",
        "account_status_display",
        "is_staff",
        "date_joined",
    )
    list_filter = ("is_active", "blocked_at", "is_staff", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")
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
                    "first_name",
                    "last_name",
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
                    "groups",
                    "user_permissions",
                ),
                "description": (
                    "این مجوزها سراسری هستند و جایگزین نقش شرکتی کاربر نیستند."
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
            permission=BusinessPermissionCode.MEMBERSHIP_MANAGE,
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
        form: PersianUserChangeForm,
        change: bool,
    ) -> None:
        previous_status = None
        if change:
            previous = User.objects.get(pk=obj.pk)
            previous_status = previous.account_status
            request._erp_previous_user_permissions = set(
                previous.user_permissions.values_list("pk", flat=True)
            )
            request._erp_previous_user_groups = set(
                previous.groups.values_list("pk", flat=True)
            )
        super().save_model(request, obj, form, change)
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

    def save_related(
        self,
        request: HttpRequest,
        form: PersianUserChangeForm,
        formsets: list[forms.BaseFormSet],
        change: bool,
    ) -> None:
        super().save_related(request, form, formsets, change)
        if not change:
            return
        user = form.instance
        previous_permissions = getattr(request, "_erp_previous_user_permissions", set())
        previous_groups = getattr(request, "_erp_previous_user_groups", set())
        current_permissions = set(user.user_permissions.values_list("pk", flat=True))
        current_groups = set(user.groups.values_list("pk", flat=True))
        if (
            previous_permissions == current_permissions
            and previous_groups == current_groups
        ):
            return
        record_audit_event(
            action=AuditAction.USER_PERMISSIONS_CHANGED,
            entity_type="user",
            entity_id=user.pk,
            actor=request.user,
            metadata={
                "target_username": user.username,
                "direct_permission_count": len(current_permissions),
                "group_count": len(current_groups),
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
            "organization", "invited_by"
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

        permission_rows = []
        permission_field = PersianPermissionChoiceField(
            queryset=Permission.objects.none()
        )
        for permission in user.user_permissions.select_related("content_type"):
            permission_rows.append(
                {
                    "source": "اختصاصی",
                    "label": permission_field.label_from_instance(permission),
                    "codename": (
                        f"{permission.content_type.app_label}.{permission.codename}"
                    ),
                }
            )
        groups = user.groups.prefetch_related("permissions__content_type")
        for group in groups:
            for permission in group.permissions.all():
                permission_rows.append(
                    {
                        "source": f"گروه: {group.name}",
                        "label": permission_field.label_from_instance(permission),
                        "codename": (
                            f"{permission.content_type.app_label}.{permission.codename}"
                        ),
                    }
                )

        return {
            "detail_user": user,
            "account_status_class": self._account_status_class(user.account_status),
            "membership_rows": membership_rows,
            "permission_rows": permission_rows,
            "user_groups": groups,
            "audit_events": events[:25],
            "last_access_change": last_access_change,
            "project_access_supported": False,
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
            MembershipStatus.INVITED: "warning",
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
