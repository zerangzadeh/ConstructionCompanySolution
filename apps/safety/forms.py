from django import forms

from apps.accounts.models import User
from apps.daily_reports.models import DailyReport
from apps.organizations.models import MembershipStatus, Organization
from apps.parties.models import BusinessParty
from apps.projects.models import Activity, Project, ProjectPhase, ProjectSite
from apps.safety.models import SafetyIncident
from apps.workforce.models import Employee


class _StyledForm:
    def _style_fields(self) -> None:
        field_class = (
            "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
            "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 "
            "focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = field_class


class SafetyIncidentForm(_StyledForm, forms.ModelForm):
    class Meta:
        model = SafetyIncident
        fields = [  # noqa: RUF012
            "project",
            "site",
            "phase",
            "activity",
            "daily_report",
            "incident_number",
            "occurred_at",
            "incident_type",
            "severity",
            "description",
            "immediate_action",
        ]
        widgets = {  # noqa: RUF012
            "occurred_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "immediate_action": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        )
        self.fields["site"].queryset = ProjectSite.objects.filter(
            organization=organization, is_active=True
        )
        self.fields["phase"].queryset = ProjectPhase.objects.filter(
            organization=organization
        )
        self.fields["activity"].queryset = Activity.objects.filter(
            organization=organization, archived_at__isnull=True, is_active=True
        )
        self.fields["daily_report"].queryset = DailyReport.objects.filter(
            organization=organization
        )
        for optional in ("site", "phase", "activity", "daily_report"):
            self.fields[optional].required = False
        self._style_fields()


class SafetyIncidentAssignmentForm(_StyledForm, forms.Form):
    responsible_user = forms.ModelChoiceField(
        label="کاربر مسئول", queryset=User.objects.none(), required=False
    )
    responsible_employee = forms.ModelChoiceField(
        label="کارمند مسئول", queryset=Employee.objects.none(), required=False
    )
    responsible_party = forms.ModelChoiceField(
        label="طرف تجاری مسئول", queryset=BusinessParty.objects.none(), required=False
    )
    due_date = forms.DateField(
        label="مهلت اقدام", widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["responsible_user"].queryset = User.objects.filter(
            organization_memberships__organization=organization,
            organization_memberships__status=MembershipStatus.ACTIVE,
            organization_memberships__role_definition__is_active=True,
            is_active=True,
        ).distinct()
        self.fields["responsible_employee"].queryset = Employee.objects.filter(
            organization=organization, archived_at__isnull=True
        )
        self.fields["responsible_party"].queryset = BusinessParty.objects.filter(
            organization=organization, archived_at__isnull=True
        )
        self._style_fields()

    def clean(self) -> dict[str, object]:
        data = super().clean()
        if not any(
            data.get(field)
            for field in (
                "responsible_user",
                "responsible_employee",
                "responsible_party",
            )
        ):
            raise forms.ValidationError("حداقل یک مسئول تعیین کنید.")
        return data


class CorrectiveActionForm(_StyledForm, forms.Form):
    corrective_action = forms.CharField(
        label="اقدام اصلاحی", widget=forms.Textarea(attrs={"rows": 4})
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._style_fields()


class ResolutionForm(_StyledForm, forms.Form):
    resolution_summary = forms.CharField(
        label="شرح رفع حادثه", widget=forms.Textarea(attrs={"rows": 4})
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._style_fields()


class ClosureForm(_StyledForm, forms.Form):
    closure_summary = forms.CharField(
        label="جمع‌بندی بستن", widget=forms.Textarea(attrs={"rows": 4})
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._style_fields()
