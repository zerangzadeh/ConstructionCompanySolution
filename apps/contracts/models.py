from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel, UUIDModel


class ContractStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    TERMINATED = "terminated", "Terminated"


class Contract(UUIDModel, TimeStampedModel):
    """A project contract owned by one organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    contract_number = models.CharField(max_length=80)
    title = models.CharField(max_length=255)
    counterparty_name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        db_index=True,
    )
    contract_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    signed_at = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracts_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracts_updated",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "contract_number"],
                name="unique_contract_number_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status"],
                name="contract_org_status_idx",
            ),
            models.Index(
                fields=["organization", "deleted_at"],
                name="contract_org_deleted_idx",
            ),
        ]
        ordering = ["-created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.contract_number} - {self.title}"
