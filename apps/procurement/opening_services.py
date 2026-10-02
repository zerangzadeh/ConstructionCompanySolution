"""P5-S09 synchronous protected opening and exact-version delivery."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.models import (
    DocumentProcessingAssessment,
    DocumentProcessingVerdict,
)
from apps.organizations.authorization import (
    membership_has_permission,
    membership_has_scope,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationStatus,
)
from apps.procurement.models import (
    QuoteConfidentialAccessGrant,
    QuoteConfidentialAccessRevocation,
    QuoteEvidencePackageFreeze,
    QuoteEvidencePackageFreezeItem,
    QuoteEvidenceType,
    QuoteOpeningEvent,
    QuoteOpeningRequest,
    QuoteRevision,
    QuoteRevisionEvidence,
    QuoteRevisionStatus,
    RequestForQuotation,
    RequestForQuotationInvitation,
    RequestForQuotationStatus,
    RequestForQuotationVersion,
    RFQCloseEntryDisposition,
    RFQCloseManifest,
    RFQCloseManifestEntry,
)

OPENING_CONTROL_PERMISSIONS = (
    BusinessPermissionCode.RFQ_QUOTES_OPEN,
    BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN,
    BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL,
    BusinessPermissionCode.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS,
)


@dataclass(frozen=True, slots=True)
class ConfidentialDocumentDelivery:
    document_version_id: str
    content: bytes
    filename: str
    content_type: str
    content_length: int
    canonical_sha256: str
    content_disposition: str
    nosniff: bool = True


def _technical_key(value: str, *, label: str, max_length: int = 128) -> str:
    normalized = str(value).strip()
    if not re.fullmatch(rf"[A-Za-z0-9._:-]{{1,{max_length}}}", normalized):
        raise ValueError(f"{label} معتبر نیست.")
    return normalized


def _reason(value: str) -> str:
    normalized = str(value).strip()
    if not normalized or len(normalized) > 500:
        raise ValueError("دلیل غیرمحتوایی معتبر الزامی است.")
    return normalized


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _audit_actor(organization: Organization, actor: User) -> User | None:
    if organization.memberships.filter(
        user=actor, status=MembershipStatus.ACTIVE
    ).exists():
        return actor
    return None


def _record_denial(
    *,
    action: str,
    organization: Organization,
    actor: User,
    revision_id: object,
    failure: Exception,
    evidence_id: object | None = None,
) -> None:
    metadata = {
        "attempted_actor_id": str(actor.pk),
        "quote_revision_id": str(revision_id),
        "failure_code": type(failure).__name__,
        "content_recorded": False,
    }
    if evidence_id is not None:
        metadata["evidence_id"] = str(evidence_id)
    record_audit_event(
        action=action,
        entity_type="quote_revision",
        entity_id=str(revision_id),
        organization=organization,
        actor=_audit_actor(organization, actor),
        metadata=metadata,
    )


def _lock_target(
    *,
    organization: Organization,
    actor: User,
    revision: QuoteRevision,
    permission: BusinessPermissionCode,
) -> tuple[QuoteRevision, RFQCloseManifest]:
    try:
        locked_organization = Organization.objects.select_for_update().get(
            pk=organization.pk, status=OrganizationStatus.ACTIVE
        )
        membership = OrganizationMembership.objects.select_for_update().get(
            organization=locked_organization,
            user=actor,
            status=MembershipStatus.ACTIVE,
            user__is_active=True,
        )
        identity = (
            QuoteRevision.objects.filter(pk=revision.pk, organization=organization)
            .values(
                "envelope__rfq_id",
                "rfq_version_id",
                "invitation_id",
                "envelope_id",
            )
            .get()
        )
        rfq = (
            RequestForQuotation.objects.select_for_update()
            .select_related("project")
            .get(pk=identity["envelope__rfq_id"], organization=organization)
        )
        version = RequestForQuotationVersion.objects.select_for_update().get(
            pk=identity["rfq_version_id"], organization=organization
        )
        invitation = RequestForQuotationInvitation.objects.select_for_update().get(
            pk=identity["invitation_id"], organization=organization
        )
        locked_revision = (
            QuoteRevision.objects.select_for_update()
            .select_related("envelope__rfq__project", "invitation", "rfq_version")
            .get(pk=revision.pk, organization=organization)
        )
        manifest = RFQCloseManifest.objects.select_for_update().get(
            rfq=rfq, effective_version=version
        )
        RFQCloseManifestEntry.objects.select_for_update().get(
            manifest=manifest,
            invitation=invitation,
            effective_revision=locked_revision,
            disposition=RFQCloseEntryDisposition.EFFECTIVE_SUBMITTED,
        )
    except (
        Organization.DoesNotExist,
        OrganizationMembership.DoesNotExist,
        QuoteRevision.DoesNotExist,
        RequestForQuotation.DoesNotExist,
        RequestForQuotationVersion.DoesNotExist,
        RequestForQuotationInvitation.DoesNotExist,
        RFQCloseManifest.DoesNotExist,
        RFQCloseManifestEntry.DoesNotExist,
    ) as exc:
        raise PermissionDenied("هدف گشایش در این سازمان معتبر نیست.") from exc

    require_business_permission(
        user=actor,
        organization=locked_organization,
        permission=permission,
        project=rfq.project,
        message="اجازه انجام عملیات حفاظت‌شده پیشنهاد را ندارید.",
    )
    if membership.user_id != actor.pk or (
        rfq.status != RequestForQuotationStatus.CLOSED
        or version.rfq_id != rfq.pk
        or version.version_number != rfq.current_version_number
        or invitation.rfq_version_id != version.pk
        or locked_revision.invitation_id != invitation.pk
        or locked_revision.rfq_version_id != version.pk
        or locked_revision.status != QuoteRevisionStatus.SUBMITTED
        or locked_revision.is_late
    ):
        raise ValueError("نسخه پیشنهاد برای گشایش حفاظت‌شده مؤثر نیست.")
    return locked_revision, manifest


def _evidence_snapshot(evidence: QuoteRevisionEvidence) -> dict[str, str]:
    return {
        "evidence_id": str(evidence.pk),
        "evidence_type": evidence.evidence_type,
        "evidence_slot": evidence.evidence_slot,
        "document_version_id": str(evidence.document_version_id),
        "canonical_sha256": evidence.canonical_sha256,
    }


def _freeze_package(
    *,
    organization: Organization,
    actor: User,
    revision: QuoteRevision,
    manifest: RFQCloseManifest,
) -> QuoteEvidencePackageFreeze:
    existing = (
        QuoteEvidencePackageFreeze.objects.select_for_update()
        .filter(quote_revision=revision)
        .first()
    )
    evidence_items = list(
        QuoteRevisionEvidence.objects.select_for_update()
        .select_related("document_version", "sealed_custody")
        .filter(quote_revision=revision)
        .order_by("evidence_type", "evidence_slot", "pk")
    )
    originals = [
        item
        for item in evidence_items
        if item.evidence_type == QuoteEvidenceType.SUPPLIER_ORIGINAL
    ]
    attachments = [
        item
        for item in evidence_items
        if item.evidence_type == QuoteEvidenceType.SUPPLIER_ATTACHMENT
    ]
    if len(originals) != 1 or len(attachments) > 20:
        raise ValueError("بسته کامل شاهد باید یک اصل و حداکثر ۲۰ پیوست داشته باشد.")
    for item in evidence_items:
        if (
            item.organization_id != organization.pk
            or item.revision_fingerprint != revision.integrity_fingerprint
            or item.document_version.sha256 != item.canonical_sha256
            or item.sealed_custody.document_version_id != item.document_version_id
            or item.sealed_custody.canonical_sha256 != item.canonical_sha256
            or not item.document_version.file.storage.exists(
                item.document_version.file.name
            )
        ):
            raise ValueError("زنجیره یا بایت شاهد بسته معتبر نیست.")
    snapshots = [_evidence_snapshot(item) for item in evidence_items]
    package_fingerprint = _fingerprint(snapshots)
    if existing:
        frozen_ids = set(existing.items.values_list("evidence_id", flat=True))
        if (
            existing.package_fingerprint != package_fingerprint
            or existing.item_count != len(evidence_items)
            or frozen_ids != {item.pk for item in evidence_items}
        ):
            raise ValueError("بسته شاهد منجمد با شواهد جاری تعارض دارد.")
        return existing

    package = QuoteEvidencePackageFreeze.objects.create(
        organization=organization,
        quote_revision=revision,
        close_manifest=manifest,
        frozen_by=actor,
        frozen_at=timezone.now(),
        item_count=len(evidence_items),
        package_fingerprint=package_fingerprint,
    )
    QuoteEvidencePackageFreezeItem.objects.bulk_create(
        [
            QuoteEvidencePackageFreezeItem(
                organization=organization,
                package=package,
                evidence=item,
                evidence_type=item.evidence_type,
                evidence_slot=item.evidence_slot,
                document_version=item.document_version,
                canonical_sha256=item.canonical_sha256,
            )
            for item in evidence_items
        ]
    )
    return package


def _verify_technical_readiness(
    package: QuoteEvidencePackageFreeze,
) -> list[QuoteEvidencePackageFreezeItem]:
    items = list(
        QuoteEvidencePackageFreezeItem.objects.select_for_update()
        .select_related("evidence", "document_version")
        .filter(package=package)
        .order_by("evidence_type", "evidence_slot", "pk")
    )
    if len(items) != package.item_count or not items:
        raise ValueError("بسته منجمد کامل نیست.")
    current_ids = set(
        QuoteRevisionEvidence.objects.filter(
            quote_revision=package.quote_revision
        ).values_list("pk", flat=True)
    )
    if current_ids != {item.evidence_id for item in items}:
        raise ValueError("شواهد جاری با بسته منجمد یکسان نیست.")
    for item in items:
        version = item.document_version
        assessment = (
            DocumentProcessingAssessment.objects.select_for_update()
            .filter(version=version)
            .order_by("-sequence")
            .first()
        )
        if (
            item.evidence.document_version_id != version.pk
            or item.evidence.canonical_sha256 != item.canonical_sha256
            or version.sha256 != item.canonical_sha256
            or assessment is None
            or assessment.verdict != DocumentProcessingVerdict.CLEAN
            or assessment.input_sha256 != item.canonical_sha256
            or not version.file.storage.exists(version.file.name)
        ):
            raise ValueError(
                "تمام اقلام بسته باید شاهد فنی CLEAN و بایت معتبر داشته باشند."
            )
        with version.file.storage.open(version.file.name, "rb") as source:
            digest = hashlib.sha256()
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != item.canonical_sha256:
            raise ValueError("هش بایت ذخیره‌شده با بسته منجمد یکسان نیست.")
    return items


def request_quote_opening(
    *,
    organization: Organization,
    actor: User,
    quote_revision: QuoteRevision,
    reason: str,
    idempotency_key: str,
) -> QuoteOpeningRequest:
    """Freeze the exact package and create an immutable pending opening request."""

    revision_id = quote_revision.pk
    try:
        normalized_reason = _reason(reason)
        key = _technical_key(idempotency_key, label="کلید یکتای درخواست گشایش")
        with transaction.atomic():
            revision, manifest = _lock_target(
                organization=organization,
                actor=actor,
                revision=quote_revision,
                permission=BusinessPermissionCode.RFQ_QUOTES_OPEN,
            )
            if timezone.now() < revision.rfq_version.earliest_opening_at:
                raise ValueError("زمان مجاز گشایش پیشنهاد فرا نرسیده است.")
            package = _freeze_package(
                organization=organization,
                actor=actor,
                revision=revision,
                manifest=manifest,
            )
            payload_fingerprint = _fingerprint(
                {
                    "organization": str(organization.pk),
                    "revision": str(revision.pk),
                    "package": str(package.pk),
                    "package_fingerprint": package.package_fingerprint,
                    "reason": normalized_reason,
                }
            )
            existing = QuoteOpeningRequest.objects.filter(
                quote_revision=revision, idempotency_key=key
            ).first()
            if existing:
                if existing.payload_fingerprint != payload_fingerprint:
                    raise ValueError(
                        "کلید یکتا با درخواست گشایش متفاوت استفاده شده است."
                    )
                return existing
            opening_request = QuoteOpeningRequest.objects.create(
                organization=organization,
                quote_revision=revision,
                frozen_package=package,
                requested_by=actor,
                requested_at=timezone.now(),
                reason=normalized_reason,
                idempotency_key=key,
                payload_fingerprint=payload_fingerprint,
            )
            record_audit_event(
                action=AuditAction.RFQ_OPENING_REQUESTED,
                entity_type="quote_opening_request",
                entity_id=opening_request.pk,
                organization=organization,
                actor=actor,
                metadata={
                    "quote_revision_id": str(revision.pk),
                    "frozen_package_id": str(package.pk),
                    "package_fingerprint": package.package_fingerprint,
                    "item_count": package.item_count,
                    "content_recorded": False,
                },
            )
            return opening_request
    except Exception as exc:
        _record_denial(
            action=AuditAction.RFQ_OPENING_REQUEST_REJECTED,
            organization=organization,
            actor=actor,
            revision_id=revision_id,
            failure=exc,
        )
        raise


def approve_quote_opening(
    *,
    organization: Organization,
    actor: User,
    opening_request: QuoteOpeningRequest,
) -> QuoteOpeningEvent:
    """Independently approve and atomically create the immutable opening event."""

    revision_id = opening_request.quote_revision_id
    try:
        with transaction.atomic():
            locked_request = (
                QuoteOpeningRequest.objects.select_for_update()
                .select_related("quote_revision", "frozen_package")
                .get(pk=opening_request.pk, organization=organization)
            )
            revision, _ = _lock_target(
                organization=organization,
                actor=actor,
                revision=locked_request.quote_revision,
                permission=BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN,
            )
            if locked_request.requested_by_id == actor.pk:
                raise PermissionDenied("درخواست‌کننده نمی‌تواند گشایش را تأیید کند.")
            if timezone.now() < revision.rfq_version.earliest_opening_at:
                raise ValueError("زمان مجاز گشایش پیشنهاد فرا نرسیده است.")
            existing = (
                QuoteOpeningEvent.objects.select_for_update()
                .filter(quote_revision=revision)
                .first()
            )
            if existing:
                if existing.opening_request_id != locked_request.pk:
                    raise ValueError(
                        "نسخه پیشنهاد قبلاً با درخواست دیگری گشوده شده است."
                    )
                return existing
            _verify_technical_readiness(locked_request.frozen_package)
            try:
                event = QuoteOpeningEvent.objects.create(
                    organization=organization,
                    quote_revision=revision,
                    opening_request=locked_request,
                    approved_by=actor,
                    opened_at=timezone.now(),
                    package_fingerprint=(
                        locked_request.frozen_package.package_fingerprint
                    ),
                )
            except IntegrityError as exc:
                raise ValueError("تأیید هم‌زمان گشایش متعارض بود.") from exc
            record_audit_event(
                action=AuditAction.RFQ_QUOTE_OPENED,
                entity_type="quote_opening_event",
                entity_id=event.pk,
                organization=organization,
                actor=actor,
                metadata={
                    "quote_revision_id": str(revision.pk),
                    "opening_request_id": str(locked_request.pk),
                    "requester_id": str(locked_request.requested_by_id),
                    "approver_id": str(actor.pk),
                    "package_fingerprint": event.package_fingerprint,
                    "content_recorded": False,
                },
            )
            return event
    except Exception as exc:
        _record_denial(
            action=AuditAction.RFQ_OPENING_APPROVAL_REJECTED,
            organization=organization,
            actor=actor,
            revision_id=revision_id,
            failure=exc,
        )
        raise


def grant_quote_confidential_access(
    *,
    organization: Organization,
    actor: User,
    quote_revision: QuoteRevision,
    membership: OrganizationMembership,
    reason: str,
    idempotency_key: str,
) -> QuoteConfidentialAccessGrant:
    """Grant one active member least-privilege access to one opened revision."""

    normalized_reason = _reason(reason)
    key = _technical_key(idempotency_key, label="کلید یکتای اعطای دسترسی")
    with transaction.atomic():
        revision, _ = _lock_target(
            organization=organization,
            actor=actor,
            revision=quote_revision,
            permission=BusinessPermissionCode.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS,
        )
        if (
            not QuoteOpeningEvent.objects.select_for_update()
            .filter(quote_revision=revision)
            .exists()
        ):
            raise ValueError(
                "تنها نسخه گشوده‌شده می‌تواند دریافت‌کننده محرمانه داشته باشد."
            )
        target = (
            OrganizationMembership.objects.select_for_update()
            .select_related("user")
            .get(
                pk=membership.pk,
                organization=organization,
                status=MembershipStatus.ACTIVE,
            )
        )
        if target.user_id == actor.pk:
            raise PermissionDenied("اعطای دسترسی محرمانه به خود مجاز نیست.")
        if not membership_has_permission(
            target, BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL
        ) or not membership_has_scope(target, project=revision.envelope.rfq.project):
            raise PermissionDenied("دریافت‌کننده مجوز و دامنه مشاهده محرمانه را ندارد.")
        payload_fingerprint = _fingerprint(
            {
                "revision": str(revision.pk),
                "membership": str(target.pk),
                "reason": normalized_reason,
            }
        )
        existing = QuoteConfidentialAccessGrant.objects.filter(
            quote_revision=revision, idempotency_key=key
        ).first()
        if existing:
            if existing.payload_fingerprint != payload_fingerprint:
                raise ValueError("کلید یکتا با اعطای دسترسی متفاوت استفاده شده است.")
            return existing
        if QuoteConfidentialAccessGrant.objects.filter(
            quote_revision=revision,
            membership=target,
            revocation__isnull=True,
        ).exists():
            raise ValueError("این عضویت از قبل دسترسی فعال به نسخه دارد.")
        grant = QuoteConfidentialAccessGrant.objects.create(
            organization=organization,
            quote_revision=revision,
            membership=target,
            granted_by=actor,
            granted_at=timezone.now(),
            reason=normalized_reason,
            idempotency_key=key,
            payload_fingerprint=payload_fingerprint,
        )
        record_audit_event(
            action=AuditAction.RFQ_CONFIDENTIAL_ACCESS_GRANTED,
            entity_type="quote_confidential_access_grant",
            entity_id=grant.pk,
            organization=organization,
            actor=actor,
            metadata={
                "quote_revision_id": str(revision.pk),
                "membership_id": str(target.pk),
                "content_recorded": False,
            },
        )
        return grant


def revoke_quote_confidential_access(
    *,
    organization: Organization,
    actor: User,
    grant: QuoteConfidentialAccessGrant,
    reason: str,
) -> QuoteConfidentialAccessRevocation:
    """Append an immutable revocation without erasing the original grant."""

    normalized_reason = _reason(reason)
    with transaction.atomic():
        locked_grant = (
            QuoteConfidentialAccessGrant.objects.select_for_update()
            .select_related("quote_revision")
            .get(pk=grant.pk, organization=organization)
        )
        _lock_target(
            organization=organization,
            actor=actor,
            revision=locked_grant.quote_revision,
            permission=BusinessPermissionCode.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS,
        )
        existing = (
            QuoteConfidentialAccessRevocation.objects.select_for_update()
            .filter(grant=locked_grant)
            .first()
        )
        if existing:
            return existing
        revocation = QuoteConfidentialAccessRevocation.objects.create(
            organization=organization,
            grant=locked_grant,
            revoked_by=actor,
            revoked_at=timezone.now(),
            reason=normalized_reason,
        )
        record_audit_event(
            action=AuditAction.RFQ_CONFIDENTIAL_ACCESS_REVOKED,
            entity_type="quote_confidential_access_revocation",
            entity_id=revocation.pk,
            organization=organization,
            actor=actor,
            metadata={
                "quote_revision_id": str(locked_grant.quote_revision_id),
                "grant_id": str(locked_grant.pk),
                "membership_id": str(locked_grant.membership_id),
                "content_recorded": False,
            },
        )
        return revocation


def _safe_filename(value: str) -> str:
    filename = Path(value).name
    forbidden = '\\/:*?"<>|'
    filename = "".join(
        character
        for character in filename
        if character.isprintable() and character not in forbidden
    ).strip(" .")
    return filename[:180] or "supplier-evidence.bin"


def deliver_quote_confidential_document(
    *,
    organization: Organization,
    actor: User,
    quote_revision: QuoteRevision,
    evidence: QuoteRevisionEvidence,
) -> ConfidentialDocumentDelivery:
    """Synchronously return only one authorized exact pinned version."""

    try:
        with transaction.atomic():
            revision, _ = _lock_target(
                organization=organization,
                actor=actor,
                revision=quote_revision,
                permission=BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL,
            )
            if (
                not QuoteOpeningEvent.objects.select_for_update()
                .filter(quote_revision=revision)
                .exists()
            ):
                raise PermissionDenied("نسخه پیشنهاد گشوده نشده است.")
            membership = OrganizationMembership.objects.select_for_update().get(
                organization=organization,
                user=actor,
                status=MembershipStatus.ACTIVE,
            )
            if not QuoteConfidentialAccessGrant.objects.filter(
                quote_revision=revision,
                membership=membership,
                revocation__isnull=True,
            ).exists():
                raise PermissionDenied("اعطای فعال مشاهده محرمانه وجود ندارد.")
            package = QuoteEvidencePackageFreeze.objects.select_for_update().get(
                quote_revision=revision
            )
            item = (
                QuoteEvidencePackageFreezeItem.objects.select_for_update()
                .select_related("evidence", "document_version")
                .get(package=package, evidence=evidence)
            )
            _verify_technical_readiness(package)
            version = item.document_version
            with version.file.storage.open(version.file.name, "rb") as source:
                content = source.read()
            if hashlib.sha256(content).hexdigest() != item.canonical_sha256:
                raise ValueError("هش بایت تحویلی با نسخه پین‌شده یکسان نیست.")
            filename = _safe_filename(version.original_file_name)
            delivery = ConfidentialDocumentDelivery(
                document_version_id=str(version.pk),
                content=content,
                filename=filename,
                content_type=version.content_type,
                content_length=len(content),
                canonical_sha256=item.canonical_sha256,
                content_disposition=f'attachment; filename="{filename}"',
            )
            record_audit_event(
                action=AuditAction.RFQ_CONFIDENTIAL_CONTENT_ACCESSED,
                entity_type="quote_revision_evidence",
                entity_id=evidence.pk,
                organization=organization,
                actor=actor,
                metadata={
                    "quote_revision_id": str(revision.pk),
                    "evidence_id": str(evidence.pk),
                    "document_version_id": str(version.pk),
                    "canonical_sha256": item.canonical_sha256,
                    "content_recorded": False,
                },
            )
            return delivery
    except Exception as exc:
        _record_denial(
            action=AuditAction.RFQ_CONFIDENTIAL_CONTENT_DENIED,
            organization=organization,
            actor=actor,
            revision_id=quote_revision.pk,
            evidence_id=evidence.pk,
            failure=exc,
        )
        raise
