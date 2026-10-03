from __future__ import annotations

from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import (
    Contract,
    ContractDirection,
    ContractStatus,
    ContractTermVersion,
    ContractTermVersionStatus,
    ContractType,
    RetentionReleaseRequirement,
)
from apps.documents.models import DocumentVersion
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import (
    SUPPORTED_BASE_CURRENCY,
    BusinessPermissionCode,
    Organization,
    OrganizationSettings,
)
from apps.parties.models import PartyIdentitySnapshot

from .models import (
    AssuranceRevisionAction,
    ComplianceEvidenceKind,
    ComplianceEvidenceStatus,
    ContractComplianceEvidence,
    ContractGuarantee,
    EvidenceExpiryKind,
    GuaranteeStatus,
    PayableCertificateAdjustment,
    PayableCertificateAdjustmentType,
    PayableCertificateStatus,
    RetentionRelease,
    RetentionReleaseCorrectionKind,
    RetentionReleaseStatus,
)


def _require(
    *,
    actor: User,
    organization: Organization,
    permission: BusinessPermissionCode,
    project: object | None,
):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        message="اجازه انجام عملیات کنترل قراردادی را ندارید.",
    )


def _money(value: Decimal | str | int, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, (bool, float)):
        raise ValidationError("مبلغ باید با Decimal وارد شود.")
    try:
        parsed = Decimal(value)
    except Exception as exc:
        raise ValidationError("مبلغ معتبر نیست.") from exc
    if not parsed.is_finite() or parsed != parsed.quantize(Decimal("0.0001")):
        raise ValidationError("دقت مبلغ معتبر نیست.")
    if parsed < 0 or (parsed == 0 and not allow_zero):
        raise ValidationError("مبلغ باید مثبت باشد.")
    return parsed


def _locked_contract(
    *, organization: Organization, contract: Contract, require_active: bool = True
) -> Contract:
    try:
        locked = (
            Contract.objects.select_for_update(of=("self",))
            .select_related("project", "party")
            .get(pk=contract.pk, organization=organization, deleted_at__isnull=True)
        )
    except Contract.DoesNotExist as exc:
        raise PermissionDenied("قرارداد متعلق به این سازمان نیست.") from exc
    if locked.party_id is None:
        raise ValidationError("قرارداد باید به طرف تجاری مرجع متصل باشد.")
    if require_active and locked.status != ContractStatus.ACTIVE:
        raise ValidationError("عملیات جدید فقط برای قرارداد فعال مجاز است.")
    return locked


def _identity_snapshot(contract: Contract) -> PartyIdentitySnapshot:
    snapshot = contract.party.identity_snapshots.order_by("-sequence").first()
    if snapshot is None:
        raise ValidationError("طرف قرارداد تصویر هویت قابل استناد ندارد.")
    return snapshot


def _evidence_version(
    *, organization: Organization, document_version: DocumentVersion
) -> DocumentVersion:
    try:
        version = (
            DocumentVersion.objects.select_related("document")
            .prefetch_related("processing_assessments")
            .get(pk=document_version.pk, organization=organization)
        )
    except DocumentVersion.DoesNotExist as exc:
        raise PermissionDenied("نسخه سند متعلق به این سازمان نیست.") from exc
    if not version.is_available:
        raise ValidationError("نسخه سند هنوز برای استفاده ایمن در دسترس نیست.")
    return version


def _currency(organization: Organization) -> str:
    settings, _ = OrganizationSettings.objects.get_or_create(
        organization=organization, defaults={"currency": SUPPORTED_BASE_CURRENCY}
    )
    return settings.currency


def organization_localdate(organization: Organization) -> date:
    settings, _ = OrganizationSettings.objects.get_or_create(
        organization=organization, defaults={"currency": SUPPORTED_BASE_CURRENCY}
    )
    return timezone.localdate(timezone=ZoneInfo(settings.timezone))


def get_guarantees(
    *, actor: User, organization: Organization
) -> QuerySet[ContractGuarantee]:
    membership = _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.GUARANTEES_VIEW,
        project=None,
    )
    return scope_queryset(
        ContractGuarantee.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "contract", "party_identity_snapshot")


def get_compliance_evidence(
    *, actor: User, organization: Organization
) -> QuerySet[ContractComplianceEvidence]:
    membership = _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.COMPLIANCE_EVIDENCE_VIEW,
        project=None,
    )
    return scope_queryset(
        ContractComplianceEvidence.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "contract", "party_identity_snapshot")


def get_retention_releases(
    *, actor: User, organization: Organization
) -> QuerySet[RetentionRelease]:
    membership = _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.RETENTION_RELEASES_VIEW,
        project=None,
    )
    return scope_queryset(
        RetentionRelease.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "contract", "contract_term_version")


def commercial_exposure(
    *, actor: User, organization: Organization, as_of: date | None = None
) -> dict[str, object]:
    as_of = as_of or organization_localdate(organization)
    guarantees = get_guarantees(actor=actor, organization=organization)
    active = guarantees.filter(
        status=GuaranteeStatus.ACTIVE, effective_from__lte=as_of
    ).filter(Q(expiry_kind=EvidenceExpiryKind.OPEN_ENDED) | Q(expires_on__gte=as_of))
    grouped = list(
        active.values("currency_code", "exposure_side", "guarantee_type")
        .annotate(amount=Sum("amount"))
        .order_by("currency_code", "exposure_side", "guarantee_type")
    )
    return {
        "as_of": as_of,
        "groups": grouped,
        "dated_active": active.filter(expiry_kind=EvidenceExpiryKind.DATED).order_by(
            "expires_on"
        ),
        "overdue_expiry": guarantees.filter(
            status=GuaranteeStatus.ACTIVE,
            expiry_kind=EvidenceExpiryKind.DATED,
            expires_on__lt=as_of,
        ).order_by("expires_on"),
    }


@transaction.atomic
def create_guarantee(
    *,
    organization: Organization,
    actor: User,
    contract: Contract,
    guarantee_type: str,
    exposure_side: str,
    instrument_reference: str,
    issuer_name: str,
    amount: Decimal,
    issued_on: date,
    effective_from: date,
    expiry_kind: str,
    expires_on: date | None,
    evidence_document_version: DocumentVersion,
    reason: str,
) -> ContractGuarantee:
    locked_contract = _locked_contract(organization=organization, contract=contract)
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.GUARANTEES_MANAGE,
        project=locked_contract.project,
    )
    if not reason.strip():
        raise ValidationError("دلیل ثبت ضمانت‌نامه الزامی است.")
    guarantee = ContractGuarantee(
        organization=organization,
        project=locked_contract.project,
        contract=locked_contract,
        party_identity_snapshot=_identity_snapshot(locked_contract),
        revision_reason=reason.strip(),
        guarantee_type=guarantee_type,
        exposure_side=exposure_side,
        instrument_reference=instrument_reference,
        issuer_name=issuer_name,
        currency_code=_currency(organization),
        amount=_money(amount),
        issued_on=issued_on,
        effective_from=effective_from,
        expiry_kind=expiry_kind,
        expires_on=expires_on,
        evidence_document_version=_evidence_version(
            organization=organization, document_version=evidence_document_version
        ),
        created_by=actor,
        updated_by=actor,
    )
    guarantee.save()
    record_audit_event(
        action=AuditAction.GUARANTEE_CREATED,
        entity_type="billing.ContractGuarantee",
        entity_id=guarantee.pk,
        organization=organization,
        actor=actor,
        metadata={
            "contract_id": str(locked_contract.pk),
            "series_id": str(guarantee.series_id),
            "version": guarantee.version,
            "revision_action": guarantee.revision_action,
        },
    )
    return guarantee


@transaction.atomic
def create_guarantee_revision(
    *,
    organization: Organization,
    actor: User,
    guarantee: ContractGuarantee,
    revision_action: str,
    evidence_document_version: DocumentVersion,
    reason: str,
    amount: Decimal | None = None,
    instrument_reference: str | None = None,
    issuer_name: str | None = None,
    issued_on: date | None = None,
    effective_from: date | None = None,
    expiry_kind: str | None = None,
    expires_on: date | None = None,
) -> ContractGuarantee:
    if revision_action not in {
        AssuranceRevisionAction.CORRECTION,
        AssuranceRevisionAction.RENEWAL,
        AssuranceRevisionAction.RELEASE,
    }:
        raise ValidationError("نوع نسخه ضمانت‌نامه معتبر نیست.")
    try:
        predecessor = (
            ContractGuarantee.objects.select_for_update(of=("self",))
            .select_related(
                "contract__project", "contract__party", "party_identity_snapshot"
            )
            .get(pk=guarantee.pk, organization=organization)
        )
    except ContractGuarantee.DoesNotExist as exc:
        raise PermissionDenied("ضمانت‌نامه متعلق به این سازمان نیست.") from exc
    locked_contract = _locked_contract(
        organization=organization,
        contract=predecessor.contract,
        require_active=revision_action != AssuranceRevisionAction.RELEASE,
    )
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.GUARANTEES_MANAGE,
        project=locked_contract.project,
    )
    if not reason.strip():
        raise ValidationError("دلیل نسخه ضمانت‌نامه الزامی است.")
    allowed = {GuaranteeStatus.ACTIVE}
    if revision_action == AssuranceRevisionAction.RENEWAL:
        allowed.add(GuaranteeStatus.EXPIRED)
    if predecessor.status not in allowed:
        raise ValidationError(
            "نسخه ضمانت‌نامه در وضعیت قابل اصلاح، تمدید یا آزادسازی نیست."
        )
    series = ContractGuarantee.objects.select_for_update(of=("self",)).filter(
        organization=organization, series_id=predecessor.series_id
    )
    if series.filter(
        status__in=(GuaranteeStatus.DRAFT, GuaranteeStatus.SUBMITTED)
    ).exists():
        raise ValidationError("برای این ضمانت‌نامه نسخه در جریان وجود دارد.")
    next_version = max(series.values_list("version", flat=True), default=0) + 1
    is_release = revision_action == AssuranceRevisionAction.RELEASE
    revised = ContractGuarantee(
        organization=organization,
        project=predecessor.project,
        contract=predecessor.contract,
        party_identity_snapshot=predecessor.party_identity_snapshot,
        series_id=predecessor.series_id,
        version=next_version,
        revision_action=revision_action,
        predecessor=predecessor,
        revision_reason=reason.strip(),
        guarantee_type=predecessor.guarantee_type,
        exposure_side=predecessor.exposure_side,
        instrument_reference=instrument_reference or predecessor.instrument_reference,
        issuer_name=issuer_name or predecessor.issuer_name,
        currency_code=predecessor.currency_code,
        amount=(
            Decimal(0)
            if is_release
            else _money(predecessor.amount if amount is None else amount)
        ),
        issued_on=issued_on or predecessor.issued_on,
        effective_from=effective_from or predecessor.effective_from,
        expiry_kind=expiry_kind or predecessor.expiry_kind,
        expires_on=(
            predecessor.expires_on
            if expiry_kind is None and expires_on is None
            else expires_on
        ),
        evidence_document_version=_evidence_version(
            organization=organization, document_version=evidence_document_version
        ),
        created_by=actor,
        updated_by=actor,
    )
    revised.save()
    record_audit_event(
        action=AuditAction.GUARANTEE_CREATED,
        entity_type="billing.ContractGuarantee",
        entity_id=revised.pk,
        organization=organization,
        actor=actor,
        metadata={
            "predecessor_id": str(predecessor.pk),
            "series_id": str(revised.series_id),
            "version": revised.version,
            "revision_action": revision_action,
        },
    )
    return revised


@transaction.atomic
def expire_due_guarantees(
    *, organization: Organization, actor: User, as_of: date
) -> int:
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.GUARANTEES_MANAGE,
        project=None,
    )
    due = list(
        ContractGuarantee.objects.select_for_update(of=("self",)).filter(
            organization=organization,
            status=GuaranteeStatus.ACTIVE,
            expiry_kind=EvidenceExpiryKind.DATED,
            expires_on__lt=as_of,
        )
    )
    for guarantee in due:
        ContractGuarantee.objects.filter(pk=guarantee.pk).update(
            status=GuaranteeStatus.EXPIRED, updated_by=actor, updated_at=timezone.now()
        )
        record_audit_event(
            action=AuditAction.GUARANTEE_EXPIRED,
            entity_type="billing.ContractGuarantee",
            entity_id=guarantee.pk,
            organization=organization,
            actor=actor,
            metadata={
                "as_of": as_of.isoformat(),
                "expires_on": str(guarantee.expires_on),
            },
        )
    return len(due)


@transaction.atomic
def create_compliance_evidence(
    *,
    organization: Organization,
    actor: User,
    contract: Contract,
    evidence_kind: str,
    reference: str,
    issuing_authority: str,
    effective_from: date,
    expiry_kind: str,
    expires_on: date | None,
    document_version: DocumentVersion,
    reason: str,
) -> ContractComplianceEvidence:
    locked_contract = _locked_contract(organization=organization, contract=contract)
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.COMPLIANCE_EVIDENCE_MANAGE,
        project=locked_contract.project,
    )
    if not reason.strip():
        raise ValidationError("دلیل ثبت شاهد الزامی است.")
    evidence = ContractComplianceEvidence(
        organization=organization,
        project=locked_contract.project,
        contract=locked_contract,
        party_identity_snapshot=_identity_snapshot(locked_contract),
        revision_reason=reason.strip(),
        evidence_kind=evidence_kind,
        reference=reference,
        issuing_authority=issuing_authority,
        effective_from=effective_from,
        expiry_kind=expiry_kind,
        expires_on=expires_on,
        document_version=_evidence_version(
            organization=organization, document_version=document_version
        ),
        created_by=actor,
        updated_by=actor,
    )
    evidence.save()
    record_audit_event(
        action=AuditAction.COMPLIANCE_EVIDENCE_CREATED,
        entity_type="billing.ContractComplianceEvidence",
        entity_id=evidence.pk,
        organization=organization,
        actor=actor,
        metadata={
            "contract_id": str(locked_contract.pk),
            "series_id": str(evidence.series_id),
            "version": evidence.version,
            "evidence_kind": evidence.evidence_kind,
        },
    )
    return evidence


@transaction.atomic
def create_compliance_evidence_revision(
    *,
    organization: Organization,
    actor: User,
    evidence: ContractComplianceEvidence,
    revision_action: str,
    reference: str,
    issuing_authority: str,
    effective_from: date,
    expiry_kind: str,
    expires_on: date | None,
    document_version: DocumentVersion,
    reason: str,
) -> ContractComplianceEvidence:
    if revision_action not in {
        AssuranceRevisionAction.CORRECTION,
        AssuranceRevisionAction.RENEWAL,
    }:
        raise ValidationError("نوع نسخه شاهد معتبر نیست.")
    try:
        predecessor = (
            ContractComplianceEvidence.objects.select_for_update(of=("self",))
            .select_related(
                "contract__project", "contract__party", "party_identity_snapshot"
            )
            .get(pk=evidence.pk, organization=organization)
        )
    except ContractComplianceEvidence.DoesNotExist as exc:
        raise PermissionDenied("شاهد متعلق به این سازمان نیست.") from exc
    locked_contract = _locked_contract(
        organization=organization, contract=predecessor.contract
    )
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.COMPLIANCE_EVIDENCE_MANAGE,
        project=locked_contract.project,
    )
    allowed = {ComplianceEvidenceStatus.APPROVED}
    if revision_action == AssuranceRevisionAction.RENEWAL:
        allowed.add(ComplianceEvidenceStatus.EXPIRED)
    if predecessor.status not in allowed:
        raise ValidationError("شاهد در وضعیت قابل اصلاح یا تمدید نیست.")
    series = ContractComplianceEvidence.objects.select_for_update(of=("self",)).filter(
        organization=organization, series_id=predecessor.series_id
    )
    if series.filter(
        status__in=(ComplianceEvidenceStatus.DRAFT, ComplianceEvidenceStatus.SUBMITTED)
    ).exists():
        raise ValidationError("برای این شاهد نسخه در جریان وجود دارد.")
    revised = ContractComplianceEvidence(
        organization=organization,
        project=predecessor.project,
        contract=predecessor.contract,
        party_identity_snapshot=predecessor.party_identity_snapshot,
        series_id=predecessor.series_id,
        version=max(series.values_list("version", flat=True), default=0) + 1,
        revision_action=revision_action,
        predecessor=predecessor,
        revision_reason=reason.strip(),
        evidence_kind=predecessor.evidence_kind,
        reference=reference,
        issuing_authority=issuing_authority,
        effective_from=effective_from,
        expiry_kind=expiry_kind,
        expires_on=expires_on,
        document_version=_evidence_version(
            organization=organization, document_version=document_version
        ),
        created_by=actor,
        updated_by=actor,
    )
    revised.save()
    record_audit_event(
        action=AuditAction.COMPLIANCE_EVIDENCE_CREATED,
        entity_type="billing.ContractComplianceEvidence",
        entity_id=revised.pk,
        organization=organization,
        actor=actor,
        metadata={
            "predecessor_id": str(predecessor.pk),
            "series_id": str(revised.series_id),
            "version": revised.version,
            "revision_action": revision_action,
        },
    )
    return revised


@transaction.atomic
def expire_due_compliance_evidence(
    *, organization: Organization, actor: User, as_of: date
) -> int:
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.COMPLIANCE_EVIDENCE_MANAGE,
        project=None,
    )
    due = list(
        ContractComplianceEvidence.objects.select_for_update(of=("self",)).filter(
            organization=organization,
            status=ComplianceEvidenceStatus.APPROVED,
            expiry_kind=EvidenceExpiryKind.DATED,
            expires_on__lt=as_of,
        )
    )
    for evidence in due:
        ContractComplianceEvidence.objects.filter(pk=evidence.pk).update(
            status=ComplianceEvidenceStatus.EXPIRED,
            updated_by=actor,
            updated_at=timezone.now(),
        )
        record_audit_event(
            action=AuditAction.COMPLIANCE_EVIDENCE_EXPIRED,
            entity_type="billing.ContractComplianceEvidence",
            entity_id=evidence.pk,
            organization=organization,
            actor=actor,
            metadata={
                "as_of": as_of.isoformat(),
                "expires_on": str(evidence.expires_on),
            },
        )
    return len(due)


def _release_term(
    *, organization: Organization, contract: Contract, release_date: date
) -> ContractTermVersion:
    term = (
        ContractTermVersion.objects.select_for_update(of=("self",))
        .filter(
            organization=organization,
            contract=contract,
            status__in=(
                ContractTermVersionStatus.APPROVED,
                ContractTermVersionStatus.SUPERSEDED,
            ),
            effective_from__lte=release_date,
        )
        .order_by("-effective_from", "-version")
        .first()
    )
    if term is None:
        raise ValidationError("نسخه شرایط تأییدشده و مؤثر برای آزادسازی یافت نشد.")
    if (
        term.retention_release_requirement == RetentionReleaseRequirement.UNCONFIGURED
        or term.retention_release_cap <= 0
    ):
        raise ValidationError(
            "اختیار صریح آزادسازی در شرایط مصوب قرارداد ثبت نشده است."
        )
    return term


def _retention_capacity(
    *,
    organization: Organization,
    contract: Contract,
    term: ContractTermVersion,
    exclude_release: RetentionRelease | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    retained = -(
        PayableCertificateAdjustment.objects.filter(
            certificate__organization=organization,
            certificate__contract=contract,
            certificate__status=PayableCertificateStatus.APPROVED,
            adjustment_type=PayableCertificateAdjustmentType.RETENTION,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal(0)
    )
    releases = RetentionRelease.objects.select_for_update(of=("self",)).filter(
        organization=organization,
        contract=contract,
        status=RetentionReleaseStatus.APPROVED,
    )
    if exclude_release is not None:
        releases = releases.exclude(pk=exclude_release.pk)
    prior = releases.aggregate(total=Sum("amount"))["total"] or Decimal(0)
    available = min(
        max(retained - prior, Decimal(0)),
        max(term.retention_release_cap - prior, Decimal(0)),
    )
    return retained, prior, available


def _valid_clearance(
    *,
    organization: Organization,
    contract: Contract,
    evidence: ContractComplianceEvidence | None,
    release_date: date,
) -> ContractComplianceEvidence:
    if evidence is None:
        raise ValidationError("این شرایط قرارداد به مفاصاحساب تأییدشده نیاز دارد.")
    try:
        locked = ContractComplianceEvidence.objects.select_for_update(of=("self",)).get(
            pk=evidence.pk,
            organization=organization,
            contract=contract,
            evidence_kind=ComplianceEvidenceKind.CLEARANCE,
            status=ComplianceEvidenceStatus.APPROVED,
            effective_from__lte=release_date,
        )
    except ContractComplianceEvidence.DoesNotExist as exc:
        raise ValidationError("مفاصاحساب تأییدشده و مؤثر یافت نشد.") from exc
    if (
        locked.expiry_kind == EvidenceExpiryKind.DATED
        and locked.expires_on < release_date
    ):
        raise ValidationError("مفاصاحساب در تاریخ آزادسازی منقضی است.")
    return locked


@transaction.atomic
def create_retention_release(
    *,
    organization: Organization,
    actor: User,
    contract: Contract,
    release_date: date,
    amount: Decimal,
    evidence_document_version: DocumentVersion,
    clearance_evidence: ContractComplianceEvidence | None = None,
) -> RetentionRelease:
    locked_contract = _locked_contract(organization=organization, contract=contract)
    if (
        locked_contract.direction != ContractDirection.PAYABLE
        or locked_contract.contract_type != ContractType.SUBCONTRACT
    ):
        raise ValidationError(
            "آزادسازی این مرحله فقط برای پیمان جزء پرداختنی مجاز است."
        )
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.RETENTION_RELEASES_CREATE,
        project=locked_contract.project,
    )
    term = _release_term(
        organization=organization, contract=locked_contract, release_date=release_date
    )
    clearance = None
    if (
        term.retention_release_requirement
        == RetentionReleaseRequirement.APPROVED_CLEARANCE
    ):
        clearance = _valid_clearance(
            organization=organization,
            contract=locked_contract,
            evidence=clearance_evidence,
            release_date=release_date,
        )
    retained, prior, available = _retention_capacity(
        organization=organization, contract=locked_contract, term=term
    )
    value = _money(amount)
    if value > available:
        raise ValidationError("مبلغ آزادسازی از مانده مجاز قراردادی بیشتر است.")
    existing = RetentionRelease.objects.select_for_update(of=("self",)).filter(
        organization=organization, contract=locked_contract
    )
    number = max(existing.values_list("release_number", flat=True), default=0) + 1
    release = RetentionRelease(
        organization=organization,
        project=locked_contract.project,
        contract=locked_contract,
        contract_term_version=term,
        party_identity_snapshot=_identity_snapshot(locked_contract),
        release_number=number,
        release_date=release_date,
        currency_code=_currency(organization),
        amount=value,
        retained_total_snapshot=retained,
        prior_release_total_snapshot=prior,
        available_amount_snapshot=available,
        calculation_snapshot={
            "retained_total": str(retained),
            "prior_approved_releases": str(prior),
            "contract_release_cap": str(term.retention_release_cap),
            "available_before_release": str(available),
            "requested_release": str(value),
            "remaining_after_release": str(available - value),
            "term_version_id": str(term.pk),
            "requirement": term.retention_release_requirement,
        },
        evidence_document_version=_evidence_version(
            organization=organization, document_version=evidence_document_version
        ),
        clearance_evidence=clearance,
        created_by=actor,
        updated_by=actor,
    )
    release.save()
    record_audit_event(
        action=AuditAction.RETENTION_RELEASE_CREATED,
        entity_type="billing.RetentionRelease",
        entity_id=release.pk,
        organization=organization,
        actor=actor,
        metadata={
            "contract_id": str(locked_contract.pk),
            "release_number": number,
            "amount": str(value),
        },
    )
    return release


@transaction.atomic
def create_retention_release_correction(
    *,
    organization: Organization,
    actor: User,
    release: RetentionRelease,
    correction_kind: str,
    amount: Decimal,
    evidence_document_version: DocumentVersion,
    reason: str,
    clearance_evidence: ContractComplianceEvidence | None = None,
) -> RetentionRelease:
    if correction_kind not in {
        RetentionReleaseCorrectionKind.REPLACEMENT,
        RetentionReleaseCorrectionKind.CANCELLATION,
    }:
        raise ValidationError("نوع اصلاح آزادسازی معتبر نیست.")
    try:
        target = (
            RetentionRelease.objects.select_for_update(of=("self",))
            .select_related(
                "contract__project", "contract__party", "party_identity_snapshot"
            )
            .get(pk=release.pk, organization=organization)
        )
    except RetentionRelease.DoesNotExist as exc:
        raise PermissionDenied("آزادسازی متعلق به این سازمان نیست.") from exc
    contract = _locked_contract(organization=organization, contract=target.contract)
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.RETENTION_RELEASES_CREATE,
        project=contract.project,
    )
    if target.status != RetentionReleaseStatus.APPROVED:
        raise ValidationError("فقط آزادسازی فعال و تأییدشده قابل اصلاح است.")
    if not reason.strip():
        raise ValidationError("دلیل اصلاح آزادسازی الزامی است.")
    if RetentionRelease.objects.filter(
        corrects=target,
        status__in=(RetentionReleaseStatus.DRAFT, RetentionReleaseStatus.SUBMITTED),
    ).exists():
        raise ValidationError("برای این آزادسازی اصلاح در جریان وجود دارد.")
    term = _release_term(
        organization=organization, contract=contract, release_date=target.release_date
    )
    clearance = None
    if (
        term.retention_release_requirement
        == RetentionReleaseRequirement.APPROVED_CLEARANCE
    ):
        clearance = _valid_clearance(
            organization=organization,
            contract=contract,
            evidence=clearance_evidence or target.clearance_evidence,
            release_date=target.release_date,
        )
    retained, prior, available = _retention_capacity(
        organization=organization,
        contract=contract,
        term=term,
        exclude_release=target,
    )
    is_cancel = correction_kind == RetentionReleaseCorrectionKind.CANCELLATION
    value = _money(amount, allow_zero=is_cancel)
    if is_cancel and value != 0:
        raise ValidationError("سند ابطال آزادسازی باید مبلغ صفر داشته باشد.")
    if not is_cancel and value > available:
        raise ValidationError("مبلغ جایگزین از مانده مجاز قراردادی بیشتر است.")
    revision = (
        max(
            RetentionRelease.objects.filter(
                organization=organization,
                contract=contract,
                release_number=target.release_number,
            ).values_list("revision_number", flat=True),
            default=0,
        )
        + 1
    )
    corrected = RetentionRelease(
        organization=organization,
        project=target.project,
        contract=contract,
        contract_term_version=term,
        party_identity_snapshot=target.party_identity_snapshot,
        release_number=target.release_number,
        revision_number=revision,
        correction_kind=correction_kind,
        corrects=target,
        correction_reason=reason.strip(),
        release_date=target.release_date,
        currency_code=target.currency_code,
        amount=value,
        retained_total_snapshot=retained,
        prior_release_total_snapshot=prior,
        available_amount_snapshot=available,
        calculation_snapshot={
            "retained_total": str(retained),
            "prior_approved_releases_excluding_corrected": str(prior),
            "contract_release_cap": str(term.retention_release_cap),
            "available_before_replacement": str(available),
            "requested_release": str(value),
            "corrects_release_id": str(target.pk),
            "correction_kind": correction_kind,
        },
        evidence_document_version=_evidence_version(
            organization=organization, document_version=evidence_document_version
        ),
        clearance_evidence=clearance,
        created_by=actor,
        updated_by=actor,
    )
    corrected.save()
    record_audit_event(
        action=AuditAction.RETENTION_RELEASE_CREATED,
        entity_type="billing.RetentionRelease",
        entity_id=corrected.pk,
        organization=organization,
        actor=actor,
        metadata={
            "corrects_release_id": str(target.pk),
            "correction_kind": correction_kind,
            "reason": reason.strip(),
        },
    )
    return corrected


@transaction.atomic
def _approve_guarantee_domain(
    *,
    organization: Organization,
    actor: User,
    guarantee: ContractGuarantee,
    reason: str,
) -> ContractGuarantee:
    try:
        locked = ContractGuarantee.objects.select_for_update(of=("self",)).get(
            pk=guarantee.pk, organization=organization
        )
    except ContractGuarantee.DoesNotExist as exc:
        raise PermissionDenied("ضمانت‌نامه متعلق به این سازمان نیست.") from exc
    if locked.status != GuaranteeStatus.SUBMITTED or not reason.strip():
        raise ValidationError("ضمانت‌نامه ارسالی و دلیل تصمیم الزامی است.")
    predecessor = None
    if locked.predecessor_id:
        predecessor = ContractGuarantee.objects.select_for_update(of=("self",)).get(
            pk=locked.predecessor_id, organization=organization
        )
        allowed = {GuaranteeStatus.ACTIVE}
        if locked.revision_action == AssuranceRevisionAction.RENEWAL:
            allowed.add(GuaranteeStatus.EXPIRED)
        if predecessor.status not in allowed:
            raise ValidationError("نسخه پیشین دیگر برای این تصمیم معتبر نیست.")
    now = timezone.now()
    final_status = (
        GuaranteeStatus.RELEASED
        if locked.revision_action == AssuranceRevisionAction.RELEASE
        else GuaranteeStatus.ACTIVE
    )
    if predecessor and predecessor.status == GuaranteeStatus.ACTIVE:
        predecessor_status = (
            GuaranteeStatus.RELEASED
            if locked.revision_action == AssuranceRevisionAction.RELEASE
            else GuaranteeStatus.SUPERSEDED
        )
        ContractGuarantee.objects.filter(pk=predecessor.pk).update(
            status=predecessor_status, updated_by=actor, updated_at=now
        )
        record_audit_event(
            action=(
                AuditAction.GUARANTEE_RELEASED
                if predecessor_status == GuaranteeStatus.RELEASED
                else AuditAction.GUARANTEE_SUPERSEDED
            ),
            entity_type="billing.ContractGuarantee",
            entity_id=predecessor.pk,
            organization=organization,
            actor=actor,
            metadata={"successor_id": str(locked.pk), "reason": reason.strip()},
        )
    locked.status = final_status
    locked.approved_by = actor
    locked.approved_at = now
    locked.decision_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "decision_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=(
            AuditAction.GUARANTEE_RELEASED
            if final_status == GuaranteeStatus.RELEASED
            else AuditAction.GUARANTEE_APPROVED
        ),
        entity_type="billing.ContractGuarantee",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip(), "revision_action": locked.revision_action},
    )
    return locked


@transaction.atomic
def _return_guarantee_domain(
    *,
    organization: Organization,
    actor: User,
    guarantee: ContractGuarantee,
    reason: str,
) -> ContractGuarantee:
    locked = ContractGuarantee.objects.select_for_update(of=("self",)).get(
        pk=guarantee.pk, organization=organization
    )
    if locked.status != GuaranteeStatus.SUBMITTED or not reason.strip():
        raise ValidationError("ضمانت‌نامه ارسالی و دلیل بازگردانی الزامی است.")
    locked.status = GuaranteeStatus.RETURNED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.decision_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "decision_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.GUARANTEE_RETURNED,
        entity_type="billing.ContractGuarantee",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip()},
    )
    return locked


@transaction.atomic
def _approve_compliance_domain(
    *,
    organization: Organization,
    actor: User,
    evidence: ContractComplianceEvidence,
    reason: str,
) -> ContractComplianceEvidence:
    locked = ContractComplianceEvidence.objects.select_for_update(of=("self",)).get(
        pk=evidence.pk, organization=organization
    )
    if locked.status != ComplianceEvidenceStatus.SUBMITTED or not reason.strip():
        raise ValidationError("شاهد ارسالی و دلیل تصمیم الزامی است.")
    predecessor = None
    if locked.predecessor_id:
        predecessor = ContractComplianceEvidence.objects.select_for_update(
            of=("self",)
        ).get(pk=locked.predecessor_id, organization=organization)
        allowed = {ComplianceEvidenceStatus.APPROVED}
        if locked.revision_action == AssuranceRevisionAction.RENEWAL:
            allowed.add(ComplianceEvidenceStatus.EXPIRED)
        if predecessor.status not in allowed:
            raise ValidationError("نسخه پیشین شاهد دیگر برای این تصمیم معتبر نیست.")
    now = timezone.now()
    if predecessor and predecessor.status == ComplianceEvidenceStatus.APPROVED:
        ContractComplianceEvidence.objects.filter(pk=predecessor.pk).update(
            status=ComplianceEvidenceStatus.SUPERSEDED,
            updated_by=actor,
            updated_at=now,
        )
        record_audit_event(
            action=AuditAction.COMPLIANCE_EVIDENCE_SUPERSEDED,
            entity_type="billing.ContractComplianceEvidence",
            entity_id=predecessor.pk,
            organization=organization,
            actor=actor,
            metadata={"successor_id": str(locked.pk)},
        )
    locked.status = ComplianceEvidenceStatus.APPROVED
    locked.approved_by = actor
    locked.approved_at = now
    locked.decision_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "decision_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.COMPLIANCE_EVIDENCE_APPROVED,
        entity_type="billing.ContractComplianceEvidence",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip()},
    )
    return locked


@transaction.atomic
def _return_compliance_domain(
    *,
    organization: Organization,
    actor: User,
    evidence: ContractComplianceEvidence,
    reason: str,
) -> ContractComplianceEvidence:
    locked = ContractComplianceEvidence.objects.select_for_update(of=("self",)).get(
        pk=evidence.pk, organization=organization
    )
    if locked.status != ComplianceEvidenceStatus.SUBMITTED or not reason.strip():
        raise ValidationError("شاهد ارسالی و دلیل بازگردانی الزامی است.")
    locked.status = ComplianceEvidenceStatus.RETURNED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.decision_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "decision_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.COMPLIANCE_EVIDENCE_RETURNED,
        entity_type="billing.ContractComplianceEvidence",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip()},
    )
    return locked


@transaction.atomic
def _approve_retention_release_domain(
    *, organization: Organization, actor: User, release: RetentionRelease, reason: str
) -> RetentionRelease:
    locked = (
        RetentionRelease.objects.select_for_update(of=("self",))
        .select_related("contract", "contract_term_version", "corrects")
        .get(pk=release.pk, organization=organization)
    )
    if locked.status != RetentionReleaseStatus.SUBMITTED or not reason.strip():
        raise ValidationError("آزادسازی ارسالی و دلیل تصمیم الزامی است.")
    contract = Contract.objects.select_for_update(of=("self",)).get(
        pk=locked.contract_id
    )
    target = None
    if locked.corrects_id:
        target = RetentionRelease.objects.select_for_update(of=("self",)).get(
            pk=locked.corrects_id, organization=organization
        )
        if target.status != RetentionReleaseStatus.APPROVED:
            raise ValidationError("آزادسازی مرجع اصلاح دیگر فعال نیست.")
    retained, prior, available = _retention_capacity(
        organization=organization,
        contract=contract,
        term=locked.contract_term_version,
        exclude_release=target,
    )
    if (
        retained != locked.retained_total_snapshot
        or prior != locked.prior_release_total_snapshot
        or available != locked.available_amount_snapshot
    ):
        raise ValidationError("مانده آزادسازی تغییر کرده است؛ نسخه جدید تهیه کنید.")
    if locked.amount > available:
        raise ValidationError("مبلغ آزادسازی از مانده مجاز بیشتر است.")
    now = timezone.now()
    if target:
        target_status = (
            RetentionReleaseStatus.CANCELLED
            if locked.correction_kind == RetentionReleaseCorrectionKind.CANCELLATION
            else RetentionReleaseStatus.SUPERSEDED
        )
        RetentionRelease.objects.filter(pk=target.pk).update(
            status=target_status, updated_by=actor, updated_at=now
        )
        record_audit_event(
            action=(
                AuditAction.RETENTION_RELEASE_CANCELLED
                if target_status == RetentionReleaseStatus.CANCELLED
                else AuditAction.RETENTION_RELEASE_SUPERSEDED
            ),
            entity_type="billing.RetentionRelease",
            entity_id=target.pk,
            organization=organization,
            actor=actor,
            metadata={"replacement_id": str(locked.pk)},
        )
    locked.status = RetentionReleaseStatus.APPROVED
    locked.approved_by = actor
    locked.approved_at = now
    locked.decision_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "decision_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.RETENTION_RELEASE_APPROVED,
        entity_type="billing.RetentionRelease",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip(), "amount": str(locked.amount)},
    )
    return locked


@transaction.atomic
def _return_retention_release_domain(
    *, organization: Organization, actor: User, release: RetentionRelease, reason: str
) -> RetentionRelease:
    locked = RetentionRelease.objects.select_for_update(of=("self",)).get(
        pk=release.pk, organization=organization
    )
    if locked.status != RetentionReleaseStatus.SUBMITTED or not reason.strip():
        raise ValidationError("آزادسازی ارسالی و دلیل بازگردانی الزامی است.")
    locked.status = RetentionReleaseStatus.RETURNED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.decision_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "decision_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.RETENTION_RELEASE_RETURNED,
        entity_type="billing.RetentionRelease",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip()},
    )
    return locked


def submit_guarantee(*, organization, actor, guarantee):
    from .commercial_workflow import submit_commercial_record

    return submit_commercial_record(
        organization=organization, actor=actor, record=guarantee
    )


def decide_guarantee(*, organization, actor, guarantee, approved: bool, reason: str):
    from .commercial_workflow import decide_commercial_record

    return decide_commercial_record(
        organization=organization,
        actor=actor,
        record=guarantee,
        approved=approved,
        reason=reason,
    )


def submit_compliance_evidence(*, organization, actor, evidence):
    from .commercial_workflow import submit_commercial_record

    return submit_commercial_record(
        organization=organization, actor=actor, record=evidence
    )


def decide_compliance_evidence(
    *, organization, actor, evidence, approved: bool, reason: str
):
    from .commercial_workflow import decide_commercial_record

    return decide_commercial_record(
        organization=organization,
        actor=actor,
        record=evidence,
        approved=approved,
        reason=reason,
    )


def submit_retention_release(*, organization, actor, release):
    from .commercial_workflow import submit_commercial_record

    return submit_commercial_record(
        organization=organization, actor=actor, record=release
    )


def decide_retention_release(
    *, organization, actor, release, approved: bool, reason: str
):
    from .commercial_workflow import decide_commercial_record

    return decide_commercial_record(
        organization=organization,
        actor=actor,
        record=release,
        approved=approved,
        reason=reason,
    )
