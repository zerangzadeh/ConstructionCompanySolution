from django import forms

from apps.accounts.models import User
from apps.organizations.models import InvitationRole
from core.identifiers import canonicalize_lower_identifier


class OrganizationInvitationForm(forms.Form):
    """Form for inviting an existing user to the active organization."""

    invitee_username = forms.CharField(label="نام کاربری فرد مدعو", max_length=150)
    role = forms.ChoiceField(label="نقش سازمانی", choices=InvitationRole.choices)

    def clean_invitee_username(self) -> User:
        username = canonicalize_lower_identifier(self.cleaned_data["invitee_username"])
        try:
            return User.objects.get(username=username, is_active=True)
        except User.DoesNotExist as exc:
            raise forms.ValidationError(
                "کاربر فعالی با این نام کاربری وجود ندارد."
            ) from exc
