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

_SENSITIVE_METADATA_KEY_PARTS = frozenset(
    {"password", "token", "secret", "credential", "authorization"}
)


def _validate_audit_metadata(metadata: dict[str, Any]) -> None:
    """Reject metadata keys that could expose secrets in immutable evidence."""

    for key, value in metadata.items():
        normalized_key = str(key).lower()
        if any(part in normalized_key for part in _SENSITIVE_METADATA_KEY_PARTS):
            raise ValueError("Audit metadata must not contain sensitive values.")
        if isinstance(value, dict):
            _validate_audit_metadata(value)


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
    normalized_metadata = metadata or {}
    _validate_audit_metadata(normalized_metadata)
    if (
        organization is not None
        and actor is not None
        and not organization.memberships.filter(
            user=actor,
            status=MembershipStatus.ACTIVE,
        ).exists()
    ):
        raise PermissionDenied("The audit actor does not belong to this organization.")
    return AuditEvent.objects.create(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        organization=organization,
        actor=actor,
        metadata=normalized_metadata,
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
