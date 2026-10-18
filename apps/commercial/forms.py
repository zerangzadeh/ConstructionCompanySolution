from django import forms

from apps.commercial.models import TenderBidStatus


class TenderBidCreateForm(forms.Form):
    opportunity_code = forms.CharField(label="شناسه فرصت", max_length=80)
    title = forms.CharField(label="عنوان", max_length=255)
    description = forms.CharField(label="شرح", required=False, widget=forms.Textarea)


class TenderBidRevisionForm(forms.Form):
    title = forms.CharField(label="عنوان", max_length=255)
    description = forms.CharField(label="شرح", required=False, widget=forms.Textarea)
    submission_reference = forms.CharField(
        label="مرجع ارسال", max_length=160, required=False
    )
    result_reference = forms.CharField(
        label="مرجع نتیجه", max_length=160, required=False
    )
    bid_bond_reference = forms.CharField(
        label="مرجع ضمانت پیشنهاد", max_length=160, required=False
    )
    bid_cost_reference = forms.CharField(
        label="مرجع هزینه پیشنهاد", max_length=160, required=False
    )
    reason = forms.CharField(label="دلیل بازنگری", widget=forms.Textarea)


class TenderBidTransitionForm(forms.Form):
    target = forms.ChoiceField(label="وضعیت بعدی", choices=TenderBidStatus.choices)
    reason = forms.CharField(label="دلیل", widget=forms.Textarea)
    submission_reference = forms.CharField(
        label="مرجع ارسال", max_length=160, required=False
    )
    result_reference = forms.CharField(
        label="مرجع نتیجه", max_length=160, required=False
    )


class TenderBidEvidenceForm(forms.Form):
    document_version_id = forms.UUIDField(label="شناسه نسخه سند")
    description = forms.CharField(label="شرح شاهد", max_length=255, required=False)
