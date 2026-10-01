from typing import ClassVar

from django import forms

from apps.expenses.models import (
    Expense,
    ExpenseAllocation,
    ExpenseCategory,
    ExpenseClassification,
    PlatformExpenseGroup,
    RecurringExpenseTemplate,
)
from apps.parties.models import BusinessParty
from apps.projects.models import (
    Activity,
    CBSNode,
    CostCenter,
    Project,
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

    def __init__(self, *args, organization=None, **kwargs):
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

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        )
        self.fields["wbs_node"].queryset = WBSNode.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        )
        self.fields["activity"].queryset = Activity.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        )
        self.fields["cbs_node"].queryset = CBSNode.objects.filter(
            organization=organization, is_leaf=True, structure_version__status="locked"
        )
        self.fields["cost_center"].queryset = CostCenter.objects.filter(
            organization=organization, structure_version__status="locked"
        )


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

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        )


class RecurringExpenseProposalForm(JalaliDateMixin, forms.Form):
    occurrence_on = forms.DateField(label="تاریخ رخداد")
