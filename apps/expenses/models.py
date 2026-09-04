from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class LegacyExpenseCategory(models.TextChoices):
    MATERIALS = "materials", "Materials"
    LABOR = "labor", "Labor"
    EQUIPMENT = "equipment", "Equipment"
    SUBCONTRACTOR = "subcontractor", "Subcontractor"
    PERMIT = "permit", "Permit"
    OTHER = "other", "Other"


class ExpenseStatus(models.TextChoices):
    RECORDED = "recorded", "Recorded"
    VOID = "void", "Void"


class ExpenseCategory(UUIDModel, TimeStampedModel):
    """A tenant-owned expense classification; legacy category text remains a snapshot."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="expense_categories",
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_categories_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_categories_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_expense_category_code_per_organization",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "is_active"],
                name="expense_cat_org_active_idx",
            )
        ]
        ordering = ["name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().lower()
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("Expense category code and name are required.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class Expense(UUIDModel, TimeStampedModel):
    """A real project expense belonging to one organization."""

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
        choices=LegacyExpenseCategory.choices,
        default=LegacyExpenseCategory.OTHER,
        db_index=True,
    )
    description = models.CharField(max_length=255)
    vendor_name = models.CharField(max_length=255, blank=True)
    party = models.ForeignKey(
        "parties.BusinessParty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    expense_category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
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
    void_reason = models.TextField(blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    receipt_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
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
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_voided",
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

    def clean(self) -> None:
        super().clean()
        relations = {}
        if self.project_id:
            relations["project"] = self.project
        if self.phase_id:
            relations["phase"] = self.phase
        if self.party_id:
            relations["party"] = self.party
        if self.expense_category_id:
            relations["expense_category"] = self.expense_category
        validate_related_organizations(self, **relations)
        if self.phase_id and self.phase.site.project_id != self.project_id:
            raise ValidationError(
                {"phase": "The phase must belong to the selected project."}
            )
        if self.party_id and self.party.archived_at is not None:
            raise ValidationError({"party": "The party must be active."})
        if self.expense_category_id and (
            self.expense_category.archived_at is not None
            or not self.expense_category.is_active
        ):
            raise ValidationError(
                {"expense_category": "The expense category must be active."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "organization_id",
                "project_id",
                "phase_id",
                "category",
                "description",
                "vendor_name",
                "party_id",
                "expense_category_id",
                "amount",
                "incurred_on",
                "receipt_reference",
                "notes",
            )
            if any(
                getattr(previous, field) != getattr(self, field)
                for field in immutable_fields
            ):
                raise ValidationError(
                    "Recorded expense details are immutable; void the expense instead."
                )
            if previous.status == ExpenseStatus.VOID:
                raise ValidationError("Voided expenses are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)
