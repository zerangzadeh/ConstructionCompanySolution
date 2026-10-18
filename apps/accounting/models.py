import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields.ranges import (
    DateRangeField,
    RangeBoundary,
    RangeOperators,
)
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.identifiers import canonicalize_upper_identifier
from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class DateRangeExpression(models.Func):
    function = "DATERANGE"
    output_field = DateRangeField()


class AccountType(models.TextChoices):
    ASSET = "asset", "دارایی"
    LIABILITY = "liability", "بدهی"
    EQUITY = "equity", "حقوق مالکانه"
    INCOME = "income", "درآمد"
    EXPENSE = "expense", "هزینه"


class ControlAccountDirection(models.TextChoices):
    RECEIVABLE = "receivable", "دریافتنی"
    PAYABLE = "payable", "پرداختنی"


class FiscalYearStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ACTIVE = "active", "فعال"
    CLOSED = "closed", "بسته"


class FiscalPeriodStatus(models.TextChoices):
    OPEN = "open", "باز"
    CLOSED = "closed", "بسته"


class JournalKind(models.TextChoices):
    MANUAL = "manual", "دستی"
    OPENING = "opening", "افتتاحیه"
    REVERSAL = "reversal", "برگشت"
    REPLACEMENT = "replacement", "جایگزین"
    OPERATIONAL = "operational", "عملیاتی"


class JournalStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    PROPOSED = "proposed", "پیشنهادشده"
    POSTED = "posted", "ثبت قطعی"
    REJECTED = "rejected", "ردشده"
    CANCELLED = "cancelled", "لغوشده"


class OpeningImportStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    PROPOSED = "proposed", "آماده بررسی"
    ACCEPTED = "accepted", "پذیرفته‌شده"
    REJECTED = "rejected", "ردشده"


class ReconciliationScope(models.TextChoices):
    MANUAL_OPENING_CORRECTION = (
        "manual_opening_correction",
        "اسناد دستی، افتتاحیه و اصلاحات حسابداری",
    )


class ReconciliationTieOutType(models.TextChoices):
    MANUAL = "manual", "سند دستی"
    OPENING = "opening", "مانده افتتاحیه"
    CORRECTION = "correction", "زنجیره اصلاح"


class ReconciliationExceptionDispositionCode(models.TextChoices):
    CORRECTION_REQUIRED = "correction_required", "نیازمند اصلاح"
    EXPLAINED_VARIANCE = "explained_variance", "اختلاف توضیح‌داده‌شده"
    NOT_APPLICABLE = "not_applicable", "نامرتبط"


class FinancialStatementKind(models.TextChoices):
    TRIAL_BALANCE = "trial_balance", "تراز آزمایشی"
    BALANCE_SHEET = "balance_sheet", "ترازنامه"
    PROFIT_LOSS = "profit_loss", "صورت سود و زیان"


class PeriodControlActionType(models.TextChoices):
    CLOSE = "close", "بستن دوره"
    REOPEN = "reopen", "بازگشایی دوره"


class Account(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="ledger_accounts",
    )
    code = models.CharField("کد حساب", max_length=50)
    name = models.CharField("نام حساب", max_length=255)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    is_posting = models.BooleanField("حساب قابل ثبت", default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ledger_accounts_created",
    )

    class Meta:
        ordering = ["code"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"], name="account_unique_tenant_code"
            ),
            models.CheckConstraint(
                condition=Q(archived_at__isnull=True) | Q(is_posting=False),
                name="account_archived_not_posting",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("کد و نام حساب الزامی است.")
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "حساب نمی‌تواند والد خودش باشد."})
            validate_related_organizations(self, parent=self.parent)
            if self.parent.account_type != self.account_type:
                raise ValidationError({"parent": "نوع حساب والد باید یکسان باشد."})
            if self.parent.is_posting:
                raise ValidationError({"parent": "حساب برگ نمی‌تواند والد باشد."})
        if self.is_posting and self.pk and self.children.exists():
            raise ValidationError({"is_posting": "فقط حساب بدون فرزند قابل ثبت است."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        if (
            not self._state.adding
            and JournalLine.objects.filter(account_id=self.pk).exists()
        ):
            original = Account.objects.get(pk=self.pk)
            if (original.organization_id, original.code, original.account_type) != (
                self.organization_id,
                self.code,
                self.account_type,
            ):
                raise ValidationError("هویت حساب استفاده‌شده قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ControlAccountMappingVersion(UUIDModel, CreatedAtModel):
    """Accounting-owned AP/AR control-account policy for one effective scope."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    source_kind = models.CharField(max_length=80)
    direction = models.CharField(max_length=16, choices=ControlAccountDirection.choices)
    version = models.PositiveIntegerField()
    control_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="control_account_mappings"
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    reason = models.TextField()
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    class Meta:
        ordering = ["source_kind", "direction", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "source_kind", "direction", "version"],
                name="control_mapping_unique_version",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gte=models.F("effective_from")),
                name="control_mapping_valid_interval",
            ),
            ExclusionConstraint(
                name="control_mapping_no_scope_overlap",
                expressions=[
                    ("organization", RangeOperators.EQUAL),
                    ("source_kind", RangeOperators.EQUAL),
                    ("direction", RangeOperators.EQUAL),
                    (
                        DateRangeExpression(
                            "effective_from",
                            "effective_to",
                            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            control_account=self.control_account,
            created_by=self.created_by,
        )
        self.source_kind = self.source_kind.strip()
        self.reason = self.reason.strip()
        if not self.source_kind or not self.reason:
            raise ValidationError("نوع منبع و دلیل نگاشت الزامی است.")
        if not self.control_account.is_posting or self.control_account.archived_at:
            raise ValidationError("نگاشت فقط به حساب برگ فعال مجاز است.")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError("بازه اعتبار نگاشت نامعتبر است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("نسخه نگاشت حساب کنترل تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class FiscalYear(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="fiscal_years",
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=255)
    starts_on = models.DateField()
    ends_on = models.DateField()
    calendar_version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=FiscalYearStatus.choices, default=FiscalYearStatus.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fiscal_years_created",
    )

    class Meta:
        ordering = ["starts_on"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"], name="fiscal_year_unique_tenant_code"
            ),
            models.CheckConstraint(
                condition=Q(ends_on__gte=models.F("starts_on")),
                name="fiscal_year_valid_interval",
            ),
            ExclusionConstraint(
                name="fiscal_year_no_tenant_overlap",
                expressions=[
                    ("organization", RangeOperators.EQUAL),
                    (
                        DateRangeExpression(
                            "starts_on",
                            "ends_on",
                            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        if self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "پایان سال مالی پیش از شروع آن است."})
        if (
            FiscalYear.objects.filter(
                organization_id=self.organization_id,
                starts_on__lte=self.ends_on,
                ends_on__gte=self.starts_on,
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError("سال مالی با سال موجود هم‌پوشانی دارد.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        if not self._state.adding and self.periods.exists():
            original = FiscalYear.objects.get(pk=self.pk)
            immutable = (
                "organization_id",
                "code",
                "starts_on",
                "ends_on",
                "calendar_version",
            )
            if any(
                getattr(original, field) != getattr(self, field) for field in immutable
            ):
                raise ValidationError("سال مالی استفاده‌شده قابل بازتفسیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class FiscalPeriod(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="fiscal_periods",
    )
    fiscal_year = models.ForeignKey(
        FiscalYear, on_delete=models.PROTECT, related_name="periods"
    )
    number = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=255)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_adjustment = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=FiscalPeriodStatus.choices,
        default=FiscalPeriodStatus.OPEN,
    )

    class Meta:
        ordering = ["fiscal_year", "number"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["fiscal_year", "number"],
                name="fiscal_period_unique_year_number",
            ),
            models.CheckConstraint(
                condition=Q(ends_on__gte=models.F("starts_on")),
                name="fiscal_period_valid_interval",
            ),
            ExclusionConstraint(
                name="fiscal_period_no_year_overlap",
                expressions=[
                    ("fiscal_year", RangeOperators.EQUAL),
                    (
                        DateRangeExpression(
                            "starts_on",
                            "ends_on",
                            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, fiscal_year=self.fiscal_year)
        if (
            self.starts_on < self.fiscal_year.starts_on
            or self.ends_on > self.fiscal_year.ends_on
        ):
            raise ValidationError("دوره باید در محدوده سال مالی باشد.")
        if self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "پایان دوره پیش از شروع آن است."})
        if self.number < 1:
            raise ValidationError({"number": "شماره دوره باید مثبت باشد."})
        if (
            FiscalPeriod.objects.filter(
                fiscal_year_id=self.fiscal_year_id,
                starts_on__lte=self.ends_on,
                ends_on__gte=self.starts_on,
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError("دوره مالی با دوره موجود هم‌پوشانی دارد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = FiscalPeriod.objects.get(pk=self.pk)
            if original.status != self.status:
                raise ValidationError(
                    "تغییر وضعیت دوره فقط از خدمت کنترل دوره مجاز است."
                )
            if self.journals.exists() or self.opening_balance_imports.exists():
                immutable = (
                    "organization_id",
                    "fiscal_year_id",
                    "number",
                    "starts_on",
                    "ends_on",
                )
                if any(
                    getattr(original, field) != getattr(self, field)
                    for field in immutable
                ):
                    raise ValidationError("دوره استفاده‌شده قابل بازتفسیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.fiscal_year.code}/{self.number}"


class JournalEntry(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    period = models.ForeignKey(
        FiscalPeriod, on_delete=models.PROTECT, related_name="journals"
    )
    kind = models.CharField(max_length=20, choices=JournalKind.choices)
    status = models.CharField(
        max_length=20, choices=JournalStatus.choices, default=JournalStatus.DRAFT
    )
    number = models.PositiveBigIntegerField(null=True, blank=True)
    document_date = models.DateField()
    accounting_date = models.DateField()
    currency = models.CharField(max_length=3, default="IRR")
    description = models.TextField()
    source_key = models.CharField(max_length=120)
    source_kind = models.CharField(max_length=40, default="manual")
    source_uuid = models.UUIDField(default=uuid.uuid4)
    source_version = models.PositiveIntegerField(default=1)
    event_kind = models.CharField(max_length=40, default="manual_entry")
    occurrence_id = models.UUIDField(default=uuid.uuid4)
    payload_hash = models.CharField(max_length=64, blank=True)
    posting_rule_code = models.CharField(max_length=100, blank=True)
    posting_rule_version = models.PositiveIntegerField(null=True, blank=True)
    evidence_reference = models.CharField(max_length=500, blank=True)
    reconciliation_reference = models.CharField(max_length=500, blank=True)
    cutoff_date = models.DateField(null=True, blank=True)
    precision_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="accounting_precision_journals",
    )
    rounding_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="accounting_rounding_journals",
    )
    prepared_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="journals_prepared",
    )
    submitted_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="journals_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="journals_posted",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal_entry",
    )
    replaces = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacement_entries",
    )
    adjusts = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="controlled_adjustments",
    )
    adjustment_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-accounting_date", "-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "source_key"],
                name="journal_unique_tenant_source",
            ),
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "source_kind",
                    "source_uuid",
                    "source_version",
                    "event_kind",
                    "occurrence_id",
                ],
                name="journal_unique_business_event",
            ),
            models.UniqueConstraint(
                fields=["organization", "number"],
                condition=Q(number__isnull=False),
                name="journal_unique_tenant_number",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=JournalStatus.DRAFT,
                        number__isnull=True,
                        posted_by__isnull=True,
                        posted_at__isnull=True,
                    )
                    | Q(
                        status=JournalStatus.PROPOSED,
                        number__isnull=True,
                        posted_by__isnull=True,
                        posted_at__isnull=True,
                    )
                    | Q(
                        status=JournalStatus.POSTED,
                        number__isnull=False,
                        posted_by__isnull=False,
                        posted_at__isnull=False,
                    )
                    | Q(
                        status__in=[JournalStatus.REJECTED, JournalStatus.CANCELLED],
                        number__isnull=True,
                        posted_by__isnull=True,
                        posted_at__isnull=True,
                    )
                ),
                name="journal_posting_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=[JournalStatus.PROPOSED, JournalStatus.POSTED],
                        precision_policy_version__isnull=False,
                        rounding_policy_version__isnull=False,
                    )
                    | Q(
                        status__in=[
                            JournalStatus.DRAFT,
                            JournalStatus.REJECTED,
                            JournalStatus.CANCELLED,
                        ]
                    )
                ),
                name="journal_submitted_policy_versions_required",
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind=JournalKind.OPENING, cutoff_date__isnull=False)
                    | Q(
                        kind__in=[
                            JournalKind.MANUAL,
                            JournalKind.REVERSAL,
                            JournalKind.REPLACEMENT,
                            JournalKind.OPERATIONAL,
                        ],
                        cutoff_date__isnull=True,
                    )
                ),
                name="journal_opening_cutoff_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        kind=JournalKind.REVERSAL,
                        reverses__isnull=False,
                        replaces__isnull=True,
                    )
                    | Q(
                        kind=JournalKind.REPLACEMENT,
                        reverses__isnull=True,
                        replaces__isnull=False,
                    )
                    | Q(
                        kind__in=[
                            JournalKind.MANUAL,
                            JournalKind.OPENING,
                            JournalKind.OPERATIONAL,
                        ],
                        reverses__isnull=True,
                        replaces__isnull=True,
                    )
                ),
                name="journal_correction_links_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        kind=JournalKind.MANUAL,
                        adjusts__isnull=False,
                        adjustment_reason__gt="",
                    )
                    | Q(adjusts__isnull=True, adjustment_reason="")
                ),
                name="journal_controlled_adjustment_consistent",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self, period=self.period, prepared_by=self.prepared_by
        )
        if self.source_version < 1:
            raise ValidationError({"source_version": "نسخه منبع باید مثبت باشد."})
        if self.currency != "IRR":
            raise ValidationError({"currency": "در محدوده فعلی فقط IRR مجاز است."})
        if not self.period.starts_on <= self.accounting_date <= self.period.ends_on:
            raise ValidationError(
                {"accounting_date": "تاریخ ثبت خارج از دوره مالی است."}
            )
        if self.kind == JournalKind.OPENING and (
            not self.evidence_reference.strip()
            or not self.reconciliation_reference.strip()
        ):
            raise ValidationError("سند افتتاحیه به مدرک و مرجع تطبیق نیاز دارد.")
        expected_contract = {
            JournalKind.MANUAL: ("manual", "manual_entry"),
            JournalKind.OPENING: ("opening", "opening_balance"),
            JournalKind.REVERSAL: ("accounting", "reversal"),
            JournalKind.REPLACEMENT: ("accounting", "replacement"),
            JournalKind.OPERATIONAL: ("treasury", "movement_posted"),
        }[self.kind]
        from .recognition_sources import (
            DRAFT_EVENT,
            DRAFT_REVERSAL_EVENT,
            DRAFT_SOURCE_KINDS,
        )

        recognition_draft = (
            self.kind == JournalKind.OPERATIONAL
            and self.source_kind in DRAFT_SOURCE_KINDS
            and self.event_kind in {DRAFT_EVENT, DRAFT_REVERSAL_EVENT}
            and self.status == JournalStatus.DRAFT
        )
        if not recognition_draft and (self.source_kind, self.event_kind) != expected_contract:
            raise ValidationError("نوع سند با قرارداد منبع/رویداد سازگار نیست.")
        for field_name in ("submitted_by", "posted_by"):
            membership = getattr(self, field_name, None)
            if membership is not None:
                validate_related_organizations(self, **{field_name: membership})
        for field_name in ("reverses", "replaces", "adjusts"):
            linked = getattr(self, field_name, None)
            if linked is not None:
                validate_related_organizations(self, **{field_name: linked})
                if linked.status != JournalStatus.POSTED:
                    raise ValidationError(
                        {field_name: "سند مرجع باید ثبت قطعی شده باشد."}
                    )
        if self.adjusts_id:
            if self.kind != JournalKind.MANUAL or not self.adjustment_reason.strip():
                raise ValidationError("تعدیل کنترل‌شده باید سند دستی با دلیل باشد.")
            if not self.period.is_adjustment:
                raise ValidationError("تعدیل فقط در دوره تعدیلی صریح مجاز است.")
            if self.adjusts.period.status != FiscalPeriodStatus.CLOSED:
                raise ValidationError("سند مرجع تعدیل باید در دوره بسته باشد.")
        elif self.period.is_adjustment and self.kind == JournalKind.MANUAL:
            raise ValidationError(
                "سند دستی دوره تعدیلی باید از خدمت تعدیل کنترل‌شده ایجاد شود."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = JournalEntry.objects.get(pk=self.pk)
            if original.status != JournalStatus.DRAFT:
                raise ValidationError("سند پس از ارسال تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != JournalStatus.DRAFT:
            raise ValidationError("سند پس از ارسال قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class JournalLine(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    journal = models.ForeignKey(
        JournalEntry, on_delete=models.PROTECT, related_name="lines"
    )
    line_number = models.PositiveIntegerField()
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="journal_lines"
    )
    description = models.CharField(max_length=500, blank=True)
    debit = models.DecimalField(max_digits=24, decimal_places=6, default=Decimal(0))
    credit = models.DecimalField(max_digits=24, decimal_places=6, default=Decimal(0))
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="journal_lines",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="journal_lines",
    )
    wbs_node = models.ForeignKey(
        "projects.WBSNode",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="journal_lines",
    )
    party = models.ForeignKey(
        "parties.BusinessParty",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="journal_lines",
    )
    source_line_uuid = models.UUIDField(editable=False)
    account_snapshot = models.JSONField(default=dict, blank=True)
    dimension_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["journal", "line_number"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["journal", "line_number"], name="journal_line_unique_number"
            ),
            models.CheckConstraint(
                condition=(Q(debit__gt=0, credit=0) | Q(credit__gt=0, debit=0)),
                name="journal_line_one_sided_positive",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, journal=self.journal, account=self.account)
        if not self.account.is_posting or self.account.archived_at is not None:
            raise ValidationError({"account": "فقط حساب برگ فعال قابل ثبت است."})
        relations = {
            key: value
            for key, value in {
                "project": self.project,
                "site": self.site,
                "wbs_node": self.wbs_node,
                "party": self.party,
            }.items()
            if value is not None
        }
        validate_related_organizations(self, **relations)
        if self.site_id and (
            not self.project_id or self.site.project_id != self.project_id
        ):
            raise ValidationError(
                {"site": "کارگاه باید متعلق به پروژه انتخاب‌شده باشد."}
            )
        if self.wbs_node_id and (
            not self.project_id or self.wbs_node.project_id != self.project_id
        ):
            raise ValidationError(
                {"wbs_node": "WBS باید متعلق به پروژه انتخاب‌شده باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        persisted_status = (
            JournalEntry.objects.only("status").get(pk=self.journal_id).status
        )
        if persisted_status != JournalStatus.DRAFT:
            raise ValidationError("ردیف‌های سند پس از ارسال قابل تغییر نیستند.")
        if not self.source_line_uuid:
            self.source_line_uuid = self.pk
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        persisted_status = (
            JournalEntry.objects.only("status").get(pk=self.journal_id).status
        )
        if persisted_status != JournalStatus.DRAFT:
            raise ValidationError("ردیف‌های سند پس از ارسال قابل حذف نیستند.")
        return super().delete(*args, **kwargs)


class JournalNumberSequence(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.PROTECT, primary_key=True
    )
    next_number = models.PositiveBigIntegerField(default=1)


class OpeningBalanceImport(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="opening_balance_imports",
    )
    fiscal_year = models.ForeignKey(
        FiscalYear, on_delete=models.PROTECT, related_name="opening_balance_imports"
    )
    period = models.ForeignKey(
        FiscalPeriod, on_delete=models.PROTECT, related_name="opening_balance_imports"
    )
    source_reference = models.CharField(max_length=500)
    cutoff_date = models.DateField()
    evidence_reference = models.CharField(max_length=500)
    reconciliation_reference = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=OpeningImportStatus.choices,
        default=OpeningImportStatus.DRAFT,
    )
    prepared_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="opening_imports_prepared",
    )
    proposed_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="opening_imports_accepted",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_journal = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="opening_import",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "source_reference", "cutoff_date"],
                name="opening_import_unique_source_cutoff",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status=OpeningImportStatus.ACCEPTED,
                        accepted_by__isnull=False,
                        accepted_at__isnull=False,
                        accepted_journal__isnull=False,
                    )
                    | Q(
                        ~Q(status=OpeningImportStatus.ACCEPTED),
                        accepted_by__isnull=True,
                        accepted_at__isnull=True,
                        accepted_journal__isnull=True,
                    )
                ),
                name="opening_import_acceptance_consistent",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            fiscal_year=self.fiscal_year,
            period=self.period,
            prepared_by=self.prepared_by,
        )
        if self.period.fiscal_year_id != self.fiscal_year_id:
            raise ValidationError({"period": "دوره متعلق به سال مالی انتخاب‌شده نیست."})
        if not all(
            value.strip()
            for value in (
                self.source_reference,
                self.evidence_reference,
                self.reconciliation_reference,
            )
        ):
            raise ValidationError("منبع، مدرک و مرجع تطبیق افتتاحیه الزامی است.")
        if self.cutoff_date >= self.period.starts_on:
            raise ValidationError("تاریخ برش باید پیش از شروع دوره افتتاحیه باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = OpeningBalanceImport.objects.get(pk=self.pk)
            if original.status != OpeningImportStatus.DRAFT:
                raise ValidationError("ورودی افتتاحیه پس از ارسال تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != OpeningImportStatus.DRAFT:
            raise ValidationError("ورودی افتتاحیه پس از ارسال قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class OpeningBalanceImportLine(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="opening_balance_import_lines",
    )
    opening_import = models.ForeignKey(
        OpeningBalanceImport, on_delete=models.PROTECT, related_name="lines"
    )
    line_number = models.PositiveIntegerField()
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="opening_import_lines"
    )
    debit = models.DecimalField(max_digits=24, decimal_places=6, default=Decimal(0))
    credit = models.DecimalField(max_digits=24, decimal_places=6, default=Decimal(0))
    description = models.CharField(max_length=500, blank=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True
    )
    site = models.ForeignKey(
        "projects.ProjectSite", on_delete=models.PROTECT, null=True, blank=True
    )
    wbs_node = models.ForeignKey(
        "projects.WBSNode", on_delete=models.PROTECT, null=True, blank=True
    )
    party = models.ForeignKey(
        "parties.BusinessParty", on_delete=models.PROTECT, null=True, blank=True
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["opening_import", "line_number"],
                name="opening_import_line_unique_number",
            ),
            models.CheckConstraint(
                condition=(Q(debit__gt=0, credit=0) | Q(credit__gt=0, debit=0)),
                name="opening_import_line_one_sided",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self, opening_import=self.opening_import, account=self.account
        )
        relations = {
            key: value
            for key, value in {
                "project": self.project,
                "site": self.site,
                "wbs_node": self.wbs_node,
                "party": self.party,
            }.items()
            if value is not None
        }
        validate_related_organizations(self, **relations)
        if not self.account.is_posting or self.account.archived_at is not None:
            raise ValidationError({"account": "فقط حساب برگ فعال قابل ورود است."})
        if self.site_id and (
            not self.project_id or self.site.project_id != self.project_id
        ):
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه باشد."})
        if self.wbs_node_id and (
            not self.project_id or self.wbs_node.project_id != self.project_id
        ):
            raise ValidationError({"wbs_node": "WBS باید متعلق به پروژه باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        persisted_status = (
            OpeningBalanceImport.objects.only("status")
            .get(pk=self.opening_import_id)
            .status
        )
        if persisted_status != OpeningImportStatus.DRAFT:
            raise ValidationError("ردیف‌های ورودی پس از ارسال قابل تغییر نیستند.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        persisted_status = (
            OpeningBalanceImport.objects.only("status")
            .get(pk=self.opening_import_id)
            .status
        )
        if persisted_status != OpeningImportStatus.DRAFT:
            raise ValidationError("ردیف‌های ورودی پس از ارسال قابل حذف نیستند.")
        return super().delete(*args, **kwargs)


class ReconciliationRun(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="accounting_reconciliation_runs",
    )
    scope = models.CharField(
        max_length=40,
        choices=ReconciliationScope.choices,
        default=ReconciliationScope.MANUAL_OPENING_CORRECTION,
    )
    scope_version = models.PositiveIntegerField(default=1)
    cutoff_date = models.DateField()
    scope_hash = models.CharField(max_length=64)
    input_hash = models.CharField(max_length=64)
    result_hash = models.CharField(max_length=64)
    source_count = models.PositiveBigIntegerField()
    journal_count = models.PositiveBigIntegerField()
    posted_count = models.PositiveBigIntegerField()
    pending_count = models.PositiveBigIntegerField()
    debit_total = models.DecimalField(max_digits=30, decimal_places=6)
    credit_total = models.DecimalField(max_digits=30, decimal_places=6)
    exception_count = models.PositiveBigIntegerField()
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="accounting_reconciliation_runs_created",
    )

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "scope_hash", "input_hash"],
                name="reconciliation_run_unique_input",
            ),
            models.CheckConstraint(
                condition=Q(scope_version__gte=1),
                name="reconciliation_run_scope_version_positive",
            ),
            models.CheckConstraint(
                condition=Q(debit_total__gte=0) & Q(credit_total__gte=0),
                name="reconciliation_run_totals_nonnegative",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, created_by=self.created_by)
        if self.scope != ReconciliationScope.MANUAL_OPENING_CORRECTION:
            raise ValidationError("دامنه تطبیق حسابداری در این مرحله مجاز نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("اجرای تطبیق نگهداری‌شده تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("اجرای تطبیق نگهداری‌شده قابل حذف نیست.")


class ReconciliationExceptionSnapshot(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="accounting_reconciliation_exception_snapshots",
    )
    run = models.ForeignKey(
        ReconciliationRun,
        on_delete=models.PROTECT,
        related_name="exceptions",
    )
    sequence = models.PositiveIntegerField()
    code = models.CharField(max_length=80)
    source_uuid = models.UUIDField()
    journal_uuid = models.UUIDField(null=True, blank=True)
    line_uuid = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["run", "sequence"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["run", "sequence"],
                name="reconciliation_exception_unique_sequence",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="reconciliation_exception_sequence_positive",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, run=self.run)

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("تصویر استثنای تطبیق تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("تصویر استثنای تطبیق قابل حذف نیست.")


class ReconciliationTieOutSnapshot(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="accounting_reconciliation_tie_out_snapshots",
    )
    run = models.ForeignKey(
        ReconciliationRun,
        on_delete=models.PROTECT,
        related_name="tie_outs",
    )
    sequence = models.PositiveIntegerField()
    tie_out_type = models.CharField(
        max_length=20, choices=ReconciliationTieOutType.choices
    )
    source_uuid = models.UUIDField()
    source_version = models.PositiveIntegerField()
    journal_uuid = models.UUIDField(null=True, blank=True)
    source_line_count = models.PositiveBigIntegerField()
    journal_line_count = models.PositiveBigIntegerField()
    source_debit_total = models.DecimalField(max_digits=30, decimal_places=6)
    source_credit_total = models.DecimalField(max_digits=30, decimal_places=6)
    journal_debit_total = models.DecimalField(max_digits=30, decimal_places=6)
    journal_credit_total = models.DecimalField(max_digits=30, decimal_places=6)
    count_matches = models.BooleanField()
    amount_matches = models.BooleanField()
    source_version_matches = models.BooleanField()
    exact_line_matches = models.BooleanField()
    dimension_matches = models.BooleanField()
    correction_chain_matches = models.BooleanField()
    evidence = models.JSONField(default=dict)
    evidence_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["run", "sequence"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["run", "sequence"],
                name="reconciliation_tie_out_unique_sequence",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="reconciliation_tie_out_sequence_positive",
            ),
            models.CheckConstraint(
                condition=Q(source_version__gte=1),
                name="reconciliation_tie_out_source_version_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(source_debit_total__gte=0)
                    & Q(source_credit_total__gte=0)
                    & Q(journal_debit_total__gte=0)
                    & Q(journal_credit_total__gte=0)
                ),
                name="reconciliation_tie_out_totals_nonnegative",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, run=self.run)

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("تصویر تطبیق تفصیلی تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("تصویر تطبیق تفصیلی قابل حذف نیست.")


class ReconciliationExceptionDisposition(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="accounting_reconciliation_exception_dispositions",
    )
    exception = models.OneToOneField(
        ReconciliationExceptionSnapshot,
        on_delete=models.PROTECT,
        related_name="disposition",
    )
    disposition = models.CharField(
        max_length=32, choices=ReconciliationExceptionDispositionCode.choices
    )
    reason = models.TextField()
    evidence_reference = models.CharField(max_length=500, blank=True)
    disposed_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="accounting_reconciliation_exceptions_disposed",
    )

    class Meta:
        ordering = ["exception"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=~Q(reason=""),
                name="reconciliation_disposition_reason_nonempty",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self, exception=self.exception, disposed_by=self.disposed_by
        )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل تعیین تکلیف الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("تعیین تکلیف استثنای تطبیق تغییرناپذیر است.")
        self.reason = self.reason.strip()
        self.evidence_reference = self.evidence_reference.strip()
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("تعیین تکلیف استثنای تطبیق قابل حذف نیست.")


class ReconciliationReview(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="accounting_reconciliation_reviews",
    )
    run = models.OneToOneField(
        ReconciliationRun,
        on_delete=models.PROTECT,
        related_name="review",
    )
    reason = models.TextField()
    scope_hash = models.CharField(max_length=64)
    input_hash = models.CharField(max_length=64)
    result_hash = models.CharField(max_length=64)
    disposition_hash = models.CharField(max_length=64)
    signed_evidence_hash = models.CharField(max_length=64)
    reviewed_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="accounting_reconciliations_reviewed",
    )

    class Meta:
        ordering = ["run"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=~Q(reason=""),
                name="reconciliation_review_reason_nonempty",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, run=self.run, reviewed_by=self.reviewed_by)
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل تأیید تطبیق الزامی است."})
        if self.reviewed_by_id == self.run.created_by_id:
            raise ValidationError(
                "ایجادکننده اجرای تطبیق نمی‌تواند همان اجرا را تأیید کند."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("تأیید تطبیق تغییرناپذیر است.")
        self.reason = self.reason.strip()
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("تأیید تطبیق قابل حذف نیست.")


class FinancialStatementRun(UUIDModel, CreatedAtModel):
    """Immutable retained reporting evidence derived only from posted journal lines."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="accounting_statement_runs",
    )
    kind = models.CharField(max_length=24, choices=FinancialStatementKind.choices)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField()
    currency = models.CharField(max_length=3, default="IRR")
    scope_hash = models.CharField(max_length=64)
    input_hash = models.CharField(max_length=64)
    result_hash = models.CharField(max_length=64)
    source_line_count = models.PositiveIntegerField(default=0)
    debit_total = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    credit_total = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    net_total = models.DecimalField(max_digits=24, decimal_places=6, default=Decimal(0))
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="accounting_statement_runs_created",
    )

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "kind",
                    "starts_on",
                    "ends_on",
                    "input_hash",
                ],
                name="statement_run_unique_retained_input",
                nulls_distinct=False,
            ),
            models.CheckConstraint(
                condition=Q(ends_on__gte=models.F("starts_on"))
                | Q(starts_on__isnull=True),
                name="statement_run_valid_interval",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, created_by=self.created_by)
        if self.currency != "IRR":
            raise ValidationError({"currency": "در محدوده فعلی فقط IRR مجاز است."})
        if self.kind == FinancialStatementKind.PROFIT_LOSS and not self.starts_on:
            raise ValidationError("صورت سود و زیان به تاریخ شروع نیاز دارد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("اجرای صورت مالی تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("اجرای صورت مالی قابل حذف نیست.")


class FinancialStatementLineSnapshot(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="accounting_statement_line_snapshots",
    )
    run = models.ForeignKey(
        FinancialStatementRun,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    sequence = models.PositiveIntegerField()
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="financial_statement_snapshots",
    )
    account_code = models.CharField(max_length=50)
    account_name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    opening_debit = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    opening_credit = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    period_debit = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    period_credit = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    closing_debit = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    closing_credit = models.DecimalField(
        max_digits=24, decimal_places=6, default=Decimal(0)
    )
    amount = models.DecimalField(max_digits=24, decimal_places=6, default=Decimal(0))
    source_line_count = models.PositiveIntegerField(default=0)
    source_line_evidence = models.JSONField(default=list)

    class Meta:
        ordering = ["run", "sequence"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["run", "sequence"],
                name="statement_line_unique_sequence",
            ),
            models.UniqueConstraint(
                fields=["run", "account"],
                name="statement_line_unique_account",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, run=self.run, account=self.account)

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("ردیف نگهداری‌شده صورت مالی تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("ردیف نگهداری‌شده صورت مالی قابل حذف نیست.")


class FiscalPeriodControlEvent(UUIDModel, CreatedAtModel):
    """Append-only close/reopen history; period.status is only the current state."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="accounting_period_control_events",
    )
    period = models.ForeignKey(
        FiscalPeriod,
        on_delete=models.PROTECT,
        related_name="control_events",
    )
    sequence = models.PositiveIntegerField()
    action = models.CharField(max_length=12, choices=PeriodControlActionType.choices)
    requested_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="accounting_period_controls_requested",
    )
    acted_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="accounting_period_controls_acted",
    )
    reason = models.TextField()
    reconciliation_run = models.ForeignKey(
        ReconciliationRun,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="period_close_events",
    )
    trial_balance_run = models.ForeignKey(
        FinancialStatementRun,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="period_trial_balance_close_events",
    )
    balance_sheet_run = models.ForeignKey(
        FinancialStatementRun,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="period_balance_sheet_close_events",
    )
    profit_loss_run = models.ForeignKey(
        FinancialStatementRun,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="period_profit_loss_close_events",
    )
    related_close = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reopen_event",
    )
    evidence_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["period", "sequence"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["period", "sequence"],
                name="period_control_unique_sequence",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gte=1),
                name="period_control_sequence_positive",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        relations = {
            "period": self.period,
            "requested_by": self.requested_by,
            "acted_by": self.acted_by,
        }
        for field_name in (
            "reconciliation_run",
            "trial_balance_run",
            "balance_sheet_run",
            "profit_loss_run",
            "related_close",
        ):
            value = getattr(self, field_name, None)
            if value is not None:
                relations[field_name] = value
        validate_related_organizations(self, **relations)
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل کنترل دوره الزامی است."})
        close_evidence = (
            self.reconciliation_run_id,
            self.trial_balance_run_id,
            self.balance_sheet_run_id,
            self.profit_loss_run_id,
        )
        if self.action == PeriodControlActionType.CLOSE:
            if not all(close_evidence) or self.related_close_id:
                raise ValidationError("رویداد بستن دوره به شواهد کامل نیاز دارد.")
        elif any(close_evidence) or not self.related_close_id:
            raise ValidationError("رویداد بازگشایی باید فقط به بستن قبلی ارجاع دهد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("سابقه کنترل دوره تغییرناپذیر است.")
        self.reason = self.reason.strip()
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("سابقه کنترل دوره قابل حذف نیست.")


# Accounting-owned CEP-042 mapping and immutable source/draft evidence.
from .recognition_models import (  # noqa: F401
    RecognitionMappingApproval,
    RecognitionMappingVersion,
    SourceRecognitionDraft,
)
