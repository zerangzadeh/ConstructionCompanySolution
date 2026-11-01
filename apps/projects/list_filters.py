"""Presentation filters over the existing authorized Project read service."""

from django import forms

from apps.projects.models import ProjectStatus
from core.forms import JalaliDateMixin


class ProjectListFilterForm(JalaliDateMixin, forms.Form):
    q = forms.CharField(label="جست‌وجوی پروژه", required=False, max_length=200)
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *ProjectStatus.choices],
    )
    code = forms.CharField(label="کد پروژه", required=False, max_length=200)
    name = forms.CharField(label="نام پروژه", required=False, max_length=200)
    start_date_from = forms.DateField(label="شروع از تاریخ", required=False)
    start_date_to = forms.DateField(label="شروع تا تاریخ", required=False)
    end_date_from = forms.DateField(label="پایان از تاریخ", required=False)
    end_date_to = forms.DateField(label="پایان تا تاریخ", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "erp-input w-full"
            field.error_messages.update(
                invalid="مقدار معتبر وارد کنید.",
                invalid_choice="وضعیت معتبر انتخاب کنید.",
                max_length="عبارت جست‌وجو بیش از حد طولانی است.",
            )
        self.fields["q"].widget = forms.TextInput(
            attrs={
                "type": "search",
                "placeholder": "کد یا نام پروژه…",
                "class": "erp-input w-full",
            }
        )
