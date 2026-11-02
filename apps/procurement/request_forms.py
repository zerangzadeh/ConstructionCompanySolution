"""Presentation inputs for MVP-04A; existing services own all mutations."""

from django import forms
from django.urls import reverse

from apps.materials.models import Material
from core.business_choices import configure_business_choice, inherit_business_parent
from core.forms import JalaliDateMixin

from .forms import PurchaseRequestForm, RequestItemForm
from .models import PurchaseRequestStatus


def request_choice(form, name):
    configure_business_choice(form, name, "contract")
    form.fields[name].widget.attrs["data-options-url"] = reverse(
        "procurement:request_choices", args=[name]
    )


class RequestCreateForm(PurchaseRequestForm):
    def __init__(self, *args, context_project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if context_project:
            inherit_business_parent(
                self, "project", context_project, detail_route="projects:detail"
            )
        else:
            request_choice(self, "project")
        self.fields["request_number"].widget.attrs.update(
            {"dir": "ltr", "placeholder": "PR-1405-001"}
        )
        self.fields["title"].widget.attrs["placeholder"] = "مثال: مصالح اجرای فونداسیون"


class RequestLineForm(RequestItemForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request_choice(self, "material")
        self.fields["material"].label_from_instance = material_label
        # Keep the shared selector's selected value and bounded first page.
        ids = [value for value, _ in self.fields["material"].widget.choices if value]
        self.fields["material"].widget.choices = [("", "انتخاب مصالح")] + [
            (str(row.pk), material_label(row))
            for row in self.fields["material"].queryset.filter(pk__in=ids)
        ]
        self.fields["quantity"].help_text = "واحد مقدار از مصالح انتخاب‌شده تعیین می‌شود."


def material_label(row: Material) -> str:
    return f"{row.name} · {row.code} · {row.unit_of_measure.name}"


class RequestFilterForm(JalaliDateMixin, forms.Form):
    q = forms.CharField(label="جست‌وجو", required=False)
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=[("", "همه وضعیت‌ها"), *PurchaseRequestStatus.choices],
    )
    project = forms.ModelChoiceField(label="پروژه", queryset=None, required=False)
    required_by_from = forms.DateField(label="نیاز از تاریخ", required=False)
    required_by_to = forms.DateField(label="نیاز تا تاریخ", required=False)

    def __init__(self, *args, projects, project_scoped=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs["placeholder"] = "شماره، عنوان درخواست یا پروژه…"
        self.fields["project"].queryset = projects
        if project_scoped:
            self.fields.pop("project")
        else:
            request_choice(self, "project")
