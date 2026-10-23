from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from django import forms

from core.jalali import format_jalali, gregorian_to_jalali, jalali_to_gregorian

JALALI_INPUT_MASK = "####/##/##"
_DATE_RE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})$")
_DATETIME_RE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})\s+(\d{1,2}):(\d{2})$")
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class ParentChoiceSelect(forms.Select):
    """Expose parent metadata for presentation of already authorized choices."""

    def __init__(self, *, parent_attribute: str, **kwargs: Any) -> None:
        self.parent_attribute = parent_attribute
        super().__init__(**kwargs)

    def create_option(
        self,
        name: str,
        value: Any,
        label: Any,
        selected: bool,
        index: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        option = super().create_option(name, value, label, selected, index, **kwargs)
        if value and hasattr(value, "instance"):
            option["attrs"]["data-parent-value"] = str(
                getattr(value.instance, self.parent_attribute)
            )
        return option


def attach_parent_choice_ui(
    form: forms.BaseForm, child: str, parent: str, parent_attribute: str
) -> None:
    """Filter rendered choices in the browser without changing field validation."""
    field = form.fields[child]
    field.widget = ParentChoiceSelect(
        parent_attribute=parent_attribute,
        attrs={**field.widget.attrs, "data-local-parent": form[parent].id_for_label},
        choices=field.choices,
    )


def normalize_jalali_digits(value: str) -> str:
    return value.translate(_PERSIAN_DIGITS)


def parse_jalali_date(value: Any) -> date:
    text = normalize_jalali_digits(str(value or "")).strip()
    match = _DATE_RE.fullmatch(text)
    if not match:
        raise ValueError("invalid Jalali date format")
    year, month, day = (int(part) for part in match.groups())
    converted = jalali_to_gregorian(year, month, day)
    if tuple(gregorian_to_jalali(*converted)) != (year, month, day):
        raise ValueError("invalid Jalali date")
    return date(*converted)


def parse_jalali_datetime(value: Any) -> datetime:
    text = normalize_jalali_digits(str(value or "")).strip().replace("T", " ")
    match = _DATETIME_RE.fullmatch(text)
    if not match:
        raise ValueError("invalid Jalali datetime format")
    year, month, day, hour, minute = (int(part) for part in match.groups())
    if hour > 23 or minute > 59:
        raise ValueError("invalid time")
    return datetime.combine(
        parse_jalali_date(f"{year:04d}/{month:02d}/{day:02d}"), datetime.min.time()
    ).replace(hour=hour, minute=minute)


class JalaliDateInput(forms.DateInput):
    input_type = "text"

    def __init__(self, attrs: dict[str, Any] | None = None, **kwargs: Any) -> None:
        merged = {
            "data-jalali-date": "date",
            "data-input-mask": JALALI_INPUT_MASK,
            "inputmode": "numeric",
            "autocomplete": "off",
        }
        merged.update(attrs or {})
        merged.pop("type", None)
        super().__init__(attrs=merged, format="%Y/%m/%d", **kwargs)

    def format_value(self, value: Any) -> str:
        if isinstance(value, (date, datetime)):
            return format_jalali(value)
        text = str(value or "")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            try:
                year, month, day = (int(part) for part in text.split("-"))
                return format_jalali(date(year, month, day))
            except ValueError:
                pass
        return text


class JalaliDateTimeInput(forms.DateTimeInput):
    input_type = "text"

    def __init__(self, attrs: dict[str, Any] | None = None, **kwargs: Any) -> None:
        merged = {
            "data-jalali-date": "datetime",
            "data-input-mask": JALALI_INPUT_MASK,
            "inputmode": "numeric",
            "autocomplete": "off",
        }
        merged.update(attrs or {})
        merged.pop("type", None)
        super().__init__(attrs=merged, format="%Y/%m/%d %H:%M", **kwargs)

    def format_value(self, value: Any) -> str:
        if isinstance(value, datetime):
            return format_jalali(value, include_time=True)
        return str(value or "")


class JalaliDateMixin:
    """Give every date field in a form a Jalali widget and server-side parser."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field, forms.DateTimeField):
                field.widget = JalaliDateTimeInput(attrs=dict(field.widget.attrs))
            elif isinstance(field, forms.DateField):
                field.widget = JalaliDateInput(attrs=dict(field.widget.attrs))

        if self.is_bound:
            data = self.data.copy()
            for name, field in self.fields.items():
                raw = data.get(self.add_prefix(name))
                if not raw:
                    continue
                try:
                    if isinstance(field, forms.DateTimeField):
                        try:
                            parsed = parse_jalali_datetime(raw)
                            data[self.add_prefix(name)] = parsed.strftime(
                                "%Y-%m-%d %H:%M"
                            )
                        except ValueError:
                            # Allow the browser's normalized ISO value after the JS submit hook.
                            data[self.add_prefix(name)] = str(raw).replace("T", " ")
                    elif isinstance(field, forms.DateField):
                        try:
                            data[self.add_prefix(name)] = parse_jalali_date(
                                raw
                            ).isoformat()
                        except ValueError:
                            # Preserve a Gregorian ISO value if a non-JavaScript client submits it.
                            data[self.add_prefix(name)] = raw
                except ValueError:
                    # Keep invalid input intact so Django exposes a normal field error.
                    continue
            self.data = data
