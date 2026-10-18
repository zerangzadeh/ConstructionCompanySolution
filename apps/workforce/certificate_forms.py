from django import forms


class CertificateRequestForm(forms.Form):
    type_id = forms.ChoiceField(label="نوع گواهی فعال")
    reason = forms.CharField(
        label="دلیل درخواست", max_length=2000, widget=forms.Textarea
    )
    replaces_id = forms.ChoiceField(
        label="جایگزین خروجی پیشین (اختیاری)", required=False
    )
    idempotency_key = forms.CharField(max_length=128, widget=forms.HiddenInput)
