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
