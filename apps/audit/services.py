from typing import Any

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
)

_SENSITIVE_METADATA_KEY_PARTS = frozenset(
    {"password", "token", "secret", "credential", "authorization"}
)


def _validate_audit_metadata(metadata: dict[str, Any]) -> None:
    """Reject metadata keys that could expose secrets in immutable evidence."""

    for key, value in metadata.items():
        normalized_key = str(key).lower()
        if any(part in normalized_key for part in _SENSITIVE_METADATA_KEY_PARTS):
            raise ValueError("فراداده ممیزی نباید شامل مقادیر حساس باشد.")
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
    allow_platform_actor: bool = False,
) -> AuditEvent:
    """Persist an audit event without exposing sensitive token values."""

    if action not in AuditAction.values:
        raise ValueError("عملیات ممیزی معتبر نیست.")
    normalized_metadata = metadata or {}
    _validate_audit_metadata(normalized_metadata)
    platform_actor_allowed = False
    if allow_platform_actor and actor is not None:
        from apps.organizations.authorization import is_platform_admin

        platform_actor_allowed = is_platform_admin(actor)
    if (
        organization is not None
        and actor is not None
        and not platform_actor_allowed
        and not organization.memberships.filter(
            user=actor,
            status=MembershipStatus.ACTIVE,
        ).exists()
    ):
        raise PermissionDenied("عامل رویداد ممیزی متعلق به این سازمان نیست.")
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

    require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.AUDIT_VIEW,
        message="اجازه مشاهده گزارش رویدادهای این شرکت را ندارید.",
    )
    return (
        AuditEvent.objects.filter(organization=organization)
        .select_related("actor")
        .order_by("-created_at")
    )
