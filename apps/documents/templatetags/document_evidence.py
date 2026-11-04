from django import template
from django.core.exceptions import PermissionDenied

from apps.documents.evidence import (
    COMMERCIAL_PERMISSIONS,
    evidence_panel,
    picker_source,
)

register = template.Library()


@register.simple_tag(takes_context=True)
def document_evidence(context, kind, target):
    if target is None:
        return None
    request = context["request"]
    return evidence_panel(
        user=request.user,
        organization=request.organization,
        kind=kind,
        identifier=target.pk,
    )


@register.simple_tag(takes_context=True)
def evidence_management_allowed(context, kind, target):
    if kind not in COMMERCIAL_PERMISSIONS:
        return False
    request = context["request"]
    try:
        picker_source(
            user=request.user,
            organization=request.organization,
            kind=kind,
            identifier=target.pk,
        )
    except PermissionDenied:
        return False
    return True
