from django import template

from core.list_filters import has_active_table_filters

register = template.Library()


@register.inclusion_tag("components/table_filter_row.html")
def table_filter_row(filters, form_id):
    return {"filters": filters, "form_id": form_id}


@register.inclusion_tag("components/table_filters.html", takes_context=True)
def table_filters(context, filters, form_id):
    rendered_key = "accounts.table_filters.rendered"
    if context.render_context.get(rendered_key):
        return {"filters": []}
    context.render_context[rendered_key] = True
    request = context.get("request")
    filter_names = {
        name
        for item in filters
        if item
        for name in (
            (f"{item['name']}_from", f"{item['name']}_to")
            if item["kind"] == "date_range"
            else (item["name"],)
        )
    }
    return {
        "filters": filters,
        "form_id": form_id,
        "has_active_filters": (
            has_active_table_filters(request, filter_names)
            or context.get("has_active_filters", False)
        )
        if request
        else context.get("has_active_filters", False),
        "request": request,
    }


@register.inclusion_tag("components/table_sort_header.html", takes_context=True)
def table_sort_header(context, sort_key, label):
    request = context.get("request")
    if request is None:
        return {
            "label": label,
            "url": "#",
            "indicator": "↕",
            "state": "none",
            "aria_sort": "none",
        }

    query = request.GET.copy()
    query.pop("page", None)
    for key, values in list(query.lists()):
        if any(value.strip() for value in values):
            query.setlist(key, [value for value in values if value.strip()])
        else:
            query.pop(key, None)
    current_key = query.get("sort", "")
    current_direction = query.get("direction", "asc").lower()
    is_current = current_key == sort_key
    state = (
        current_direction
        if is_current and current_direction in {"asc", "desc"}
        else "none"
    )
    next_direction = "desc" if state == "asc" else "asc"
    query["sort"] = sort_key
    query["direction"] = next_direction
    query_string = query.urlencode()
    return {
        "label": label,
        "url": f"{request.path}?{query_string}" if query_string else request.path,
        "indicator": "↑" if state == "asc" else "↓" if state == "desc" else "↕",
        "state": state,
        "aria_sort": "ascending"
        if state == "asc"
        else "descending"
        if state == "desc"
        else "none",
    }
