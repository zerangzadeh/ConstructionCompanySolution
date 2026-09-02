from django import forms

from apps.contracts.models import Contract
from apps.payments.models import Payment
from apps.projects.models import Project, ProjectPhase


class PaymentForm(forms.ModelForm):
    """Form for recording a payment in the active organization."""

    project = forms.ModelChoiceField(queryset=Project.objects.none())
    contract = forms.ModelChoiceField(
        queryset=Contract.objects.none(),
        required=False,
        empty_label="No contract",
    )
    phase = forms.ModelChoiceField(
        queryset=ProjectPhase.objects.none(),
        required=False,
        empty_label="No phase",
    )

    class Meta:
        model = Payment
        fields = [  # noqa: RUF012
            "project",
            "contract",
            "phase",
            "payment_number",
            "direction",
            "amount",
            "paid_on",
            "method",
            "counterparty_name",
            "reference",
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
        self.fields["phase"].queryset = (
            ProjectPhase.objects.filter(
                organization=organization,
                site__project__deleted_at__isnull=True,
            )
            .select_related("site", "site__project")
            .order_by("site__project__name", "site__name", "name")
        )

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        contract = cleaned_data.get("contract")
        phase = cleaned_data.get("phase")
        if project and contract and contract.project_id != project.pk:
            self.add_error(
                "contract", "Selected contract does not belong to the project."
            )
        if phase and project and phase.site.project_id != project.pk:
            self.add_error("phase", "Selected phase does not belong to the project.")
        return cleaned_data


class PaymentVoidForm(forms.Form):
    """Requires an explicit reason before voiding a posted payment."""

    reason = forms.CharField(widget=forms.Textarea, max_length=1000)
