from django import forms

from apps.projects.models import (
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectSite,
    ProjectStatus,
)


class ProjectForm(forms.ModelForm):
    """Form for creating a project in the active organization."""

    class Meta:
        model = Project
        fields = [  # noqa: RUF012
            "code",
            "name",
            "description",
            "status",
            "start_date",
            "end_date",
            "budget",
        ]
        widgets = {  # noqa: RUF012
            "code": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "placeholder": "P-001",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "placeholder": "Project name",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "rows": 4,
                    "placeholder": "Optional project description",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                }
            ),
            "start_date": forms.DateInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "type": "date",
                }
            ),
            "end_date": forms.DateInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "type": "date",
                }
            ),
            "budget": forms.NumberInput(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "step": "0.01",
                    "min": "0",
                }
            ),
        }

    def clean_status(self) -> str:
        status = self.cleaned_data["status"]
        if status not in ProjectStatus.values:
            raise forms.ValidationError("Invalid project status.")
        return status


class ProjectSiteForm(forms.ModelForm):
    """Form for adding a worksite to an active project."""

    class Meta:
        model = ProjectSite
        fields = ["code", "name", "address"]  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "code": forms.TextInput(attrs={"placeholder": "SITE-001"}),
            "name": forms.TextInput(attrs={"placeholder": "North worksite"}),
            "address": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_class = (
            "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
            "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 "
            "focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = field_class


class ProjectPhaseForm(forms.ModelForm):
    """Form for creating a phase within one active worksite."""

    class Meta:
        model = ProjectPhase
        fields = [  # noqa: RUF012
            "code",
            "name",
            "status",
            "planned_start_date",
            "planned_end_date",
        ]
        widgets = {  # noqa: RUF012
            "code": forms.TextInput(attrs={"placeholder": "PH-001"}),
            "name": forms.TextInput(attrs={"placeholder": "Foundation works"}),
            "planned_start_date": forms.DateInput(attrs={"type": "date"}),
            "planned_end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_class = (
            "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
            "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 "
            "focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = field_class

    def clean_status(self) -> str:
        status = self.cleaned_data["status"]
        if status not in ProjectPhaseStatus.values:
            raise forms.ValidationError("Invalid project phase status.")
        return status
