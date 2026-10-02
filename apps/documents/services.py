import hashlib
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from django.contrib.postgres.search import SearchQuery, SearchVector
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, OuterRef, Q, QuerySet, Subquery
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import Contract
from apps.daily_reports.models import DailyReport
from apps.documents.link_registry import (
    DOCUMENT_LINK_TYPES,
    create_typed_link,
    typed_links_for_document,
)
from apps.documents.models import (
    DOCUMENT_LINK_TARGET_FIELDS,
    DisposalIntentState,
    Document,
    DocumentCategory,
    DocumentConfidentiality,
    DocumentDisposalIntent,
    DocumentExportManifest,
    DocumentKeyCustodyAttestation,
    DocumentLegalHold,
    DocumentLink,
    DocumentNumberSequence,
    DocumentProcessingAssessment,
    DocumentProcessingVerdict,
    DocumentRecoveryManifest,
    DocumentRetentionApplication,
    DocumentRetentionClassification,
    DocumentRetentionPolicy,
    DocumentRetentionPolicyVersion,
    DocumentSignatureEvidence,
    DocumentType,
    DocumentVersion,
    ManifestCompleteness,
    RecoveryEvidenceState,
    RetentionPolicyVersionState,
    RetentionTrigger,
    SignatureVerificationState,
)
from apps.estimates.models import Estimate
from apps.expenses.models import Expense
from apps.materials.models import Material
from apps.organizations.authorization import (
    effective_scope_grants,
    get_active_membership,
    has_platform_role,
    membership_has_permission,
    membership_has_scope,
    membership_is_tenant_owner,
    require_business_permission,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermissionCode,
    Organization,
    OrganizationSettings,
    OrganizationStatus,
    PlatformRoleCode,
    ProtectedOperation,
    ProtectedOperationCode,
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
    "material": Material,
    "project": Project,
    "contract": Contract,
    "estimate": Estimate,
    "expense": Expense,
    "payment": Payment,
    "daily_report": DailyReport,
}
TARGET_VIEW_PERMISSIONS = {
    "material": BusinessPermissionCode.MATERIALS_VIEW,
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


def _allocate_document_number(*, organization: Organization) -> str:
    settings_record = OrganizationSettings.objects.select_for_update().get(
        organization=organization
    )
    sequence, _ = DocumentNumberSequence.objects.select_for_update().get_or_create(
        organization=organization
    )
    value = sequence.next_value
    sequence.next_value = value + 1
    sequence.save(update_fields=["next_value", "updated_at"])
    return f"{settings_record.document_code_prefix}-{value:06d}"


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
        allow_any_scope=True,
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
    site = getattr(target, "site", None)
    if project is not None and project.deleted_at is not None:
        raise PermissionDenied("پروژه مرتبط بایگانی شده است.")
    require_business_permission(
        user=actor,
        organization=organization,
        permission=TARGET_VIEW_PERMISSIONS[field_name],
        project=project,
        site=site,
        message="اجازه مشاهده موجودیت مرتبط با سند را ندارید.",
    )
    return field_name


def _validate_document_context_access(
    *, document: Document, actor: User, permission: BusinessPermissionCode
) -> None:
    if (
        document.retention_classification
        == DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
    ):
        raise PermissionDenied("شاهد مهروموم‌شده پیش از گشایش قابل دسترسی نیست.")
    _validate_access(
        user=actor,
        organization=document.organization,
        permission=permission,
    )
    if document.access_expires_at and document.access_expires_at <= timezone.now():
        raise PermissionDenied("دسترسی به سند منقضی شده است.")
    links = typed_links_for_document(document)
    if not links:
        raise PermissionDenied("سند هیچ موجودیت مرتبط معتبری ندارد.")
    legacy_link_ids = set(document.links.values_list("pk", flat=True))
    typed_link_ids = {
        link.pk
        for link in links
        if next(item for item in DOCUMENT_LINK_TYPES if item.key == link.target_type).legacy_compatible
    }
    if legacy_link_ids != typed_link_ids:
        raise PermissionDenied("نگاشت لینک‌های سند کامل و قابل اتکا نیست.")
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
    category: DocumentCategory | None = None,
    confidentiality: str = DocumentConfidentiality.INTERNAL,
    access_expires_at: datetime | None = None,
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
    if target_field == "material":
        _validate_access(
            user=actor,
            organization=organization,
            permission=BusinessPermissionCode.MATERIAL_DOCUMENTS_LINK,
        )
    if document_type not in DocumentType.values:
        raise ValueError("نوع سند معتبر نیست.")
    if not title.strip():
        raise ValueError("وارد کردن عنوان سند الزامی است.")
    if confidentiality not in DocumentConfidentiality.values:
        raise ValueError("سطح محرمانگی سند معتبر نیست.")
    if category is not None and (
        category.organization_id != organization.pk or category.archived_at
    ):
        raise PermissionDenied("دسته‌بندی فعال متعلق به این سازمان نیست.")

    document = Document.objects.create(
        organization=organization,
        document_number=_allocate_document_number(organization=organization),
        document_type=document_type,
        category=category,
        confidentiality=confidentiality,
        access_expires_at=access_expires_at,
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
    document.current_version = version
    document.save(update_fields=["current_version", "updated_at"])
    if target_field == "material":
        create_typed_link(
            organization=organization,
            document=document,
            created_by=actor,
            document_version=version,
            target_type=target_field,
            target=target,
        )
    else:
        legacy_link = DocumentLink.objects.create(
            organization=organization,
            document=document,
            created_by=actor,
            **{target_field: target},
        )
        create_typed_link(
            legacy_link=legacy_link,
            target_type=target_field,
            target=target,
        )
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
            "document_number": document.document_number,
            "confidentiality": document.confidentiality,
            "file_size": version.file_size,
            "sha256": version.sha256,
        },
    )
    return document


@transaction.atomic
def create_document_category(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    description: str = "",
) -> DocumentCategory:
    _validate_access(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.DOCUMENT_CATEGORIES_MANAGE,
    )
    category = DocumentCategory(
        organization=organization,
        code=code,
        name=name,
        description=description.strip(),
        created_by=actor,
    )
    category.save()
    record_audit_event(
        action=AuditAction.DOCUMENT_CATEGORY_CREATED,
        entity_type="document_category",
        entity_id=category.pk,
        organization=organization,
        actor=actor,
        metadata={"code": category.code},
    )
    return category


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
def add_document_link(*, document: Document, actor: User, target: "Model") -> "Model":
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
    if target_field == "material":
        _validate_access(
            user=actor,
            organization=locked_document.organization,
            permission=BusinessPermissionCode.MATERIAL_DOCUMENTS_LINK,
        )
    if target_field == "material":
        link = create_typed_link(
            organization=locked_document.organization,
            document=locked_document,
            created_by=actor,
            target_type=target_field,
            target=target,
        )
    else:
        link = DocumentLink.objects.create(
            organization=locked_document.organization,
            document=locked_document,
            created_by=actor,
            **{target_field: target},
        )
        create_typed_link(
            legacy_link=link,
            target_type=target_field,
            target=target,
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
        "versions__processing_assessments",
        "versions__signature_evidence",
        "retention_applications__policy_version",
        "legal_holds",
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
    documents = (
        Document.objects.filter(
            organization=organization,
            archived_at__isnull=True,
            current_version__isnull=False,
        )
        .exclude(
            retention_classification=DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
        )
        .filter(
            Q(access_expires_at__isnull=True) | Q(access_expires_at__gt=timezone.now())
        )
    )
    linked_documents = Q(pk__in=[])
    for link_type in DOCUMENT_LINK_TYPES:
        linked_documents |= Q(
            pk__in=link_type.model.objects.filter(organization=organization).values(
                "document_id"
            )
        )
    documents = documents.filter(linked_documents)
    membership = get_active_membership(user=user, organization=organization)
    for link_type in DOCUMENT_LINK_TYPES:
        registered_links = link_type.model.objects.filter(organization=organization)
        if not membership_has_permission(membership, link_type.view_permission):
            documents = documents.exclude(pk__in=registered_links.values("document_id"))
    grants = effective_scope_grants(membership)
    if not membership_has_scope(membership):
        project_ids = list(
            grants.filter(scope_type=AuthorizationScopeType.PROJECT).values_list(
                "project_id", flat=True
            )
        )
        site_grants = grants.filter(scope_type=AuthorizationScopeType.SITE)
        site_ids = list(site_grants.values_list("site_id", flat=True))
        for link_type in DOCUMENT_LINK_TYPES:
            allowed = (
                Q(**{f"{link_type.project_lookup}__in": project_ids})
                if link_type.project_lookup
                else Q(pk__in=[])
            )
            if link_type.site_lookup:
                allowed |= Q(**{f"{link_type.site_lookup}__in": site_ids})
            denied_document_ids = (
                link_type.model.objects.filter(organization=organization)
                .exclude(allowed)
                .values("document_id")
            )
            documents = documents.exclude(pk__in=denied_document_ids)
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
        ).exclude(
            retention_classification=DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
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
    if not version.is_available:
        raise PermissionDenied("نسخه سند هنوز برای استفاده ایمن در دسترس نیست.")
    return version


@transaction.atomic
def record_document_processing_assessment(
    *,
    version: DocumentVersion,
    actor: User,
    verdict: str,
    adapter_code: str,
    adapter_version: str = "",
    provider_reference: str = "",
    extracted_text: str = "",
    details: dict[str, object] | None = None,
    correlation_id: uuid.UUID | None = None,
) -> DocumentProcessingAssessment:
    """Append a scanner/OCR result under the Platform Operations duty."""

    if not has_platform_role(actor, PlatformRoleCode.PLATFORM_OPERATIONS):
        raise PermissionDenied("نقش فعال Platform Operations الزامی است.")
    if verdict not in DocumentProcessingVerdict.values:
        raise ValueError("نتیجه ارزیابی پردازش معتبر نیست.")
    locked_version = (
        DocumentVersion.objects.select_for_update()
        .select_related("document", "organization")
        .get(pk=version.pk)
    )
    if (
        locked_version.document.retention_classification
        == DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
        and (extracted_text or details or provider_reference)
    ):
        raise PermissionDenied(
            "پردازش شاهد مهروموم‌شده فقط می‌تواند نتیجه فنی بدون محتوای مشتق ثبت کند."
        )
    sequence = (
        locked_version.processing_assessments.aggregate(latest=Max("sequence"))[
            "latest"
        ]
        or 0
    ) + 1
    assessment = DocumentProcessingAssessment.objects.create(
        organization=locked_version.organization,
        version=locked_version,
        sequence=sequence,
        verdict=verdict,
        input_sha256=locked_version.sha256,
        adapter_code=adapter_code.strip(),
        adapter_version=adapter_version.strip(),
        provider_reference=provider_reference.strip(),
        extracted_text=extracted_text if verdict == DocumentProcessingVerdict.CLEAN else "",
        details=details or {},
        recorded_by=actor,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_PROCESSING_ASSESSED,
        entity_type="document_version",
        entity_id=locked_version.pk,
        organization=locked_version.organization,
        actor=actor,
        allow_platform_actor=True,
        correlation_id=correlation_id,
        changes={"availability": {"to": verdict}},
        metadata={
            "assessment_id": str(assessment.pk),
            "sequence": sequence,
            "adapter_code": assessment.adapter_code,
            "input_sha256": assessment.input_sha256,
        },
    )
    return assessment


@transaction.atomic
def record_document_signature_evidence(
    *,
    version: DocumentVersion,
    actor: User,
    verification_state: str = SignatureVerificationState.UNKNOWN,
    provider_code: str = "",
    provider_reference: str = "",
    standard_code: str = "",
    evidence: dict[str, object] | None = None,
) -> DocumentSignatureEvidence:
    """Record provider-neutral evidence without asserting legal signature effect."""

    if not has_platform_role(actor, PlatformRoleCode.PLATFORM_OPERATIONS):
        raise PermissionDenied("نقش فعال Platform Operations الزامی است.")
    if (
        version.document.retention_classification
        == DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
    ):
        raise PermissionDenied("شاهد امضای محتوای مهروموم‌شده در این مرحله مجاز نیست.")
    if verification_state not in SignatureVerificationState.values:
        raise ValueError("وضعیت راستی‌آزمایی امضا معتبر نیست.")
    signature = DocumentSignatureEvidence.objects.create(
        organization=version.organization,
        version=version,
        verification_state=verification_state,
        provider_code=provider_code.strip(),
        provider_reference=provider_reference.strip(),
        standard_code=standard_code.strip(),
        evidence=evidence or {},
        recorded_by=actor,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_SIGNATURE_EVIDENCE_RECORDED,
        entity_type="document_version",
        entity_id=version.pk,
        organization=version.organization,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "signature_evidence_id": str(signature.pk),
            "verification_state": signature.verification_state,
        },
    )
    return signature


def search_organization_documents(
    *, user: User, organization: Organization, query: str
) -> QuerySet[Document]:
    """PostgreSQL search over authorized metadata and clean extracted text."""

    normalized_query = query.strip()
    accessible = get_organization_documents(user=user, organization=organization)
    if not normalized_query:
        return accessible.none()
    search_query = SearchQuery(normalized_query, search_type="websearch")
    metadata_ids = (
        accessible.annotate(
            document_search=SearchVector("title", "reference", "description")
        )
        .filter(document_search=search_query)
        .values("pk")
    )
    latest_assessment_id = (
        DocumentProcessingAssessment.objects.filter(version_id=OuterRef("version_id"))
        .order_by("-sequence")
        .values("pk")[:1]
    )
    content_ids = (
        DocumentProcessingAssessment.objects.filter(
            organization=organization,
            verdict=DocumentProcessingVerdict.CLEAN,
        )
        .annotate(
            latest_assessment_id=Subquery(latest_assessment_id),
            content_search=SearchVector("extracted_text"),
        )
        .filter(pk=Subquery(latest_assessment_id))
        .filter(content_search=search_query)
        .values("version__document_id")
    )
    return accessible.filter(Q(pk__in=metadata_ids) | Q(pk__in=content_ids)).distinct()


def compare_document_versions(
    *,
    document: Document,
    actor: User,
    left_version_id: object,
    right_version_id: object,
) -> dict[str, object]:
    """Return permission-checked immutable metadata and available text snapshots."""

    _validate_document_context_access(
        document=document,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENTS_VIEW,
    )
    versions = {
        version.pk: version
        for version in DocumentVersion.objects.filter(
            document=document,
            pk__in=[left_version_id, right_version_id],
        )
    }
    try:
        left = versions[uuid.UUID(str(left_version_id))]
        right = versions[uuid.UUID(str(right_version_id))]
    except (KeyError, ValueError) as exc:
        raise PermissionDenied("نسخه‌های سند برای مقایسه یافت نشدند.") from exc

    def snapshot(version: DocumentVersion) -> dict[str, object]:
        assessment = version.latest_processing_assessment
        return {
            "id": str(version.pk),
            "version_number": version.version_number,
            "sha256": version.sha256,
            "file_size": version.file_size,
            "content_type": version.content_type,
            "available": version.is_available,
            "extracted_text": (
                assessment.extracted_text if version.is_available and assessment else ""
            ),
        }

    return {"left": snapshot(left), "right": snapshot(right)}


def _require_retention_permission(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
):
    _validate_access(user=actor, organization=organization, permission=permission)
    return get_active_membership(user=actor, organization=organization)


def _require_protected_operation(code: str) -> None:
    now = timezone.now()
    if not ProtectedOperation.objects.filter(
        code=code,
        effective_at__lte=now,
        retired_at__isnull=True,
    ).exists():
        raise PermissionDenied("طبقه‌بندی فعال عملیات حفاظت‌شده موجود نیست.")


@transaction.atomic
def create_document_retention_policy(
    *, organization: Organization, actor: User, code: str, name: str
) -> DocumentRetentionPolicy:
    membership = _require_retention_permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENT_RETENTION_MANAGE,
    )
    policy = DocumentRetentionPolicy.objects.create(
        organization=organization,
        code=code,
        name=name,
        created_by_membership=membership,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_RETENTION_POLICY_CREATED,
        entity_type="document_retention_policy",
        entity_id=policy.pk,
        organization=organization,
        actor=actor,
        metadata={"code": policy.code},
    )
    return policy


@transaction.atomic
def create_document_retention_policy_version(
    *,
    policy: DocumentRetentionPolicy,
    actor: User,
    trigger: str,
    source_reference: str,
    effective_from: datetime,
    duration_days: int | None = None,
    applies_to_category: DocumentCategory | None = None,
) -> DocumentRetentionPolicyVersion:
    membership = _require_retention_permission(
        organization=policy.organization,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENT_RETENTION_MANAGE,
    )
    if trigger not in RetentionTrigger.values:
        raise ValueError("محرک نگهداری سند معتبر نیست.")
    locked_policy = DocumentRetentionPolicy.objects.select_for_update().get(
        pk=policy.pk
    )
    next_version = (
        locked_policy.versions.aggregate(latest=Max("version"))["latest"] or 0
    ) + 1
    return DocumentRetentionPolicyVersion.objects.create(
        organization=locked_policy.organization,
        policy=locked_policy,
        version=next_version,
        trigger=trigger,
        duration_days=duration_days,
        source_reference=source_reference.strip(),
        applies_to_category=applies_to_category,
        effective_from=effective_from,
        created_by_membership=membership,
    )


@transaction.atomic
def approve_document_retention_policy_version(
    *, version: DocumentRetentionPolicyVersion, actor: User
) -> DocumentRetentionPolicyVersion:
    membership = _require_retention_permission(
        organization=version.organization,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENT_RETENTION_APPROVE,
    )
    if not membership_is_tenant_owner(membership):
        raise PermissionDenied("تأیید سیاست نگهداری فقط در اختیار Tenant Owner است.")
    locked = DocumentRetentionPolicyVersion.objects.select_for_update().get(
        pk=version.pk
    )
    if locked.state == RetentionPolicyVersionState.APPROVED:
        return locked
    approved_at = timezone.now()
    DocumentRetentionPolicyVersion.objects.filter(pk=locked.pk).update(
        state=RetentionPolicyVersionState.APPROVED,
        approved_at=approved_at,
        approved_by_membership=membership,
        updated_at=approved_at,
    )
    locked.refresh_from_db()
    record_audit_event(
        action=AuditAction.DOCUMENT_RETENTION_POLICY_APPROVED,
        entity_type="document_retention_policy_version",
        entity_id=locked.pk,
        organization=locked.organization,
        actor=actor,
        metadata={
            "policy_id": str(locked.policy_id),
            "version": locked.version,
            "duration_is_known": locked.duration_days is not None,
            "approver_membership_id": str(membership.pk),
        },
    )
    return locked


@transaction.atomic
def apply_document_retention_policy(
    *,
    document: Document,
    policy_version: DocumentRetentionPolicyVersion,
    actor: User,
) -> DocumentRetentionApplication:
    membership = _require_retention_permission(
        organization=document.organization,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENT_RETENTION_MANAGE,
    )
    locked_document = Document.objects.select_for_update().get(pk=document.pk)
    if (
        locked_document.retention_classification
        == DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
    ):
        raise PermissionDenied(
            "سیاست عمومی نگهداری بر شاهد مهروموم‌شده قابل اعمال نیست."
        )
    if (
        policy_version.organization_id != locked_document.organization_id
        or policy_version.state != RetentionPolicyVersionState.APPROVED
        or policy_version.effective_from > timezone.now()
    ):
        raise PermissionDenied("نسخه سیاست نگهداری معتبر و مؤثر نیست.")
    if (
        policy_version.applies_to_category_id
        and policy_version.applies_to_category_id != locked_document.category_id
    ):
        raise PermissionDenied("سیاست نگهداری برای دسته سند قابل اعمال نیست.")
    if policy_version.trigger == RetentionTrigger.DOCUMENT_ARCHIVED:
        if locked_document.archived_at is None:
            raise ValueError("محرک بایگانی سند هنوز رخ نداده است.")
        trigger_at = locked_document.archived_at
    else:
        trigger_at = locked_document.created_at
    retention_until = None
    if policy_version.duration_days is not None:
        retention_until = trigger_at + timedelta(days=policy_version.duration_days)
    application = DocumentRetentionApplication.objects.create(
        organization=locked_document.organization,
        document=locked_document,
        policy_version=policy_version,
        trigger_at=trigger_at,
        retention_until=retention_until,
        applied_by_membership=membership,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_RETENTION_APPLIED,
        entity_type="document",
        entity_id=locked_document.pk,
        organization=locked_document.organization,
        actor=actor,
        metadata={
            "policy_version_id": str(policy_version.pk),
            "duration_is_known": retention_until is not None,
        },
    )
    return application


@transaction.atomic
def place_document_legal_hold(
    *,
    document: Document,
    actor: User,
    reason: str,
    source_reference: str,
) -> DocumentLegalHold:
    membership = _require_retention_permission(
        organization=document.organization,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENT_HOLDS_PLACE,
    )
    if not reason.strip() or not source_reference.strip():
        raise ValueError("دلیل و مرجع نگهداری حقوقی الزامی است.")
    locked_document = Document.objects.select_for_update().get(pk=document.pk)
    hold = DocumentLegalHold.objects.create(
        organization=locked_document.organization,
        document=locked_document,
        reason=reason.strip(),
        source_reference=source_reference.strip(),
        placed_by_membership=membership,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_HOLD_PLACED,
        entity_type="document_legal_hold",
        entity_id=hold.pk,
        organization=hold.organization,
        actor=actor,
        metadata={"document_id": str(locked_document.pk)},
    )
    return hold


@transaction.atomic
def release_document_legal_hold(
    *, hold: DocumentLegalHold, actor: User, reason: str
) -> DocumentLegalHold:
    _require_protected_operation(ProtectedOperationCode.DOCUMENT_HOLD_RELEASE)
    membership = _require_retention_permission(
        organization=hold.organization,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENT_HOLDS_RELEASE,
    )
    if not reason.strip():
        raise ValueError("دلیل آزادسازی نگهداری حقوقی الزامی است.")
    Document.objects.select_for_update().get(pk=hold.document_id)
    locked = DocumentLegalHold.objects.select_for_update().get(pk=hold.pk)
    if locked.released_at:
        return locked
    if locked.placed_by_membership_id == membership.pk:
        raise PermissionDenied("ثبت‌کننده نگهداری نمی‌تواند همان نگهداری را آزاد کند.")
    locked.released_at = timezone.now()
    locked.released_by_membership = membership
    locked.release_reason = reason.strip()
    locked.save(
        update_fields=[
            "released_at",
            "released_by_membership",
            "release_reason",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_HOLD_RELEASED,
        entity_type="document_legal_hold",
        entity_id=locked.pk,
        organization=locked.organization,
        actor=actor,
        metadata={
            "document_id": str(locked.document_id),
            "releaser_membership_id": str(membership.pk),
        },
    )
    return locked


@transaction.atomic
def request_document_disposal(
    *, document: Document, actor: User, reason: str
) -> DocumentDisposalIntent:
    membership = _require_retention_permission(
        organization=document.organization,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENT_DISPOSALS_REQUEST,
    )
    if not reason.strip():
        raise ValueError("دلیل درخواست امحا الزامی است.")
    locked_document = Document.objects.select_for_update().get(pk=document.pk)
    if (
        locked_document.retention_classification
        == DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
    ):
        raise PermissionDenied("برای شاهد مهروموم‌شده فرایند امحا تعریف نشده است.")
    intent = DocumentDisposalIntent.objects.create(
        organization=locked_document.organization,
        document=locked_document,
        reason=reason.strip(),
        requested_by_membership=membership,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_DISPOSAL_REQUESTED,
        entity_type="document_disposal_intent",
        entity_id=intent.pk,
        organization=intent.organization,
        actor=actor,
        metadata={"document_id": str(locked_document.pk)},
    )
    return intent


@transaction.atomic
def review_document_disposal_intent(
    *, intent: DocumentDisposalIntent, actor: User
) -> DocumentDisposalIntent:
    """Review intent only; no P1 code path deletes metadata or bytes."""

    _require_protected_operation(ProtectedOperationCode.DOCUMENT_DISPOSAL_APPROVAL)
    membership = _require_retention_permission(
        organization=intent.organization,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENT_DISPOSALS_APPROVE,
    )
    Document.objects.select_for_update().get(pk=intent.document_id)
    locked = DocumentDisposalIntent.objects.select_for_update().get(pk=intent.pk)
    if locked.requested_by_membership_id == membership.pk:
        raise PermissionDenied("درخواست‌کننده نمی‌تواند قصد امحای خود را تأیید کند.")
    applications = list(locked.document.retention_applications.all())
    block_reason = ""
    if not applications:
        block_reason = "هیچ سیاست نگهداری تأییدشده‌ای اعمال نشده است."
    elif any(item.retention_until is None for item in applications):
        block_reason = "مدت نگهداری حداقل یک تعهد نامشخص است."
    elif any(item.retention_until > timezone.now() for item in applications):
        block_reason = "حداقل یک تعهد نگهداری هنوز منقضی نشده است."
    elif locked.document.legal_holds.filter(released_at__isnull=True).exists():
        block_reason = "نگهداری حقوقی فعال، امحا را مسدود می‌کند."
    locked.approved_by_membership = membership
    locked.approved_at = timezone.now()
    locked.block_reason = block_reason
    locked.state = (
        DisposalIntentState.BLOCKED
        if block_reason
        else DisposalIntentState.APPROVED_NON_DESTRUCTIVE
    )
    locked.save(
        update_fields=[
            "state",
            "approved_by_membership",
            "approved_at",
            "block_reason",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_DISPOSAL_REVIEWED,
        entity_type="document_disposal_intent",
        entity_id=locked.pk,
        organization=locked.organization,
        actor=actor,
        metadata={
            "state": locked.state,
            "destructive_execution_enabled": False,
        },
    )
    return locked


def measure_document_storage(*, organization: Organization) -> dict[str, int]:
    """Measure P1 byte categories without quota enforcement or overlap."""

    counts = {
        "original_bytes": 0,
        "quarantine_bytes": 0,
        "derivative_bytes": 0,
        "export_bundle_bytes": 0,
    }
    for version in DocumentVersion.objects.filter(organization=organization):
        key = "original_bytes" if version.is_available else "quarantine_bytes"
        counts[key] += version.file_size
    counts["derivative_bytes"] = 0
    counts["export_bundle_bytes"] = (
        DocumentExportManifest.objects.filter(organization=organization).aggregate(
            total=Max("export_bundle_bytes")
        )["total"]
        or 0
    )
    return counts


@transaction.atomic
def create_document_export_manifest(
    *, organization: Organization, actor: User, document_ids: list[object]
) -> DocumentExportManifest:
    membership = _require_retention_permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.DOCUMENTS_EXPORT,
    )
    documents = list(
        Document.objects.filter(organization=organization, pk__in=document_ids)
        .select_related("category")
        .prefetch_related("versions")
    )
    if len(documents) != len(set(map(str, document_ids))):
        raise PermissionDenied("دامنه خروجی سند معتبر نیست.")
    manifest_documents = []
    complete = True
    for document in documents:
        _validate_document_context_access(
            document=document,
            actor=actor,
            permission=BusinessPermissionCode.DOCUMENTS_EXPORT,
        )
        versions = []
        for version in document.versions.all():
            assessment = version.latest_processing_assessment
            storage_exists = version.file.storage.exists(version.file.name)
            available = bool(
                storage_exists
                and assessment
                and assessment.verdict == DocumentProcessingVerdict.CLEAN
            )
            complete = complete and available
            versions.append(
                {
                    "version_id": str(version.pk),
                    "version_number": version.version_number,
                    "sha256": version.sha256,
                    "file_size": version.file_size,
                    "available": available,
                    "processing_verdict": assessment.verdict if assessment else None,
                }
            )
        manifest_documents.append(
            {
                "document_id": str(document.pk),
                "document_number": document.document_number,
                "confidentiality": document.confidentiality,
                "links": [
                    {"id": str(link.pk), "type": link.target_type}
                    for link in typed_links_for_document(document)
                ],
                "versions": versions,
            }
        )
    byte_counts = measure_document_storage(organization=organization)
    export = DocumentExportManifest.objects.create(
        organization=organization,
        requested_by_membership=membership,
        completeness=(
            ManifestCompleteness.COMPLETE
            if complete
            else ManifestCompleteness.INCOMPLETE
        ),
        manifest={"documents": manifest_documents},
        **byte_counts,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_EXPORT_MANIFEST_CREATED,
        entity_type="document_export_manifest",
        entity_id=export.pk,
        organization=organization,
        actor=actor,
        metadata={
            "completeness": export.completeness,
            "document_count": len(documents),
        },
    )
    return export


@transaction.atomic
def attest_document_key_custody(
    *,
    organization: Organization,
    actor: User,
    reference: str,
    boundary_id: uuid.UUID | None = None,
) -> DocumentKeyCustodyAttestation:
    if not has_platform_role(actor, PlatformRoleCode.PLATFORM_SECURITY):
        raise PermissionDenied("نقش فعال Platform Security الزامی است.")
    if not reference.strip():
        raise ValueError("مرجع شاهد نگهداری کلید الزامی است.")
    attestation = DocumentKeyCustodyAttestation.objects.create(
        organization=organization,
        boundary_id=boundary_id or uuid.uuid4(),
        reference=reference.strip(),
        attested_by=actor,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_KEY_CUSTODY_ATTESTED,
        entity_type="document_key_custody_attestation",
        entity_id=attestation.pk,
        organization=organization,
        actor=actor,
        allow_platform_actor=True,
        metadata={"boundary_id": str(attestation.boundary_id)},
    )
    return attestation


@transaction.atomic
def reconcile_document_recovery_boundary(
    *,
    organization: Organization,
    actor: User,
    database_reference: str,
    key_custody_attestation: DocumentKeyCustodyAttestation,
) -> DocumentRecoveryManifest:
    if not has_platform_role(actor, PlatformRoleCode.PLATFORM_OPERATIONS):
        raise PermissionDenied("نقش فعال Platform Operations الزامی است.")
    if (
        key_custody_attestation.organization_id != organization.pk
        or not database_reference.strip()
    ):
        raise PermissionDenied("مرز بازیابی و شاهد کلید معتبر نیست.")
    version_rows = []
    complete = True
    for version in DocumentVersion.objects.filter(organization=organization):
        exists = version.file.storage.exists(version.file.name)
        actual_hash = ""
        if exists:
            digest = hashlib.sha256()
            try:
                with version.file.open("rb") as stored_file:
                    for chunk in iter(lambda: stored_file.read(65536), b""):
                        digest.update(chunk)
                actual_hash = digest.hexdigest()
            except OSError:
                exists = False
        matches = exists and actual_hash == version.sha256
        complete = complete and matches
        version_rows.append(
            {
                "version_id": str(version.pk),
                "expected_sha256": version.sha256,
                "storage_present": exists,
                "hash_matches": matches,
            }
        )
    byte_counts = measure_document_storage(organization=organization)
    manifest = DocumentRecoveryManifest.objects.create(
        organization=organization,
        boundary_id=key_custody_attestation.boundary_id,
        database_reference=database_reference.strip(),
        key_custody_attestation=key_custody_attestation,
        state=(
            RecoveryEvidenceState.RECONCILED
            if complete
            else RecoveryEvidenceState.INCOMPLETE
        ),
        manifest={
            "versions": version_rows,
            "retention_policy_versions": organization.document_retention_policy_versions.count(),
            "legal_holds": organization.document_legal_holds.count(),
            "audit_events": organization.audit_events.count(),
            "key_custody_attestation_id": str(key_custody_attestation.pk),
        },
        byte_counts=byte_counts,
        generated_by=actor,
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_RECOVERY_RECONCILED,
        entity_type="document_recovery_manifest",
        entity_id=manifest.pk,
        organization=organization,
        actor=actor,
        allow_platform_actor=True,
        metadata={
            "boundary_id": str(manifest.boundary_id),
            "state": manifest.state,
        },
    )
    return manifest


@transaction.atomic
def approve_document_restore_evidence(
    *, manifest: DocumentRecoveryManifest, actor: User
) -> DocumentRecoveryManifest:
    if not has_platform_role(actor, PlatformRoleCode.RESTORE_EVIDENCE_APPROVER):
        raise PermissionDenied("نقش فعال Restore Evidence Approver الزامی است.")
    locked = DocumentRecoveryManifest.objects.select_for_update().get(pk=manifest.pk)
    if locked.state != RecoveryEvidenceState.RECONCILED:
        raise ValueError("شاهد بازیابی ناقص قابل تأیید نیست.")
    if actor.pk in (
        locked.generated_by_id,
        locked.key_custody_attestation.attested_by_id,
    ):
        raise PermissionDenied("تأیید شاهد بازیابی باید توسط اختیار مستقل انجام شود.")
    locked.state = RecoveryEvidenceState.APPROVED
    locked.approved_at = timezone.now()
    locked.approved_by = actor
    locked.save(
        update_fields=["state", "approved_at", "approved_by", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.DOCUMENT_RESTORE_EVIDENCE_APPROVED,
        entity_type="document_recovery_manifest",
        entity_id=locked.pk,
        organization=locked.organization,
        actor=actor,
        allow_platform_actor=True,
        metadata={"boundary_id": str(locked.boundary_id)},
    )
    return locked


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
