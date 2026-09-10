from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class ContractStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ACTIVE = "active", "فعال"
    COMPLETED = "completed", "تکمیل‌شده"
    TERMINATED = "terminated", "خاتمه‌یافته"


class ContractDirection(models.TextChoices):
    RECEIVABLE = "receivable", "دریافتنی"
    PAYABLE = "payable", "پرداختنی"


class ContractType(models.TextChoices):
    CLIENT = "client", "قرارداد کارفرمایی"
    SUBCONTRACT = "subcontract", "قرارداد پیمانکار جزء"
    SUPPLIER = "supplier", "قرارداد تأمین‌کننده"
    OTHER = "other", "سایر"


class ContractAmendmentStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    APPROVED = "approved", "تأییدشده"


class Contract(UUIDModel, TimeStampedModel):
    """A project contract owned by one organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    contract_number = models.CharField("شماره قرارداد", max_length=80)
    title = models.CharField("عنوان قرارداد", max_length=255)
    counterparty_name = models.CharField("نام طرف قرارداد", max_length=255)
    party = models.ForeignKey(
        "parties.BusinessParty",
        verbose_name="طرف تجاری",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracts",
    )
    direction = models.CharField(
        "جهت قرارداد", max_length=20, choices=ContractDirection.choices, null=True, blank=True
    )
    contract_type = models.CharField(
        "نوع قرارداد", max_length=20, choices=ContractType.choices, null=True, blank=True
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        db_index=True,
    )
    contract_value = models.DecimalField(
        "مبلغ قرارداد",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    signed_at = models.DateField("تاریخ امضا", null=True, blank=True)
    start_date = models.DateField("تاریخ شروع", null=True, blank=True)
    end_date = models.DateField("تاریخ پایان", null=True, blank=True)
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracts_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contracts_updated",
    )
    deleted_at = models.DateTimeField("زمان حذف", null=True, blank=True)

    class Meta:
        verbose_name = "قرارداد"
        verbose_name_plural = "قراردادها"
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
                    "شرایط قرارداد نهایی‌شده فقط از طریق الحاقیه قابل تغییر است."
                )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.contract_number} - {self.title}"


class ContractItem(UUIDModel, TimeStampedModel):
    """A draft commercial line; header value remains authoritative in R7."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="contract_items",
    )
    contract = models.ForeignKey(
        Contract, verbose_name="قرارداد", on_delete=models.CASCADE, related_name="items"
    )
    wbs_node = models.ForeignKey(
        "projects.WBSNode",
        verbose_name="گره ساختار شکست کار",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contract_items",
    )
    description = models.CharField("شرح ردیف", max_length=255)
    quantity = models.DecimalField("مقدار", max_digits=18, decimal_places=4)
    unit = models.CharField("واحد قدیمی", max_length=30, default="unit")
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contract_items",
    )
    unit_price = models.DecimalField("قیمت واحد", max_digits=18, decimal_places=2)
    sort_order = models.PositiveIntegerField("ترتیب نمایش", default=0)

    class Meta:
        verbose_name = "ردیف قرارداد"
        verbose_name_plural = "ردیف‌های قرارداد"
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
                {"wbs_node": "گره ساختار شکست باید متعلق به پروژه قرارداد باشد."}
            )
        if self.unit_of_measure_id and (
            not self.unit_of_measure.is_active or self.unit_of_measure.archived_at
        ):
            raise ValidationError(
                {"unit_of_measure": "واحد اندازه‌گیری باید فعال باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class ContractAmendment(UUIDModel, TimeStampedModel):
    """An approved, immutable adjustment to a finalized contract's terms."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="contract_amendments",
    )
    contract = models.ForeignKey(
        Contract, verbose_name="قرارداد", on_delete=models.CASCADE, related_name="amendments"
    )
    amendment_number = models.PositiveIntegerField("شماره الحاقیه")
    title = models.CharField("عنوان الحاقیه", max_length=255)
    reason = models.TextField("دلیل")
    value_change = models.DecimalField(
        "تغییر مبلغ",
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=ContractAmendmentStatus.choices,
        default=ContractAmendmentStatus.DRAFT,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تأییدکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_amendments_approved",
    )
    approved_at = models.DateTimeField("زمان تأیید", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contract_amendments_created",
    )

    class Meta:
        verbose_name = "الحاقیه قرارداد"
        verbose_name_plural = "الحاقیه‌های قرارداد"
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
                raise ValidationError("الحاقیه تأییدشده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)
