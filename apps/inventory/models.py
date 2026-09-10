from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class StockTransactionType(models.TextChoices):
    RECEIPT = "receipt", "ورود از خرید"
    ISSUE = "issue", "حواله خروج"
    ADJUSTMENT_IN = "adjustment_in", "تعدیل افزایشی"
    ADJUSTMENT_OUT = "adjustment_out", "تعدیل کاهشی"
    TRANSFER = "transfer", "انتقال بین انبارها"
    REVERSAL = "reversal", "برگشت تراکنش"


class StockTransactionStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    POSTED = "posted", "ثبت‌شده"
    REVERSED = "reversed", "برگشت‌خورده"


class Warehouse(UUIDModel, TimeStampedModel):
    """A tenant-owned central or project-specific material storage location."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="warehouses",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="warehouses",
    )
    code = models.CharField("کد انبار", max_length=50)
    name = models.CharField("نام انبار", max_length=255)
    location = models.TextField("محل انبار", blank=True)
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouses_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouses_updated",
    )

    class Meta:
        verbose_name = "انبار"
        verbose_name_plural = "انبارها"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="uq_warehouse_org_code",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "is_active"],
                name="warehouse_org_active_idx",
            ),
            models.Index(
                fields=["organization", "project", "is_active"],
                name="warehouse_org_proj_idx",
            ),
        ]
        ordering = ["name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        self.location = self.location.strip()
        if not self.code or not self.name:
            raise ValidationError("وارد کردن کد و نام انبار الزامی است.")
        if self.project_id:
            validate_related_organizations(self, project=self.project)
            if self.project.deleted_at is not None:
                raise ValidationError({"project": "پروژه باید فعال باشد."})
        if self.archived_at is not None and self.is_active:
            raise ValidationError("انبار بایگانی‌شده نمی‌تواند فعال باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            has_history = (
                self.outgoing_stock_transactions.exists()
                or self.incoming_stock_transactions.exists()
            )
            if has_history and any(
                getattr(previous, field) != getattr(self, field)
                for field in ("organization_id", "project_id")
            ):
                raise ValidationError(
                    "سازمان یا پروژه انباری که سابقه موجودی دارد قابل تغییر نیست."
                )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("انبارها باید به‌جای حذف، بایگانی شوند.")

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class StockTransactionQuerySet(models.QuerySet):
    def delete(self) -> tuple[int, dict[str, int]]:
        if self.exclude(status=StockTransactionStatus.DRAFT).exists():
            raise ValidationError("تراکنش ثبت‌شده انبار قابل حذف نیست.")
        return super().delete()


class StockTransaction(UUIDModel, TimeStampedModel):
    """An immutable-after-posting material movement and inventory source of truth."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="stock_transactions",
    )
    transaction_number = models.CharField("شماره تراکنش انبار", max_length=80)
    transaction_type = models.CharField(
        "نوع تراکنش",
        max_length=20,
        choices=StockTransactionType.choices,
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=StockTransactionStatus.choices,
        default=StockTransactionStatus.DRAFT,
        db_index=True,
    )
    source_warehouse = models.ForeignKey(
        Warehouse,
        verbose_name="انبار مبدأ",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="outgoing_stock_transactions",
    )
    destination_warehouse = models.ForeignKey(
        Warehouse,
        verbose_name="انبار مقصد",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="incoming_stock_transactions",
    )
    material = models.ForeignKey(
        "materials.Material",
        verbose_name="مصالح",
        on_delete=models.PROTECT,
        related_name="stock_transactions",
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        related_name="stock_transactions",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_transactions",
    )
    goods_receipt_item = models.ForeignKey(
        "procurement.GoodsReceiptItem",
        verbose_name="ردیف رسید کالا",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_transactions",
    )
    reversal_of = models.OneToOneField(
        "self",
        verbose_name="تراکنش اصلی",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal",
    )
    quantity = models.DecimalField("مقدار", max_digits=18, decimal_places=4)
    occurred_at = models.DateTimeField("زمان وقوع")
    reference = models.CharField("شماره مرجع", max_length=120, blank=True)
    notes = models.TextField("یادداشت‌ها", blank=True)
    posted_at = models.DateTimeField("زمان ثبت", null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_transactions_posted",
    )
    reversed_at = models.DateTimeField("زمان برگشت", null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="برگشت‌دهنده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_transactions_reversed",
    )
    reversal_reason = models.TextField("دلیل برگشت", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_transactions_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_transactions_updated",
    )

    objects = models.Manager.from_queryset(StockTransactionQuerySet)()

    class Meta:
        verbose_name = "تراکنش انبار"
        verbose_name_plural = "تراکنش‌های انبار"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "transaction_number"],
                name="uq_stock_tx_org_num",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="stock_tx_qty_gt_0",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(source_warehouse__isnull=False)
                    | models.Q(destination_warehouse__isnull=False)
                ),
                name="stock_tx_has_warehouse",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(source_warehouse__isnull=True)
                    | models.Q(destination_warehouse__isnull=True)
                    | ~models.Q(source_warehouse=models.F("destination_warehouse"))
                ),
                name="stock_tx_distinct_warehouses",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        transaction_type=StockTransactionType.RECEIPT,
                        source_warehouse__isnull=True,
                        destination_warehouse__isnull=False,
                        goods_receipt_item__isnull=False,
                        reversal_of__isnull=True,
                    )
                    | models.Q(
                        transaction_type=StockTransactionType.ISSUE,
                        source_warehouse__isnull=False,
                        destination_warehouse__isnull=True,
                        project__isnull=False,
                        goods_receipt_item__isnull=True,
                        reversal_of__isnull=True,
                    )
                    | models.Q(
                        transaction_type=StockTransactionType.ADJUSTMENT_IN,
                        source_warehouse__isnull=True,
                        destination_warehouse__isnull=False,
                        goods_receipt_item__isnull=True,
                        reversal_of__isnull=True,
                    )
                    | models.Q(
                        transaction_type=StockTransactionType.ADJUSTMENT_OUT,
                        source_warehouse__isnull=False,
                        destination_warehouse__isnull=True,
                        goods_receipt_item__isnull=True,
                        reversal_of__isnull=True,
                    )
                    | models.Q(
                        transaction_type=StockTransactionType.TRANSFER,
                        source_warehouse__isnull=False,
                        destination_warehouse__isnull=False,
                        goods_receipt_item__isnull=True,
                        reversal_of__isnull=True,
                    )
                    | models.Q(
                        transaction_type=StockTransactionType.REVERSAL,
                        goods_receipt_item__isnull=True,
                        reversal_of__isnull=False,
                    )
                ),
                name="stock_tx_type_shape",
            ),
            models.UniqueConstraint(
                fields=["goods_receipt_item"],
                condition=(
                    models.Q(goods_receipt_item__isnull=False)
                    & models.Q(
                        status__in=[
                            StockTransactionStatus.DRAFT,
                            StockTransactionStatus.POSTED,
                        ]
                    )
                ),
                name="uq_active_tx_goods_receipt_item",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "material", "status"],
                name="stock_tx_org_mat_status_idx",
            ),
            models.Index(
                fields=["organization", "source_warehouse", "occurred_at"],
                name="stock_tx_org_source_idx",
            ),
            models.Index(
                fields=["organization", "destination_warehouse", "occurred_at"],
                name="stock_tx_org_dest_idx",
            ),
        ]
        ordering = ["-occurred_at", "-created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.transaction_number = canonicalize_upper_identifier(self.transaction_number)
        self.reference = self.reference.strip()
        self.notes = self.notes.strip()
        self.reversal_reason = self.reversal_reason.strip()
        if not self.transaction_number:
            raise ValidationError(
                {"transaction_number": "وارد کردن شماره تراکنش انبار الزامی است."}
            )
        if self.quantity <= Decimal(0):
            raise ValidationError({"quantity": "مقدار باید مثبت باشد."})
        if self.occurred_at and timezone.is_naive(self.occurred_at):
            raise ValidationError(
                {"occurred_at": "زمان تراکنش باید دارای منطقه زمانی باشد."}
            )
        validate_related_organizations(
            self,
            source_warehouse=(
                self.source_warehouse if self.source_warehouse_id else None
            ),
            destination_warehouse=(
                self.destination_warehouse if self.destination_warehouse_id else None
            ),
            material=self.material if self.material_id else None,
            unit_of_measure=(self.unit_of_measure if self.unit_of_measure_id else None),
            project=self.project if self.project_id else None,
            goods_receipt_item=(
                self.goods_receipt_item if self.goods_receipt_item_id else None
            ),
            reversal_of=self.reversal_of if self.reversal_of_id else None,
        )
        self._validate_material_and_project()
        self._validate_movement_shape()
        self._validate_lifecycle()

    def _validate_material_and_project(self) -> None:
        if self.material_id and self.unit_of_measure_id:
            if self.material.unit_of_measure_id != self.unit_of_measure_id:
                raise ValidationError(
                    {
                        "unit_of_measure": "واحد باید با واحد اصلی مصالح مطابقت داشته باشد."
                    }
                )
            if (
                not self.material.is_active
                or self.material.archived_at is not None
                or not self.unit_of_measure.is_active
                or self.unit_of_measure.archived_at is not None
            ):
                raise ValidationError("مصالح و واحد اندازه‌گیری باید فعال باشند.")
        if (
            self.project_id
            and self.project.deleted_at is not None
            and self.transaction_type != StockTransactionType.REVERSAL
            and self.status != StockTransactionStatus.REVERSED
        ):
            raise ValidationError({"project": "پروژه باید فعال باشد."})
        for field_name, warehouse in (
            ("source_warehouse", self.source_warehouse),
            ("destination_warehouse", self.destination_warehouse),
        ):
            if warehouse is None:
                continue
            if not warehouse.is_active or warehouse.archived_at is not None:
                raise ValidationError({field_name: "انبار باید فعال باشد."})
            if warehouse.project_id and warehouse.project_id != self.project_id:
                raise ValidationError(
                    {
                        "project": (
                            "پروژه تراکنش باید با پروژه هر انبار اختصاصی مطابقت داشته "
                            "باشد."
                        )
                    }
                )

    def _validate_movement_shape(self) -> None:
        has_source = self.source_warehouse_id is not None
        has_destination = self.destination_warehouse_id is not None
        if has_source and has_destination:
            if self.source_warehouse_id == self.destination_warehouse_id:
                raise ValidationError("انبار مبدأ و مقصد باید متفاوت باشند.")
            if self.transaction_type not in {
                StockTransactionType.TRANSFER,
                StockTransactionType.REVERSAL,
            }:
                raise ValidationError(
                    "فقط انتقال و برگشت تراکنش می‌توانند دو انبار داشته باشند."
                )
        elif has_destination:
            if self.transaction_type not in {
                StockTransactionType.RECEIPT,
                StockTransactionType.ADJUSTMENT_IN,
                StockTransactionType.REVERSAL,
            }:
                raise ValidationError("این نوع تراکنش به انبار مبدأ نیاز دارد.")
        elif has_source:
            if self.transaction_type not in {
                StockTransactionType.ISSUE,
                StockTransactionType.ADJUSTMENT_OUT,
                StockTransactionType.REVERSAL,
            }:
                raise ValidationError("این نوع تراکنش به انبار مقصد نیاز دارد.")
        else:
            raise ValidationError("تراکنش انبار باید حداقل یک انبار داشته باشد.")

        if self.transaction_type == StockTransactionType.ISSUE and not self.project_id:
            raise ValidationError(
                {"project": "برای حواله خروج، انتخاب پروژه الزامی است."}
            )
        if self.transaction_type == StockTransactionType.RECEIPT:
            if not self.goods_receipt_item_id:
                raise ValidationError(
                    {"goods_receipt_item": "ورود از خرید به ردیف رسید کالا نیاز دارد."}
                )
            item = self.goods_receipt_item
            if item.material_id != self.material_id:
                raise ValidationError(
                    {"material": "مصالح باید با ردیف رسید کالا مطابقت داشته باشد."}
                )
            if item.unit_of_measure_id != self.unit_of_measure_id:
                raise ValidationError(
                    {
                        "unit_of_measure": "واحد باید با ردیف رسید کالا مطابقت داشته باشد."
                    }
                )
            if item.goods_receipt.project_id != self.project_id:
                raise ValidationError(
                    {"project": "پروژه باید با رسید کالا مطابقت داشته باشد."}
                )
            if self.quantity != item.quantity:
                raise ValidationError(
                    {"quantity": "مقدار ورود باید با مقدار ردیف رسید کالا برابر باشد."}
                )
        elif self.goods_receipt_item_id:
            raise ValidationError(
                {
                    "goods_receipt_item": "فقط تراکنش ورود از خرید می‌تواند به رسید کالا ارجاع دهد."
                }
            )

        if self.transaction_type == StockTransactionType.REVERSAL:
            if not self.reversal_of_id:
                raise ValidationError(
                    {"reversal_of": "برای برگشت تراکنش، انتخاب تراکنش اصلی الزامی است."}
                )
        elif self.reversal_of_id:
            raise ValidationError(
                {"reversal_of": "فقط تراکنش برگشت می‌تواند یک گردش دیگر را برگرداند."}
            )

        if self.reversal_of_id:
            original = self.reversal_of
            if original.transaction_type == StockTransactionType.REVERSAL:
                raise ValidationError("تراکنش برگشتی را نمی‌توان دوباره برگشت داد.")
            if original.status not in {
                StockTransactionStatus.POSTED,
                StockTransactionStatus.REVERSED,
            }:
                raise ValidationError("فقط تراکنش ثبت‌شده قابل برگشت است.")
            if any(
                (
                    self.source_warehouse_id != original.destination_warehouse_id,
                    self.destination_warehouse_id != original.source_warehouse_id,
                    self.material_id != original.material_id,
                    self.unit_of_measure_id != original.unit_of_measure_id,
                    self.project_id != original.project_id,
                    self.quantity != original.quantity,
                )
            ):
                raise ValidationError(
                    "تراکنش برگشت باید نسخه برابر و معکوس تراکنش اصلی باشد."
                )

    def _validate_lifecycle(self) -> None:
        if self.status == StockTransactionStatus.DRAFT:
            if any(
                (
                    self.posted_at,
                    self.posted_by_id,
                    self.reversed_at,
                    self.reversed_by_id,
                    self.reversal_reason,
                )
            ):
                raise ValidationError(
                    "تراکنش پیش‌نویس نمی‌تواند اطلاعات ثبت یا برگشت داشته باشد."
                )
        elif self.status == StockTransactionStatus.POSTED:
            if not self.posted_at:
                raise ValidationError({"posted_at": "زمان ثبت الزامی است."})
            if self.reversed_at or self.reversed_by_id or self.reversal_reason:
                raise ValidationError(
                    "تراکنش ثبت‌شده نمی‌تواند اطلاعات برگشت داشته باشد."
                )
        elif self.status == StockTransactionStatus.REVERSED and (
            not self.posted_at or not self.reversed_at or not self.reversal_reason
        ):
            raise ValidationError("تراکنش برگشت‌خورده به اطلاعات ثبت و برگشت نیاز دارد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self._state.adding:
            if (
                self.transaction_type == StockTransactionType.REVERSAL
                and self.status != StockTransactionStatus.POSTED
            ):
                raise ValidationError("تراکنش برگشت باید در وضعیت ثبت‌شده ایجاد شود.")
            if (
                self.transaction_type != StockTransactionType.REVERSAL
                and self.status != StockTransactionStatus.DRAFT
            ):
                raise ValidationError(
                    "تراکنش جدید انبار باید با وضعیت پیش‌نویس آغاز شود."
                )
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "organization_id",
                "transaction_number",
                "transaction_type",
                "source_warehouse_id",
                "destination_warehouse_id",
                "material_id",
                "unit_of_measure_id",
                "project_id",
                "goods_receipt_item_id",
                "reversal_of_id",
                "quantity",
                "occurred_at",
                "reference",
                "notes",
            )
            if previous.status != StockTransactionStatus.DRAFT and any(
                getattr(previous, field) != getattr(self, field)
                for field in immutable_fields
            ):
                raise ValidationError("جزئیات تراکنش ثبت‌شده انبار قابل تغییر نیست.")
            if previous.status == StockTransactionStatus.REVERSED:
                raise ValidationError("تراکنش برگشت‌خورده انبار قابل تغییر نیست.")
            if previous.status == StockTransactionStatus.DRAFT and self.status not in {
                StockTransactionStatus.DRAFT,
                StockTransactionStatus.POSTED,
            }:
                raise ValidationError("تراکنش پیش‌نویس انبار فقط می‌تواند ثبت شود.")
            if (
                previous.status == StockTransactionStatus.POSTED
                and self.status != StockTransactionStatus.REVERSED
            ):
                raise ValidationError("تراکنش ثبت‌شده انبار فقط می‌تواند برگشت داده شود.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != StockTransactionStatus.DRAFT:
            raise ValidationError("تراکنش ثبت‌شده انبار قابل حذف نیست.")
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return self.transaction_number
