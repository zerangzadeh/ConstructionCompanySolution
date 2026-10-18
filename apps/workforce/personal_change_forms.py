from django import forms


class ChangeForm(forms.Form):
    enrollment_id = forms.ChoiceField(label="فیلد ارتباطی مجاز")
    proposed_value = forms.CharField(
        label="مقدار پیشنهادی", max_length=1000, required=False, widget=forms.Textarea
    )
    reason = forms.CharField(
        label="دلیل درخواست", max_length=2000, widget=forms.Textarea
    )
    idempotency_key = forms.CharField(max_length=128, widget=forms.HiddenInput)


class DecisionForm(forms.Form):
    outcome = forms.ChoiceField(label="نتیجه تعریف‌شده گردش‌کار")
    reason = forms.CharField(
        label="دلیل قابل نمایش به درخواست‌کننده", max_length=2000, widget=forms.Textarea
    )
    idempotency_key = forms.CharField(max_length=128, widget=forms.HiddenInput)
