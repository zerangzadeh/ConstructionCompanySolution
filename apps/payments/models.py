from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class PaymentDirection(models.TextChoices):
    RECEIPT = "receipt", "Receipt"
    DISBURSEMENT = "disbursement", "Disbursement"


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = "bank_transfer", "Bank transfer"
    CASH = "cash", "Cash"
    CHECK = "check", "Check"
    OTHER = "other", "Other"


class PaymentStatus(models.TextChoices):
    POSTED = "posted", "Posted"
    VOID = "void", "Void"


class PaymentAllocationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REVERSED = "reversed", "Reversed"


class Payment(UUIDModel, TimeStampedModel):
    """An immutable posted cash transaction for one organization and project."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    payment_number = models.CharField(max_length=80)
    direction = models.CharField(max_length=20, choices=PaymentDirection.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    paid_on = models.DateField()
    method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER,
    )
    counterparty_name = models.CharField(max_length=255)
    party = models.ForeignKey(
        "parties.BusinessParty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.POSTED,
        db_index=True,
    )
    void_reason = models.TextField(blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_updated",
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_voided",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "payment_number"],
                name="unique_payment_number_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "paid_on", "status"],
                name="payment_org_paid_status_idx",
            ),
            models.Index(
                fields=["organization", "project", "paid_on"],
                name="payment_org_project_paid_idx",
            ),
        ]
        ordering = ["-paid_on", "-created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.payment_number = canonicalize_upper_identifier(self.payment_number)
        relations = {}
        if self.project_id:
            relations["project"] = self.project
        if self.contract_id:
            relations["contract"] = self.contract
        if self.phase_id:
            relations["phase"] = self.phase
        if self.party_id:
            relations["party"] = self.party
        validate_related_organizations(self, **relations)
        if self.contract_id and self.contract.project_id != self.project_id:
            raise ValidationError(
                {"contract": "The contract must belong to the selected project."}
            )
        if self.phase_id and self.phase.site.project_id != self.project_id:
            raise ValidationError(
                {"phase": "The phase must belong to the selected project."}
            )
        if self.party_id and self.party.archived_at is not None:
            raise ValidationError({"party": "The party must be active."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.payment_number = canonicalize_upper_identifier(self.payment_number)
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "organization_id",
                "project_id",
                "contract_id",
                "phase_id",
                "payment_number",
                "direction",
                "amount",
                "paid_on",
                "method",
                "counterparty_name",
                "party_id",
                "reference",
                "notes",
            )
            if any(
                getattr(previous, field) != getattr(self, field)
                for field in immutable_fields
            ):
                raise ValidationError(
                    "Posted payment details are immutable; void the payment instead."
                )
            if previous.status == PaymentStatus.VOID:
                raise ValidationError("Voided payments are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.payment_number} - {self.counterparty_name}"


class PaymentAllocation(UUIDModel, TimeStampedModel):
    """A controlled allocation of a posted payment to a contract."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="payment_allocations",
    )
    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="allocations"
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.PROTECT,
        related_name="payment_allocations",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=PaymentAllocationStatus.choices,
        default=PaymentAllocationStatus.ACTIVE,
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_allocations_reversed",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_allocations_created",
    )

    class Meta:
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "payment", "status"],
                name="alloc_org_payment_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        relations = {}
        if self.payment_id:
            relations["payment"] = self.payment
        if self.contract_id:
            relations["contract"] = self.contract
        validate_related_organizations(self, **relations)
        if (
            self.payment_id
            and self.contract_id
            and self.payment.project_id != self.contract.project_id
        ):
            raise ValidationError(
                {"contract": "The contract must belong to the payment project."}
            )
        if self.amount <= 0:
            raise ValidationError({"amount": "Allocation amount must be positive."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "organization_id",
                "payment_id",
                "contract_id",
                "amount",
            )
            if any(
                getattr(previous, field) != getattr(self, field)
                for field in immutable_fields
            ):
                raise ValidationError("Payment allocations are immutable.")
            if previous.status == PaymentAllocationStatus.REVERSED:
                raise ValidationError("Reversed payment allocations are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)
