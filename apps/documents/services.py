import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.models import DocumentType, ProjectDocument
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.payments.models import Payment
from apps.projects.models import Project

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = {
    ".pdf": {"application/pdf"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
}
FILE_SIGNATURES = {
    ".pdf": b"%PDF-",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89PNG\r\n\x1a\n",
}


def _can_manage_documents(user: User, organization: Organization) -> bool:
    return organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
        role__in=[
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        ],
    ).exists()


def _validate_access(*, user: User, organization: Organization) -> None:
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    if not organization.memberships.filter(
        user=user,
        status=MembershipStatus.ACTIVE,
    ).exists():
        raise PermissionDenied("You do not have access to this organization.")


def _validate_upload_context(
    *,
    actor: User,
    organization: Organization,
    project: Project,
    payment: Payment | None,
) -> None:
    _validate_access(user=actor, organization=organization)
    if not _can_manage_documents(actor, organization):
        raise PermissionDenied("You cannot upload documents in this organization.")
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")
    if payment and (
        payment.organization_id != organization.pk
        or payment.project_id != project.pk
        or payment.project.deleted_at is not None
    ):
        raise PermissionDenied("The payment does not belong to this project.")


def _validate_uploaded_file(upload: "UploadedFile") -> tuple[str, int, str]:
    file_name = Path(upload.name).name
    extension = Path(file_name).suffix.lower()
    content_type = getattr(upload, "content_type", "")
    if extension not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError("Only PDF, JPEG, and PNG files are allowed.")
    if content_type not in ALLOWED_DOCUMENT_TYPES[extension]:
        raise ValueError("The uploaded file type does not match its extension.")
    if upload.size <= 0:
        raise ValueError("The uploaded file is empty.")
    if upload.size > MAX_DOCUMENT_SIZE:
        raise ValueError("Uploaded files must not exceed 10 MB.")
    signature = upload.read(8)
    upload.seek(0)
    if not signature.startswith(FILE_SIGNATURES[extension]):
        raise ValueError("The uploaded file contents are not a valid file type.")

    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return file_name, upload.size, digest.hexdigest()


@transaction.atomic
def upload_project_document(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    document_type: str,
    title: str,
    upload: "UploadedFile",
    payment: Payment | None = None,
) -> ProjectDocument:
    """Store validated private document metadata and its uploaded file."""

    _validate_upload_context(
        actor=actor,
        organization=organization,
        project=project,
        payment=payment,
    )
    if document_type not in DocumentType.values:
        raise ValueError("Invalid document type.")
    if not title.strip():
        raise ValueError("Document title is required.")

    original_file_name, file_size, sha256 = _validate_uploaded_file(upload)
    document = ProjectDocument.objects.create(
        organization=organization,
        project=project,
        payment=payment,
        document_type=document_type,
        title=title.strip(),
        original_file_name=original_file_name,
        file=upload,
        content_type=upload.content_type,
        file_size=file_size,
        sha256=sha256,
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_UPLOADED,
        entity_type="project_document",
        entity_id=document.pk,
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "payment_id": str(payment.pk) if payment else None,
            "document_type": document.document_type,
            "file_size": document.file_size,
            "sha256": document.sha256,
        },
    )
    return document


def get_organization_documents(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[ProjectDocument]:
    """Return non-archived private documents visible to an active member."""

    _validate_access(user=user, organization=organization)
    return (
        ProjectDocument.objects.filter(
            organization=organization,
            archived_at__isnull=True,
            project__deleted_at__isnull=True,
        )
        .select_related("project", "payment", "created_by")
        .order_by("-created_at")
    )


def get_organization_document(
    *,
    user: User,
    organization: Organization,
    document_id: str,
) -> ProjectDocument:
    """Resolve one document only after tenant and membership validation."""

    _validate_access(user=user, organization=organization)
    document = (
        ProjectDocument.objects.filter(
            pk=document_id,
            organization=organization,
            archived_at__isnull=True,
            project__deleted_at__isnull=True,
        )
        .select_related("project", "payment")
        .first()
    )
    if document is None:
        raise PermissionDenied("Document not found in this organization.")
    return document


def record_document_download(*, document: ProjectDocument, actor: User) -> None:
    """Audit an authorized private-document download."""

    _validate_access(user=actor, organization=document.organization)
    is_available = ProjectDocument.objects.filter(
        pk=document.pk,
        organization=document.organization,
        archived_at__isnull=True,
        project__deleted_at__isnull=True,
    ).exists()
    if not is_available:
        raise PermissionDenied("Document not found in this organization.")
    record_audit_event(
        action=AuditAction.DOCUMENT_DOWNLOADED,
        entity_type="project_document",
        entity_id=document.pk,
        organization=document.organization,
        actor=actor,
        metadata={"project_id": str(document.project_id)},
    )


@transaction.atomic
def archive_project_document(
    *,
    document: ProjectDocument,
    actor: User,
    reason: str,
) -> ProjectDocument:
    """Archive a document without deleting its metadata or stored evidence."""

    locked_document = (
        ProjectDocument.objects.select_for_update()
        .select_related("organization", "project")
        .get(pk=document.pk)
    )
    _validate_access(user=actor, organization=locked_document.organization)
    if not _can_manage_documents(actor, locked_document.organization):
        raise PermissionDenied("You cannot archive documents in this organization.")
    if locked_document.project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")
    if locked_document.archived_at is not None:
        raise ValueError("This document is already archived.")
    if not reason.strip():
        raise ValueError("An archive reason is required.")

    locked_document.archive_reason = reason.strip()
    locked_document.archived_at = timezone.now()
    locked_document.archived_by = actor
    locked_document.save(update_fields=["archive_reason", "archived_at", "archived_by"])
    record_audit_event(
        action=AuditAction.DOCUMENT_ARCHIVED,
        entity_type="project_document",
        entity_id=locked_document.pk,
        organization=locked_document.organization,
        actor=actor,
        metadata={
            "project_id": str(locked_document.project_id),
            "reason": locked_document.archive_reason,
        },
    )
    return locked_document
