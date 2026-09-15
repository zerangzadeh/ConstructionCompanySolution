from django import template

register = template.Library()


@register.inclusion_tag("components/table_filter_row.html")
def table_filter_row(filters, form_id):
    return {"filters": filters, "form_id": form_id}


@register.inclusion_tag("components/table_filters.html", takes_context=True)
def table_filters(context, filters, form_id):
    rendered_key = "core.table_filters.rendered"
    if context.render_context.get(rendered_key):
        return {"filters": []}
    context.render_context[rendered_key] = True
    return {
        "filters": filters,
        "form_id": form_id,
        "has_active_filters": context.get("has_active_filters", False),
        "request": context.get("request"),
    }
