from django import forms

from apps.materials.models import UnitOfMeasure
from apps.projects.models import (
    Activity,
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectSite,
    ProjectStatus,
    WBSNode,
)
from core.identifiers import canonicalize_upper_identifier


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
                    "placeholder": "نام پروژه",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
                    "rows": 4,
                    "placeholder": "شرح پروژه (اختیاری)",
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

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])

    def clean_status(self) -> str:
        status = self.cleaned_data["status"]
        if status not in ProjectStatus.values:
            raise forms.ValidationError("وضعیت پروژه معتبر نیست.")
        return status


class ProjectSiteForm(forms.ModelForm):
    """Form for adding a worksite to an active project."""

    class Meta:
        model = ProjectSite
        fields = ["code", "name", "address"]  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "code": forms.TextInput(attrs={"placeholder": "SITE-001"}),
            "name": forms.TextInput(attrs={"placeholder": "نام کارگاه"}),
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

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])


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
            "name": forms.TextInput(attrs={"placeholder": "نام فاز اجرایی"}),
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

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])

    def clean_status(self) -> str:
        status = self.cleaned_data["status"]
        if status not in ProjectPhaseStatus.values:
            raise forms.ValidationError("وضعیت فاز پروژه معتبر نیست.")
        return status


class WBSNodeForm(forms.ModelForm):
    class Meta:
        model = WBSNode
        fields = ["code", "title", "parent", "sort_order"]  # noqa: RUF012

    def __init__(self, *args: object, project: Project, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = WBSNode.objects.filter(
            project=project, archived_at__isnull=True, is_active=True
        )

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = [  # noqa: RUF012
            "code",
            "name",
            "wbs_node",
            "site",
            "phase",
            "unit_of_measure",
            "planned_quantity",
            "planned_start_date",
            "planned_end_date",
            "status",
        ]
        widgets = {  # noqa: RUF012
            "planned_start_date": forms.DateInput(attrs={"type": "date"}),
            "planned_end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args: object, project: Project, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        organization = project.organization
        self.fields["wbs_node"].queryset = WBSNode.objects.filter(
            project=project, archived_at__isnull=True, is_active=True
        )
        self.fields["site"].queryset = ProjectSite.objects.filter(
            project=project, is_active=True
        )
        self.fields["phase"].queryset = ProjectPhase.objects.filter(
            site__project=project
        )
        self.fields["unit_of_measure"].queryset = UnitOfMeasure.objects.filter(
            organization=organization, archived_at__isnull=True, is_active=True
        )

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])
