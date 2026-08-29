from typing import Any

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    MembershipStatus,
    Organization,
    OrganizationStatus,
)


def record_audit_event(
    *,
    action: str,
    entity_type: str,
    entity_id: str = "",
    organization: Organization | None = None,
    actor: User | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Persist an audit event without exposing sensitive token values."""

    if action not in AuditAction.values:
        raise ValueError("Invalid audit action.")
    return AuditEvent.objects.create(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        organization=organization,
        actor=actor,
        metadata=metadata or {},
    )


def get_organization_audit_events(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[AuditEvent]:
    """Return audit events only for an active organization membership."""

    if not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    has_membership = organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
    ).exists()
    if not has_membership:
        raise PermissionDenied("You do not have access to this organization.")
    return (
        AuditEvent.objects.filter(organization=organization)
        .select_related("actor")
        .order_by("-created_at")
    )
