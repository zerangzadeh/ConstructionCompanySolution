"""Business inputs for the existing receipt lifecycle; no warehouse ownership."""

from decimal import Decimal

from django import forms
from django.urls import reverse

from apps.procurement.forms import GoodsReceiptForm, ReceiptItemForm
from apps.procurement.models import GoodsReceiptStatus
from apps.procurement.order_forms import order_label
from core.business_choices import (
    InheritedParent,
    configure_business_choice,
    inherit_business_parent,
)
from core.forms import JalaliDateMixin


def receipt_choice(form, name, purpose):
    configure_business_choice(form, name, "contract")
    field = form.fields[name]
    field.widget.attrs["data-options-url"] = reverse(
        "procurement:receipt_choices", args=[purpose, name]
    )
    if name == "purchase_order":
        field.label_from_instance = order_label
        ids = [v for v, _ in field.widget.choices if v]
        field.widget.choices = [("", field.empty_label)] + [
            (str(o.pk), order_label(o)) for o in field.queryset.filter(pk__in=ids)
        ]


class ReceiptCreateForm(GoodsReceiptForm):
    def __init__(self, *args, orders, source_order=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purchase_order"].queryset = orders.filter(
            status="issued",
            current_version__isnull=False,
            current_version__lines__isnull=False,
        ).distinct()
        if source_order:
            # Recognize inaccessible lifecycle states only after tenant/scope resolution.
            self.fields["purchase_order"].queryset = orders.filter(pk=source_order.pk)
            inherit_business_parent(
                self,
                "purchase_order",
                source_order,
                detail_route="procurement:order_detail",
            )
        else:
            receipt_choice(self, "purchase_order", "create")
        self.inherited_parents = (
            InheritedParent(
                label="پروژه",
                title=source_order.project.name
                if source_order
                else "از سفارش خرید انتخابی",
                code=source_order.project.code if source_order else "",
                url=reverse("projects:detail", args=[source_order.project_id])
                if source_order
                else "",
            ),
        )
        self.fields["receipt_number"].widget.attrs["dir"] = "ltr"

    def clean(self):
        data = super().clean()
        if any(
            name in self.data
            for name in (
                "supplier",
                "project",
                "purchase_order_version",
                "warehouse",
                "destination_warehouse",
            )
        ):
            self.add_error(
                None,
                "تأمین‌کننده، پروژه و نسخه سفارش از سفارش خرید دریافت می‌شوند؛ تغییر زمینه رسید مجاز نیست.",
            )
        return data


class ReceiptLineForm(ReceiptItemForm):
    quantity = forms.DecimalField(
        label="مقدار این دریافت",
        min_value=Decimal("0.0001"),
        max_digits=18,
        decimal_places=4,
    )

    def __init__(self, *args, receipt, rows, **kwargs):
        super().__init__(*args, purchase_order=receipt.purchase_order, **kwargs)
        self.receipt = receipt
        self.rows = {
            r["line"].source_item_id: r
            for r in rows
            if not r["item"] and r["remaining"] > 0
        }
        field = self.fields["purchase_order_item"]
        field.queryset = field.queryset.filter(
            organization=receipt.organization, pk__in=self.rows
        )
        field.label_from_instance = lambda i: (
            f"{self.rows[i.pk]['line'].material.name} · {self.rows[i.pk]['line'].unit_of_measure.name} · باقی‌مانده {self.rows[i.pk]['remaining']}"
        )
        field.error_messages["invalid_choice"] = (
            "ردیف انتخاب‌شده در اقلام مجاز این رسید نیست یا قبلاً افزوده شده است."
        )
        self.fields["quantity"].min_value = Decimal("0.0001")

    def clean(self):
        data = super().clean()
        item, quantity = data.get("purchase_order_item"), data.get("quantity")
        if item and quantity and quantity > self.rows[item.pk]["remaining"]:
            self.add_error(
                "quantity", "مقدار این دریافت نمی‌تواند از باقی‌مانده سفارش بیشتر باشد."
            )
        if any(
            name in self.data
            for name in (
                "project",
                "supplier",
                "material",
                "unit_of_measure",
                "purchase_order",
                "purchase_order_version",
            )
        ):
            self.add_error(None, "زمینه قلم رسید فقط از ردیف مجاز سفارش دریافت می‌شود.")
        return data


class ReceiptFilterForm(JalaliDateMixin, forms.Form):
    q = forms.CharField(label="جست‌وجو", required=False)
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *GoodsReceiptStatus.choices],
    )
    project = forms.ModelChoiceField(label="پروژه", queryset=None, required=False)
    supplier = forms.ModelChoiceField(label="تأمین‌کننده", queryset=None, required=False)
    date_from = forms.DateField(label="دریافت از تاریخ", required=False)
    date_to = forms.DateField(label="دریافت تا تاریخ", required=False)

    def __init__(self, *args, projects, suppliers, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = projects
        self.fields["supplier"].queryset = suppliers
        for name in ("project", "supplier"):
            receipt_choice(self, name, "filter")
        self.fields["q"].widget.attrs["placeholder"] = (
            "شماره رسید، سفارش، تأمین‌کننده یا پروژه…"
        )
