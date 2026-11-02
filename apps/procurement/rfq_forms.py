"""Presentation-only inputs for the existing governed buyer RFQ services."""

from typing import ClassVar
from uuid import uuid4

from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.parties.models import BusinessParty, PartyRoleType
from apps.procurement.models import (
    PurchaseRequest,
    PurchaseRequestItem,
    RequestForQuotationStatus,
)
from core.business_choices import configure_business_choice, inherit_business_parent
from core.forms import JalaliDateMixin


class BusinessChoiceField(forms.ModelChoiceField):
    default_error_messages: ClassVar = {
        "invalid_choice": "انتخاب معتبر نیست؛ از گزینه‌های مجاز همین فرم انتخاب کنید."
    }

    def to_python(self, value):
        try:
            return super().to_python(value)
        except ValidationError as exc:
            raise ValidationError(
                self.error_messages["invalid_choice"], code="invalid_choice"
            ) from exc


class SupplierChoiceField(forms.ModelMultipleChoiceField):
    def _check_values(self, value):
        try:
            return super()._check_values(value)
        except ValidationError as exc:
            raise ValidationError(
                "یکی از تأمین‌کنندگان انتخاب‌شده مجاز یا فعال نیست؛ دوباره انتخاب کنید.",
                code="invalid_choice",
            ) from exc


def pr_label(row):
    return f"{row.request_number} · {row.title} · {row.project.name}"


def line_label(line):
    return f"{line.material.name} · {line.quantity} {line.unit_of_measure.name}"


def rfq_choice(form, name, *, url, label):
    configure_business_choice(form, name, "contract")
    field = form.fields[name]
    field.label_from_instance = label
    field.widget.attrs["data-options-url"] = url
    ids = [value for value, _ in field.widget.choices if value]
    field.widget.choices = [("", field.empty_label)] + [
        (str(row.pk), label(row)) for row in field.queryset.filter(pk__in=ids)
    ]


class RFQCreateForm(JalaliDateMixin, forms.Form):
    purchase_request_id = BusinessChoiceField(
        label="درخواست خرید تأییدشده",
        queryset=PurchaseRequest.objects.none(),
        empty_label="درخواست خرید را انتخاب کنید",
    )
    rfq_number = forms.CharField(label="شماره استعلام", max_length=80)
    title = forms.CharField(label="عنوان", max_length=255)
    closing_at = forms.DateTimeField(label="مهلت دریافت")
    earliest_opening_at = forms.DateTimeField(label="زودترین زمان گشایش")
    terms = forms.CharField(label="شرایط", required=False, widget=forms.Textarea)

    def __init__(self, *args, requests=None, source=None, **kwargs):
        super().__init__(*args, **kwargs)
        if requests is not None:
            self.fields["purchase_request_id"].queryset = requests
        self.fields["purchase_request_id"].label_from_instance = pr_label
        if source:
            inherit_business_parent(
                self,
                "purchase_request_id",
                source,
                detail_route="procurement:request_detail",
            )
        else:
            rfq_choice(
                self,
                "purchase_request_id",
                url=reverse("procurement:rfq_choices", args=["purchase_request_id"]),
                label=pr_label,
            )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "erp-input w-full")
        self.fields["terms"].widget.attrs["rows"] = 3

    def clean(self):
        data = super().clean()
        if (
            data.get("closing_at")
            and data.get("earliest_opening_at")
            and data["earliest_opening_at"] < data["closing_at"]
        ):
            self.add_error(
                "earliest_opening_at", "زمان گشایش نمی‌تواند پیش از مهلت دریافت باشد."
            )
        return data


class RFQLineForm(forms.Form):
    purchase_request_item_id = BusinessChoiceField(
        label="قلم درخواست خرید", queryset=PurchaseRequestItem.objects.none()
    )
    quantity = forms.DecimalField(
        label="مقدار", max_digits=18, decimal_places=4, min_value=0
    )
    description = forms.CharField(label="شرح", required=False)

    def __init__(self, *args, rfq=None, **kwargs):
        super().__init__(*args, **kwargs)
        if rfq:
            self.fields["purchase_request_item_id"].queryset = (
                rfq.purchase_request.items.filter(
                    organization=rfq.organization,
                    quantity__gt=0,
                )
                .exclude(rfq_lines__rfq=rfq)
                .select_related("material", "unit_of_measure")
            )
            rfq_choice(
                self,
                "purchase_request_item_id",
                url=reverse(
                    "procurement:rfq_choices", args=["purchase_request_item_id"]
                )
                + f"?rfq={rfq.pk}",
                label=line_label,
            )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "erp-input w-full")
        self.fields[
            "quantity"
        ].help_text = (
            "مقدار مثبت، حداکثر به اندازه قلم درخواست خرید؛ واحد از همان قلم حفظ می‌شود."
        )


class RFQIssueForm(forms.Form):
    supplier_ids = SupplierChoiceField(
        label="تأمین‌کنندگان دعوت‌شونده",
        queryset=BusinessParty.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "invalid_choice": "یکی از تأمین‌کنندگان انتخاب‌شده مجاز یا فعال نیست؛ دوباره انتخاب کنید.",
            "invalid_pk_value": "انتخاب تأمین‌کننده معتبر نیست؛ از گزینه‌های همین فرم انتخاب کنید.",
            "invalid_list": "تأمین‌کنندگان را از گزینه‌های همین فرم انتخاب کنید.",
        },
    )
    idempotency_key = forms.CharField(
        widget=forms.HiddenInput(), max_length=128, initial=lambda: uuid4().hex
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier_ids"].queryset = (
            BusinessParty.objects.filter(
                organization=organization,
                archived_at__isnull=True,
                roles__role=PartyRoleType.SUPPLIER,
                roles__is_active=True,
                roles__organization=organization,
            )
            .distinct()
            .order_by("display_name")
        )
        self.fields["supplier_ids"].label_from_instance = lambda party: (
            party.display_name
        )


class RFQCloseForm(forms.Form):
    idempotency_key = forms.CharField(
        widget=forms.HiddenInput(), max_length=128, initial=lambda: uuid4().hex
    )


class RFQCancelForm(forms.Form):
    reason = forms.CharField(label="دلیل لغو", widget=forms.Textarea)


class RFQFilterForm(JalaliDateMixin, forms.Form):
    q = forms.CharField(label="جست‌وجو", required=False)
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *RequestForQuotationStatus.choices],
    )
    project = BusinessChoiceField(label="پروژه", queryset=None, required=False)
    closing_from = forms.DateField(label="مهلت دریافت از", required=False)
    closing_to = forms.DateField(label="مهلت دریافت تا", required=False)

    def __init__(self, *args, projects, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs["placeholder"] = (
            "شماره، عنوان، درخواست خرید یا پروژه…"
        )
        self.fields["project"].queryset = projects
        rfq_choice(
            self,
            "project",
            url=reverse("procurement:rfq_choices", args=["project"]),
            label=lambda row: f"{row.name} · {row.code}",
        )
