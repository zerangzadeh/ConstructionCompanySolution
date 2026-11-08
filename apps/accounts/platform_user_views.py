"""Platform-only account pages using the existing authentication identity."""

from smtplib import SMTPException
from uuid import UUID

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.contrib.auth.password_validation import (
    password_validators_help_text_html,
    validate_password,
)
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MaxLengthValidator
from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Case, Count, Exists, OuterRef, Q, Value, When
from django.db.models.functions import Concat
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.models import User
from apps.accounts.platform_user_services import (
    ACCOUNT_AUDIT_ACTIONS,
    MAX_TEMPORARY_PASSWORD_LENGTH,
    can_issue_temporary_password,
    create_platform_user,
    platform_user_directory,
    prepare_platform_user_recovery,
    protected_account,
    recovery_delivery_configured,
    require_user_management_permission,
    set_platform_temporary_password,
    set_platform_user_active,
    temporary_password_validators,
    update_platform_user,
)
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.authorization import (
    effective_role_assignments,
    has_business_permission,
)
from apps.organizations.models import (
    BusinessPermission,
    Organization,
    OrganizationMembership,
)
from apps.organizations.models import BusinessPermissionCode as P
from core.list_filters import paginate_table

STATUS_CHOICES = (("", "همه وضعیت‌ها"), ("active", "فعال"), ("inactive", "غیرفعال"))


class UserSearchForm(forms.Form):
    q = forms.CharField(
        label="جستجو بر اساس نام، نام کاربری یا ایمیل",
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={"dir": "auto", "placeholder": "جستجو در کاربران…"}
        ),
    )
    status = forms.ChoiceField(
        label="وضعیت حساب", choices=STATUS_CHOICES, required=False
    )
    company = forms.ModelChoiceField(
        label="عضویت در شرکت",
        queryset=Organization.objects.order_by("name", "pk"),
        required=False,
        empty_label="همه شرکت‌ها",
    )
    platform_admin = forms.ChoiceField(
        label="مدیر پلتفرم",
        choices=(("", "همه کاربران"), ("yes", "مدیر فعال"), ("no", "سایر کاربران")),
        required=False,
    )
    page_size = forms.TypedChoiceField(
        label="تعداد در هر صفحه",
        choices=((10, "۱۰"), (20, "۲۰"), (50, "۵۰")),
        coerce=int,
        empty_value=20,
        initial=20,
        required=False,
        widget=forms.Select(attrs={"form": "platform-user-filters"}),
    )


class ProfileForm(forms.Form):
    first_name = forms.CharField(label="نام", max_length=150, required=False)
    last_name = forms.CharField(label="نام خانوادگی", max_length=150, required=False)
    phone_number = forms.CharField(
        label="شماره تماس",
        max_length=32,
        required=False,
        widget=forms.TextInput(attrs={"dir": "ltr", "autocomplete": "tel"}),
    )


class CreateUserForm(ProfileForm):
    username = forms.CharField(
        label="نام کاربری",
        max_length=150,
        validators=User._meta.get_field("username").validators,
        widget=forms.TextInput(attrs={"dir": "ltr", "autocomplete": "off"}),
    )
    email = forms.EmailField(
        label="ایمیل بازیابی",
        max_length=254,
        widget=forms.EmailInput(attrs={"dir": "ltr"}),
    )
    field_order = ("username", "email", "first_name", "last_name", "phone_number")


class EditUserForm(ProfileForm):
    expected_updated_at = forms.DateTimeField(widget=forms.HiddenInput)


class UserStatusForm(forms.Form):
    status = forms.ChoiceField(choices=STATUS_CHOICES[1:], widget=forms.HiddenInput)
    expected_updated_at = forms.DateTimeField(widget=forms.HiddenInput)
    reason = forms.CharField(label="دلیل تغییر وضعیت", max_length=1000)


class TemporaryPasswordForm(SetPasswordForm):
    expected_updated_at = forms.DateTimeField(widget=forms.HiddenInput)

    def __init__(self, user: User, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["new_password1"].label = "گذرواژه موقت"
        self.fields["new_password1"].help_text = password_validators_help_text_html(
            temporary_password_validators()
        )
        self.fields["new_password2"].label = "تکرار گذرواژه موقت"
        self.fields["new_password2"].help_text = "گذرواژه موقت را دوباره وارد کنید."
        for name in ("new_password1", "new_password2"):
            field = self.fields[name]
            field.validators.append(MaxLengthValidator(MAX_TEMPORARY_PASSWORD_LENGTH))
            field.widget.attrs.update(
                {"dir": "ltr", "maxlength": MAX_TEMPORARY_PASSWORD_LENGTH}
            )

    @sensitive_variables("password")
    def validate_password_for_user(self, user, password_field_name="password2"):
        if password := self.cleaned_data.get(password_field_name):
            try:
                validate_password(
                    password,
                    user=user,
                    password_validators=temporary_password_validators(),
                )
            except ValidationError as error:
                self.add_error(password_field_name, error)


def _form_error(form: forms.Form, error: ValidationError) -> None:
    for field, errors in getattr(
        error, "message_dict", {"__all__": error.messages}
    ).items():
        form.add_error(field if field in form.fields else None, errors)


@login_required
@require_GET
@never_cache
def directory(request: HttpRequest) -> HttpResponse:
    permissions = require_user_management_permission(request.user)
    form = UserSearchForm({"page_size": "20", **request.GET.dict()})
    directory_users = platform_user_directory()
    summary = directory_users.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        inactive=Count("pk", filter=Q(is_active=False)),
        administrators=Count("pk", filter=Q(platform_admin_effective=True)),
    )
    users = directory_users.only(
        "username",
        "first_name",
        "last_name",
        "email",
        "is_active",
        "blocked_at",
        "last_login",
        "created_at",
        "is_staff",
        "is_superuser",
    ).annotate(
        membership_count=Count("organization_memberships"),
        directory_has_usable_password=Case(
            When(password__startswith=UNUSABLE_PASSWORD_PREFIX, then=Value(False)),
            default=Value(True),
            output_field=BooleanField(),
        ),
    )
    if form.is_valid():
        data = form.cleaned_data
        if query := " ".join(data["q"].split()):
            users = users.alias(
                full_name=Concat("first_name", Value(" "), "last_name"),
            ).filter(
                Q(full_name__icontains=query)
                | Q(username__icontains=query)
                | Q(email__icontains=query)
            )
        if data["status"]:
            users = users.filter(is_active=data["status"] == "active")
        if data["company"]:
            users = users.filter(
                Exists(
                    OrganizationMembership.objects.filter(
                        user_id=OuterRef("pk"),
                        organization=data["company"],
                    )
                )
            )
        if data["platform_admin"]:
            users = users.filter(
                platform_admin_effective=data["platform_admin"] == "yes"
            )
    else:
        users = users.none()
    page = paginate_table(
        users,
        request,
        sort_fields={},
        default_ordering=("username", "pk"),
        per_page=form.cleaned_data.get("page_size", 20),
    )
    can_manage = P.PLATFORM_ADMIN_USERS_MANAGE in permissions
    can_manage_operators = (
        can_manage
        and BusinessPermission.objects.filter(
            code=P.PLATFORM_ADMIN_MANAGE_OPERATORS, is_active=True
        ).exists()
    )
    can_recover = P.PLATFORM_ADMIN_USERS_RECOVER in permissions
    email_configured = can_recover and recovery_delivery_configured()
    for account in page.object_list:
        mutable = not protected_account(account) and account.blocked_at is None
        other_account = account.pk != request.user.pk
        account.directory_can_edit = mutable and can_manage
        account.directory_can_change_status = (
            account.directory_can_edit
            and other_account
            and (not account.platform_admin_duty or can_manage_operators)
        )
        can_recover_account = (
            mutable
            and other_account
            and account.is_active
            and can_recover
            and account.directory_has_usable_password
        )
        account.directory_can_reset_temporary = (
            can_recover_account and not account.platform_admin_duty
        )
        account.directory_can_recover = (
            can_recover_account and email_configured and bool(account.email)
        )
    return render(
        request,
        "accounts/platform_user_list.html",
        {
            "form": form,
            "page_obj": page,
            "pagination_rendered": True,
            "can_manage": can_manage,
            "user_metrics": [
                {
                    "label": "همه کاربران",
                    "value": summary["total"],
                    "icon": "users",
                    "tone": "companies",
                },
                {
                    "label": "حساب‌های فعال",
                    "value": summary["active"],
                    "icon": "id-card",
                    "tone": "active",
                },
                {
                    "label": "حساب‌های غیرفعال",
                    "value": summary["inactive"],
                    "icon": "pause",
                    "tone": "suspended",
                },
                {
                    "label": "مدیران پلتفرم",
                    "value": summary["administrators"],
                    "icon": "layers",
                    "tone": "accounts",
                },
            ],
        },
    )


@login_required
@require_GET
@never_cache
def detail(request: HttpRequest, user_id: UUID) -> HttpResponse:
    permissions = require_user_management_permission(request.user)
    target = get_object_or_404(platform_user_directory(), pk=user_id)
    memberships = target.organization_memberships.select_related(
        "organization", "role_definition"
    ).order_by("organization__name", "pk")
    page = paginate_table(memberships, request, sort_fields={})
    rows = []
    show_membership_actions = False
    for membership in page.object_list:
        can_inspect_roles = all(
            has_business_permission(
                user=request.user,
                organization=membership.organization,
                permission=permission,
            )
            for permission in (P.MEMBERSHIP_VIEW, P.AUTHORIZATION_ROLES_VIEW)
        )
        role_names = None
        if can_inspect_roles:
            role_names = list(
                effective_role_assignments(membership).values_list(
                    "role__name", flat=True
                )
            )
            if (
                not role_names
                and membership.authorization_migrated_at is None
                and not membership.role_assignments.exists()
                and membership.role_definition
                and membership.role_definition.is_active
            ):
                role_names = [membership.role_definition.name]
        show_membership_actions |= can_inspect_roles
        rows.append((membership, role_names, can_inspect_roles))
    mutable = not protected_account(target) and target.blocked_at is None
    other_account = request.user.pk != target.pk
    can_manage = mutable and P.PLATFORM_ADMIN_USERS_MANAGE in permissions
    can_change_status = (
        can_manage
        and other_account
        and (
            not target.platform_admin_duty
            or BusinessPermission.objects.filter(
                code=P.PLATFORM_ADMIN_MANAGE_OPERATORS, is_active=True
            ).exists()
        )
    )
    audit_events = (
        AuditEvent.objects.filter(
            organization__isnull=True,
            entity_type="user",
            entity_id=str(target.pk),
            action__in=(
                *ACCOUNT_AUDIT_ACTIONS,
                AuditAction.USER_PASSWORD_INITIALIZED,
            ),
        )
        .select_related("actor")
        .only("action", "created_at", "actor__username")
        .annotate(
            recovery_unavailable=Case(
                When(
                    action=AuditAction.USER_PASSWORD_RESET_REQUESTED,
                    metadata__delivery="unavailable",
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            ),
            temporary_password_set=Case(
                When(
                    action=AuditAction.USER_PASSWORD_RESET_COMPLETED,
                    metadata__channel="temporary_password",
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        .order_by("-created_at", "-pk")[:10]
    )
    return render(
        request,
        "accounts/platform_user_detail.html",
        {
            "account": target,
            "membership_rows": rows,
            "show_membership_actions": show_membership_actions,
            "page_obj": page,
            "pagination_rendered": True,
            "audit_events": audit_events,
            "can_edit": can_manage,
            "can_change_status": can_change_status,
            "can_reset_temporary": P.PLATFORM_ADMIN_USERS_RECOVER in permissions
            and can_issue_temporary_password(actor=request.user, target=target),
            "can_recover": mutable
            and other_account
            and target.is_active
            and P.PLATFORM_ADMIN_USERS_RECOVER in permissions,
            "recovery_configured": recovery_delivery_configured(),
            "recovery_account_eligible": bool(
                target.email and target.has_usable_password()
            ),
            "status_form": UserStatusForm(
                initial={
                    "expected_updated_at": target.updated_at.isoformat(),
                    "status": "inactive" if target.is_active else "active",
                }
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
@never_cache
def account_form(request: HttpRequest, user_id: UUID | None = None) -> HttpResponse:
    require_user_management_permission(request.user, P.PLATFORM_ADMIN_USERS_MANAGE)
    data = request.POST if request.method == "POST" else None
    target = None
    if user_id is None:
        form = CreateUserForm(data)
    else:
        target = get_object_or_404(platform_user_directory(), pk=user_id)
        if protected_account(target) or target.blocked_at is not None:
            raise PermissionDenied("تغییر این حساب از این مسیر مجاز نیست.")
        form = EditUserForm(
            data,
            initial={
                "first_name": target.first_name,
                "last_name": target.last_name,
                "phone_number": target.phone_number,
                "expected_updated_at": target.updated_at.isoformat(),
            },
        )
    if request.method == "POST" and form.is_valid():
        try:
            if target is None:
                target = create_platform_user(
                    actor=request.user, data=form.cleaned_data
                )
                messages.success(
                    request,
                    "حساب ایجاد شد. از پرونده حساب، گذرواژه موقت تعیین کنید یا پیوند بازیابی بفرستید.",
                )
            else:
                update_platform_user(
                    actor=request.user,
                    user_id=target.pk,
                    data=form.cleaned_data,
                    expected_updated_at=form.cleaned_data["expected_updated_at"],
                )
                messages.success(request, "اطلاعات حساب ذخیره شد.")
        except ValidationError as error:
            _form_error(form, error)
        except IntegrityError:
            form.add_error(None, "ذخیره حساب به‌دلیل تداخل اطلاعات انجام نشد.")
        else:
            return redirect("organizations:platform_user_detail", user_id=target.pk)
    return render(
        request, "accounts/platform_user_form.html", {"form": form, "account": target}
    )


@login_required
@require_POST
@never_cache
def change_status(request: HttpRequest, user_id: UUID) -> HttpResponse:
    require_user_management_permission(request.user, P.PLATFORM_ADMIN_USERS_MANAGE)
    get_object_or_404(User, pk=user_id)
    form = UserStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, "وضعیت، نسخه و دلیل تغییر را بررسی کنید.")
    else:
        try:
            set_platform_user_active(
                actor=request.user,
                user_id=user_id,
                active=form.cleaned_data["status"] == "active",
                reason=form.cleaned_data["reason"],
                expected_updated_at=form.cleaned_data["expected_updated_at"],
            )
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, "وضعیت حساب به‌روزرسانی شد.")
    return redirect("organizations:platform_user_detail", user_id=user_id)


@sensitive_post_parameters("new_password1", "new_password2")
@login_required
@require_http_methods(["GET", "POST"])
@never_cache
@sensitive_variables()
def temporary_password(request: HttpRequest, user_id: UUID) -> HttpResponse:
    require_user_management_permission(request.user, P.PLATFORM_ADMIN_USERS_RECOVER)
    target = get_object_or_404(platform_user_directory(), pk=user_id)
    if not can_issue_temporary_password(actor=request.user, target=target):
        raise PermissionDenied("تنظیم گذرواژه موقت برای این حساب مجاز نیست.")
    if request.method == "POST" and not request.is_secure() and not settings.DEBUG:
        raise PermissionDenied("برای تنظیم گذرواژه موقت از اتصال امن استفاده کنید.")
    form = TemporaryPasswordForm(
        target,
        request.POST if request.method == "POST" else None,
        initial={"expected_updated_at": target.updated_at},
    )
    if request.method == "POST" and form.is_valid():
        try:
            set_platform_temporary_password(
                actor=request.user,
                user_id=target.pk,
                temporary_password=form.cleaned_data["new_password1"],
                expected_updated_at=form.cleaned_data["expected_updated_at"],
            )
        except ValidationError as error:
            _form_error(form, error)
        else:
            messages.success(
                request,
                "گذرواژه موقت تنظیم شد. کاربر در ورود بعدی باید گذرواژه شخصی خود را تعیین کند.",
            )
            return redirect("organizations:platform_user_detail", user_id=target.pk)
    return render(
        request,
        "accounts/platform_user_temporary_password.html",
        {"account": target, "form": form},
    )


@login_required
@require_POST
@never_cache
def reset_password(request: HttpRequest, user_id: UUID) -> HttpResponse:
    require_user_management_permission(request.user, P.PLATFORM_ADMIN_USERS_RECOVER)
    get_object_or_404(User, pk=user_id)
    try:
        email = prepare_platform_user_recovery(
            actor=request.user,
            user_id=user_id,
            domain=request.get_host(),
            use_https=request.is_secure(),
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        if email is None:
            messages.error(
                request, "سرویس ارسال ایمیل پیکربندی نشده است. پیوندی ارسال نشد."
            )
        else:

            def deliver() -> None:
                try:
                    accepted = email.send()
                except (OSError, SMTPException):
                    accepted = 0
                if accepted == 1:
                    messages.success(
                        request, "درخواست ارسال پیوند بازیابی به سرویس ایمیل تحویل شد."
                    )
                else:
                    messages.error(
                        request, "سرویس ایمیل ارسال پیوند بازیابی را تأیید نکرد."
                    )

            transaction.on_commit(deliver)
    return redirect("organizations:platform_user_detail", user_id=user_id)
