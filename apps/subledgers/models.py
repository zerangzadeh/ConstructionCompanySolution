from __future__ import annotations

from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class ObligationDirection(models.TextChoices):
    RECEIVABLE = "receivable", "دریافتنی"
    PAYABLE = "payable", "پرداختنی"


class WriteOffDecisionKind(models.TextChoices):
    REJECTED = "rejected", "ردشده"
    APPROVED = "approved", "تأییدشده"


class SupplierInvoiceStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"
    REJECTED = "rejected", "ردشده"


class SupplierInvoiceLineKind(models.TextChoices):
    GOODS = "goods", "کالا"
    SERVICE = "service", "خدمت"


class InvoiceMatchStatus(models.TextChoices):
    MATCHED = "matched", "تطبیق کامل"
    WITHIN_TOLERANCE = "within_tolerance", "در محدوده رواداری"
    BLOCKED = "blocked", "مسدود"
    INCOMPLETE = "incomplete", "ناقص"


class MatchDiscrepancyCode(models.TextChoices):
    MISSING_ACCEPTANCE = "missing_acceptance", "پذیرش کافی نیست"
    QUANTITY_VARIANCE = "quantity_variance", "مغایرت مقدار"
    UNIT_PRICE_VARIANCE = "unit_price_variance", "مغایرت قیمت واحد"
    CUMULATIVE_OVERBILLING = "cumulative_overbilling", "صورتحساب تجمعی بیش از پوشش"
    SOURCE_VERSION_MISMATCH = "source_version_mismatch", "نسخه منبع ناهم‌خوان"
    UNSUPPORTED_CHARGES = "unsupported_charges", "سیاست مالیات یا هزینه موجود نیست"


class ImmutableSubledgerEvidence:
    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("شواهد زیر‌دفتر تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("شواهد زیر‌دفتر قابل حذف نیست.")


class SupplierInvoice(UUIDModel, CreatedAtModel):
    """AP/Finance-owned stable supplier-invoice identity."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    supplier = models.ForeignKey(
        "parties.BusinessParty",
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="supplier_invoices"
    )
    invoice_number = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="supplier_invoices_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "supplier", "invoice_number"],
                name="uq_supplier_invoice_identity",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            supplier=self.supplier if self.supplier_id else None,
            project=self.project if self.project_id else None,
        )
        self.invoice_number = self.invoice_number.strip().upper()
        if not self.invoice_number:
            raise ValidationError("شماره صورتحساب تأمین‌کننده الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("هویت صورتحساب تأمین‌کننده تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("صورتحساب تأمین‌کننده حذف‌پذیر نیست.")


class SupplierInvoiceVersion(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    invoice = models.ForeignKey(
        SupplierInvoice, on_delete=models.PROTECT, related_name="versions"
    )
    version_number = models.PositiveIntegerField()
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_by",
    )
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="IRR")
    status = models.CharField(
        max_length=16,
        choices=SupplierInvoiceStatus.choices,
        default=SupplierInvoiceStatus.DRAFT,
    )
    source_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=128)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="supplier_invoice_versions_prepared",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supplier_invoice_versions_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["invoice", "version_number"],
                name="uq_supplier_invoice_version",
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="uq_supplier_invoice_version_idem",
            ),
            models.CheckConstraint(
                condition=Q(currency="IRR"), name="supplier_invoice_irr_only"
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            invoice=self.invoice if self.invoice_id else None,
            supersedes=self.supersedes if self.supersedes_id else None,
        )
        if self.version_number < 1 or self.currency != "IRR":
            raise ValidationError("نسخه صورتحساب نامعتبر است یا ارز پشتیبانی نمی‌شود.")
        if self.due_date and self.due_date < self.invoice_date:
            raise ValidationError("سررسید نمی‌تواند پیش از تاریخ صورتحساب باشد.")
        if self.version_number > 1 and (
            not self.supersedes_id
            or self.supersedes.invoice_id != self.invoice_id
            or self.supersedes.version_number + 1 != self.version_number
            or self.supersedes.status != SupplierInvoiceStatus.APPROVED
        ):
            raise ValidationError(
                "اصلاح صورتحساب باید نسخه تأییدشده قبلی را جانشین کند."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable = (
                "organization_id",
                "invoice_id",
                "version_number",
                "supersedes_id",
                "invoice_date",
                "due_date",
                "currency",
                "source_hash",
                "idempotency_key",
                "prepared_by_id",
            )
            if any(getattr(previous, f) != getattr(self, f) for f in immutable):
                raise ValidationError("محتوای نسخه صورتحساب تغییرپذیر نیست.")
            allowed = {
                SupplierInvoiceStatus.DRAFT: {SupplierInvoiceStatus.SUBMITTED},
                SupplierInvoiceStatus.SUBMITTED: {
                    SupplierInvoiceStatus.APPROVED,
                    SupplierInvoiceStatus.REJECTED,
                },
            }
            if previous.status != self.status and self.status not in allowed.get(
                previous.status, set()
            ):
                raise ValidationError("گذار وضعیت صورتحساب نامعتبر است.")
            if previous.status in {
                SupplierInvoiceStatus.APPROVED,
                SupplierInvoiceStatus.REJECTED,
            }:
                raise ValidationError("نسخه تعیین‌تکلیف‌شده صورتحساب تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("نسخه صورتحساب حذف‌پذیر نیست.")


class SupplierInvoiceLine(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    invoice_version = models.ForeignKey(
        SupplierInvoiceVersion, on_delete=models.PROTECT, related_name="lines"
    )
    line_number = models.PositiveIntegerField()
    kind = models.CharField(max_length=16, choices=SupplierInvoiceLineKind.choices)
    purchase_order_version_line = models.ForeignKey(
        "procurement.PurchaseOrderVersionLine",
        on_delete=models.PROTECT,
        related_name="supplier_invoice_lines",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    freight_amount = models.DecimalField(max_digits=24, decimal_places=2, default=0)
    other_charge_amount = models.DecimalField(
        max_digits=24, decimal_places=2, default=0
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["invoice_version", "line_number"],
                name="uq_supplier_invoice_line_number",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="supplier_invoice_line_qty_positive"
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="supplier_invoice_line_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(tax_amount__gte=0)
                & Q(freight_amount__gte=0)
                & Q(other_charge_amount__gte=0),
                name="supplier_invoice_charges_nonnegative",
            ),
        ]

    @property
    def net_amount(self):
        return self.quantity * self.unit_price

    @property
    def gross_amount(self):
        return (
            self.net_amount
            + self.tax_amount
            + self.freight_amount
            + self.other_charge_amount
        )

    def clean(self) -> None:
        validate_related_organizations(
            self,
            invoice_version=self.invoice_version if self.invoice_version_id else None,
            purchase_order_version_line=self.purchase_order_version_line
            if self.purchase_order_version_line_id
            else None,
        )
        if self.purchase_order_version_line_id:
            order = self.purchase_order_version_line.version.purchase_order
            invoice = self.invoice_version.invoice
            if (
                order.supplier_id != invoice.supplier_id
                or order.project_id != invoice.project_id
            ):
                raise ValidationError(
                    "ردیف صورتحساب باید با تأمین‌کننده و پروژه سفارش یکسان باشد."
                )
        if not self.description.strip():
            raise ValidationError("شرح ردیف صورتحساب الزامی است.")


class MatchTolerancePolicy(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    version_number = models.PositiveIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    quantity_tolerance_bps = models.PositiveIntegerField()
    unit_price_tolerance_bps = models.PositiveIntegerField()
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="match_tolerance_policies_prepared",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="match_tolerance_policies_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    reason = models.CharField(max_length=500)
    payload_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "version_number"],
                name="uq_match_tolerance_policy_version",
            ),
            models.CheckConstraint(
                condition=Q(quantity_tolerance_bps__lte=10000),
                name="match_qty_tolerance_bps_valid",
            ),
            models.CheckConstraint(
                condition=Q(unit_price_tolerance_bps__lte=10000),
                name="match_price_tolerance_bps_valid",
            ),
        ]

    def clean(self) -> None:
        if self.is_approved and (
            not self.approved_by_id
            or not self.approved_at
            or self.prepared_by_id == self.approved_by_id
        ):
            raise ValidationError("سیاست رواداری نیازمند تأییدکننده مستقل است.")
        if not self.is_approved and (self.approved_by_id or self.approved_at):
            raise ValidationError(
                "سیاست آماده‌سازی‌شده هنوز نباید شاهد تأیید داشته باشد."
            )
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError("پایان اثر سیاست پیش از آغاز آن نیست.")
        if not self.reason.strip():
            raise ValidationError("دلیل سیاست رواداری الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable = (
                "organization_id",
                "version_number",
                "effective_from",
                "effective_to",
                "quantity_tolerance_bps",
                "unit_price_tolerance_bps",
                "prepared_by_id",
                "reason",
                "payload_hash",
            )
            if any(getattr(previous, f) != getattr(self, f) for f in immutable):
                raise ValidationError("محتوای سیاست رواداری تغییرپذیر نیست.")
            if previous.is_approved or not self.is_approved:
                raise ValidationError("سیاست رواداری فقط یک‌بار قابل تأیید است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("سیاست رواداری حذف‌پذیر نیست.")


class SupplierInvoiceMatch(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    invoice_version = models.ForeignKey(
        SupplierInvoiceVersion, on_delete=models.PROTECT, related_name="matches"
    )
    tolerance_policy = models.ForeignKey(
        MatchTolerancePolicy, on_delete=models.PROTECT, related_name="matches"
    )
    version_number = models.PositiveIntegerField()
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_by",
    )
    status = models.CharField(max_length=24, choices=InvoiceMatchStatus.choices)
    source_fingerprint = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=128)
    matched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="supplier_invoice_matches_run",
    )
    matched_at = models.DateTimeField()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["invoice_version", "version_number"],
                name="uq_supplier_invoice_match_version",
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="uq_supplier_invoice_match_idem",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            invoice_version=self.invoice_version if self.invoice_version_id else None,
            tolerance_policy=self.tolerance_policy
            if self.tolerance_policy_id
            else None,
            supersedes=self.supersedes if self.supersedes_id else None,
        )
        if (
            self.invoice_version_id
            and self.invoice_version.status != SupplierInvoiceStatus.APPROVED
        ):
            raise ValidationError("فقط نسخه تأییدشده صورتحساب قابل تطبیق است.")
        if self.version_number > 1 and (
            not self.supersedes_id
            or self.supersedes.invoice_version_id != self.invoice_version_id
            or self.supersedes.version_number + 1 != self.version_number
        ):
            raise ValidationError("زنجیره نسخه تطبیق نامعتبر است.")


class SupplierInvoiceMatchLine(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    match = models.ForeignKey(
        SupplierInvoiceMatch, on_delete=models.PROTECT, related_name="lines"
    )
    invoice_line = models.ForeignKey(
        SupplierInvoiceLine, on_delete=models.PROTECT, related_name="match_lines"
    )
    ordered_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    accepted_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    previously_invoiced_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    invoiced_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    ordered_unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    invoiced_unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    quantity_variance_bps = models.DecimalField(max_digits=18, decimal_places=6)
    unit_price_variance_bps = models.DecimalField(max_digits=18, decimal_places=6)
    status = models.CharField(max_length=24, choices=InvoiceMatchStatus.choices)
    calculation_lineage = models.JSONField()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["match", "invoice_line"],
                name="uq_supplier_invoice_match_line",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            match=self.match if self.match_id else None,
            invoice_line=self.invoice_line if self.invoice_line_id else None,
        )
        if (
            self.invoice_line_id
            and self.invoice_line.invoice_version_id != self.match.invoice_version_id
        ):
            raise ValidationError("ردیف تطبیق باید متعلق به نسخه صورتحساب باشد.")


class MatchDiscrepancy(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    match_line = models.ForeignKey(
        SupplierInvoiceMatchLine, on_delete=models.PROTECT, related_name="discrepancies"
    )
    code = models.CharField(max_length=40, choices=MatchDiscrepancyCode.choices)
    blocking = models.BooleanField(default=True)
    evidence = models.JSONField()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["match_line", "code"], name="uq_match_line_discrepancy"
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, match_line=self.match_line if self.match_line_id else None
        )


class Obligation(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="obligations",
    )
    direction = models.CharField(max_length=16, choices=ObligationDirection.choices)
    source_kind = models.CharField(max_length=80)
    source_uuid = models.UUIDField()
    source_version = models.PositiveIntegerField()
    source_line_key = models.CharField(max_length=120, blank=True)
    source_status = models.CharField(max_length=80)
    source_hash = models.CharField(max_length=64)
    source_snapshot = models.JSONField()
    party = models.ForeignKey(
        "parties.BusinessParty", on_delete=models.PROTECT, null=True, blank=True
    )
    party_name_snapshot = models.CharField(max_length=255)
    party_tax_identifier_snapshot = models.CharField(max_length=100, blank=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.PROTECT, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="IRR")
    original_amount = models.DecimalField(max_digits=24, decimal_places=6)
    recognized_on = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    recognized_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="subledger_obligations_recognized",
    )
    recognition_journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_recognition",
    )
    control_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_control_obligations",
    )
    control_account_mapping = models.ForeignKey(
        "accounting.ControlAccountMappingVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pinned_obligations",
    )

    class Meta:
        ordering = ["recognized_on", "created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "source_kind",
                    "source_uuid",
                    "source_version",
                    "source_line_key",
                    "direction",
                ],
                name="subledger_obligation_unique_source",
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_obligation_unique_idempotency",
            ),
            models.CheckConstraint(
                condition=Q(original_amount__gt=0),
                name="subledger_obligation_positive_amount",
            ),
            models.CheckConstraint(
                condition=Q(currency="IRR"), name="subledger_obligation_irr_only"
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            party=self.party,
            project=self.project,
            contract=self.contract,
            recognized_by=self.recognized_by,
            recognition_journal=self.recognition_journal,
            control_account=self.control_account,
            control_account_mapping=self.control_account_mapping,
        )
        if (
            self.contract_id
            and self.project_id
            and self.contract.project_id != self.project_id
        ):
            raise ValidationError("قرارداد و پروژه تعهد باید هم‌راستا باشند.")
        if not self.party_name_snapshot.strip():
            raise ValidationError({"party_name_snapshot": "تصویر نام طرف الزامی است."})
        if self.original_amount <= 0:
            raise ValidationError({"original_amount": "مبلغ تعهد باید مثبت باشد."})
        if bool(self.control_account_id) != bool(self.control_account_mapping_id):
            raise ValidationError("حساب کنترل و نسخه نگاشت باید هم‌زمان ثبت شوند.")
        if self.control_account_mapping_id and (
            self.control_account_mapping.control_account_id != self.control_account_id
            or self.control_account_mapping.source_kind != self.source_kind
            or self.control_account_mapping.direction != self.direction
        ):
            raise ValidationError("شواهد نگاشت حساب کنترل با تعهد سازگار نیست.")

    @property
    def source_reversal_evidence(self):
        if self.source_kind == "payroll.liability.v1":
            return PayrollAPReversal.objects.filter(obligation=self).first()
        return self.source_reversals.first()

    @property
    def outstanding_amount(self):
        reversal = self.source_reversal_evidence
        if reversal is not None:
            from apps.organizations.services import get_organization_settings

            settings = get_organization_settings(organization=self.organization)
            if reversal.effective_date <= timezone.localdate(
                timezone=ZoneInfo(settings.timezone)
            ):
                return self.original_amount * 0
        settled = (
            self.settlement_allocations.filter(reversal__isnull=True).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        written_off = (
            self.write_off_proposals.filter(
                decision__decision=WriteOffDecisionKind.APPROVED,
                decision__reversal__isnull=True,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        return self.original_amount - settled - written_off

    @property
    def settlement_status(self) -> str:
        if self.source_reversal_evidence is not None:
            return "reversed"
        outstanding = self.outstanding_amount
        if outstanding == self.original_amount:
            return "open"
        if outstanding == 0:
            return "settled"
        return "partial"


class APSourceReversalQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("شواهد برگشت منبع AP تغییرناپذیر است.")

    def delete(self):
        raise ValidationError("شواهد برگشت منبع AP حذف‌پذیر نیست.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("ثبت برگشت منبع AP فقط از سرویس مجاز است.")


class SupplierInvoiceAPReversal(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    """AP source reversal; never a cash reversal, write-off or GL journal."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    obligation = models.ForeignKey(
        Obligation, on_delete=models.PROTECT, related_name="source_reversals"
    )
    replacement_match = models.ForeignKey(
        SupplierInvoiceMatch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ap_corrections",
    )
    effective_date = models.DateField()
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    reversed_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    objects = APSourceReversalQuerySet.as_manager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["obligation"], name="ap_source_reversal_once"
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="ap_source_reversal_unique_key",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            obligation=self.obligation,
            replacement_match=self.replacement_match,
            reversed_by=self.reversed_by,
        )
        if (
            self.obligation.source_kind != "procurement.supplier_invoice_match.v1"
            or self.obligation.direction != ObligationDirection.PAYABLE
            or self.effective_date < self.obligation.recognized_on
            or not self.reason.strip()
        ):
            raise ValidationError("منبع یا تاریخ و دلیل برگشت AP نامعتبر است.")
        if self.replacement_match_id and (
            str(self.replacement_match.invoice_version.invoice_id)
            != self.obligation.source_snapshot.get("invoice_id")
            or self.replacement_match_id == self.obligation.source_uuid
        ):
            raise ValidationError("اصلاح AP باید منبع جانشین همان صورتحساب باشد.")


class SettlementAllocation(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    obligation = models.ForeignKey(
        Obligation, on_delete=models.PROTECT, related_name="settlement_allocations"
    )
    treasury_movement = models.ForeignKey(
        "treasury.TreasuryMovement",
        on_delete=models.PROTECT,
        related_name="subledger_allocations",
    )
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    effective_date = models.DateField()
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    settlement_journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_settlement",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_allocation_unique_idempotency",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="subledger_allocation_positive_amount"
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            obligation=self.obligation,
            treasury_movement=self.treasury_movement,
            created_by=self.created_by,
            settlement_journal=self.settlement_journal,
        )
        if self.amount <= 0:
            raise ValidationError({"amount": "مبلغ تخصیص باید مثبت باشد."})
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل تخصیص الزامی است."})


class SettlementReversal(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    allocation = models.OneToOneField(
        SettlementAllocation, on_delete=models.PROTECT, related_name="reversal"
    )
    effective_date = models.DateField()
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    reversed_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    reversal_journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_settlement_reversal",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_allocation_reversal_unique_idempotency",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            allocation=self.allocation,
            reversed_by=self.reversed_by,
            reversal_journal=self.reversal_journal,
        )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل برگشت الزامی است."})


class WriteOffProposal(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    obligation = models.ForeignKey(
        Obligation, on_delete=models.PROTECT, related_name="write_off_proposals"
    )
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    effective_date = models.DateField()
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    proposed_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_writeoff_unique_idempotency",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="subledger_writeoff_positive_amount"
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, obligation=self.obligation, proposed_by=self.proposed_by
        )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل پیشنهاد سوخت الزامی است."})


class WriteOffDecision(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    proposal = models.OneToOneField(
        WriteOffProposal, on_delete=models.PROTECT, related_name="decision"
    )
    decision = models.CharField(max_length=16, choices=WriteOffDecisionKind.choices)
    reason = models.TextField()
    decided_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_write_off",
    )

    def clean(self) -> None:
        validate_related_organizations(
            self,
            proposal=self.proposal,
            decided_by=self.decided_by,
            journal=self.journal,
        )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل تصمیم سوخت الزامی است."})
        if self.decision == WriteOffDecisionKind.APPROVED:
            raise ValidationError(
                "اختیار سوخت هنوز تصویب نشده است؛ تصمیم P3-S27-Q03 لازم است."
            )


class WriteOffReversal(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    decision = models.OneToOneField(
        WriteOffDecision, on_delete=models.PROTECT, related_name="reversal"
    )
    effective_date = models.DateField()
    reason = models.TextField()
    reversed_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_write_off_reversal",
    )

    def clean(self) -> None:
        validate_related_organizations(
            self,
            decision=self.decision,
            reversed_by=self.reversed_by,
            journal=self.journal,
        )
        raise ValidationError(
            "اختیار برگشت سوخت هنوز تصویب نشده است؛ تصمیم P3-S27-Q03 لازم است."
        )


class AgingRun(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    direction = models.CharField(max_length=16, choices=ObligationDirection.choices)
    as_of_date = models.DateField()
    obligation_count = models.PositiveIntegerField()
    original_total = models.DecimalField(max_digits=30, decimal_places=6)
    settled_total = models.DecimalField(max_digits=30, decimal_places=6)
    written_off_total = models.DecimalField(max_digits=30, decimal_places=6)
    outstanding_total = models.DecimalField(max_digits=30, decimal_places=6)
    item_snapshots = models.JSONField(blank=True)
    evidence_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_aging_unique_idempotency",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(self, created_by=self.created_by)


class SubledgerReconciliationRun(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    direction = models.CharField(max_length=16, choices=ObligationDirection.choices)
    as_of_date = models.DateField()
    subledger_outstanding_total = models.DecimalField(max_digits=30, decimal_places=6)
    linked_gl_total = models.DecimalField(max_digits=30, decimal_places=6)
    difference = models.DecimalField(max_digits=30, decimal_places=6)
    exception_snapshots = models.JSONField(blank=True)
    obligation_ids = models.JSONField(blank=True)
    journal_ids = models.JSONField(blank=True)
    evidence_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_recon_unique_idempotency",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(self, created_by=self.created_by)


class SubledgerReconciliationAccountSlice(
    ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel
):
    run = models.ForeignKey(
        SubledgerReconciliationRun,
        on_delete=models.PROTECT,
        related_name="account_slices",
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    direction = models.CharField(max_length=16, choices=ObligationDirection.choices)
    as_of_date = models.DateField()
    control_account = models.ForeignKey("accounting.Account", on_delete=models.PROTECT)
    subledger_outstanding_total = models.DecimalField(max_digits=30, decimal_places=6)
    linked_gl_total = models.DecimalField(max_digits=30, decimal_places=6)
    difference = models.DecimalField(max_digits=30, decimal_places=6)
    evidence_hash = models.CharField(max_length=64)
    grain_revision = models.PositiveIntegerField()
    supersedes = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_by",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["run", "control_account"],
                name="subledger_slice_one_account_per_run",
            ),
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "direction",
                    "as_of_date",
                    "control_account",
                    "grain_revision",
                ],
                name="subledger_slice_unique_grain_revision",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=[
                    "organization",
                    "direction",
                    "as_of_date",
                    "control_account",
                    "grain_revision",
                ],
                name="subledger_slice_current_idx",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run,
            control_account=self.control_account,
            supersedes=self.supersedes,
        )
        if (
            self.run.organization_id != self.organization_id
            or self.run.direction != self.direction
            or self.run.as_of_date != self.as_of_date
            or self.grain_revision < 1
        ):
            raise ValidationError("شواهد برش تطبیق با اجرای والد سازگار نیست.")
        if self.difference != self.subledger_outstanding_total - self.linked_gl_total:
            raise ValidationError("اختلاف برش تطبیق باید از جمع‌های ثبت‌شده محاسبه شود.")
        if self.supersedes_id and (
            self.supersedes.organization_id != self.organization_id
            or self.supersedes.direction != self.direction
            or self.supersedes.as_of_date != self.as_of_date
            or self.supersedes.control_account_id != self.control_account_id
            or self.supersedes.grain_revision + 1 != self.grain_revision
        ):
            raise ValidationError("جانشین برش تطبیق معتبر نیست.")


class SubledgerReconciliationObligationEvidence(
    ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel
):
    slice = models.ForeignKey(
        SubledgerReconciliationAccountSlice,
        on_delete=models.PROTECT,
        related_name="obligation_evidence",
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    obligation = models.ForeignKey(Obligation, on_delete=models.PROTECT)
    source_kind = models.CharField(max_length=80)
    source_uuid = models.UUIDField()
    source_version = models.PositiveIntegerField()
    source_line_key = models.CharField(max_length=120, blank=True)
    source_hash = models.CharField(max_length=64)
    outstanding_amount = models.DecimalField(max_digits=24, decimal_places=6)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["slice", "obligation"], name="subledger_slice_unique_obligation"
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, slice=self.slice, obligation=self.obligation
        )
        if self.obligation.organization_id != self.organization_id:
            raise ValidationError("شاهد تعهد متعلق به Tenant برش نیست.")


class SubledgerReconciliationJournalLineEvidence(
    ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel
):
    slice = models.ForeignKey(
        SubledgerReconciliationAccountSlice,
        on_delete=models.PROTECT,
        related_name="journal_line_evidence",
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    obligation = models.ForeignKey(Obligation, on_delete=models.PROTECT)
    journal = models.ForeignKey("accounting.JournalEntry", on_delete=models.PROTECT)
    journal_line = models.ForeignKey("accounting.JournalLine", on_delete=models.PROTECT)
    journal_source_uuid = models.UUIDField()
    journal_source_version = models.PositiveIntegerField()
    debit = models.DecimalField(max_digits=24, decimal_places=6)
    credit = models.DecimalField(max_digits=24, decimal_places=6)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["slice", "journal_line"],
                name="subledger_slice_unique_journal_line",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            slice=self.slice,
            obligation=self.obligation,
            journal=self.journal,
            journal_line=self.journal_line,
        )
        if (
            self.obligation.organization_id != self.organization_id
            or self.journal_line.journal_id != self.journal_id
            or self.journal_line.account_id != self.slice.control_account_id
        ):
            raise ValidationError("شاهد خط دفترکل با برش تطبیق سازگار نیست.")


class SubledgerReconciliationSliceInvalidation(
    ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel
):
    slice = models.OneToOneField(
        SubledgerReconciliationAccountSlice,
        on_delete=models.PROTECT,
        related_name="invalidation",
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    reason = models.TextField()
    evidence_hash = models.CharField(max_length=64)
    invalidated_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    def clean(self) -> None:
        validate_related_organizations(
            self, slice=self.slice, invalidated_by=self.invalidated_by
        )
        if (
            self.slice.organization_id != self.organization_id
            or not self.reason.strip()
        ):
            raise ValidationError("ابطال برش تطبیق نامعتبر است.")


class SubledgerReconciliationRunProvenance(
    ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel
):
    LEGACY_UNVERIFIED = "legacy_unverified"
    PROSPECTIVE = "prospective"
    run = models.OneToOneField(
        SubledgerReconciliationRun, on_delete=models.PROTECT, related_name="provenance"
    )
    classification = models.CharField(max_length=32)
    evidence_hash = models.CharField(max_length=64)

    def clean(self) -> None:
        if self.classification not in {self.LEGACY_UNVERIFIED, self.PROSPECTIVE}:
            raise ValidationError("طبقه‌بندی منشأ تطبیق معتبر نیست.")


class SubledgerReconciliationReview(
    ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel
):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    run = models.OneToOneField(
        SubledgerReconciliationRun, on_delete=models.PROTECT, related_name="review"
    )
    reason = models.TextField()
    run_evidence_hash = models.CharField(max_length=64)
    signed_evidence_hash = models.CharField(max_length=64)
    reviewed_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    def clean(self) -> None:
        validate_related_organizations(self, run=self.run, reviewed_by=self.reviewed_by)
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل بررسی تطبیق الزامی است."})
        if self.reviewed_by_id == self.run.created_by_id:
            raise ValidationError("اجراکننده تطبیق نمی‌تواند همان اجرا را بررسی کند.")


from .payroll_models import (  # noqa: F401
    PayrollAPDraft,
    PayrollAPEnrollment,
    PayrollAPEnrollmentEvent,
    PayrollAPOperation,
    PayrollAPReversal,
)
