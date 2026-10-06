from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations

from .models import StockTransaction, Warehouse


class TraceabilityMode(models.TextChoices):
    NONE = "none", "بدون رهگیری"
    LOT = "lot", "سری ساخت/بچ"
    SERIAL = "serial", "شماره سریال"


class TraceQualityStatus(models.TextChoices):
    AVAILABLE = "available", "قابل استفاده"
    QUARANTINED = "quarantined", "قرنطینه"
    CLOSED = "closed", "بسته/مصرف‌شده"


class TraceAllocationDirection(models.TextChoices):
    SOURCE = "source", "مبدأ"
    DESTINATION = "destination", "مقصد"


class ReservationStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ACTIVE = "active", "فعال"
    PARTIALLY_FULFILLED = "partially_fulfilled", "تأمین بخشی"
    FULFILLED = "fulfilled", "تأمین‌شده"
    CANCELLED = "cancelled", "لغوشده"
    EXPIRED = "expired", "منقضی"


class ReservationAllocationStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    FULFILLED = "fulfilled", "تأمین‌شده"
    RELEASED = "released", "آزادشده"


class InventoryCountStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    FROZEN = "frozen", "دامنه منجمد"
    COUNTED = "counted", "شمارش‌شده"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"
    POSTED = "posted", "ثبت تعدیل"
    CANCELLED = "cancelled", "لغوشده"


class InventoryTransferStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    DISPATCHED = "dispatched", "ارسال‌شده"
    IN_TRANSIT = "in_transit", "در راه"
    ACCEPTED = "accepted", "پذیرفته‌شده"
    CANCELLED = "cancelled", "لغوشده"


class TransferExceptionCode(models.TextChoices):
    NONE = "none", "بدون مغایرت"
    SHORTAGE = "shortage", "کسری"
    DAMAGED = "damaged", "آسیب‌دیده"
    REJECTED = "rejected", "ردشده"


class InventoryValuationEventType(models.TextChoices):
    RECEIPT = "receipt", "رسید"
    ISSUE = "issue", "حواله"
    RETURN = "return", "برگشت"
    TRANSFER = "transfer", "انتقال"
    COUNT_ADJUSTMENT = "count_adjustment", "تعدیل شمارش"
    REVERSAL = "reversal", "برگشت ارزش‌گذاری"


class InventoryValuationStatus(models.TextChoices):
    FINALIZED = "finalized", "نهایی‌شده"
    REVERSED = "reversed", "برگشت‌خورده"
    EXCEPTION = "exception", "استثنا"


class DownstreamCostConsumer(models.TextChoices):
    ACCOUNTING = "accounting", "حسابداری"
    PROJECT_CONTROLS = "project_controls", "کنترل پروژه"


class InventoryValuationEvent(UUIDModel, TimeStampedModel):
    """Immutable Inventory value evidence; never a journal or cost actual."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    stock_transaction = models.OneToOneField(
        StockTransaction, on_delete=models.PROTECT, related_name="valuation_event"
    )
    material = models.ForeignKey("materials.Material", on_delete=models.PROTECT)
    event_type = models.CharField(
        max_length=20, choices=InventoryValuationEventType.choices
    )
    status = models.CharField(
        max_length=12,
        choices=InventoryValuationStatus.choices,
        default=InventoryValuationStatus.FINALIZED,
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=24, decimal_places=8)
    value_amount = models.DecimalField(max_digits=24, decimal_places=4)
    currency = models.CharField(max_length=3)
    source_reference = models.CharField(max_length=160, blank=True)
    source_version = models.CharField(max_length=80, blank=True)
    idempotency_key = models.CharField(max_length=96)
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal"
    )
    monetary_precision_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="inventory_valuation_precision_events",
    )
    rounding_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="inventory_valuation_rounding_events",
    )
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_valuations_finalized",
    )
    finalized_at = models.DateTimeField()
    quantity_before = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    value_before = models.DecimalField(
        max_digits=24, decimal_places=4, default=Decimal(0)
    )
    quantity_after = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    value_after = models.DecimalField(
        max_digits=24, decimal_places=4, default=Decimal(0)
    )
    average_cost_after = models.DecimalField(
        max_digits=24, decimal_places=8, default=Decimal(0)
    )

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="inventory_valuation_idempotency_uq",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="inventory_valuation_qty_positive_ck"
            ),
            models.CheckConstraint(
                condition=Q(value_amount__gte=0),
                name="inventory_valuation_value_nonnegative_ck",
            ),
        ]
        indexes: ClassVar[list] = [
            models.Index(
                fields=["organization", "material", "finalized_at"],
                name="inventory_valuation_pool_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self, stock_transaction=self.stock_transaction, material=self.material
        )
        if self.stock_transaction.material_id != self.material_id:
            raise ValidationError(
                "مصالح رویداد ارزش‌گذاری باید با حرکت موجودی یکسان باشد."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("رویداد نهایی ارزش‌گذاری تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class InventoryValuationPool(UUIDModel, TimeStampedModel):
    """One locked tenant/material functional-currency moving-average state."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    material = models.ForeignKey("materials.Material", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal(0))
    value_amount = models.DecimalField(
        max_digits=24, decimal_places=4, default=Decimal(0)
    )
    average_cost = models.DecimalField(
        max_digits=24, decimal_places=8, default=Decimal(0)
    )
    currency = models.CharField(max_length=3)
    monetary_precision_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="inventory_valuation_pools_precision",
    )
    rounding_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="inventory_valuation_pools_rounding",
    )

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "material"],
                name="inventory_valuation_pool_org_material_uq",
            )
        ]


class InventoryValuationException(UUIDModel, TimeStampedModel):
    """Fail-closed value exception; it never supplies or infers a cost."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    stock_transaction = models.OneToOneField(
        StockTransaction, on_delete=models.PROTECT, related_name="valuation_exception"
    )
    material = models.ForeignKey("materials.Material", on_delete=models.PROTECT)
    reason = models.CharField(max_length=80)
    required_authority = models.CharField(max_length=120)
    source_reference = models.CharField(max_length=160, blank=True)
    source_version = models.CharField(max_length=80, blank=True)
    resolved_by_event = models.OneToOneField(
        InventoryValuationEvent,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="resolved_exception",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes: ClassVar[list] = [
            models.Index(
                fields=["organization", "resolved_at"], name="inv_val_exception_idx"
            )
        ]


class DownstreamCostSourceEnvelope(UUIDModel, TimeStampedModel):
    """Idempotent proposal evidence only; downstream authorities create their own facts."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    valuation_event = models.ForeignKey(
        InventoryValuationEvent,
        on_delete=models.PROTECT,
        related_name="downstream_envelopes",
    )
    consumer = models.CharField(max_length=20, choices=DownstreamCostConsumer.choices)
    idempotency_key = models.CharField(max_length=96)
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT
    )
    payload = models.JSONField(default=dict)
    supplied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_cost_envelopes_supplied",
    )
    supplied_at = models.DateTimeField()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "consumer", "idempotency_key"],
                name="inventory_cost_envelope_idempotency_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "consumer", "valuation_event"],
                name="inventory_cost_envelope_source_uq",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("پیشنهاد هزینه نهایی تغییرپذیر نیست.")
        super().save(*args, **kwargs)


class WarehouseBin(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inventory_bins",
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="bins"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_legacy_unlocated = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_bins_created",
    )

    class Meta:
        ordering = ["warehouse", "code"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "warehouse", "code"],
                name="inventory_bin_org_wh_code_uq",
            ),
            models.UniqueConstraint(
                fields=["warehouse"],
                condition=Q(is_legacy_unlocated=True),
                name="inventory_bin_one_legacy_unlocated_uq",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        validate_related_organizations(self, warehouse=self.warehouse)
        if not self.code or not self.name:
            raise ValidationError("کد و نام مکان انبار الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class MaterialTraceabilityProfile(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="material_traceability_profiles",
    )
    material = models.ForeignKey(
        "materials.Material",
        on_delete=models.PROTECT,
        related_name="traceability_profiles",
    )
    version = models.PositiveIntegerField()
    mode = models.CharField(max_length=12, choices=TraceabilityMode.choices)
    expiry_controlled = models.BooleanField(default=False)
    effective_from = models.DateTimeField()
    effective_until = models.DateTimeField(null=True, blank=True)
    reason = models.TextField()
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="traceability_profiles_activated",
    )
    activated_at = models.DateTimeField()

    class Meta:
        ordering = ["material", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["material", "version"],
                name="material_trace_profile_version_uq",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="material_trace_profile_version_positive",
            ),
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gt=models.F("effective_from")),
                name="material_trace_profile_interval_ck",
            ),
            models.CheckConstraint(
                condition=Q(expiry_controlled=False) | ~Q(mode=TraceabilityMode.NONE),
                name="material_trace_expiry_requires_tracking_ck",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, material=self.material)
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل نسخه سیاست رهگیری الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("نسخه فعال سیاست رهگیری تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("نسخه سیاست رهگیری حذف‌پذیر نیست.")


class InventoryLot(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inventory_lots",
    )
    material = models.ForeignKey(
        "materials.Material", on_delete=models.PROTECT, related_name="inventory_lots"
    )
    profile = models.ForeignKey(
        MaterialTraceabilityProfile,
        on_delete=models.PROTECT,
        related_name="lots",
    )
    lot_code = models.CharField(max_length=100)
    manufactured_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=TraceQualityStatus.choices,
        default=TraceQualityStatus.AVAILABLE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_lots_created",
    )

    class Meta:
        ordering = ["material", "lot_code"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "material", "lot_code"],
                name="inventory_lot_org_material_code_uq",
            ),
            models.CheckConstraint(
                condition=Q(expires_on__isnull=True)
                | Q(manufactured_on__isnull=True)
                | Q(expires_on__gte=models.F("manufactured_on")),
                name="inventory_lot_expiry_after_mfg_ck",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.lot_code = canonicalize_upper_identifier(self.lot_code)
        validate_related_organizations(
            self, material=self.material, profile=self.profile
        )
        if self.profile.material_id != self.material_id:
            raise ValidationError("سیاست رهگیری باید متعلق به همین مصالح باشد.")
        if self.profile.mode != TraceabilityMode.LOT:
            raise ValidationError("برای بچ باید سیاست رهگیری بچ فعال باشد.")
        if self.profile.expiry_controlled and self.expires_on is None:
            raise ValidationError(
                {"expires_on": "تاریخ انقضا برای این مصالح الزامی است."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if any(
                getattr(previous, field) != getattr(self, field)
                for field in (
                    "organization_id",
                    "material_id",
                    "profile_id",
                    "lot_code",
                )
            ):
                raise ValidationError("هویت بچ موجودی تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class InventorySerial(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inventory_serials",
    )
    material = models.ForeignKey(
        "materials.Material",
        on_delete=models.PROTECT,
        related_name="inventory_serials",
    )
    profile = models.ForeignKey(
        MaterialTraceabilityProfile,
        on_delete=models.PROTECT,
        related_name="serials",
    )
    serial_number = models.CharField(max_length=120)
    expires_on = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=TraceQualityStatus.choices,
        default=TraceQualityStatus.AVAILABLE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_serials_created",
    )

    class Meta:
        ordering = ["material", "serial_number"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "material", "serial_number"],
                name="inventory_serial_org_material_num_uq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.serial_number = canonicalize_upper_identifier(self.serial_number)
        validate_related_organizations(
            self, material=self.material, profile=self.profile
        )
        if self.profile.material_id != self.material_id:
            raise ValidationError("سیاست رهگیری باید متعلق به همین مصالح باشد.")
        if self.profile.mode != TraceabilityMode.SERIAL:
            raise ValidationError("برای سریال باید سیاست رهگیری سریال فعال باشد.")
        if self.profile.expiry_controlled and self.expires_on is None:
            raise ValidationError(
                {"expires_on": "تاریخ انقضا برای این مصالح الزامی است."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if any(
                getattr(previous, field) != getattr(self, field)
                for field in (
                    "organization_id",
                    "material_id",
                    "profile_id",
                    "serial_number",
                )
            ):
                raise ValidationError("هویت سریال موجودی تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class StockTraceAllocation(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="stock_trace_allocations",
    )
    stock_transaction = models.ForeignKey(
        StockTransaction,
        on_delete=models.PROTECT,
        related_name="trace_allocations",
    )
    direction = models.CharField(
        max_length=12, choices=TraceAllocationDirection.choices
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="trace_allocations"
    )
    bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_allocations",
    )
    lot = models.ForeignKey(
        InventoryLot,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_allocations",
    )
    serial = models.ForeignKey(
        InventorySerial,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_allocations",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    is_legacy_unknown = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_trace_allocations_created",
    )

    class Meta:
        ordering = ["stock_transaction", "direction", "created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="stock_trace_allocation_qty_gt_0"
            ),
            models.CheckConstraint(
                condition=~(Q(lot__isnull=False) & Q(serial__isnull=False)),
                name="stock_trace_lot_or_serial_ck",
            ),
            models.UniqueConstraint(
                fields=["stock_transaction", "direction", "serial"],
                condition=Q(serial__isnull=False),
                name="stock_trace_tx_direction_serial_uq",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            stock_transaction=self.stock_transaction,
            warehouse=self.warehouse,
            bin=self.bin,
            lot=self.lot,
            serial=self.serial,
        )
        expected_warehouse_id = (
            self.stock_transaction.source_warehouse_id
            if self.direction == TraceAllocationDirection.SOURCE
            else self.stock_transaction.destination_warehouse_id
        )
        if expected_warehouse_id != self.warehouse_id:
            raise ValidationError("جهت تخصیص رهگیری با انبار تراکنش سازگار نیست.")
        if self.bin_id and self.bin.warehouse_id != self.warehouse_id:
            raise ValidationError("مکان باید متعلق به انبار تخصیص باشد.")
        if self.lot_id and self.lot.material_id != self.stock_transaction.material_id:
            raise ValidationError("بچ باید متعلق به مصالح تراکنش باشد.")
        if self.serial_id:
            if self.serial.material_id != self.stock_transaction.material_id:
                raise ValidationError("سریال باید متعلق به مصالح تراکنش باشد.")
            if self.quantity != Decimal("1.0000"):
                raise ValidationError("مقدار هر سریال باید دقیقاً یک باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("تخصیص نهایی رهگیری تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("تخصیص رهگیری حذف‌پذیر نیست.")


class InventoryReservation(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inventory_reservations",
    )
    reservation_number = models.CharField(max_length=80)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="inventory_reservations",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_reservations",
    )
    wbs_node = models.ForeignKey(
        "projects.WBSNode",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_reservations",
    )
    activity = models.ForeignKey(
        "projects.Activity",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_reservations",
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="reservations"
    )
    material = models.ForeignKey(
        "materials.Material",
        on_delete=models.PROTECT,
        related_name="inventory_reservations",
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="inventory_reservations",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    need_by = models.DateField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=24,
        choices=ReservationStatus.choices,
        default=ReservationStatus.DRAFT,
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_reservations_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_reservations_updated",
    )

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "reservation_number"],
                name="inventory_reservation_org_number_uq",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="inventory_reservation_qty_gt_0"
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.reservation_number = canonicalize_upper_identifier(self.reservation_number)
        validate_related_organizations(
            self,
            project=self.project,
            site=self.site,
            wbs_node=self.wbs_node,
            activity=self.activity,
            warehouse=self.warehouse,
            material=self.material,
            unit_of_measure=self.unit_of_measure,
        )
        if self.warehouse.project_id and self.warehouse.project_id != self.project_id:
            raise ValidationError("انبار پروژه‌ای باید متعلق به پروژه رزرو باشد.")
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError("کارگاه باید متعلق به پروژه رزرو باشد.")
        if self.wbs_node_id and self.wbs_node.project_id != self.project_id:
            raise ValidationError("WBS باید متعلق به پروژه رزرو باشد.")
        if self.activity_id and self.activity.project_id != self.project_id:
            raise ValidationError("فعالیت باید متعلق به پروژه رزرو باشد.")
        if (
            self.activity_id
            and self.wbs_node_id
            and self.activity.wbs_node_id != self.wbs_node_id
        ):
            raise ValidationError("فعالیت باید متعلق به WBS رزرو باشد.")
        if self.material.unit_of_measure_id != self.unit_of_measure_id:
            raise ValidationError("واحد رزرو باید واحد اصلی مصالح باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class InventoryReservationAllocation(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inventory_reservation_allocations",
    )
    reservation = models.ForeignKey(
        InventoryReservation, on_delete=models.PROTECT, related_name="allocations"
    )
    bin = models.ForeignKey(
        WarehouseBin, on_delete=models.PROTECT, null=True, blank=True
    )
    lot = models.ForeignKey(
        InventoryLot, on_delete=models.PROTECT, null=True, blank=True
    )
    serial = models.ForeignKey(
        InventorySerial, on_delete=models.PROTECT, null=True, blank=True
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    fulfilled_quantity = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("0.0000")
    )
    released_quantity = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("0.0000")
    )
    status = models.CharField(
        max_length=16,
        choices=ReservationAllocationStatus.choices,
        default=ReservationAllocationStatus.ACTIVE,
    )
    fulfillment_transaction = models.ForeignKey(
        StockTransaction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reservation_fulfillments",
    )
    release_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["reservation", "created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="reservation_allocation_qty_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(fulfilled_quantity__gte=0) & Q(released_quantity__gte=0),
                name="reservation_allocation_progress_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(fulfilled_quantity__lte=models.F("quantity"))
                & Q(released_quantity__lte=models.F("quantity")),
                name="reservation_allocation_progress_lte_qty",
            ),
            models.CheckConstraint(
                condition=~(Q(lot__isnull=False) & Q(serial__isnull=False)),
                name="reservation_allocation_lot_or_serial_ck",
            ),
        ]

    @property
    def open_quantity(self) -> Decimal:
        return self.quantity - self.fulfilled_quantity - self.released_quantity

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            reservation=self.reservation,
            bin=self.bin,
            lot=self.lot,
            serial=self.serial,
            fulfillment_transaction=self.fulfillment_transaction,
        )
        if self.bin_id and self.bin.warehouse_id != self.reservation.warehouse_id:
            raise ValidationError("مکان رزرو باید متعلق به انبار رزرو باشد.")
        if self.lot_id and self.lot.material_id != self.reservation.material_id:
            raise ValidationError("بچ رزرو باید متعلق به مصالح رزرو باشد.")
        if self.serial_id:
            if self.serial.material_id != self.reservation.material_id:
                raise ValidationError("سریال رزرو باید متعلق به مصالح رزرو باشد.")
            if self.quantity != Decimal("1.0000"):
                raise ValidationError("رزرو هر سریال باید دقیقاً یک باشد.")
        if self.fulfilled_quantity + self.released_quantity > self.quantity:
            raise ValidationError("مقدار تأمین و آزادشده از تخصیص بیشتر است.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class InventoryCount(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inventory_counts",
    )
    count_number = models.CharField(max_length=80)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="inventory_counts"
    )
    bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_counts",
    )
    status = models.CharField(
        max_length=16,
        choices=InventoryCountStatus.choices,
        default=InventoryCountStatus.DRAFT,
    )
    frozen_at = models.DateTimeField(null=True, blank=True)
    stock_watermark = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_counts_created",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_counts_submitted",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_counts_approved",
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_counts_posted",
    )

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "count_number"],
                name="inventory_count_org_number_uq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.count_number = canonicalize_upper_identifier(self.count_number)
        validate_related_organizations(self, warehouse=self.warehouse, bin=self.bin)
        if self.bin_id and self.bin.warehouse_id != self.warehouse_id:
            raise ValidationError("مکان شمارش باید متعلق به انبار باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class InventoryCountLine(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inventory_count_lines",
    )
    inventory_count = models.ForeignKey(
        InventoryCount, on_delete=models.PROTECT, related_name="lines"
    )
    material = models.ForeignKey("materials.Material", on_delete=models.PROTECT)
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure", on_delete=models.PROTECT
    )
    bin = models.ForeignKey(
        WarehouseBin, on_delete=models.PROTECT, null=True, blank=True
    )
    lot = models.ForeignKey(
        InventoryLot, on_delete=models.PROTECT, null=True, blank=True
    )
    serial = models.ForeignKey(
        InventorySerial, on_delete=models.PROTECT, null=True, blank=True
    )
    expected_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    counted_quantity = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    variance_reason = models.TextField(blank=True)
    adjustment_transaction = models.OneToOneField(
        StockTransaction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="count_line",
    )

    class Meta:
        ordering = ["material", "created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(expected_quantity__gte=0),
                name="inventory_count_expected_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(counted_quantity__isnull=True) | Q(counted_quantity__gte=0),
                name="inventory_count_counted_nonnegative",
            ),
            models.CheckConstraint(
                condition=~(Q(lot__isnull=False) & Q(serial__isnull=False)),
                name="inventory_count_line_lot_or_serial_ck",
            ),
        ]

    @property
    def variance(self) -> Decimal | None:
        if self.counted_quantity is None:
            return None
        return self.counted_quantity - self.expected_quantity

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            inventory_count=self.inventory_count,
            material=self.material,
            unit_of_measure=self.unit_of_measure,
            bin=self.bin,
            lot=self.lot,
            serial=self.serial,
            adjustment_transaction=self.adjustment_transaction,
        )
        if self.material.unit_of_measure_id != self.unit_of_measure_id:
            raise ValidationError("واحد شمارش باید واحد اصلی مصالح باشد.")
        if self.bin_id and self.bin.warehouse_id != self.inventory_count.warehouse_id:
            raise ValidationError("مکان خط شمارش باید متعلق به انبار شمارش باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class InventoryTransfer(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inventory_transfers",
    )
    transfer_number = models.CharField(max_length=80)
    source_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="custody_transfers_out"
    )
    destination_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="custody_transfers_in"
    )
    status = models.CharField(
        max_length=16,
        choices=InventoryTransferStatus.choices,
        default=InventoryTransferStatus.DRAFT,
    )
    dispatched_at = models.DateTimeField(null=True, blank=True)
    in_transit_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_transfers_created",
    )
    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_transfers_dispatched",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_transfers_accepted",
    )

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "transfer_number"],
                name="inventory_transfer_org_number_uq",
            ),
            models.CheckConstraint(
                condition=~Q(source_warehouse=models.F("destination_warehouse")),
                name="inventory_transfer_distinct_warehouses_ck",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.transfer_number = canonicalize_upper_identifier(self.transfer_number)
        validate_related_organizations(
            self,
            source_warehouse=self.source_warehouse,
            destination_warehouse=self.destination_warehouse,
        )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class InventoryTransferLine(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inventory_transfer_lines",
    )
    transfer = models.ForeignKey(
        InventoryTransfer, on_delete=models.PROTECT, related_name="lines"
    )
    material = models.ForeignKey("materials.Material", on_delete=models.PROTECT)
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure", on_delete=models.PROTECT
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    source_bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfer_lines_out",
    )
    destination_bin = models.ForeignKey(
        WarehouseBin,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfer_lines_in",
    )
    lot = models.ForeignKey(
        InventoryLot, on_delete=models.PROTECT, null=True, blank=True
    )
    serial = models.ForeignKey(
        InventorySerial, on_delete=models.PROTECT, null=True, blank=True
    )
    accepted_quantity = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("0.0000")
    )
    exception_code = models.CharField(
        max_length=12,
        choices=TransferExceptionCode.choices,
        default=TransferExceptionCode.NONE,
    )
    exception_reason = models.TextField(blank=True)
    exception_resolved_at = models.DateTimeField(null=True, blank=True)
    exception_resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_transfer_exceptions_resolved",
    )
    dispatch_transaction = models.OneToOneField(
        StockTransaction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custody_dispatch_line",
    )
    receipt_transaction = models.OneToOneField(
        StockTransaction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custody_receipt_line",
    )

    class Meta:
        ordering = ["transfer", "created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="inventory_transfer_line_qty_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(accepted_quantity__gte=0)
                & Q(accepted_quantity__lte=models.F("quantity")),
                name="inventory_transfer_accepted_range_ck",
            ),
            models.CheckConstraint(
                condition=~(Q(lot__isnull=False) & Q(serial__isnull=False)),
                name="inventory_transfer_line_lot_or_serial_ck",
            ),
        ]

    @property
    def exception_quantity(self) -> Decimal:
        return self.quantity - self.accepted_quantity

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            transfer=self.transfer,
            material=self.material,
            unit_of_measure=self.unit_of_measure,
            source_bin=self.source_bin,
            destination_bin=self.destination_bin,
            lot=self.lot,
            serial=self.serial,
            dispatch_transaction=self.dispatch_transaction,
            receipt_transaction=self.receipt_transaction,
        )
        if self.material.unit_of_measure_id != self.unit_of_measure_id:
            raise ValidationError("واحد انتقال باید واحد اصلی مصالح باشد.")
        if (
            self.source_bin_id
            and self.source_bin.warehouse_id != self.transfer.source_warehouse_id
        ):
            raise ValidationError("مکان مبدأ باید متعلق به انبار مبدأ باشد.")
        if (
            self.destination_bin_id
            and self.destination_bin.warehouse_id
            != self.transfer.destination_warehouse_id
        ):
            raise ValidationError("مکان مقصد باید متعلق به انبار مقصد باشد.")
        if self.lot_id and self.lot.material_id != self.material_id:
            raise ValidationError("بچ انتقال باید متعلق به مصالح باشد.")
        if self.serial_id:
            if self.serial.material_id != self.material_id:
                raise ValidationError("سریال انتقال باید متعلق به مصالح باشد.")
            if self.quantity != Decimal("1.0000"):
                raise ValidationError("مقدار انتقال هر سریال باید دقیقاً یک باشد.")
        outcome_recorded = (
            self.accepted_quantity > 0
            or self.exception_code != TransferExceptionCode.NONE
            or bool(self.exception_reason.strip())
            or self.receipt_transaction_id is not None
        )
        if outcome_recorded and self.accepted_quantity < self.quantity:
            if (
                self.exception_code == TransferExceptionCode.NONE
                or not self.exception_reason.strip()
            ):
                raise ValidationError("مغایرت انتقال به نوع و دلیل نیاز دارد.")
        elif outcome_recorded and self.exception_code != TransferExceptionCode.NONE:
            raise ValidationError("انتقال بدون کسری نباید نوع مغایرت داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)
