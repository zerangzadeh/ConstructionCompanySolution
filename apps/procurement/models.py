from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class PurchaseRequestStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class GoodsReceiptStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    VOID = "void", "Void"


class PurchaseRequest(UUIDModel, TimeStampedModel):
    """A tenant-owned internal request for project materials."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="purchase_requests",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="purchase_requests"
    )
    request_number = models.CharField(max_length=80)
    title = models.CharField(max_length=255)
    required_by = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PurchaseRequestStatus.choices,
        default=PurchaseRequestStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_requests_approved",
    )
    decision_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_requests_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_requests_updated",
    )

    class Meta:
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
            raise ValidationError("Request number and title are required.")
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
                raise ValidationError("Finalized purchase requests are immutable.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.request_number} - {self.title}"


class PurchaseRequestItem(UUIDModel, TimeStampedModel):
    """A material quantity requested within an editable request."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="purchase_request_items",
    )
    purchase_request = models.ForeignKey(
        PurchaseRequest, on_delete=models.CASCADE, related_name="items"
    )
    material = models.ForeignKey(
        "materials.Material",
        on_delete=models.PROTECT,
        related_name="purchase_request_items",
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="purchase_request_items",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_request_items_created",
    )

    class Meta:
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
                        "unit_of_measure": "Unit must match the material's canonical unit."
                    }
                )
            if (
                not self.material.is_active
                or self.material.archived_at
                or not self.unit_of_measure.is_active
                or self.unit_of_measure.archived_at
            ):
                raise ValidationError("Material and unit of measure must be active.")
        if self.quantity <= Decimal(0):
            raise ValidationError({"quantity": "Quantity must be positive."})
        self.description = self.description.strip()
        if not self.description:
            raise ValidationError({"description": "Description is required."})

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
                "Only draft purchase requests can have items changed."
            )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class PurchaseOrder(UUIDModel, TimeStampedModel):
    """A tenant-owned supplier commitment for one project."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="purchase_orders",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="purchase_orders"
    )
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    supplier = models.ForeignKey(
        "parties.BusinessParty",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    order_number = models.CharField(max_length=80)
    order_date = models.DateField()
    expected_delivery_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PurchaseOrderStatus.choices,
        default=PurchaseOrderStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders_issued",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders_updated",
    )

    class Meta:
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
            raise ValidationError({"order_number": "Order number is required."})
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
                {
                    "purchase_request": "Purchase request must belong to the order project."
                }
            )
        if (
            self.expected_delivery_date
            and self.expected_delivery_date < self.order_date
        ):
            raise ValidationError(
                {"expected_delivery_date": "Delivery date cannot precede order date."}
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
                raise ValidationError("Issued purchase order terms are immutable.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.order_number


class PurchaseOrderItem(UUIDModel, TimeStampedModel):
    """A priced line within an editable purchase order."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="purchase_order_items",
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="items"
    )
    purchase_request_item = models.ForeignKey(
        PurchaseRequestItem,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_order_items",
    )
    material = models.ForeignKey(
        "materials.Material",
        on_delete=models.PROTECT,
        related_name="purchase_order_items",
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="purchase_order_items",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
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
                        "unit_of_measure": "Unit must match the material's canonical unit."
                    }
                )
            if (
                not self.material.is_active
                or self.material.archived_at
                or not self.unit_of_measure.is_active
                or self.unit_of_measure.archived_at
            ):
                raise ValidationError("Material and unit of measure must be active.")
        if self.purchase_request_item_id:
            request = self.purchase_order.purchase_request
            if (
                request is None
                or self.purchase_request_item.purchase_request_id != request.pk
            ):
                raise ValidationError(
                    {
                        "purchase_request_item": "Request item must belong to the linked request."
                    }
                )
            if self.purchase_request_item.material_id != self.material_id:
                raise ValidationError(
                    {"material": "Order material must match the request item."}
                )
        if self.quantity <= Decimal(0) or self.unit_price < Decimal(0):
            raise ValidationError(
                "Quantity must be positive and unit price non-negative."
            )
        self.description = self.description.strip()
        if not self.description:
            raise ValidationError({"description": "Description is required."})

    def save(self, *args: object, **kwargs: object) -> None:
        order_status = (
            PurchaseOrder.objects.values_list("status", flat=True).get(
                pk=self.purchase_order_id
            )
            if self.purchase_order_id
            else None
        )
        if order_status != PurchaseOrderStatus.DRAFT:
            raise ValidationError("Only draft purchase orders can have items changed.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class GoodsReceipt(UUIDModel, TimeStampedModel):
    """A receipt against an issued purchase order; no inventory movement is created."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="goods_receipts",
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="goods_receipts"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="goods_receipts"
    )
    receipt_number = models.CharField(max_length=80)
    received_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=GoodsReceiptStatus.choices,
        default=GoodsReceiptStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts_posted",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts_voided",
    )
    void_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts_updated",
    )

    class Meta:
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
            raise ValidationError({"receipt_number": "Receipt number is required."})
        if self.received_at and timezone.is_naive(self.received_at):
            raise ValidationError(
                {"received_at": "Receipt time must be timezone-aware."}
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
                {"project": "Receipt project must match the purchase order project."}
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
                raise ValidationError("Posted goods receipt details are immutable.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.receipt_number


class GoodsReceiptItem(UUIDModel, TimeStampedModel):
    """A received quantity tied exactly to one purchase-order line."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="goods_receipt_items",
    )
    goods_receipt = models.ForeignKey(
        GoodsReceipt, on_delete=models.CASCADE, related_name="items"
    )
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem, on_delete=models.PROTECT, related_name="goods_receipt_items"
    )
    material = models.ForeignKey(
        "materials.Material",
        on_delete=models.PROTECT,
        related_name="goods_receipt_items",
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="goods_receipt_items",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipt_items_created",
    )

    class Meta:
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
                        "purchase_order_item": "Order item must belong to the receipt order."
                    }
                )
            if self.purchase_order_item.material_id != self.material_id:
                raise ValidationError(
                    {"material": "Material must match the order item."}
                )
            if self.purchase_order_item.unit_of_measure_id != self.unit_of_measure_id:
                raise ValidationError(
                    {"unit_of_measure": "Unit must match the order item."}
                )
        if self.quantity <= Decimal(0):
            raise ValidationError({"quantity": "Quantity must be positive."})
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
            raise ValidationError("Only draft goods receipts can have items changed.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)
