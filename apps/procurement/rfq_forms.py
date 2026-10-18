"""Presentation-only inputs for the existing governed buyer RFQ services."""

from django import forms

from core.forms import JalaliDateMixin


class RFQCreateForm(JalaliDateMixin, forms.Form):
    purchase_request_id = forms.UUIDField(label="درخواست خرید تأییدشده")
    rfq_number = forms.CharField(label="شماره استعلام", max_length=80)
    title = forms.CharField(label="عنوان", max_length=255)
    closing_at = forms.DateTimeField(label="مهلت دریافت")
    earliest_opening_at = forms.DateTimeField(label="زودترین زمان گشایش")
    terms = forms.CharField(label="شرایط", required=False, widget=forms.Textarea)


class RFQLineForm(forms.Form):
    purchase_request_item_id = forms.UUIDField(label="ردیف درخواست خرید")
    quantity = forms.DecimalField(
        label="مقدار", max_digits=18, decimal_places=4, min_value=0
    )
    description = forms.CharField(label="شرح", required=False)


class RFQIssueForm(forms.Form):
    supplier_ids = forms.CharField(label="شناسه تأمین‌کنندگان (با ویرگول جدا شود)")
    idempotency_key = forms.CharField(label="کلید یکتای صدور", max_length=128)


class RFQCloseForm(forms.Form):
    idempotency_key = forms.CharField(label="کلید یکتای بستن", max_length=128)


class RFQCancelForm(forms.Form):
    reason = forms.CharField(label="دلیل لغو", widget=forms.Textarea)
