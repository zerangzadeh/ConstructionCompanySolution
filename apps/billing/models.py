from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.contracts.models import ContractDirection
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations

MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.0001")


class ProjectBaselineStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    APPROVED = "approved", "تأییدشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    WITHDRAWN = "withdrawn", "مستردشده"


class ProjectBaseline(UUIDModel, TimeStampedModel):
    """An immutable, fully priced commercial measurement snapshot."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="project_baselines",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        related_name="billing_baselines",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        verbose_name="قرارداد دریافتنی",
        on_delete=models.PROTECT,
        related_name="project_baselines",
    )
    version = models.PositiveIntegerField("نسخه")
    effective_date = models.DateField("تاریخ اثر")
    measurement_policy = models.CharField(
        "سیاست اندازه‌گیری",
        max_length=30,
        default="fully_priced",
        editable=False,
    )
    contract_value_snapshot = models.DecimalField(
        "تصویر مبلغ قرارداد", max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    approved_amendments_snapshot = models.DecimalField(
        "تصویر الحاقیه‌های تأییدشده",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    effective_ceiling = models.DecimalField(
        "سقف مؤثر قرارداد", max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=ProjectBaselineStatus.choices,
        default=ProjectBaselineStatus.DRAFT,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تأییدکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_baselines_approved",
    )
    approved_at = models.DateTimeField("زمان تأیید", null=True, blank=True)
    approval_reason = models.TextField("دلیل تأیید", blank=True)
    superseded_by = models.ForeignKey(
        "self",
        verbose_name="نسخه جایگزین",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_baselines",
    )
    withdrawn_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="مستردکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_baselines_withdrawn",
    )
    withdrawn_at = models.DateTimeField("زمان استرداد", null=True, blank=True)
    withdrawal_reason = models.TextField("دلیل استرداد", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_baselines_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_baselines_updated",
    )

    class Meta:
        verbose_name = "مبنای تجاری پروژه"
        verbose_name_plural = "مبناهای تجاری پروژه"
        ordering = ["contract_id", "-version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "contract", "version"],
                name="baseline_org_contract_version_uniq",
            ),
            models.UniqueConstraint(
                fields=["organization", "contract"],
                condition=Q(status=ProjectBaselineStatus.APPROVED),
                name="baseline_one_current_approved_contract",
            ),
            models.CheckConstraint(
                condition=Q(contract_value_snapshot__gte=0),
                name="baseline_contract_snapshot_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(effective_ceiling__gte=0),
                name="baseline_effective_ceiling_nonnegative",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "contract", "status"],
                name="baseline_org_ct_state_idx",
            ),
            models.Index(
                fields=["organization", "project", "status"],
                name="baseline_org_project_state_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        relations = {}
        if self.project_id:
            relations["project"] = self.project
        if self.contract_id:
            relations["contract"] = self.contract
        if self.superseded_by_id:
            relations["superseded_by"] = self.superseded_by
        validate_related_organizations(self, **relations)
        if self.contract_id and self.project_id:
            if self.contract.project_id != self.project_id:
                raise ValidationError(
                    {"contract": "قرارداد باید متعلق به پروژه مبنا باشد."}
                )
            if self.contract.direction != ContractDirection.RECEIVABLE:
                raise ValidationError(
                    {"contract": "مبنا فقط برای قرارداد دریافتنی است."}
                )
        if self.superseded_by_id and (
            self.superseded_by.contract_id != self.contract_id
            or self.superseded_by_id == self.pk
        ):
            raise ValidationError(
                {"superseded_by": "نسخه جایگزین باید برای همین قرارداد باشد."}
            )
        if self.status == ProjectBaselineStatus.APPROVED and (
            not self.approved_by_id or not self.approved_at or not self.approval_reason
        ):
            raise ValidationError("مبنای تأییدشده باید شواهد کامل تأیید داشته باشد.")
        if (
            self.status == ProjectBaselineStatus.SUPERSEDED
            and not self.superseded_by_id
        ):
            raise ValidationError("مبنای جایگزین‌شده باید به نسخه جایگزین متصل باشد.")
        if self.status == ProjectBaselineStatus.WITHDRAWN and (
            not self.withdrawn_by_id
            or not self.withdrawn_at
            or not self.withdrawal_reason
        ):
            raise ValidationError("مبنای مستردشده باید شواهد کامل استرداد داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable_states = {
                ProjectBaselineStatus.SUPERSEDED,
                ProjectBaselineStatus.WITHDRAWN,
            }
            if previous.status in immutable_states:
                raise ValidationError("مبنای نهایی‌شده قابل تغییر نیست.")
            if previous.status == ProjectBaselineStatus.APPROVED:
                changed = {
                    field
                    for field in (
                        "organization_id",
                        "project_id",
                        "contract_id",
                        "version",
                        "effective_date",
                        "measurement_policy",
                        "contract_value_snapshot",
                        "approved_amendments_snapshot",
                        "effective_ceiling",
                        "approved_by_id",
                        "approved_at",
                        "approval_reason",
                        "created_by_id",
                        "updated_by_id",
                    )
                    if getattr(previous, field) != getattr(self, field)
                }
                if changed or self.status not in {
                    ProjectBaselineStatus.APPROVED,
                    ProjectBaselineStatus.SUPERSEDED,
                }:
                    raise ValidationError("محتوای مبنای تأییدشده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("مبنای تجاری حذف نمی‌شود؛ پیش‌نویس را مسترد کنید.")

    def __str__(self) -> str:
        return f"{self.contract} / نسخه {self.version}"


class BaselineItem(UUIDModel, TimeStampedModel):
    """A fully priced, ordered line within a draft baseline."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="baseline_items",
    )
    baseline = models.ForeignKey(
        ProjectBaseline,
        verbose_name="مبنای تجاری",
        on_delete=models.PROTECT,
        related_name="items",
    )
    line_key = models.CharField("کلید پایدار ردیف", max_length=80)
    contract_item = models.ForeignKey(
        "contracts.ContractItem",
        verbose_name="ردیف قرارداد",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="baseline_items",
    )
    wbs_node = models.ForeignKey(
        "projects.WBSNode",
        verbose_name="گره ساختار شکست کار",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="baseline_items",
    )
    activity = models.ForeignKey(
        "projects.Activity",
        verbose_name="فعالیت",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="baseline_items",
    )
    description = models.CharField("شرح ردیف", max_length=255)
    unit = models.CharField("واحد", max_length=30)
    planned_quantity = models.DecimalField(
        "مقدار برنامه‌ریزی‌شده", max_digits=18, decimal_places=4
    )
    unit_rate = models.DecimalField("نرخ واحد", max_digits=18, decimal_places=2)
    planned_value = models.DecimalField(
        "ارزش برنامه‌ریزی‌شده", max_digits=18, decimal_places=2
    )
    sort_order = models.PositiveIntegerField("ترتیب نمایش", default=0)

    class Meta:
        verbose_name = "ردیف مبنای تجاری"
        verbose_name_plural = "ردیف‌های مبنای تجاری"
        ordering = ["sort_order", "created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["baseline", "line_key"], name="baseline_item_line_key_uniq"
            ),
            models.CheckConstraint(
                condition=Q(planned_quantity__gt=0),
                name="baseline_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_rate__gte=0),
                name="baseline_item_rate_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(planned_value__gte=0),
                name="baseline_item_value_nonnegative",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "baseline"], name="baseline_item_org_base_idx"
            )
        ]

    @property
    def calculated_value(self) -> Decimal:
        return (self.planned_quantity * self.unit_rate).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )

    def clean(self) -> None:
        super().clean()
        relations = {"baseline": self.baseline} if self.baseline_id else {}
        for name in ("contract_item", "wbs_node", "activity"):
            if getattr(self, f"{name}_id"):
                relations[name] = getattr(self, name)
        validate_related_organizations(self, **relations)
        if not self.baseline_id:
            return
        if self.baseline.status != ProjectBaselineStatus.DRAFT:
            raise ValidationError(
                {"baseline": "ردیف فقط در مبنای پیش‌نویس قابل تغییر است."}
            )
        if (
            self.contract_item_id
            and self.contract_item.contract_id != self.baseline.contract_id
        ):
            raise ValidationError(
                {"contract_item": "ردیف قرارداد باید متعلق به قرارداد مبنا باشد."}
            )
        if self.wbs_node_id and self.wbs_node.project_id != self.baseline.project_id:
            raise ValidationError(
                {"wbs_node": "گره ساختار شکست باید متعلق به پروژه مبنا باشد."}
            )
        if self.activity_id and self.activity.project_id != self.baseline.project_id:
            raise ValidationError({"activity": "فعالیت باید متعلق به پروژه مبنا باشد."})
        if (
            self.activity_id
            and self.wbs_node_id
            and self.activity.wbs_node_id != self.wbs_node_id
        ):
            raise ValidationError(
                {"activity": "فعالیت باید به گره ساختار شکست انتخابی وابسته باشد."}
            )
        if self.planned_value != self.calculated_value:
            raise ValidationError(
                {"planned_value": "ارزش ردیف باید از مقدار و نرخِ گرد‌شده محاسبه شود."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.select_related("baseline").get(pk=self.pk)
            if previous.baseline.status != ProjectBaselineStatus.DRAFT:
                raise ValidationError("ردیف مبنای نهایی‌شده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.baseline.status != ProjectBaselineStatus.DRAFT:
            raise ValidationError("ردیف مبنای نهایی‌شده قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class ProgressRecordStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده برای راستی‌آزمایی"
    VERIFIED = "verified", "راستی‌آزمایی‌شده"
    REJECTED = "rejected", "ردشده"


class ProgressRecord(UUIDModel, TimeStampedModel):
    """An append-only, baseline-pinned measurement source ledger entry."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="progress_records",
    )
    baseline = models.ForeignKey(
        ProjectBaseline,
        verbose_name="مبنای تجاری",
        on_delete=models.PROTECT,
        related_name="progress_records",
    )
    baseline_item = models.ForeignKey(
        BaselineItem,
        verbose_name="ردیف مبنا",
        on_delete=models.PROTECT,
        related_name="progress_records",
    )
    period_start = models.DateField("شروع دوره")
    period_end = models.DateField("پایان دوره")
    measured_on = models.DateField("تاریخ اندازه‌گیری")
    source_type = models.CharField("نوع منبع", max_length=40)
    source_reference = models.CharField("شناسه منبع", max_length=120)
    evidence = models.TextField("شواهد", blank=True)
    period_quantity = models.DecimalField("مقدار دوره", max_digits=18, decimal_places=4)
    previous_cumulative_quantity = models.DecimalField(
        "تجمعی پیشین", max_digits=18, decimal_places=4, default=Decimal("0.0000")
    )
    cumulative_quantity = models.DecimalField(
        "مقدار تجمعی", max_digits=18, decimal_places=4
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=ProgressRecordStatus.choices,
        default=ProgressRecordStatus.DRAFT,
        db_index=True,
    )
    corrects = models.ForeignKey(
        "self",
        verbose_name="رکورد اصلاح‌شده",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="corrections",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ارسال‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="progress_records_submitted",
    )
    submitted_at = models.DateTimeField("زمان ارسال", null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="راستی‌آزما",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="progress_records_verified",
    )
    verified_at = models.DateTimeField("زمان راستی‌آزمایی", null=True, blank=True)
    verification_reason = models.TextField("دلیل راستی‌آزمایی", blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ردکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="progress_records_rejected",
    )
    rejected_at = models.DateTimeField("زمان رد", null=True, blank=True)
    rejection_reason = models.TextField("دلیل رد", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="progress_records_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="progress_records_updated",
    )

    class Meta:
        verbose_name = "رکورد پیشرفت"
        verbose_name_plural = "رکوردهای پیشرفت"
        ordering = ["baseline_item_id", "measured_on", "created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["baseline_item", "source_type", "source_reference"],
                name="progress_source_per_baseline_item_uniq",
            ),
            models.UniqueConstraint(
                fields=["corrects"],
                condition=Q(corrects__isnull=False),
                name="progress_one_direct_correction_uniq",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start")),
                name="progress_period_order_valid",
            ),
            models.CheckConstraint(
                condition=Q(measured_on__gte=F("period_start"))
                & Q(measured_on__lte=F("period_end")),
                name="progress_measurement_in_period",
            ),
            models.CheckConstraint(
                condition=Q(period_quantity__gte=0),
                name="progress_period_quantity_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(previous_cumulative_quantity__gte=0),
                name="progress_previous_cumulative_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(cumulative_quantity__gte=0),
                name="progress_cumulative_quantity_nonnegative",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "baseline_item", "status"],
                name="progress_org_item_state_idx",
            ),
            models.Index(
                fields=["organization", "baseline", "measured_on"],
                name="progress_org_base_date_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        relations: dict[str, object] = {}
        for name in ("baseline", "baseline_item", "corrects"):
            if getattr(self, f"{name}_id"):
                relations[name] = getattr(self, name)
        validate_related_organizations(self, **relations)
        if self.baseline_item_id and self.baseline_item.baseline_id != self.baseline_id:
            raise ValidationError(
                {"baseline_item": "ردیف باید متعلق به مبنای انتخابی باشد."}
            )
        if self.corrects_id:
            if self.corrects_id == self.pk:
                raise ValidationError({"corrects": "رکورد نمی‌تواند خودش را اصلاح کند."})
            if (
                self.corrects.baseline_id != self.baseline_id
                or self.corrects.baseline_item_id != self.baseline_item_id
            ):
                raise ValidationError(
                    {"corrects": "اصلاح فقط برای همان ردیف مبنا مجاز است."}
                )
        if self.status == ProgressRecordStatus.SUBMITTED and (
            not self.submitted_by_id or not self.submitted_at
        ):
            raise ValidationError("رکورد ارسال‌شده باید شواهد ارسال داشته باشد.")
        if self.status == ProgressRecordStatus.VERIFIED and (
            not self.verified_by_id
            or not self.verified_at
            or not self.verification_reason
        ):
            raise ValidationError("رکورد راستی‌آزمایی‌شده باید شواهد کامل داشته باشد.")
        if self.status == ProgressRecordStatus.REJECTED and (
            not self.rejected_by_id or not self.rejected_at or not self.rejection_reason
        ):
            raise ValidationError("رکورد ردشده باید دلیل و شواهد کامل داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                ProgressRecordStatus.VERIFIED,
                ProgressRecordStatus.REJECTED,
            }:
                raise ValidationError(
                    "رکورد نهایی‌شده تغییر نمی‌کند؛ اصلاح پیوندخورده بسازید."
                )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("رکورد پیشرفت حذف نمی‌شود؛ مسیر اصلاح را استفاده کنید.")


class ClaimNumberScope(models.TextChoices):
    ORGANIZATION = "organization", "سازمان"
    CONTRACT = "contract", "قرارداد"


class ClaimPeriodBoundary(models.TextChoices):
    CALENDAR = "calendar", "تقویمی"
    EXPLICIT = "explicit", "دوره صریح"


class ClaimAdjustmentType(models.TextChoices):
    RETENTION = "retention", "کسور تضمین"
    RETENTION_RELEASE = "retention_release", "آزادسازی تضمین"
    TAX = "tax", "مالیات"
    INSURANCE = "insurance", "بیمه"
    ADVANCE_RECOVERY = "advance_recovery", "بازیافت پیش‌پرداخت"
    PENALTY = "penalty", "جرایم"
    OTHER = "other", "سایر"


class ClaimSettlementAllocationStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    REVERSED = "reversed", "برگشت‌خورده"


class BillingPolicy(UUIDModel, TimeStampedModel):
    """Tenant-owned, explicit rules used to produce draft commercial claims."""

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="billing_policy",
    )
    claim_number_scope = models.CharField(
        max_length=20,
        choices=ClaimNumberScope.choices,
        default=ClaimNumberScope.CONTRACT,
    )
    period_boundary = models.CharField(
        max_length=20,
        choices=ClaimPeriodBoundary.choices,
        default=ClaimPeriodBoundary.EXPLICIT,
    )
    allow_partial_periods = models.BooleanField(default=True)
    allow_late_measurements = models.BooleanField(default=False)
    money_decimal_places = models.PositiveSmallIntegerField(default=2)
    tax_rate = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal(0))
    tax_basis = models.CharField(max_length=20, default="gross")
    insurance_rate = models.DecimalField(
        max_digits=9, decimal_places=6, default=Decimal(0)
    )
    insurance_basis = models.CharField(max_length=20, default="gross")
    retention_rate = models.DecimalField(
        max_digits=9, decimal_places=6, default=Decimal(0)
    )
    retention_cap = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    advance_recovery_rate = models.DecimalField(
        max_digits=9, decimal_places=6, default=Decimal(0)
    )
    advance_recovery_cap = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    allow_negative_corrective_claims = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="billing_policies_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(money_decimal_places__gte=0)
                & Q(money_decimal_places__lte=4),
                name="billing_policy_money_places_range",
            ),
            models.CheckConstraint(
                condition=Q(tax_rate__gte=0)
                & Q(insurance_rate__gte=0)
                & Q(retention_rate__gte=0)
                & Q(advance_recovery_rate__gte=0),
                name="billing_policy_rates_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(retention_cap__gte=0) & Q(advance_recovery_cap__gte=0),
                name="billing_policy_caps_nonnegative",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.tax_basis not in {
            "gross",
            "net_before_tax",
        } or self.insurance_basis not in {"gross", "net_before_tax"}:
            raise ValidationError("مبنای مالیات و بیمه باید صریحاً معتبر باشد.")


class ProgressClaim(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="progress_claims",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="progress_claims"
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.PROTECT, related_name="progress_claims"
    )
    baseline = models.ForeignKey(
        ProjectBaseline, on_delete=models.PROTECT, related_name="progress_claims"
    )
    claim_number = models.PositiveIntegerField()
    revision_number = models.PositiveIntegerField(default=1)
    period_start = models.DateField()
    period_end = models.DateField()
    measurement_cutoff = models.DateField()
    policy_snapshot = models.JSONField(default=dict)
    gross_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    adjustment_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    net_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    status = models.CharField(
        max_length=20,
        choices=(
            ("draft", "پیش‌نویس"),
            ("submitted", "ارسال‌شده برای تأیید"),
            ("approved", "تأییدشده"),
            ("returned", "بازگردانده‌شده برای اصلاح"),
        ),
        default="draft",
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_claims_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_snapshot = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_claims_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_reason = models.TextField(blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_claims_returned",
    )
    returned_at = models.DateTimeField(null=True, blank=True)
    return_reason = models.TextField(blank=True)
    returned_revision = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="returned_from",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_claims_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="progress_claims_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "contract", "claim_number", "revision_number"],
                name="claim_org_contract_number_revision_uniq",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start"))
                & Q(measurement_cutoff__gte=F("period_start"))
                & Q(measurement_cutoff__lte=F("period_end")),
                name="claim_period_cutoff_valid",
            ),
            models.UniqueConstraint(
                fields=["organization", "contract", "claim_number"],
                condition=Q(status="approved"),
                name="claim_one_approved_revision_uniq",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "contract", "period_start"],
                name="claim_org_contract_period_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self, project=self.project, contract=self.contract, baseline=self.baseline
        )
        if (
            self.contract.project_id != self.project_id
            or self.baseline.contract_id != self.contract_id
        ):
            raise ValidationError(
                "پروژه، قرارداد و مبنای صورت‌وضعیت باید هم‌راستا باشند."
            )
        if self.status == "submitted" and (
            not self.submitted_by_id
            or not self.submitted_at
            or not self.submission_snapshot
        ):
            raise ValidationError(
                "صورت‌وضعیت ارسالی باید تصویر و شواهد ارسال داشته باشد."
            )
        if self.status == "approved" and (
            not self.approved_by_id or not self.approved_at or not self.approval_reason
        ):
            raise ValidationError(
                "صورت‌وضعیت تأییدشده باید شواهد کامل تأیید داشته باشد."
            )
        if self.status == "returned" and (
            not self.returned_by_id
            or not self.returned_at
            or not self.return_reason
            or not self.returned_revision_id
        ):
            raise ValidationError(
                "بازگشت صورت‌وضعیت باید به revision و شواهد کامل متصل باشد."
            )
        if self.returned_revision_id and (
            self.returned_revision.organization_id != self.organization_id
            or self.returned_revision.contract_id != self.contract_id
            or self.returned_revision.claim_number != self.claim_number
            or self.returned_revision.revision_number <= self.revision_number
        ):
            raise ValidationError(
                "revision بازگشتی باید نسخه بعدی همین صورت‌وضعیت باشد."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {"approved", "returned"}:
                raise ValidationError("صورت‌وضعیت نهایی‌شده قابل تغییر نیست.")
            if previous.status == "submitted":
                permitted = {
                    "status",
                    "approved_by_id",
                    "approved_at",
                    "approval_reason",
                    "returned_by_id",
                    "returned_at",
                    "return_reason",
                    "returned_revision_id",
                    "updated_by_id",
                    "updated_at",
                }
                changed = {
                    field.attname
                    for field in self._meta.concrete_fields
                    if getattr(previous, field.attname) != getattr(self, field.attname)
                }
                if changed - permitted or self.status not in {
                    "submitted",
                    "approved",
                    "returned",
                }:
                    raise ValidationError("تصویر صورت‌وضعیت ارسالی قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class ClaimSettlementAllocation(UUIDModel, TimeStampedModel):
    """An append-only settlement against an existing contract payment allocation."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="claim_settlement_allocations",
    )
    claim = models.ForeignKey(
        ProgressClaim,
        on_delete=models.PROTECT,
        related_name="settlement_allocations",
    )
    payment_allocation = models.ForeignKey(
        "payments.PaymentAllocation",
        on_delete=models.PROTECT,
        related_name="claim_settlement_allocations",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=ClaimSettlementAllocationStatus.choices,
        default=ClaimSettlementAllocationStatus.ACTIVE,
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="claim_settlement_allocations_reversed",
    )
    reversal_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="claim_settlement_allocations_created",
    )

    class Meta:
        verbose_name = "تخصیص تسویه صورت‌وضعیت"
        verbose_name_plural = "تخصیص‌های تسویه صورت‌وضعیت"
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="claim_settlement_amount_positive",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "claim", "status"],
                name="clm_set_org_clm_stat_idx",
            ),
            models.Index(
                fields=["organization", "payment_allocation", "status"],
                name="clm_set_org_pay_stat_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        relations = {}
        if self.claim_id:
            relations["claim"] = self.claim
        if self.payment_allocation_id:
            relations["payment_allocation"] = self.payment_allocation
        validate_related_organizations(self, **relations)
        if self.amount <= 0:
            raise ValidationError({"amount": "مبلغ تسویه باید مثبت باشد."})
        if self.amount != self.amount.quantize(MONEY_QUANTUM):
            raise ValidationError({"amount": "مبلغ تسویه حداکثر دو رقم اعشار دارد."})
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل تسویه الزامی است."})
        if self.claim_id and self.payment_allocation_id:
            allocation = self.payment_allocation
            if (
                allocation.contract_id != self.claim.contract_id
                or allocation.payment.project_id != self.claim.project_id
            ):
                raise ValidationError(
                    "تخصیص پرداخت باید با پروژه و قرارداد صورت‌وضعیت هم‌راستا باشد."
                )
        if self.status == ClaimSettlementAllocationStatus.REVERSED and (
            not self.reversed_at or not self.reversed_by_id or not self.reversal_reason
        ):
            raise ValidationError("برگشت تسویه باید شواهد کامل داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "organization_id",
                "claim_id",
                "payment_allocation_id",
                "amount",
                "reason",
                "created_by_id",
            )
            if any(
                getattr(previous, field) != getattr(self, field)
                for field in immutable_fields
            ):
                raise ValidationError("تخصیص تسویه قابل تغییر نیست.")
            if previous.status == ClaimSettlementAllocationStatus.REVERSED:
                raise ValidationError("تخصیص تسویه برگشت‌خورده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("تخصیص تسویه حذف نمی‌شود؛ مسیر برگشت را استفاده کنید.")


class ProgressClaimItem(UUIDModel, TimeStampedModel):
    claim = models.ForeignKey(
        ProgressClaim, on_delete=models.CASCADE, related_name="items"
    )
    baseline_item = models.ForeignKey(
        BaselineItem, on_delete=models.PROTECT, related_name="claim_items"
    )
    previous_cumulative_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    current_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    new_cumulative_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_rate_snapshot = models.DecimalField(max_digits=18, decimal_places=4)
    current_amount = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["claim", "baseline_item"], name="claim_item_baseline_item_uniq"
            )
        ]

    def _assert_draft(self) -> None:
        if self.claim_id and self.claim.status != "draft":
            raise ValidationError("ردیف صورت‌وضعیت ارسالی یا نهایی‌شده قابل تغییر نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        self._assert_draft()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        self._assert_draft()
        return super().delete(*args, **kwargs)


class ProgressClaimSource(UUIDModel):
    claim_item = models.ForeignKey(
        ProgressClaimItem, on_delete=models.CASCADE, related_name="sources"
    )
    progress_record = models.ForeignKey(
        ProgressRecord, on_delete=models.PROTECT, related_name="claim_sources"
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["claim_item", "progress_record"],
                name="claim_source_item_record_uniq",
            )
        ]

    def _assert_draft(self) -> None:
        if self.claim_item_id and self.claim_item.claim.status != "draft":
            raise ValidationError("منبع صورت‌وضعیت ارسالی یا نهایی‌شده قابل تغییر نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        self._assert_draft()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        self._assert_draft()
        return super().delete(*args, **kwargs)


class ClaimAdjustment(UUIDModel, TimeStampedModel):
    claim = models.ForeignKey(
        ProgressClaim, on_delete=models.CASCADE, related_name="adjustments"
    )
    adjustment_type = models.CharField(
        max_length=30, choices=ClaimAdjustmentType.choices
    )
    description = models.CharField(max_length=255)
    sequence = models.PositiveIntegerField(default=0)
    rate_snapshot = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    base_amount_snapshot = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    evidence = models.TextField(blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["claim", "sequence"], name="claim_adjustment_sequence_uniq"
            )
        ]

    def _assert_draft(self) -> None:
        if self.claim_id and self.claim.status != "draft":
            raise ValidationError("کسور صورت‌وضعیت ارسالی یا نهایی‌شده قابل تغییر نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        self._assert_draft()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        self._assert_draft()
        return super().delete(*args, **kwargs)
