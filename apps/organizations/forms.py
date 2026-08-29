from django import forms

from apps.organizations.models import Organization


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
