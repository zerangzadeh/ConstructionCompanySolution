"""Template adapters for the single product surface authority."""

from django import template

from core.product_surface import route_exposed, url_exposed

register = template.Library()
register.filter("surface_exposed", route_exposed)
register.filter("surface_url_exposed", url_exposed)


@register.filter
def surface_link_active(link, view_name):
    return link.is_active_for(view_name)
