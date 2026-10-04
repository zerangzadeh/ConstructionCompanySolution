import uuid
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.authorization import (
    membership_has_permission,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
)

_SENSITIVE_METADATA_KEY_PARTS = frozenset(
    {"password", "token", "secret", "credential", "authorization"}
)

_STATUTORY_PAYROLL_AUDIT_ACTIONS = frozenset(
    action
    for action in AuditAction.values
    if action.startswith("payroll.statutory_")
)
_CORE_PAYROLL_AUDIT_ACTIONS = frozenset(
    action
    for action in AuditAction.values
    if action.startswith("payroll.") and action not in _STATUTORY_PAYROLL_AUDIT_ACTIONS
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
    changes: dict[str, Any] | None = None,
    correlation_id: uuid.UUID | None = None,
    allow_platform_actor: bool = False,
) -> AuditEvent:
    """Persist an audit event without exposing sensitive token values."""

    if action not in AuditAction.values:
        raise ValueError("عملیات ممیزی معتبر نیست.")
    normalized_metadata = metadata or {}
    normalized_changes = changes or {}
    _validate_audit_metadata(normalized_metadata)
    _validate_audit_metadata(normalized_changes)
    platform_actor_allowed = False
    if allow_platform_actor and actor is not None:
        from apps.organizations.authorization import is_platform_actor

        platform_actor_allowed = is_platform_actor(actor)
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
        correlation_id=correlation_id or uuid.uuid4(),
        changes=normalized_changes,
        metadata=normalized_metadata,
    )


def get_organization_audit_events(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[AuditEvent]:
    """Return audit events only for an active organization membership."""

    membership = require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.AUDIT_VIEW,
        message="اجازه مشاهده گزارش رویدادهای این شرکت را ندارید.",
    )
    queryset = (
        AuditEvent.objects.filter(organization=organization)
        .select_related("actor")
        .order_by("-created_at")
    )
    if not membership_has_permission(
        membership, BusinessPermissionCode.PAYROLL_AUDIT_VIEW
    ):
        queryset = queryset.exclude(action__in=_CORE_PAYROLL_AUDIT_ACTIONS)
    if not membership_has_permission(
        membership, BusinessPermissionCode.PAYROLL_STATUTORY_AUDIT_VIEW
    ):
        queryset = queryset.exclude(action__in=_STATUTORY_PAYROLL_AUDIT_ACTIONS)
    return queryset
