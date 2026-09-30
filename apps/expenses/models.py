from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

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
    RECORDED = "recorded", "ثبت‌شده"
    VOID = "void", "باطل‌شده"


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
            raise ValidationError({"phase": "فاز باید متعلق به پروژه انتخاب‌شده باشد."})
        if self.party_id and self.party.archived_at is not None:
            raise ValidationError({"party": "طرف تجاری باید فعال باشد."})
        if self.expense_category_id and (
            self.expense_category.archived_at is not None
            or not self.expense_category.is_active
        ):
            raise ValidationError({"expense_category": "دسته هزینه باید فعال باشد."})

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
                    "جزئیات هزینه ثبت‌شده قابل تغییر نیست؛ در صورت نیاز هزینه را باطل کنید."
                )
            if previous.status == ExpenseStatus.VOID:
                raise ValidationError("هزینه باطل‌شده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)
