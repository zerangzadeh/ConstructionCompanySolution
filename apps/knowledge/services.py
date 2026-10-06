"""Transactional commands for P9 knowledge; source facts and DMS bytes stay external."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.models import DocumentConfidentiality, DocumentVersion
from apps.organizations.authorization import (
    is_platform_admin,
    require_business_permission,
)
from apps.organizations.models import BusinessPermissionCode

from .models import (
    CandidateStatus,
    KnowledgeAuthority,
    KnowledgeCandidate,
    KnowledgeCandidateRevision,
    KnowledgePromotion,
    KnowledgePromotionEvent,
    KnowledgePublication,
    KnowledgePublicationEvent,
    KnowledgePublicationVersion,
    KnowledgeRecurrenceEvidence,
    KnowledgeRecurrenceSource,
    KnowledgeReuseEvidence,
    KnowledgeReview,
    KnowledgeScope,
    KnowledgeSensitivity,
    KnowledgeSourcePin,
    PromotionStatus,
    PublicationEventType,
    PublicationStatus,
    RecurrenceStatus,
    ReuseStatus,
    ReuseType,
)


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _allow(*, organization, actor, permission: BusinessPermissionCode) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="مجوز لازم برای عملیات دانش وجود ندارد.",
    )


def _allow_scope(
    *, organization, scope: str, actor, permission: BusinessPermissionCode
) -> None:
    if scope == KnowledgeScope.PLATFORM:
        if not is_platform_admin(actor):
            raise PermissionDenied("فقط Platform Admin مجاز به عملیات دانش پلتفرم است.")
        return
    if organization is None:
        raise ValidationError("سازمان Tenant الزامی است.")
    _allow(organization=organization, actor=actor, permission=permission)


def _audit(
    action: str,
    item,
    actor,
    *,
    organization=None,
    metadata: dict[str, Any] | None = None,
) -> None:
    record_audit_event(
        action=action,
        entity_type=item._meta.label_lower,
        entity_id=str(item.pk),
        organization=organization
        if organization is not None
        else getattr(item, "organization", None),
        actor=actor,
        metadata=metadata or {},
        allow_platform_actor=True,
    )


def _source_registry() -> dict[str, tuple[Any, set[str], str, str]]:
    from apps.compliance.models import (
        CapaAction,
        Inspection,
        InspectionFinding,
        Nonconformance,
    )
    from apps.daily_reports.field_models import FieldObservation
    from apps.partner_qualification.models import PartnerEvaluation
    from apps.support.models import SupportCase

    return {
        "field_observation": (
            FieldObservation,
            {"accepted"},
            "revision",
            BusinessPermissionCode.FIELD_OBSERVATIONS_VIEW,
        ),
        "inspection": (
            Inspection,
            {"passed", "conditional", "failed"},
            "updated_at",
            BusinessPermissionCode.COMPLIANCE_VIEW,
        ),
        "inspection_finding": (
            InspectionFinding,
            {"verified", "closed", "dismissed"},
            "updated_at",
            BusinessPermissionCode.COMPLIANCE_VIEW,
        ),
        "nonconformance": (
            Nonconformance,
            {"verified", "closed"},
            "updated_at",
            BusinessPermissionCode.COMPLIANCE_VIEW,
        ),
        "capa_action": (
            CapaAction,
            {"effective", "closed"},
            "updated_at",
            BusinessPermissionCode.COMPLIANCE_VIEW,
        ),
        "partner_evaluation": (
            PartnerEvaluation,
            {"published"},
            "updated_at",
            BusinessPermissionCode.PARTNER_VIEW,
        ),
        "support_case": (
            SupportCase,
            {"resolved", "closed"},
            "created_at",
            BusinessPermissionCode.SUPPORT_CASE_VIEW,
        ),
    }


def _resolve_source(
    *, organization, actor, source_type: str, source_id: uuid.UUID
) -> tuple[Any, str, str, str]:
    try:
        model, final_statuses, version_attr, permission = _source_registry()[
            source_type
        ]
    except KeyError as exc:
        raise ValidationError("نوع منبع دانش ثبت‌شده معتبر نیست.") from exc
    item = model.objects.filter(pk=source_id, organization=organization).first()
    if item is None:
        raise PermissionDenied("منبع دانش خارج از دامنه Tenant یا ناموجود است.")
    _allow(organization=organization, actor=actor, permission=permission)
    status = getattr(item, "status", "")
    if status not in final_statuses:
        raise ValidationError("منبع باید در وضعیت بازبینی/نهایی واجد شرایط باشد.")
    version = str(getattr(item, version_attr))
    evidence_hash = _hash(
        {"type": source_type, "id": str(item.pk), "version": version, "status": status}
    )
    return item, version, status, evidence_hash


def _resolve_consumer(
    *, organization, actor, consumer_type: str, consumer_id, consumer_version: str
) -> Any:
    try:
        model, _, version_attr, permission = _source_registry()[consumer_type]
    except KeyError as exc:
        raise ValidationError("نوع مصرف‌کننده در کاتالوگ آداپتور ثبت نشده است.") from exc
    _allow(organization=organization, actor=actor, permission=permission)
    item = model.objects.filter(pk=consumer_id, organization=organization).first()
    if item is None:
        raise PermissionDenied("مصرف‌کننده خارج از دامنه Tenant یا ناموجود است.")
    if str(getattr(item, version_attr)) != consumer_version:
        raise ValidationError("نسخه مصرف‌کننده با رکورد جاری منطبق نیست.")
    return item


def _candidate_snapshot(candidate: KnowledgeCandidate) -> dict[str, Any]:
    return {
        "title": candidate.title,
        "body": candidate.body,
        "knowledge_type": candidate.knowledge_type,
        "authority_classification": candidate.authority_classification,
        "sensitivity": candidate.sensitivity,
        "audience": candidate.audience,
        "category_code": candidate.category_code,
        "tags": candidate.tags,
        "scope": candidate.scope,
        "source_organization_id": str(candidate.source_organization_id or ""),
        "corrects_version_id": str(candidate.corrects_version_id or ""),
        "correction_reason": candidate.correction_reason,
    }


def _revalidate_revision_sources(*, organization, actor, revision) -> None:
    pins = revision.source_pins.select_related("document", "document_version")
    if not pins.exists():
        raise ValidationError("نسخه کاندید فاقد منبع پین‌شده است.")
    for pin in pins:
        _, version, status, _ = _resolve_source(
            organization=organization,
            actor=actor,
            source_type=pin.source_type,
            source_id=pin.source_id,
        )
        if version != pin.source_version or status != pin.source_status:
            raise ValidationError("نسخه یا وضعیت منبع از زمان ارسال تغییر کرده است.")
        if pin.document_version_id:
            _allow(
                organization=organization,
                actor=actor,
                permission=BusinessPermissionCode.DOCUMENTS_VIEW,
            )
            if (
                pin.document_version.document_id != pin.document_id
                or pin.document_version.organization_id != organization.pk
                or pin.document_version.sha256 != pin.sha256
            ):
                raise ValidationError("نسخه یا هش سند پین‌شده معتبر نیست.")
            if pin.document.confidentiality != DocumentConfidentiality.INTERNAL:
                _allow(
                    organization=organization,
                    actor=actor,
                    permission=BusinessPermissionCode.KNOWLEDGE_SENSITIVE_PROVENANCE_VIEW,
                )


def get_publication_history(*, organization, actor, version_id):
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_HISTORY_VIEW,
    )
    version = (
        KnowledgePublicationVersion.objects.select_related(
            "publication", "candidate_revision__candidate"
        )
        .prefetch_related(
            "publication__versions__lifecycle_events",
            "candidate_revision__reviews",
            "candidate_revision__source_pins",
        )
        .get(pk=version_id)
    )
    if (
        version.publication.scope == KnowledgeScope.TENANT
        and version.publication.organization_id != organization.pk
    ):
        raise PermissionDenied("تاریخچه انتشار خارج از Tenant است.")
    has_restricted_document = False
    if version.publication.scope == KnowledgeScope.TENANT:
        for pin in version.candidate_revision.source_pins.all():
            try:
                permission = _source_registry()[pin.source_type][3]
            except KeyError as exc:
                raise PermissionDenied("نوع منبع تاریخچه دیگر ثبت‌شده نیست.") from exc
            _allow(organization=organization, actor=actor, permission=permission)
            if pin.document_version_id:
                has_restricted_document = (
                    has_restricted_document
                    or pin.document.confidentiality != DocumentConfidentiality.INTERNAL
                )
                _allow(
                    organization=organization,
                    actor=actor,
                    permission=BusinessPermissionCode.DOCUMENTS_VIEW,
                )
    sensitive = (
        version.metadata.get("sensitivity") == KnowledgeSensitivity.SENSITIVE
        or has_restricted_document
    )
    if sensitive:
        _allow(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.KNOWLEDGE_SENSITIVE_PROVENANCE_VIEW,
        )
        _audit(
            AuditAction.KNOWLEDGE_SENSITIVE_PROVENANCE_VIEWED,
            version,
            actor,
            organization=organization,
        )
    return version


@transaction.atomic
def create_candidate(
    *,
    organization,
    actor,
    title: str,
    body: str,
    knowledge_type: str,
    authority_classification: str,
    audience: str,
    category_code: str,
    tags: list[str] | None = None,
    sensitivity: str = KnowledgeSensitivity.INTERNAL,
    operation_key: uuid.UUID | None = None,
    scope: str = KnowledgeScope.TENANT,
    source_organization=None,
    tenant_disclosure_authorized_by=None,
    corrects_version: KnowledgePublicationVersion | None = None,
    correction_reason: str = "",
) -> KnowledgeCandidate:
    _allow_scope(
        organization=organization,
        scope=scope,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_CANDIDATES_CREATE,
    )
    if (
        authority_classification not in KnowledgeAuthority.values
        or sensitivity not in KnowledgeSensitivity.values
    ):
        raise ValidationError("طبقه‌بندی اختیار یا حساسیت معتبر نیست.")
    if not all(
        (
            title.strip(),
            body.strip(),
            knowledge_type.strip(),
            audience.strip(),
            category_code.strip(),
        )
    ):
        raise ValidationError("عنوان، متن، نوع، مخاطب و دسته‌بندی الزامی است.")
    if scope == KnowledgeScope.PLATFORM and source_organization is not None:
        if tenant_disclosure_authorized_by is None:
            raise ValidationError(
                "ترویج Tenant به Platform به مجوز افشای صریح نیاز دارد."
            )
        _allow(
            organization=source_organization,
            actor=tenant_disclosure_authorized_by,
            permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_PUBLISH,
        )
    if corrects_version is not None:
        if (
            scope != KnowledgeScope.TENANT
            or corrects_version.publication.organization_id != organization.pk
            or corrects_version.status
            not in {PublicationStatus.CURRENT, PublicationStatus.REVIEW_DUE}
            or not correction_reason.strip()
        ):
            raise ValidationError("نسخه و دلیل اصلاح انتشار معتبر نیست.")
        _allow(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_SUPERSEDE,
        )
    key = operation_key or uuid.uuid4()
    payload = {
        "title": title.strip(),
        "body": body.strip(),
        "knowledge_type": knowledge_type,
        "authority": authority_classification,
        "audience": audience,
        "category": category_code,
        "tags": tags or [],
        "sensitivity": sensitivity,
        "scope": scope,
        "corrects_version": str(corrects_version.pk if corrects_version else ""),
        "correction_reason": correction_reason.strip(),
    }
    existing = (
        KnowledgeCandidate.objects.filter(
            organization=organization, created_by=actor, operation_key=key
        ).first()
        if scope == KnowledgeScope.TENANT
        else None
    )
    if existing:
        if existing.content_hash != _hash(payload):
            raise ValidationError("کلید عملیات پیش‌تر با محتوای دیگری استفاده شده است.")
        return existing
    item = KnowledgeCandidate.objects.create(
        organization=organization if scope == KnowledgeScope.TENANT else None,
        scope=scope,
        source_organization=source_organization
        if scope == KnowledgeScope.PLATFORM
        else None,
        title=title.strip(),
        body=body.strip(),
        knowledge_type=knowledge_type.strip(),
        authority_classification=authority_classification,
        sensitivity=sensitivity,
        audience=audience.strip(),
        category_code=category_code.strip(),
        tags=tags or [],
        content_hash=_hash(payload),
        created_by=actor,
        tenant_disclosure_authorized_by=tenant_disclosure_authorized_by
        if scope == KnowledgeScope.PLATFORM
        else None,
        operation_key=key,
        corrects_version=corrects_version,
        correction_reason=correction_reason.strip(),
    )
    _audit(
        AuditAction.KNOWLEDGE_CANDIDATE_CREATED, item, actor, organization=organization
    )
    return item


@transaction.atomic
def create_publication_correction(
    *,
    organization,
    actor,
    version_id,
    title: str,
    body: str,
    reason: str,
    operation_key: uuid.UUID | None = None,
) -> KnowledgeCandidate:
    previous = (
        KnowledgePublicationVersion.objects.select_for_update()
        .select_related("publication")
        .get(pk=version_id)
    )
    if previous.publication.organization_id != organization.pk:
        raise PermissionDenied("نسخه انتشار خارج از Tenant است.")
    metadata = previous.metadata
    return create_candidate(
        organization=organization,
        actor=actor,
        title=title,
        body=body,
        knowledge_type=previous.candidate_revision.snapshot["knowledge_type"],
        authority_classification=metadata["authority"],
        sensitivity=metadata["sensitivity"],
        audience=metadata["audience"],
        category_code=metadata["category"],
        tags=metadata.get("tags", []),
        operation_key=operation_key,
        corrects_version=previous,
        correction_reason=reason,
    )


@transaction.atomic
def submit_candidate(
    *,
    organization,
    actor,
    candidate_id,
    expected_status: str,
    sources: list[dict[str, Any]],
    operation_key: uuid.UUID | None = None,
) -> KnowledgeCandidate:
    candidate = KnowledgeCandidate.objects.select_for_update().get(pk=candidate_id)
    if (
        candidate.scope != KnowledgeScope.TENANT
        or candidate.organization_id != organization.pk
    ):
        raise PermissionDenied("Tenant کاندید نامعتبر است.")
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_CANDIDATES_SUBMIT,
    )
    if candidate.created_by_id != actor.pk:
        raise PermissionDenied("فقط مؤلف می‌تواند نسخه کاندید را ارسال کند.")
    if candidate.status != expected_status or candidate.status not in {
        CandidateStatus.DRAFT,
        CandidateStatus.CHANGES_REQUESTED,
    }:
        raise ValidationError("وضعیت کاندید کهنه یا غیرقابل ارسال است.")
    if not sources:
        raise ValidationError("حداقل یک منبع واجد شرایط الزامی است.")
    revision = KnowledgeCandidateRevision.objects.create(
        candidate=candidate,
        revision=candidate.revision,
        snapshot=_candidate_snapshot(candidate),
        content_hash=candidate.content_hash,
        submitted_by=actor,
    )
    for source in sources:
        source_type, source_id = source["source_type"], source["source_id"]
        item, version, status, _ = _resolve_source(
            organization=organization,
            actor=actor,
            source_type=source_type,
            source_id=source_id,
        )
        document_version = source.get("document_version")
        if document_version is not None:
            if (
                not isinstance(document_version, DocumentVersion)
                or document_version.organization_id != organization.pk
            ):
                raise PermissionDenied("نسخه سند خارج از Tenant است.")
            _allow(
                organization=organization,
                actor=actor,
                permission=BusinessPermissionCode.DOCUMENTS_VIEW,
            )
            if (
                document_version.document.confidentiality
                != DocumentConfidentiality.INTERNAL
            ):
                _allow(
                    organization=organization,
                    actor=actor,
                    permission=BusinessPermissionCode.KNOWLEDGE_SENSITIVE_PROVENANCE_VIEW,
                )
        KnowledgeSourcePin.objects.create(
            candidate_revision=revision,
            source_organization=organization,
            source_type=source_type,
            source_id=item.pk,
            source_version=version,
            source_status=status,
            document=document_version.document if document_version else None,
            document_version=document_version,
            sha256=document_version.sha256 if document_version else "",
            citation_purpose=source.get("citation_purpose", "source evidence")[:160],
        )
    candidate.status = CandidateStatus.SUBMITTED
    candidate.submitted_by = actor
    candidate._knowledge_transition = True
    candidate.save(update_fields=["status", "submitted_by", "updated_at"])
    _audit(
        AuditAction.KNOWLEDGE_CANDIDATE_SUBMITTED,
        candidate,
        actor,
        organization=organization,
        metadata={"revision": candidate.revision},
    )
    return candidate


@transaction.atomic
def review_candidate(
    *,
    organization,
    actor,
    candidate_id,
    expected_status: str,
    outcome: str,
    reason: str = "",
    operation_key: uuid.UUID | None = None,
) -> KnowledgeCandidate:
    candidate = KnowledgeCandidate.objects.select_for_update().get(pk=candidate_id)
    if candidate.organization_id != organization.pk:
        raise PermissionDenied("Tenant کاندید نامعتبر است.")
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_CANDIDATES_REVIEW,
    )
    if candidate.created_by_id == actor.pk:
        raise PermissionDenied("مؤلف نمی‌تواند کاندید خود را بررسی کند.")
    if candidate.status != expected_status or candidate.status not in {
        CandidateStatus.SUBMITTED,
        CandidateStatus.IN_REVIEW,
    }:
        raise ValidationError("وضعیت بررسی کهنه است.")
    target = {
        "changes_requested": CandidateStatus.CHANGES_REQUESTED,
        "recommended": CandidateStatus.RECOMMENDED,
        "rejected": CandidateStatus.REJECTED,
    }.get(outcome)
    if target is None:
        raise ValidationError("نتیجه بررسی معتبر نیست.")
    revision = candidate.revisions.get(revision=candidate.revision)
    _revalidate_revision_sources(
        organization=organization, actor=actor, revision=revision
    )
    key = operation_key or uuid.uuid4()
    existing = KnowledgeReview.objects.filter(
        candidate_revision=revision, reviewer=actor, operation_key=key
    ).first()
    if existing:
        if existing.outcome != outcome or existing.reason != reason:
            raise ValidationError("کلید عملیات بررسی با محتوای دیگری استفاده شده است.")
        return candidate
    KnowledgeReview.objects.create(
        candidate_revision=revision,
        reviewer=actor,
        outcome=outcome,
        reason=reason,
        operation_key=key,
    )
    candidate.status, candidate.reviewed_by = target, actor
    candidate._knowledge_transition = True
    candidate.save(update_fields=["status", "reviewed_by", "updated_at"])
    _audit(
        AuditAction.KNOWLEDGE_CANDIDATE_REVIEWED,
        candidate,
        actor,
        organization=organization,
        metadata={"outcome": outcome},
    )
    return candidate


@transaction.atomic
def approve_candidate(
    *, organization, actor, candidate_id, expected_status: str
) -> KnowledgeCandidate:
    candidate = KnowledgeCandidate.objects.select_for_update().get(pk=candidate_id)
    if candidate.organization_id != organization.pk:
        raise PermissionDenied("Tenant کاندید نامعتبر است.")
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_APPROVE,
    )
    if (
        candidate.created_by_id == actor.pk
        or candidate.status != expected_status
        or candidate.status != CandidateStatus.RECOMMENDED
    ):
        raise PermissionDenied("تأیید مستقل و وضعیت توصیه‌شده الزامی است.")
    revision = candidate.revisions.get(revision=candidate.revision)
    _revalidate_revision_sources(
        organization=organization, actor=actor, revision=revision
    )
    candidate.status, candidate.approved_by = CandidateStatus.APPROVED, actor
    candidate._knowledge_transition = True
    candidate.save(update_fields=["status", "approved_by", "updated_at"])
    _audit(
        AuditAction.KNOWLEDGE_CANDIDATE_APPROVED,
        candidate,
        actor,
        organization=organization,
    )
    return candidate


@transaction.atomic
def publish_candidate(
    *,
    organization,
    actor,
    candidate_id,
    expected_status: str,
    supersedes_id=None,
    operation_key: uuid.UUID | None = None,
) -> KnowledgePublicationVersion:
    candidate = KnowledgeCandidate.objects.select_for_update().get(pk=candidate_id)
    if candidate.organization_id != organization.pk:
        raise PermissionDenied("Tenant کاندید نامعتبر است.")
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_PUBLISH,
    )
    if (
        candidate.status != expected_status
        or candidate.status != CandidateStatus.APPROVED
    ):
        raise ValidationError("کاندید برای انتشار آماده نیست.")
    if candidate.created_by_id == actor.pk:
        raise PermissionDenied("مؤلف نمی‌تواند نسخه خود را منتشر کند.")
    revision = candidate.revisions.get(revision=candidate.revision)
    _revalidate_revision_sources(
        organization=organization, actor=actor, revision=revision
    )
    existing_version = KnowledgePublicationVersion.objects.filter(
        candidate_revision=revision,
        supersedes_id=candidate.corrects_version_id,
    ).first()
    if existing_version:
        return existing_version
    previous = None
    if supersedes_id or candidate.corrects_version_id:
        if str(candidate.corrects_version_id or "") != str(supersedes_id or ""):
            raise ValidationError("جایگزینی فقط از کاندید اصلاحی پیوندخورده مجاز است.")
        _allow(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_SUPERSEDE,
        )
        previous = (
            KnowledgePublicationVersion.objects.select_for_update()
            .select_related("publication")
            .get(pk=supersedes_id)
        )
        if (
            previous.publication.organization_id != organization.pk
            or previous.status
            not in {PublicationStatus.CURRENT, PublicationStatus.REVIEW_DUE}
        ):
            raise ValidationError("نسخه جایگزین‌شونده جاری نیست.")
        publication = previous.publication
        next_version = (
            publication.versions.order_by("-version_number")
            .values_list("version_number", flat=True)
            .first()
            + 1
        )
    else:
        publication = KnowledgePublication.objects.create(
            organization=organization,
            scope=KnowledgeScope.TENANT,
            source_candidate=candidate,
        )
        next_version = 1
    manifest = {
        "candidate_revision": str(revision.pk),
        "snapshot": revision.snapshot,
        "pins": list(
            revision.source_pins.order_by("source_type", "source_id").values(
                "source_type",
                "source_id",
                "source_version",
                "source_status",
                "document_version_id",
                "sha256",
                "citation_purpose",
            )
        ),
        "version": next_version,
    }
    version = KnowledgePublicationVersion.objects.create(
        publication=publication,
        candidate_revision=revision,
        version_number=next_version,
        title=candidate.title,
        body=candidate.body,
        metadata={
            "authority": candidate.authority_classification,
            "sensitivity": candidate.sensitivity,
            "audience": candidate.audience,
            "category": candidate.category_code,
            "tags": candidate.tags,
        },
        manifest_hash=_hash(manifest),
        published_by=actor,
        published_at=timezone.now(),
        supersedes=previous,
    )
    KnowledgePublicationEvent.objects.create(
        publication_version=version,
        event_type=PublicationEventType.PUBLISHED,
        actor=actor,
        reason=candidate.correction_reason,
        related_version=previous,
        operation_key=operation_key or uuid.uuid4(),
    )
    if previous:
        previous.status = PublicationStatus.SUPERSEDED
        previous._knowledge_transition = True
        previous.save(update_fields=["status"])
        KnowledgePublicationEvent.objects.create(
            publication_version=previous,
            event_type=PublicationEventType.SUPERSEDED,
            actor=actor,
            reason=candidate.correction_reason,
            related_version=version,
        )
        _audit(
            AuditAction.KNOWLEDGE_PUBLICATION_SUPERSEDED,
            previous,
            actor,
            organization=organization,
            metadata={"successor_id": str(version.pk)},
        )
    publication.current_version = version
    publication.save(update_fields=["current_version"])
    candidate.status = CandidateStatus.APPROVED
    candidate._knowledge_transition = True
    candidate.save(update_fields=["updated_at"])
    _audit(
        AuditAction.KNOWLEDGE_PUBLICATION_PUBLISHED,
        version,
        actor,
        organization=organization,
    )
    return version


@transaction.atomic
def withdraw_publication(
    *,
    organization,
    actor,
    version_id,
    expected_status: str,
    reason: str,
    operation_key: uuid.UUID | None = None,
) -> KnowledgePublicationVersion:
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_WITHDRAW,
    )
    item = (
        KnowledgePublicationVersion.objects.select_for_update()
        .select_related("publication")
        .get(pk=version_id)
    )
    if item.status == PublicationStatus.WITHDRAWN:
        if item.withdrawal_reason == reason.strip():
            return item
        raise ValidationError("نسخه با دلیل دیگری پس گرفته شده است.")
    if (
        item.publication.organization_id != organization.pk
        or item.status != expected_status
        or item.status not in {PublicationStatus.CURRENT, PublicationStatus.REVIEW_DUE}
        or not reason.strip()
    ):
        raise ValidationError("برداشت نسخه با وضعیت جاری سازگار نیست.")
    item.status, item.withdrawal_reason, item._knowledge_transition = (
        PublicationStatus.WITHDRAWN,
        reason.strip(),
        True,
    )
    item.save(update_fields=["status", "withdrawal_reason"])
    item.publication.current_version = None
    item.publication.save(update_fields=["current_version"])
    KnowledgePublicationEvent.objects.create(
        publication_version=item,
        event_type=PublicationEventType.WITHDRAWN,
        actor=actor,
        reason=reason.strip(),
        operation_key=operation_key or uuid.uuid4(),
    )
    _audit(
        AuditAction.KNOWLEDGE_PUBLICATION_WITHDRAWN,
        item,
        actor,
        organization=organization,
    )
    return item


@transaction.atomic
def record_recurrence(
    *,
    organization,
    actor,
    recurrence_key: str,
    scope_description: str,
    period_start: date,
    period_end: date,
    sources: list[dict[str, Any]],
    operation_key: uuid.UUID | None = None,
    replaces: KnowledgeRecurrenceEvidence | None = None,
    status: str = RecurrenceStatus.VALID,
    correction_reason: str = "",
) -> KnowledgeRecurrenceEvidence:
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_RECURRENCE_RECORD,
    )
    key = operation_key or uuid.uuid4()
    request_hash = _hash(
        {
            "key": recurrence_key.strip(),
            "scope": scope_description,
            "period": [period_start, period_end],
            "sources": sorted(
                (source["source_type"], str(source["source_id"])) for source in sources
            ),
            "status": status,
            "replaces": str(replaces.pk if replaces else ""),
            "correction_reason": correction_reason.strip(),
        }
    )
    existing = KnowledgeRecurrenceEvidence.objects.filter(
        organization=organization, created_by=actor, operation_key=key
    ).first()
    if existing:
        if existing.request_hash != request_hash:
            raise ValidationError("کلید عملیات تکرار با محتوای دیگری استفاده شده است.")
        return existing
    if (
        not recurrence_key.strip()
        or len({(x["source_type"], x["source_id"]) for x in sources}) < 2
    ):
        raise ValidationError("تکرار به حداقل دو منبع متمایز واجد شرایط نیاز دارد.")
    if replaces is not None and (
        replaces.organization_id != organization.pk
        or status not in {RecurrenceStatus.VALID, RecurrenceStatus.INVALIDATED}
        or not correction_reason.strip()
    ):
        raise ValidationError("اصلاح تکرار به سابقه هم‌Tenant و دلیل نیاز دارد.")
    resolved = []
    for source in sources:
        item, version, source_status, source_hash = _resolve_source(
            organization=organization,
            actor=actor,
            source_type=source["source_type"],
            source_id=source["source_id"],
        )
        resolved.append(
            (source["source_type"], item, version, source_status, source_hash)
        )
    manifest = _hash(
        {
            "key": recurrence_key,
            "scope": scope_description,
            "period": [period_start, period_end],
            "sources": [
                (kind, str(item.pk), version) for kind, item, version, _, _ in resolved
            ],
            "status": status,
            "replaces": str(replaces.pk if replaces else ""),
            "correction_reason": correction_reason.strip(),
        }
    )
    evidence = KnowledgeRecurrenceEvidence.objects.create(
        organization=organization,
        recurrence_key=recurrence_key.strip(),
        scope_description=scope_description[:240],
        period_start=period_start,
        period_end=period_end,
        manifest_hash=manifest,
        request_hash=request_hash,
        created_by=actor,
        status=status,
        replaces=replaces,
        correction_reason=correction_reason.strip(),
        operation_key=key,
    )
    for kind, item, version, source_status, source_hash in resolved:
        KnowledgeRecurrenceSource.objects.create(
            recurrence=evidence,
            source_type=kind,
            source_id=item.pk,
            source_version=version,
            source_status=source_status,
            source_hash=source_hash,
        )
    _audit(
        AuditAction.KNOWLEDGE_RECURRENCE_CORRECTED
        if replaces
        else AuditAction.KNOWLEDGE_RECURRENCE_RECORDED,
        evidence,
        actor,
        organization=organization,
        metadata={"replaces_id": str(replaces.pk)} if replaces else None,
    )
    return evidence


@transaction.atomic
def correct_recurrence(
    *,
    organization,
    actor,
    recurrence_id,
    disposition: str,
    reason: str,
    recurrence_key: str = "",
    scope_description: str = "",
    period_start: date | None = None,
    period_end: date | None = None,
    sources: list[dict[str, Any]] | None = None,
    operation_key: uuid.UUID | None = None,
) -> KnowledgeRecurrenceEvidence:
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_RECURRENCE_RECORD,
    )
    previous = (
        KnowledgeRecurrenceEvidence.objects.select_for_update()
        .prefetch_related("sources")
        .get(pk=recurrence_id)
    )
    if disposition not in {"invalidate", "replace"} or not reason.strip():
        raise ValidationError("نوع و دلیل اصلاح تکرار الزامی است.")
    key = operation_key or uuid.uuid4()
    existing = KnowledgeRecurrenceEvidence.objects.filter(
        organization=organization, created_by=actor, operation_key=key
    ).first()
    if existing:
        expected_status = (
            RecurrenceStatus.INVALIDATED
            if disposition == "invalidate"
            else RecurrenceStatus.VALID
        )
        if (
            existing.replaces_id != previous.pk
            or existing.status != expected_status
            or existing.correction_reason != reason.strip()
        ):
            raise ValidationError("کلید اصلاح تکرار با محتوای دیگری استفاده شده است.")
        if disposition == "replace":
            expected_hash = _hash(
                {
                    "key": recurrence_key.strip(),
                    "scope": scope_description,
                    "period": [period_start, period_end],
                    "sources": sorted(
                        (source["source_type"], str(source["source_id"]))
                        for source in (sources or [])
                    ),
                    "status": RecurrenceStatus.VALID,
                    "replaces": str(previous.pk),
                    "correction_reason": reason.strip(),
                }
            )
            if existing.request_hash != expected_hash:
                raise ValidationError(
                    "کلید اصلاح تکرار با محتوای دیگری استفاده شده است."
                )
        return existing
    if (
        previous.organization_id != organization.pk
        or previous.status != RecurrenceStatus.VALID
        or previous.replacements.exists()
    ):
        raise ValidationError("شاهد تکرار برای اصلاح جاری نیست.")
    if disposition == "invalidate":
        pins = list(previous.sources.all())
        replacement = KnowledgeRecurrenceEvidence.objects.create(
            organization=organization,
            recurrence_key=previous.recurrence_key,
            scope_description=previous.scope_description,
            period_start=previous.period_start,
            period_end=previous.period_end,
            manifest_hash=_hash(
                {
                    "invalidates": str(previous.pk),
                    "reason": reason.strip(),
                    "source_hashes": [pin.source_hash for pin in pins],
                }
            ),
            request_hash=_hash(
                {
                    "invalidates": str(previous.pk),
                    "reason": reason.strip(),
                }
            ),
            created_by=actor,
            replaces=previous,
            status=RecurrenceStatus.INVALIDATED,
            correction_reason=reason,
            operation_key=key,
        )
        for pin in pins:
            KnowledgeRecurrenceSource.objects.create(
                recurrence=replacement,
                source_type=pin.source_type,
                source_id=pin.source_id,
                source_version=pin.source_version,
                source_status=pin.source_status,
                source_hash=pin.source_hash,
            )
        _audit(
            AuditAction.KNOWLEDGE_RECURRENCE_CORRECTED,
            replacement,
            actor,
            organization=organization,
            metadata={"replaces_id": str(previous.pk), "disposition": disposition},
        )
        return replacement
    if period_start is None or period_end is None:
        raise ValidationError("دوره اصلاح جایگزین الزامی است.")
    return record_recurrence(
        organization=organization,
        actor=actor,
        recurrence_key=recurrence_key,
        scope_description=scope_description,
        period_start=period_start,
        period_end=period_end,
        sources=sources or [],
        operation_key=key,
        replaces=previous,
        status=RecurrenceStatus.VALID,
        correction_reason=reason,
    )


@transaction.atomic
def record_reuse(
    *,
    organization,
    actor,
    publication_version_id,
    reuse_type: str,
    consumer_type: str,
    consumer_id: uuid.UUID,
    consumer_version: str,
    purpose: str,
    operation_key: uuid.UUID | None = None,
) -> KnowledgeReuseEvidence:
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_REUSE_RECORD,
    )
    if reuse_type not in ReuseType.values or not all(
        (consumer_type.strip(), consumer_version.strip(), purpose.strip())
    ):
        raise ValidationError("نوع و خط مصرف دانش معتبر نیست.")
    _resolve_consumer(
        organization=organization,
        actor=actor,
        consumer_type=consumer_type,
        consumer_id=consumer_id,
        consumer_version=consumer_version,
    )
    version = KnowledgePublicationVersion.objects.select_related("publication").get(
        pk=publication_version_id
    )
    if (
        version.status not in {PublicationStatus.CURRENT, PublicationStatus.REVIEW_DUE}
        or version.publication.scope == KnowledgeScope.TENANT
        and version.publication.organization_id != organization.pk
    ):
        raise PermissionDenied("نسخه دانش برای استفاده مجدد قابل دسترس نیست.")
    key = operation_key or uuid.uuid4()
    payload = {
        "version": str(version.pk),
        "type": reuse_type,
        "consumer_type": consumer_type,
        "consumer_id": str(consumer_id),
        "consumer_version": consumer_version,
        "purpose": purpose,
    }
    existing = KnowledgeReuseEvidence.objects.filter(
        organization=organization, actor=actor, operation_key=key
    ).first()
    if existing:
        if existing.payload_hash != _hash(payload):
            raise ValidationError(
                "کلید عملیات استفاده مجدد با محتوای دیگری استفاده شده است."
            )
        return existing
    try:
        item = KnowledgeReuseEvidence.objects.create(
            organization=organization,
            publication_version=version,
            reuse_type=reuse_type,
            consumer_type=consumer_type.strip(),
            consumer_id=consumer_id,
            consumer_version=consumer_version.strip(),
            purpose=purpose.strip(),
            actor=actor,
            operation_key=key,
            payload_hash=_hash(payload),
        )
    except IntegrityError as exc:
        raise ValidationError("شاهد استفاده مجدد تکراری است.") from exc
    _audit(AuditAction.KNOWLEDGE_REUSE_RECORDED, item, actor, organization=organization)
    return item


@transaction.atomic
def correct_reuse(
    *,
    organization,
    actor,
    reuse_id,
    disposition: str,
    reason: str,
    purpose: str = "",
    consumer_version: str = "",
    operation_key: uuid.UUID | None = None,
) -> KnowledgeReuseEvidence:
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_REUSE_RECORD,
    )
    previous = (
        KnowledgeReuseEvidence.objects.select_for_update()
        .select_related("publication_version")
        .get(pk=reuse_id)
    )
    replacement_purpose = purpose.strip() or previous.purpose
    replacement_consumer_version = consumer_version.strip() or previous.consumer_version
    payload = {
        "reverses": str(previous.pk),
        "disposition": disposition,
        "reason": reason.strip(),
        "purpose": replacement_purpose,
        "consumer_version": replacement_consumer_version,
    }
    key = operation_key or uuid.uuid4()
    existing = KnowledgeReuseEvidence.objects.filter(
        organization=organization, actor=actor, operation_key=key
    ).first()
    if existing:
        if existing.payload_hash != _hash(payload):
            raise ValidationError("کلید اصلاح استفاده با محتوای دیگری استفاده شده است.")
        return existing
    if (
        previous.organization_id != organization.pk
        or previous.reverses_id
        or previous.reversed_by.exists()
        or disposition not in {"reverse", "replace"}
        or not reason.strip()
    ):
        raise ValidationError("شاهد استفاده مجدد برای اصلاح جاری نیست.")
    status = (
        ReuseStatus.REVERSAL if disposition == "reverse" else ReuseStatus.REPLACEMENT
    )
    item = KnowledgeReuseEvidence.objects.create(
        organization=organization,
        publication_version=previous.publication_version,
        reuse_type=previous.reuse_type,
        consumer_type=previous.consumer_type,
        consumer_id=previous.consumer_id,
        consumer_version=replacement_consumer_version,
        purpose=replacement_purpose,
        actor=actor,
        status=status,
        reverses=previous,
        reason=reason.strip(),
        operation_key=key,
        payload_hash=_hash(payload),
    )
    _audit(
        AuditAction.KNOWLEDGE_REUSE_CORRECTED,
        item,
        actor,
        organization=organization,
        metadata={"reverses_id": str(previous.pk), "disposition": disposition},
    )
    return item


@transaction.atomic
def request_platform_promotion(
    *,
    organization,
    actor,
    version_id,
    title: str,
    body: str,
    audience: str,
    category_code: str,
    anonymization_statement: str,
    operation_key: uuid.UUID | None = None,
) -> KnowledgePromotion:
    _allow(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.KNOWLEDGE_PUBLICATIONS_PUBLISH,
    )
    version = (
        KnowledgePublicationVersion.objects.select_for_update()
        .select_related("publication", "candidate_revision__candidate")
        .get(pk=version_id)
    )
    if (
        version.publication.organization_id != organization.pk
        or version.status
        not in {PublicationStatus.CURRENT, PublicationStatus.REVIEW_DUE}
        or not all(
            (
                title.strip(),
                body.strip(),
                audience.strip(),
                category_code.strip(),
                anonymization_statement.strip(),
            )
        )
    ):
        raise ValidationError("درخواست ترویج یا متن پالایش‌شده معتبر نیست.")
    snapshot = {
        "title": title.strip(),
        "body": body.strip(),
        "knowledge_type": version.candidate_revision.snapshot["knowledge_type"],
        "authority_classification": version.metadata["authority"],
        "sensitivity": KnowledgeSensitivity.INTERNAL,
        "audience": audience.strip(),
        "category_code": category_code.strip(),
        "tags": version.metadata.get("tags", []),
    }
    key = operation_key or uuid.uuid4()
    existing = KnowledgePromotion.objects.filter(
        source_organization=organization, requested_by=actor, operation_key=key
    ).first()
    if existing:
        if existing.snapshot_hash != _hash(snapshot):
            raise ValidationError("کلید درخواست ترویج با محتوای دیگری استفاده شده است.")
        return existing
    promotion = KnowledgePromotion.objects.create(
        source_organization=organization,
        source_version=version,
        sanitized_snapshot=snapshot,
        snapshot_hash=_hash(snapshot),
        anonymization_statement=anonymization_statement.strip(),
        requested_by=actor,
        operation_key=key,
    )
    KnowledgePromotionEvent.objects.create(
        promotion=promotion,
        to_status=PromotionStatus.REQUESTED,
        actor=actor,
        reason=anonymization_statement.strip(),
    )
    _audit(
        AuditAction.KNOWLEDGE_PROMOTION_REQUESTED,
        promotion,
        actor,
        organization=organization,
    )
    return promotion


@transaction.atomic
def review_platform_promotion(
    *, promotion_id, actor, outcome: str, reason: str, operation_key=None
) -> KnowledgePromotion:
    if not is_platform_admin(actor):
        raise PermissionDenied("فقط اختیار Platform برای بررسی ترویج معتبر است.")
    promotion = KnowledgePromotion.objects.select_for_update().get(pk=promotion_id)
    if (
        promotion.status != PromotionStatus.REQUESTED
        or actor.pk == promotion.requested_by_id
        or outcome not in {"recommend", "reject"}
        or not reason.strip()
    ):
        raise ValidationError("بررسی مستقل ترویج یا وضعیت آن معتبر نیست.")
    target = (
        PromotionStatus.RECOMMENDED
        if outcome == "recommend"
        else PromotionStatus.REJECTED
    )
    promotion.status = target
    promotion.reviewed_by = actor
    promotion.review_reason = reason.strip()
    promotion._knowledge_transition = True
    promotion.save(update_fields=["status", "reviewed_by", "review_reason"])
    KnowledgePromotionEvent.objects.create(
        promotion=promotion,
        from_status=PromotionStatus.REQUESTED,
        to_status=target,
        actor=actor,
        reason=reason.strip(),
        operation_key=operation_key or uuid.uuid4(),
    )
    _audit(AuditAction.KNOWLEDGE_PROMOTION_REVIEWED, promotion, actor)
    return promotion


@transaction.atomic
def approve_platform_promotion(
    *, promotion_id, actor, operation_key=None
) -> KnowledgePromotion:
    if not is_platform_admin(actor):
        raise PermissionDenied("فقط اختیار Platform برای تأیید ترویج معتبر است.")
    promotion = (
        KnowledgePromotion.objects.select_for_update()
        .select_related("source_version__candidate_revision__candidate")
        .get(pk=promotion_id)
    )
    source_author_id = (
        promotion.source_version.candidate_revision.candidate.created_by_id
    )
    if promotion.status != PromotionStatus.RECOMMENDED or actor.pk in {
        promotion.requested_by_id,
        source_author_id,
    }:
        raise PermissionDenied("تأیید Platform باید از همه مؤلفان Tenant مستقل باشد.")
    snapshot = promotion.sanitized_snapshot
    candidate = KnowledgeCandidate.objects.create(
        scope=KnowledgeScope.PLATFORM,
        source_organization=promotion.source_organization,
        title=snapshot["title"],
        body=snapshot["body"],
        knowledge_type=snapshot["knowledge_type"],
        authority_classification=snapshot["authority_classification"],
        sensitivity=KnowledgeSensitivity.INTERNAL,
        audience=snapshot["audience"],
        category_code=snapshot["category_code"],
        tags=snapshot.get("tags", []),
        status=CandidateStatus.APPROVED,
        content_hash=promotion.snapshot_hash,
        created_by=promotion.requested_by,
        submitted_by=promotion.requested_by,
        reviewed_by=promotion.reviewed_by,
        approved_by=actor,
        tenant_disclosure_authorized_by=promotion.requested_by,
    )
    KnowledgeCandidateRevision.objects.create(
        candidate=candidate,
        revision=1,
        snapshot=_candidate_snapshot(candidate),
        content_hash=candidate.content_hash,
        submitted_by=promotion.requested_by,
    )
    promotion.status = PromotionStatus.APPROVED
    promotion.approved_by = actor
    promotion.platform_candidate = candidate
    promotion._knowledge_transition = True
    promotion.save(update_fields=["status", "approved_by", "platform_candidate"])
    KnowledgePromotionEvent.objects.create(
        promotion=promotion,
        from_status=PromotionStatus.RECOMMENDED,
        to_status=PromotionStatus.APPROVED,
        actor=actor,
        reason=promotion.review_reason,
        operation_key=operation_key or uuid.uuid4(),
    )
    _audit(AuditAction.KNOWLEDGE_PROMOTION_APPROVED, promotion, actor)
    return promotion


@transaction.atomic
def publish_platform_promotion(
    *, promotion_id, actor, operation_key=None
) -> KnowledgePublicationVersion:
    if not is_platform_admin(actor):
        raise PermissionDenied("فقط اختیار Platform برای انتشار ترویج معتبر است.")
    promotion = KnowledgePromotion.objects.select_for_update().get(pk=promotion_id)
    if (
        promotion.status != PromotionStatus.APPROVED
        or promotion.platform_candidate is None
        or actor.pk == promotion.requested_by_id
    ):
        raise PermissionDenied("ترویج برای انتشار مستقل Platform آماده نیست.")
    candidate = promotion.platform_candidate
    revision = candidate.revisions.get(revision=1)
    publication = KnowledgePublication.objects.create(
        scope=KnowledgeScope.PLATFORM, source_candidate=candidate
    )
    manifest = {
        "candidate_revision": str(revision.pk),
        "snapshot_hash": promotion.snapshot_hash,
        "promotion_id": str(promotion.pk),
        "version": 1,
    }
    version = KnowledgePublicationVersion.objects.create(
        publication=publication,
        candidate_revision=revision,
        version_number=1,
        title=candidate.title,
        body=candidate.body,
        metadata={
            "authority": candidate.authority_classification,
            "sensitivity": candidate.sensitivity,
            "audience": candidate.audience,
            "category": candidate.category_code,
            "tags": candidate.tags,
            "platform_derivative": True,
        },
        manifest_hash=_hash(manifest),
        published_by=actor,
        published_at=timezone.now(),
    )
    KnowledgePublicationEvent.objects.create(
        publication_version=version,
        event_type=PublicationEventType.PUBLISHED,
        actor=actor,
        reason="انتشار مشتق پالایش‌شده Platform",
        operation_key=operation_key or uuid.uuid4(),
    )
    publication.current_version = version
    publication.save(update_fields=["current_version"])
    promotion.status = PromotionStatus.PUBLISHED
    promotion._knowledge_transition = True
    promotion.save(update_fields=["status"])
    KnowledgePromotionEvent.objects.create(
        promotion=promotion,
        from_status=PromotionStatus.APPROVED,
        to_status=PromotionStatus.PUBLISHED,
        actor=actor,
    )
    _audit(AuditAction.KNOWLEDGE_PROMOTION_PUBLISHED, promotion, actor)
    return version
