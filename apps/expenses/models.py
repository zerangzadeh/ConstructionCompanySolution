from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.documents.models import AbstractTypedDocumentLink
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class ExpenseDocumentLink(AbstractTypedDocumentLink):
    """Expense-owned append-only evidence link."""

    target_field_name = "expense"
    expense = models.ForeignKey(
        "expenses.Expense",
        on_delete=models.PROTECT,
        related_name="typed_document_links",
    )

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["document", "expense"], name="expense_document_link_uq"
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "document"],
                name="expense_doclink_org_doc_idx",
            )
        ]


class LegacyExpenseCategory(models.TextChoices):
    MATERIALS = "materials", "مصالح"
    LABOR = "labor", "نیروی انسانی"
    EQUIPMENT = "equipment", "تجهیزات"
    SUBCONTRACTOR = "subcontractor", "پیمانکار جزء"
    PERMIT = "permit", "مجوزها"
    OTHER = "other", "سایر"


class ExpenseStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"
    RETURNED = "returned", "بازگردانده‌شده"
    RECORDED = "recorded", "ثبت‌شده"
    VOID = "void", "باطل‌شده"


class ExpenseClassification(models.TextChoices):
    DIRECT = "direct", "مستقیم"
    INDIRECT = "indirect", "غیرمستقیم"


class ExpenseSettlementStatus(models.TextChoices):
    UNSETTLED = "unsettled", "تسویه‌نشده"
    EXTERNAL = "external", "تسویه در مرجع بیرونی"


class ExpenseRecurrenceFrequency(models.TextChoices):
    WEEKLY = "weekly", "هفتگی"
    MONTHLY = "monthly", "ماهانه"


class PlatformExpenseGroup(UUIDModel, TimeStampedModel):
    """Platform-owned canonical grouping for every tenant expense category."""

    code = models.CharField("کد", max_length=30, unique=True)
    name = models.CharField("نام گروه اصلی هزینه", max_length=100, unique=True)
    is_active = models.BooleanField("فعال", default=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_expense_groups_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_expense_groups_updated",
    )

    class Meta:
        verbose_name = "گروه اصلی هزینه"
        verbose_name_plural = "گروه‌های اصلی هزینه"
        ordering = ["name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = self.code.strip().lower()
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("کد و نام گروه اصلی هزینه الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class ExpenseCategory(UUIDModel, TimeStampedModel):
    """A tenant-owned expense classification; legacy category text remains a snapshot."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="expense_categories",
    )
    code = models.CharField("کد", max_length=30)
    name = models.CharField("نام دسته هزینه", max_length=100)
    primary_group = models.ForeignKey(
        PlatformExpenseGroup,
        verbose_name="گروه اصلی هزینه",
        on_delete=models.PROTECT,
        related_name="expense_categories",
    )
    is_active = models.BooleanField("فعال", default=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_categories_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_categories_updated",
    )

    class Meta:
        verbose_name = "دسته هزینه"
        verbose_name_plural = "دسته‌های هزینه"
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
            raise ValidationError("وارد کردن کد و نام دسته هزینه الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class Expense(UUIDModel, TimeStampedModel):
    """A real project expense belonging to one organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        verbose_name="فاز پروژه",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    category = models.CharField(
        "دسته قدیمی هزینه",
        max_length=30,
        choices=LegacyExpenseCategory.choices,
        default=LegacyExpenseCategory.OTHER,
        db_index=True,
    )
    primary_group = models.ForeignKey(
        PlatformExpenseGroup,
        verbose_name="گروه اصلی هزینه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expenses",
    )
    description = models.CharField("شرح هزینه", max_length=255)
    vendor_name = models.CharField("نام فروشنده", max_length=255, blank=True)
    party = models.ForeignKey(
        "parties.BusinessParty",
        verbose_name="طرف تجاری",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    expense_category = models.ForeignKey(
        ExpenseCategory,
        verbose_name="دسته هزینه",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    amount = models.DecimalField(
        "مبلغ",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    incurred_on = models.DateField("تاریخ وقوع هزینه")
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=ExpenseStatus.choices,
        default=ExpenseStatus.RECORDED,
        db_index=True,
    )
    classification = models.CharField(
        max_length=16,
        choices=ExpenseClassification.choices,
        default=ExpenseClassification.DIRECT,
    )
    source_reference = models.CharField(max_length=160, blank=True)
    source_fingerprint = models.CharField(max_length=64, blank=True)
    idempotency_key = models.CharField(max_length=120, blank=True)
    settlement_status = models.CharField(
        max_length=16,
        choices=ExpenseSettlementStatus.choices,
        default=ExpenseSettlementStatus.UNSETTLED,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expenses_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expenses_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expenses_returned",
    )
    returned_at = models.DateTimeField(null=True, blank=True)
    return_reason = models.TextField(blank=True)
    recurrence_template = models.ForeignKey(
        "expenses.RecurringExpenseTemplate",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="proposals",
    )
    recurrence_occurrence_on = models.DateField(null=True, blank=True)
    void_reason = models.TextField("دلیل ابطال", blank=True)
    voided_at = models.DateTimeField("زمان ابطال", null=True, blank=True)
    receipt_reference = models.CharField("مرجع رسید", max_length=120, blank=True)
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_updated",
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ابطال‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_voided",
    )
    deleted_at = models.DateTimeField("زمان حذف", null=True, blank=True)

    class Meta:
        verbose_name = "هزینه"
        verbose_name_plural = "هزینه‌ها"
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
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                condition=~Q(idempotency_key=""),
                name="expense_org_idempotency_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "source_fingerprint"],
                condition=~Q(source_fingerprint="") & ~Q(status=ExpenseStatus.VOID),
                name="expense_org_source_fingerprint_uq",
            ),
            models.UniqueConstraint(
                fields=["recurrence_template", "recurrence_occurrence_on"],
                condition=Q(recurrence_template__isnull=False),
                name="expense_recurrence_occurrence_uq",
            ),
        ]

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
        if self.recurrence_template_id:
            relations["recurrence_template"] = self.recurrence_template
        validate_related_organizations(self, **relations)
        if self.phase_id and self.phase.site.project_id != self.project_id:
            raise ValidationError({"phase": "فاز باید متعلق به پروژه انتخاب‌شده باشد."})
        if self.primary_group_id and self.primary_group.code != self.category:
            raise ValidationError(
                {"primary_group": "گروه اصلی هزینه باید با کد گروه ثبت‌شده سازگار باشد."}
            )
        if self.party_id and self.party.archived_at is not None:
            raise ValidationError({"party": "طرف تجاری باید فعال باشد."})
        if self.expense_category_id and (
            self.expense_category.archived_at is not None
            or not self.expense_category.is_active
        ):
            raise ValidationError({"expense_category": "دسته هزینه باید فعال باشد."})
        if self.recurrence_template_id and (
            self.recurrence_template.project_id != self.project_id
            or self.recurrence_occurrence_on is None
        ):
            raise ValidationError(
                {
                    "recurrence_template": "Recurrence template and occurrence must match the expense project."
                }
            )
        if self.recurrence_occurrence_on and not self.recurrence_template_id:
            raise ValidationError(
                {
                    "recurrence_occurrence_on": "An occurrence date requires a recurrence template."
                }
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "organization_id",
                "project_id",
                "phase_id",
                "category",
                "primary_group_id",
                "description",
                "vendor_name",
                "party_id",
                "expense_category_id",
                "amount",
                "incurred_on",
                "receipt_reference",
                "notes",
                "classification",
                "source_reference",
                "source_fingerprint",
                "idempotency_key",
                "settlement_status",
                "recurrence_template_id",
                "recurrence_occurrence_on",
            )
            if any(
                getattr(previous, field) != getattr(self, field)
                for field in immutable_fields
            ):
                raise ValidationError(
                    "جزئیات هزینه ثبت‌شده قابل تغییر نیست؛ در صورت نیاز هزینه را باطل کنید."
                )
            if previous.status == ExpenseStatus.VOID:
                raise ValidationError("هزینه باطل‌شده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("Expense evidence must be voided and cannot be deleted.")


class ExpenseAllocation(UUIDModel, TimeStampedModel):
    """Conserved, explicitly coded split of one expense; never a GL posting."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    expense = models.ForeignKey(
        Expense, on_delete=models.PROTECT, related_name="allocations"
    )
    sequence = models.PositiveIntegerField()
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="expense_allocations"
    )
    wbs_node = models.ForeignKey("projects.WBSNode", on_delete=models.PROTECT)
    activity = models.ForeignKey(
        "projects.Activity", on_delete=models.PROTECT, null=True, blank=True
    )
    cbs_node = models.ForeignKey("projects.CBSNode", on_delete=models.PROTECT)
    cost_center = models.ForeignKey(
        "projects.CostCenter", on_delete=models.PROTECT, null=True, blank=True
    )
    governing_budget = models.ForeignKey(
        "projects.BudgetVersion", on_delete=models.PROTECT
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    allocation_basis_reference = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expense_allocations_created",
    )

    class Meta:
        ordering = ["sequence"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["expense", "sequence"], name="expense_allocation_sequence_uq"
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=Decimal("0.00")),
                name="expense_allocation_amount_positive",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            expense=self.expense,
            project=self.project,
            wbs_node=self.wbs_node,
            activity=self.activity if self.activity_id else None,
            cbs_node=self.cbs_node,
            cost_center=self.cost_center if self.cost_center_id else None,
            governing_budget=self.governing_budget,
        )
        if self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "WBS must belong to the allocation project."}
            )
        if self.activity_id and (
            self.activity.project_id != self.project_id
            or self.activity.wbs_node_id != self.wbs_node_id
        ):
            raise ValidationError(
                {"activity": "Activity must belong to the selected project and WBS."}
            )
        if self.governing_budget.project_id != self.project_id:
            raise ValidationError(
                {"governing_budget": "Budget must govern the allocation project."}
            )
        if self.governing_budget.status != "accepted":
            raise ValidationError(
                {"governing_budget": "Expense coding requires an accepted budget."}
            )
        if (
            self.cbs_node.structure_version_id
            != self.governing_budget.structure_version_id
        ):
            raise ValidationError(
                {"cbs_node": "CBS must come from the governing budget structure."}
            )
        if (
            self.cost_center_id
            and self.cost_center.structure_version_id
            != self.governing_budget.structure_version_id
        ):
            raise ValidationError(
                {
                    "cost_center": "Cost center must come from the governing budget structure."
                }
            )
        if not self.allocation_basis_reference.strip():
            raise ValidationError(
                {"allocation_basis_reference": "Allocation basis evidence is required."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError(
                "Expense allocations are immutable; replace a draft split instead."
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("Expense allocations are immutable evidence.")


class ExpenseBudgetAssessment(UUIDModel, TimeStampedModel):
    """Immutable advisory snapshot against accepted-budget facts (P4-G10 open)."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    expense = models.ForeignKey(
        Expense, on_delete=models.PROTECT, related_name="budget_assessments"
    )
    allocation = models.ForeignKey(
        ExpenseAllocation, on_delete=models.PROTECT, related_name="budget_assessments"
    )
    governing_budget = models.ForeignKey(
        "projects.BudgetVersion", on_delete=models.PROTECT
    )
    accepted_budget_amount = models.DecimalField(max_digits=20, decimal_places=2)
    prior_approved_expense_amount = models.DecimalField(max_digits=20, decimal_places=2)
    proposed_amount = models.DecimalField(max_digits=20, decimal_places=2)
    remaining_after_proposal = models.DecimalField(max_digits=20, decimal_places=2)
    is_overrun = models.BooleanField()
    control_mode = models.CharField(max_length=32, default="advisory_only")
    assessed_at = models.DateTimeField()

    def clean(self) -> None:
        validate_related_organizations(
            self,
            expense=self.expense,
            allocation=self.allocation,
            governing_budget=self.governing_budget,
        )
        if (
            self.allocation.expense_id != self.expense_id
            or self.allocation.governing_budget_id != self.governing_budget_id
        ):
            raise ValidationError(
                "Budget assessment must match its expense allocation and budget."
            )
        if self.control_mode != "advisory_only":
            raise ValidationError("P4-G10 permits advisory-only budget evidence.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("Budget assessments are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("Budget assessments are append-only evidence.")


class RecurringExpenseTemplate(UUIDModel, TimeStampedModel):
    """A manual proposal schedule; it never posts or approves an expense."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    classification = models.CharField(
        max_length=16, choices=ExpenseClassification.choices
    )
    frequency = models.CharField(
        max_length=16, choices=ExpenseRecurrenceFrequency.choices
    )
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    source_reference_prefix = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(amount__gt=Decimal("0.00")),
                name="recurring_expense_amount_positive",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(self, project=self.project)
        self.description = self.description.strip()
        self.source_reference_prefix = self.source_reference_prefix.strip()
        if not self.description or not self.source_reference_prefix:
            raise ValidationError(
                "Recurring proposal description and source prefix are required."
            )
        if self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "End date cannot precede start date."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
