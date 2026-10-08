from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)

from apps.accounts.models import User
from core.identifiers import canonicalize_lower_identifier

INPUT_CLASSES = (
    "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
    "text-slate-900 outline-none transition placeholder:text-slate-400 "
    "focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
)


class ProfileImageInput(forms.ClearableFileInput):
    """Render profile image controls without exposing the storage path."""

    template_name = "widgets/profile_image_input.html"
    clear_checkbox_label = "حذف تصویر فعلی"


class UserLoginForm(AuthenticationForm):
    """Username and password form styled for the login page."""

    username = forms.CharField(
        label="نام کاربری",
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASSES,
                "autocomplete": "username",
                "placeholder": "نام کاربری خود را وارد کنید",
                "aria-describedby": "id_username-errors",
            }
        ),
    )
    password = forms.CharField(
        label="گذرواژه",
        widget=forms.PasswordInput(
            attrs={
                "class": INPUT_CLASSES,
                "autocomplete": "current-password",
                "placeholder": "گذرواژه خود را وارد کنید",
                "aria-describedby": "id_password-errors",
            }
        ),
    )

    def clean_username(self) -> str:
        return canonicalize_lower_identifier(self.cleaned_data["username"])


class PublicPasswordResetRequestForm(PasswordResetForm):
    """Issue recovery email only for one unambiguous active account."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "ایمیل سازمانی"
        self.fields["email"].widget.attrs.update(
            {
                "class": INPUT_CLASSES,
                "autocomplete": "email",
                "dir": "ltr",
                "inputmode": "email",
                "placeholder": "email@example.com",
            }
        )

    def get_users(self, email: str):  # type: ignore[override]
        users = [
            user
            for user in User.objects.filter(email__iexact=email, is_active=True)
            if user.has_usable_password()
        ]
        return iter(users if len(users) == 1 else [])


class PublicPasswordResetSetForm(SetPasswordForm):
    """Set a permanent password after a verified public recovery link."""

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.must_change_password = False
        if commit:
            user.save(update_fields=["password", "must_change_password", "updated_at"])
        return user


class PersonalSettingsForm(forms.ModelForm):
    """Allow an authenticated user to edit only their own personal details."""

    class Meta:
        model = User
        fields = [  # noqa: RUF012
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "profile_image",
        ]
        widgets = {  # noqa: RUF012
            "first_name": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "last_name": forms.TextInput(attrs={"class": INPUT_CLASSES}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASSES, "dir": "ltr"}),
            "phone_number": forms.TextInput(
                attrs={"class": INPUT_CLASSES, "dir": "ltr", "inputmode": "tel"}
            ),
            "profile_image": ProfileImageInput(
                attrs={
                    "class": INPUT_CLASSES,
                    "accept": "image/png,image/jpeg,image/webp",
                }
            ),
        }

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()

    def clean_phone_number(self) -> str:
        return self.cleaned_data["phone_number"].strip()


class PersonalPasswordChangeForm(PasswordChangeForm):
    """Style Django's password-change validation for the personal settings page."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASSES


class RequiredPasswordChangeForm(SetPasswordForm):
    """Set the permanent password after authentication with a temporary one."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASSES
