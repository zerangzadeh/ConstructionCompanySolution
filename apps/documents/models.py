import uuid
from pathlib import Path
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.documents.storage import document_storage
from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class DocumentType(models.TextChoices):
    GENERAL = "general", "عمومی"
    CONTRACT = "contract", "قرارداد"
    DRAWING = "drawing", "نقشه"
    RECEIPT = "receipt", "رسید"
    PHOTO = "photo", "تصویر"
    REPORT = "report", "گزارش"
    OTHER = "other", "سایر"


class PhotoSource(models.TextChoices):
    CAMERA = "camera", "دوربین"
    UPLOAD = "upload", "بارگذاری"


class DocumentConfidentiality(models.TextChoices):
    INTERNAL = "internal", "داخلی"
    CONFIDENTIAL = "confidential", "محرمانه"
    RESTRICTED = "restricted", "بسیار محدود"


class DocumentProcessingVerdict(models.TextChoices):
    CLEAN = "clean", "پاک و قابل استفاده"
    UNSAFE = "unsafe", "ناامن"
    UNSUPPORTED = "unsupported", "پشتیبانی‌نشده"
    ERROR = "error", "خطای پردازش"


class SignatureVerificationState(models.TextChoices):
    UNKNOWN = "unknown", "نامشخص"
    PENDING = "pending", "در انتظار بررسی"
    VERIFIED = "verified", "تأیید فنی"
    FAILED = "failed", "نامعتبر"


class RetentionTrigger(models.TextChoices):
    DOCUMENT_RECEIVED = "document_received", "دریافت سند"
    DOCUMENT_ARCHIVED = "document_archived", "بایگانی سند"


class DocumentRetentionClassification(models.TextChoices):
    STANDARD_DOCUMENT = "standard_document", "سند استاندارد"
    SEALED_SUPPLIER_QUOTE_EVIDENCE = (
        "sealed_supplier_quote_evidence",
        "شاهد مهروموم‌شده پیشنهاد تأمین‌کننده",
    )


class SealedCustodyState(models.TextChoices):
    QUARANTINED = "quarantined", "قرنطینه و غیرقابل دسترس"


class RetentionPolicyVersionState(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    APPROVED = "approved", "تأییدشده"


class DisposalIntentState(models.TextChoices):
    REQUESTED = "requested", "درخواست‌شده"
    BLOCKED = "blocked", "مسدود"
    APPROVED_NON_DESTRUCTIVE = (
        "approved_non_destructive",
        "تأیید قصد بدون اجرای امحا",
    )


class ManifestCompleteness(models.TextChoices):
    COMPLETE = "complete", "کامل"
    INCOMPLETE = "incomplete", "ناقص"


class RecoveryEvidenceState(models.TextChoices):
    RECONCILED = "reconciled", "تطبیق‌شده"
    INCOMPLETE = "incomplete", "ناقص"
    APPROVED = "approved", "تأییدشده"


class DocumentCategory(UUIDModel, TimeStampedModel):
    """Tenant category with explicit, default-denied employee access policy."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="document_categories",
    )
    code = models.SlugField(max_length=50)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    employee_current_visible = models.BooleanField(default=False)
    employee_history_visible = models.BooleanField(default=False)
    employee_download_allowed = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_categories_created",
    )

    class Meta:
        ordering = ["name"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="document_category_org_code_uq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().lower()
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("کد و نام دسته‌بندی سند الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class DocumentNumberSequence(UUIDModel, TimeStampedModel):
    """Serialized Tenant-local allocator; issued document numbers never change."""

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_number_sequence",
    )
    next_value = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(next_value__gte=1),
                name="document_sequence_next_positive",
            )
        ]


DOCUMENT_LINK_TARGET_FIELDS = (
    "project",
    "contract",
    "estimate",
    "expense",
    "payment",
    "daily_report",
)


def document_version_upload_path(instance: "DocumentVersion", filename: str) -> str:
    """Store each immutable version at a private, non-guessable tenant path."""

    extension = Path(filename).suffix.lower()
    return (
        f"organizations/{instance.organization_id}/documents/{instance.document_id}/"
        f"versions/{uuid.uuid4()}{extension}"
    )


def document_upload_path(instance: models.Model, filename: str) -> str:
    """Historical migration callable; not used by the current document model."""

    extension = Path(filename).suffix.lower()
    return (
        f"organizations/{instance.organization_id}/projects/{instance.project_id}/"
        f"documents/{uuid.uuid4()}{extension}"
    )


class Document(UUIDModel, TimeStampedModel):
    """Tenant-owned document metadata whose binary history lives in versions."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(
        "نوع سند",
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.GENERAL,
    )
    document_number = models.CharField(max_length=40, editable=False)
    category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    confidentiality = models.CharField(
        max_length=20,
        choices=DocumentConfidentiality.choices,
        default=DocumentConfidentiality.INTERNAL,
    )
    retention_classification = models.CharField(
        max_length=48,
        choices=DocumentRetentionClassification.choices,
        default=DocumentRetentionClassification.STANDARD_DOCUMENT,
    )
    access_expires_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField("عنوان سند", max_length=255)
    reference = models.CharField("شماره مرجع", max_length=120, blank=True)
    description = models.TextField("توضیحات", blank=True)
    current_version = models.ForeignKey(
        "DocumentVersion",
        verbose_name="نسخه جاری",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_for_documents",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_updated",
    )
    archive_reason = models.TextField("دلیل بایگانی", blank=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بایگانی‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_archived",
    )

    class Meta:
        verbose_name = "سند"
        verbose_name_plural = "اسناد"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "document_number"],
                name="document_org_number_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "reference"],
                condition=~Q(reference=""),
                name="document_org_reference_uq",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "archived_at", "document_type"],
                name="document_org_active_type_idx",
            ),
        ]
        ordering = ["-created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        self.title = self.title.strip()
        self.reference = self.reference.strip()
        self.description = self.description.strip()
        if not self.title:
            raise ValidationError({"title": "وارد کردن عنوان سند الزامی است."})
        if not self.document_number.strip():
            raise ValidationError({"document_number": "شماره داخلی سند الزامی است."})
        if self.category_id:
            if self.category.organization_id != self.organization_id:
                raise ValidationError("دسته‌بندی سند باید متعلق به همین سازمان باشد.")
            if self.category.archived_at:
                raise ValidationError("دسته‌بندی بایگانی‌شده قابل استفاده نیست.")
        if self.current_version_id:
            if self.current_version.document_id != self.pk:
                raise ValidationError(
                    {"current_version": "نسخه جاری باید متعلق به همین سند باشد."}
                )
            validate_related_organizations(self, current_version=self.current_version)
            latest_version_id = (
                self.versions.order_by("-version_number")
                .values_list("pk", flat=True)
                .first()
            )
            if latest_version_id != self.current_version_id:
                raise ValidationError(
                    {"current_version": "نسخه جاری باید آخرین نسخه سند باشد."}
                )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            original_number = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("document_number", flat=True)
                .first()
            )
            if original_number and original_number != self.document_number:
                raise ValidationError("شماره داخلی صادرشده سند تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("سند باید بایگانی شود و قابل حذف مستقیم نیست.")


class DocumentVersion(UUIDModel, CreatedAtModel):
    """An immutable binary version belonging to one document and tenant."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="document_versions",
    )
    document = models.ForeignKey(
        Document,
        verbose_name="سند",
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField("شماره نسخه")
    original_file_name = models.CharField("نام اصلی فایل", max_length=255)
    file = models.FileField(
        "فایل",
        upload_to=document_version_upload_path,
        storage=document_storage,
        max_length=255,
    )
    content_type = models.CharField("نوع محتوای فایل", max_length=100)
    file_size = models.PositiveBigIntegerField("حجم فایل")
    sha256 = models.CharField("SHA-256", max_length=64)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بارگذاری‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_versions_uploaded",
    )

    class Meta:
        verbose_name = "نسخه سند"
        verbose_name_plural = "نسخه‌های سند"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["document", "version_number"],
                name="document_version_number_uq",
            ),
            models.CheckConstraint(
                condition=Q(version_number__gte=1),
                name="document_version_number_positive",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "document", "-version_number"],
                name="docversion_org_doc_num_idx",
            ),
        ]
        ordering = ["-version_number"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.document} — نسخه {self.version_number}"

    def clean(self) -> None:
        super().clean()
        if self.document_id:
            validate_related_organizations(self, document=self.document)
        if self.version_number < 1:
            raise ValidationError(
                {"version_number": "شماره نسخه باید بزرگ‌تر از صفر باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("نسخه سند immutable است و قابل ویرایش نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("نسخه سند immutable است و قابل حذف نیست.")

    @property
    def latest_processing_assessment(self) -> "DocumentProcessingAssessment | None":
        cache = getattr(self, "_prefetched_objects_cache", {})
        if "processing_assessments" in cache:
            assessments = cache["processing_assessments"]
            return max(assessments, key=lambda item: item.sequence, default=None)
        return self.processing_assessments.order_by("-sequence").first()

    @property
    def is_available(self) -> bool:
        assessment = self.latest_processing_assessment
        return bool(
            assessment and assessment.verdict == DocumentProcessingVerdict.CLEAN
        )


class PhotoMetadata(UUIDModel, CreatedAtModel):
    """Metadata-only photo evidence; the binary remains a DocumentVersion."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="photo_metadata_records",
    )
    document = models.OneToOneField(
        Document,
        on_delete=models.PROTECT,
        related_name="photo_metadata",
    )
    source = models.CharField(max_length=16, choices=PhotoSource.choices)
    captured_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "source", "-created_at"],
                name="photo_meta_org_src_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.document_id:
            validate_related_organizations(self, document=self.document)
            if self.document.document_type != DocumentType.PHOTO:
                raise ValidationError(
                    {"document": "فراداده تصویر فقط برای سند از نوع تصویر مجاز است."}
                )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("فراداده منبع تصویر تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("فراداده تصویر جزئی از سابقه سند و حذف‌ناپذیر است.")


class ImmutableSealedCustodyQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        raise ValidationError("شاهد نگهداری مهروموم‌شده قابل تغییر نیست.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("شاهد نگهداری مهروموم‌شده قابل حذف نیست.")


class ImmutableSealedCustodyManager(
    models.Manager.from_queryset(ImmutableSealedCustodyQuerySet)
):
    pass


class SealedDocumentCustody(UUIDModel, CreatedAtModel):
    """Immutable DMS custody evidence; it never grants content retrieval."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="sealed_document_custody_records",
    )
    document_version = models.OneToOneField(
        DocumentVersion,
        on_delete=models.PROTECT,
        related_name="sealed_custody",
    )
    retention_classification = models.CharField(
        max_length=48,
        choices=DocumentRetentionClassification.choices,
        default=DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE,
    )
    state = models.CharField(
        max_length=16,
        choices=SealedCustodyState.choices,
        default=SealedCustodyState.QUARANTINED,
    )
    canonical_sha256 = models.CharField(max_length=64)
    received_at = models.DateTimeField()
    custodied_at = models.DateTimeField()
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sealed_document_custody_records",
    )

    objects = ImmutableSealedCustodyManager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(
                    retention_classification=DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
                ),
                name="sealed_custody_retention_class",
            ),
            models.CheckConstraint(
                condition=Q(state=SealedCustodyState.QUARANTINED),
                name="sealed_custody_initial_quarantine",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            document_version=self.document_version
            if self.document_version_id
            else None,
        )
        self.canonical_sha256 = self.canonical_sha256.strip().lower()
        if self.document_version_id and (
            self.document_version.sha256 != self.canonical_sha256
            or self.document_version.document.retention_classification
            != DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
        ):
            raise ValidationError("هویت بایت و طبقه‌بندی شاهد نگهداری معتبر نیست.")
        if (
            self.retention_classification
            != DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
            or self.state != SealedCustodyState.QUARANTINED
        ):
            raise ValidationError("شاهد باید با طبقه‌بندی مهروموم‌شده در قرنطینه باشد.")
        if self.received_at > self.custodied_at:
            raise ValidationError("زمان نگهداری نمی‌تواند پیش از دریافت باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("شاهد نگهداری مهروموم‌شده قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("شاهد نگهداری مهروموم‌شده قابل حذف نیست.")


class DocumentProcessingAssessment(UUIDModel, CreatedAtModel):
    """Append-only scan/OCR assessment; absence is unknown and unavailable."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_processing_assessments",
    )
    version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.PROTECT,
        related_name="processing_assessments",
    )
    sequence = models.PositiveIntegerField()
    verdict = models.CharField(max_length=20, choices=DocumentProcessingVerdict.choices)
    input_sha256 = models.CharField(max_length=64)
    adapter_code = models.CharField(max_length=80)
    adapter_version = models.CharField(max_length=80, blank=True)
    provider_reference = models.CharField(max_length=160, blank=True)
    extracted_text = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_processing_assessments_recorded",
    )

    class Meta:
        ordering = ["version", "sequence"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["version", "sequence"],
                name="document_assessment_sequence_uq",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="document_assessment_sequence_positive",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "verdict", "created_at"],
                name="docassessment_org_verdict_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, version=self.version)
        if self.input_sha256 != self.version.sha256:
            raise ValidationError("هویت بایت ارزیابی با نسخه سند یکسان نیست.")
        if not self.adapter_code.strip():
            raise ValidationError("شناسه آداپتور ارزیابی الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("ارزیابی پردازش سند تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("ارزیابی پردازش سند حذف‌پذیر نیست.")


class DocumentSignatureEvidence(UUIDModel, CreatedAtModel):
    """Provider-neutral signature evidence; legal effect is intentionally unset."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_signature_evidence",
    )
    version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.PROTECT,
        related_name="signature_evidence",
    )
    verification_state = models.CharField(
        max_length=20,
        choices=SignatureVerificationState.choices,
        default=SignatureVerificationState.UNKNOWN,
    )
    provider_code = models.CharField(max_length=80, blank=True)
    provider_reference = models.CharField(max_length=160, blank=True)
    standard_code = models.CharField(max_length=120, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_signature_evidence_recorded",
    )

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "verification_state", "created_at"],
                name="docsig_org_state_created_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, version=self.version)

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("شاهد امضای سند تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("شاهد امضای سند حذف‌پذیر نیست.")


class DocumentRetentionPolicy(UUIDModel, TimeStampedModel):
    """Tenant-owned retention identity; versions carry effective obligations."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_retention_policies",
    )
    code = models.SlugField(max_length=60)
    name = models.CharField(max_length=160)
    created_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="document_retention_policies_created",
    )

    class Meta:
        ordering = ["code"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="document_retention_policy_org_code_uq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().lower()
        self.name = self.name.strip()
        validate_related_organizations(
            self, created_by_membership=self.created_by_membership
        )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class DocumentRetentionPolicyVersion(UUIDModel, TimeStampedModel):
    """Versioned retention rule; null duration is explicitly non-disposable."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_retention_policy_versions",
    )
    policy = models.ForeignKey(
        DocumentRetentionPolicy,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version = models.PositiveIntegerField()
    state = models.CharField(
        max_length=20,
        choices=RetentionPolicyVersionState.choices,
        default=RetentionPolicyVersionState.DRAFT,
    )
    trigger = models.CharField(max_length=30, choices=RetentionTrigger.choices)
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    source_reference = models.CharField(max_length=255)
    applies_to_category = models.ForeignKey(
        DocumentCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="retention_policy_versions",
    )
    effective_from = models.DateTimeField()
    created_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="document_retention_policy_versions_created",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_retention_policy_versions_approved",
    )

    class Meta:
        ordering = ["policy", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["policy", "version"],
                name="document_retention_policy_version_uq",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="document_retention_version_positive",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        relations: dict[str, models.Model] = {
            "policy": self.policy,
            "created_by_membership": self.created_by_membership,
        }
        if self.applies_to_category_id:
            relations["applies_to_category"] = self.applies_to_category
        if self.approved_by_membership_id:
            relations["approved_by_membership"] = self.approved_by_membership
        validate_related_organizations(self, **relations)
        if not self.source_reference.strip():
            raise ValidationError("مرجع منبع سیاست نگهداری الزامی است.")
        approval_complete = bool(self.approved_at and self.approved_by_membership_id)
        if self.state == RetentionPolicyVersionState.APPROVED and not approval_complete:
            raise ValidationError("شاهد تأیید سیاست نگهداری کامل نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            original_state = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("state", flat=True)
                .first()
            )
            if original_state == RetentionPolicyVersionState.APPROVED:
                raise ValidationError("نسخه تأییدشده سیاست نگهداری تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class DocumentRetentionApplication(UUIDModel, CreatedAtModel):
    """Immutable application snapshot; conflicting/unknown obligations accumulate."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_retention_applications",
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        related_name="retention_applications",
    )
    policy_version = models.ForeignKey(
        DocumentRetentionPolicyVersion,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    trigger_at = models.DateTimeField()
    retention_until = models.DateTimeField(null=True, blank=True)
    applied_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="document_retention_applications",
    )

    class Meta:
        ordering = ["created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["document", "policy_version"],
                name="document_retention_application_uq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            document=self.document,
            policy_version=self.policy_version,
            applied_by_membership=self.applied_by_membership,
        )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("اعمال سیاست نگهداری تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class DocumentLegalHold(UUIDModel, TimeStampedModel):
    """Retained hold evidence; release never implies disposal."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_legal_holds",
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        related_name="legal_holds",
    )
    reason = models.TextField()
    source_reference = models.CharField(max_length=255)
    placed_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="document_holds_placed",
    )
    released_at = models.DateTimeField(null=True, blank=True)
    released_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_holds_released",
    )
    release_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "document", "released_at"],
                name="dochold_org_doc_release_idx",
            )
        ]


class DocumentDisposalIntent(UUIDModel, TimeStampedModel):
    """Non-destructive intent only; P1 deliberately has no byte deletion command."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_disposal_intents",
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        related_name="disposal_intents",
    )
    state = models.CharField(
        max_length=32,
        choices=DisposalIntentState.choices,
        default=DisposalIntentState.REQUESTED,
    )
    reason = models.TextField()
    requested_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="document_disposals_requested",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_disposals_approved",
    )
    block_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012


class DocumentExportManifest(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_export_manifests",
    )
    requested_by_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="document_export_manifests",
    )
    completeness = models.CharField(max_length=20, choices=ManifestCompleteness.choices)
    manifest = models.JSONField(default=dict)
    original_bytes = models.PositiveBigIntegerField(default=0)
    quarantine_bytes = models.PositiveBigIntegerField(default=0)
    derivative_bytes = models.PositiveBigIntegerField(default=0)
    export_bundle_bytes = models.PositiveBigIntegerField(default=0)


class DocumentKeyCustodyAttestation(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_key_custody_attestations",
    )
    boundary_id = models.UUIDField(default=uuid.uuid4, unique=True)
    reference = models.CharField(max_length=255)
    attested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_key_custody_attestations",
    )


class DocumentRecoveryManifest(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="document_recovery_manifests",
    )
    boundary_id = models.UUIDField(default=uuid.uuid4, unique=True)
    database_reference = models.CharField(max_length=255)
    key_custody_attestation = models.ForeignKey(
        DocumentKeyCustodyAttestation,
        on_delete=models.PROTECT,
        related_name="recovery_manifests",
    )
    state = models.CharField(max_length=20, choices=RecoveryEvidenceState.choices)
    manifest = models.JSONField(default=dict)
    byte_counts = models.JSONField(default=dict)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_recovery_manifests_generated",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_recovery_manifests_approved",
    )


class AbstractTypedDocumentLink(UUIDModel, CreatedAtModel):
    """Shared invariant shell for domain-owned, append-only document links."""

    target_field_name: ClassVar[str]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="+",
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        related_name="+",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    legacy_link_id = models.UUIDField(null=True, blank=True, unique=True)

    class Meta:
        abstract = True
        ordering = ["created_at"]  # noqa: RUF012

    @property
    def target(self) -> models.Model:
        return getattr(self, self.target_field_name)

    @property
    def target_type(self) -> str:
        return self.target_field_name

    def clean(self) -> None:
        super().clean()
        target = self.target
        validate_related_organizations(self, document=self.document, target=target)
        if (
            hasattr(self, "document_version_id")
            and self.document_version.document_id != self.document_id
        ):
            raise ValidationError(
                {"document_version": "نسخه سند باید متعلق به همان سند پیوندشده باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            target_id_field = f"{self.target_field_name}_id"
            immutable_fields = [
                "organization_id",
                "document_id",
                target_id_field,
                "created_by_id",
                "legacy_link_id",
            ]
            if hasattr(self, "document_version_id"):
                immutable_fields.append("document_version_id")
            original = (
                type(self).objects.filter(pk=self.pk).values(*immutable_fields).first()
            )
            current = {field: getattr(self, field) for field in immutable_fields}
            if original is not None and original != current:
                raise ValidationError("لینک نوع‌دار سند تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("لینک نوع‌دار سند جزئی از سابقه و حذف‌ناپذیر است.")


class RetainedEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Retired source evidence is immutable.")

    def delete(self):
        raise ValidationError("Retired source evidence cannot be deleted.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Retired source evidence is immutable.")


class RetiredPaymentEvidence(UUIDModel, CreatedAtModel):
    """Immutable interpretation of excluded demo history; never a cash authority."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT)
    payment_number = models.CharField(max_length=80)
    source_snapshot = models.JSONField()
    source_sha256 = models.CharField(max_length=64)
    authority_reference = models.CharField(max_length=255)
    objects = RetainedEvidenceQuerySet.as_manager()

    def __str__(self):
        return f"Retired demo Payment {self.payment_number} ({self.pk})"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Retired source evidence is immutable.")
        validate_related_organizations(self, project=self.project)
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retired source evidence cannot be deleted.")


class RetiredPaymentDocumentLink(AbstractTypedDocumentLink):
    """DMS-owned retained source link; original link/document UUIDs are unchanged."""

    target_field_name = "payment"
    payment = models.ForeignKey(
        RetiredPaymentEvidence,
        on_delete=models.PROTECT,
        related_name="typed_document_links",
    )

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["document", "payment"], name="retired_payment_document_uq"
            )
        ]


class DocumentLink(UUIDModel, CreatedAtModel):
    """A controlled link from a document to exactly one supported entity."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="document_links",
    )
    document = models.ForeignKey(
        Document,
        verbose_name="سند",
        on_delete=models.CASCADE,
        related_name="links",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_links",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        verbose_name="قرارداد",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_links",
    )
    estimate = models.ForeignKey(
        "estimates.Estimate",
        verbose_name="برآورد",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_links",
    )
    expense = models.ForeignKey(
        "expenses.Expense",
        verbose_name="هزینه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_links",
    )
    payment = models.ForeignKey(
        "documents.RetiredPaymentEvidence",
        verbose_name="شاهد پرداخت نمایشی بازنشسته",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_links",
    )
    daily_report = models.ForeignKey(
        "daily_reports.DailyReport",
        verbose_name="گزارش روزانه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="document_links",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده لینک",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_links_created",
    )

    class Meta:
        verbose_name = "لینک سند"
        verbose_name_plural = "لینک‌های سند"
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=(
                    Q(
                        project__isnull=False,
                        contract__isnull=True,
                        estimate__isnull=True,
                        expense__isnull=True,
                        payment__isnull=True,
                        daily_report__isnull=True,
                    )
                    | Q(
                        project__isnull=True,
                        contract__isnull=False,
                        estimate__isnull=True,
                        expense__isnull=True,
                        payment__isnull=True,
                        daily_report__isnull=True,
                    )
                    | Q(
                        project__isnull=True,
                        contract__isnull=True,
                        estimate__isnull=False,
                        expense__isnull=True,
                        payment__isnull=True,
                        daily_report__isnull=True,
                    )
                    | Q(
                        project__isnull=True,
                        contract__isnull=True,
                        estimate__isnull=True,
                        expense__isnull=False,
                        payment__isnull=True,
                        daily_report__isnull=True,
                    )
                    | Q(
                        project__isnull=True,
                        contract__isnull=True,
                        estimate__isnull=True,
                        expense__isnull=True,
                        payment__isnull=False,
                        daily_report__isnull=True,
                    )
                    | Q(
                        project__isnull=True,
                        contract__isnull=True,
                        estimate__isnull=True,
                        expense__isnull=True,
                        payment__isnull=True,
                        daily_report__isnull=False,
                    )
                ),
                name="document_link_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["document", "project"],
                condition=Q(project__isnull=False),
                name="document_link_project_uq",
            ),
            models.UniqueConstraint(
                fields=["document", "contract"],
                condition=Q(contract__isnull=False),
                name="document_link_contract_uq",
            ),
            models.UniqueConstraint(
                fields=["document", "estimate"],
                condition=Q(estimate__isnull=False),
                name="document_link_estimate_uq",
            ),
            models.UniqueConstraint(
                fields=["document", "expense"],
                condition=Q(expense__isnull=False),
                name="document_link_expense_uq",
            ),
            models.UniqueConstraint(
                fields=["document", "payment"],
                condition=Q(payment__isnull=False),
                name="document_link_payment_uq",
            ),
            models.UniqueConstraint(
                fields=["document", "daily_report"],
                condition=Q(daily_report__isnull=False),
                name="document_link_daily_report_uq",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "document"],
                name="doclink_org_document_idx",
            ),
        ]
        ordering = ["created_at"]  # noqa: RUF012

    @property
    def target(self) -> models.Model:
        for field_name in DOCUMENT_LINK_TARGET_FIELDS:
            value = getattr(self, field_name)
            if value is not None:
                return value
        raise AttributeError("لینک سند target ندارد.")

    @property
    def target_type(self) -> str:
        for field_name in DOCUMENT_LINK_TARGET_FIELDS:
            if getattr(self, f"{field_name}_id") is not None:
                return field_name
        return ""

    def clean(self) -> None:
        super().clean()
        selected_fields = [
            field_name
            for field_name in DOCUMENT_LINK_TARGET_FIELDS
            if getattr(self, f"{field_name}_id") is not None
        ]
        if len(selected_fields) != 1:
            raise ValidationError(
                "برای هر لینک سند باید دقیقاً یک موجودیت مرتبط انتخاب شود."
            )
        relations = {"document": self.document}
        relations[selected_fields[0]] = getattr(self, selected_fields[0])
        validate_related_organizations(self, **relations)

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("لینک سند جزئی از سابقه است و قابل حذف مستقیم نیست.")
