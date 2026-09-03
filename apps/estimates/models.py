from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel, UUIDModel


class EstimateStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    REVISED = "revised", "Revised"
    ARCHIVED = "archived", "Archived"


class Estimate(UUIDModel, TimeStampedModel):
    """A project estimate belonging to exactly one organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="estimates",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="estimates",
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates",
    )
    estimate_number = models.CharField(max_length=80)
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=EstimateStatus.choices,
        default=EstimateStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates_updated",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "estimate_number"],
                name="unique_estimate_number_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status"],
                name="estimate_org_status_idx",
            ),
            models.Index(
                fields=["organization", "deleted_at"],
                name="estimate_org_deleted_idx",
            ),
            models.Index(
                fields=["organization", "phase", "status"],
                name="estimate_org_phase_status_idx",
            ),
        ]
        ordering = ["-created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.estimate_number} - {self.title}"

    @property
    def total_amount(self) -> Decimal:
        return sum(
            (item.line_total for item in self.items.all()),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class EstimateItem(UUIDModel, TimeStampedModel):
    """A priced line item belonging to one estimate and organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="estimate_items",
    )
    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.CASCADE,
        related_name="items",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=30, default="unit")
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "created_at"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "estimate"],
                name="estimate_item_org_est_idx",
            ),
        ]

    @property
    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def __str__(self) -> str:
        return f"{self.description} ({self.line_total})"
