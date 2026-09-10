from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class PaymentDirection(models.TextChoices):
    RECEIPT = "receipt", "دریافت"
    DISBURSEMENT = "disbursement", "پرداخت"


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = "bank_transfer", "انتقال بانکی"
    CASH = "cash", "نقدی"
    CHECK = "check", "چک"
    OTHER = "other", "سایر"


class PaymentStatus(models.TextChoices):
    POSTED = "posted", "ثبت‌شده"
    VOID = "void", "باطل‌شده"


class PaymentAllocationStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    REVERSED = "reversed", "برگشت‌خورده"


class Payment(UUIDModel, TimeStampedModel):
    """An immutable posted cash transaction for one organization and project."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        verbose_name="قرارداد",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        verbose_name="فاز پروژه",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    payment_number = models.CharField("شماره پرداخت", max_length=80)
    direction = models.CharField("جهت تراکنش", max_length=20, choices=PaymentDirection.choices)
    amount = models.DecimalField("مبلغ", max_digits=18, decimal_places=2)
    paid_on = models.DateField("تاریخ پرداخت")
    method = models.CharField(
        "روش پرداخت",
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER,
    )
    counterparty_name = models.CharField("نام طرف حساب", max_length=255)
    party = models.ForeignKey(
        "parties.BusinessParty",
        verbose_name="طرف تجاری",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    reference = models.CharField("شماره مرجع", max_length=120, blank=True)
    notes = models.TextField("یادداشت‌ها", blank=True)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.POSTED,
        db_index=True,
    )
    void_reason = models.TextField("دلیل ابطال", blank=True)
    voided_at = models.DateTimeField("زمان ابطال", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_updated",
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ابطال‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_voided",
    )

    class Meta:
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"
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
                {"contract": "قرارداد باید متعلق به پروژه انتخاب‌شده باشد."}
            )
        if self.phase_id and self.phase.site.project_id != self.project_id:
            raise ValidationError(
                {"phase": "فاز باید متعلق به پروژه انتخاب‌شده باشد."}
            )
        if self.party_id and self.party.archived_at is not None:
            raise ValidationError({"party": "طرف تجاری باید فعال باشد."})

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
                    "جزئیات پرداخت ثبت‌شده قابل تغییر نیست؛ در صورت نیاز پرداخت را باطل کنید."
                )
            if previous.status == PaymentStatus.VOID:
                raise ValidationError("پرداخت باطل‌شده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.payment_number} - {self.counterparty_name}"


class PaymentAllocation(UUIDModel, TimeStampedModel):
    """A controlled allocation of a posted payment to a contract."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="payment_allocations",
    )
    payment = models.ForeignKey(
        Payment, verbose_name="پرداخت", on_delete=models.CASCADE, related_name="allocations"
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        verbose_name="قرارداد",
        on_delete=models.PROTECT,
        related_name="payment_allocations",
    )
    amount = models.DecimalField("مبلغ تخصیص", max_digits=18, decimal_places=2)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=PaymentAllocationStatus.choices,
        default=PaymentAllocationStatus.ACTIVE,
    )
    reversed_at = models.DateTimeField("زمان برگشت", null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="برگشت‌دهنده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_allocations_reversed",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_allocations_created",
    )

    class Meta:
        verbose_name = "تخصیص پرداخت"
        verbose_name_plural = "تخصیص‌های پرداخت"
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
                {"contract": "قرارداد باید متعلق به پروژه پرداخت باشد."}
            )
        if self.amount <= 0:
            raise ValidationError({"amount": "مبلغ تخصیص باید مثبت باشد."})

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
                raise ValidationError("تخصیص پرداخت قابل تغییر نیست.")
            if previous.status == PaymentAllocationStatus.REVERSED:
                raise ValidationError("تخصیص پرداخت برگشت‌خورده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)
