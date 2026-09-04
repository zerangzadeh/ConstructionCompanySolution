from django import forms

from apps.accounts.models import User
from apps.organizations.models import InvitationRole
from core.identifiers import canonicalize_lower_identifier


class OrganizationInvitationForm(forms.Form):
    """Form for inviting an existing user to the active organization."""

    invitee_username = forms.CharField(max_length=150)
    role = forms.ChoiceField(choices=InvitationRole.choices)

    def clean_invitee_username(self) -> User:
        username = canonicalize_lower_identifier(self.cleaned_data["invitee_username"])
        try:
            return User.objects.get(username=username, is_active=True)
        except User.DoesNotExist as exc:
            raise forms.ValidationError(
                "No active user exists with this username."
            ) from exc
