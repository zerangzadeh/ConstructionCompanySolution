"""Read-only action presentation; mutations remain in existing domain services."""

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
)
from apps.organizations.models import BusinessPermissionCode

from .models import PayableCertificate
from .payable_workflow import _actor_item


def payable_detail_actions(
    request: HttpRequest, certificate: PayableCertificate
) -> dict[str, bool]:
    def permitted(code: BusinessPermissionCode) -> bool:
        return has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=code,
            project=certificate.project,
        )

    mutable = request.organization.status == "active"
    can_decide = False
    if (
        mutable
        and certificate.status == "submitted"
        and permitted(BusinessPermissionCode.PAYABLE_CERTIFICATES_APPROVE)
        and permitted(BusinessPermissionCode.WORK_ITEMS_ACT)
    ):
        try:
            membership = get_active_membership(
                user=request.user, organization=request.organization
            )
            item = _actor_item(
                organization=request.organization,
                certificate=certificate,
                membership=membership,
            )
            can_decide = (
                item.status == "open"
                and permitted(BusinessPermissionCode.WORK_ITEMS_CLAIM)
            ) or (
                item.status == "claimed" and item.current_assignee_id == membership.pk
            )
        except PermissionDenied:
            pass
    return {
        "can_submit": mutable
        and certificate.status == "draft"
        and permitted(BusinessPermissionCode.PAYABLE_CERTIFICATES_SUBMIT),
        "can_decide": can_decide,
        "can_revise": mutable
        and permitted(BusinessPermissionCode.PAYABLE_CERTIFICATES_REVISE),
    }
