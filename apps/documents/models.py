import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from core.models import CreatedAtModel, UUIDModel


class DocumentType(models.TextChoices):
    GENERAL = "general", "General"
    CONTRACT = "contract", "Contract"
    DRAWING = "drawing", "Drawing"
    RECEIPT = "receipt", "Receipt"
    PHOTO = "photo", "Photo"
    OTHER = "other", "Other"


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
        on_delete=models.CASCADE,
        related_name="project_documents",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.GENERAL,
    )
    title = models.CharField(max_length=255)
    original_file_name = models.CharField(max_length=255)
    file = models.FileField(upload_to=document_upload_path)
    content_type = models.CharField(max_length=100)
    file_size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_created",
    )
    archive_reason = models.TextField(blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_archived",
    )

    class Meta:
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
