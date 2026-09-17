from django import forms

from apps.contracts.models import Contract
from apps.parties.models import BusinessParty
from apps.payments.models import Payment
from apps.projects.models import Project, ProjectPhase
from core.forms import JalaliDateMixin
from core.identifiers import canonicalize_upper_identifier


class PaymentForm(JalaliDateMixin, forms.ModelForm):
    """Form for recording a payment in the active organization."""

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
            "party",
            "reference",
            "notes",
        ]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_number"].label = "شماره دریافت/ پرداخت"
        self.fields["paid_on"].label = "تاریخ دریافت/ پرداخت"
        self.fields["method"].label = "روش دریافت/ پرداخت"
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
        self.fields["party"].queryset = BusinessParty.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("display_name")

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        contract = cleaned_data.get("contract")
        phase = cleaned_data.get("phase")
        if project and contract and contract.project_id != project.pk:
            self.add_error("contract", "قرارداد انتخاب‌شده متعلق به این پروژه نیست.")
        if phase and project and phase.site.project_id != project.pk:
            self.add_error("phase", "فاز انتخاب‌شده متعلق به این پروژه نیست.")
        return cleaned_data

    def clean_payment_number(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["payment_number"])


class PaymentVoidForm(forms.Form):
    """Requires an explicit reason before voiding a posted payment."""

    reason = forms.CharField(label="دلیل ابطال", widget=forms.Textarea, max_length=1000)
