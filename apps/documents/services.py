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
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
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


def _validate_access(
    *,
    user: User,
    organization: Organization,
    permission: BusinessPermissionCode,
) -> None:
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("ورود به حساب کاربری الزامی است.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("سازمان فعال نیست.")
    require_business_permission(
        user=user,
        organization=organization,
        permission=permission,
        message="اجازه انجام این عملیات روی اسناد پروژه را ندارید.",
    )


def _validate_upload_context(
    *,
    actor: User,
    organization: Organization,
    project: Project,
    payment: Payment | None,
) -> None:
    _validate_access(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENTS_UPLOAD,
    )
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")
    if payment and (
        payment.organization_id != organization.pk
        or payment.project_id != project.pk
        or payment.project.deleted_at is not None
    ):
        raise PermissionDenied("پرداخت متعلق به این پروژه نیست.")


def _validate_uploaded_file(upload: "UploadedFile") -> tuple[str, int, str]:
    file_name = Path(upload.name).name
    extension = Path(file_name).suffix.lower()
    content_type = getattr(upload, "content_type", "")
    if extension not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError("فقط فایل‌های PDF، JPEG و PNG مجاز هستند.")
    if content_type not in ALLOWED_DOCUMENT_TYPES[extension]:
        raise ValueError("نوع فایل بارگذاری‌شده با پسوند آن مطابقت ندارد.")
    if upload.size <= 0:
        raise ValueError("فایل بارگذاری‌شده خالی است.")
    if upload.size > MAX_DOCUMENT_SIZE:
        raise ValueError("حجم فایل بارگذاری‌شده نباید بیشتر از ۱۰ مگابایت باشد.")
    signature = upload.read(8)
    upload.seek(0)
    if not signature.startswith(FILE_SIGNATURES[extension]):
        raise ValueError("محتوای فایل بارگذاری‌شده معتبر نیست.")

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
        raise ValueError("نوع سند معتبر نیست.")
    if not title.strip():
        raise ValueError("وارد کردن عنوان سند الزامی است.")

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

    _validate_access(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENTS_VIEW,
    )
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

    _validate_access(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENTS_VIEW,
    )
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
        raise PermissionDenied("سند در این سازمان یافت نشد.")
    return document


def record_document_download(*, document: ProjectDocument, actor: User) -> None:
    """Audit an authorized private-document download."""

    _validate_access(
        user=actor,
        organization=document.organization,
        permission=BusinessPermissionCode.DOCUMENTS_DOWNLOAD,
    )
    is_available = ProjectDocument.objects.filter(
        pk=document.pk,
        organization=document.organization,
        archived_at__isnull=True,
        project__deleted_at__isnull=True,
    ).exists()
    if not is_available:
        raise PermissionDenied("سند در این سازمان یافت نشد.")
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
    _validate_access(
        user=actor,
        organization=locked_document.organization,
        permission=BusinessPermissionCode.DOCUMENTS_ARCHIVE,
    )
    if locked_document.project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")
    if locked_document.archived_at is not None:
        raise ValueError("سند از قبل بایگانی شده است.")
    if not reason.strip():
        raise ValueError("وارد کردن دلیل بایگانی الزامی است.")

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
