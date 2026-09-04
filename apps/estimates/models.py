from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


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
    current_revision = models.ForeignKey(
        "EstimateRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_for_estimates",
    )

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

    def clean(self) -> None:
        super().clean()
        self.estimate_number = canonicalize_upper_identifier(self.estimate_number)
        relations = {}
        if self.project_id:
            relations["project"] = self.project
        if self.phase_id:
            relations["phase"] = self.phase
        if self.contract_id:
            relations["contract"] = self.contract
        validate_related_organizations(self, **relations)
        if self.phase_id and self.phase.site.project_id != self.project_id:
            raise ValidationError(
                {"phase": "The phase must belong to the selected project."}
            )
        if self.contract_id and self.contract.project_id != self.project_id:
            raise ValidationError(
                {"contract": "The contract must belong to the selected project."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.estimate_number = canonicalize_upper_identifier(self.estimate_number)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.estimate_number} - {self.title}"

    @property
    def total_amount(self) -> Decimal:
        if self.current_revision_id:
            return self.current_revision.total_amount
        return sum(
            (item.line_total for item in self.items.all()),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class EstimateRevisionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    SUPERSEDED = "superseded", "Superseded"


class EstimateRevision(UUIDModel, TimeStampedModel):
    """Versioned estimate terms; approvals remain immutable historical evidence."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="estimate_revisions",
    )
    estimate = models.ForeignKey(
        Estimate, on_delete=models.CASCADE, related_name="revisions"
    )
    revision_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=EstimateRevisionStatus.choices,
        default=EstimateRevisionStatus.DRAFT,
    )
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimate_revisions_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimate_revisions_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimate_revisions_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["estimate", "revision_number"],
                name="unique_estimate_revision_number",
            )
        ]
        ordering = ["revision_number"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        if self.estimate_id:
            validate_related_organizations(self, estimate=self.estimate)

    @property
    def total_amount(self) -> Decimal:
        return sum(
            (item.line_total for item in self.items.all()), Decimal("0.00")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                EstimateRevisionStatus.APPROVED,
                EstimateRevisionStatus.SUPERSEDED,
            }:
                raise ValidationError("Finalized estimate revisions are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)


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
    revision = models.ForeignKey(
        EstimateRevision,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=30, default="unit")
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="estimate_items",
    )
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

    def clean(self) -> None:
        super().clean()
        if self.estimate_id:
            relations = {"estimate": self.estimate}
            if self.revision_id:
                relations["revision"] = self.revision
            if self.unit_of_measure_id:
                relations["unit_of_measure"] = self.unit_of_measure
            validate_related_organizations(self, **relations)
            if self.revision_id and self.revision.estimate_id != self.estimate_id:
                raise ValidationError(
                    {"revision": "Revision must belong to the estimate."}
                )
            if self.unit_of_measure_id and (
                not self.unit_of_measure.is_active or self.unit_of_measure.archived_at
            ):
                raise ValidationError(
                    {"unit_of_measure": "Unit of measure must be active."}
                )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
