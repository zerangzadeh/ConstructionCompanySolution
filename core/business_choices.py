"""Reuse the qualified searchable selector with each consuming form's querysets."""

from typing import ClassVar
from urllib.parse import urlencode

from django import forms
from django.urls import reverse


class SearchChoiceSelect(forms.Select):
    """Shared widget, retaining the qualified MVP-02 assets and template paths."""

    template_name = "workforce/widgets/search_choice.html"

    class Media:
        css: ClassVar = {
            "all": (
                "workforce/vendor/tom-select-2.6.2/tom-select.default.min.css",
                "workforce/field_choices.css",
            )
        }
        js = (
            "workforce/vendor/tom-select-2.6.2/tom-select.base.min.js",
            "workforce/vendor/tom-select-2.6.2/virtual_scroll.js",
            "workforce/field_choices.js",
        )


def business_label(record) -> str:
    name = (
        getattr(record, "display_name", None)
        or getattr(record, "name", None)
        or getattr(record, "title", None)
        or getattr(record, "description", None)
    )
    if hasattr(record, "effective_date") and hasattr(record, "version"):
        return f"{record.contract.title} · مبنای نسخه {record.version}"
    if hasattr(record, "site_id") and record.site_id:
        return f"{name} · {record.site.name}"
    code = getattr(record, "contract_number", None) or getattr(record, "code", None)
    return f"{name} · {code}" if code else str(name or record)


def configure_business_choice(form, name, purpose, *, parent=None):
    field = form.fields[name]
    field.label_from_instance = business_label
    field.empty_label = f"انتخاب {field.label}"
    records = list(field.queryset[:40])
    selected = (
        form.data.get(form.add_prefix(name))
        if form.is_bound
        else form.initial.get(name)
    )
    try:
        chosen = (
            field.queryset.filter(pk=getattr(selected, "pk", selected)).first()
            if selected
            else None
        )
    except (ValueError, forms.ValidationError):
        chosen = None
    if chosen and all(record.pk != chosen.pk for record in records):
        records.insert(0, chosen)
    field.widget = SearchChoiceSelect(
        attrs={
            "data-options-url": reverse(
                "billing:journey_choices", args=[purpose, name]
            ),
            "data-business-choice": name,
            "data-business-names-primary": "true",
            "data-placeholder": f"جست‌وجو یا انتخاب {field.label}…",
            "data-choice-parents": "project contract",
            **(
                {"data-depends-on": parent, "data-requires-parent": "true"}
                if parent
                else {}
            ),
            "dir": "rtl",
        },
        choices=[("", field.empty_label)]
        + [(str(record.pk), business_label(record)) for record in records],
    )


def contextual_url(route, **context):
    values = {
        key: str(getattr(value, "pk", value)) for key, value in context.items() if value
    }
    return reverse(route) + (f"?{urlencode(values)}" if values else "")
