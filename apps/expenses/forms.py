from typing import ClassVar

from django import forms
from django.urls import reverse

from apps.expenses.models import (
    Expense,
    ExpenseAllocation,
    ExpenseCategory,
    ExpenseClassification,
    PlatformExpenseGroup,
    RecurringExpenseTemplate,
)
from apps.organizations.authorization import scope_queryset
from apps.organizations.form_scoping import (
    normalized_uuid,
    scope_project_related_choices,
    scoped_projects_for_form,
    selected_form_project,
)
from apps.organizations.models import OrganizationMembership
from apps.parties.models import BusinessParty
from apps.projects.models import (
    Activity,
    CBSNode,
    CostCenter,
    Project,
    ProjectBudgetControl,
    ProjectPhase,
    WBSNode,
)
from core.forms import JalaliDateMixin


class ExpenseForm(JalaliDateMixin, forms.ModelForm):
    """Form for recording an expense in the active organization."""

    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    phase = forms.ModelChoiceField(
        label="فاز پروژه",
        queryset=ProjectPhase.objects.none(),
        required=False,
        empty_label="بدون فاز",
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

    def __init__(
        self,
        *args,
        organization=None,
        membership=None,
        active_project=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.fields["category"].label = "گروه اصلی هزینه"
        self.fields["expense_category"].label = "دسته هزینه"
        self.fields["category"].choices = list(
            PlatformExpenseGroup.objects.filter(
                is_active=True, archived_at__isnull=True
            )
            .order_by("name")
            .values_list("code", "name")
        )
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
            data=self.data if self.is_bound else None,
            field_name=self.add_prefix("project"),
            projects=projects,
            active_project=active_project,
        )
        if not self.is_bound and selected_project is not None:
            self.initial.setdefault("project", selected_project.pk)
        phases = ProjectPhase.objects.filter(
            organization=organization,
            site__project__deleted_at__isnull=True,
        )
        if membership is not None:
            phases = scope_project_related_choices(
                phases,
                membership=membership,
                project_lookup="site__project_id",
                site_lookup="site_id",
                project=selected_project,
            )
        elif selected_project is not None:
            phases = phases.filter(site__project=selected_project)
        else:
            phases = phases.none()
        self.fields["phase"].queryset = phases.select_related(
            "site", "site__project"
        ).order_by("site__name", "name")
        self.fields["phase"].widget.attrs.update(
            {
                "data-cascade-field": "phase",
                "data-cascade-source": "expenses",
                "data-options-url": reverse("organizations:form_context_options"),
                "data-empty-label": "بدون فاز",
            }
        )
        self.fields["party"].queryset = BusinessParty.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("display_name")
        self.fields["expense_category"].queryset = ExpenseCategory.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        ).order_by("name")

    def clean_category(self) -> str:
        category = self.cleaned_data["category"]
        if not PlatformExpenseGroup.objects.filter(
            code=category, is_active=True, archived_at__isnull=True
        ).exists():
            raise forms.ValidationError("گروه اصلی هزینه معتبر نیست.")
        return category

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        phase = cleaned_data.get("phase")
        if phase and project and phase.site.project_id != project.pk:
            self.add_error("phase", "فاز انتخاب‌شده متعلق به این پروژه نیست.")
        if phase and project is None:
            self.add_error("phase", "ابتدا پروژه مجاز را انتخاب کنید.")
        return cleaned_data


class ExpenseVoidForm(forms.Form):
    reason = forms.CharField(
        label="دلیل ابطال",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class ExpenseDraftForm(ExpenseForm):
    source_reference = forms.CharField(
        label="مرجع سند/صورتحساب", max_length=160, required=True
    )
    classification = forms.ChoiceField(
        label="نوع هزینه", choices=ExpenseClassification.choices
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput())

    class Meta(ExpenseForm.Meta):
        fields: ClassVar[list[str]] = [
            *ExpenseForm.Meta.fields,
            "classification",
            "source_reference",
            "idempotency_key",
        ]


class ExpenseAllocationForm(forms.ModelForm):
    class Meta:
        model = ExpenseAllocation
        fields: ClassVar[list[str]] = [
            "project",
            "wbs_node",
            "activity",
            "cbs_node",
            "cost_center",
            "amount",
            "allocation_basis_reference",
        ]

    def __init__(
        self, *args, organization=None, membership=None, expense=None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        for name in ("project", "wbs_node", "activity"):
            self.fields[name].queryset = self.fields[name].queryset.none()
        self.fields["cbs_node"].queryset = CBSNode.objects.filter(
            organization=organization, is_leaf=True, structure_version__status="locked"
        )
        self.fields["cost_center"].queryset = CostCenter.objects.filter(
            organization=organization, structure_version__status="locked"
        )
        if not isinstance(membership, OrganizationMembership) or (
            organization is None or membership.organization_id != organization.pk
        ):
            return
        projects = scope_queryset(
            Project.objects.filter(organization=organization, deleted_at__isnull=True),
            membership=membership,
            project_lookup="pk",
        )
        self.fields["project"].queryset = projects
        wbs_nodes = scope_queryset(
            WBSNode.objects.filter(
                organization=organization, is_active=True, archived_at__isnull=True
            ),
            membership=membership,
            project_lookup="project_id",
        )
        activities = scope_queryset(
            Activity.objects.filter(
                organization=organization, is_active=True, archived_at__isnull=True
            ),
            membership=membership,
            project_lookup="project_id",
        )
        if self.is_bound:
            project = selected_form_project(
                data=self.data,
                field_name=self.add_prefix("project"),
                projects=projects,
                active_project=None,
            )
            wbs_nodes = (
                wbs_nodes.filter(project=project) if project else wbs_nodes.none()
            )
            wbs_id = normalized_uuid(self.data.get(self.add_prefix("wbs_node")))
            selected_wbs = wbs_nodes.filter(pk=wbs_id).first() if wbs_id else None
            activities = (
                activities.filter(project=project, wbs_node=selected_wbs)
                if project and selected_wbs
                else activities.none()
            )
            # The service supplies these non-editable relations at save time;
            # model validation needs the same trusted context before that call.
            if expense is not None and expense.organization_id == organization.pk:
                self.instance.expense = expense
                self.instance.organization = organization
            control = (
                ProjectBudgetControl.objects.filter(
                    organization=organization,
                    project=project,
                    governing_budget__status="accepted",
                )
                .select_related("governing_budget")
                .first()
                if project
                else None
            )
            if control:
                self.instance.governing_budget = control.governing_budget
        self.fields["wbs_node"].queryset = wbs_nodes
        self.fields["activity"].queryset = activities

    def _post_clean(self):
        # Invalid choices must fail before model.clean dereferences required FKs.
        if self.errors:
            return
        if not self.instance.expense_id:
            self.add_error(None, "An authorized expense is required for allocation.")
            return
        if not self.instance.governing_budget_id:
            self.add_error(
                None, "An accepted governing budget is required for expense coding."
            )
            return
        super()._post_clean()


class ExpenseReturnForm(forms.Form):
    reason = forms.CharField(
        label="دلیل بازگشت", max_length=1000, widget=forms.Textarea(attrs={"rows": 3})
    )


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields: ClassVar[list[str]] = ["code", "name", "primary_group"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["primary_group"].queryset = PlatformExpenseGroup.objects.filter(
            is_active=True, archived_at__isnull=True
        ).order_by("name")


class PlatformExpenseGroupForm(forms.ModelForm):
    class Meta:
        model = PlatformExpenseGroup
        fields: ClassVar[list[str]] = ["code", "name"]


class RecurringExpenseTemplateForm(JalaliDateMixin, forms.ModelForm):
    """Form for creating a recurring expense proposal in the Persian UI."""

    class Meta:
        model = RecurringExpenseTemplate
        labels: ClassVar[dict[str, str]] = {
            "project": "پروژه",
            "description": "توضیحات",
            "amount": "مبلغ",
            "classification": "نوع هزینه",
            "frequency": "دوره تکرار",
            "starts_on": "تاریخ شروع",
            "ends_on": "تاریخ پایان",
            "source_reference_prefix": "پیشوند مرجع سند",
        }
        fields: ClassVar[list[str]] = [
            "project",
            "description",
            "amount",
            "classification",
            "frequency",
            "starts_on",
            "ends_on",
            "source_reference_prefix",
        ]

    def __init__(self, *args, organization=None, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.none()
        if not isinstance(membership, OrganizationMembership) or (
            organization is None or membership.organization_id != organization.pk
        ):
            return
        self.fields["project"].queryset = scope_queryset(
            Project.objects.filter(organization=organization, deleted_at__isnull=True),
            membership=membership,
            project_lookup="pk",
        )

    def _post_clean(self):
        # Model.clean dereferences required Project/date values; reject incomplete
        # field validation before reaching those model invariants.
        if self.errors:
            return
        super()._post_clean()


class RecurringExpenseProposalForm(JalaliDateMixin, forms.Form):
    occurrence_on = forms.DateField(label="تاریخ رخداد")
