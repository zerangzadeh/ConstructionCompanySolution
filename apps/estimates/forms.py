from django import forms
from django.urls import reverse

from apps.contracts.models import Contract
from apps.estimates.models import Estimate, EstimateItem
from apps.materials.models import UnitOfMeasure
from apps.organizations.form_scoping import (
    scope_project_related_choices,
    scoped_projects_for_form,
    selected_form_project,
)
from apps.projects.models import Project, ProjectPhase
from core.business_choices import configure_business_choice
from core.forms import JalaliDateMixin
from core.identifiers import canonicalize_upper_identifier


class EstimateForm(JalaliDateMixin, forms.ModelForm):
    """Form for creating an estimate in the active organization."""

    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    contract = forms.ModelChoiceField(
        label="قرارداد",
        queryset=Contract.objects.none(),
        required=False,
        empty_label="بدون قرارداد",
    )
    phase = forms.ModelChoiceField(
        label="فاز پروژه",
        queryset=ProjectPhase.objects.none(),
        required=False,
        empty_label="بدون فاز",
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

    def __init__(
        self,
        *args,
        organization=None,
        membership=None,
        active_project=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        projects = (
            scoped_projects_for_form(
                organization=organization,
                membership=membership,
            )
            if membership is not None
            else Project.objects.filter(
                organization=organization, deleted_at__isnull=True
            ).order_by("name")
        )
        self.fields["project"].queryset = projects
        self.fields["project"].widget.attrs["data-cascade-project"] = ""
        selected_project = selected_form_project(
            data=self.data if self.is_bound else self.initial,
            field_name=self.add_prefix("project"),
            projects=projects,
            active_project=None
            if self.is_bound or "project" in self.initial
            else active_project,
        )
        if not self.is_bound and selected_project is not None:
            self.initial.setdefault("project", selected_project.pk)

        contracts = Contract.objects.filter(
            organization=organization,
            deleted_at__isnull=True,
            project__deleted_at__isnull=True,
        )
        phases = ProjectPhase.objects.filter(
            organization=organization,
            site__project__deleted_at__isnull=True,
        )
        if membership is not None:
            contracts = scope_project_related_choices(
                contracts,
                membership=membership,
                project_lookup="project_id",
                project=selected_project,
            )
            phases = scope_project_related_choices(
                phases,
                membership=membership,
                project_lookup="site__project_id",
                site_lookup="site_id",
                project=selected_project,
            )
        elif selected_project is not None:
            contracts = contracts.filter(project=selected_project)
            phases = phases.filter(site__project=selected_project)
        else:
            contracts = contracts.none()
            phases = phases.none()
        self.fields["contract"].queryset = contracts.select_related("project").order_by(
            "contract_number"
        )
        self.fields["phase"].queryset = phases.select_related(
            "site", "site__project"
        ).order_by("site__name", "name")
        for field_name, empty_label in (
            ("contract", "بدون قرارداد"),
            ("phase", "بدون فاز"),
        ):
            self.fields[field_name].widget.attrs.update(
                {
                    "data-cascade-field": field_name,
                    "data-cascade-source": "estimates",
                    "data-options-url": reverse("organizations:form_context_options"),
                    "data-empty-label": empty_label,
                }
            )
        for name in ("project", "contract", "phase"):
            configure_business_choice(
                self, name, "estimate", parent="project" if name != "project" else None
            )

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        contract = cleaned_data.get("contract")
        phase = cleaned_data.get("phase")
        if project and contract and contract.project_id != project.pk:
            raise forms.ValidationError("قرارداد انتخاب‌شده متعلق به این پروژه نیست.")
        if phase and project and phase.site.project_id != project.pk:
            self.add_error("phase", "فاز انتخاب‌شده متعلق به این پروژه نیست.")
        if (contract or phase) and project is None:
            raise forms.ValidationError("ابتدا پروژه مجاز را انتخاب کنید.")
        return cleaned_data

    def clean_estimate_number(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["estimate_number"])


class EstimateItemForm(JalaliDateMixin, forms.ModelForm):
    """Form for adding a priced item to an estimate."""

    unit_of_measure = forms.ModelChoiceField(
        label="واحد اندازه‌گیری",
        queryset=UnitOfMeasure.objects.none(),
        required=False,
        empty_label="استفاده از واحد متنی قدیمی",
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit_of_measure"].queryset = UnitOfMeasure.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        ).order_by("name")
        self.fields.pop("unit")
        self.fields["unit_of_measure"].required = True
        configure_business_choice(self, "unit_of_measure", "estimate_item")

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
