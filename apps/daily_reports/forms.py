from django import forms

from apps.daily_reports.models import (
    DailyActivity,
    DailyReport,
    DailyReportEquipmentEntry,
    DailyReportLaborEntry,
    DailyReportMaterialEntry,
    DelayEvent,
)
from apps.materials.models import Material, UnitOfMeasure
from apps.projects.models import (
    Activity,
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectSite,
)


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
        fields = [  # noqa: RUF012
            "material",
            "material_name",
            "quantity",
            "unit_of_measure",
            "unit",
            "notes",
        ]
        widgets = {  # noqa: RUF012
            "material_name": forms.TextInput(
                attrs={"placeholder": "Ready-mix concrete"}
            ),
            "quantity": forms.NumberInput(attrs={"min": "0.0001", "step": "0.0001"}),
            "unit": forms.TextInput(attrs={"placeholder": "m³"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(
        self, *args: object, organization_id: object | None = None, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        if organization_id is not None:
            self.fields["material"].queryset = Material.objects.filter(
                organization_id=organization_id,
                archived_at__isnull=True,
                is_active=True,
            )
            self.fields["unit_of_measure"].queryset = UnitOfMeasure.objects.filter(
                organization_id=organization_id,
                archived_at__isnull=True,
                is_active=True,
            )
        self.fields["material"].required = False
        self.fields["unit_of_measure"].required = False

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        material = cleaned_data.get("material")
        if material:
            cleaned_data["material_name"] = material.name
            cleaned_data["unit_of_measure"] = material.unit_of_measure
            cleaned_data["unit"] = material.unit_of_measure.symbol
        return cleaned_data


class DailyActivityForm(_DailyReportEntryForm):
    class Meta:
        model = DailyActivity
        fields = [  # noqa: RUF012
            "activity",
            "description",
            "quantity",
            "unit_of_measure",
            "progress_percent",
            "notes",
        ]
        widgets = {  # noqa: RUF012
            "description": forms.Textarea(attrs={"rows": 2}),
            "quantity": forms.NumberInput(attrs={"min": "0.0001", "step": "0.0001"}),
            "progress_percent": forms.NumberInput(
                attrs={"min": "0", "max": "100", "step": "0.01"}
            ),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args: object, report: DailyReport, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["activity"].queryset = Activity.objects.filter(
            organization=report.organization,
            project=report.project,
            archived_at__isnull=True,
            is_active=True,
        )
        self.fields["unit_of_measure"].queryset = UnitOfMeasure.objects.filter(
            organization=report.organization, archived_at__isnull=True, is_active=True
        )
        self.fields["activity"].required = False
        self.fields["unit_of_measure"].required = False
        self.fields["description"].required = False

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        activity = cleaned_data.get("activity")
        if activity and not cleaned_data.get("description"):
            cleaned_data["description"] = activity.name
        return cleaned_data


class DelayEventForm(_DailyReportEntryForm):
    class Meta:
        model = DelayEvent
        fields = [  # noqa: RUF012
            "activity",
            "occurred_on",
            "category",
            "cause",
            "impact",
            "responsible_party",
            "duration_hours",
        ]
        widgets = {  # noqa: RUF012
            "occurred_on": forms.DateInput(attrs={"type": "date"}),
            "cause": forms.Textarea(attrs={"rows": 2}),
            "impact": forms.Textarea(attrs={"rows": 2}),
            "duration_hours": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args: object, report: DailyReport, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["activity"].queryset = Activity.objects.filter(
            organization=report.organization,
            project=report.project,
            archived_at__isnull=True,
            is_active=True,
        )
        self.fields["activity"].required = False
