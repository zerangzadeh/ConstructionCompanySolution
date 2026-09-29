from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import (
    is_platform_admin,
    membership_has_role,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipRole,
    Organization,
    PlatformPolicy,
    PlatformPolicyVersion,
    PolicyReviewDisposition,
    PolicyReviewEvidence,
    PolicySource,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)


def _require_platform_admin(actor: User) -> None:
    if not is_platform_admin(actor):
        raise PermissionDenied("فقط Platform Admin مجاز به مدیریت کاتالوگ سیاست است.")


def _snapshot_version(version: PlatformPolicyVersion) -> dict[str, Any]:
    return {
        "policy_code": version.policy.code,
        "version": version.version,
        "status": version.status,
        "effective_from": version.effective_from.isoformat(),
        "effective_to": (
            version.effective_to.isoformat() if version.effective_to else None
        ),
        "source_ids": sorted(
            str(item) for item in version.sources.values_list("pk", flat=True)
        ),
    }


@transaction.atomic
def record_policy_source(
    *,
    actor: User,
    issuer: str,
    title: str,
    source_identifier: str,
    version: str,
    applicability: str,
    source_location: str = "",
    publication_date: date | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    supersedes: PolicySource | None = None,
) -> PolicySource:
    """Record source metadata without treating the issuer as a system actor."""

    _require_platform_admin(actor)
    source = PolicySource(
        issuer=issuer.strip(),
        title=title.strip(),
        source_identifier=source_identifier.strip(),
        source_location=source_location.strip(),
        version=version.strip(),
        publication_date=publication_date,
        effective_from=effective_from,
        effective_to=effective_to,
        applicability=applicability.strip(),
        supersedes=supersedes,
        created_by=actor,
    )
    source.full_clean()
    source.save()
    record_audit_event(
        action=AuditAction.POLICY_SOURCE_RECORDED,
        entity_type="organizations.PolicySource",
        entity_id=source.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "issuer": source.issuer,
            "source_identifier": source.source_identifier,
            "version": source.version,
        },
    )
    return source


@transaction.atomic
def create_platform_policy(
    *,
    actor: User,
    code: str,
    name: str,
    category: str,
    sensitivity: str,
    tenant_selectable: bool = True,
    requires_source_provenance: bool = False,
) -> PlatformPolicy:
    _require_platform_admin(actor)
    policy = PlatformPolicy(
        code=code,
        name=name.strip(),
        category=category,
        sensitivity=sensitivity,
        tenant_selectable=tenant_selectable,
        requires_source_provenance=requires_source_provenance,
        created_by=actor,
        updated_by=actor,
    )
    policy.full_clean()
    policy.save()
    record_audit_event(
        action=AuditAction.PLATFORM_POLICY_CREATED,
        entity_type="organizations.PlatformPolicy",
        entity_id=policy.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "policy_code": policy.code,
            "category": policy.category,
            "sensitivity": policy.sensitivity,
            "requires_source_provenance": policy.requires_source_provenance,
        },
    )
    return policy


@transaction.atomic
def create_platform_policy_version(
    *,
    actor: User,
    policy: PlatformPolicy,
    version: int,
    parameters: dict[str, Any],
    effective_from: date,
    reason: str,
    effective_to: date | None = None,
    sources: Iterable[PolicySource] = (),
    supersedes: PlatformPolicyVersion | None = None,
) -> PlatformPolicyVersion:
    _require_platform_admin(actor)
    locked_policy = PlatformPolicy.objects.select_for_update().get(pk=policy.pk)
    if not locked_policy.is_active:
        raise ValidationError("سیاست غیرفعال نسخه جدید نمی‌پذیرد.")
    policy_version = PlatformPolicyVersion(
        policy=locked_policy,
        version=version,
        parameters=parameters,
        effective_from=effective_from,
        effective_to=effective_to,
        supersedes=supersedes,
        created_by=actor,
        reason=reason.strip(),
    )
    policy_version.full_clean()
    policy_version.save()
    policy_version.sources.set(sources)
    record_audit_event(
        action=AuditAction.PLATFORM_POLICY_VERSION_CREATED,
        entity_type="organizations.PlatformPolicyVersion",
        entity_id=policy_version.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata=_snapshot_version(policy_version),
    )
    return policy_version


@transaction.atomic
def publish_platform_policy_version(
    *, actor: User, policy_version: PlatformPolicyVersion
) -> PlatformPolicyVersion:
    _require_platform_admin(actor)
    locked = (
        PlatformPolicyVersion.objects.select_for_update()
        .select_related("policy")
        .get(pk=policy_version.pk)
    )
    if locked.status != PolicyVersionStatus.DRAFT:
        raise ValidationError("فقط نسخه پیش‌نویس قابل انتشار است.")
    if not locked.parameters:
        raise ValidationError("سیاست بدون پارامتر مشخص قابل انتشار نیست.")
    if locked.policy.requires_source_provenance and not locked.sources.exists():
        raise ValidationError("سیاست دارای الزام منبع بدون منبع قابل انتشار نیست.")
    overlap = PlatformPolicyVersion.objects.filter(
        policy=locked.policy,
        status=PolicyVersionStatus.PUBLISHED,
        effective_from__lt=locked.effective_to or date.max,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=locked.effective_from))
    if overlap.exists():
        raise ValidationError("بازه اعتبار نسخه با نسخه منتشرشده هم‌پوشانی دارد.")
    locked.status = PolicyVersionStatus.PUBLISHED
    locked.published_by = actor
    locked.published_at = timezone.now()
    locked.save(update_fields=["status", "published_by", "published_at", "updated_at"])
    record_audit_event(
        action=AuditAction.PLATFORM_POLICY_VERSION_PUBLISHED,
        entity_type="organizations.PlatformPolicyVersion",
        entity_id=locked.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata=_snapshot_version(locked),
    )
    return locked


@transaction.atomic
def record_optional_policy_review(
    *,
    actor: User,
    policy_version: PlatformPolicyVersion,
    reviewer_identity: str,
    qualification_summary: str,
    independence_statement: str,
    evidence_reference: str,
    reviewed_on: date,
    review_scope: str,
    disposition: str,
    conditions: str = "",
) -> PolicyReviewEvidence:
    """Attach optional evidence; it grants no role and is not a publication gate."""

    _require_platform_admin(actor)
    if disposition not in PolicyReviewDisposition.values:
        raise ValidationError("نتیجه بررسی معتبر نیست.")
    evidence = PolicyReviewEvidence(
        policy_version=policy_version,
        reviewer_identity=reviewer_identity.strip(),
        qualification_summary=qualification_summary.strip(),
        independence_statement=independence_statement.strip(),
        evidence_reference=evidence_reference.strip(),
        reviewed_on=reviewed_on,
        review_scope=review_scope.strip(),
        disposition=disposition,
        conditions=conditions.strip(),
        created_by=actor,
    )
    evidence.full_clean()
    evidence.save()
    record_audit_event(
        action=AuditAction.POLICY_REVIEW_EVIDENCE_RECORDED,
        entity_type="organizations.PolicyReviewEvidence",
        entity_id=evidence.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "policy_code": policy_version.policy.code,
            "policy_version": policy_version.version,
            "disposition": evidence.disposition,
            "evidence_reference": evidence.evidence_reference,
        },
    )
    return evidence


def _require_tenant_role(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
    role: str,
):
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اختیار مدیریت سیاست Tenant را ندارید.",
    )
    if not membership_has_role(membership, role):
        raise PermissionDenied("نقش داخلی لازم برای این مرحله را ندارید.")
    return membership


@transaction.atomic
def approve_tenant_policy_selection(
    *,
    organization: Organization,
    actor: User,
    policy_version: PlatformPolicyVersion,
    reason: str,
) -> TenantPolicySelection:
    locked_organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )
    owner = _require_tenant_role(
        organization=locked_organization,
        actor=actor,
        permission=BusinessPermissionCode.TENANT_POLICIES_APPROVE,
        role=MembershipRole.TENANT_OWNER,
    )
    version = (
        PlatformPolicyVersion.objects.select_for_update()
        .select_related("policy")
        .get(pk=policy_version.pk)
    )
    if version.status != PolicyVersionStatus.PUBLISHED or not version.policy.is_active:
        raise ValidationError("فقط نسخه منتشرشده سیاست فعال قابل انتخاب است.")
    if not version.policy.tenant_selectable:
        raise ValidationError("این سیاست توسط Tenant قابل انتخاب نیست.")
    selection = TenantPolicySelection(
        organization=locked_organization,
        policy=version.policy,
        policy_version=version,
        approved_by=owner,
        approved_at=timezone.now(),
        reason=reason.strip(),
    )
    selection.full_clean()
    selection.save()
    record_audit_event(
        action=AuditAction.TENANT_POLICY_APPROVED,
        entity_type="organizations.TenantPolicySelection",
        entity_id=selection.pk,
        organization=locked_organization,
        actor=actor,
        metadata={
            "policy_code": version.policy.code,
            "policy_version": version.version,
            "reason": selection.reason,
        },
    )
    return selection


def _version_is_effective(version: PlatformPolicyVersion, on_date: date) -> bool:
    return (
        version.status == PolicyVersionStatus.PUBLISHED
        and version.effective_from <= on_date
        and (version.effective_to is None or version.effective_to > on_date)
    )


def list_tenant_policy_selections(*, organization: Organization, actor: User):
    """Return only the active member's authorized, organization-scoped selections."""

    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TENANT_POLICIES_VIEW,
        message="اختیار مشاهده سیاست‌های Tenant را ندارید.",
    )
    return TenantPolicySelection.objects.filter(
        organization=organization
    ).select_related("policy", "policy_version", "approved_by", "applied_by")


@transaction.atomic
def apply_tenant_policy_selection(
    *, organization: Organization, actor: User, selection: TenantPolicySelection
) -> TenantPolicySelection:
    locked_organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )
    admin = _require_tenant_role(
        organization=locked_organization,
        actor=actor,
        permission=BusinessPermissionCode.TENANT_POLICIES_APPLY,
        role=MembershipRole.TENANT_ADMIN,
    )
    locked = (
        TenantPolicySelection.objects.select_for_update()
        .select_related("policy", "policy_version")
        .get(pk=selection.pk)
    )
    if locked.organization_id != locked_organization.pk:
        raise PermissionDenied("انتخاب سیاست متعلق به Tenant دیگری است.")
    if locked.status != TenantPolicySelectionStatus.APPROVED:
        raise ValidationError("فقط انتخاب تأییدشده قابل اعمال است.")
    if not _version_is_effective(locked.policy_version, timezone.localdate()):
        raise ValidationError("نسخه سیاست در تاریخ جاری معتبر و منتشرشده نیست.")
    if (
        locked.policy.requires_source_provenance
        and not locked.policy_version.sources.exists()
    ):
        raise ValidationError("سیاست دارای الزام منبع بدون منبع قابل اعمال نیست.")
    prior = TenantPolicySelection.objects.select_for_update().filter(
        organization=locked_organization,
        policy=locked.policy,
        status=TenantPolicySelectionStatus.ACTIVE,
    )
    now = timezone.now()
    for previous in prior:
        previous.status = TenantPolicySelectionStatus.SUPERSEDED
        previous.save(update_fields=["status", "updated_at"])
        locked.supersedes = previous
    locked.status = TenantPolicySelectionStatus.ACTIVE
    locked.applied_by = admin
    locked.applied_at = now
    locked.full_clean()
    locked.save(
        update_fields=[
            "status",
            "applied_by",
            "applied_at",
            "supersedes",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.TENANT_POLICY_APPLIED,
        entity_type="organizations.TenantPolicySelection",
        entity_id=locked.pk,
        organization=locked_organization,
        actor=actor,
        metadata={
            "policy_code": locked.policy.code,
            "policy_version": locked.policy_version.version,
            "reason": locked.reason,
        },
    )
    return locked


def resolve_active_tenant_policy(
    *, organization: Organization, policy_code: str
) -> PlatformPolicyVersion:
    """Resolve only an active, effective selection; absence/invalidity fails closed."""

    if not organization.is_active:
        raise PermissionDenied("Tenant فعال نیست.")
    try:
        selection = TenantPolicySelection.objects.select_related(
            "policy", "policy_version"
        ).get(
            organization=organization,
            policy__code=policy_code,
            status=TenantPolicySelectionStatus.ACTIVE,
        )
    except TenantPolicySelection.DoesNotExist as exc:
        raise ValidationError("سیاست فعال برای Tenant پیکربندی نشده است.") from exc
    if not _version_is_effective(selection.policy_version, timezone.localdate()):
        raise ValidationError("نسخه سیاست فعال منقضی یا منتشرنشده است.")
    if (
        selection.policy.requires_source_provenance
        and not selection.policy_version.sources.exists()
    ):
        raise ValidationError("سیاست دارای الزام منبع فاقد منبع است.")
    return selection.policy_version
