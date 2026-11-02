"""Template adapters for the single product surface authority."""

from django import template
from django.urls import reverse

from core.product_surface import route_exposed, url_exposed

register = template.Library()
register.filter("surface_exposed", route_exposed)
register.filter("surface_url_exposed", url_exposed)


@register.simple_tag
def breadcrumb_trail(current_label, *parents):
    """Assemble presentation labels and source-validated URLs for the shared renderer."""
    if len(parents) % 2:
        raise template.TemplateSyntaxError(
            "Breadcrumb parents require label/URL pairs."
        )
    return [
        {"label": "خانه", "url": reverse("home")},
        *(
            {"label": parents[i], "url": parents[i + 1]}
            for i in range(0, len(parents), 2)
        ),
        {"label": current_label},
    ]


@register.filter
def surface_link_active(link, view_name):
    return link.is_active_for(view_name)


@register.simple_tag
def module_selector_links(groups, view_name, current_path):
    """Present only already-authorized shell destinations; grant nothing.

    Canonical active-route aliases win. For descendants without an alias,
    highlight the longest existing destination path. No new destination,
    namespace map, permission or exposure policy is created.
    """
    items = [
        {"link": link, "url": reverse(link.route), "active": False}
        for group in groups
        for link in group.links
    ]
    active = next(
        (item for item in items if item["link"].is_active_for(view_name)), None
    )
    if active is None:
        candidates = [
            item
            for item in items
            if current_path == item["url"]
            or current_path.startswith(item["url"].rstrip("/") + "/")
        ]
        active = max(candidates, key=lambda item: len(item["url"]), default=None)
    if active is not None:
        active["active"] = True
    return items
