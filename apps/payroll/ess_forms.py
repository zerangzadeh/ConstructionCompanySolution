"""Input shapes; authoritative checks remain inside transactional services."""

from django import forms


class InquiryForm(forms.Form):
    payslip_id = forms.ChoiceField(label="فیش قطعی")
    category_id = forms.ChoiceField(label="دسته پرسش")
    subject = forms.CharField(label="عنوان", max_length=255)
    description = forms.CharField(label="شرح", max_length=4000, widget=forms.Textarea)
    document_version_ids = forms.MultipleChoiceField(
        label="نسخه شواهد مجاز (اختیاری)", required=False
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput, max_length=128)


class ResponseForm(forms.Form):
    outcome = forms.ChoiceField(label="نتیجه تعریف‌شده گردش‌کار")
    body = forms.CharField(
        label="پاسخ قابل نمایش به کارمند", max_length=4000, widget=forms.Textarea
    )
    idempotency_key = forms.CharField(widget=forms.HiddenInput, max_length=128)
