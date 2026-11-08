from django import forms

from apps.audit.models import AuditAction
from core.forms import JalaliDateMixin


class AuditFilterForm(JalaliDateMixin, forms.Form):
    q = forms.CharField(
        label="جست‌وجو",
        required=False,
        max_length=150,
        widget=forms.SearchInput(attrs={"placeholder": "عنوان فعالیت یا نام کاربری"}),
    )
    actor = forms.CharField(
        label="کاربر",
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "نام کاربری دقیق", "dir": "auto"}),
    )
    action = forms.ChoiceField(
        label="نوع فعالیت",
        required=False,
        choices=[
            ("", "همه انواع"),
            *sorted(AuditAction.choices, key=lambda item: item[1]),
        ],
    )
    date_from = forms.DateField(label="از تاریخ", required=False)
    date_to = forms.DateField(label="تا تاریخ", required=False)

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("date_from"), cleaned.get("date_to")
        if start and end and start > end:
            self.add_error(
                "date_to", "تاریخ پایان باید برابر یا پس از تاریخ شروع باشد."
            )
        return cleaned
