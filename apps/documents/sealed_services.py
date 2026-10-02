"""Documents-owned persistence for pre-production sealed supplier evidence."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from django.core.files import File
from django.utils import timezone

from apps.accounts.models import User
from apps.documents.models import (
    Document,
    DocumentConfidentiality,
    DocumentRetentionClassification,
    DocumentType,
    DocumentVersion,
    SealedCustodyState,
    SealedDocumentCustody,
)
from apps.documents.services import _allocate_document_number
from apps.organizations.models import Organization


def create_quarantined_sealed_document(
    *,
    organization: Organization,
    actor: User,
    staged_path: Path,
    original_file_name: str,
    content_type: str,
    file_size: int,
    canonical_sha256: str,
    received_at: datetime,
    stored_names: list[str],
) -> tuple[Document, DocumentVersion, SealedDocumentCustody]:
    """Persist immutable DMS identities and verify the protected stored bytes."""

    document = Document(
        organization=organization,
        document_number=_allocate_document_number(organization=organization),
        document_type=DocumentType.OTHER,
        confidentiality=DocumentConfidentiality.RESTRICTED,
        retention_classification=DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE,
        title="sealed-evidence",
        created_by=actor,
        updated_by=actor,
    )
    document.title = f"sealed-evidence-{document.pk}"
    document.save()
    version = DocumentVersion(
        organization=organization,
        document=document,
        version_number=1,
        original_file_name=original_file_name,
        content_type=content_type,
        file_size=file_size,
        sha256=canonical_sha256,
        uploaded_by=actor,
    )
    with staged_path.open("rb") as source:
        version.file.save(original_file_name, File(source), save=False)
    stored_names.append(version.file.name)
    version.save()
    document.current_version = version
    document.save(update_fields=["current_version", "updated_at"])

    post_write_hash = hashlib.sha256()
    with version.file.open("rb") as stored_file:
        for chunk in iter(lambda: stored_file.read(65536), b""):
            post_write_hash.update(chunk)
    if post_write_hash.hexdigest() != canonical_sha256:
        raise ValueError("کنترل یکپارچگی پس از ذخیره‌سازی ناموفق بود.")

    custodied_at = timezone.now()
    custody = SealedDocumentCustody.objects.create(
        organization=organization,
        document_version=version,
        retention_classification=DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE,
        state=SealedCustodyState.QUARANTINED,
        canonical_sha256=canonical_sha256,
        received_at=received_at,
        custodied_at=custodied_at,
        captured_by=actor,
    )
    return document, version, custody
