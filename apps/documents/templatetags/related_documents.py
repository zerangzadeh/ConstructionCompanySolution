"""Presentation-only integration; the business view has already read its object."""

from django import template

from apps.documents.presentation import related_documents_for

register = template.Library()


@register.simple_tag(takes_context=True)
def related_documents(context, target):
    request = context["request"]
    return related_documents_for(
        user=request.user, organization=request.organization, target=target
    )
