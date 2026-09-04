from django import forms

from apps.organizations.models import Organization, OrganizationSettings
from core.identifiers import canonicalize_lower_identifier


class OrganizationForm(forms.ModelForm):
    """Form for creating a new organization."""

    class Meta:
        model = Organization
        fields = [  # noqa: RUF012
            "name",
            "legal_name",
            "slug",
            "timezone",
            "currency",
        ]
        widgets = {  # noqa: RUF012
            "name": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "placeholder": "Company name",
                }
            ),
            "legal_name": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "placeholder": "Legal name (optional)",
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "placeholder": "company-slug",
                }
            ),
            "timezone": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "placeholder": "UTC",
                }
            ),
            "currency": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 uppercase text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "placeholder": "USD",
                }
            ),
        }

    def clean_slug(self) -> str:
        return canonicalize_lower_identifier(self.cleaned_data["slug"])


class OrganizationSettingsForm(forms.ModelForm):
    """Form for the active organization's configuration only."""

    class Meta:
        model = OrganizationSettings
        fields = ["timezone", "currency", "fiscal_year_start_month"]  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "timezone": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                }
            ),
            "currency": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 uppercase text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                }
            ),
            "fiscal_year_start_month": forms.NumberInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "min": 1,
                    "max": 12,
                }
            ),
        }
