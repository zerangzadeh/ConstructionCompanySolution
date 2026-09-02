import uuid

from django.conf import settings
from django.db import models


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


class Payment(models.Model):
    """An immutable posted cash transaction for one organization and project."""

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
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

    def __str__(self) -> str:
        return f"{self.payment_number} - {self.counterparty_name}"
