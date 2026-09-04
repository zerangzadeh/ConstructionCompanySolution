from django import forms

from apps.parties.models import BusinessParty, PartyContact, PartyRole


class BusinessPartyForm(forms.ModelForm):
    class Meta:
        model = BusinessParty
        fields = ["party_kind", "display_name", "legal_name", "tax_identifier"]  # noqa: RUF012


class PartyRoleForm(forms.ModelForm):
    class Meta:
        model = PartyRole
        fields = ["role"]  # noqa: RUF012


class PartyContactForm(forms.ModelForm):
    class Meta:
        model = PartyContact
        fields = ["contact_type", "value", "label", "is_primary"]  # noqa: RUF012
