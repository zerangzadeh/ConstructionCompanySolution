"""P5-S08 synchronous sealed supplier-evidence custody; no content retrieval."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.models import (
    DocumentRetentionClassification,
    DocumentVersion,
    SealedCustodyState,
)
from apps.documents.sealed_services import create_quarantined_sealed_document
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.procurement.models import (
    QuoteEnvelope,
    QuoteEvidencePackageFreeze,
    QuoteEvidenceSourceChannel,
    QuoteEvidenceType,
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

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


MAX_EVIDENCE_ITEM_BYTES = 25 * 1024 * 1024
MAX_SEALED_PACKAGE_BYTES = 100 * 1024 * 1024
MAX_SUPPLIER_ATTACHMENTS = 20
MAX_OOXML_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
SEALED_RETENTION_CLASSIFICATION = (
    DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
)

ALLOWED_EVIDENCE_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


@dataclass(frozen=True, slots=True)
class StagedEvidence:
    path: Path
    original_file_name: str
    extension: str
    content_type: str
    file_size: int
    sha256: str
    received_at: datetime


def _safe_technical_key(value: str, *, label: str, max_length: int) -> str:
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > max_length
        or not re.fullmatch(rf"[A-Za-z0-9._:-]{{1,{max_length}}}", normalized)
    ):
        raise ValueError(f"{label} معتبر نیست.")
    return normalized


def _stage_upload(upload: UploadedFile) -> StagedEvidence:
    original_file_name = Path(upload.name).name
    if not original_file_name or len(original_file_name) > 255:
        raise ValueError("نام فنی فایل معتبر نیست.")
    extension = Path(original_file_name).suffix.lower()
    content_type = str(getattr(upload, "content_type", "")).strip().lower()
    if extension not in ALLOWED_EVIDENCE_TYPES:
        raise ValueError("نوع فایل شاهد مجاز نیست.")
    if content_type != ALLOWED_EVIDENCE_TYPES[extension]:
        raise ValueError("پسوند و MIME فایل شاهد یکسان نیستند.")

    temporary_root = Path(settings.DOCUMENT_PROTECTED_ROOT) / ".custody-temporary"
    temporary_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(prefix="sealed-", dir=temporary_root)
    staged_path = Path(raw_path)
    digest = hashlib.sha256()
    size = 0
    try:
        with os.fdopen(descriptor, "wb") as target:
            for chunk in upload.chunks():
                size += len(chunk)
                if size > MAX_EVIDENCE_ITEM_BYTES:
                    raise ValueError("حجم هر قلم شاهد نباید از ۲۵ MiB بیشتر باشد.")
                digest.update(chunk)
                target.write(chunk)
        if size == 0:
            raise ValueError("فایل شاهد خالی است.")
        _validate_file_structure(staged_path, extension)
        return StagedEvidence(
            path=staged_path,
            original_file_name=original_file_name,
            extension=extension,
            content_type=content_type,
            file_size=size,
            sha256=digest.hexdigest(),
            received_at=timezone.now(),
        )
    except Exception:
        staged_path.unlink(missing_ok=True)
        raise


def _validate_file_structure(path: Path, extension: str) -> None:
    with path.open("rb") as source:
        prefix = source.read(16)
    if extension == ".pdf":
        if not prefix.startswith(b"%PDF-"):
            raise ValueError("امضای فایل PDF معتبر نیست.")
        return
    if extension in {".jpg", ".jpeg"}:
        if not prefix.startswith(b"\xff\xd8\xff"):
            raise ValueError("امضای فایل JPEG معتبر نیست.")
        return
    if extension == ".png":
        if not prefix.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("امضای فایل PNG معتبر نیست.")
        return
    if extension == ".csv":
        data = path.read_bytes()
        if b"\x00" in data:
            raise ValueError("ساختار فایل CSV معتبر نیست.")
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("فایل CSV باید متن UTF-8 معتبر باشد.") from exc
        return
    _validate_ooxml(path, extension)


def _validate_ooxml(path: Path, extension: str) -> None:
    required_part = "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
    required_content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        if extension == ".docx"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
    )
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = {item.filename for item in infos}
            if (
                "[Content_Types].xml" not in names
                or "_rels/.rels" not in names
                or required_part not in names
                or any(item.flag_bits & 0x1 for item in infos)
                or any("vbaproject.bin" in item.filename.lower() for item in infos)
                or sum(item.file_size for item in infos) > MAX_OOXML_UNCOMPRESSED_BYTES
            ):
                raise ValueError("ساختار محفظه OOXML معتبر نیست.")
            content_types = archive.read("[Content_Types].xml", pwd=None)
    except (OSError, KeyError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError("ساختار محفظه OOXML معتبر نیست.") from exc
    if required_content_type.encode() not in content_types:
        raise ValueError("نوع محتوای داخلی OOXML با پسوند یکسان نیست.")


def _payload_fingerprint(
    *,
    organization: Organization,
    revision: QuoteRevision,
    evidence_type: str,
    evidence_slot: str,
    staged: StagedEvidence,
    expected_sha256: str,
) -> str:
    payload = {
        "organization": str(organization.pk),
        "rfq": str(revision.envelope.rfq_id),
        "rfq_version": str(revision.rfq_version_id),
        "invitation": str(revision.invitation_id),
        "envelope": str(revision.envelope_id),
        "quote_revision": str(revision.pk),
        "evidence_type": evidence_type,
        "evidence_slot": evidence_slot,
        "canonical_sha256": staged.sha256,
        "expected_sha256": expected_sha256,
        "extension": staged.extension,
        "content_type": staged.content_type,
        "file_size": staged.file_size,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _lock_and_validate_target(
    *, organization: Organization, actor: User, revision: QuoteRevision
) -> QuoteRevision:
    try:
        locked_organization = Organization.objects.select_for_update().get(
            pk=organization.pk
        )
        OrganizationMembership.objects.select_for_update().get(
            organization=locked_organization,
            user=actor,
            status=MembershipStatus.ACTIVE,
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
        envelope = QuoteEnvelope.objects.select_for_update().get(
            pk=identity["envelope_id"], organization=organization
        )
        locked_revision = (
            QuoteRevision.objects.select_for_update()
            .select_related(
                "envelope__rfq__project", "invitation__rfq_version", "rfq_version"
            )
            .get(pk=revision.pk, organization=organization)
        )
    except (
        Organization.DoesNotExist,
        OrganizationMembership.DoesNotExist,
        QuoteRevision.DoesNotExist,
        RequestForQuotation.DoesNotExist,
        RequestForQuotationVersion.DoesNotExist,
        RequestForQuotationInvitation.DoesNotExist,
        QuoteEnvelope.DoesNotExist,
    ) as exc:
        raise PermissionDenied("هدف نگهداری شاهد در این سازمان معتبر نیست.") from exc

    require_business_permission(
        user=actor,
        organization=locked_organization,
        permission=BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE,
        project=rfq.project,
        message="اجازه نگهداری شاهد مهروموم‌شده پیشنهاد را ندارید.",
    )
    if not locked_organization.is_active or rfq.project.deleted_at is not None:
        raise PermissionDenied("سازمان یا پروژه فعال نیست.")
    if (
        rfq.status != RequestForQuotationStatus.CLOSED
        or version.rfq_id != rfq.pk
        or version.version_number != rfq.current_version_number
        or invitation.rfq_version_id != version.pk
        or envelope.rfq_id != rfq.pk
        or envelope.supplier_id != invitation.supplier_id
        or locked_revision.envelope_id != envelope.pk
        or locked_revision.invitation_id != invitation.pk
        or locked_revision.rfq_version_id != version.pk
        or locked_revision.status != QuoteRevisionStatus.SUBMITTED
        or locked_revision.is_late
    ):
        raise ValueError("نسخه پیشنهاد در وضعیت یا زنجیره مؤثر قابل نگهداری نیست.")
    try:
        manifest = RFQCloseManifest.objects.select_for_update().get(
            rfq=rfq, effective_version=version
        )
        entry = RFQCloseManifestEntry.objects.select_for_update().get(
            manifest=manifest,
            invitation=invitation,
            effective_revision=locked_revision,
            disposition=RFQCloseEntryDisposition.EFFECTIVE_SUBMITTED,
        )
    except (RFQCloseManifest.DoesNotExist, RFQCloseManifestEntry.DoesNotExist) as exc:
        raise ValueError(
            "مانیفست نهایی بستن، این نسخه پیشنهاد را مؤثر نمی‌داند."
        ) from exc
    if entry.organization_id != organization.pk:
        raise PermissionDenied("شاهد بستن متعلق به این سازمان نیست.")
    return locked_revision


def _create_sealed_records(
    *,
    organization: Organization,
    actor: User,
    revision: QuoteRevision,
    evidence_type: str,
    evidence_slot: str,
    idempotency_key: str,
    payload_fingerprint: str,
    staged: StagedEvidence,
    stored_names: list[str],
) -> QuoteRevisionEvidence:
    existing = QuoteRevisionEvidence.objects.filter(
        quote_revision=revision, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.payload_fingerprint != payload_fingerprint:
            raise ValueError("کلید یکتا قبلاً با محموله فنی متفاوت استفاده شده است.")
        return existing
    if QuoteEvidencePackageFreeze.objects.filter(quote_revision=revision).exists():
        raise ValueError("بسته شاهد این نسخه برای گشایش به‌طور دائمی منجمد شده است.")

    evidence_items = QuoteRevisionEvidence.objects.filter(quote_revision=revision)
    original_exists = evidence_items.filter(
        evidence_type=QuoteEvidenceType.SUPPLIER_ORIGINAL
    ).exists()
    attachment_count = evidence_items.filter(
        evidence_type=QuoteEvidenceType.SUPPLIER_ATTACHMENT
    ).count()
    if evidence_type == QuoteEvidenceType.SUPPLIER_ORIGINAL and original_exists:
        raise ValueError("نسخه اصلی تأمین‌کننده قبلاً پذیرفته شده است.")
    if evidence_type == QuoteEvidenceType.SUPPLIER_ATTACHMENT:
        if not original_exists:
            raise ValueError("پیش از پیوست، نسخه اصلی تأمین‌کننده باید پذیرفته شود.")
        if attachment_count >= MAX_SUPPLIER_ATTACHMENTS:
            raise ValueError("حداکثر ۲۰ پیوست تأمین‌کننده مجاز است.")
    package_size = (
        evidence_items.aggregate(total=Sum("document_version__file_size"))["total"] or 0
    )
    if package_size + staged.file_size > MAX_SEALED_PACKAGE_BYTES:
        raise ValueError("حجم کل بسته مهروموم‌شده نباید از ۱۰۰ MiB بیشتر باشد.")

    document, version, custody = create_quarantined_sealed_document(
        organization=organization,
        actor=actor,
        staged_path=staged.path,
        original_file_name=staged.original_file_name,
        content_type=staged.content_type,
        file_size=staged.file_size,
        canonical_sha256=staged.sha256,
        received_at=staged.received_at,
        stored_names=stored_names,
    )
    custodied_at = custody.custodied_at
    try:
        evidence = QuoteRevisionEvidence.objects.create(
            organization=organization,
            quote_revision=revision,
            document=document,
            document_version=version,
            sealed_custody=custody,
            evidence_type=evidence_type,
            evidence_slot=evidence_slot,
            canonical_sha256=staged.sha256,
            revision_fingerprint=revision.integrity_fingerprint,
            source_channel=QuoteEvidenceSourceChannel.INTERNAL_CUSTODY_CAPTURE,
            captured_by=actor,
            received_at=staged.received_at,
            custodied_at=custodied_at,
            idempotency_key=idempotency_key,
            payload_fingerprint=payload_fingerprint,
        )
    except IntegrityError as exc:
        raise ValueError(
            "پذیرش هم‌زمان شاهد متعارض بود؛ با همان کلید دوباره تلاش کنید."
        ) from exc
    record_audit_event(
        action=AuditAction.RFQ_SEALED_EVIDENCE_CUSTODIED,
        entity_type="quote_revision_evidence",
        entity_id=evidence.pk,
        organization=organization,
        actor=actor,
        metadata={
            "quote_revision_id": str(revision.pk),
            "document_id": str(document.pk),
            "document_version_id": str(version.pk),
            "sealed_custody_id": str(custody.pk),
            "evidence_type": evidence_type,
            "evidence_slot": evidence_slot,
            "canonical_sha256": staged.sha256,
            "revision_fingerprint": revision.integrity_fingerprint,
            "source_channel": QuoteEvidenceSourceChannel.INTERNAL_CUSTODY_CAPTURE,
            "retention_classification": SEALED_RETENTION_CLASSIFICATION,
            "custody_state": SealedCustodyState.QUARANTINED,
            "file_size": staged.file_size,
            "payload_fingerprint": payload_fingerprint,
        },
    )
    return evidence


def _record_rejection(
    *,
    organization: Organization,
    actor: User,
    revision: QuoteRevision,
    evidence_type: str,
    evidence_slot: str,
    idempotency_key: str,
    failure_code: str,
    temporary_cleanup_failed: bool = False,
) -> None:
    actor_is_member = organization.memberships.filter(
        user=actor, status=MembershipStatus.ACTIVE
    ).exists()
    audit_type = (
        evidence_type if evidence_type in QuoteEvidenceType.values else "invalid"
    )
    audit_slot = (
        evidence_slot
        if re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", evidence_slot)
        else "invalid"
    )
    record_audit_event(
        action=AuditAction.RFQ_SEALED_EVIDENCE_REJECTED,
        entity_type="quote_revision",
        entity_id=revision.pk,
        organization=organization,
        actor=actor if actor_is_member else None,
        metadata={
            "attempted_actor_id": str(actor.pk),
            "evidence_type": audit_type,
            "evidence_slot": audit_slot,
            "idempotency_key_sha256": hashlib.sha256(
                idempotency_key.encode()
            ).hexdigest(),
            "failure_code": failure_code,
            "temporary_cleanup_failed": temporary_cleanup_failed,
            "content_recorded": False,
        },
    )


def custody_sealed_quote_evidence(
    *,
    organization: Organization,
    actor: User,
    quote_revision: QuoteRevision,
    evidence_type: str,
    evidence_slot: str,
    upload: UploadedFile,
    idempotency_key: str,
    expected_sha256: str = "",
) -> QuoteRevisionEvidence:
    """Atomically accept one sealed item into unavailable pre-production custody."""

    normalized_type = str(evidence_type).strip()
    normalized_slot = "unvalidated"
    key = str(idempotency_key).strip()
    staged: StagedEvidence | None = None
    stored_names: list[str] = []
    cleanup_failed = False
    try:
        if normalized_type not in QuoteEvidenceType.values:
            raise ValueError("نوع شاهد پیشنهاد معتبر نیست.")
        normalized_slot = (
            "primary"
            if normalized_type == QuoteEvidenceType.SUPPLIER_ORIGINAL
            else _safe_technical_key(
                evidence_slot, label="شناسه فنی قلم شاهد", max_length=80
            )
        )
        key = _safe_technical_key(
            idempotency_key, label="کلید یکتای نگهداری", max_length=128
        )
        normalized_expected = expected_sha256.strip().lower()
        if normalized_expected and not re.fullmatch(
            r"[0-9a-f]{64}", normalized_expected
        ):
            raise ValueError("هش مورد انتظار SHA-256 معتبر نیست.")
        staged = _stage_upload(upload)
        if normalized_expected and normalized_expected != staged.sha256:
            raise ValueError("هش مورد انتظار با هش مرجع بایت‌ها یکسان نیست.")
        payload_fingerprint = _payload_fingerprint(
            organization=organization,
            revision=quote_revision,
            evidence_type=normalized_type,
            evidence_slot=normalized_slot,
            staged=staged,
            expected_sha256=normalized_expected,
        )
        with transaction.atomic():
            locked_revision = _lock_and_validate_target(
                organization=organization,
                actor=actor,
                revision=quote_revision,
            )
            return _create_sealed_records(
                organization=organization,
                actor=actor,
                revision=locked_revision,
                evidence_type=normalized_type,
                evidence_slot=normalized_slot,
                idempotency_key=key,
                payload_fingerprint=payload_fingerprint,
                staged=staged,
                stored_names=stored_names,
            )
    except Exception as exc:
        for stored_name in stored_names:
            try:
                DocumentVersion._meta.get_field("file").storage.delete(stored_name)
            except OSError:
                cleanup_failed = True
        _record_rejection(
            organization=organization,
            actor=actor,
            revision=quote_revision,
            evidence_type=normalized_type,
            evidence_slot=normalized_slot,
            idempotency_key=key,
            failure_code=type(exc).__name__,
            temporary_cleanup_failed=cleanup_failed,
        )
        raise
    finally:
        if staged is not None:
            try:
                staged.path.unlink(missing_ok=True)
            except OSError:
                cleanup_failed = True
                _record_rejection(
                    organization=organization,
                    actor=actor,
                    revision=quote_revision,
                    evidence_type=normalized_type,
                    evidence_slot=normalized_slot,
                    idempotency_key=key,
                    failure_code="TemporaryCleanupFailure",
                    temporary_cleanup_failed=True,
                )
