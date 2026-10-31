"""Contract List presentation filters; existing read services own access."""

from django import forms
from django.urls import reverse

from apps.contracts.models import ContractDirection, ContractStatus
from apps.projects.models import Project
from core.business_choices import SearchChoiceSelect, business_label


class ContractListFilterForm(forms.Form):
    q = forms.CharField(label="جست‌وجوی قرارداد", required=False, max_length=200)
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *ContractStatus.choices],
    )
    side = forms.ChoiceField(
        label="سمت قرارداد",
        required=False,
        choices=[
            ("", "همه سمت‌ها"),
            (ContractDirection.RECEIVABLE, "با کارفرما"),
            (ContractDirection.PAYABLE, "با پیمانکار / تأمین‌کننده"),
        ],
    )
    project = forms.ModelChoiceField(
        label="پروژه",
        queryset=Project.objects.none(),
        required=False,
        empty_label="همه پروژه‌ها",
    )
    number = forms.CharField(label="شماره قرارداد", required=False, max_length=200)
    title = forms.CharField(
        label="عنوان قرارداد یا پروژه", required=False, max_length=200
    )
    counterparty = forms.CharField(label="طرف قرارداد", required=False, max_length=200)

    def __init__(self, *args, contracts, project_scoped=False, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "erp-input w-full"
            field.error_messages["invalid_choice"] = (
                "گزینه معتبر و مجاز را انتخاب کنید."
            )
            field.error_messages["max_length"] = "عبارت جست‌وجو بیش از حد طولانی است."
        self.fields["q"].widget = forms.TextInput(
            attrs={
                "type": "search",
                "class": "erp-input w-full",
                "placeholder": "شماره، عنوان، پروژه یا طرف قرارداد…",
            }
        )
        if project_scoped:
            self.fields.pop("project")
            return
        field = self.fields["project"]
        # Project names already visible through the existing scoped Contract read.
        field.queryset = Project.objects.filter(
            pk__in=contracts.values("project_id")
        ).order_by("name", "pk")
        field.label_from_instance = business_label
        records = list(field.queryset[:40])
        selected = self.data.get("project")
        try:
            chosen = field.queryset.filter(pk=selected).first() if selected else None
        except (ValueError, forms.ValidationError):
            chosen = None
        if chosen and all(row.pk != chosen.pk for row in records):
            records.insert(0, chosen)
        field.widget = SearchChoiceSelect(
            attrs={
                "data-business-choice": "project",
                "data-business-names-primary": "true",
                "data-options-url": reverse("contracts:list")
                + "?filter_options=project",
                "data-placeholder": "جست‌وجو یا انتخاب پروژه…",
                "dir": "rtl",
            },
            choices=[("", "همه پروژه‌ها")]
            + [(str(row.pk), business_label(row)) for row in records],
        )
