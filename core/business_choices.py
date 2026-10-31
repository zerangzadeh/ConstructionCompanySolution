"""Reuse the qualified searchable selector with each consuming form's querysets."""

from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import urlencode
from uuid import UUID

from django import forms
from django.db.models import Model, QuerySet
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse


def contextual_parent(
    request: HttpRequest, name: str, records: QuerySet
) -> Model | None:
    """Reload a reference from an already tenant/permission-scoped source.

    An absent reference means general Create. Empty, ambiguous or inaccessible
    references never fall back to another parent or global application context.
    """
    if name not in request.GET:
        return None
    values = request.GET.getlist(name)
    try:
        if len(values) != 1:
            raise ValueError
        identifier = UUID(values[0])
    except (ValueError, TypeError, AttributeError) as exc:
        raise Http404 from exc
    return get_object_or_404(records, pk=identifier)


@dataclass(frozen=True)
class InheritedParent:
    label: str
    title: str
    code: str
    url: str
    project_name: str = ""


class InheritedParentInput(forms.HiddenInput):
    """Re-render the trusted reference while validation uses the actual POST."""

    def __init__(self, parent_value, **kwargs):
        self.parent_value = str(parent_value)
        super().__init__(**kwargs)

    def format_value(self, value):
        return self.parent_value


def inherit_business_parent(
    form: forms.BaseForm, name: str, parent: Model, *, detail_route: str
) -> None:
    """Present a server-resolved parent without making it a new authority.

    Keep a required, restricted ModelChoiceField so forged or missing POST values
    are rejected instead of silently ignored as with a disabled form field.
    """
    field = form.fields[name]
    field.queryset = field.queryset.filter(pk=parent.pk)
    field.required = True
    field.error_messages["invalid_choice"] = (
        f"{field.label} ارسال‌شده با زمینه این فرم هم‌خوان نیست."
    )
    field.widget = InheritedParentInput(
        parent.pk, attrs={"data-inherited-parent": name}
    )
    form.initial[name] = parent.pk
    context = InheritedParent(
        label=field.label,
        title=getattr(parent, "name", "") or getattr(parent, "title", ""),
        code=getattr(parent, "contract_number", "") or getattr(parent, "code", ""),
        url=reverse(detail_route, args=[parent.pk]),
        project_name=parent.project.name if getattr(parent, "project_id", None) else "",
    )
    form.inherited_parents = (*getattr(form, "inherited_parents", ()), context)


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
