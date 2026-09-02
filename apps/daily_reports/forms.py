from django import forms

from apps.daily_reports.models import (
    DailyReport,
    DailyReportEquipmentEntry,
    DailyReportLaborEntry,
    DailyReportMaterialEntry,
)
from apps.projects.models import Project, ProjectPhase, ProjectPhaseStatus, ProjectSite


class DailyReportForm(forms.ModelForm):
    """Form for recording one project's daily operational report."""

    project = forms.ModelChoiceField(queryset=Project.objects.none())
    site = forms.ModelChoiceField(queryset=ProjectSite.objects.none())
    phase = forms.ModelChoiceField(
        queryset=ProjectPhase.objects.none(),
        required=False,
        empty_label="No phase",
    )

    class Meta:
        model = DailyReport
        fields = [  # noqa: RUF012
            "project",
            "site",
            "phase",
            "reporting_date",
            "weather_conditions",
            "labor_count",
            "work_performed",
            "progress_summary",
            "issues_and_delays",
            "safety_notes",
            "quality_notes",
        ]
        widgets = {  # noqa: RUF012
            "reporting_date": forms.DateInput(attrs={"type": "date"}),
            "weather_conditions": forms.TextInput(
                attrs={"placeholder": "e.g. Clear, 28°C"}
            ),
            "labor_count": forms.NumberInput(attrs={"min": "0"}),
            "work_performed": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Completed work and activities"}
            ),
            "progress_summary": forms.Textarea(attrs={"rows": 3}),
            "issues_and_delays": forms.Textarea(attrs={"rows": 3}),
            "safety_notes": forms.Textarea(attrs={"rows": 3}),
            "quality_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
        ).order_by("name")
        self.fields["site"].queryset = (
            ProjectSite.objects.filter(
                organization=organization,
                project__deleted_at__isnull=True,
                is_active=True,
            )
            .select_related("project")
            .order_by("project__name", "name")
        )
        self.fields["phase"].queryset = (
            ProjectPhase.objects.filter(
                organization=organization,
                site__project__deleted_at__isnull=True,
                site__is_active=True,
                status=ProjectPhaseStatus.ACTIVE,
            )
            .select_related("site", "site__project")
            .order_by("site__project__name", "site__name", "name")
        )
        field_class = (
            "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
            "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 "
            "focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = field_class

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        site = cleaned_data.get("site")
        phase = cleaned_data.get("phase")
        if project and site and site.project_id != project.pk:
            self.add_error("site", "Selected worksite does not belong to the project.")
        if phase and site and phase.site_id != site.pk:
            self.add_error("phase", "Selected phase does not belong to the worksite.")
        return cleaned_data


class _DailyReportEntryForm(forms.ModelForm):
    """Apply the standard input style to daily report entry forms."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_class = (
            "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
            "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 "
            "focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = field_class


class DailyReportLaborEntryForm(_DailyReportEntryForm):
    class Meta:
        model = DailyReportLaborEntry
        fields = ["team_name", "worker_count", "hours_worked", "notes"]  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "team_name": forms.TextInput(attrs={"placeholder": "Concrete crew"}),
            "worker_count": forms.NumberInput(attrs={"min": "1"}),
            "hours_worked": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class DailyReportEquipmentEntryForm(_DailyReportEntryForm):
    class Meta:
        model = DailyReportEquipmentEntry
        fields = ["equipment_name", "hours_used", "notes"]  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "equipment_name": forms.TextInput(attrs={"placeholder": "Excavator"}),
            "hours_used": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class DailyReportMaterialEntryForm(_DailyReportEntryForm):
    class Meta:
        model = DailyReportMaterialEntry
        fields = ["material_name", "quantity", "unit", "notes"]  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "material_name": forms.TextInput(
                attrs={"placeholder": "Ready-mix concrete"}
            ),
            "quantity": forms.NumberInput(attrs={"min": "0.0001", "step": "0.0001"}),
            "unit": forms.TextInput(attrs={"placeholder": "m³"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
