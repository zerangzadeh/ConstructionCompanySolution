"""P9-S16–S20 tenant-scoped attention and support coordination facts."""

import uuid
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel


class ImmutableSupportHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        raise ValidationError("Support history is immutable.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("Support history is immutable.")


class ImmutableSupportHistoryManager(
    models.Manager.from_queryset(ImmutableSupportHistoryQuerySet)
):
    pass


class Notification(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_notifications",
    )
    source_type = models.CharField(max_length=80)
    source_id = models.UUIDField()
    source_version = models.CharField(max_length=80)
    category = models.CharField(max_length=40)
    summary = models.CharField(max_length=240)
    status = models.CharField(max_length=20, default="available")
    read_at = models.DateTimeField(null=True, blank=True)
    operation_key = models.UUIDField(default=uuid.uuid4)

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "recipient",
                    "source_type",
                    "source_id",
                    "source_version",
                    "category",
                ],
                name="support_notification_dedupe_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "recipient", "operation_key"],
                name="support_notification_op_uq",
            ),
        ]


class SupportCase(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_cases_requested",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="support_cases_assigned",
    )
    category = models.CharField(max_length=50)
    priority = models.CharField(max_length=20, default="normal")
    summary = models.CharField(max_length=240)
    status = models.CharField(max_length=20, default="open")
    resolution = models.TextField(blank=True)
    operation_key = models.UUIDField(default=uuid.uuid4)


class SupportCaseEvent(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    case = models.ForeignKey(
        SupportCase, on_delete=models.PROTECT, related_name="events"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    comment = models.TextField(blank=True)
    operation_key = models.UUIDField(default=uuid.uuid4)

    objects = ImmutableSupportHistoryManager()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "actor", "operation_key"],
                name="support_case_event_op_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("Support case history is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("Support case history is immutable.")


class SupportEvidence(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    case = models.ForeignKey(
        SupportCase, on_delete=models.PROTECT, related_name="evidence"
    )
    document = models.ForeignKey("documents.Document", on_delete=models.PROTECT)
    document_version = models.ForeignKey(
        "documents.DocumentVersion", on_delete=models.PROTECT
    )
    sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    objects = ImmutableSupportHistoryManager()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["case", "document_version"], name="support_evidence_version_uq"
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("Support evidence is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("Support evidence is immutable.")


class SupportAccessRequest(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_access_requested",
    )
    purpose = models.CharField(max_length=240)
    scope = models.CharField(max_length=80)
    expires_at = models.DateTimeField()
    tenant_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="support_access_confirmed",
    )
    platform_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="support_access_approved",
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="support_access_revoked",
    )
    status = models.CharField(max_length=20, default="requested")
    operation_key = models.UUIDField(default=uuid.uuid4)
