"""Platform-owned company oversight and explicitly bounded administration."""

from datetime import datetime
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, OuterRef, Q, QuerySet, Subquery

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.authorization import is_platform_admin
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    Organization,
    OrganizationSettings,
    OrganizationStatus,
)
from apps.organizations.permission_registry import PLATFORM_COMPANY_PERMISSIONS
from apps.organizations.platform_grants import lock_platform_admin
from apps.organizations.services import _save_organization_settings


def _require_platform_permission(
    actor: User, permission: BusinessPermissionCode
) -> None:
    if (
        permission not in PLATFORM_COMPANY_PERMISSIONS
        or not is_platform_admin(actor)
        or not BusinessPermission.objects.filter(
            code=permission, is_active=True
        ).exists()
    ):
        raise PermissionDenied("اجازه مدیریت شرکت‌های پلتفرم را ندارید.")


def platform_companies(*, actor: User) -> QuerySet[Organization]:
    _require_platform_permission(actor, BusinessPermissionCode.PLATFORM_COMPANIES_VIEW)
    return Organization.objects.annotate(
        member_count=Count("memberships", distinct=True),
        last_activity=Subquery(
            AuditEvent.objects.filter(organization_id=OuterRef("pk"))
            .order_by("-created_at")
            .values("created_at")[:1]
        ),
    ).order_by("name", "pk")


def company_activity(
    *, actor: User, organization: Organization
) -> QuerySet[AuditEvent]:
    _require_platform_permission(
        actor, BusinessPermissionCode.PLATFORM_COMPANIES_AUDIT_VIEW
    )
    return (
        AuditEvent.objects.filter(organization=organization)
        .select_related("actor")
        .only("action", "created_at", "actor__username")
        .order_by("-created_at", "-pk")
    )


def filter_company_activity(
    events: QuerySet[AuditEvent], *, search: str
) -> QuerySet[AuditEvent]:
    if not search:
        return events
    matching_actions = [
        action for action, label in AuditAction.choices if search in str(label)
    ]
    return events.filter(
        Q(actor__username__icontains=search)
        | Q(action__icontains=search)
        | Q(action__in=matching_actions)
    )


def _lock_company(organization_id: UUID) -> Organization:
    organization = Organization.objects.select_for_update().get(pk=organization_id)
    if (
        organization.deleted_at is not None
        or organization.archived_at is not None
        or organization.status
        not in {OrganizationStatus.ACTIVE, OrganizationStatus.SUSPENDED}
    ):
        raise ValidationError("این عملیات فقط برای شرکت فعال یا تعلیق‌شده مجاز است.")
    return organization


def _validate_change(
    organization: Organization, *, expected_updated_at: datetime, reason: str
) -> str:
    reason = reason.strip()
    if not reason or len(reason) > 1000:
        raise ValidationError("دلیل عملیات باید بین ۱ تا ۱۰۰۰ نویسه باشد.")
    if organization.updated_at != expected_updated_at:
        raise ValidationError("اطلاعات شرکت تغییر کرده است. صفحه را تازه‌سازی کنید.")
    return reason


@transaction.atomic
def change_company_status(
    *,
    actor: User,
    organization_id: UUID,
    target_status: str,
    expected_updated_at: datetime,
    reason: str,
) -> Organization:
    actor = lock_platform_admin(actor)
    _require_platform_permission(
        actor, BusinessPermissionCode.PLATFORM_COMPANIES_CHANGE_STATUS
    )
    organization = _lock_company(organization_id)
    reason = _validate_change(
        organization, expected_updated_at=expected_updated_at, reason=reason
    )
    if target_status not in {OrganizationStatus.ACTIVE, OrganizationStatus.SUSPENDED}:
        raise ValidationError("عملیات تغییر وضعیت معتبر نیست.")
    if organization.status == target_status:
        return organization
    previous_status = organization.status
    organization.status = target_status
    organization.updated_by = actor
    organization.full_clean()
    organization.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.ORGANIZATION_STATUS_CHANGED,
        organization=organization,
        actor=actor,
        entity_type="organizations.Organization",
        entity_id=organization.pk,
        changes={"status": {"before": previous_status, "after": target_status}},
        metadata={"reason": reason, "control_plane": True},
        allow_platform_actor=True,
    )
    return organization


@transaction.atomic
def update_platform_company(
    *,
    actor: User,
    organization_id: UUID,
    expected_updated_at: datetime,
    reason: str,
    profile_data: dict,
    settings_data: dict,
) -> OrganizationSettings:
    actor = lock_platform_admin(actor)
    _require_platform_permission(
        actor, BusinessPermissionCode.PLATFORM_COMPANIES_CONFIGURE
    )
    organization = _lock_company(organization_id)
    reason = _validate_change(
        organization, expected_updated_at=expected_updated_at, reason=reason
    )
    return _save_organization_settings(
        organization=organization,
        actor=actor,
        profile_data=profile_data,
        settings_data=settings_data,
        platform_reason=reason,
    )
