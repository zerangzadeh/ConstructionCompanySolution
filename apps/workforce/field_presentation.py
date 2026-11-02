"""Field UI composition only. Queries and domain services retain authority."""

import re
from copy import copy
from urllib.parse import parse_qsl, urlencode, urlsplit

from django import forms
from django.core.exceptions import ValidationError

from core.list_filters import build_filter_bar


def presentation_error(exc: Exception) -> str:
    """Keep Persian business explanations; never surface internal error payloads."""
    messages = exc.messages if isinstance(exc, ValidationError) else [str(exc)]
    safe = [message for message in messages if not re.search(r"[A-Za-z_{}]", message)]
    return (
        "؛ ".join(safe)
        if safe
        else "اطلاعات واردشده قابل ثبت نیست؛ مقادیر و وضعیت سابقه را بررسی کنید."
    )


def cascade_filter_chips(bar: dict) -> None:
    """Remove dependent page values with their parent, without session mutation."""
    for chip in bar["chips"]:
        descendants = {"project": {"site", "employee"}, "site": {"employee"}}.get(
            chip["name"], set()
        )
        if descendants:
            parts = urlsplit(chip["url"])
            query = urlencode(
                [
                    (key, value)
                    for key, value in parse_qsl(parts.query)
                    if key not in descendants
                ]
            )
            chip["url"] = parts.path + (f"?{query}" if query else "")


def list_presentation(request, form, page, *, kind: str) -> dict:
    specs = {
        "workers": (("project", "site", "status"), (), "نیرو"),
        "assignments": (
            ("project", "site", "status"),
            ("employee", "role", "start_date_from", "start_date_to"),
            "تخصیص",
        ),
        "teams": ((), ("department", "lead"), "گروه"),
    }
    quick, secondary, label = specs[kind]
    form.fields["q"].widget.attrs["placeholder"] = form.fields["q"].label
    form.is_valid()
    if not form.is_bound:
        form.cleaned_data = {}
    bar_request = copy(request)
    if form.is_bound:
        bar_request.GET = form.data.copy()
    bar = build_filter_bar(
        bar_request,
        form=form,
        quick_fields=quick,
        secondary_fields=secondary,
        context={"page_filters": "1"} if kind != "teams" else None,
        result_count=page.paginator.count,
        result_label=label,
    )
    # Clearing a parent filter clears its dependent page filters, never the
    # organization's working context or the authorized selector querysets.
    cascade_filter_chips(bar)
    sort_options = {
        "workers": {
            "name": "نام نیرو",
            "number": "شماره پرسنلی",
            "status": "وضعیت همکاری",
        },
        "assignments": {
            "employee": "نیروی کار",
            "project": "پروژه",
            "role": "مسئولیت",
            "start_date": "تاریخ شروع",
            "status": "وضعیت",
        },
        "teams": {"team": "نام گروه", "department": "واحد شرکتی", "lead": "سرپرست"},
    }[kind]
    default_sort = {"workers": "name", "assignments": "start_date", "teams": "team"}[
        kind
    ]
    requested_sort = request.GET.get("sort")
    valid_sort = requested_sort in sort_options
    return {
        "form": form,
        "filter_bar": bar,
        "result_label": label,
        "list_sort": {
            "label": sort_options[requested_sort if valid_sort else default_sort],
            "descending": request.GET.get("direction", "asc").lower() == "desc"
            if valid_sort
            else kind == "assignments",
        },
    }


class TeamFilterForm(forms.Form):
    q = forms.CharField(label="جست‌وجوی گروه کاری", required=False)
    department = forms.CharField(label="واحد شرکتی", required=False)
    lead = forms.CharField(label="سرپرست", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget = forms.TextInput(
                attrs={
                    "class": "w-full rounded-lg border border-slate-300 px-3 py-2",
                    "type": "search",
                }
            )
