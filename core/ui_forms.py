"""Presentation adapters; canonical service payloads remain unchanged."""

from uuid import uuid4

from django import forms
from django.template.loader import render_to_string


class SharedTemplateWidget:
    def _render(self, template_name, context, renderer=None):
        return render_to_string(template_name, context)


class StructuredDataWidget(SharedTemplateWidget, forms.Textarea):
    template_name = "components/widgets/structured_data.html"

    def __init__(self, attrs=None, *, empty_value="{}"):
        super().__init__(
            {
                **(attrs or {}),
                "data-structured-data": "",
                "data-empty-value": empty_value,
            }
        )

    class Media:
        js = ("js/structured-data.js",)


class OccurrenceKeyWidget(SharedTemplateWidget, forms.TextInput):
    """Keep the normal key hidden, with explicit supplied-source compatibility."""

    template_name = "components/widgets/occurrence_key.html"

    def __init__(self, attrs=None, *, help_text=None):
        super().__init__(attrs)
        self.help_text = (
            help_text
            or "برای ثبت دستی، مرجع داخلی خودکار است. ارسال دوباره همین فرم همان مرجع را نگه می‌دارد؛ بازکردن فرم جدید، رخداد جدید است. برای حفظ مرجع یک منبع بیرونی یا قبلی، آن را در بالا وارد کنید."
        )

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["occurrence_help"] = self.help_text
        return context

    def value_from_datadict(self, data, files, name):
        supplied = data.get(f"{name}_existing", "").strip()
        return supplied or super().value_from_datadict(data, files, name)


def initialize_occurrence_key(form, name, *, generate=True, help_text=None):
    form.fields[name].widget = OccurrenceKeyWidget(help_text=help_text)
    form.fields[name].label = "مرجع ثبت (خودکار)"
    if generate and not form.is_bound:
        form.initial.setdefault(name, str(uuid4()))


def initialize_retry_key(form, name="idempotency_key"):
    form.fields[name].widget = forms.HiddenInput()
    if not form.is_bound:
        form.initial.setdefault(name, str(uuid4()))
