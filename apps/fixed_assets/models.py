from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class PolicyStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    REVIEWED = "reviewed", "بررسی‌شده"
    PUBLISHED = "published", "منتشرشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    RETIRED = "retired", "بازنشسته"


class DepreciationConvention(models.TextChoices):
    DAILY_PRORATA = "daily_prorata", "تسهیم روزانه"
    FULL_MONTH = "full_month", "ماه کامل آماده‌به‌کار"
    NEXT_MONTH = "next_month", "از ماه کامل بعد"


class AssetStatus(models.TextChoices):
    CANDIDATE = "candidate", "نامزد"
    READY_FOR_REVIEW = "ready_for_review", "آماده بررسی"
    ACTIVE = "active", "فعال/سرمایه‌ای"
    SUSPENDED = "suspended", "تعلیق"
    HELD_FOR_DISPOSAL = "held_for_disposal", "نگهداری برای واگذاری"
    DISPOSED = "disposed", "واگذارشده"
    RETIRED = "retired", "خارج‌شده"
    REJECTED = "rejected", "ردشده"


class AssetTransactionType(models.TextChoices):
    OPENING = "opening", "افتتاحیه"
    CAPITALIZATION = "capitalization", "سرمایه‌ای‌کردن"
    ADDITION = "addition", "افزایش"
    IMPAIRMENT = "impairment", "کاهش ارزش"
    IMPAIRMENT_REVERSAL = "impairment_reversal", "برگشت کاهش ارزش"
    TRANSFER = "transfer", "انتقال"
    DISPOSAL = "disposal", "واگذاری"
    RETIREMENT = "retirement", "خروج"
    REVERSAL = "reversal", "برگشت اصلاحی"


class TransactionStatus(models.TextChoices):
    PREPARED = "prepared", "تهیه‌شده"
    FINALIZED = "finalized", "نهایی"
    REVERSED = "reversed", "برگشت‌شده"


class DepreciationRunStatus(models.TextChoices):
    PREVIEW = "preview", "پیش‌نمایش"
    FINALIZED = "finalized", "نهایی"
    REVERSED = "reversed", "برگشت‌شده"


class EnvelopeStatus(models.TextChoices):
    PREPARED = "prepared", "تهیه‌شده"
    REVIEWED = "reviewed", "بررسی‌شده"
    ACKNOWLEDGED = "acknowledged", "دریافت‌شده"
    REJECTED = "rejected", "ردشده"
    RECONCILED = "reconciled", "تطبیق‌شده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class FixedAssetClassVersion(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="fixed_asset_classes",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=160)
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20, choices=PolicyStatus.choices, default=PolicyStatus.DRAFT
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    account_mapping_reference = models.CharField(max_length=120)
    capitalization_policy_reference = models.CharField(max_length=120)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fixed_asset_classes_prepared",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_asset_classes_reviewed",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_asset_classes_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012 - Django Meta declarative configuration.
            models.UniqueConstraint(
                fields=["organization", "code", "version"],
                name="fixed_asset_class_org_code_ver_uq",
            )
        ]

    def clean(self):
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if (
            not self.code
            or not self.name
            or not self.account_mapping_reference.strip()
            or not self.capitalization_policy_reference.strip()
        ):
            raise ValidationError(
                "طبقه دارایی نیازمند کد، نام و مراجع سیاست/نگاشت است."
            )

    def delete(self, *args, **kwargs):
        raise ValidationError("نسخه طبقه دارایی قابل حذف نیست.")


class AssetBookPolicyVersion(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="asset_book_policies",
    )
    code = models.CharField(max_length=50)
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20, choices=PolicyStatus.choices, default=PolicyStatus.DRAFT
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    currency_code = models.CharField(max_length=3, default="IRR")
    monetary_policy_code = models.CharField(max_length=80)
    monetary_policy_version = models.CharField(max_length=40)
    decimal_places = models.PositiveSmallIntegerField(default=0)
    convention = models.CharField(max_length=20, choices=DepreciationConvention.choices)
    method = models.CharField(max_length=30, default="straight_line_monthly")
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_book_policies_prepared",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_book_policies_reviewed",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_book_policies_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012 - Django Meta declarative configuration.
            models.UniqueConstraint(
                fields=["organization", "code", "version"],
                name="asset_book_policy_org_code_ver_uq",
            )
        ]

    def clean(self):
        self.code = canonicalize_upper_identifier(self.code)
        if self.currency_code != "IRR" or self.method != "straight_line_monthly":
            raise ValidationError("کتاب اولیه فقط IRR و استهلاک خط مستقیم ماهانه است.")
        if (
            self.decimal_places > 6
            or not self.monetary_policy_code.strip()
            or not self.monetary_policy_version.strip()
        ):
            raise ValidationError("سیاست پولی/دقت کتاب ناقص است.")

    def delete(self, *args, **kwargs):
        raise ValidationError("نسخه سیاست کتاب قابل حذف نیست.")


class FixedAsset(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="fixed_assets",
    )
    asset_number = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    asset_class = models.ForeignKey(
        FixedAssetClassVersion, on_delete=models.PROTECT, related_name="assets"
    )
    book_policy = models.ForeignKey(
        AssetBookPolicyVersion, on_delete=models.PROTECT, related_name="assets"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="components",
    )
    status = models.CharField(
        max_length=25, choices=AssetStatus.choices, default=AssetStatus.CANDIDATE
    )
    ownership_scope = models.CharField(max_length=20, default="owned_controlled")
    ready_for_use_date = models.DateField()
    useful_life_months = models.PositiveIntegerField()
    residual_value = models.DecimalField(max_digits=24, decimal_places=6)
    capitalization_basis = models.DecimalField(max_digits=24, decimal_places=6)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_assets",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_assets",
    )
    cost_center = models.ForeignKey(
        "projects.CostCenter",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_assets",
    )
    evidence_reference = models.CharField(max_length=255)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fixed_assets_prepared",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_assets_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012 - Django Meta declarative configuration.
            models.UniqueConstraint(
                fields=["organization", "asset_number"],
                name="fixed_asset_org_number_uq",
            ),
            models.CheckConstraint(
                condition=Q(capitalization_basis__gt=0),
                name="fixed_asset_basis_positive",
            ),
            models.CheckConstraint(
                condition=Q(residual_value__gte=0),
                name="fixed_asset_residual_nonnegative",
            ),
        ]

    def clean(self):
        self.asset_number = canonicalize_upper_identifier(self.asset_number)
        self.name = self.name.strip()
        validate_related_organizations(
            self,
            asset_class=self.asset_class,
            book_policy=self.book_policy,
            parent=self.parent,
            project=self.project,
            site=self.site,
            cost_center=self.cost_center,
        )
        if (
            self.asset_class.status != PolicyStatus.PUBLISHED
            or self.book_policy.status != PolicyStatus.PUBLISHED
        ):
            raise ValidationError("دارایی فقط با طبقه و کتاب منتشرشده مجاز است.")
        if self.residual_value > self.capitalization_basis:
            raise ValidationError("ارزش اسقاط نمی‌تواند بیش از مبنای سرمایه‌ای باشد.")
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError("کارگاه باید متعلق به پروژه دارایی باشد.")
        if self.ownership_scope != "owned_controlled":
            raise ValidationError("حسابداری اجاره/حق استفاده در این بسته مجاز نیست.")

    def delete(self, *args, **kwargs):
        raise ValidationError("دارایی ثابت قابل حذف نیست.")


class FixedAssetEquipmentLink(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="fixed_asset_equipment_links",
    )
    asset = models.ForeignKey(
        FixedAsset, on_delete=models.PROTECT, related_name="equipment_links"
    )
    equipment = models.ForeignKey(
        "equipment.Equipment",
        on_delete=models.PROTECT,
        related_name="fixed_asset_links",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=True)
    reason = models.TextField()
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fixed_asset_equipment_links_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012 - Django Meta declarative configuration.
            models.UniqueConstraint(
                fields=["asset"],
                condition=Q(is_primary=True, effective_to__isnull=True),
                name="fixed_asset_one_active_primary_equipment_uq",
            )
        ]

    def clean(self):
        validate_related_organizations(self, asset=self.asset, equipment=self.equipment)
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError("پایان پیوند پیش از شروع است.")
        if not self.reason.strip():
            raise ValidationError("علت پیوند الزامی است.")


class AssetSourceReference(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="asset_source_references",
    )
    asset = models.ForeignKey(
        FixedAsset, on_delete=models.PROTECT, related_name="source_references"
    )
    source_family = models.CharField(max_length=30)
    source_public_id = models.CharField(max_length=120)
    source_version = models.CharField(max_length=40)
    source_line = models.CharField(max_length=80, blank=True)
    source_date = models.DateField()
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    currency_code = models.CharField(max_length=3, default="IRR")
    evidence_reference = models.CharField(max_length=255)
    reviewed = models.BooleanField(default=False)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_sources_prepared",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_sources_reviewed",
    )

    class Meta:
        constraints = [  # noqa: RUF012 - Django Meta declarative configuration.
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "source_family",
                    "source_public_id",
                    "source_version",
                    "source_line",
                ],
                name="asset_source_occurrence_uq",
            )
        ]

    def clean(self):
        validate_related_organizations(self, asset=self.asset)
        if (
            self.source_family
            not in {"acquisition", "construction_ready", "legacy_opening"}
            or self.currency_code != "IRR"
            or self.amount <= 0
        ):
            raise ValidationError("مرجع منبع دارایی معتبر نیست.")

    def delete(self, *args, **kwargs):
        raise ValidationError("مرجع منبع دارایی قابل حذف نیست.")


class AssetTransaction(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="asset_transactions",
    )
    asset = models.ForeignKey(
        FixedAsset, on_delete=models.PROTECT, related_name="transactions"
    )
    source = models.ForeignKey(
        AssetSourceReference,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=25, choices=AssetTransactionType.choices
    )
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PREPARED,
    )
    occurred_on = models.DateField()
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    currency_code = models.CharField(max_length=3, default="IRR")
    occurrence_key = models.CharField(max_length=140)
    reason = models.TextField()
    source_dimensions_captured = models.BooleanField(default=False)
    source_project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_asset_transfer_sources",
    )
    source_site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_asset_transfer_sources",
    )
    source_cost_center = models.ForeignKey(
        "projects.CostCenter",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_asset_transfer_sources",
    )
    target_project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_asset_transfer_transactions",
    )
    target_site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_asset_transfer_transactions",
    )
    target_cost_center = models.ForeignKey(
        "projects.CostCenter",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_asset_transfer_transactions",
    )
    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversals",
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_transactions_prepared",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_transactions_reviewed",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012 - Django Meta declarative configuration.
            models.UniqueConstraint(
                fields=["organization", "occurrence_key"],
                name="asset_transaction_org_occurrence_uq",
            )
        ]

    def clean(self):
        validate_related_organizations(
            self,
            asset=self.asset,
            source=self.source,
            reversal_of=self.reversal_of,
            source_project=self.source_project,
            source_site=self.source_site,
            source_cost_center=self.source_cost_center,
            target_project=self.target_project,
            target_site=self.target_site,
            target_cost_center=self.target_cost_center,
        )
        if self.currency_code != "IRR" or self.amount < 0 or not self.reason.strip():
            raise ValidationError("مبلغ/علت رویداد دارایی معتبر نیست.")
        if self.source_id and self.source.asset_id != self.asset_id:
            raise ValidationError("منبع باید متعلق به همان دارایی باشد.")
        if (
            self.source_site_id
            and self.source_site.project_id != self.source_project_id
        ):
            raise ValidationError("کارگاه مبدأ باید متعلق به پروژه مبدأ باشد.")
        if (
            self.target_site_id
            and self.target_site.project_id != self.target_project_id
        ):
            raise ValidationError("کارگاه مقصد باید متعلق به پروژه مقصد باشد.")
        if (
            self.transaction_type == AssetTransactionType.TRANSFER
            and not self.target_project_id
        ):
            raise ValidationError("انتقال به پروژه مقصد نیاز دارد.")

    def delete(self, *args, **kwargs):
        raise ValidationError("رویداد دارایی قابل حذف نیست.")


class DepreciationRun(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="depreciation_runs",
    )
    book_policy = models.ForeignKey(
        AssetBookPolicyVersion,
        on_delete=models.PROTECT,
        related_name="depreciation_runs",
    )
    fiscal_period = models.ForeignKey(
        "accounting.FiscalPeriod",
        on_delete=models.PROTECT,
        related_name="fixed_asset_depreciation_runs",
    )
    status = models.CharField(
        max_length=20,
        choices=DepreciationRunStatus.choices,
        default=DepreciationRunStatus.PREVIEW,
    )
    occurrence_key = models.CharField(max_length=140)
    source_watermark = models.DateTimeField()
    reason = models.TextField(blank=True)
    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal_runs",
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="depreciation_runs_prepared",
    )
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="depreciation_runs_finalized",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012 - Django Meta declarative configuration.
            models.UniqueConstraint(
                fields=["organization", "occurrence_key"],
                name="depreciation_run_org_occurrence_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "book_policy", "fiscal_period"],
                condition=Q(
                    status=DepreciationRunStatus.FINALIZED, reversal_of__isnull=True
                ),
                name="depreciation_one_final_book_period_uq",
            ),
        ]

    def clean(self):
        validate_related_organizations(
            self,
            book_policy=self.book_policy,
            fiscal_period=self.fiscal_period,
            reversal_of=self.reversal_of,
        )

    def delete(self, *args, **kwargs):
        raise ValidationError("اجرای استهلاک قابل حذف نیست.")


class DepreciationLine(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="depreciation_lines",
    )
    run = models.ForeignKey(
        DepreciationRun, on_delete=models.PROTECT, related_name="lines"
    )
    asset = models.ForeignKey(
        FixedAsset, on_delete=models.PROTECT, related_name="depreciation_lines"
    )
    basis_snapshot = models.DecimalField(max_digits=24, decimal_places=6)
    residual_snapshot = models.DecimalField(max_digits=24, decimal_places=6)
    useful_life_months_snapshot = models.PositiveIntegerField()
    prior_accumulated_depreciation = models.DecimalField(
        max_digits=24, decimal_places=6
    )
    depreciation_amount = models.DecimalField(max_digits=24, decimal_places=6)
    carrying_value_after = models.DecimalField(max_digits=24, decimal_places=6)
    convention_snapshot = models.CharField(
        max_length=20, choices=DepreciationConvention.choices
    )

    class Meta:
        constraints = [  # noqa: RUF012 - Django Meta declarative configuration.
            models.UniqueConstraint(
                fields=["run", "asset"], name="depreciation_line_run_asset_uq"
            )
        ]

    def clean(self):
        validate_related_organizations(self, run=self.run, asset=self.asset)

    def delete(self, *args, **kwargs):
        raise ValidationError("خط استهلاک قابل حذف نیست.")


class FixedAssetSourceEnvelope(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="fixed_asset_envelopes",
    )
    consumer = models.CharField(max_length=30)
    asset_transaction = models.ForeignKey(
        AssetTransaction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="source_envelopes",
    )
    depreciation_line = models.ForeignKey(
        DepreciationLine,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="source_envelopes",
    )
    status = models.CharField(
        max_length=20, choices=EnvelopeStatus.choices, default=EnvelopeStatus.PREPARED
    )
    occurrence_key = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fixed_asset_envelopes_prepared",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_asset_envelopes_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    consumer_reference = models.CharField(max_length=120, blank=True)
    reconciliation_note = models.TextField(blank=True)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successors",
    )

    class Meta:
        constraints = [  # noqa: RUF012 - Django Meta declarative configuration.
            models.UniqueConstraint(
                fields=["organization", "consumer", "occurrence_key"],
                name="fixed_asset_env_org_cons_occ_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "consumer", "asset_transaction"],
                condition=Q(asset_transaction__isnull=False),
                name="fixed_asset_env_tx_cons_source_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "consumer", "depreciation_line"],
                condition=Q(depreciation_line__isnull=False),
                name="fixed_asset_env_dep_cons_source_uq",
            ),
        ]

    def clean(self):
        validate_related_organizations(
            self,
            asset_transaction=self.asset_transaction,
            depreciation_line=self.depreciation_line,
            supersedes=self.supersedes,
        )
        if self.consumer not in {"accounting", "project_cost"} or bool(
            self.asset_transaction_id
        ) == bool(self.depreciation_line_id):
            raise ValidationError("پیشنهاد باید یک منبع و مصرف‌کننده مجاز داشته باشد.")

    def delete(self, *args, **kwargs):
        raise ValidationError("پیشنهاد دارایی ثابت قابل حذف نیست.")


class AssetReconciliationEvidence(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="asset_reconciliation_evidence",
    )
    envelope = models.ForeignKey(
        FixedAssetSourceEnvelope,
        on_delete=models.PROTECT,
        related_name="reconciliation_evidence",
    )
    source_amount = models.DecimalField(max_digits=24, decimal_places=6)
    consumer_amount = models.DecimalField(
        max_digits=24, decimal_places=6, null=True, blank=True
    )
    difference = models.DecimalField(
        max_digits=24, decimal_places=6, null=True, blank=True
    )
    consumer_reference = models.CharField(max_length=120, blank=True)
    disposition = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asset_reconciliations_recorded",
    )

    def clean(self):
        validate_related_organizations(self, envelope=self.envelope)

    def delete(self, *args, **kwargs):
        raise ValidationError("شواهد تطبیق قابل حذف نیست.")
