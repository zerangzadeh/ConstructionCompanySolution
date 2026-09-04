from django import forms

from apps.expenses.models import Expense, ExpenseCategory, LegacyExpenseCategory
from apps.parties.models import BusinessParty
from apps.projects.models import Project, ProjectPhase


class ExpenseForm(forms.ModelForm):
    """Form for recording an expense in the active organization."""

    project = forms.ModelChoiceField(queryset=Project.objects.none())
    phase = forms.ModelChoiceField(
        queryset=ProjectPhase.objects.none(),
        required=False,
        empty_label="No phase",
    )

    class Meta:
        model = Expense
        fields = [  # noqa: RUF012
            "project",
            "phase",
            "category",
            "description",
            "vendor_name",
            "party",
            "expense_category",
            "amount",
            "incurred_on",
            "receipt_reference",
            "notes",
        ]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
        ).order_by("name")
        self.fields["phase"].queryset = (
            ProjectPhase.objects.filter(
                organization=organization,
                site__project__deleted_at__isnull=True,
            )
            .select_related("site", "site__project")
            .order_by("site__project__name", "site__name", "name")
        )
        self.fields["party"].queryset = BusinessParty.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("display_name")
        self.fields["expense_category"].queryset = ExpenseCategory.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        ).order_by("name")

    def clean_category(self) -> str:
        category = self.cleaned_data["category"]
        if category not in LegacyExpenseCategory.values:
            raise forms.ValidationError("Invalid expense category.")
        return category

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        phase = cleaned_data.get("phase")
        if phase and project and phase.site.project_id != project.pk:
            self.add_error("phase", "Selected phase does not belong to the project.")
        return cleaned_data


class ExpenseVoidForm(forms.Form):
    reason = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
