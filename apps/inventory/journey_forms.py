"""Business-labelled Inventory entry forms over existing source contracts."""

from decimal import Decimal
from urllib.parse import urlencode

from django import forms
from django.urls import reverse
from django.utils import timezone

from apps.inventory.forms import ReversalForm, StockTransactionForm, _StyledForm
from apps.inventory.journey_ui import source_label, warehouse_label
from apps.inventory.models import StockTransactionStatus, StockTransactionType
from apps.procurement.models import GoodsReceiptItem
from core.business_choices import (
    InheritedParent,
    InheritedParentInput,
    configure_business_choice,
)
from core.forms import JalaliDateMixin


def inventory_choice(form, name, purpose, label=None, **context):
    configure_business_choice(form, name, "contract")
    field = form.fields[name]
    field.widget.attrs["data-options-url"] = reverse(
        "inventory:journey_choices", args=[purpose, name]
    ) + ("?" + urlencode(context) if context else "")
    if label:
        field.label_from_instance = label
        ids = [v for v, _ in field.widget.choices if v]
        field.widget.choices = [("", field.empty_label)] + [
            (str(i.pk), label(i)) for i in field.queryset.filter(pk__in=ids)
        ]


class SourceSelectionForm(_StyledForm):
    goods_receipt_item = forms.ModelChoiceField(
        label="قلم رسید کالای نهایی‌شده", queryset=GoodsReceiptItem.objects.none()
    )

    def __init__(self, *args, sources, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["goods_receipt_item"].queryset = sources
        inventory_choice(self, "goods_receipt_item", "source", source_label)


class ReceiptEntryForm(_StyledForm):
    goods_receipt_item = forms.ModelChoiceField(
        label="قلم رسید کالا",
        queryset=GoodsReceiptItem.objects.none(),
        widget=forms.HiddenInput(),
    )
    transaction_number = forms.CharField(label="شماره ورود به انبار", max_length=80)
    destination_warehouse = forms.ModelChoiceField(label="انبار مقصد", queryset=None)
    occurred_at = forms.DateTimeField(label="تاریخ و زمان ورود")
    reference = forms.CharField(label="مرجع ورود", max_length=120, required=False)
    notes = forms.CharField(
        label="یادداشت", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    transaction_type = forms.ChoiceField(
        choices=[("receipt", "ورود از خرید")],
        initial="receipt",
        widget=forms.HiddenInput(),
        required=False,
        label="نوع گردش",
        error_messages={
            "invalid_choice": "نوع گردش ارسالی با ورود از رسید کالا هم‌خوان نیست."
        },
    )
    material = forms.UUIDField(
        label="مصالح",
        widget=forms.HiddenInput(),
        required=False,
        error_messages={"invalid": "مصالح ارسالی معتبر نیست."},
    )
    project = forms.UUIDField(
        label="پروژه",
        widget=forms.HiddenInput(),
        required=False,
        error_messages={"invalid": "پروژه ارسالی معتبر نیست."},
    )
    quantity = forms.DecimalField(
        label="مقدار",
        max_digits=18,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        widget=forms.HiddenInput(),
        required=False,
    )

    def __init__(self, *args, source, warehouses, **kwargs):
        super().__init__(*args, **kwargs)
        self.source = source
        self.fields["goods_receipt_item"].queryset = GoodsReceiptItem.objects.filter(
            organization=source.organization, pk=source.pk
        )
        self.fields["goods_receipt_item"].widget = InheritedParentInput(source.pk)
        self.fields["goods_receipt_item"].error_messages["invalid_choice"] = (
            "قلم رسید با زمینه این ورود هم‌خوان نیست."
        )
        self.fields["destination_warehouse"].queryset = warehouses
        self.fields["destination_warehouse"].error_messages["invalid_choice"] = (
            "انبار انتخاب‌شده برای پروژه و رسید این ورود مجاز نیست."
        )
        self.initial.update(
            goods_receipt_item=source.pk,
            material=source.material_id,
            project=source.goods_receipt.project_id,
            quantity=source.quantity,
            transaction_type="receipt",
            reference=source.goods_receipt.receipt_number,
        )
        self.inherited_parents = (
            InheritedParent(
                label="پروژه",
                title=source.goods_receipt.project.name,
                code=source.goods_receipt.project.code,
                url="",
            ),
        )
        self.fields["transaction_number"].widget.attrs["dir"] = "ltr"
        inventory_choice(
            self,
            "destination_warehouse",
            "warehouse",
            warehouse_label,
            goods_receipt_item=str(source.pk),
        )

    def clean_occurred_at(self):
        value = self.cleaned_data["occurred_at"]
        return timezone.make_aware(value) if timezone.is_naive(value) else value

    def clean(self):
        data = super().clean()
        expected = {
            "material": self.source.material_id,
            "project": self.source.goods_receipt.project_id,
            "quantity": self.source.quantity,
            "transaction_type": "receipt",
        }
        if (
            any(data.get(k) not in (None, "", v) for k, v in expected.items())
            or self.data.get("unit_of_measure", str(self.source.unit_of_measure_id))
            != str(self.source.unit_of_measure_id)
            or self.data.get("source_warehouse")
        ):
            self.add_error(
                None,
                "مصالح، واحد، پروژه و مقدار ورود باید دقیقاً با قلم رسید کالا یکسان باشند.",
            )
        data.update(
            material=self.source.material,
            unit_of_measure=self.source.unit_of_measure,
            project=self.source.goods_receipt.project,
            quantity=self.source.quantity,
            transaction_type="receipt",
        )
        return data


class OtherMovementForm(StockTransactionForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["transaction_type"].choices = [
            c for c in self.fields["transaction_type"].choices if c[0] != "receipt"
        ]
        for name in (
            "source_warehouse",
            "destination_warehouse",
            "material",
            "project",
            "goods_receipt_item",
        ):
            inventory_choice(
                self,
                name,
                "other",
                source_label
                if name == "goods_receipt_item"
                else warehouse_label
                if name.endswith("warehouse")
                else None,
            )
        self.fields["quantity"].min_value = Decimal("0.0001")


class MovementFilterForm(JalaliDateMixin, forms.Form):
    q = forms.CharField(label="جست‌وجو", required=False)
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *StockTransactionStatus.choices],
    )
    transaction_type = forms.ChoiceField(
        label="نوع گردش",
        required=False,
        choices=[("", "همه انواع"), *StockTransactionType.choices],
    )
    project = forms.ModelChoiceField(label="پروژه", queryset=None, required=False)
    warehouse = forms.ModelChoiceField(label="انبار", queryset=None, required=False)
    date_from = forms.DateField(label="ورود از تاریخ", required=False)
    date_to = forms.DateField(label="ورود تا تاریخ", required=False)

    def __init__(self, *args, projects, warehouses, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = projects
        self.fields["warehouse"].queryset = warehouses
        for name in ("project", "warehouse"):
            inventory_choice(
                self, name, "filter", warehouse_label if name == "warehouse" else None
            )
        self.fields["q"].widget.attrs["placeholder"] = (
            "شماره گردش، رسید کالا، مصالح، انبار یا پروژه…"
        )


class MovementReversalForm(ReversalForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reversal_number"].widget.attrs["dir"] = "ltr"
