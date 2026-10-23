from django import forms

from apps.accounts.models import User
from apps.daily_reports.models import DailyReport
from apps.organizations.authorization import scope_queryset
from apps.organizations.form_scoping import scoped_projects_for_form
from apps.organizations.models import (
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.parties.models import BusinessParty
from apps.projects.models import Activity, ProjectPhase, ProjectSite
from apps.quality.models import QualityIssue
from apps.workforce.models import Employee
from core.forms import JalaliDateMixin


class _StyledForm(JalaliDateMixin):
    def _style_fields(self) -> None:
        field_class = (
            "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
            "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 "
            "focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = field_class


class QualityIssueForm(_StyledForm, forms.ModelForm):
    class Meta:
        model = QualityIssue
        fields = [  # noqa: RUF012
            "project",
            "site",
            "phase",
            "activity",
            "daily_report",
            "issue_number",
            "identified_at",
            "issue_type",
            "severity",
            "description",
            "specification_reference",
        ]
        widgets = {  # noqa: RUF012
            "identified_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "specification_reference": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(
        self,
        *args: object,
        organization: Organization,
        membership: OrganizationMembership | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        for protected in ("project", "site", "phase", "activity", "daily_report"):
            self.fields[protected].queryset = self.fields[protected].queryset.none()
        for optional in ("site", "phase", "activity", "daily_report"):
            self.fields[optional].required = False
        self._style_fields()
        if not isinstance(membership, OrganizationMembership) or (
            membership.organization_id != organization.pk
        ):
            return
        self.fields["project"].queryset = scoped_projects_for_form(
            organization=organization, membership=membership
        )
        self.fields["site"].queryset = scope_queryset(
            ProjectSite.objects.filter(organization=organization, is_active=True),
            membership=membership,
            project_lookup="project_id",
            site_lookup="pk",
        )
        self.fields["phase"].queryset = scope_queryset(
            ProjectPhase.objects.filter(organization=organization),
            membership=membership,
            project_lookup="site__project_id",
            site_lookup="site_id",
        )
        self.fields["activity"].queryset = scope_queryset(
            Activity.objects.filter(
                organization=organization, archived_at__isnull=True, is_active=True
            ),
            membership=membership,
            project_lookup="project_id",
            site_lookup="site_id",
        )
        self.fields["daily_report"].queryset = scope_queryset(
            DailyReport.objects.filter(organization=organization),
            membership=membership,
            project_lookup="project_id",
            site_lookup="site_id",
        )


class QualityIssueAssignmentForm(_StyledForm, forms.Form):
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


class VerificationSubmissionForm(_StyledForm, forms.Form):
    corrective_action_result = forms.CharField(
        label="نتیجه اقدام اصلاحی", widget=forms.Textarea(attrs={"rows": 4})
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._style_fields()


class VerificationForm(_StyledForm, forms.Form):
    verification_summary = forms.CharField(
        label="نتیجه راستی‌آزمایی", widget=forms.Textarea(attrs={"rows": 4})
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
