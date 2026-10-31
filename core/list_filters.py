"""Small, tenant-safe helpers for server-rendered table filters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from django.core.paginator import Page, Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.utils.dateparse import parse_date

from core.jalali import jalali_to_gregorian


def contextual_list_filters(
    request: HttpRequest, *, keys: Sequence[str] = ("project_id", "contract")
) -> dict[str, Any]:
    """Keep applied business context when clearing temporary query controls.

    Callers still authorize and apply their existing context filters. These
    values are URL state only and grant no access or global session context.
    """
    context = {key: request.GET[key] for key in keys if request.GET.get(key)}
    query = request.GET.copy()
    for key in list(query):
        if key not in context:
            query.pop(key)
    encoded = query.urlencode()
    return {
        "filter_context": context,
        "clear_filters_url": f"{request.path}?{encoded}" if encoded else request.path,
        "has_context": bool(context),
        "has_temporary_filters": any(
            value.strip()
            for key, values in request.GET.lists()
            if key not in context
            for value in values
        ),
    }


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


def apply_table_sorting(
    queryset: QuerySet,
    request: HttpRequest,
    *,
    sort_fields: Mapping[str, str | Sequence[str]],
    default_ordering: Sequence[str] = (),
) -> QuerySet:
    """Apply a whitelisted sort from GET without exposing ORM field names."""

    sort_key = request.GET.get("sort", "").strip()
    ordering = sort_fields.get(sort_key)
    if ordering is None:
        if not default_ordering:
            return queryset
        return queryset.order_by(*default_ordering)
    if isinstance(ordering, str):
        ordering = (ordering,)
    if not ordering:
        return queryset

    descending = request.GET.get("direction", "asc").strip().lower() == "desc"
    prefix = "-" if descending else ""
    return queryset.order_by(*(f"{prefix}{field.lstrip('-')}" for field in ordering))


def paginate_table(
    queryset: QuerySet,
    request: HttpRequest,
    *,
    sort_fields: Mapping[str, str | Sequence[str]],
    default_ordering: Sequence[str] = (),
    per_page: int = 25,
) -> Page:
    """Sort and paginate a table queryset using the shared list contract."""

    sorted_queryset = apply_table_sorting(
        queryset,
        request,
        sort_fields=sort_fields,
        default_ordering=default_ordering,
    )
    page = Paginator(sorted_queryset, per_page).get_page(request.GET.get("page"))
    page.object_list = list(page.object_list)
    return page


def table_pagination_query(request: HttpRequest) -> str:
    """Return the current non-page query, excluding empty parameters."""

    query = request.GET.copy()
    query.pop("page", None)
    for key, values in list(query.lists()):
        non_empty = [value for value in values if value.strip()]
        if non_empty:
            query.setlist(key, non_empty)
        else:
            query.pop(key, None)
    return query.urlencode()


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


def has_active_table_filters(
    request: HttpRequest, filter_names: Iterable[str] | None = None
) -> bool:
    """Return whether one or more actual filter values are active."""

    names = set(filter_names or ())
    if names:
        return any(request.GET.get(name, "").strip() for name in names)
    ignored = {"page", "sort", "direction"}
    return any(
        value.strip()
        for key, values in request.GET.lists()
        if key not in ignored
        for value in values
    )


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
        try:
            return parse_date(normalized.replace("/", "-"))
        except ValueError:
            return None
