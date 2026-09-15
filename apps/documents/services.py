import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import Contract
from apps.daily_reports.models import DailyReport
from apps.documents.models import (
    DOCUMENT_LINK_TARGET_FIELDS,
    Document,
    DocumentLink,
    DocumentType,
    DocumentVersion,
)
from apps.estimates.models import Estimate
from apps.expenses.models import Expense
from apps.organizations.authorization import (
    has_business_permission,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationStatus,
)
from apps.payments.models import Payment
from apps.projects.models import Project

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile
    from django.db.models import Model


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

TARGET_MODELS = {
    "project": Project,
    "contract": Contract,
    "estimate": Estimate,
    "expense": Expense,
    "payment": Payment,
    "daily_report": DailyReport,
}
TARGET_VIEW_PERMISSIONS = {
    "project": BusinessPermissionCode.PROJECTS_VIEW,
    "contract": BusinessPermissionCode.CONTRACTS_VIEW,
    "estimate": BusinessPermissionCode.ESTIMATES_VIEW,
    "expense": BusinessPermissionCode.EXPENSES_VIEW,
    "payment": BusinessPermissionCode.PAYMENTS_VIEW,
    "daily_report": BusinessPermissionCode.DAILY_REPORTS_VIEW,
}
LINK_PREFETCHES = tuple(
    f"links__{field_name}" for field_name in DOCUMENT_LINK_TARGET_FIELDS
)


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
        message="اجازه انجام این عملیات روی اسناد را ندارید.",
    )


def _target_field(target: "Model") -> str:
    for field_name, model_class in TARGET_MODELS.items():
        if isinstance(target, model_class):
            return field_name
    raise ValueError("نوع موجودیت مرتبط با سند پشتیبانی نمی‌شود.")


def _validate_target_access(
    *, actor: User, organization: Organization, target: "Model"
) -> str:
    field_name = _target_field(target)
    if getattr(target, "organization_id", None) != organization.pk:
        raise PermissionDenied("موجودیت مرتبط متعلق به این سازمان نیست.")
    project = target if field_name == "project" else getattr(target, "project", None)
    if project is not None and project.deleted_at is not None:
        raise PermissionDenied("پروژه مرتبط بایگانی شده است.")
    require_business_permission(
        user=actor,
        organization=organization,
        permission=TARGET_VIEW_PERMISSIONS[field_name],
        message="اجازه مشاهده موجودیت مرتبط با سند را ندارید.",
    )
    return field_name


def _validate_document_context_access(
    *, document: Document, actor: User, permission: BusinessPermissionCode
) -> None:
    _validate_access(
        user=actor,
        organization=document.organization,
        permission=permission,
    )
    links = list(document.links.all())
    if not links:
        raise PermissionDenied("سند هیچ موجودیت مرتبط معتبری ندارد.")
    for link in links:
        target = link.target
        _validate_target_access(
            actor=actor,
            organization=document.organization,
            target=target,
        )


def _validate_uploaded_file(upload: "UploadedFile") -> tuple[str, int, str, str]:
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
    return file_name, upload.size, content_type, digest.hexdigest()


def _create_version(
    *,
    document: Document,
    actor: User,
    upload: "UploadedFile",
    version_number: int,
) -> DocumentVersion:
    original_file_name, file_size, content_type, sha256 = _validate_uploaded_file(
        upload
    )
    return DocumentVersion.objects.create(
        organization=document.organization,
        document=document,
        version_number=version_number,
        original_file_name=original_file_name,
        file=upload,
        content_type=content_type,
        file_size=file_size,
        sha256=sha256,
        uploaded_by=actor,
    )


@transaction.atomic
def create_document(
    *,
    organization: Organization,
    actor: User,
    document_type: str,
    title: str,
    upload: "UploadedFile",
    target: "Model",
    reference: str = "",
    description: str = "",
) -> Document:
    """Create a document, its first immutable version, and its initial link."""

    _validate_access(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENTS_UPLOAD,
    )
    target_field = _validate_target_access(
        actor=actor,
        organization=organization,
        target=target,
    )
    if document_type not in DocumentType.values:
        raise ValueError("نوع سند معتبر نیست.")
    if not title.strip():
        raise ValueError("وارد کردن عنوان سند الزامی است.")

    document = Document.objects.create(
        organization=organization,
        document_type=document_type,
        title=title.strip(),
        reference=reference.strip(),
        description=description.strip(),
        created_by=actor,
        updated_by=actor,
    )
    version = _create_version(
        document=document,
        actor=actor,
        upload=upload,
        version_number=1,
    )
    DocumentLink.objects.create(
        organization=organization,
        document=document,
        created_by=actor,
        **{target_field: target},
    )
    document.current_version = version
    document.save(update_fields=["current_version", "updated_at"])
    record_audit_event(
        action=AuditAction.DOCUMENT_UPLOADED,
        entity_type="document",
        entity_id=document.pk,
        organization=organization,
        actor=actor,
        metadata={
            "version_id": str(version.pk),
            "version_number": version.version_number,
            "target_type": target_field,
            "target_id": str(target.pk),
            "document_type": document.document_type,
            "file_size": version.file_size,
            "sha256": version.sha256,
        },
    )
    return document


@transaction.atomic
def add_document_version(
    *, document: Document, actor: User, upload: "UploadedFile"
) -> DocumentVersion:
    """Append a numbered immutable version while holding the document row lock."""

    locked_document = (
        Document.objects.select_for_update()
        .select_related("organization")
        .prefetch_related(*LINK_PREFETCHES)
        .get(pk=document.pk)
    )
    _validate_document_context_access(
        document=locked_document,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENTS_UPLOAD,
    )
    if locked_document.archived_at is not None:
        raise ValueError("برای سند بایگانی‌شده نمی‌توان نسخه جدید ساخت.")
    latest_number = (
        locked_document.versions.aggregate(latest=Max("version_number"))["latest"] or 0
    )
    version = _create_version(
        document=locked_document,
        actor=actor,
        upload=upload,
        version_number=latest_number + 1,
    )
    locked_document.current_version = version
    locked_document.updated_by = actor
    locked_document.save(update_fields=["current_version", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.DOCUMENT_VERSION_ADDED,
        entity_type="document",
        entity_id=locked_document.pk,
        organization=locked_document.organization,
        actor=actor,
        metadata={
            "version_id": str(version.pk),
            "version_number": version.version_number,
            "file_size": version.file_size,
            "sha256": version.sha256,
        },
    )
    return version


@transaction.atomic
def add_document_link(
    *, document: Document, actor: User, target: "Model"
) -> DocumentLink:
    """Attach one additional explicit, authorized, same-tenant context."""

    locked_document = (
        Document.objects.select_for_update()
        .select_related("organization")
        .prefetch_related(*LINK_PREFETCHES)
        .get(pk=document.pk)
    )
    _validate_document_context_access(
        document=locked_document,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENTS_UPLOAD,
    )
    if locked_document.archived_at is not None:
        raise ValueError("برای سند بایگانی‌شده نمی‌توان لینک جدید ساخت.")
    target_field = _validate_target_access(
        actor=actor,
        organization=locked_document.organization,
        target=target,
    )
    link = DocumentLink.objects.create(
        organization=locked_document.organization,
        document=locked_document,
        created_by=actor,
        **{target_field: target},
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_LINK_ADDED,
        entity_type="document",
        entity_id=locked_document.pk,
        organization=locked_document.organization,
        actor=actor,
        metadata={"target_type": target_field, "target_id": str(target.pk)},
    )
    return link


def _with_document_context(queryset: QuerySet[Document]) -> QuerySet[Document]:
    return queryset.select_related("organization", "current_version").prefetch_related(
        "versions",
        *LINK_PREFETCHES,
    )


def get_organization_documents(
    *, user: User, organization: Organization
) -> QuerySet[Document]:
    """Return active documents whose every linked context the actor may view."""

    _validate_access(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENTS_VIEW,
    )
    documents = Document.objects.filter(
        organization=organization,
        archived_at__isnull=True,
        current_version__isnull=False,
        links__isnull=False,
    )
    for field_name, permission in TARGET_VIEW_PERMISSIONS.items():
        if not has_business_permission(
            user=user,
            organization=organization,
            permission=permission,
        ):
            documents = documents.exclude(**{f"links__{field_name}__isnull": False})
    return _with_document_context(documents.distinct()).order_by("-created_at")


def get_organization_document(
    *, user: User, organization: Organization, document_id: str
) -> Document:
    """Resolve one active document and enforce all linked context permissions."""

    _validate_access(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENTS_VIEW,
    )
    document = _with_document_context(
        Document.objects.filter(
            pk=document_id,
            organization=organization,
            archived_at__isnull=True,
            current_version__isnull=False,
        )
    ).first()
    if document is None:
        raise PermissionDenied("سند در این سازمان یافت نشد.")
    _validate_document_context_access(
        document=document,
        actor=user,
        permission=BusinessPermissionCode.DOCUMENTS_VIEW,
    )
    return document


def get_document_version_for_download(
    *, document: Document, version_id: str, actor: User
) -> DocumentVersion:
    """Resolve an authorized version without exposing its storage URL."""

    _validate_document_context_access(
        document=document,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENTS_DOWNLOAD,
    )
    version = DocumentVersion.objects.filter(
        pk=version_id,
        document=document,
        organization=document.organization,
    ).first()
    if version is None:
        raise PermissionDenied("نسخه سند در این سازمان یافت نشد.")
    return version


def record_document_download(*, version: DocumentVersion, actor: User) -> None:
    """Audit an authorized private-version download."""

    document = _with_document_context(
        Document.objects.filter(pk=version.document_id)
    ).get()
    _validate_document_context_access(
        document=document,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENTS_DOWNLOAD,
    )
    if document.archived_at is not None:
        raise PermissionDenied("سند در این سازمان یافت نشد.")
    record_audit_event(
        action=AuditAction.DOCUMENT_DOWNLOADED,
        entity_type="document",
        entity_id=document.pk,
        organization=document.organization,
        actor=actor,
        metadata={
            "version_id": str(version.pk),
            "version_number": version.version_number,
        },
    )


@transaction.atomic
def archive_document(*, document: Document, actor: User, reason: str) -> Document:
    """Archive a document without deleting its links, versions, or stored files."""

    locked_document = (
        Document.objects.select_for_update()
        .select_related("organization")
        .prefetch_related(*LINK_PREFETCHES)
        .get(pk=document.pk)
    )
    _validate_document_context_access(
        document=locked_document,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENTS_ARCHIVE,
    )
    if locked_document.archived_at is not None:
        raise ValueError("سند از قبل بایگانی شده است.")
    if not reason.strip():
        raise ValueError("وارد کردن دلیل بایگانی الزامی است.")

    locked_document.archive_reason = reason.strip()
    locked_document.archived_at = timezone.now()
    locked_document.archived_by = actor
    locked_document.updated_by = actor
    locked_document.save(
        update_fields=[
            "archive_reason",
            "archived_at",
            "archived_by",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_ARCHIVED,
        entity_type="document",
        entity_id=locked_document.pk,
        organization=locked_document.organization,
        actor=actor,
        metadata={"reason": locked_document.archive_reason},
    )
    return locked_document
