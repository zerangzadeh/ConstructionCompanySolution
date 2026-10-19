"""Disabled compatibility entry points; retained only until readiness-gated removal.

Current operations use apps.treasury.services and apps.subledgers.services.
These stubs deliberately perform no legacy reads or writes.
"""

from django.core.exceptions import PermissionDenied


def _retired(*args, **kwargs):
    raise PermissionDenied(
        "Legacy Payment is retired; use Treasury/Subledger services."
    )


create_payment = _retired
void_payment = _retired
allocate_payment = _retired
reverse_payment_allocation = _retired
get_organization_payments = _retired

# Retained catalog evidence until the gated schema contract step. No permission
# can reactivate these fail-closed compatibility entry points.
from apps.organizations.models import BusinessPermissionCode

RETIRED_PERMISSIONS = (
    BusinessPermissionCode.PAYMENTS_VIEW,
    BusinessPermissionCode.PAYMENTS_CREATE,
    BusinessPermissionCode.PAYMENTS_VOID,
    BusinessPermissionCode.PAYMENTS_ALLOCATE,
)
