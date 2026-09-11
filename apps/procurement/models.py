from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class PurchaseRequestStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"
    REJECTED = "rejected", "ردشده"
    CANCELLED = "cancelled", "لغوشده"


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ISSUED = "issued", "صادرشده"
    COMPLETED = "completed", "تکمیل‌شده"
    CANCELLED = "cancelled", "لغوشده"


class GoodsReceiptStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    POSTED = "posted", "ثبت‌شده"
    VOID = "void", "باطل‌شده"


class PurchaseRequest(UUIDModel, TimeStampedModel):
    """A tenant-owned internal request for project materials."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="purchase_requests",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        related_name="purchase_requests",
    )
    request_number = models.CharField("شماره درخواست خرید", max_length=80)
    title = models.CharField("عنوان درخواست", max_length=255)
    required_by = models.DateField("تاریخ موردنیاز", null=True, blank=True)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=PurchaseRequestStatus.choices,
        default=PurchaseRequestStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField("یادداشت‌ها", blank=True)
    submitted_at = models.DateTimeField("زمان ارسال", null=True, blank=True)
    approved_at = models.DateTimeField("زمان تأیید", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تأییدکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_requests_approved",
    )
    decision_reason = models.TextField("دلیل تصمیم", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_requests_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_requests_updated",
    )

    class Meta:
        verbose_name = "درخواست خرید"
        verbose_name_plural = "درخواست‌های خرید"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "request_number"],
                name="uq_pr_org_num",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "status"],
                name="pr_org_proj_status_idx",
            )
        ]
        ordering = ["-created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.request_number = canonicalize_upper_identifier(self.request_number)
        self.title = self.title.strip()
        self.notes = self.notes.strip()
        self.decision_reason = self.decision_reason.strip()
        if not self.request_number or not self.title:
            raise ValidationError("وارد کردن شماره و عنوان درخواست خرید الزامی است.")
        if self.project_id:
            validate_related_organizations(self, project=self.project)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                PurchaseRequestStatus.APPROVED,
                PurchaseRequestStatus.REJECTED,
                PurchaseRequestStatus.CANCELLED,
            } and any(
                getattr(previous, field) != getattr(self, field)
                for field in (
                    "project_id",
                    "request_number",
                    "title",
                    "required_by",
                    "notes",
                )
            ):
                raise ValidationError("درخواست خرید نهایی‌شده قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.request_number} - {self.title}"


class PurchaseRequestItem(UUIDModel, TimeStampedModel):
    """A material quantity requested within an editable request."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="purchase_request_items",
    )
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        verbose_name="درخواست خرید",
        on_delete=models.CASCADE,
        related_name="items",
    )
    material = models.ForeignKey(
        "materials.Material",
        verbose_name="مصالح",
        on_delete=models.PROTECT,
        related_name="purchase_request_items",
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        related_name="purchase_request_items",
    )
    description = models.CharField("شرح ردیف", max_length=255)
    quantity = models.DecimalField("مقدار درخواستی", max_digits=18, decimal_places=4)
    sort_order = models.PositiveIntegerField("ترتیب نمایش", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_request_items_created",
    )

    class Meta:
        verbose_name = "ردیف درخواست خرید"
        verbose_name_plural = "ردیف‌های درخواست خرید"
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="purchase_request_item_qty_gt_0",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "purchase_request"],
                name="purchase_req_item_org_req_idx",
            )
        ]
        ordering = ["sort_order", "created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            purchase_request=self.purchase_request
            if self.purchase_request_id
            else None,
            material=self.material if self.material_id else None,
            unit_of_measure=self.unit_of_measure if self.unit_of_measure_id else None,
        )
        if self.material_id and self.unit_of_measure_id:
            if self.material.unit_of_measure_id != self.unit_of_measure_id:
                raise ValidationError(
                    {
                        "unit_of_measure": "واحد باید با واحد اصلی مصالح مطابقت داشته باشد."
                    }
                )
            if (
                not self.material.is_active
                or self.material.archived_at
                or not self.unit_of_measure.is_active
                or self.unit_of_measure.archived_at
            ):
                raise ValidationError("مصالح و واحد اندازه‌گیری باید فعال باشند.")
        if self.quantity <= Decimal(0):
            raise ValidationError({"quantity": "مقدار باید مثبت باشد."})
        self.description = self.description.strip()
        if not self.description:
            raise ValidationError({"description": "وارد کردن شرح ردیف الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        request_status = (
            PurchaseRequest.objects.values_list("status", flat=True).get(
                pk=self.purchase_request_id
            )
            if self.purchase_request_id
            else None
        )
        if request_status != PurchaseRequestStatus.DRAFT:
            raise ValidationError(
                "فقط ردیف‌های درخواست خرید در وضعیت پیش‌نویس قابل تغییر هستند."
            )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class PurchaseOrder(UUIDModel, TimeStampedModel):
    """A tenant-owned supplier commitment for one project."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="purchase_orders",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        verbose_name="درخواست خرید",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    supplier = models.ForeignKey(
        "parties.BusinessParty",
        verbose_name="تأمین‌کننده",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    order_number = models.CharField("شماره سفارش خرید", max_length=80)
    order_date = models.DateField("تاریخ سفارش")
    expected_delivery_date = models.DateField(
        "تاریخ تحویل موردانتظار", null=True, blank=True
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=PurchaseOrderStatus.choices,
        default=PurchaseOrderStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField("یادداشت‌ها", blank=True)
    issued_at = models.DateTimeField("زمان صدور", null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="صادرکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders_issued",
    )
    cancelled_at = models.DateTimeField("زمان لغو", null=True, blank=True)
    cancellation_reason = models.TextField("دلیل لغو", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders_updated",
    )

    class Meta:
        verbose_name = "سفارش خرید"
        verbose_name_plural = "سفارش‌های خرید"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "order_number"],
                name="uq_po_org_num",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "status"],
                name="po_org_proj_status_idx",
            ),
            models.Index(
                fields=["organization", "supplier", "status"],
                name="po_org_supplier_idx",
            ),
        ]
        ordering = ["-order_date", "-created_at"]  # noqa: RUF012

    @property
    def total_amount(self) -> Decimal:
        total = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def clean(self) -> None:
        super().clean()
        self.order_number = canonicalize_upper_identifier(self.order_number)
        self.notes = self.notes.strip()
        self.cancellation_reason = self.cancellation_reason.strip()
        if not self.order_number:
            raise ValidationError(
                {"order_number": "وارد کردن شماره سفارش خرید الزامی است."}
            )
        relations = {
            "project": self.project if self.project_id else None,
            "supplier": self.supplier if self.supplier_id else None,
            "purchase_request": self.purchase_request
            if self.purchase_request_id
            else None,
        }
        validate_related_organizations(self, **relations)
        if (
            self.purchase_request_id
            and self.project_id
            and self.purchase_request.project_id != self.project_id
        ):
            raise ValidationError(
                {"purchase_request": "درخواست خرید باید متعلق به پروژه سفارش باشد."}
            )
        if (
            self.expected_delivery_date
            and self.expected_delivery_date < self.order_date
        ):
            raise ValidationError(
                {
                    "expected_delivery_date": "تاریخ تحویل نمی‌تواند پیش از تاریخ سفارش باشد."
                }
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status != PurchaseOrderStatus.DRAFT and any(
                getattr(previous, field) != getattr(self, field)
                for field in (
                    "project_id",
                    "purchase_request_id",
                    "supplier_id",
                    "order_number",
                    "order_date",
                    "expected_delivery_date",
                    "notes",
                )
            ):
                raise ValidationError("شرایط سفارش خرید صادرشده قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.order_number


class PurchaseOrderItem(UUIDModel, TimeStampedModel):
    """A priced line within an editable purchase order."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="purchase_order_items",
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        verbose_name="سفارش خرید",
        on_delete=models.CASCADE,
        related_name="items",
    )
    purchase_request_item = models.ForeignKey(
        PurchaseRequestItem,
        verbose_name="ردیف درخواست خرید",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_order_items",
    )
    material = models.ForeignKey(
        "materials.Material",
        verbose_name="مصالح",
        on_delete=models.PROTECT,
        related_name="purchase_order_items",
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        related_name="purchase_order_items",
    )
    description = models.CharField("شرح ردیف", max_length=255)
    quantity = models.DecimalField("مقدار سفارش", max_digits=18, decimal_places=4)
    unit_price = models.DecimalField("قیمت واحد", max_digits=18, decimal_places=2)
    sort_order = models.PositiveIntegerField("ترتیب نمایش", default=0)

    class Meta:
        verbose_name = "ردیف سفارش خرید"
        verbose_name_plural = "ردیف‌های سفارش خرید"
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="purchase_order_item_qty_gt_0"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="po_item_price_gte_0",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "purchase_order"],
                name="purchase_order_item_org_po_idx",
            )
        ]
        ordering = ["sort_order", "created_at"]  # noqa: RUF012

    @property
    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            purchase_order=self.purchase_order if self.purchase_order_id else None,
            purchase_request_item=(
                self.purchase_request_item if self.purchase_request_item_id else None
            ),
            material=self.material if self.material_id else None,
            unit_of_measure=self.unit_of_measure if self.unit_of_measure_id else None,
        )
        if self.material_id and self.unit_of_measure_id:
            if self.material.unit_of_measure_id != self.unit_of_measure_id:
                raise ValidationError(
                    {
                        "unit_of_measure": "واحد باید با واحد اصلی مصالح مطابقت داشته باشد."
                    }
                )
            if (
                not self.material.is_active
                or self.material.archived_at
                or not self.unit_of_measure.is_active
                or self.unit_of_measure.archived_at
            ):
                raise ValidationError("مصالح و واحد اندازه‌گیری باید فعال باشند.")
        if self.purchase_request_item_id:
            request = self.purchase_order.purchase_request
            if (
                request is None
                or self.purchase_request_item.purchase_request_id != request.pk
            ):
                raise ValidationError(
                    {
                        "purchase_request_item": "ردیف درخواست باید متعلق به درخواست خرید مرتبط باشد."
                    }
                )
            if self.purchase_request_item.material_id != self.material_id:
                raise ValidationError(
                    {"material": "مصالح سفارش باید با ردیف درخواست مطابقت داشته باشد."}
                )
        if self.quantity <= Decimal(0) or self.unit_price < Decimal(0):
            raise ValidationError("مقدار باید مثبت و قیمت واحد نامنفی باشد.")
        self.description = self.description.strip()
        if not self.description:
            raise ValidationError({"description": "وارد کردن شرح ردیف الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        order_status = (
            PurchaseOrder.objects.values_list("status", flat=True).get(
                pk=self.purchase_order_id
            )
            if self.purchase_order_id
            else None
        )
        if order_status != PurchaseOrderStatus.DRAFT:
            raise ValidationError(
                "فقط ردیف‌های سفارش خرید در وضعیت پیش‌نویس قابل تغییر هستند."
            )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class GoodsReceipt(UUIDModel, TimeStampedModel):
    """A receipt against an issued purchase order; no inventory movement is created."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="goods_receipts",
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        verbose_name="سفارش خرید",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    receipt_number = models.CharField("شماره رسید کالا", max_length=80)
    received_at = models.DateTimeField("زمان دریافت")
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=GoodsReceiptStatus.choices,
        default=GoodsReceiptStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField("یادداشت‌ها", blank=True)
    posted_at = models.DateTimeField("زمان ثبت", null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts_posted",
    )
    voided_at = models.DateTimeField("زمان ابطال", null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ابطال‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts_voided",
    )
    void_reason = models.TextField("دلیل ابطال", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts_updated",
    )

    class Meta:
        verbose_name = "رسید کالا"
        verbose_name_plural = "رسیدهای کالا"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "receipt_number"],
                name="uq_gr_org_num",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "purchase_order", "status"],
                name="gr_org_po_status_idx",
            )
        ]
        ordering = ["-received_at", "-created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.receipt_number = canonicalize_upper_identifier(self.receipt_number)
        self.notes = self.notes.strip()
        self.void_reason = self.void_reason.strip()
        if not self.receipt_number:
            raise ValidationError(
                {"receipt_number": "وارد کردن شماره رسید کالا الزامی است."}
            )
        if self.received_at and timezone.is_naive(self.received_at):
            raise ValidationError(
                {"received_at": "زمان دریافت باید دارای منطقه زمانی باشد."}
            )
        validate_related_organizations(
            self,
            purchase_order=self.purchase_order if self.purchase_order_id else None,
            project=self.project if self.project_id else None,
        )
        if (
            self.purchase_order_id
            and self.project_id
            and self.purchase_order.project_id != self.project_id
        ):
            raise ValidationError(
                {
                    "project": "پروژه رسید کالا باید با پروژه سفارش خرید مطابقت داشته باشد."
                }
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status != GoodsReceiptStatus.DRAFT and any(
                getattr(previous, field) != getattr(self, field)
                for field in (
                    "purchase_order_id",
                    "project_id",
                    "receipt_number",
                    "received_at",
                    "notes",
                )
            ):
                raise ValidationError("جزئیات رسید کالای ثبت‌شده قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.receipt_number


class GoodsReceiptItem(UUIDModel, TimeStampedModel):
    """A received quantity tied exactly to one purchase-order line."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="goods_receipt_items",
    )
    goods_receipt = models.ForeignKey(
        GoodsReceipt,
        verbose_name="رسید کالا",
        on_delete=models.CASCADE,
        related_name="items",
    )
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem,
        verbose_name="ردیف سفارش خرید",
        on_delete=models.PROTECT,
        related_name="goods_receipt_items",
    )
    material = models.ForeignKey(
        "materials.Material",
        verbose_name="مصالح",
        on_delete=models.PROTECT,
        related_name="goods_receipt_items",
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        related_name="goods_receipt_items",
    )
    quantity = models.DecimalField("مقدار دریافتی", max_digits=18, decimal_places=4)
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipt_items_created",
    )

    class Meta:
        verbose_name = "ردیف رسید کالا"
        verbose_name_plural = "ردیف‌های رسید کالا"
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="goods_receipt_item_qty_gt_0"
            ),
            models.UniqueConstraint(
                fields=["goods_receipt", "purchase_order_item"],
                name="uq_gr_order_item",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "goods_receipt"],
                name="goods_receipt_item_org_gr_idx",
            )
        ]
        ordering = ["created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            goods_receipt=self.goods_receipt if self.goods_receipt_id else None,
            purchase_order_item=(
                self.purchase_order_item if self.purchase_order_item_id else None
            ),
            material=self.material if self.material_id else None,
            unit_of_measure=self.unit_of_measure if self.unit_of_measure_id else None,
        )
        if self.goods_receipt_id and self.purchase_order_item_id:
            if (
                self.purchase_order_item.purchase_order_id
                != self.goods_receipt.purchase_order_id
            ):
                raise ValidationError(
                    {
                        "purchase_order_item": "ردیف سفارش باید متعلق به سفارش خرید این رسید باشد."
                    }
                )
            if self.purchase_order_item.material_id != self.material_id:
                raise ValidationError(
                    {"material": "مصالح باید با ردیف سفارش مطابقت داشته باشد."}
                )
            if self.purchase_order_item.unit_of_measure_id != self.unit_of_measure_id:
                raise ValidationError(
                    {"unit_of_measure": "واحد باید با ردیف سفارش مطابقت داشته باشد."}
                )
        if self.quantity <= Decimal(0):
            raise ValidationError({"quantity": "مقدار باید مثبت باشد."})
        self.notes = self.notes.strip()

    def save(self, *args: object, **kwargs: object) -> None:
        receipt_status = (
            GoodsReceipt.objects.values_list("status", flat=True).get(
                pk=self.goods_receipt_id
            )
            if self.goods_receipt_id
            else None
        )
        if receipt_status != GoodsReceiptStatus.DRAFT:
            raise ValidationError(
                "فقط ردیف‌های رسید کالا در وضعیت پیش‌نویس قابل تغییر هستند."
            )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)
