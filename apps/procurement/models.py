import re
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.identifiers import canonicalize_upper_identifier
from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
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


class RequestForQuotationStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED_FOR_ISSUE = "submitted_for_issue", "ارسال‌شده برای صدور"
    ISSUED = "issued", "صادرشده"
    CLOSED = "closed", "بسته‌شده"
    CANCELLED = "cancelled", "لغوشده"


class RequestForQuotationInvitationStatus(models.TextChoices):
    PREPARED = "prepared", "آماده"
    SENT = "sent", "ارسال‌شده"
    ACKNOWLEDGED = "acknowledged", "تأییدشده"
    DECLINED = "declined", "ردشده"
    EXPIRED = "expired", "منقضی‌شده"
    WITHDRAWN = "withdrawn", "پس‌گرفته‌شده"
    CLOSED = "closed", "بسته‌شده"


class QuoteRevisionStatus(models.TextChoices):
    CAPTURED = "captured", "ثبت‌شده"
    SUBMITTED = "submitted", "نهایی‌شده"
    WITHDRAWN = "withdrawn", "بازپس‌گرفته‌شده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class QuoteEligibilityState(models.TextChoices):
    UNREVIEWED = "unreviewed", "بررسی‌نشده"


class QuoteSourceChannel(models.TextChoices):
    INTERNAL_EMAIL = "internal_email", "ایمیل داخلی"
    MANUAL_CAPTURE = "manual_capture", "ثبت داخلی"
    SECURE_DROP = "secure_drop", "دریافت امن"


class QuoteEvidenceType(models.TextChoices):
    SUPPLIER_ORIGINAL = "supplier_original", "نسخه اصلی تأمین‌کننده"
    SUPPLIER_ATTACHMENT = "supplier_attachment", "پیوست تأمین‌کننده"


class QuoteEvidenceSourceChannel(models.TextChoices):
    INTERNAL_CUSTODY_CAPTURE = "internal_custody_capture", "ثبت داخلی نگهداری"


class RFQCloseEntryDisposition(models.TextChoices):
    EFFECTIVE_SUBMITTED = "effective_submitted", "نسخه نهایی مؤثر"
    NO_EFFECTIVE_SUBMISSION = "no_effective_submission", "بدون نسخه نهایی مؤثر"


class QuoteOpeningRequestStatus(models.TextChoices):
    PENDING = "pending", "در انتظار تأیید مستقل"
    OPENED = "opened", "گشوده‌شده"


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


class RequestForQuotation(UUIDModel, TimeStampedModel):
    """Internal RFQ foundation. It intentionally stores no supplier offer content."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="rfqs"
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="rfqs"
    )
    purchase_request = models.ForeignKey(
        PurchaseRequest, on_delete=models.PROTECT, related_name="rfqs"
    )
    rfq_number = models.CharField(max_length=80)
    title = models.CharField(max_length=255)
    terms = models.TextField(blank=True)
    closing_at = models.DateTimeField()
    earliest_opening_at = models.DateTimeField()
    status = models.CharField(
        max_length=24,
        choices=RequestForQuotationStatus.choices,
        default=RequestForQuotationStatus.DRAFT,
        db_index=True,
    )
    current_version_number = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rfqs_issued",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rfqs_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rfqs_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "rfq_number"], name="uq_rfq_org_number"
            ),
            models.CheckConstraint(
                condition=models.Q(closing_at__lte=models.F("earliest_opening_at")),
                name="rfq_opening_not_before_close",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "status"],
                name="rfq_org_project_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.rfq_number = canonicalize_upper_identifier(self.rfq_number)
        self.title = self.title.strip()
        self.terms = self.terms.strip()
        self.cancellation_reason = self.cancellation_reason.strip()
        if not self.rfq_number or not self.title:
            raise ValidationError("شماره و عنوان استعلام الزامی است.")
        validate_related_organizations(
            self,
            project=self.project if self.project_id else None,
            purchase_request=self.purchase_request
            if self.purchase_request_id
            else None,
        )
        if (
            self.purchase_request_id
            and self.project_id
            and self.purchase_request.project_id != self.project_id
        ):
            raise ValidationError(
                {"purchase_request": "درخواست خرید باید متعلق به پروژه استعلام باشد."}
            )
        if (
            self.closing_at
            and self.earliest_opening_at
            and self.earliest_opening_at < self.closing_at
        ):
            raise ValidationError(
                {"earliest_opening_at": "زمان مجاز گشایش نمی‌تواند پیش از مهلت باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            frozen = (
                "organization_id",
                "project_id",
                "purchase_request_id",
                "rfq_number",
                "title",
                "terms",
                "closing_at",
                "earliest_opening_at",
            )
            if previous.status in {
                RequestForQuotationStatus.ISSUED,
                RequestForQuotationStatus.CLOSED,
                RequestForQuotationStatus.CANCELLED,
            } and any(getattr(previous, f) != getattr(self, f) for f in frozen):
                raise ValidationError("استعلام صادرشده فقط با الحاقیه قابل اصلاح است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class RequestForQuotationLine(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="rfq_lines"
    )
    rfq = models.ForeignKey(
        RequestForQuotation, on_delete=models.CASCADE, related_name="lines"
    )
    purchase_request_item = models.ForeignKey(
        PurchaseRequestItem, on_delete=models.PROTECT, related_name="rfq_lines"
    )
    material = models.ForeignKey(
        "materials.Material", on_delete=models.PROTECT, related_name="rfq_lines"
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure", on_delete=models.PROTECT, related_name="rfq_lines"
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["rfq", "purchase_request_item"], name="uq_rfq_request_item"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="rfq_line_quantity_gt_zero"
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(fields=["organization", "rfq"], name="rfq_line_org_rfq_idx")
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            rfq=self.rfq if self.rfq_id else None,
            purchase_request_item=self.purchase_request_item
            if self.purchase_request_item_id
            else None,
            material=self.material if self.material_id else None,
            unit_of_measure=self.unit_of_measure if self.unit_of_measure_id else None,
        )
        if (
            self.rfq_id
            and self.purchase_request_item_id
            and self.purchase_request_item.purchase_request_id
            != self.rfq.purchase_request_id
        ):
            raise ValidationError("ردیف درخواست باید متعلق به درخواست استعلام باشد.")
        if (
            self.rfq_id
            and self.purchase_request_item_id
            and self.purchase_request_item.material_id != self.material_id
        ):
            raise ValidationError("مصالح باید با ردیف درخواست مطابقت داشته باشد.")
        if (
            self.material_id
            and self.unit_of_measure_id
            and self.material.unit_of_measure_id != self.unit_of_measure_id
        ):
            raise ValidationError("واحد باید با واحد مصالح مطابقت داشته باشد.")
        self.description = self.description.strip()
        if not self.description or self.quantity <= Decimal(0):
            raise ValidationError("شرح و مقدار مثبت الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if (
            self.pk
            and not self._state.adding
            and RequestForQuotation.objects.filter(
                pk=self.rfq_id,
                status__in=[
                    RequestForQuotationStatus.ISSUED,
                    RequestForQuotationStatus.CLOSED,
                    RequestForQuotationStatus.CANCELLED,
                ],
            ).exists()
        ):
            raise ValidationError("ردیف استعلام صادرشده قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class RequestForQuotationVersion(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="rfq_versions",
    )
    rfq = models.ForeignKey(
        RequestForQuotation, on_delete=models.CASCADE, related_name="versions"
    )
    version_number = models.PositiveIntegerField()
    issued_at = models.DateTimeField()
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rfq_versions_issued",
    )
    terms = models.TextField(blank=True)
    closing_at = models.DateTimeField()
    earliest_opening_at = models.DateTimeField()
    is_addendum = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=128)
    payload_fingerprint = models.CharField(max_length=64)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["rfq", "version_number"], name="uq_rfq_version_number"
            ),
            models.UniqueConstraint(
                fields=["rfq", "idempotency_key"], name="uq_rfq_version_idempotency"
            ),
            models.CheckConstraint(
                condition=models.Q(closing_at__lte=models.F("earliest_opening_at")),
                name="rfq_version_opening_not_before_close",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, rfq=self.rfq if self.rfq_id else None)
        self.terms = self.terms.strip()
        self.idempotency_key = self.idempotency_key.strip()
        self.payload_fingerprint = self.payload_fingerprint.strip().lower()
        if self.version_number < 1 or not self.idempotency_key:
            raise ValidationError("شماره نسخه و کلید یکتای صدور الزامی است.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.payload_fingerprint):
            raise ValidationError("اثر انگشت نسخه استعلام معتبر نیست.")
        if timezone.is_naive(self.issued_at) or timezone.is_naive(self.closing_at):
            raise ValidationError("زمان‌های نسخه استعلام باید دارای منطقه زمانی باشند.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("نسخه صادرشده استعلام تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class RequestForQuotationVersionLine(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="rfq_version_lines",
    )
    rfq_version = models.ForeignKey(
        RequestForQuotationVersion, on_delete=models.CASCADE, related_name="lines"
    )
    purchase_request_item = models.ForeignKey(
        PurchaseRequestItem, on_delete=models.PROTECT, related_name="rfq_version_lines"
    )
    material = models.ForeignKey(
        "materials.Material", on_delete=models.PROTECT, related_name="rfq_version_lines"
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="rfq_version_lines",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    sort_order = models.PositiveIntegerField()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["rfq_version", "purchase_request_item"],
                name="uq_rfq_version_line_request_item",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="rfq_version_line_quantity_gt_zero",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("ردیف نسخه صادرشده استعلام تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class RequestForQuotationInvitation(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="rfq_invitations",
    )
    rfq_version = models.ForeignKey(
        RequestForQuotationVersion, on_delete=models.PROTECT, related_name="invitations"
    )
    supplier = models.ForeignKey(
        "parties.BusinessParty",
        on_delete=models.PROTECT,
        related_name="rfq_invitations",
    )
    status = models.CharField(
        max_length=16,
        choices=RequestForQuotationInvitationStatus.choices,
        default=RequestForQuotationInvitationStatus.PREPARED,
    )
    delivery_channel = models.CharField(max_length=32, blank=True)
    delivery_reference = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    state_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="rfq_invitations_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="rfq_invitations_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["rfq_version", "supplier"],
                name="uq_rfq_invitation_version_supplier",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "supplier", "status"],
                name="rfq_inv_org_supplier_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            rfq_version=self.rfq_version if self.rfq_version_id else None,
            supplier=self.supplier if self.supplier_id else None,
        )
        self.delivery_channel = self.delivery_channel.strip()
        self.delivery_reference = self.delivery_reference.strip()
        self.state_reason = self.state_reason.strip()
        if self.status == RequestForQuotationInvitationStatus.SENT and (
            not self.delivery_channel or not self.delivery_reference or not self.sent_at
        ):
            raise ValidationError(
                "ارسال دعوت‌نامه نیازمند کانال، مرجع و زمان اثبات‌شده است."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if (
                previous.rfq_version_id != self.rfq_version_id
                or previous.supplier_id != self.supplier_id
            ):
                raise ValidationError("هویت دعوت‌نامه صادرشده تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class QuoteEnvelope(UUIDModel, TimeStampedModel):
    """Supplier/RFQ identity envelope. Commercial quote content is deliberately absent."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="quote_envelopes",
    )
    rfq = models.ForeignKey(
        RequestForQuotation, on_delete=models.PROTECT, related_name="quote_envelopes"
    )
    supplier = models.ForeignKey(
        "parties.BusinessParty",
        on_delete=models.PROTECT,
        related_name="quote_envelopes",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quote_envelopes_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "rfq", "supplier"],
                name="uq_quote_envelope_org_rfq_supplier",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "rfq", "supplier"],
                name="quote_env_org_rfq_supplier_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            rfq=self.rfq if self.rfq_id else None,
            supplier=self.supplier if self.supplier_id else None,
        )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("پاکت پیشنهاد قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("پاکت پیشنهاد حذف‌پذیر نیست.")


class QuoteRevision(UUIDModel, TimeStampedModel):
    """Sealed metadata and integrity evidence, never commercial quote content."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="quote_revisions",
    )
    envelope = models.ForeignKey(
        QuoteEnvelope, on_delete=models.PROTECT, related_name="revisions"
    )
    invitation = models.ForeignKey(
        RequestForQuotationInvitation,
        on_delete=models.PROTECT,
        related_name="quote_revisions",
    )
    rfq_version = models.ForeignKey(
        RequestForQuotationVersion,
        on_delete=models.PROTECT,
        related_name="quote_revisions",
    )
    revision_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=QuoteRevisionStatus.choices,
        default=QuoteRevisionStatus.CAPTURED,
        db_index=True,
    )
    source_channel = models.CharField(max_length=32, choices=QuoteSourceChannel.choices)
    source_reference = models.CharField(max_length=128, blank=True)
    supplier_submitted_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField()
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quote_revisions_captured",
    )
    integrity_algorithm = models.CharField(max_length=16, default="sha256")
    integrity_fingerprint = models.CharField(max_length=64)
    payload_fingerprint = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=128)
    is_late = models.BooleanField(default=False)
    eligibility_state = models.CharField(
        max_length=16,
        choices=QuoteEligibilityState.choices,
        default=QuoteEligibilityState.UNREVIEWED,
    )
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_by",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["envelope", "revision_number"],
                name="uq_quote_revision_envelope_number",
            ),
            models.UniqueConstraint(
                fields=["envelope", "idempotency_key"],
                name="uq_quote_revision_envelope_idem",
            ),
            models.UniqueConstraint(
                fields=["envelope"],
                condition=models.Q(status=QuoteRevisionStatus.SUBMITTED),
                name="uq_quote_revision_one_submitted",
            ),
            models.CheckConstraint(
                condition=models.Q(revision_number__gte=1),
                name="quote_revision_number_positive",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "rfq_version", "status"],
                name="quote_rev_org_ver_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            envelope=self.envelope if self.envelope_id else None,
            invitation=self.invitation if self.invitation_id else None,
            rfq_version=self.rfq_version if self.rfq_version_id else None,
        )
        self.source_channel = self.source_channel.strip()
        self.source_reference = self.source_reference.strip()
        self.integrity_algorithm = self.integrity_algorithm.strip().lower()
        self.integrity_fingerprint = self.integrity_fingerprint.strip().lower()
        self.idempotency_key = self.idempotency_key.strip()
        if self.integrity_algorithm != "sha256" or not re.fullmatch(
            r"[0-9a-f]{64}", self.integrity_fingerprint
        ):
            raise ValidationError("اثر انگشت یکپارچگی SHA-256 معتبر الزامی است.")
        if not self.source_channel or not self.idempotency_key:
            raise ValidationError("کانال منبع و کلید یکتای ثبت الزامی است.")
        if self.source_reference and not re.fullmatch(
            r"[A-Za-z0-9._:-]{1,128}", self.source_reference
        ):
            raise ValidationError("شناسه منبع باید یک شناسه غیرمحتوایی معتبر باشد.")
        if (
            self.envelope_id
            and self.invitation_id
            and (
                self.envelope.rfq_id != self.invitation.rfq_version.rfq_id
                or self.envelope.supplier_id != self.invitation.supplier_id
            )
        ):
            raise ValidationError(
                "دعوت‌نامه باید به تأمین‌کننده و استعلام پاکت تعلق داشته باشد."
            )
        if (
            self.invitation_id
            and self.rfq_version_id
            and (self.invitation.rfq_version_id != self.rfq_version_id)
        ):
            raise ValidationError("نسخه استعلام دعوت‌نامه و پیشنهاد باید یکسان باشد.")
        if self.supersedes_id and (
            self.supersedes.envelope_id != self.envelope_id
            or self.supersedes.revision_number >= self.revision_number
        ):
            raise ValidationError("جانشین پیشنهاد باید نسخه پیشین همان پاکت باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("شواهد نسخه پیشنهاد تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("نسخه پیشنهاد حذف‌پذیر نیست.")


class ImmutableQuoteEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        raise ValidationError("شاهد محتوای پیشنهاد قابل تغییر نیست.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("شاهد محتوای پیشنهاد قابل حذف نیست.")


class ImmutableQuoteEvidenceManager(
    models.Manager.from_queryset(ImmutableQuoteEvidenceQuerySet)
):
    pass


class QuoteRevisionEvidence(UUIDModel, CreatedAtModel):
    """Immutable, version-pinned lineage for one sealed supplier evidence item."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    quote_revision = models.ForeignKey(
        QuoteRevision, on_delete=models.PROTECT, related_name="evidence_items"
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.PROTECT,
        related_name="quote_revision_evidence_items",
    )
    document_version = models.OneToOneField(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="quote_revision_evidence",
    )
    sealed_custody = models.OneToOneField(
        "documents.SealedDocumentCustody",
        on_delete=models.PROTECT,
        related_name="quote_revision_evidence",
    )
    evidence_type = models.CharField(max_length=24, choices=QuoteEvidenceType.choices)
    evidence_slot = models.CharField(max_length=80)
    canonical_sha256 = models.CharField(max_length=64)
    revision_fingerprint = models.CharField(max_length=64)
    source_channel = models.CharField(
        max_length=32,
        choices=QuoteEvidenceSourceChannel.choices,
        default=QuoteEvidenceSourceChannel.INTERNAL_CUSTODY_CAPTURE,
    )
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quote_revision_evidence_captured",
    )
    received_at = models.DateTimeField()
    custodied_at = models.DateTimeField()
    idempotency_key = models.CharField(max_length=128)
    payload_fingerprint = models.CharField(max_length=64)

    objects = ImmutableQuoteEvidenceManager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["quote_revision", "idempotency_key"],
                name="uq_quote_evidence_revision_idem",
            ),
            models.UniqueConstraint(
                fields=["quote_revision", "evidence_type", "evidence_slot"],
                name="uq_quote_evidence_revision_slot",
            ),
            models.UniqueConstraint(
                fields=["quote_revision"],
                condition=models.Q(evidence_type=QuoteEvidenceType.SUPPLIER_ORIGINAL),
                name="uq_quote_evidence_one_original",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    source_channel=QuoteEvidenceSourceChannel.INTERNAL_CUSTODY_CAPTURE
                ),
                name="quote_evidence_internal_channel",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "quote_revision", "evidence_type"],
                name="quote_ev_org_rev_type_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            quote_revision=self.quote_revision if self.quote_revision_id else None,
            document=self.document if self.document_id else None,
            document_version=self.document_version
            if self.document_version_id
            else None,
            sealed_custody=self.sealed_custody if self.sealed_custody_id else None,
        )
        self.evidence_slot = self.evidence_slot.strip()
        self.canonical_sha256 = self.canonical_sha256.strip().lower()
        self.revision_fingerprint = self.revision_fingerprint.strip().lower()
        self.idempotency_key = self.idempotency_key.strip()
        self.payload_fingerprint = self.payload_fingerprint.strip().lower()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", self.evidence_slot):
            raise ValidationError("شناسه فنی قلم شاهد معتبر نیست.")
        if not self.idempotency_key:
            raise ValidationError("کلید یکتای نگهداری شاهد الزامی است.")
        for value in (
            self.canonical_sha256,
            self.revision_fingerprint,
            self.payload_fingerprint,
        ):
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValidationError("اثر انگشت شاهد معتبر نیست.")
        if (
            self.document_version_id
            and self.document_version.document_id != self.document_id
        ):
            raise ValidationError("نسخه سند باید به سند پین‌شده تعلق داشته باشد.")
        if self.sealed_custody_id and (
            self.sealed_custody.document_version_id != self.document_version_id
            or self.sealed_custody.canonical_sha256 != self.canonical_sha256
        ):
            raise ValidationError("شاهد DMS باید همان نسخه و هش پین‌شده را نگهداری کند.")
        if (
            self.document_version_id
            and self.document_version.sha256 != self.canonical_sha256
        ):
            raise ValidationError("هش نسخه سند با هش مرجع شاهد یکسان نیست.")
        if self.quote_revision_id and (
            self.quote_revision.integrity_fingerprint != self.revision_fingerprint
        ):
            raise ValidationError("اثر انگشت نسخه پیشنهاد تغییر کرده است.")
        if self.evidence_type == QuoteEvidenceType.SUPPLIER_ORIGINAL:
            if self.evidence_slot != "primary":
                raise ValidationError("قلم اصلی باید شناسه فنی primary داشته باشد.")
        elif self.evidence_type != QuoteEvidenceType.SUPPLIER_ATTACHMENT:
            raise ValidationError("نوع شاهد پیشنهاد معتبر نیست.")
        if self.source_channel != QuoteEvidenceSourceChannel.INTERNAL_CUSTODY_CAPTURE:
            raise ValidationError("کانال منبع شاهد پیشنهاد معتبر نیست.")
        if self.received_at > self.custodied_at:
            raise ValidationError("زمان نگهداری نمی‌تواند پیش از دریافت باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("شاهد محتوای پیشنهاد قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("شاهد محتوای پیشنهاد قابل حذف نیست.")


class QuoteRevisionTransition(UUIDModel, CreatedAtModel):
    """Append-only state evidence without revealing commercial assertions."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    revision = models.ForeignKey(
        QuoteRevision, on_delete=models.PROTECT, related_name="transitions"
    )
    from_status = models.CharField(max_length=16, choices=QuoteRevisionStatus.choices)
    to_status = models.CharField(max_length=16, choices=QuoteRevisionStatus.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.CharField(max_length=128)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["revision", "idempotency_key"],
                name="uq_quote_transition_revision_idem",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "revision", "created_at"],
                name="quote_transition_org_rev_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self, revision=self.revision if self.revision_id else None
        )
        self.idempotency_key = self.idempotency_key.strip()
        if not self.idempotency_key:
            raise ValidationError("کلید یکتای انتقال الزامی است.")
        if self.from_status == self.to_status:
            raise ValidationError("وضعیت انتقال باید تغییر کند.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("شواهد انتقال پیشنهاد تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("شواهد انتقال پیشنهاد حذف‌پذیر نیست.")


class ImmutableCloseEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        raise ValidationError("شواهد نهایی بستن استعلام قابل تغییر نیست.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("شواهد نهایی بستن استعلام قابل حذف نیست.")


class ImmutableCloseEvidenceManager(
    models.Manager.from_queryset(ImmutableCloseEvidenceQuerySet)
):
    pass


class RFQCloseManifest(UUIDModel, CreatedAtModel):
    """Immutable, metadata-only custody snapshot at the authoritative deadline."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    rfq = models.OneToOneField(
        RequestForQuotation,
        on_delete=models.PROTECT,
        related_name="close_manifest",
    )
    effective_version = models.ForeignKey(
        RequestForQuotationVersion,
        on_delete=models.PROTECT,
        related_name="close_manifests",
    )
    closed_at = models.DateTimeField()
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rfq_close_manifests",
    )
    idempotency_key = models.CharField(max_length=128)
    payload_fingerprint = models.CharField(max_length=64)

    objects = ImmutableCloseEvidenceManager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["rfq", "idempotency_key"],
                name="uq_rfq_close_manifest_idem",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            rfq=self.rfq if self.rfq_id else None,
            effective_version=self.effective_version
            if self.effective_version_id
            else None,
        )
        self.idempotency_key = self.idempotency_key.strip()
        self.payload_fingerprint = self.payload_fingerprint.strip().lower()
        if not self.idempotency_key:
            raise ValidationError("کلید یکتای بستن استعلام الزامی است.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.payload_fingerprint):
            raise ValidationError("اثر انگشت مانیفست بستن معتبر نیست.")
        if (
            self.effective_version_id
            and self.rfq_id
            and self.effective_version.rfq_id != self.rfq_id
        ):
            raise ValidationError("نسخه مؤثر باید متعلق به استعلام باشد.")
        if self.closed_at and timezone.is_naive(self.closed_at):
            raise ValidationError("زمان بستن باید دارای منطقه زمانی باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("مانیفست نهایی بستن استعلام تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("مانیفست نهایی بستن استعلام حذف‌پذیر نیست.")


class RFQCloseManifestEntry(UUIDModel, CreatedAtModel):
    """One immutable invitation-level result; excluded quote evidence stays external."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    manifest = models.ForeignKey(
        RFQCloseManifest, on_delete=models.PROTECT, related_name="entries"
    )
    invitation = models.ForeignKey(
        RequestForQuotationInvitation,
        on_delete=models.PROTECT,
        related_name="close_manifest_entries",
    )
    envelope = models.ForeignKey(
        QuoteEnvelope,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="close_manifest_entries",
    )
    effective_revision = models.ForeignKey(
        QuoteRevision,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="effective_close_entries",
    )
    invitation_status = models.CharField(
        max_length=16, choices=RequestForQuotationInvitationStatus.choices
    )
    disposition = models.CharField(
        max_length=32, choices=RFQCloseEntryDisposition.choices
    )
    revision_count = models.PositiveIntegerField(default=0)
    captured_unsubmitted_count = models.PositiveIntegerField(default=0)
    withdrawn_count = models.PositiveIntegerField(default=0)
    superseded_count = models.PositiveIntegerField(default=0)
    late_count = models.PositiveIntegerField(default=0)

    objects = ImmutableCloseEvidenceManager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["manifest", "invitation"],
                name="uq_rfq_close_entry_invitation",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        disposition=RFQCloseEntryDisposition.EFFECTIVE_SUBMITTED,
                        effective_revision__isnull=False,
                    )
                    | models.Q(
                        disposition=RFQCloseEntryDisposition.NO_EFFECTIVE_SUBMISSION,
                        effective_revision__isnull=True,
                    )
                ),
                name="rfq_close_entry_effective_revision",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            manifest=self.manifest if self.manifest_id else None,
            invitation=self.invitation if self.invitation_id else None,
            envelope=self.envelope if self.envelope_id else None,
            effective_revision=self.effective_revision
            if self.effective_revision_id
            else None,
        )
        if (
            self.manifest_id
            and self.invitation_id
            and self.invitation.rfq_version_id != self.manifest.effective_version_id
        ):
            raise ValidationError("دعوت‌نامه باید متعلق به نسخه مؤثر مانیفست باشد.")
        if (
            self.envelope_id
            and self.invitation_id
            and (
                self.envelope.rfq_id != self.invitation.rfq_version.rfq_id
                or self.envelope.supplier_id != self.invitation.supplier_id
            )
        ):
            raise ValidationError("پاکت باید متعلق به دعوت‌نامه مانیفست باشد.")
        if self.effective_revision_id and (
            self.effective_revision.invitation_id != self.invitation_id
            or self.effective_revision.rfq_version_id
            != self.manifest.effective_version_id
            or self.effective_revision.envelope_id != self.envelope_id
        ):
            raise ValidationError(
                "نسخه مؤثر باید متعلق به دعوت‌نامه و پاکت مانیفست باشد."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("ردیف مانیفست نهایی تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("ردیف مانیفست نهایی حذف‌پذیر نیست.")


class ImmutableOpeningEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        raise ValidationError("شواهد گشایش پیشنهاد قابل تغییر نیست.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("شواهد گشایش پیشنهاد قابل حذف نیست.")


class ImmutableOpeningEvidenceManager(
    models.Manager.from_queryset(ImmutableOpeningEvidenceQuerySet)
):
    pass


class QuoteEvidencePackageFreeze(UUIDModel, CreatedAtModel):
    """Permanent exact-evidence boundary created by the first opening request."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    quote_revision = models.OneToOneField(
        QuoteRevision,
        on_delete=models.PROTECT,
        related_name="evidence_package_freeze",
    )
    close_manifest = models.ForeignKey(
        RFQCloseManifest,
        on_delete=models.PROTECT,
        related_name="quote_evidence_package_freezes",
    )
    frozen_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quote_evidence_packages_frozen",
    )
    frozen_at = models.DateTimeField()
    item_count = models.PositiveSmallIntegerField()
    package_fingerprint = models.CharField(max_length=64)

    objects = ImmutableOpeningEvidenceManager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=models.Q(item_count__gte=1, item_count__lte=21),
                name="quote_freeze_item_count_range",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            quote_revision=self.quote_revision if self.quote_revision_id else None,
            close_manifest=self.close_manifest if self.close_manifest_id else None,
        )
        self.package_fingerprint = self.package_fingerprint.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", self.package_fingerprint):
            raise ValidationError("اثر انگشت بسته شاهد معتبر نیست.")
        if self.item_count < 1 or self.item_count > 21:
            raise ValidationError("بسته شاهد باید شامل یک تا ۲۱ قلم باشد.")
        if (
            self.quote_revision_id
            and self.close_manifest_id
            and (
                self.quote_revision.rfq_version_id
                != self.close_manifest.effective_version_id
                or self.quote_revision.envelope.rfq_id != self.close_manifest.rfq_id
            )
        ):
            raise ValidationError(
                "بسته شاهد باید به مانیفست مؤثر همان استعلام تعلق داشته باشد."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("بسته منجمد شاهد تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("بسته منجمد شاهد حذف‌پذیر نیست.")


class QuoteEvidencePackageFreezeItem(UUIDModel, CreatedAtModel):
    """Immutable snapshot of one exact P5-S08 evidence identity."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    package = models.ForeignKey(
        QuoteEvidencePackageFreeze,
        on_delete=models.PROTECT,
        related_name="items",
    )
    evidence = models.OneToOneField(
        QuoteRevisionEvidence,
        on_delete=models.PROTECT,
        related_name="package_freeze_item",
    )
    evidence_type = models.CharField(max_length=24, choices=QuoteEvidenceType.choices)
    evidence_slot = models.CharField(max_length=80)
    document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="quote_package_freeze_items",
    )
    canonical_sha256 = models.CharField(max_length=64)

    objects = ImmutableOpeningEvidenceManager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["package", "evidence_type", "evidence_slot"],
                name="uq_quote_freeze_package_slot",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            package=self.package if self.package_id else None,
            evidence=self.evidence if self.evidence_id else None,
            document_version=self.document_version
            if self.document_version_id
            else None,
        )
        self.evidence_slot = self.evidence_slot.strip()
        self.canonical_sha256 = self.canonical_sha256.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", self.canonical_sha256):
            raise ValidationError("هش ردیف بسته منجمد معتبر نیست.")
        if self.evidence_id and (
            self.evidence.quote_revision_id != self.package.quote_revision_id
            or self.evidence.evidence_type != self.evidence_type
            or self.evidence.evidence_slot != self.evidence_slot
            or self.evidence.document_version_id != self.document_version_id
            or self.evidence.canonical_sha256 != self.canonical_sha256
        ):
            raise ValidationError("ردیف بسته منجمد با شاهد پین‌شده یکسان نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("ردیف بسته منجمد تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("ردیف بسته منجمد حذف‌پذیر نیست.")


class QuoteOpeningRequest(UUIDModel, CreatedAtModel):
    """Immutable request; absence of an opening event means it remains pending."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    quote_revision = models.ForeignKey(
        QuoteRevision, on_delete=models.PROTECT, related_name="opening_requests"
    )
    frozen_package = models.ForeignKey(
        QuoteEvidencePackageFreeze,
        on_delete=models.PROTECT,
        related_name="opening_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quote_opening_requests",
    )
    requested_at = models.DateTimeField()
    reason = models.CharField(max_length=500)
    idempotency_key = models.CharField(max_length=128)
    payload_fingerprint = models.CharField(max_length=64)

    objects = ImmutableOpeningEvidenceManager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["quote_revision", "idempotency_key"],
                name="uq_quote_open_request_revision_idem",
            )
        ]

    @property
    def status(self) -> str:
        return (
            QuoteOpeningRequestStatus.OPENED
            if hasattr(self, "opening_event")
            else QuoteOpeningRequestStatus.PENDING
        )

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            quote_revision=self.quote_revision if self.quote_revision_id else None,
            frozen_package=self.frozen_package if self.frozen_package_id else None,
        )
        self.reason = self.reason.strip()
        self.idempotency_key = self.idempotency_key.strip()
        self.payload_fingerprint = self.payload_fingerprint.strip().lower()
        if not self.reason or not self.idempotency_key:
            raise ValidationError("دلیل و کلید یکتای درخواست گشایش الزامی است.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.payload_fingerprint):
            raise ValidationError("اثر انگشت درخواست گشایش معتبر نیست.")
        if self.requested_at and timezone.is_naive(self.requested_at):
            raise ValidationError("زمان درخواست گشایش باید دارای منطقه زمانی باشد.")
        if self.frozen_package_id and (
            self.frozen_package.quote_revision_id != self.quote_revision_id
        ):
            raise ValidationError(
                "درخواست باید به بسته منجمد همان نسخه تعلق داشته باشد."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("درخواست گشایش تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("درخواست گشایش حذف‌پذیر نیست.")


class QuoteOpeningEvent(UUIDModel, CreatedAtModel):
    """Immutable revision-specific opening created by independent approval."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    quote_revision = models.OneToOneField(
        QuoteRevision, on_delete=models.PROTECT, related_name="opening_event"
    )
    opening_request = models.OneToOneField(
        QuoteOpeningRequest, on_delete=models.PROTECT, related_name="opening_event"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quote_openings_approved",
    )
    opened_at = models.DateTimeField()
    package_fingerprint = models.CharField(max_length=64)

    objects = ImmutableOpeningEvidenceManager()

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            quote_revision=self.quote_revision if self.quote_revision_id else None,
            opening_request=self.opening_request if self.opening_request_id else None,
        )
        self.package_fingerprint = self.package_fingerprint.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", self.package_fingerprint):
            raise ValidationError("اثر انگشت رویداد گشایش معتبر نیست.")
        if self.opened_at and timezone.is_naive(self.opened_at):
            raise ValidationError("زمان گشایش باید دارای منطقه زمانی باشد.")
        if self.opening_request_id and (
            self.opening_request.quote_revision_id != self.quote_revision_id
            or self.opening_request.requested_by_id == self.approved_by_id
            or self.opening_request.frozen_package.package_fingerprint
            != self.package_fingerprint
        ):
            raise ValidationError("تأیید گشایش یا تفکیک وظایف معتبر نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("رویداد گشایش تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("رویداد گشایش حذف‌پذیر نیست.")


class QuoteConfidentialAccessGrant(UUIDModel, CreatedAtModel):
    """Immutable exact-revision viewer grant; permission and scope remain required."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    quote_revision = models.ForeignKey(
        QuoteRevision,
        on_delete=models.PROTECT,
        related_name="confidential_access_grants",
    )
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="quote_confidential_access_grants",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quote_confidential_access_grants_made",
    )
    granted_at = models.DateTimeField()
    reason = models.CharField(max_length=500)
    idempotency_key = models.CharField(max_length=128)
    payload_fingerprint = models.CharField(max_length=64)

    objects = ImmutableOpeningEvidenceManager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["quote_revision", "idempotency_key"],
                name="uq_quote_access_grant_revision_idem",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            quote_revision=self.quote_revision if self.quote_revision_id else None,
            membership=self.membership if self.membership_id else None,
        )
        self.reason = self.reason.strip()
        self.idempotency_key = self.idempotency_key.strip()
        self.payload_fingerprint = self.payload_fingerprint.strip().lower()
        if self.membership_id and self.membership.user_id == self.granted_by_id:
            raise ValidationError("اعطای دسترسی محرمانه به خود مجاز نیست.")
        if not self.reason or not self.idempotency_key:
            raise ValidationError("دلیل و کلید یکتای اعطای دسترسی الزامی است.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.payload_fingerprint):
            raise ValidationError("اثر انگشت اعطای دسترسی معتبر نیست.")
        if self.granted_at and timezone.is_naive(self.granted_at):
            raise ValidationError("زمان اعطای دسترسی باید دارای منطقه زمانی باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("اعطای دسترسی محرمانه تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("اعطای دسترسی محرمانه حذف‌پذیر نیست.")


class QuoteConfidentialAccessRevocation(UUIDModel, CreatedAtModel):
    """Append-only revocation preserving the original grant and access history."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    grant = models.OneToOneField(
        QuoteConfidentialAccessGrant,
        on_delete=models.PROTECT,
        related_name="revocation",
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quote_confidential_access_revocations",
    )
    revoked_at = models.DateTimeField()
    reason = models.CharField(max_length=500)

    objects = ImmutableOpeningEvidenceManager()

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self, grant=self.grant if self.grant_id else None
        )
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValidationError("دلیل لغو دسترسی محرمانه الزامی است.")
        if self.revoked_at and timezone.is_naive(self.revoked_at):
            raise ValidationError("زمان لغو دسترسی باید دارای منطقه زمانی باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("لغو دسترسی محرمانه تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("لغو دسترسی محرمانه حذف‌پذیر نیست.")


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
