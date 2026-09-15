import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

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
        "فایل", upload_to=document_version_upload_path, max_length=255
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
        "payments.Payment",
        verbose_name="پرداخت",
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
