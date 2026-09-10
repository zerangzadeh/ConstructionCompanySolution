import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class DocumentType(models.TextChoices):
    GENERAL = "general", "عمومی"
    CONTRACT = "contract", "قرارداد"
    DRAWING = "drawing", "نقشه"
    RECEIPT = "receipt", "رسید"
    PHOTO = "photo", "تصویر"
    OTHER = "other", "سایر"


def document_upload_path(instance: "ProjectDocument", filename: str) -> str:
    """Store files under non-guessable, organization-specific private paths."""

    extension = Path(filename).suffix.lower()
    return (
        f"organizations/{instance.organization_id}/projects/{instance.project_id}/"
        f"documents/{uuid.uuid4()}{extension}"
    )


class ProjectDocument(UUIDModel, CreatedAtModel):
    """An immutable, private file associated with a tenant project."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="project_documents",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        verbose_name="پرداخت",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    document_type = models.CharField(
        "نوع سند",
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.GENERAL,
    )
    title = models.CharField("عنوان سند", max_length=255)
    original_file_name = models.CharField("نام اصلی فایل", max_length=255)
    file = models.FileField("فایل", upload_to=document_upload_path, max_length=255)
    content_type = models.CharField("نوع محتوای فایل", max_length=100)
    file_size = models.PositiveBigIntegerField("حجم فایل")
    sha256 = models.CharField("SHA-256", max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بارگذاری‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_created",
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
        verbose_name = "سند پروژه"
        verbose_name_plural = "اسناد پروژه"
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "created_at"],
                name="doc_org_project_created_idx",
            ),
            models.Index(
                fields=["organization", "payment"],
                name="doc_org_payment_idx",
            ),
        ]
        ordering = ["-created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        relations = {}
        if self.project_id:
            relations["project"] = self.project
        if self.payment_id:
            relations["payment"] = self.payment
        validate_related_organizations(self, **relations)
        if self.payment_id and self.payment.project_id != self.project_id:
            raise ValidationError(
                {"payment": "پرداخت باید متعلق به پروژه انتخاب‌شده باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
