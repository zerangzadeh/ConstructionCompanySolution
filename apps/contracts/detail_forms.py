"""Contract Detail forms for already registered application-service operations."""

from datetime import date
from decimal import Decimal

from django import forms

from apps.materials.models import UnitOfMeasure
from apps.organizations.models import InsuranceClassification
from apps.organizations.policy_services import available_insurance_classifications
from apps.parties.models import BusinessParty
from core.forms import JalaliDateMixin

from .models import (
    Contract,
    ContractDirection,
    ContractType,
    RetentionReleaseRequirement,
)


class DraftContractEditForm(forms.Form):
    title = forms.CharField(label="عنوان قرارداد", max_length=255)
    party = forms.ModelChoiceField(
        label="طرف قرارداد", queryset=BusinessParty.objects.none(), required=False
    )
    counterparty_name = forms.CharField(
        label="نام ثبت‌شده طرف قرارداد",
        max_length=255,
        required=False,
        help_text="با انتخاب طرف مرجع، نام آن در قرارداد ثبت می‌شود.",
    )
    direction = forms.ChoiceField(
        label="سمت قرارداد",
        choices=[("", "انتخاب نشده"), *ContractDirection.choices],
        required=False,
    )
    contract_type = forms.ChoiceField(
        label="نوع قرارداد",
        choices=[("", "انتخاب نشده"), *ContractType.choices],
        required=False,
    )
    contract_value = forms.DecimalField(
        label="مبلغ قرارداد", max_digits=18, decimal_places=2, min_value=Decimal(0)
    )
    notes = forms.CharField(
        label="یادداشت‌ها", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, organization, contract: Contract, **kwargs):
        initial = {
            name: getattr(contract, name)
            for name in (
                "title",
                "counterparty_name",
                "direction",
                "contract_type",
                "contract_value",
                "notes",
            )
        }
        initial["party"] = contract.party_id
        super().__init__(*args, initial=initial, auto_id="draft-base-%s", **kwargs)
        self.fields["party"].queryset = BusinessParty.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("display_name")

    def clean(self):
        values = super().clean()
        if values.get("party"):
            values["counterparty_name"] = values["party"].display_name
        elif not values.get("counterparty_name"):
            self.add_error(
                "counterparty_name",
                "نام طرف قرارداد را وارد کنید یا طرف مرجع را انتخاب کنید.",
            )
        return values


class DraftContractItemForm(forms.Form):
    description = forms.CharField(label="شرح ردیف", max_length=255)
    quantity = forms.DecimalField(
        label="مقدار", max_digits=18, decimal_places=4, min_value=Decimal("0.0001")
    )
    unit_of_measure = forms.ModelChoiceField(
        label="واحد اندازه‌گیری", queryset=UnitOfMeasure.objects.none()
    )
    unit_price = forms.DecimalField(
        label="قیمت واحد", max_digits=18, decimal_places=2, min_value=Decimal(0)
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, auto_id="draft-item-%s", **kwargs)
        self.fields["unit_of_measure"].queryset = UnitOfMeasure.objects.filter(
            organization=organization, is_active=True, archived_at__isnull=True
        ).order_by("name")


class ContractTermDraftForm(JalaliDateMixin, forms.Form):
    effective_from = forms.DateField(label="تاریخ اثر شرایط")
    payment_due_days = forms.IntegerField(
        label="مهلت پرداخت (روز)", min_value=0, max_value=3650, initial=0
    )
    retention_rate = forms.DecimalField(
        label="نرخ کسور تضمین (درصد)",
        max_digits=9,
        decimal_places=6,
        min_value=0,
        max_value=100,
        initial=0,
    )
    retention_cap = forms.DecimalField(
        label="سقف کسور تضمین", max_digits=18, decimal_places=4, min_value=0, initial=0
    )
    advance_recovery_rate = forms.DecimalField(
        label="نرخ بازیافت پیش‌پرداخت (درصد)",
        max_digits=9,
        decimal_places=6,
        min_value=0,
        max_value=100,
        initial=0,
    )
    advance_recovery_cap = forms.DecimalField(
        label="سقف بازیافت پیش‌پرداخت",
        max_digits=18,
        decimal_places=4,
        min_value=0,
        initial=0,
    )
    contractual_insurance_rate = forms.DecimalField(
        label="نرخ بیمه قراردادی (درصد)",
        max_digits=9,
        decimal_places=6,
        min_value=0,
        max_value=100,
        initial=0,
    )
    contractual_insurance_cap = forms.DecimalField(
        label="سقف بیمه قراردادی",
        max_digits=18,
        decimal_places=4,
        min_value=0,
        initial=0,
    )
    retention_release_requirement = forms.ChoiceField(
        label="شرط آزادسازی تضمین",
        choices=RetentionReleaseRequirement.choices,
        initial=RetentionReleaseRequirement.UNCONFIGURED,
    )
    retention_release_cap = forms.DecimalField(
        label="سقف آزادسازی تضمین",
        max_digits=18,
        decimal_places=4,
        min_value=0,
        initial=0,
    )
    insurance_classification = forms.ModelChoiceField(
        label="طبقه‌بندی بیمه",
        queryset=InsuranceClassification.objects.none(),
        required=False,
    )
    reason = forms.CharField(
        label="دلیل تهیه نسخه شرایط", widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, on_date: date, initial=None, **kwargs):
        values = {"effective_from": on_date, **(initial or {})}
        super().__init__(*args, initial=values, auto_id="draft-term-%s", **kwargs)
        cutoff = on_date
        if self.is_bound:
            try:
                cutoff = self.fields["effective_from"].clean(
                    self.data.get("effective_from")
                )
            except forms.ValidationError:
                pass
        self.fields[
            "insurance_classification"
        ].queryset = available_insurance_classifications(on_date=cutoff)
