from __future__ import annotations

from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
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
    InsuranceClassification,
    MembershipRole,
    Organization,
    PlatformPolicy,
    PlatformPolicyVersion,
    PlatformPolicyVersionSource,
    PolicyReviewDisposition,
    PolicyReviewEvidence,
    PolicySource,
    PolicySourceBasis,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_specs import (
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
    ACCOUNTING_ROUNDING_POLICY_CODE,
    RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
    get_platform_policy_spec,
    initial_accounting_policy_parameters,
    validate_policy_for_consumer,
    validate_policy_parameters,
)


def _require_platform_admin(actor: User) -> None:
    if not is_platform_admin(actor):
        raise PermissionDenied("فقط Platform Admin مجاز به مدیریت کاتالوگ سیاست است.")


def _snapshot_version(version: PlatformPolicyVersion) -> dict[str, Any]:
    return {
        "policy_code": version.policy.code,
        "insurance_classification_id": str(version.insurance_classification_id)
        if version.insurance_classification_id
        else None,
        "version": version.version,
        "status": version.status,
        "effective_from": version.effective_from.isoformat(),
        "effective_to": (
            version.effective_to.isoformat() if version.effective_to else None
        ),
        "supersedes_id": str(version.supersedes_id) if version.supersedes_id else None,
        "source_basis": version.source_basis,
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
    reason: str,
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
        reason=reason.strip(),
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
            "before": None,
            "after": {
                "issuer": source.issuer,
                "source_identifier": source.source_identifier,
                "version": source.version,
            },
            "reason": source.reason,
        },
    )
    return source


@transaction.atomic
def create_platform_policy(
    *,
    actor: User,
    code: str,
    reason: str,
) -> PlatformPolicy:
    _require_platform_admin(actor)
    spec = get_platform_policy_spec(code)
    if not reason.strip():
        raise ValidationError("دلیل ثبت تعریف سیاست الزامی است.")
    policy, created = PlatformPolicy.objects.get_or_create(
        code=spec.code,
        defaults={
            "name": spec.name,
            "category": spec.category,
            "sensitivity": spec.sensitivity,
            "tenant_selectable": spec.tenant_selectable,
            "requires_source_provenance": False,
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if (
        policy.name != spec.name
        or policy.category != spec.category
        or policy.sensitivity != spec.sensitivity
        or policy.tenant_selectable != spec.tenant_selectable
        or policy.requires_source_provenance
    ):
        raise ValidationError("تعریف ذخیره‌شده با کاتالوگ کد-محور سیاست هم‌خوان نیست.")
    if created:
        record_audit_event(
            action=AuditAction.PLATFORM_POLICY_CREATED,
            entity_type="organizations.PlatformPolicy",
            entity_id=policy.pk,
            actor=actor,
            allow_platform_actor=True,
            metadata={
                "before": None,
                "after": {
                    "policy_code": policy.code,
                    "category": policy.category,
                    "sensitivity": policy.sensitivity,
                    "tenant_selectable": policy.tenant_selectable,
                },
                "reason": reason.strip(),
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
    source_basis: str,
    effective_to: date | None = None,
    supersedes: PlatformPolicyVersion | None = None,
    insurance_classification: InsuranceClassification | None = None,
) -> PlatformPolicyVersion:
    _require_platform_admin(actor)
    locked_policy = PlatformPolicy.objects.select_for_update().get(pk=policy.pk)
    if not locked_policy.is_active:
        raise ValidationError("سیاست غیرفعال نسخه جدید نمی‌پذیرد.")
    spec = get_platform_policy_spec(locked_policy.code)
    if (
        locked_policy.name != spec.name
        or locked_policy.category != spec.category
        or locked_policy.sensitivity != spec.sensitivity
        or locked_policy.tenant_selectable != spec.tenant_selectable
    ):
        raise ValidationError("تعریف ذخیره‌شده با کاتالوگ کد-محور سیاست هم‌خوان نیست.")
    if effective_from < timezone.localdate():
        raise ValidationError("تغییر با تاریخ گذشته برای سیاست مجاز نیست.")
    if source_basis not in PolicySourceBasis.values:
        raise ValidationError("مبنای منبع سیاست معتبر نیست.")
    validate_policy_parameters(spec=spec, parameters=parameters)
    existing_versions = locked_policy.versions.filter(
        insurance_classification=insurance_classification
    ).exclude(status=PolicyVersionStatus.DRAFT)
    if existing_versions.exists() and supersedes is None:
        raise ValidationError("نسخه جایگزین باید صریحاً نسخه قبلی را supersede کند.")
    if supersedes and supersedes.policy_id != locked_policy.pk:
        raise ValidationError("نسخه supersede‌شده متعلق به همین سیاست نیست.")
    policy_version = PlatformPolicyVersion(
        policy=locked_policy,
        insurance_classification=insurance_classification,
        version=version,
        parameters=parameters,
        effective_from=effective_from,
        effective_to=effective_to,
        supersedes=supersedes,
        source_basis=source_basis,
        created_by=actor,
        reason=reason.strip(),
    )
    policy_version.full_clean()
    policy_version.save()
    record_audit_event(
        action=AuditAction.PLATFORM_POLICY_VERSION_CREATED,
        entity_type="organizations.PlatformPolicyVersion",
        entity_id=policy_version.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "before": None,
            "after": _snapshot_version(policy_version),
            "reason": policy_version.reason,
        },
    )
    return policy_version


@transaction.atomic
def update_platform_policy_version(
    *,
    actor: User,
    policy_version: PlatformPolicyVersion,
    parameters: dict[str, Any],
    effective_from: date,
    reason: str,
    source_basis: str,
    effective_to: date | None = None,
    supersedes: PlatformPolicyVersion | None = None,
    insurance_classification: InsuranceClassification | None = None,
) -> PlatformPolicyVersion:
    """Edit only a Platform-managed draft; published history is never rewritten."""
    _require_platform_admin(actor)
    locked = (
        PlatformPolicyVersion.objects.select_for_update()
        .select_related("policy")
        .get(pk=policy_version.pk)
    )
    if locked.status != PolicyVersionStatus.DRAFT:
        raise ValidationError("فقط نسخه پیش‌نویس قابل ویرایش است.")
    if effective_from < timezone.localdate():
        raise ValidationError("تغییر با تاریخ گذشته برای سیاست مجاز نیست.")
    if source_basis not in PolicySourceBasis.values:
        raise ValidationError("مبنای منبع سیاست معتبر نیست.")
    if supersedes and supersedes.policy_id != locked.policy_id:
        raise ValidationError("نسخه supersede‌شده متعلق به همین سیاست نیست.")
    validate_policy_parameters(
        spec=get_platform_policy_spec(locked.policy.code), parameters=parameters
    )
    before = _snapshot_version(locked)
    locked.insurance_classification = insurance_classification
    locked.parameters = parameters
    locked.effective_from = effective_from
    locked.effective_to = effective_to
    locked.source_basis = source_basis
    locked.supersedes = supersedes
    locked.reason = reason.strip()
    locked.full_clean()
    locked.save()
    record_audit_event(
        action=AuditAction.PLATFORM_POLICY_VERSION_UPDATED,
        entity_type="organizations.PlatformPolicyVersion",
        entity_id=locked.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "before": before,
            "after": _snapshot_version(locked),
            "reason": locked.reason,
        },
    )
    return locked


@transaction.atomic
def link_policy_version_source(
    *,
    actor: User,
    policy_version: PlatformPolicyVersion,
    source: PolicySource,
    reason: str,
) -> PlatformPolicyVersionSource:
    _require_platform_admin(actor)
    locked = PlatformPolicyVersion.objects.select_for_update().get(pk=policy_version.pk)
    if locked.status != PolicyVersionStatus.DRAFT:
        raise ValidationError("منبع فقط به نسخه پیش‌نویس قابل پیوند است.")
    before = _snapshot_version(locked)
    link = PlatformPolicyVersionSource(
        policy_version=locked,
        source=source,
        linked_by=actor,
        reason=reason.strip(),
    )
    link.full_clean()
    link.save()
    record_audit_event(
        action=AuditAction.PLATFORM_POLICY_SOURCE_LINKED,
        entity_type="organizations.PlatformPolicyVersionSource",
        entity_id=link.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "before": before,
            "after": _snapshot_version(locked),
            "reason": link.reason,
        },
    )
    return link


@transaction.atomic
def publish_platform_policy_version(
    *, actor: User, policy_version: PlatformPolicyVersion, reason: str
) -> PlatformPolicyVersion:
    _require_platform_admin(actor)
    if not reason.strip():
        raise ValidationError("دلیل انتشار نسخه سیاست الزامی است.")
    locked = (
        PlatformPolicyVersion.objects.select_for_update()
        .select_related("policy")
        .get(pk=policy_version.pk)
    )
    if locked.status != PolicyVersionStatus.DRAFT:
        raise ValidationError("فقط نسخه پیش‌نویس قابل انتشار است.")
    PlatformPolicy.objects.select_for_update().get(pk=locked.policy_id)
    spec = get_platform_policy_spec(locked.policy.code)
    validate_policy_parameters(spec=spec, parameters=locked.parameters)
    if locked.policy.code == RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE:
        if not locked.insurance_classification_id:
            raise ValidationError("انتشار قواعد صورت‌وضعیت به طبقه‌بندی بیمه نیاز دارد.")
        classification = InsuranceClassification.objects.select_for_update().get(
            pk=locked.insurance_classification_id
        )
        if not classification.is_active:
            raise ValidationError("طبقه‌بندی بیمه غیرفعال است.")
    if locked.policy.sensitivity == "regulatory":
        if locked.source_basis != PolicySourceBasis.EXTERNAL_AUTHORITY:
            raise ValidationError("قاعده مقرراتی باید به مرجع بیرونی متکی باشد.")
        if not locked.review_evidence.filter(
            disposition=PolicyReviewDisposition.ACCEPTED
        ).exists():
            raise ValidationError(
                "قاعده مقرراتی بدون شواهد بررسی پذیرفته‌شده قابل انتشار نیست."
            )
    if (
        locked.source_basis == PolicySourceBasis.EXTERNAL_AUTHORITY
        and not locked.sources.exists()
    ):
        raise ValidationError("سیاست مبتنی بر مرجع بیرونی بدون منبع قابل انتشار نیست.")
    if not locked.source_basis:
        raise ValidationError("مبنای منبع سیاست باید مشخص باشد.")
    overlap = PlatformPolicyVersion.objects.filter(
        policy=locked.policy,
        insurance_classification_id=locked.insurance_classification_id,
        status=PolicyVersionStatus.PUBLISHED,
        effective_from__lt=locked.effective_to or date.max,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=locked.effective_from))
    # A successor is intentionally allowed to overlap its explicitly linked
    # predecessor.  Published rows stay immutable; the resolver deterministically
    # selects the newest effective version after the successor's start date.
    if locked.supersedes_id:
        overlap = overlap.exclude(pk=locked.supersedes_id)
    if overlap.exists():
        raise ValidationError("بازه اعتبار نسخه با نسخه منتشرشده هم‌پوشانی دارد.")
    before = _snapshot_version(locked)
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
        metadata={
            "before": before,
            "after": _snapshot_version(locked),
            "reason": reason.strip(),
        },
    )
    return locked


@transaction.atomic
def retire_platform_policy_version(
    *, actor: User, policy_version: PlatformPolicyVersion, reason: str
) -> PlatformPolicyVersion:
    _require_platform_admin(actor)
    locked = PlatformPolicyVersion.objects.select_for_update().get(pk=policy_version.pk)
    if locked.status != PolicyVersionStatus.PUBLISHED:
        raise ValidationError("فقط نسخه منتشرشده قابل بازنشستگی است.")
    before = _snapshot_version(locked)
    locked.status = PolicyVersionStatus.RETIRED
    locked.retired_by = actor
    locked.retired_at = timezone.now()
    locked.retirement_reason = reason.strip()
    locked.full_clean()
    locked.save(
        update_fields=[
            "status",
            "retired_by",
            "retired_at",
            "retirement_reason",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PLATFORM_POLICY_VERSION_RETIRED,
        entity_type="organizations.PlatformPolicyVersion",
        entity_id=locked.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "before": before,
            "after": _snapshot_version(locked),
            "reason": reason.strip(),
        },
    )
    return locked


@transaction.atomic
def deactivate_platform_policy(
    *, actor: User, policy: PlatformPolicy, reason: str
) -> PlatformPolicy:
    _require_platform_admin(actor)
    locked = PlatformPolicy.objects.select_for_update().get(pk=policy.pk)
    if not locked.is_active:
        raise ValidationError("سیاست از قبل غیرفعال است.")
    if not reason.strip():
        raise ValidationError("دلیل غیرفعال‌سازی سیاست الزامی است.")
    before = {"is_active": locked.is_active}
    locked.is_active = False
    locked.updated_by = actor
    locked.save(update_fields=["is_active", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.PLATFORM_POLICY_DEACTIVATED,
        entity_type="organizations.PlatformPolicy",
        entity_id=locked.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "before": before,
            "after": {"is_active": locked.is_active},
            "reason": reason.strip(),
        },
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
    if not (
        membership_has_role(membership, role)
        or membership_has_role(membership, MembershipRole.TENANT_OWNER)
    ):
        raise PermissionDenied("نقش داخلی لازم برای این مرحله را ندارید.")
    return membership


@transaction.atomic
def select_tenant_policy_version(
    *,
    organization: Organization,
    actor: User,
    policy_version: PlatformPolicyVersion,
    reason: str,
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
    version = (
        PlatformPolicyVersion.objects.select_for_update()
        .select_related("policy")
        .get(pk=policy_version.pk)
    )
    if version.status != PolicyVersionStatus.PUBLISHED or not version.policy.is_active:
        raise ValidationError("فقط نسخه منتشرشده سیاست فعال قابل انتخاب است.")
    if not version.policy.tenant_selectable:
        raise ValidationError("این سیاست توسط Tenant قابل انتخاب نیست.")
    if not _version_is_effective(version, timezone.localdate()):
        raise ValidationError("انتخاب آینده یا با تاریخ گذشته پشتیبانی نمی‌شود.")
    validate_policy_parameters(
        spec=get_platform_policy_spec(version.policy.code),
        parameters=version.parameters,
    )
    selection = TenantPolicySelection(
        organization=locked_organization,
        policy=version.policy,
        policy_version=version,
        approved_by=admin,
        approved_at=timezone.now(),
        reason=reason.strip(),
    )
    selection.full_clean()
    selection.save()
    record_audit_event(
        action=AuditAction.TENANT_POLICY_SELECTED,
        entity_type="organizations.TenantPolicySelection",
        entity_id=selection.pk,
        organization=locked_organization,
        actor=actor,
        metadata={
            "before": None,
            "after": {
                "policy_code": version.policy.code,
                "policy_version": version.version,
                "status": selection.status,
            },
            "reason": selection.reason,
            "selected_by": str(admin.pk),
        },
    )
    return selection


def _version_is_effective(version: PlatformPolicyVersion, on_date: date) -> bool:
    return (
        version.status == PolicyVersionStatus.PUBLISHED
        and version.effective_from <= on_date
        and (version.effective_to is None or version.effective_to > on_date)
    )


def derive_next_open_fiscal_period_start(
    *, organization: Organization, on_date: date | None = None
) -> date:
    """Return the next non-retroactive open accounting-period start for one Tenant."""

    from apps.accounting.models import FiscalPeriod, FiscalPeriodStatus

    if not organization.is_active:
        raise ValidationError("Tenant غیرفعال تاریخ اثر سیاست دریافت نمی‌کند.")
    as_of = on_date or timezone.localdate()
    period = (
        FiscalPeriod.objects.filter(
            organization=organization,
            status=FiscalPeriodStatus.OPEN,
            starts_on__gt=as_of,
        )
        .order_by("starts_on", "number")
        .first()
    )
    if period is None:
        raise ValidationError(
            "دوره مالی باز آینده برای تاریخ اثر سیاست حسابداری پیکربندی نشده است."
        )
    return period.starts_on


@transaction.atomic
def publish_initial_accounting_policy_versions(
    *, actor: User, effective_from: date, reason: str
) -> dict[str, PlatformPolicyVersion]:
    """Publish the two Product Owner-approved initial accounting policies together."""

    _require_platform_admin(actor)
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError("دلیل تصمیم مالک محصول الزامی است.")
    if effective_from < timezone.localdate():
        raise ValidationError(
            "نسخه نخست سیاست حسابداری نباید با تاریخ گذشته منتشر شود."
        )

    published: dict[str, PlatformPolicyVersion] = {}
    for code in (
        ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
        ACCOUNTING_ROUNDING_POLICY_CODE,
    ):
        policy = create_platform_policy(
            actor=actor, code=code, reason=normalized_reason
        )
        existing = policy.versions.filter(version=1).first()
        parameters = initial_accounting_policy_parameters(code)
        if existing is not None:
            if (
                existing.status == PolicyVersionStatus.PUBLISHED
                and existing.effective_from == effective_from
                and existing.parameters == parameters
                and existing.source_basis == PolicySourceBasis.PRODUCT_DEFINED
            ):
                published[code] = existing
                continue
            raise ValidationError(
                "نسخه نخست سیاست حسابداری از قبل با قرارداد دیگری وجود دارد."
            )
        draft = create_platform_policy_version(
            actor=actor,
            policy=policy,
            version=1,
            parameters=parameters,
            effective_from=effective_from,
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            reason=normalized_reason,
        )
        published[code] = publish_platform_policy_version(
            actor=actor,
            policy_version=draft,
            reason=normalized_reason,
        )
    return published


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
    *,
    organization: Organization,
    actor: User,
    selection: TenantPolicySelection,
    profile_audit: dict[str, Any] | None = None,
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
        locked.policy_version.source_basis == PolicySourceBasis.EXTERNAL_AUTHORITY
        and not locked.policy_version.sources.exists()
    ):
        raise ValidationError("سیاست مبتنی بر مرجع بیرونی بدون منبع قابل اعمال نیست.")
    validate_policy_parameters(
        spec=get_platform_policy_spec(locked.policy.code),
        parameters=locked.policy_version.parameters,
    )
    prior = TenantPolicySelection.objects.select_for_update().filter(
        organization=locked_organization,
        policy=locked.policy,
        status=TenantPolicySelectionStatus.ACTIVE,
    )
    now = timezone.now()
    superseded_selection_ids: list[str] = []
    for previous in prior:
        superseded_selection_ids.append(str(previous.pk))
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
            "before": {
                "status": TenantPolicySelectionStatus.APPROVED,
                "superseded_selection_ids": superseded_selection_ids,
            },
            "after": {
                "status": locked.status,
                "policy_code": locked.policy.code,
                "policy_version": locked.policy_version.version,
            },
            "reason": locked.reason,
            **(
                {
                    "configuration_profile": {
                        **profile_audit,
                        "effective_time": now.isoformat(),
                    }
                }
                if profile_audit
                else {}
            ),
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
        selection.policy_version.source_basis == PolicySourceBasis.EXTERNAL_AUTHORITY
        and not selection.policy_version.sources.exists()
    ):
        raise ValidationError("سیاست مبتنی بر مرجع بیرونی فاقد منبع است.")
    validate_policy_parameters(
        spec=get_platform_policy_spec(selection.policy.code),
        parameters=selection.policy_version.parameters,
    )
    return selection.policy_version


def resolve_effective_platform_regulatory_policy(
    *,
    code: str,
    consumer: str,
    on_date: date,
    insurance_classification: InsuranceClassification | None = None,
) -> PlatformPolicyVersion:
    """Resolve national rules directly from Platform history, never Tenant choice."""
    if code == RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE:
        if (
            insurance_classification is None
            or not InsuranceClassification.objects.filter(
                pk=insurance_classification.pk, is_active=True
            ).exists()
        ):
            raise ValidationError(
                "طبقه‌بندی بیمه فعال برای شرایط قرارداد انتخاب نشده است."
            )
    elif insurance_classification is not None:
        raise ValidationError("طبقه‌بندی بیمه برای این سیاست معتبر نیست.")
    statuses = [PolicyVersionStatus.PUBLISHED]
    if on_date < timezone.localdate():
        statuses.append(PolicyVersionStatus.RETIRED)
    version = (
        PlatformPolicyVersion.objects.select_related("policy")
        .filter(
            policy__code=code,
            insurance_classification=insurance_classification,
            policy__is_active=True,
            policy__tenant_selectable=False,
            policy__sensitivity="regulatory",
            status__in=statuses,
            effective_from__lte=on_date,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=on_date))
        .order_by("-effective_from", "-version")
        .first()
    )
    if version is None:
        raise ValidationError("نسخه مقرراتی پلتفرمِ منتشرشده و مؤثر وجود ندارد.")
    if (
        version.source_basis != PolicySourceBasis.EXTERNAL_AUTHORITY
        or not version.sources.exists()
        or not version.review_evidence.filter(
            disposition=PolicyReviewDisposition.ACCEPTED
        ).exists()
    ):
        raise ValidationError("نسخه مقرراتی پلتفرم فاقد منبع و بررسی پذیرفته‌شده است.")
    validate_policy_for_consumer(
        policy_version=version, consumer=consumer, expected_policy_code=code
    )
    return version


@transaction.atomic
def create_insurance_classification(
    *, actor: User, code: str, name: str, reason: str
) -> InsuranceClassification:
    _require_platform_admin(actor)
    if not reason.strip():
        raise ValidationError("دلیل ثبت طبقه‌بندی الزامی است.")
    classification = InsuranceClassification(
        code=code, name=name.strip(), created_by=actor
    )
    classification.save()
    record_audit_event(
        action=AuditAction.PLATFORM_POLICY_CREATED,
        entity_type="organizations.InsuranceClassification",
        entity_id=classification.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "after": {"code": classification.code, "name": classification.name},
            "reason": reason.strip(),
        },
    )
    return classification


@transaction.atomic
def set_insurance_classification_active(
    *,
    actor: User,
    classification: InsuranceClassification,
    is_active: bool,
    reason: str,
) -> InsuranceClassification:
    _require_platform_admin(actor)
    if not reason.strip() or type(is_active) is not bool:
        raise ValidationError("وضعیت و دلیل معتبر الزامی است.")
    locked = InsuranceClassification.objects.select_for_update().get(
        pk=classification.pk
    )
    before = locked.is_active
    locked.is_active = is_active
    locked.save(update_fields=["is_active", "updated_at"])
    record_audit_event(
        action=AuditAction.PLATFORM_POLICY_VERSION_UPDATED,
        entity_type="organizations.InsuranceClassification",
        entity_id=locked.pk,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "before": {"is_active": before},
            "after": {"is_active": is_active},
            "reason": reason.strip(),
        },
    )
    return locked


def available_insurance_classifications(
    *, on_date: date
) -> QuerySet[InsuranceClassification]:
    """Only classifications covered by approved effective national rules are selectable."""
    statuses = [PolicyVersionStatus.PUBLISHED]
    if on_date < timezone.localdate():
        statuses.append(PolicyVersionStatus.RETIRED)
    versions = PlatformPolicyVersion.objects.filter(
        policy__code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
        policy__is_active=True,
        policy__tenant_selectable=False,
        policy__sensitivity="regulatory",
        status__in=statuses,
        effective_from__lte=on_date,
        source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
        source_links__isnull=False,
        review_evidence__disposition=PolicyReviewDisposition.ACCEPTED,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=on_date))
    return InsuranceClassification.objects.filter(
        is_active=True, pk__in=versions.values("insurance_classification_id")
    )
