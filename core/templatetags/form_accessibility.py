from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def accessible_field(field):
    """Render a form control with stable help and validation associations."""
    described_by = str(field.field.widget.attrs.get("aria-describedby", "")).split()
    if field.help_text:
        described_by.append(f"{field.auto_id}-help")
    if field.errors:
        described_by.append(f"{field.auto_id}-errors")

    attrs: dict[str, str] = {}
    if described_by:
        attrs["aria-describedby"] = " ".join(dict.fromkeys(described_by))
    if field.errors:
        attrs["aria-invalid"] = "true"
    return field.as_widget(attrs=attrs)
