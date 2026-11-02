"""Business-labelled PO presentation forms over the existing service contracts."""

from django import forms
from django.urls import reverse

from apps.procurement import models as m
from apps.procurement.forms import GoodsReceiptForm, OrderItemForm, PurchaseOrderForm
from apps.procurement.request_forms import material_label
from core.business_choices import (
    InheritedParentInput,
    configure_business_choice,
    inherit_business_parent,
)
from core.forms import JalaliDateMixin


def request_label(row):
    return f"{row.request_number} · {row.title} · {row.project.name}"


def order_label(row):
    return f"{row.order_number} · {row.supplier.display_name} · {row.project.name}"


def choice_ui(form, name, purpose, label=None, **context):
    configure_business_choice(form, name, "contract")
    field = form.fields[name]
    from urllib.parse import urlencode

    field.widget.attrs["data-options-url"] = reverse(
        "procurement:order_choices", args=[purpose, name]
    ) + ("?" + urlencode({k: str(v) for k, v in context.items()}) if context else "")
    if label:
        field.label_from_instance = label
        ids = [value for value, _ in field.widget.choices if value]
        field.widget.choices = [("", field.empty_label)] + [
            (str(row.pk), label(row)) for row in field.queryset.filter(pk__in=ids)
        ]


class OrderCreateForm(PurchaseOrderForm):
    def __init__(self, *args, context_project=None, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("project", "supplier", "purchase_request"):
            choice_ui(
                self,
                name,
                "create",
                request_label if name == "purchase_request" else None,
            )
        self.fields["purchase_request"].widget.attrs.update(
            {"data-depends-on": "project", "data-requires-parent": "true"}
        )
        if context_project:
            inherit_business_parent(
                self, "project", context_project, detail_route="projects:detail"
            )
        self.fields["order_number"].widget.attrs["dir"] = "ltr"


class OrderLineForm(OrderItemForm):
    def __init__(self, *args, purchase_order, **kwargs):
        super().__init__(*args, purchase_order=purchase_order, **kwargs)
        choice_ui(self, "material", "line", material_label, order=purchase_order.pk)
        choice_ui(
            self,
            "purchase_request_item",
            "line",
            lambda row: (
                f"{row.material.name} · {row.quantity} {row.unit_of_measure.symbol}"
            ),
            order=purchase_order.pk,
        )


class AwardOrderForm(JalaliDateMixin, forms.Form):
    order_number = forms.CharField(label="شماره سفارش خرید", max_length=80)
    order_date = forms.DateField(label="تاریخ سفارش")
    expected_delivery_date = forms.DateField(
        label="تاریخ تحویل موردانتظار", required=False
    )
    notes = forms.CharField(
        label="یادداشت", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, award, supplier, rows, replay=None, **kwargs):
        super().__init__(*args, **kwargs)
        rfq = award.comparison.commercial_scope.rfq_version.rfq
        self.award, self.supplier, self.rows, self.replay = (
            award,
            supplier,
            rows,
            replay,
        )
        for name, parent, label in [
            ("award", award, "انتخاب نهایی"),
            ("supplier", supplier, "تأمین‌کننده"),
            ("project", rfq.project, "پروژه"),
        ]:
            self.fields[name] = forms.ModelChoiceField(
                label=label,
                queryset=type(parent).objects.filter(pk=parent.pk),
                widget=InheritedParentInput(parent.pk),
            )
            self.initial[name] = parent.pk
        inherit_business_parent(
            self, "project", rfq.project, detail_route="projects:detail"
        )
        allowed = [r["allocation"].pk for r in rows if r["eligible"]]
        if replay:
            allowed += list(
                replay.items.values_list("source_award_allocation_id", flat=True)
            )
        self.fields["allocations"] = forms.ModelMultipleChoiceField(
            label="تخصیص‌های مصوب برای این سفارش",
            queryset=m.SourcingAwardAllocation.objects.filter(
                organization=award.organization,
                award=award,
                pk__in=allowed,
                quote_revision__envelope__supplier=supplier,
            ),
            widget=forms.CheckboxSelectMultiple,
            error_messages={
                "invalid_choice": "تخصیص انتخاب‌شده متعلق به منبع و تأمین‌کننده مجاز این سفارش نیست.",
                "invalid_pk_value": "تخصیص انتخاب‌شده معتبر نیست؛ از گزینه‌های مجاز همین صفحه انتخاب کنید.",
                "invalid_list": "تخصیص‌ها باید از گزینه‌های مجاز این صفحه انتخاب شوند.",
            },
        )
        by_id = {r["allocation"].pk: r for r in rows}
        self.fields["allocations"].label_from_instance = lambda a: (
            f"{by_id[a.pk]['material'].name if by_id[a.pk]['material'] else 'بسته'} · مقدار مصوب {a.quantity} {by_id[a.pk]['scope'].unit_of_measure.symbol} · قیمت واحد {by_id[a.pk]['unit_price']} {by_id[a.pk]['currency']}"
        )
        self.fields["order_number"].widget.attrs["dir"] = "ltr"

    def clean(self):
        data = super().clean()
        if (
            data.get("expected_delivery_date")
            and data.get("order_date")
            and data["expected_delivery_date"] < data["order_date"]
        ):
            self.add_error(
                "expected_delivery_date",
                "تاریخ تحویل نمی‌تواند پیش از تاریخ سفارش باشد.",
            )
        if any(
            name in self.data
            for name in ("quantity", "unit_price", "allocation_quantity")
        ):
            self.add_error(
                None,
                "مقدار و قیمت سفارش فقط از تخصیص مصوب دریافت می‌شود؛ تغییر آن در این فرم مجاز نیست.",
            )
        return data


class OrderFilterForm(JalaliDateMixin, forms.Form):
    q = forms.CharField(label="جست‌وجو", required=False)
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *m.PurchaseOrderStatus.choices],
    )
    project = forms.ModelChoiceField(label="پروژه", queryset=None, required=False)
    supplier = forms.ModelChoiceField(label="تأمین‌کننده", queryset=None, required=False)
    lineage = forms.ChoiceField(
        label="مسیر ایجاد",
        required=False,
        choices=[
            ("", "همه مسیرها"),
            ("sourced", "از انتخاب تأمین‌کننده"),
            ("direct", "ثبت مستقیم / سابقه"),
        ],
    )
    date_from = forms.DateField(label="سفارش از تاریخ", required=False)
    date_to = forms.DateField(label="سفارش تا تاریخ", required=False)

    def __init__(self, *args, projects, suppliers, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project"].queryset = projects
        self.fields["supplier"].queryset = suppliers
        for name in ("project", "supplier"):
            choice_ui(self, name, "filter")
        self.fields["q"].widget.attrs["placeholder"] = (
            "شماره سفارش، تأمین‌کننده، پروژه یا استعلام…"
        )


class ReceiptContextForm(GoodsReceiptForm):
    """Only pins the existing GRN parent; receiving semantics remain unchanged."""

    def __init__(self, *args, source_order=None, **kwargs):
        super().__init__(*args, **kwargs)
        if source_order:
            inherit_business_parent(
                self,
                "purchase_order",
                source_order,
                detail_route="procurement:order_detail",
            )
