"""Platform-owned company oversight and explicitly bounded administration."""

from datetime import datetime
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, OuterRef, Q, QuerySet, Subquery

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.authorization import (
    is_platform_admin,
    membership_has_role,
    membership_is_tenant_owner,
)
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
    OrganizationStatus,
)
from apps.organizations.permission_registry import PLATFORM_COMPANY_PERMISSIONS
from apps.organizations.platform_grants import lock_platform_admin
from apps.organizations.services import _save_organization_settings

PLATFORM_READ_ONLY_SETTINGS = (
    "currency",
    "fiscal_year_start_month",
    "fiscal_year_start_day",
    "project_code_prefix",
    "contract_code_prefix",
    "site_code_prefix",
    "document_code_prefix",
)


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
    settings = OrganizationSettings.objects.get(organization=organization)
    if any(
        field in settings_data and settings_data[field] != getattr(settings, field)
        for field in PLATFORM_READ_ONLY_SETTINGS
    ):
        raise ValidationError("تنظیمات مالی و شماره‌گذاری از این مسیر قابل تغییر نیست.")
    return _save_organization_settings(
        organization=organization,
        actor=actor,
        profile_data=profile_data,
        settings_data=settings_data,
        platform_reason=reason,
    )


def company_governors(organization: Organization) -> tuple[list[User], list[User]]:
    memberships = (
        organization.memberships.filter(
            status=MembershipStatus.ACTIVE,
            user__is_active=True,
        )
        .filter(
            Q(role_definition__is_owner=True)
            | Q(role_definition__code=MembershipRole.TENANT_ADMIN)
            | Q(
                role_assignments__role__code__in=(
                    MembershipRole.TENANT_OWNER,
                    MembershipRole.TENANT_ADMIN,
                )
            )
        )
        .distinct()
        .select_related("user", "role_definition")
        .prefetch_related("role_assignments__role")
    )
    owners, admins = [], []
    for membership in memberships:
        if membership_is_tenant_owner(membership):
            owners.append(membership.user)
        if membership_has_role(membership, MembershipRole.TENANT_ADMIN):
            admins.append(membership.user)
    return owners, admins


def incomplete_company_onboarding(organization: Organization) -> bool:
    from apps.daily_reports.workflow import WORKFLOW_TYPE_CODE as daily_reports_code
    from apps.procurement.workflow import WORKFLOW_TYPE_CODE as procurement_code
    from apps.workflows.models import (
        WorkflowVersion,
        WorkflowVersionStatus,
        canonical_scope,
    )

    codes = {daily_reports_code, procurement_code}
    published = WorkflowVersion.objects.filter(
        organization=organization,
        status=WorkflowVersionStatus.PUBLISHED,
        definition__scope_key=canonical_scope({})[1],
        definition__workflow_type__code__in=codes,
        definition__workflow_type__is_active=True,
    ).values_list("definition__workflow_type__code", flat=True)
    return set(published) != codes


@transaction.atomic
def retry_company_onboarding(*, actor: User, organization_id: UUID) -> None:
    from apps.daily_reports.workflow import ensure_daily_report_compatibility_workflow
    from apps.procurement.workflow import ensure_purchase_request_compatibility_workflow

    actor = lock_platform_admin(actor)
    _require_platform_permission(
        actor, BusinessPermissionCode.PLATFORM_COMPANIES_CONFIGURE
    )
    organization = _lock_company(organization_id)
    if not organization.is_active:
        raise ValidationError("برای تکمیل راه‌اندازی، شرکت باید فعال باشد.")
    if not incomplete_company_onboarding(organization):
        return
    owners, _ = company_governors(organization)
    if len(owners) != 1:
        raise ValidationError("تکمیل راه‌اندازی به یک مالک فعال و مشخص نیاز دارد.")
    owner = owners[0]
    ensure_purchase_request_compatibility_workflow(
        organization=organization, actor=owner
    )
    ensure_daily_report_compatibility_workflow(organization=organization, actor=owner)
    record_audit_event(
        action=AuditAction.ORGANIZATION_ONBOARDING_RETRIED,
        entity_type="organization",
        entity_id=organization.pk,
        organization=organization,
        actor=actor,
        allow_platform_actor=True,
        metadata={"control_plane": True},
    )
