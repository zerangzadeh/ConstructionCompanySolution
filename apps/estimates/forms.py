from django import forms

from apps.contracts.models import Contract
from apps.estimates.models import Estimate, EstimateItem
from apps.materials.models import UnitOfMeasure
from apps.projects.models import Project, ProjectPhase
from core.identifiers import canonicalize_upper_identifier


class EstimateForm(forms.ModelForm):
    """Form for creating an estimate in the active organization."""

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
        model = Estimate
        fields = [  # noqa: RUF012
            "project",
            "contract",
            "phase",
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
            raise forms.ValidationError(
                "Selected contract does not belong to the selected project."
            )
        if phase and project and phase.site.project_id != project.pk:
            self.add_error("phase", "Selected phase does not belong to the project.")
        return cleaned_data

    def clean_estimate_number(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["estimate_number"])


class EstimateItemForm(forms.ModelForm):
    """Form for adding a priced item to an estimate."""

    unit_of_measure = forms.ModelChoiceField(
        queryset=UnitOfMeasure.objects.none(),
        required=False,
        empty_label="Legacy unit text",
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit_of_measure"].queryset = UnitOfMeasure.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        ).order_by("name")

    class Meta:
        model = EstimateItem
        fields = [  # noqa: RUF012
            "description",
            "quantity",
            "unit",
            "unit_of_measure",
            "unit_price",
            "sort_order",
        ]
