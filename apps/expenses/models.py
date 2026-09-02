import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class ExpenseCategory(models.TextChoices):
    MATERIALS = "materials", "Materials"
    LABOR = "labor", "Labor"
    EQUIPMENT = "equipment", "Equipment"
    SUBCONTRACTOR = "subcontractor", "Subcontractor"
    PERMIT = "permit", "Permit"
    OTHER = "other", "Other"


class ExpenseStatus(models.TextChoices):
    RECORDED = "recorded", "Recorded"
    VOID = "void", "Void"


class Expense(models.Model):
    """A real project expense belonging to one organization."""

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    category = models.CharField(
        max_length=30,
        choices=ExpenseCategory.choices,
        default=ExpenseCategory.OTHER,
        db_index=True,
    )
    description = models.CharField(max_length=255)
    vendor_name = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    incurred_on = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=ExpenseStatus.choices,
        default=ExpenseStatus.RECORDED,
        db_index=True,
    )
    receipt_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_updated",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "incurred_on"],
                name="expense_org_project_date_idx",
            ),
            models.Index(
                fields=["organization", "category"],
                name="expense_org_category_idx",
            ),
            models.Index(
                fields=["organization", "deleted_at"],
                name="expense_org_deleted_idx",
            ),
            models.Index(
                fields=["organization", "phase", "incurred_on"],
                name="expense_org_phase_date_idx",
            ),
        ]
        ordering = ["-incurred_on", "-created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.description} - {self.amount}"
