"""Transactional P9-S12–S15 partner qualification services."""

from __future__ import annotations

import hashlib
import json
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.models import DocumentVersion
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.parties.models import BusinessParty
from apps.partner_qualification.models import (
    AppealStatus,
    EvaluationStatus,
    PartnerCategoryApproval,
    PartnerEligibilityProposal,
    PartnerEvaluation,
    PartnerEvaluationAppeal,
    PartnerEvidence,
    PartnerLifecycleEvent,
    PartnerProfile,
    PartnerQualification,
    QualificationRequirement,
    QualificationStatus,
)
from apps.projects.models import Project, ProjectSite


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _permission(
    *,
    organization: Organization,
    actor: User,
    permission: str,
    project: Project | None = None,
    site: ProjectSite | None = None,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        site=site,
        allow_site_parent=True,
        message="اجازه انجام عملیات صلاحیت و عملکرد همکار را ندارید.",
    )


def _audit(
    action: str, record: Any, actor: User, metadata: dict[str, Any] | None = None
) -> None:
    record_audit_event(
        action=action,
        entity_type=record._meta.label_lower,
        entity_id=str(record.pk),
        organization=record.organization,
        actor=actor,
        metadata=metadata or {},
    )


@transaction.atomic
def create_profile(
    *, organization: Organization, actor: User, party: BusinessParty
) -> PartnerProfile:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTNER_PROFILE_MANAGE,
    )
    if party.organization_id != organization.pk or party.archived_at:
        raise PermissionDenied("طرف تجاری فعال متعلق به سازمان نیست.")
    profile, _ = PartnerProfile.objects.get_or_create(
        organization=organization, party=party, defaults={"created_by": actor}
    )
    _audit(AuditAction.PARTNER_PROFILE_CREATED, profile, actor)
    return profile


@transaction.atomic
def publish_requirement(
    *,
    organization: Organization,
    actor: User,
    code: str,
    title: str,
    category_code: str,
    source_reference: str,
    source_version: str,
    evidence_required: bool = True,
) -> QualificationRequirement:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTNER_REQUIREMENTS_MANAGE,
    )
    if not source_reference.strip() or not source_version.strip():
        raise ValidationError("مرجع و نسخه الزام منبع‌دار الزامی است.")
    normalized = code.strip().upper()
    version = (
        QualificationRequirement.objects.select_for_update()
        .filter(organization=organization, code=normalized)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    payload = {
        "code": normalized,
        "title": title,
        "category": category_code,
        "source": source_reference,
        "version": source_version,
        "evidence_required": evidence_required,
    }
    record = QualificationRequirement(
        organization=organization,
        code=normalized,
        version=version,
        title=title,
        category_code=category_code,
        source_reference=source_reference,
        source_version=source_version,
        evidence_required=evidence_required,
        published_by=actor,
        canonical_hash=_hash(payload),
    )
    record.save()
    _audit(
        AuditAction.PARTNER_REQUIREMENT_PUBLISHED, record, actor, {"version": version}
    )
    return record


@transaction.atomic
def create_qualification(
    *,
    organization: Organization,
    actor: User,
    profile: PartnerProfile,
    requirement: QualificationRequirement,
    reference_number: str,
    valid_from: Any = None,
    valid_until: Any = None,
    replaces: PartnerQualification | None = None,
    operation_key: uuid.UUID | None = None,
) -> PartnerQualification:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTNER_QUALIFICATIONS_PREPARE,
    )
    key = operation_key or uuid.uuid4()
    existing = PartnerQualification.objects.filter(
        organization=organization, submitted_by=actor, operation_key=key
    ).first()
    if existing:
        return existing
    record = PartnerQualification(
        organization=organization,
        profile=profile,
        requirement=requirement,
        reference_number=reference_number,
        valid_from=valid_from,
        valid_until=valid_until,
        replaces=replaces,
        submitted_by=actor,
        operation_key=key,
    )
    record.save()
    _audit(AuditAction.PARTNER_QUALIFICATION_CREATED, record, actor)
    return record


def _qualification_permission(status: str) -> str:
    if status == QualificationStatus.SUBMITTED:
        return BusinessPermissionCode.PARTNER_QUALIFICATIONS_SUBMIT
    if status in {
        QualificationStatus.UNDER_REVIEW,
        QualificationStatus.APPROVED,
        QualificationStatus.RETURNED,
        QualificationStatus.REJECTED,
    }:
        return BusinessPermissionCode.PARTNER_QUALIFICATIONS_REVIEW
    return BusinessPermissionCode.PARTNER_QUALIFICATIONS_CONTROL


@transaction.atomic
def transition_qualification(
    *,
    organization: Organization,
    actor: User,
    qualification_id: str,
    expected_status: str,
    to_status: str,
    reason: str,
    operation_key: uuid.UUID,
) -> PartnerQualification:
    record = PartnerQualification.objects.select_for_update().get(
        pk=qualification_id, organization=organization
    )
    payload_hash = _hash({"to": to_status, "reason": reason})
    event = PartnerLifecycleEvent.objects.filter(
        organization=organization,
        actor=actor,
        entity_type="partner_qualification",
        operation_key=operation_key,
    ).first()
    if event:
        if event.payload_hash != payload_hash:
            raise ValidationError("کلید عملیات با محتوای متفاوت استفاده شده است.")
        return record
    if record.status != expected_status:
        raise ValidationError("وضعیت صلاحیت تغییر کرده است.")
    allowed = {
        QualificationStatus.DRAFT: {
            QualificationStatus.SUBMITTED,
            QualificationStatus.WITHDRAWN,
        },
        QualificationStatus.SUBMITTED: {
            QualificationStatus.UNDER_REVIEW,
            QualificationStatus.WITHDRAWN,
        },
        QualificationStatus.UNDER_REVIEW: {
            QualificationStatus.APPROVED,
            QualificationStatus.RETURNED,
            QualificationStatus.REJECTED,
        },
        QualificationStatus.APPROVED: {
            QualificationStatus.SUSPENDED,
            QualificationStatus.SUPERSEDED,
        },
        QualificationStatus.RETURNED: {
            QualificationStatus.SUBMITTED,
            QualificationStatus.WITHDRAWN,
        },
        QualificationStatus.SUSPENDED: {QualificationStatus.SUPERSEDED},
    }
    if to_status not in allowed.get(record.status, set()):
        raise ValidationError("گذار صلاحیت مجاز نیست.")
    _permission(
        organization=organization,
        actor=actor,
        permission=_qualification_permission(to_status),
    )
    if to_status == QualificationStatus.APPROVED:
        if record.submitted_by_id == actor.pk:
            raise PermissionDenied("ارسال‌کننده نمی‌تواند صلاحیت خود را تأیید کند.")
        if record.requirement.evidence_required and not record.evidence.exists():
            raise ValidationError("الزام بدون شواهد نسخه‌پین‌شده تأیید نمی‌شود.")
        record.reviewed_by = actor
    record.status, record.reason = to_status, reason
    record._service_transition = True
    try:
        record.save()
    finally:
        del record._service_transition
    PartnerLifecycleEvent.objects.create(
        organization=organization,
        entity_type="partner_qualification",
        entity_id=record.pk,
        from_status=expected_status,
        to_status=to_status,
        reason=reason,
        actor=actor,
        operation_key=operation_key,
        payload_hash=payload_hash,
    )
    _audit(
        AuditAction.PARTNER_QUALIFICATION_TRANSITIONED, record, actor, {"to": to_status}
    )
    return record


@transaction.atomic
def link_evidence(
    *,
    organization: Organization,
    actor: User,
    qualification: PartnerQualification,
    document_version: DocumentVersion,
) -> PartnerEvidence:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTNER_EVIDENCE_LINK,
    )
    if (
        qualification.organization_id != organization.pk
        or document_version.organization_id != organization.pk
    ):
        raise PermissionDenied("شواهد متعلق به سازمان نیست.")
    evidence, _ = PartnerEvidence.objects.get_or_create(
        organization=organization,
        qualification=qualification,
        document=document_version.document,
        document_version=document_version,
        defaults={"sha256": document_version.sha256, "created_by": actor},
    )
    _audit(AuditAction.PARTNER_EVIDENCE_LINKED, evidence, actor)
    return evidence


@transaction.atomic
def decide_category(
    *,
    organization: Organization,
    actor: User,
    profile: PartnerProfile,
    category_code: str,
    requirements: list[QualificationRequirement],
    reason: str,
) -> PartnerCategoryApproval:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTNER_CATEGORY_DECIDE,
    )
    required = [
        item
        for item in requirements
        if item.organization_id == organization.pk
        and item.category_code == category_code
    ]
    eligible = bool(required) and all(
        PartnerQualification.objects.filter(
            organization=organization,
            profile=profile,
            requirement=item,
            status=QualificationStatus.APPROVED,
        )
        .exclude(valid_until__lt=timezone.localdate())
        .exists()
        for item in required
    )
    record, _ = PartnerCategoryApproval.objects.select_for_update().get_or_create(
        organization=organization, profile=profile, category_code=category_code
    )
    record.requirements_snapshot = [
        {"id": str(item.pk), "version": item.version, "hash": item.canonical_hash}
        for item in required
    ]
    record.status = "eligible" if eligible else "not_eligible"
    record.decided_by, record.decision_reason = actor, reason
    record.save()
    _audit(AuditAction.PARTNER_CATEGORY_DECIDED, record, actor, {"eligible": eligible})
    return record


def calculate_score(
    criteria: list[dict[str, Any]], scores: dict[str, Any]
) -> tuple[Decimal, str]:
    if not criteria:
        raise ValidationError("معیار نسخه‌پین‌شده الزامی است.")
    total_weight = sum(Decimal(str(item.get("weight", 0))) for item in criteria)
    if total_weight != Decimal(100):
        raise ValidationError("جمع وزن معیارها باید ۱۰۰ باشد.")
    weighted = Decimal(0)
    for item in criteria:
        key = str(item["code"])
        value = Decimal(str(scores[key]))
        if not Decimal(0) <= value <= Decimal(100):
            raise ValidationError("امتیاز هر معیار باید بین صفر و صد باشد.")
        weighted += value * Decimal(str(item["weight"])) / Decimal(100)
    result = weighted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return result, _hash({"criteria": criteria, "scores": scores, "score": str(result)})


@transaction.atomic
def create_evaluation(
    *,
    organization: Organization,
    actor: User,
    profile: PartnerProfile,
    project: Project,
    site: ProjectSite | None,
    period_start: Any,
    period_end: Any,
    criteria: list[dict[str, Any]],
    scores: dict[str, Any],
    replaces: PartnerEvaluation | None = None,
    operation_key: uuid.UUID | None = None,
) -> PartnerEvaluation:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTNER_EVALUATIONS_PREPARE,
        project=project,
        site=site,
    )
    score, explanation_hash = calculate_score(criteria, scores)
    record = PartnerEvaluation(
        organization=organization,
        profile=profile,
        project=project,
        site=site,
        period_start=period_start,
        period_end=period_end,
        criteria_snapshot=criteria,
        scores=scores,
        total_score=score,
        explanation_hash=explanation_hash,
        authored_by=actor,
        replaces=replaces,
        operation_key=operation_key or uuid.uuid4(),
    )
    record.save()
    _audit(AuditAction.PARTNER_EVALUATION_CREATED, record, actor, {"score": str(score)})
    return record


@transaction.atomic
def transition_evaluation(
    *,
    organization: Organization,
    actor: User,
    evaluation_id: str,
    expected_status: str,
    to_status: str,
    reason: str,
    operation_key: uuid.UUID,
) -> PartnerEvaluation:
    record = PartnerEvaluation.objects.select_for_update().get(
        pk=evaluation_id, organization=organization
    )
    if record.status != expected_status:
        raise ValidationError("وضعیت ارزیابی تغییر کرده است.")
    allowed = {
        EvaluationStatus.DRAFT: {
            EvaluationStatus.SUBMITTED,
            EvaluationStatus.WITHDRAWN,
        },
        EvaluationStatus.SUBMITTED: {
            EvaluationStatus.UNDER_REVIEW,
            EvaluationStatus.WITHDRAWN,
        },
        EvaluationStatus.UNDER_REVIEW: {
            EvaluationStatus.PUBLISHED,
            EvaluationStatus.RETURNED,
        },
        EvaluationStatus.RETURNED: {
            EvaluationStatus.SUBMITTED,
            EvaluationStatus.WITHDRAWN,
        },
        EvaluationStatus.PUBLISHED: {EvaluationStatus.SUPERSEDED},
    }
    if to_status not in allowed.get(record.status, set()):
        raise ValidationError("گذار ارزیابی مجاز نیست.")
    permission = (
        BusinessPermissionCode.PARTNER_EVALUATIONS_PUBLISH
        if to_status == EvaluationStatus.PUBLISHED
        else BusinessPermissionCode.PARTNER_EVALUATIONS_SUBMIT
    )
    _permission(
        organization=organization,
        actor=actor,
        permission=permission,
        project=record.project,
        site=record.site,
    )
    if to_status == EvaluationStatus.PUBLISHED:
        if record.authored_by_id == actor.pk:
            raise PermissionDenied("نویسنده نمی‌تواند ارزیابی خود را منتشر کند.")
        score, explanation_hash = calculate_score(
            record.criteria_snapshot, record.scores
        )
        if score != record.total_score or explanation_hash != record.explanation_hash:
            raise ValidationError("محاسبه امتیاز قابل بازتولید نیست.")
        record.published_by = actor
    record.status = to_status
    record._service_transition = True
    try:
        record.save()
    finally:
        del record._service_transition
    PartnerLifecycleEvent.objects.create(
        organization=organization,
        entity_type="partner_evaluation",
        entity_id=record.pk,
        from_status=expected_status,
        to_status=to_status,
        reason=reason,
        actor=actor,
        operation_key=operation_key,
        payload_hash=_hash({"to": to_status, "reason": reason}),
    )
    _audit(
        AuditAction.PARTNER_EVALUATION_TRANSITIONED, record, actor, {"to": to_status}
    )
    return record


@transaction.atomic
def raise_appeal(
    *,
    organization: Organization,
    actor: User,
    evaluation: PartnerEvaluation,
    reason: str,
) -> PartnerEvaluationAppeal:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTNER_EVALUATIONS_APPEAL,
        project=evaluation.project,
        site=evaluation.site,
    )
    if evaluation.status != EvaluationStatus.PUBLISHED:
        raise ValidationError("اعتراض فقط برای ارزیابی منتشرشده مجاز است.")
    appeal = PartnerEvaluationAppeal.objects.create(
        organization=organization, evaluation=evaluation, reason=reason, raised_by=actor
    )
    _audit(AuditAction.PARTNER_EVALUATION_APPEALED, appeal, actor)
    return appeal


@transaction.atomic
def decide_appeal(
    *, organization: Organization, actor: User, appeal_id: str, status: str, reason: str
) -> PartnerEvaluationAppeal:
    appeal = (
        PartnerEvaluationAppeal.objects.select_for_update()
        .select_related("evaluation")
        .get(pk=appeal_id, organization=organization)
    )
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTNER_EVALUATIONS_APPEAL,
        project=appeal.evaluation.project,
        site=appeal.evaluation.site,
    )
    if (
        appeal.status != AppealStatus.OPEN
        or status not in {AppealStatus.UPHELD, AppealStatus.DISMISSED}
        or appeal.evaluation.authored_by_id == actor.pk
    ):
        raise PermissionDenied("تصمیم اعتراض مجاز نیست.")
    appeal.status, appeal.decided_by, appeal.decision_reason = status, actor, reason
    appeal.save()
    _audit(
        AuditAction.PARTNER_EVALUATION_APPEAL_DECIDED, appeal, actor, {"status": status}
    )
    return appeal


@transaction.atomic
def create_proposal(
    *,
    organization: Organization,
    actor: User,
    profile: PartnerProfile,
    target_domain: str,
    source_hash: str,
    payload: dict[str, Any],
    operation_key: uuid.UUID,
) -> PartnerEligibilityProposal:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.PARTNER_PROPOSALS_CREATE,
    )
    proposal, created = PartnerEligibilityProposal.objects.get_or_create(
        organization=organization,
        created_by=actor,
        operation_key=operation_key,
        defaults={
            "profile": profile,
            "target_domain": target_domain,
            "source_hash": source_hash,
            "payload": payload,
        },
    )
    if not created and (
        proposal.source_hash != source_hash or proposal.target_domain != target_domain
    ):
        raise ValidationError("کلید پیشنهاد با محتوای متفاوت استفاده شده است.")
    _audit(AuditAction.PARTNER_PROPOSAL_CREATED, proposal, actor)
    return proposal


def scoped_evaluations(*, organization: Organization, actor: User):
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PARTNER_VIEW,
        message="اجازه مشاهده صلاحیت و عملکرد همکاران را ندارید.",
    )
    return scope_queryset(
        PartnerEvaluation.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )
