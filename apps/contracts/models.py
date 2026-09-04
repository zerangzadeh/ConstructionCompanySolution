from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class ContractStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    TERMINATED = "terminated", "Terminated"


class ContractDirection(models.TextChoices):
    RECEIVABLE = "receivable", "Receivable"
    PAYABLE = "payable", "Payable"


class ContractType(models.TextChoices):
    CLIENT = "client", "Client"
    SUBCONTRACT = "subcontract", "Subcontract"
    SUPPLIER = "supplier", "Supplier"
    OTHER = "other", "Other"


class ContractAmendmentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"


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
    party = models.ForeignKey(
        "parties.BusinessParty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracts",
    )
    direction = models.CharField(
        max_length=20, choices=ContractDirection.choices, null=True, blank=True
    )
    contract_type = models.CharField(
        max_length=20, choices=ContractType.choices, null=True, blank=True
    )
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

    def clean(self) -> None:
        super().clean()
        self.contract_number = canonicalize_upper_identifier(self.contract_number)
        if self.project_id:
            validate_related_organizations(
                self,
                project=self.project,
                party=self.party if self.party_id else None,
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.contract_number = canonicalize_upper_identifier(self.contract_number)
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                ContractStatus.ACTIVE,
                ContractStatus.COMPLETED,
                ContractStatus.TERMINATED,
            } and any(
                getattr(previous, field) != getattr(self, field)
                for field in (
                    "title",
                    "counterparty_name",
                    "party_id",
                    "direction",
                    "contract_type",
                    "contract_value",
                    "notes",
                )
            ):
                raise ValidationError(
                    "Finalized contract terms can only change by amendment."
                )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.contract_number} - {self.title}"


class ContractItem(UUIDModel, TimeStampedModel):
    """A draft commercial line; header value remains authoritative in R7."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="contract_items",
    )
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name="items"
    )
    wbs_node = models.ForeignKey(
        "projects.WBSNode",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contract_items",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=30, default="unit")
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contract_items",
    )
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "created_at"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "contract"], name="contract_item_org_ct_idx"
            )
        ]

    @property
    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def clean(self) -> None:
        super().clean()
        relations = {"contract": self.contract} if self.contract_id else {}
        if self.wbs_node_id:
            relations["wbs_node"] = self.wbs_node
        if self.unit_of_measure_id:
            relations["unit_of_measure"] = self.unit_of_measure
        validate_related_organizations(self, **relations)
        if self.wbs_node_id and self.wbs_node.project_id != self.contract.project_id:
            raise ValidationError(
                {"wbs_node": "WBS node must belong to the contract project."}
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


class ContractAmendment(UUIDModel, TimeStampedModel):
    """An approved, immutable adjustment to a finalized contract's terms."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="contract_amendments",
    )
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name="amendments"
    )
    amendment_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    reason = models.TextField()
    value_change = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(
        max_length=20,
        choices=ContractAmendmentStatus.choices,
        default=ContractAmendmentStatus.DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_amendments_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_amendments_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["contract", "amendment_number"],
                name="unique_amendment_number_per_contract",
            )
        ]
        ordering = ["amendment_number"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        if self.contract_id:
            validate_related_organizations(self, contract=self.contract)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status == ContractAmendmentStatus.APPROVED:
                raise ValidationError("Approved amendments are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)
