import calendar

from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.accounts.models import User
from apps.organizations.authorization import (
    MINIMAL_SITE_PARENT_FIELDS,
    scope_queryset,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
    ProtectedOperationCode,
)
from apps.projects.models import Project, ProjectSite
from core.identifiers import canonicalize_lower_identifier

TEXT_INPUT_CLASS = (
    "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
    "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 "
    "focus:ring-blue-100"
)
ROLE_ACCESS_HELP_TEXT = (
    "این مورد سطح دسترسی به سامانه را تعیین می‌کند و سمت شغلی فرد نیست."
)

ORGANIZATION_PROFILE_FIELDS = [
    "name",
    "legal_name",
    "slug",
    "registration_number",
    "national_id",
    "economic_code",
    "phone",
    "email",
    "website",
    "province",
    "city",
    "address",
    "postal_code",
]
ORGANIZATION_PROFILE_WIDGETS = {
    "name": forms.TextInput(
        attrs={"class": TEXT_INPUT_CLASS, "placeholder": "نام شرکت"}
    ),
    "legal_name": forms.TextInput(
        attrs={"class": TEXT_INPUT_CLASS, "placeholder": "نام ثبتی/قانونی"}
    ),
    "slug": forms.TextInput(
        attrs={"class": TEXT_INPUT_CLASS, "placeholder": "company-slug"}
    ),
    "registration_number": forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    "national_id": forms.TextInput(attrs={"class": TEXT_INPUT_CLASS, "dir": "ltr"}),
    "economic_code": forms.TextInput(attrs={"class": TEXT_INPUT_CLASS, "dir": "ltr"}),
    "phone": forms.TextInput(attrs={"class": TEXT_INPUT_CLASS, "dir": "ltr"}),
    "email": forms.EmailInput(attrs={"class": TEXT_INPUT_CLASS, "dir": "ltr"}),
    "website": forms.URLInput(attrs={"class": TEXT_INPUT_CLASS, "dir": "ltr"}),
    "province": forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    "city": forms.TextInput(attrs={"class": TEXT_INPUT_CLASS}),
    "address": forms.Textarea(attrs={"class": TEXT_INPUT_CLASS, "rows": 3}),
    "postal_code": forms.TextInput(attrs={"class": TEXT_INPUT_CLASS, "dir": "ltr"}),
}
ORGANIZATION_ADMIN_SETTINGS_FIELD_MAP = {
    "logo": "logo",
    "language": "language",
    "settings_timezone": "timezone",
    "default_currency": "currency",
    "fiscal_year_start_month": "fiscal_year_start_month",
    "fiscal_year_start_day": "fiscal_year_start_day",
    "project_code_prefix": "project_code_prefix",
    "contract_code_prefix": "contract_code_prefix",
    "site_code_prefix": "site_code_prefix",
    "document_code_prefix": "document_code_prefix",
}


def _settings_form_field(model_field_name: str, **kwargs: object) -> forms.Field:
    form_field = OrganizationSettings._meta.get_field(model_field_name).formfield(
        **kwargs
    )
    if form_field is None:  # pragma: no cover - all selected model fields are editable
        raise RuntimeError(f"No form field for {model_field_name}")
    return form_field


class OrganizationProfileForm(forms.ModelForm):
    """Form for editable identity and contact details of the active company."""

    website = forms.URLField(
        label="وب‌سایت",
        required=False,
        assume_scheme="https",
        widget=ORGANIZATION_PROFILE_WIDGETS["website"],
    )

    class Meta:
        model = Organization
        fields = ORGANIZATION_PROFILE_FIELDS
        widgets = ORGANIZATION_PROFILE_WIDGETS

    def clean_slug(self) -> str:
        return canonicalize_lower_identifier(self.cleaned_data["slug"])


class OrganizationForm(OrganizationProfileForm):
    """Create Tenant identity plus authoritative settings through the service."""

    timezone = _settings_form_field(
        "timezone",
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASS,
                "placeholder": "Asia/Tehran",
                "dir": "ltr",
            }
        ),
    )
    currency = _settings_form_field(
        "currency",
        widget=forms.TextInput(
            attrs={
                "class": f"{TEXT_INPUT_CLASS} uppercase",
                "placeholder": "IRR",
                "dir": "ltr",
            }
        ),
    )

    initial_owner_username = forms.CharField(
        label="نام کاربری Tenant Owner اولیه",
        max_length=150,
        widget=forms.TextInput(attrs={"class": TEXT_INPUT_CLASS, "dir": "ltr"}),
        help_text="مالک اولیه به‌صورت صریح و مستقل از Platform Admin انتخاب می‌شود.",
    )

    class Meta(OrganizationProfileForm.Meta):
        fields = (
            "initial_owner_username",
            *ORGANIZATION_PROFILE_FIELDS,
            "timezone",
            "currency",
        )
        widgets = ORGANIZATION_PROFILE_WIDGETS

    def clean_initial_owner_username(self) -> str:
        username = canonicalize_lower_identifier(
            self.cleaned_data["initial_owner_username"]
        )
        if not User.objects.filter(username=username, is_active=True).exists():
            raise ValidationError("حساب فعال مالک اولیه یافت نشد.")
        return username


class OrganizationAdminForm(OrganizationProfileForm):
    """Unified admin form backed by separate organization and settings models."""

    logo = _settings_form_field("logo")
    language = _settings_form_field("language")
    settings_timezone = _settings_form_field(
        "timezone",
        label="منطقه زمانی",
    )
    default_currency = _settings_form_field(
        "currency",
        label="واحد پول پیش‌فرض",
    )
    fiscal_year_start_month = _settings_form_field("fiscal_year_start_month")
    fiscal_year_start_day = _settings_form_field("fiscal_year_start_day")
    project_code_prefix = _settings_form_field("project_code_prefix")
    contract_code_prefix = _settings_form_field("contract_code_prefix")
    site_code_prefix = _settings_form_field("site_code_prefix")
    document_code_prefix = _settings_form_field("document_code_prefix")

    class Meta(OrganizationProfileForm.Meta):
        fields = ORGANIZATION_PROFILE_FIELDS

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        if self.instance._state.adding:
            return

        settings_record = OrganizationSettings.objects.filter(
            organization=self.instance
        ).first()
        if settings_record is None:
            settings_record = OrganizationSettings(organization=self.instance)
        for (
            form_field_name,
            model_field_name,
        ) in ORGANIZATION_ADMIN_SETTINGS_FIELD_MAP.items():
            self.initial[form_field_name] = getattr(settings_record, model_field_name)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        month = cleaned_data.get("fiscal_year_start_month")
        day = cleaned_data.get("fiscal_year_start_day")
        if isinstance(month, int) and isinstance(day, int):
            max_day = calendar.monthrange(2001, month)[1]
            if day > max_day:
                self.add_error(
                    "fiscal_year_start_day",
                    "روز شروع برای ماه انتخاب‌شده معتبر نیست.",
                )
        return cleaned_data


class OrganizationSettingsForm(forms.ModelForm):
    """Form for the active organization's configuration only."""

    class Meta:
        model = OrganizationSettings
        fields = [  # noqa: RUF012
            "logo",
            "language",
            "timezone",
            "currency",
            "fiscal_year_start_month",
            "fiscal_year_start_day",
            "project_code_prefix",
            "contract_code_prefix",
            "site_code_prefix",
            "document_code_prefix",
        ]
        widgets = {  # noqa: RUF012
            "logo": forms.ClearableFileInput(attrs={"class": TEXT_INPUT_CLASS}),
            "language": forms.Select(attrs={"class": TEXT_INPUT_CLASS}),
            "timezone": forms.TextInput(
                attrs={"class": TEXT_INPUT_CLASS, "dir": "ltr"}
            ),
            "currency": forms.TextInput(
                attrs={
                    "class": f"{TEXT_INPUT_CLASS} uppercase",
                    "dir": "ltr",
                }
            ),
            "fiscal_year_start_month": forms.NumberInput(
                attrs={
                    "class": TEXT_INPUT_CLASS,
                    "min": 1,
                    "max": 12,
                }
            ),
            "fiscal_year_start_day": forms.NumberInput(
                attrs={"class": TEXT_INPUT_CLASS, "min": 1, "max": 31}
            ),
            "project_code_prefix": forms.TextInput(
                attrs={"class": f"{TEXT_INPUT_CLASS} uppercase", "dir": "ltr"}
            ),
            "contract_code_prefix": forms.TextInput(
                attrs={"class": f"{TEXT_INPUT_CLASS} uppercase", "dir": "ltr"}
            ),
            "site_code_prefix": forms.TextInput(
                attrs={"class": f"{TEXT_INPUT_CLASS} uppercase", "dir": "ltr"}
            ),
            "document_code_prefix": forms.TextInput(
                attrs={"class": f"{TEXT_INPUT_CLASS} uppercase", "dir": "ltr"}
            ),
        }


class OrganizationMembershipForm(forms.ModelForm):
    """Assign an administrator-defined role within the active company."""

    role_definition = forms.ModelChoiceField(
        label="نقش شرکتی",
        queryset=OrganizationRole.objects.none(),
        to_field_name="code",
        empty_label=None,
        help_text=ROLE_ACCESS_HELP_TEXT,
    )
    status = forms.ChoiceField(
        label="وضعیت عضویت",
        choices=[
            (MembershipStatus.ACTIVE, "فعال"),
            (MembershipStatus.SUSPENDED, "تعلیق‌شده"),
            (MembershipStatus.REVOKED, "لغوشده"),
        ],
    )

    class Meta:
        model = OrganizationMembership
        fields = ["role_definition", "status"]  # noqa: RUF012

    def __init__(
        self,
        *args: object,
        allow_owner_role: bool = False,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        organization_id = self.instance.organization_id
        roles = OrganizationRole.objects.filter(is_active=True).filter(
            Q(organization__isnull=True) | Q(organization_id=organization_id)
        )
        if not allow_owner_role:
            roles = roles.filter(is_owner=False)
        self.fields["role_definition"].queryset = roles.order_by("name")
        if self.instance.status == MembershipStatus.PENDING_ROLE:
            self.fields["status"].choices = [
                (MembershipStatus.ACTIVE, "فعال"),
            ]
            self.initial["status"] = MembershipStatus.ACTIVE
            self.fields[
                "status"
            ].help_text = "با ذخیره نقش، عضویت و حساب کاربر فعال می‌شوند."


class OrganizationMemberPasswordResetForm(SetPasswordForm):
    """Set a temporary password for a member without exposing their current one."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = TEXT_INPUT_CLASS
        self.fields[
            "new_password1"
        ].help_text = "عضو در ورود بعدی باید گذرواژه شخصی خود را تعیین کند."


class MembershipRoleAssignmentForm(forms.Form):
    role = forms.ModelChoiceField(
        label="نقش عضو",
        queryset=OrganizationRole.objects.none(),
    )
    approver_membership = forms.ModelChoiceField(
        label="تأییدکننده مستقل",
        queryset=OrganizationMembership.objects.none(),
    )
    ends_at = forms.DateTimeField(label="پایان اعتبار", required=False)
    reason = forms.CharField(label="دلیل", widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(
        self,
        *args: object,
        organization: Organization,
        actor_membership: OrganizationMembership,
        target_membership: OrganizationMembership,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = (
            OrganizationRole.objects.filter(is_active=True)
            .filter(Q(organization__isnull=True) | Q(organization=organization))
            .order_by("name")
        )
        self.fields["approver_membership"].queryset = (
            OrganizationMembership.objects.filter(
                organization=organization,
                status=MembershipStatus.ACTIVE,
                user__is_active=True,
            )
            .exclude(pk__in=(actor_membership.pk, target_membership.pk))
            .select_related("user")
            .order_by("user__username")
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", TEXT_INPUT_CLASS)


class MembershipScopeGrantForm(forms.Form):
    scope_type = forms.ChoiceField(
        label="سطح دسترسی به شرکت، پروژه یا کارگاه",
        choices=AuthorizationScopeType.choices,
    )
    project = forms.ModelChoiceField(
        label="پروژه", queryset=Project.objects.none(), required=False
    )
    site = forms.ModelChoiceField(
        label="کارگاه", queryset=ProjectSite.objects.none(), required=False
    )
    approver_membership = forms.ModelChoiceField(
        label="تأییدکننده مستقل",
        queryset=OrganizationMembership.objects.none(),
    )
    ends_at = forms.DateTimeField(label="پایان اعتبار", required=False)
    reason = forms.CharField(label="دلیل", widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(
        self,
        *args: object,
        organization: Organization,
        actor_membership: OrganizationMembership,
        target_membership: OrganizationMembership,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = (
            scope_queryset(
                Project.objects.filter(
                    organization=organization, deleted_at__isnull=True
                ),
                membership=actor_membership,
                project_lookup="pk",
                include_site_parent=True,
            )
            .only(*MINIMAL_SITE_PARENT_FIELDS)
            .order_by("name")
        )
        self.fields["site"].queryset = (
            scope_queryset(
                ProjectSite.objects.filter(organization=organization, is_active=True),
                membership=actor_membership,
                project_lookup="project_id",
                site_lookup="pk",
            )
            .select_related("project")
            .order_by("project__name", "name")
        )
        self.fields["approver_membership"].queryset = (
            OrganizationMembership.objects.filter(
                organization=organization,
                status=MembershipStatus.ACTIVE,
                user__is_active=True,
            )
            .exclude(pk__in=(actor_membership.pk, target_membership.pk))
            .select_related("user")
            .order_by("user__username")
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", TEXT_INPUT_CLASS)


class OrganizationAccountCreateForm(forms.Form):
    username = forms.CharField(
        label="نام کاربری",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    first_name = forms.CharField(label="نام", max_length=150)
    last_name = forms.CharField(label="نام خانوادگی", max_length=150)
    email = forms.EmailField(label="ایمیل", required=False)
    phone_number = forms.CharField(label="شماره تلفن", max_length=32, required=False)
    national_id = forms.CharField(label="کد ملی", max_length=10, required=False)
    role_definition = forms.ModelChoiceField(
        label="نقش شرکتی",
        queryset=OrganizationRole.objects.none(),
        to_field_name="code",
        empty_label=None,
        help_text=ROLE_ACCESS_HELP_TEXT,
    )
    temporary_password = forms.CharField(
        label="گذرواژه موقت",
        widget=forms.PasswordInput(render_value=True),
        help_text="کاربر در نخستین ورود ملزم به تعیین گذرواژه شخصی خواهد بود.",
    )
    temporary_password_confirm = forms.CharField(
        label="تکرار گذرواژه موقت",
        widget=forms.PasswordInput(render_value=True),
    )

    def __init__(
        self,
        *args: object,
        allow_owner_role: bool,
        organization: Organization | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        roles = OrganizationRole.objects.filter(is_active=True).filter(
            Q(organization__isnull=True) | Q(organization=organization)
        )
        if not allow_owner_role:
            roles = roles.filter(is_owner=False)
        self.fields["role_definition"].queryset = roles.order_by("name")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", TEXT_INPUT_CLASS)

    def clean_username(self) -> str:
        return canonicalize_lower_identifier(self.cleaned_data["username"])

    def clean(self) -> dict[str, object]:
        cleaned = super().clean()
        password = cleaned.get("temporary_password")
        confirmation = cleaned.get("temporary_password_confirm")
        if password and password != confirmation:
            self.add_error("temporary_password_confirm", "تکرار گذرواژه یکسان نیست.")
        if password:
            candidate = User(
                username=str(cleaned.get("username") or ""),
                first_name=str(cleaned.get("first_name") or ""),
                last_name=str(cleaned.get("last_name") or ""),
            )
            try:
                validate_password(password, user=candidate)
            except ValidationError as exc:
                self.add_error("temporary_password", exc)
        return cleaned


class ExistingAccountConnectionForm(forms.Form):
    username = forms.CharField(
        label="نام کاربری دقیق حساب موجود",
        max_length=150,
        help_text="فهرست کاربران سراسری نمایش داده نمی‌شود.",
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    role_definition = forms.ModelChoiceField(
        label="نقش پس از پذیرش",
        queryset=OrganizationRole.objects.none(),
        to_field_name="code",
        empty_label=None,
        help_text=ROLE_ACCESS_HELP_TEXT,
    )

    def __init__(
        self,
        *args: object,
        allow_owner_role: bool,
        organization: Organization | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        roles = OrganizationRole.objects.filter(is_active=True).filter(
            Q(organization__isnull=True) | Q(organization=organization)
        )
        if not allow_owner_role:
            roles = roles.filter(is_owner=False)
        self.fields["role_definition"].queryset = roles.order_by("name")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", TEXT_INPUT_CLASS)

    def clean_username(self) -> str:
        return canonicalize_lower_identifier(self.cleaned_data["username"])


class OrganizationRoleCatalogForm(forms.Form):
    """Edit role presentation and bind only active, code-owned permissions."""

    organization = forms.ModelChoiceField(
        label="Tenant",
        queryset=Organization.objects.none(),
        required=False,
        help_text="برای نقش سراسری خالی بگذارید.",
    )
    code = forms.SlugField(label="کد پایدار نقش", max_length=64)
    name = forms.CharField(label="عنوان نقش", max_length=255)
    description = forms.CharField(
        label="توضیحات", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    permissions = forms.ModelMultipleChoiceField(
        label="مجوزهای فعال",
        queryset=BusinessPermission.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )
    reason = forms.CharField(
        label="دلیل تغییر", widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(
        self,
        *args: object,
        platform_mode: bool,
        organization: Organization | None = None,
        role: OrganizationRole | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["permissions"].queryset = BusinessPermission.objects.filter(
            is_active=True
        ).order_by("code")
        self.fields["organization"].queryset = Organization.objects.filter(
            status="active", archived_at__isnull=True
        ).order_by("name")
        if not platform_mode:
            self.fields.pop("organization")
        if role is not None:
            self.initial.update(
                {
                    "organization": role.organization,
                    "code": role.code,
                    "name": role.name,
                    "description": role.description,
                    "permissions": role.permissions.all(),
                }
            )
            self.fields["code"].disabled = True
            if platform_mode:
                self.fields["organization"].disabled = True
        elif not platform_mode:
            self.initial["organization"] = organization
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.setdefault("class", TEXT_INPUT_CLASS)


class ProtectedOperationCatalogForm(forms.Form):
    """Create an immutable protected-operation classification version."""

    code = forms.ChoiceField(
        label="کد عملیات حفاظت‌شده", choices=ProtectedOperationCode.choices
    )
    name = forms.CharField(label="عنوان", max_length=255)
    description = forms.CharField(
        label="شرح کنترل", widget=forms.Textarea(attrs={"rows": 3})
    )
    reason = forms.CharField(
        label="دلیل تغییر", widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", TEXT_INPUT_CLASS)
