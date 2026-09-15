from django import forms

from apps.contracts.models import Contract, ContractStatus
from apps.parties.models import BusinessParty
from apps.projects.models import Project
from core.forms import JalaliDateMixin
from core.identifiers import canonicalize_upper_identifier


class ContractForm(JalaliDateMixin, forms.ModelForm):
    """Form for creating a contract in the active organization."""

    project = forms.ModelChoiceField(
        label="پروژه",
        queryset=Project.objects.none(),
        empty_label="پروژه را انتخاب کنید",
    )

    class Meta:
        model = Contract
        fields = [  # noqa: RUF012
            "project",
            "contract_number",
            "title",
            "counterparty_name",
            "party",
            "direction",
            "contract_type",
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
        self.fields["party"].queryset = BusinessParty.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("display_name")

    def clean_status(self) -> str:
        status = self.cleaned_data["status"]
        if status not in ContractStatus.values:
            raise forms.ValidationError("وضعیت قرارداد معتبر نیست.")
        return status

    def clean_contract_number(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["contract_number"])

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(
                "تاریخ پایان قرارداد نمی‌تواند پیش از تاریخ شروع باشد."
            )
        return cleaned_data
