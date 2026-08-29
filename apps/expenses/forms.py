from django import forms

from apps.expenses.models import Expense, ExpenseCategory
from apps.projects.models import Project


class ExpenseForm(forms.ModelForm):
    """Form for recording an expense in the active organization."""

    project = forms.ModelChoiceField(queryset=Project.objects.none())

    class Meta:
        model = Expense
        fields = [  # noqa: RUF012
            "project",
            "category",
            "description",
            "vendor_name",
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

    def clean_category(self) -> str:
        category = self.cleaned_data["category"]
        if category not in ExpenseCategory.values:
            raise forms.ValidationError("Invalid expense category.")
        return category
