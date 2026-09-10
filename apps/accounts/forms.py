from django import forms
from django.contrib.auth.forms import AuthenticationForm

from core.identifiers import canonicalize_lower_identifier

INPUT_CLASSES = (
    "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
    "text-slate-900 outline-none transition placeholder:text-slate-400 "
    "focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
)


class UserLoginForm(AuthenticationForm):
    """Username and password form styled for the login page."""

    username = forms.CharField(
        label="نام کاربری",
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASSES,
                "autocomplete": "username",
                "placeholder": "نام کاربری خود را وارد کنید",
            }
        )
    )
    password = forms.CharField(
        label="گذرواژه",
        widget=forms.PasswordInput(
            attrs={
                "class": INPUT_CLASSES,
                "autocomplete": "current-password",
                "placeholder": "گذرواژه خود را وارد کنید",
            }
        )
    )

    def clean_username(self) -> str:
        return canonicalize_lower_identifier(self.cleaned_data["username"])
