from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.identifiers import canonicalize_upper_identifier
from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class TreasuryAccountKind(models.TextChoices):
    BANK = "bank", "بانک"
    CASH = "cash", "صندوق"
    PETTY_CASH = "petty_cash", "تنخواه"


class TreasuryAccountStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ACTIVE = "active", "فعال"
    SUSPENDED = "suspended", "معلق"
    CLOSED = "closed", "بسته"


class TreasuryMovementKind(models.TextChoices):
    RECEIPT = "receipt", "دریافت"
    DISBURSEMENT = "disbursement", "پرداخت"
    TRANSFER = "transfer", "انتقال"
    REVERSAL = "reversal", "برگشت"


class TreasuryMovementStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"
    POSTED = "posted", "ثبت قطعی"
    REJECTED = "rejected", "ردشده"
    CANCELLED = "cancelled", "لغوشده"


class TreasuryLegDirection(models.TextChoices):
    IN = "in", "ورودی"
    OUT = "out", "خروجی"


class ChequeDirection(models.TextChoices):
    INCOMING = "incoming", "دریافتی"
    OUTGOING = "outgoing", "پرداختی"


class ChequeStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ISSUED = "issued", "صادرشده"
    RECEIVED = "received", "دریافت‌شده"
    DELIVERED = "delivered", "تحویل‌شده"
    DEPOSITED = "deposited", "واگذارشده"
    PRESENTED = "presented", "ارائه‌شده"
    CLEARED = "cleared", "وصول‌شده"
    BOUNCED = "bounced", "برگشتی"
    CANCELLED = "cancelled", "لغوشده"


class PaymentRequestKind(models.TextChoices):
    PAYMENT = "payment", "درخواست پرداخت"
    EMPLOYEE_ADVANCE = "employee_advance", "تنخواه کارمند"
    VENDOR_ADVANCE = "vendor_advance", "پیش‌پرداخت تأمین‌کننده"
    EMPLOYEE_REIMBURSEMENT = "employee_reimbursement", "بازپرداخت هزینه کارمند"


class PaymentRequestStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"
    RELEASED = "released", "پرداخت‌شده"
    REJECTED = "rejected", "ردشده"
    CANCELLED = "cancelled", "لغوشده"


class TreasuryAdvanceStatus(models.TextChoices):
    OPEN = "open", "باز"
    PARTIALLY_SETTLED = "partially_settled", "تسویه جزئی"
    SETTLED = "settled", "تسویه‌شده"
    REVERSED = "reversed", "برگشت‌شده"


class AdvanceSettlementStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"
    REJECTED = "rejected", "ردشده"
    CANCELLED = "cancelled", "لغوشده"


class StatementImportStatus(models.TextChoices):
    PREVIEWED = "previewed", "پیش‌نمایش‌شده"
    ACCEPTED = "accepted", "پذیرفته‌شده"
    CANCELLED = "cancelled", "لغوشده"


class StatementMatchStatus(models.TextChoices):
    SUGGESTED = "suggested", "پیشنهادشده"
    CONFIRMED = "confirmed", "تأییدشده"
    REJECTED = "rejected", "ردشده"
    REVERSED = "reversed", "برگشت‌شده"


class ImmutableTreasuryEvidence:
    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("شواهد خزانه‌داری تغییرناپذیر است.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("شواهد خزانه‌داری قابل حذف نیست.")


class TreasuryAccount(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="treasury_accounts",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=TreasuryAccountKind.choices)
    status = models.CharField(
        max_length=20,
        choices=TreasuryAccountStatus.choices,
        default=TreasuryAccountStatus.DRAFT,
    )
    currency = models.CharField(max_length=3, default="IRR")
    identifier_last4 = models.CharField(max_length=4, blank=True, editable=False)
    identifier_fingerprint = models.CharField(max_length=64, blank=True, editable=False)
    custodian = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="treasury_accounts_in_custody",
    )
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="treasury_accounts_created",
    )

    class Meta:
        ordering = ["code"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="treasury_account_unique_tenant_code",
            ),
            models.UniqueConstraint(
                fields=["organization", "identifier_fingerprint"],
                condition=~Q(identifier_fingerprint=""),
                name="treasury_account_unique_tenant_identifier",
            ),
            models.CheckConstraint(
                condition=Q(currency="IRR"), name="treasury_account_irr_only"
            ),
        ]

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        validate_related_organizations(self, custodian=self.custodian)
        if (
            self.kind in {TreasuryAccountKind.CASH, TreasuryAccountKind.PETTY_CASH}
            and not self.custodian_id
        ):
            raise ValidationError(
                {"custodian": "صندوق و تنخواه به متولی فعال نیاز دارند."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        if not self._state.adding:
            original = TreasuryAccount.objects.get(pk=self.pk)
            if original.status != self.status:
                raise ValidationError("تغییر وضعیت حساب فقط از خدمت چرخه عمر مجاز است.")
            immutable = (
                "organization_id",
                "code",
                "kind",
                "currency",
                "identifier_fingerprint",
            )
            if any(
                getattr(original, field) != getattr(self, field) for field in immutable
            ):
                raise ValidationError("هویت حساب خزانه‌داری قابل بازنویسی نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        if self.status != TreasuryAccountStatus.DRAFT:
            raise ValidationError("حساب فعال‌شده قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class TreasuryAccountMappingVersion(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    treasury_account = models.ForeignKey(
        TreasuryAccount, on_delete=models.PROTECT, related_name="mapping_versions"
    )
    version = models.PositiveIntegerField()
    cash_ledger_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.PROTECT,
        related_name="treasury_cash_mappings",
    )
    clearing_ledger_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.PROTECT,
        related_name="treasury_clearing_mappings",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    reason = models.TextField()
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion", on_delete=models.PROTECT
    )
    approved_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="treasury_mappings_approved",
    )

    class Meta:
        ordering = ["treasury_account", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["treasury_account", "version"],
                name="treasury_mapping_unique_version",
            ),
            models.UniqueConstraint(
                fields=["treasury_account"],
                condition=Q(is_active=True),
                name="treasury_mapping_one_active",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gte=models.F("effective_from")),
                name="treasury_mapping_valid_interval",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("نسخه نگاشت حسابداری تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("نسخه نگاشت حسابداری قابل حذف نیست.")


class TreasuryAccountLifecycleEvent(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    account = models.ForeignKey(
        TreasuryAccount, on_delete=models.PROTECT, related_name="lifecycle_events"
    )
    from_status = models.CharField(max_length=20, choices=TreasuryAccountStatus.choices)
    to_status = models.CharField(max_length=20, choices=TreasuryAccountStatus.choices)
    reason = models.TextField()
    actor = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    requested_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="treasury_account_transitions_requested",
    )
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion", on_delete=models.PROTECT
    )


class TreasuryMovement(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="treasury_movements",
    )
    kind = models.CharField(max_length=20, choices=TreasuryMovementKind.choices)
    status = models.CharField(
        max_length=20,
        choices=TreasuryMovementStatus.choices,
        default=TreasuryMovementStatus.DRAFT,
    )
    movement_date = models.DateField()
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    currency = models.CharField(max_length=3, default="IRR")
    description = models.CharField(max_length=500)
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    version = models.PositiveIntegerField(default=1)
    occurrence_id = models.UUIDField(default=uuid.uuid4)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True
    )
    site = models.ForeignKey(
        "projects.ProjectSite", on_delete=models.PROTECT, null=True, blank=True
    )
    party = models.ForeignKey(
        "parties.BusinessParty", on_delete=models.PROTECT, null=True, blank=True
    )
    origin_request = models.OneToOneField(
        "treasury.PaymentRequest", on_delete=models.PROTECT, null=True, blank=True,
        related_name="originated_movement",
    )
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="treasury_movements_created",
    )
    submitted_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="treasury_movements_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="treasury_movements_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="treasury_movement",
    )
    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal_movement",
    )

    class Meta:
        ordering = ["-movement_date", "-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="treasury_movement_unique_idempotency",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="treasury_movement_positive_amount"
            ),
            models.CheckConstraint(
                condition=Q(currency="IRR"), name="treasury_movement_irr_only"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=TreasuryMovementStatus.DRAFT,
                        submitted_by__isnull=True,
                        approved_by__isnull=True,
                        journal__isnull=True,
                    )
                    | Q(
                        status=TreasuryMovementStatus.SUBMITTED,
                        submitted_by__isnull=False,
                        approved_by__isnull=True,
                        journal__isnull=True,
                    )
                    | Q(
                        status=TreasuryMovementStatus.APPROVED,
                        submitted_by__isnull=False,
                        approved_by__isnull=False,
                        journal__isnull=True,
                    )
                    | Q(
                        status=TreasuryMovementStatus.POSTED,
                        submitted_by__isnull=False,
                        approved_by__isnull=False,
                        journal__isnull=False,
                    )
                    | Q(
                        status__in=[
                            TreasuryMovementStatus.REJECTED,
                            TreasuryMovementStatus.CANCELLED,
                        ],
                        journal__isnull=True,
                    )
                ),
                name="treasury_movement_state_consistent",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = TreasuryMovement.objects.get(pk=self.pk)
            immutable = (
                "organization_id",
                "kind",
                "movement_date",
                "amount",
                "currency",
                "idempotency_key",
                "payload_hash",
                "version",
                "occurrence_id",
                "project_id",
                "site_id",
                "party_id",
                "origin_request_id",
                "created_by_id",
                "reverses_id",
            )
            if any(
                getattr(original, field) != getattr(self, field) for field in immutable
            ):
                raise ValidationError(
                    "هویت و محتوای حرکت خزانه‌داری قابل بازنویسی نیست."
                )
            if original.status != self.status:
                raise ValidationError("تغییر وضعیت حرکت فقط از خدمت چرخه عمر مجاز است.")
        validate_related_organizations(
            self,
            project=self.project,
            site=self.site,
            party=self.party,
            origin_request=self.origin_request,
            created_by=self.created_by,
        )
        if self.site_id and (
            not self.project_id or self.site.project_id != self.project_id
        ):
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه باشد."})
        if self.origin_request_id and (
            self.kind != TreasuryMovementKind.DISBURSEMENT
            or self.origin_request.kind != PaymentRequestKind.EMPLOYEE_REIMBURSEMENT
            or self.origin_request.status != PaymentRequestStatus.APPROVED
            or self.amount != self.origin_request.amount
            or self.currency != self.origin_request.currency
            or self.project_id != self.origin_request.project_id
            or self.site_id != self.origin_request.site_id
            or self.party_id is not None
        ):
            raise ValidationError("The reimbursement movement must match its approved request.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        if self.status != TreasuryMovementStatus.DRAFT:
            raise ValidationError("حرکت ارسال‌شده قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class TreasuryMovementLeg(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    movement = models.ForeignKey(
        TreasuryMovement, on_delete=models.PROTECT, related_name="legs"
    )
    line_number = models.PositiveSmallIntegerField()
    account = models.ForeignKey(
        TreasuryAccount, on_delete=models.PROTECT, related_name="movement_legs"
    )
    direction = models.CharField(max_length=3, choices=TreasuryLegDirection.choices)
    amount = models.DecimalField(max_digits=24, decimal_places=6)

    class Meta:
        ordering = ["movement", "line_number"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["movement", "line_number"], name="treasury_leg_unique_line"
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="treasury_leg_positive_amount"
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.movement.status != TreasuryMovementStatus.DRAFT:
            raise ValidationError("ردیف حرکت پس از ارسال تغییرناپذیر است.")
        validate_related_organizations(
            self, movement=self.movement, account=self.account
        )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        if self.movement.status != TreasuryMovementStatus.DRAFT:
            raise ValidationError("ردیف حرکت پس از ارسال قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class TreasuryMovementTransition(ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    movement = models.ForeignKey(
        TreasuryMovement, on_delete=models.PROTECT, related_name="transitions"
    )
    from_status = models.CharField(
        max_length=20, choices=TreasuryMovementStatus.choices
    )
    to_status = models.CharField(max_length=20, choices=TreasuryMovementStatus.choices)
    reason = models.TextField()
    actor = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )


class TreasuryPostingEvidence(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    movement = models.OneToOneField(
        TreasuryMovement, on_delete=models.PROTECT, related_name="posting_evidence"
    )
    journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        related_name="treasury_posting_evidence",
    )
    source_version = models.PositiveIntegerField()
    occurrence_id = models.UUIDField()
    source_line_ids = models.JSONField()
    mapping_version_ids = models.JSONField()
    posting_rule_code = models.CharField(max_length=100)
    posting_rule_version = models.PositiveIntegerField()
    precision_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="treasury_precision_evidence",
    )
    rounding_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="treasury_rounding_evidence",
    )
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="treasury_approval_evidence",
    )
    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod", on_delete=models.PROTECT
    )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("شواهد ثبت خزانه‌داری تغییرناپذیر است.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("شواهد ثبت خزانه‌داری قابل حذف نیست.")


class ChequeInstrument(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="cheque_instruments",
    )
    direction = models.CharField(max_length=10, choices=ChequeDirection.choices)
    status = models.CharField(
        max_length=20, choices=ChequeStatus.choices, default=ChequeStatus.DRAFT
    )
    controlled_account = models.ForeignKey(
        TreasuryAccount, on_delete=models.PROTECT, related_name="cheques"
    )
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    due_date = models.DateField()
    party = models.ForeignKey(
        "parties.BusinessParty", on_delete=models.PROTECT, null=True, blank=True
    )
    serial_last4 = models.CharField(max_length=4, editable=False)
    serial_fingerprint = models.CharField(max_length=64, editable=False)
    custodian = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="cheques_created",
    )
    cleared_movement = models.OneToOneField(
        TreasuryMovement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cleared_cheque",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "serial_fingerprint"],
                name="treasury_cheque_unique_serial",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="treasury_cheque_positive_amount"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=[ChequeStatus.CLEARED, ChequeStatus.BOUNCED],
                        cleared_movement__isnull=False,
                    )
                    | Q(
                        status__in=[
                            ChequeStatus.DRAFT,
                            ChequeStatus.ISSUED,
                            ChequeStatus.RECEIVED,
                            ChequeStatus.DELIVERED,
                            ChequeStatus.DEPOSITED,
                            ChequeStatus.PRESENTED,
                            ChequeStatus.CANCELLED,
                        ],
                        cleared_movement__isnull=True,
                    )
                ),
                name="treasury_cheque_cash_effect_consistent",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = ChequeInstrument.objects.get(pk=self.pk)
            immutable = (
                "organization_id",
                "direction",
                "controlled_account_id",
                "amount",
                "due_date",
                "party_id",
                "serial_fingerprint",
                "created_by_id",
            )
            if any(
                getattr(original, field) != getattr(self, field) for field in immutable
            ):
                raise ValidationError("هویت چک قابل بازنویسی نیست.")
            if original.status != self.status:
                raise ValidationError("تغییر وضعیت چک فقط از خدمت چرخه عمر مجاز است.")
        validate_related_organizations(
            self,
            controlled_account=self.controlled_account,
            party=self.party,
            custodian=self.custodian,
            created_by=self.created_by,
        )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        if self.status != ChequeStatus.DRAFT:
            raise ValidationError("چک واردشده به چرخه قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class ChequeTransition(ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    cheque = models.ForeignKey(
        ChequeInstrument, on_delete=models.PROTECT, related_name="transitions"
    )
    from_status = models.CharField(max_length=20, choices=ChequeStatus.choices)
    to_status = models.CharField(max_length=20, choices=ChequeStatus.choices)
    reason = models.TextField()
    actor = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )


class TreasuryGLReconciliationRun(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    cutoff_date = models.DateField()
    movement_count = models.PositiveIntegerField()
    journal_count = models.PositiveIntegerField()
    treasury_in = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    treasury_out = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    journal_debit = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    journal_credit = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    exceptions = models.JSONField(default=list)
    evidence_hash = models.CharField(max_length=64)
    run_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("اجرای تطبیق نگهداری‌شده تغییرناپذیر است.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("اجرای تطبیق نگهداری‌شده قابل حذف نیست.")


class TreasuryGLReconciliationSlice(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    run = models.ForeignKey(
        TreasuryGLReconciliationRun, on_delete=models.PROTECT, related_name="slices"
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    cutoff_date = models.DateField()
    currency = models.CharField(max_length=3)
    treasury_account = models.ForeignKey(TreasuryAccount, on_delete=models.PROTECT)
    treasury_in = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    treasury_out = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    journal_debit = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    journal_credit = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
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
                fields=["run", "currency", "treasury_account"],
                name="treasury_gl_slice_one_grain_per_run",
            ),
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "cutoff_date",
                    "currency",
                    "treasury_account",
                    "grain_revision",
                ],
                name="treasury_gl_slice_unique_grain_revision",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=[
                    "organization",
                    "cutoff_date",
                    "currency",
                    "treasury_account",
                    "grain_revision",
                ],
                name="treasury_gl_slice_current_idx",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run,
            treasury_account=self.treasury_account,
            supersedes=self.supersedes,
        )
        if (
            self.run.organization_id != self.organization_id
            or self.run.cutoff_date != self.cutoff_date
            or self.grain_revision < 1
        ):
            raise ValidationError("برش تطبیق خزانه با اجرای والد سازگار نیست.")
        if self.supersedes_id and (
            self.supersedes.organization_id != self.organization_id
            or self.supersedes.cutoff_date != self.cutoff_date
            or self.supersedes.currency != self.currency
            or self.supersedes.treasury_account_id != self.treasury_account_id
            or self.supersedes.grain_revision + 1 != self.grain_revision
        ):
            raise ValidationError("جانشین برش تطبیق خزانه معتبر نیست.")


class TreasuryGLReconciliationLegEvidence(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    slice = models.ForeignKey(
        TreasuryGLReconciliationSlice,
        on_delete=models.PROTECT,
        related_name="leg_evidence",
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    movement = models.ForeignKey(TreasuryMovement, on_delete=models.PROTECT)
    leg = models.ForeignKey(TreasuryMovementLeg, on_delete=models.PROTECT)
    movement_version = models.PositiveIntegerField()
    occurrence_id = models.UUIDField()
    currency = models.CharField(max_length=3)
    direction = models.CharField(max_length=3, choices=TreasuryLegDirection.choices)
    amount = models.DecimalField(max_digits=24, decimal_places=6)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["slice", "leg"], name="treasury_gl_slice_unique_leg"
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, slice=self.slice, movement=self.movement, leg=self.leg
        )
        if (
            self.movement.organization_id != self.organization_id
            or self.leg.movement_id != self.movement_id
            or self.leg.account_id != self.slice.treasury_account_id
            or self.movement.currency != self.currency
        ):
            raise ValidationError("شاهد حرکت خزانه با برش سازگار نیست.")


class TreasuryGLReconciliationJournalLineEvidence(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    slice = models.ForeignKey(
        TreasuryGLReconciliationSlice,
        on_delete=models.PROTECT,
        related_name="journal_line_evidence",
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    movement = models.ForeignKey(TreasuryMovement, on_delete=models.PROTECT)
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
                name="treasury_gl_slice_unique_journal_line",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            slice=self.slice,
            movement=self.movement,
            journal=self.journal,
            journal_line=self.journal_line,
        )
        if (
            self.journal_line.journal_id != self.journal_id
            or self.movement.organization_id != self.organization_id
        ):
            raise ValidationError("شاهد خط دفترکل خزانه معتبر نیست.")


class TreasuryGLReconciliationSliceInvalidation(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    slice = models.OneToOneField(
        TreasuryGLReconciliationSlice,
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
            raise ValidationError("ابطال برش تطبیق خزانه نامعتبر است.")


class TreasuryGLReconciliationRunProvenance(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    run = models.OneToOneField(
        TreasuryGLReconciliationRun, on_delete=models.PROTECT, related_name="provenance"
    )
    classification = models.CharField(max_length=32)
    evidence_hash = models.CharField(max_length=64)

    def clean(self) -> None:
        if self.classification not in {"legacy_unverified", "prospective"}:
            raise ValidationError("طبقه‌بندی منشأ تطبیق معتبر نیست.")


class TreasuryGLReconciliationReview(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    run = models.OneToOneField(
        TreasuryGLReconciliationRun, on_delete=models.PROTECT, related_name="review"
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
        if self.reviewed_by_id == self.run.run_by_id:
            raise ValidationError("اجراکننده تطبیق نمی‌تواند همان اجرا را بررسی کند.")


class PaymentRequest(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payment_requests",
    )
    kind = models.CharField(max_length=24, choices=PaymentRequestKind.choices)
    status = models.CharField(
        max_length=20,
        choices=PaymentRequestStatus.choices,
        default=PaymentRequestStatus.DRAFT,
    )
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    currency = models.CharField(max_length=3, default="IRR")
    purpose = models.CharField(max_length=500)
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    employee = models.ForeignKey(
        "workforce.Employee", on_delete=models.PROTECT, null=True, blank=True
    )
    source_expense = models.OneToOneField(
        "expenses.Expense", on_delete=models.PROTECT, null=True, blank=True,
        related_name="treasury_payment_request",
    )
    source_expense_version = models.PositiveIntegerField(null=True, blank=True)
    party = models.ForeignKey(
        "parties.BusinessParty", on_delete=models.PROTECT, null=True, blank=True
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True
    )
    site = models.ForeignKey(
        "projects.ProjectSite", on_delete=models.PROTECT, null=True, blank=True
    )
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="payment_requests_created",
    )
    submitted_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment_requests_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment_requests_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    released_movement = models.OneToOneField(
        TreasuryMovement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment_request_release",
    )

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="treasury_request_unique_idempotency",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="treasury_request_positive_amount"
            ),
            models.CheckConstraint(
                condition=Q(currency="IRR"), name="treasury_request_irr_only"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        kind=PaymentRequestKind.EMPLOYEE_ADVANCE,
                        employee__isnull=False,
                        party__isnull=True,
                        source_expense__isnull=True,
                        source_expense_version__isnull=True,
                    )
                    | Q(
                        kind__in=[
                            PaymentRequestKind.PAYMENT,
                            PaymentRequestKind.VENDOR_ADVANCE,
                        ],
                        employee__isnull=True,
                        party__isnull=False,
                        source_expense__isnull=True,
                        source_expense_version__isnull=True,
                    )
                    | Q(
                        kind=PaymentRequestKind.EMPLOYEE_REIMBURSEMENT,
                        employee__isnull=False,
                        party__isnull=True,
                        source_expense__isnull=False,
                        source_expense_version__isnull=False,
                    )
                ),
                name="treasury_request_beneficiary_consistent",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = PaymentRequest.objects.get(pk=self.pk)
            immutable = (
                "organization_id",
                "kind",
                "amount",
                "currency",
                "purpose",
                "idempotency_key",
                "payload_hash",
                "employee_id",
                "source_expense_id",
                "source_expense_version",
                "party_id",
                "project_id",
                "site_id",
                "created_by_id",
            )
            if any(
                getattr(original, field) != getattr(self, field) for field in immutable
            ):
                raise ValidationError(
                    "محتوای درخواست پرداخت پس از ثبت قابل بازنویسی نیست."
                )
            if (
                original.status != self.status
                or original.released_movement_id != self.released_movement_id
            ):
                raise ValidationError("تغییر چرخه درخواست فقط از خدمت مجاز است.")
        validate_related_organizations(
            self,
            employee=self.employee,
            source_expense=self.source_expense,
            party=self.party,
            project=self.project,
            site=self.site,
            created_by=self.created_by,
        )
        if self.site_id and (
            not self.project_id or self.site.project_id != self.project_id
        ):
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه باشد."})
        if self.kind == PaymentRequestKind.EMPLOYEE_REIMBURSEMENT:
            source = self.source_expense
            if (
                source is None
                or source.status != "approved"
                or source.classification != "direct"
                or source.settlement_status != "unsettled"
                or source.reimbursement_employee_id != self.employee_id
                or source.source_version != self.source_expense_version
                or source.amount != self.amount
                or source.project_id != self.project_id
                or self.currency != "IRR"
                or self.party_id is not None
            ):
                raise ValidationError("Reimbursement request must match an approved direct Expense version.")
        elif self.source_expense_id or self.source_expense_version is not None:
            raise ValidationError("Only reimbursement requests may link an Expense.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        if self.status != PaymentRequestStatus.DRAFT:
            raise ValidationError("درخواست ارسال‌شده قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class PaymentRequestTransition(ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    request = models.ForeignKey(
        PaymentRequest, on_delete=models.PROTECT, related_name="transitions"
    )
    from_status = models.CharField(max_length=20, choices=PaymentRequestStatus.choices)
    to_status = models.CharField(max_length=20, choices=PaymentRequestStatus.choices)
    reason = models.TextField()
    actor = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    requested_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="payment_request_decisions_requested",
    )
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )


class TreasuryAdvance(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    request = models.OneToOneField(
        PaymentRequest, on_delete=models.PROTECT, related_name="advance"
    )
    issue_movement = models.OneToOneField(
        TreasuryMovement, on_delete=models.PROTECT, related_name="issued_advance"
    )
    status = models.CharField(
        max_length=24,
        choices=TreasuryAdvanceStatus.choices,
        default=TreasuryAdvanceStatus.OPEN,
    )
    opened_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="advances_opened",
    )
    reversal_movement = models.OneToOneField(
        TreasuryMovement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_advance_issue",
    )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = TreasuryAdvance.objects.get(pk=self.pk)
            if (
                original.status != self.status
                or original.reversal_movement_id != self.reversal_movement_id
            ):
                raise ValidationError("تغییر وضعیت تنخواه فقط از خدمت مجاز است.")
            if (
                original.request_id != self.request_id
                or original.issue_movement_id != self.issue_movement_id
            ):
                raise ValidationError("هویت تنخواه تغییرناپذیر است.")
        validate_related_organizations(
            self,
            request=self.request,
            issue_movement=self.issue_movement,
            opened_by=self.opened_by,
        )
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("شواهد تنخواه قابل حذف نیست.")


class AdvanceSettlement(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    advance = models.ForeignKey(
        TreasuryAdvance, on_delete=models.PROTECT, related_name="settlements"
    )
    receipt_movement = models.ForeignKey(
        TreasuryMovement, on_delete=models.PROTECT, related_name="advance_settlements"
    )
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    status = models.CharField(
        max_length=20,
        choices=AdvanceSettlementStatus.choices,
        default=AdvanceSettlementStatus.DRAFT,
    )
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="advance_settlements_created",
    )
    submitted_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="advance_settlements_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="advance_settlements_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="treasury_settlement_unique_idempotency",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="treasury_settlement_positive_amount"
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = AdvanceSettlement.objects.get(pk=self.pk)
            immutable = (
                "organization_id",
                "advance_id",
                "receipt_movement_id",
                "amount",
                "idempotency_key",
                "payload_hash",
                "created_by_id",
            )
            if any(
                getattr(original, field) != getattr(self, field) for field in immutable
            ):
                raise ValidationError("محتوای تسویه تغییرناپذیر است.")
            if original.status != self.status:
                raise ValidationError("تغییر وضعیت تسویه فقط از خدمت مجاز است.")
        validate_related_organizations(
            self,
            advance=self.advance,
            receipt_movement=self.receipt_movement,
            created_by=self.created_by,
        )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        if self.status != AdvanceSettlementStatus.DRAFT:
            raise ValidationError("تسویه ارسال‌شده قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class AdvanceSettlementTransition(ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    settlement = models.ForeignKey(
        AdvanceSettlement, on_delete=models.PROTECT, related_name="transitions"
    )
    from_status = models.CharField(
        max_length=20, choices=AdvanceSettlementStatus.choices
    )
    to_status = models.CharField(max_length=20, choices=AdvanceSettlementStatus.choices)
    reason = models.TextField()
    actor = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    requested_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="advance_settlement_decisions_requested",
    )
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )


class AdvanceSettlementReversal(ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    settlement = models.OneToOneField(
        AdvanceSettlement, on_delete=models.PROTECT, related_name="reversal"
    )
    reversal_movement = models.OneToOneField(
        TreasuryMovement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="advance_settlement_reversal",
    )
    actor = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    requested_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="advance_settlement_reversals_requested",
    )
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion", on_delete=models.PROTECT
    )
    reason = models.TextField()


class TreasuryAdvanceReconciliationRun(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    cutoff_date = models.DateField()
    idempotency_key = models.CharField(max_length=120)
    evidence_hash = models.CharField(max_length=64)
    advance_count = models.PositiveIntegerField()
    issued_total = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    settled_total = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    outstanding_total = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    exceptions = models.JSONField(default=list)
    run_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="treasury_advance_recon_unique_key",
            )
        ]


class BankStatementImport(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    account = models.ForeignKey(
        TreasuryAccount, on_delete=models.PROTECT, related_name="statement_imports"
    )
    status = models.CharField(
        max_length=20,
        choices=StatementImportStatus.choices,
        default=StatementImportStatus.PREVIEWED,
    )
    provider_code = models.CharField(max_length=80)
    format_code = models.CharField(max_length=80)
    period_start = models.DateField()
    period_end = models.DateField()
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64)
    file_size = models.PositiveBigIntegerField()
    max_file_bytes = models.PositiveBigIntegerField()
    max_rows = models.PositiveIntegerField()
    row_count = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="statement_imports_created",
    )
    accepted_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="statement_imports_accepted",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    acceptance_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="treasury_stmt_import_unique_key",
            ),
            models.UniqueConstraint(
                fields=["organization", "account", "file_hash"],
                name="treasury_stmt_import_unique_file",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="treasury_stmt_import_valid_period",
            ),
            models.CheckConstraint(
                condition=Q(file_size__lte=models.F("max_file_bytes")),
                name="treasury_stmt_import_file_bounded",
            ),
            models.CheckConstraint(
                condition=Q(row_count__lte=models.F("max_rows")),
                name="treasury_stmt_import_rows_bounded",
            ),
            models.CheckConstraint(
                condition=Q(file_size__gt=0)
                & Q(max_file_bytes__gt=0)
                & Q(max_rows__gt=0)
                & Q(row_count__gt=0),
                name="treasury_stmt_import_positive_bounds",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=StatementImportStatus.ACCEPTED,
                        accepted_by__isnull=False,
                        accepted_at__isnull=False,
                        approval_policy_version__isnull=False,
                    )
                    & ~Q(acceptance_hash="")
                )
                | Q(
                    status__in=[
                        StatementImportStatus.PREVIEWED,
                        StatementImportStatus.CANCELLED,
                    ],
                    accepted_by__isnull=True,
                    accepted_at__isnull=True,
                    approval_policy_version__isnull=True,
                    acceptance_hash="",
                ),
                name="treasury_stmt_import_state_consistent",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("ورودی صورتحساب فقط از خدمت چرخه عمر تغییر می‌کند.")
        validate_related_organizations(
            self, account=self.account, created_by=self.created_by
        )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("شواهد ورود صورتحساب قابل حذف نیست.")


class BankStatementLine(ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    statement_import = models.ForeignKey(
        BankStatementImport, on_delete=models.PROTECT, related_name="lines"
    )
    account = models.ForeignKey(TreasuryAccount, on_delete=models.PROTECT)
    row_number = models.PositiveIntegerField()
    provider_code = models.CharField(max_length=80)
    provider_row_id = models.CharField(max_length=160, blank=True)
    transaction_date = models.DateField()
    value_date = models.DateField(null=True, blank=True)
    direction = models.CharField(max_length=3, choices=TreasuryLegDirection.choices)
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    currency = models.CharField(max_length=3, default="IRR")
    reference = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=500, blank=True)
    raw_evidence = models.JSONField(default=dict)
    evidence_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["statement_import", "row_number"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["statement_import", "row_number"],
                name="treasury_stmt_line_unique_number",
            ),
            models.UniqueConstraint(
                fields=["organization", "account", "evidence_hash"],
                name="treasury_stmt_line_unique_evidence",
            ),
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "account",
                    "provider_code",
                    "provider_row_id",
                ],
                condition=~Q(provider_row_id=""),
                name="treasury_stmt_line_unique_provider_id",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="treasury_stmt_line_positive_amount"
            ),
            models.CheckConstraint(
                condition=Q(currency="IRR"), name="treasury_stmt_line_irr_only"
            ),
        ]


class StatementMatchProposal(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    statement_line = models.ForeignKey(
        BankStatementLine, on_delete=models.PROTECT, related_name="match_proposals"
    )
    movement = models.ForeignKey(
        TreasuryMovement, on_delete=models.PROTECT, related_name="statement_matches"
    )
    movement_leg = models.ForeignKey(TreasuryMovementLeg, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20,
        choices=StatementMatchStatus.choices,
        default=StatementMatchStatus.SUGGESTED,
    )
    deterministic = models.BooleanField(default=False)
    basis = models.CharField(max_length=80)
    generation_key = models.CharField(max_length=120)
    evidence_hash = models.CharField(max_length=64)
    proposed_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="statement_matches_proposed",
    )
    decided_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="statement_matches_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["statement_line", "movement", "generation_key"],
                name="treasury_stmt_match_unique_generation",
            ),
            models.CheckConstraint(
                condition=Q(
                    status=StatementMatchStatus.SUGGESTED,
                    decided_by__isnull=True,
                    decided_at__isnull=True,
                    decision_reason="",
                    approval_policy_version__isnull=True,
                )
                | Q(
                    status__in=[
                        StatementMatchStatus.CONFIRMED,
                        StatementMatchStatus.REJECTED,
                        StatementMatchStatus.REVERSED,
                    ],
                    decided_by__isnull=False,
                    decided_at__isnull=False,
                ),
                name="treasury_stmt_match_state_consistent",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("پیشنهاد تطبیق فقط از خدمت چرخه عمر تغییر می‌کند.")
        validate_related_organizations(
            self,
            statement_line=self.statement_line,
            movement=self.movement,
            movement_leg=self.movement_leg,
            proposed_by=self.proposed_by,
        )
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("شواهد پیشنهاد تطبیق قابل حذف نیست.")


class TreasuryMovementClearing(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    proposal = models.OneToOneField(
        StatementMatchProposal, on_delete=models.PROTECT, related_name="clearing"
    )
    statement_line = models.ForeignKey(
        BankStatementLine, on_delete=models.PROTECT, related_name="clearings"
    )
    movement = models.ForeignKey(
        TreasuryMovement, on_delete=models.PROTECT, related_name="bank_clearings"
    )
    active = models.BooleanField(default=True)
    cleared_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    approval_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion", on_delete=models.PROTECT
    )
    evidence_hash = models.CharField(max_length=64)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["statement_line"],
                condition=Q(active=True),
                name="treasury_stmt_line_one_clearing",
            ),
            models.UniqueConstraint(
                fields=["movement"],
                condition=Q(active=True),
                name="treasury_movement_one_clearing",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("رفع اثر تسویه فقط از خدمت برگشت مجاز است.")
        validate_related_organizations(
            self,
            proposal=self.proposal,
            statement_line=self.statement_line,
            movement=self.movement,
            cleared_by=self.cleared_by,
        )
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("شواهد تسویه بانکی قابل حذف نیست.")


class TreasuryMovementClearingReversal(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    clearing = models.OneToOneField(
        TreasuryMovementClearing, on_delete=models.PROTECT, related_name="reversal"
    )
    reason = models.TextField()
    reversed_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    evidence_hash = models.CharField(max_length=64)


class BankReconciliationRun(ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    statement_import = models.ForeignKey(
        BankStatementImport, on_delete=models.PROTECT, related_name="reconciliations"
    )
    account = models.ForeignKey(TreasuryAccount, on_delete=models.PROTECT)
    as_of_date = models.DateField()
    idempotency_key = models.CharField(max_length=120)
    evidence_hash = models.CharField(max_length=64)
    statement_in = models.DecimalField(max_digits=24, decimal_places=6)
    statement_out = models.DecimalField(max_digits=24, decimal_places=6)
    cleared_book_in = models.DecimalField(max_digits=24, decimal_places=6)
    cleared_book_out = models.DecimalField(max_digits=24, decimal_places=6)
    unmatched_line_ids = models.JSONField(default=list)
    uncleared_movement_ids = models.JSONField(default=list)
    exceptions = models.JSONField(default=list)
    run_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    grain_revision = models.PositiveIntegerField(null=True, blank=True)
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
                fields=["organization", "idempotency_key"],
                name="treasury_bank_recon_unique_key",
            ),
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "account",
                    "statement_import",
                    "as_of_date",
                    "grain_revision",
                ],
                condition=Q(grain_revision__isnull=False),
                name="treasury_bank_unique_grain_revision",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=[
                    "organization",
                    "account",
                    "statement_import",
                    "as_of_date",
                    "grain_revision",
                ],
                name="treasury_bank_current_idx",
            ),
        ]


class BankReconciliationRunInvalidation(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    run = models.OneToOneField(
        BankReconciliationRun, on_delete=models.PROTECT, related_name="invalidation"
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
            self, run=self.run, invalidated_by=self.invalidated_by
        )
        if self.run.organization_id != self.organization_id or not self.reason.strip():
            raise ValidationError("ابطال اجرای تطبیق بانکی نامعتبر است.")


class BankReconciliationRunProvenance(
    ImmutableTreasuryEvidence, UUIDModel, CreatedAtModel
):
    run = models.OneToOneField(
        BankReconciliationRun, on_delete=models.PROTECT, related_name="provenance"
    )
    classification = models.CharField(max_length=32)
    evidence_hash = models.CharField(max_length=64)

    def clean(self) -> None:
        if self.classification not in {"legacy_unverified", "prospective"}:
            raise ValidationError("طبقه‌بندی منشأ تطبیق بانکی معتبر نیست.")
