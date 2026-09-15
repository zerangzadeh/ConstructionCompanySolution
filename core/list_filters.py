"""Small, tenant-safe helpers for server-rendered table filters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.utils.dateparse import parse_date

from core.jalali import jalali_to_gregorian


def apply_table_filters(
    queryset: QuerySet,
    request: HttpRequest,
    *,
    text_fields: Mapping[str, Sequence[str]] | None = None,
    choice_fields: Mapping[str, tuple[str, Iterable[str]]] | None = None,
    date_fields: Mapping[str, str] | None = None,
) -> QuerySet:
    """Apply validated GET filters to an already tenant-scoped queryset.

    ``text_fields`` maps a query parameter to one or more ``icontains`` lookups.
    ``choice_fields`` maps a parameter to a model field and its allowed values.
    ``date_fields`` maps a date prefix to a date or datetime field lookup; it
    accepts both ISO/Gregorian and Jalali values from the shared date picker.
    """

    for parameter, lookups in (text_fields or {}).items():
        value = request.GET.get(parameter, "").strip()
        if not value:
            continue
        query = Q()
        for lookup in lookups:
            query |= Q(**{f"{lookup}__icontains": value})
        queryset = queryset.filter(query)

    for parameter, (field_name, allowed_values) in (choice_fields or {}).items():
        value = request.GET.get(parameter, "").strip()
        if value and value in set(allowed_values):
            queryset = queryset.filter(**{field_name: value})

    for prefix, field_name in (date_fields or {}).items():
        start = parse_user_date(request.GET.get(f"{prefix}_from", ""))
        end = parse_user_date(request.GET.get(f"{prefix}_to", ""))
        if start:
            queryset = queryset.filter(**{f"{field_name}__gte": start})
        if end:
            queryset = queryset.filter(**{f"{field_name}__lte": end})

    return queryset


def build_table_filters(
    request: HttpRequest, columns: Sequence[dict[str, Any] | None]
) -> list[dict[str, Any] | None]:
    """Bind compact table-filter column definitions to the current GET values."""

    bound_columns: list[dict[str, Any] | None] = []
    for column in columns:
        if column is None:
            bound_columns.append(None)
            continue
        bound = dict(column)
        if bound["kind"] == "date_range":
            prefix = bound["name"]
            bound["from_value"] = request.GET.get(f"{prefix}_from", "")
            bound["to_value"] = request.GET.get(f"{prefix}_to", "")
        else:
            bound["value"] = request.GET.get(bound["name"], "")
        bound_columns.append(bound)
    return bound_columns


def has_active_table_filters(request: HttpRequest) -> bool:
    return bool(request.GET)


def parse_user_date(value: str) -> date | None:
    """Parse ISO dates and Persian-facing Jalali dates without raising for GETs."""

    normalized = value.strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    if not normalized:
        return None
    try:
        year, month, day = (
            int(part) for part in normalized.replace("/", "-").split("-")
        )
        if year < 1700:
            year, month, day = jalali_to_gregorian(year, month, day)
        return date(year, month, day)
    except (TypeError, ValueError):
        return parse_date(normalized.replace("/", "-"))
