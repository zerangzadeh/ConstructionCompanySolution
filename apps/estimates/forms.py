from django import forms

from apps.contracts.models import Contract
from apps.estimates.models import Estimate, EstimateItem
from apps.projects.models import Project


class EstimateForm(forms.ModelForm):
    """Form for creating an estimate in the active organization."""

    project = forms.ModelChoiceField(queryset=Project.objects.none())
    contract = forms.ModelChoiceField(
        queryset=Contract.objects.none(),
        required=False,
        empty_label="No contract",
    )

    class Meta:
        model = Estimate
        fields = [  # noqa: RUF012
            "project",
            "contract",
            "estimate_number",
            "title",
            "notes",
        ]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
        ).order_by("name")
        self.fields["contract"].queryset = (
            Contract.objects.filter(
                organization=organization,
                deleted_at__isnull=True,
                project__deleted_at__isnull=True,
            )
            .select_related("project")
            .order_by("contract_number")
        )

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        contract = cleaned_data.get("contract")
        if project and contract and contract.project_id != project.pk:
            raise forms.ValidationError(
                "Selected contract does not belong to the selected project."
            )
        return cleaned_data


class EstimateItemForm(forms.ModelForm):
    """Form for adding a priced item to an estimate."""

    class Meta:
        model = EstimateItem
        fields = ["description", "quantity", "unit", "unit_price", "sort_order"]  # noqa: RUF012
