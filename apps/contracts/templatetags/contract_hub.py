"""Permission-checked return path into the existing Contract workspace."""

from django import template
from django.urls import reverse

from apps.contracts.services import get_organization_contracts
from apps.organizations.authorization import has_business_permission
from apps.organizations.form_scoping import normalized_uuid
from apps.organizations.models import BusinessPermissionCode as P
from core.product_surface import route_exposed

register = template.Library()


@register.simple_tag(takes_context=True)
def contract_quantities_url(context, identifier):
    request = context["request"]
    identifier = normalized_uuid(identifier)
    if not identifier or not route_exposed("contracts:detail"):
        return ""
    if not has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=P.CONTRACTS_VIEW,
        allow_any_scope=True,
    ):
        return ""
    contract = (
        get_organization_contracts(user=request.user, organization=request.organization)
        .filter(pk=identifier)
        .first()
    )
    return (
        reverse("contracts:detail", args=[contract.pk])
        + "?section=quantities&pane=basis"
        if contract
        and contract.direction == "receivable"
        and contract.status != "draft"
        else ""
    )
