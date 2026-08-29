from django import forms

from apps.projects.models import Project, ProjectStatus


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
