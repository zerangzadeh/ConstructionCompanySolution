from django import forms

from apps.contracts.models import Contract, ContractStatus
from apps.projects.models import Project


class ContractForm(forms.ModelForm):
    """Form for creating a contract in the active organization."""

    project = forms.ModelChoiceField(
        queryset=Project.objects.none(),
        empty_label="Select project",
    )

    class Meta:
        model = Contract
        fields = [  # noqa: RUF012
            "project",
            "contract_number",
            "title",
            "counterparty_name",
            "status",
            "contract_value",
            "signed_at",
            "start_date",
            "end_date",
            "notes",
        ]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
        ).order_by("name")

    def clean_status(self) -> str:
        status = self.cleaned_data["status"]
        if status not in ContractStatus.values:
            raise forms.ValidationError("Invalid contract status.")
        return status

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(
                "Contract end date cannot be before start date."
            )
        return cleaned_data
