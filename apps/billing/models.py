import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.contracts.models import ContractDirection
from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations

MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.0001")


class IndexationHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("سابقه تعدیل تغییرپذیر نیست.")

    def delete(self):
        raise ValidationError("سابقه تعدیل حذف‌پذیر نیست.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("ثبت گروهی سابقه تعدیل مجاز نیست.")


class IndexationHistory(UUIDModel, CreatedAtModel):
    objects = models.Manager.from_queryset(IndexationHistoryQuerySet)()
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    contract = models.ForeignKey("contracts.Contract", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField(max_length=2000)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("سابقه تعدیل تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("سابقه تعدیل حذف‌پذیر نیست.")

    def clean(self):
        super().clean()
        validate_related_organizations(self, contract=self.contract)
        if not self.reason.strip():
            raise ValidationError("دلیل لازم است.")


class IndexationRuleVersion(IndexationHistory):
    """Staging is immutable and never constitutes approval or activation."""

    code = models.CharField(max_length=80)
    version = models.PositiveIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField()
    adapter_key = models.CharField(max_length=100)
    specification = models.JSONField()
    sha256 = models.CharField(max_length=64)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "contract", "code", "version"],
                name="idx_rule_contract_version_uq",
            ),
            models.CheckConstraint(condition=Q(version__gte=1), name="idx_version_pos"),
            models.CheckConstraint(
                condition=Q(effective_to__gte=F("effective_from")),
                name="idx_effective_range",
            ),
        ]

    def clean(self):
        super().clean()
        from .indexation import rule_digest, validate_specification

        validate_specification(self.specification)
        if not self.code.strip() or not self.adapter_key.strip():
            raise ValidationError("شناسه قانون و تطبیق‌دهنده لازم است.")
        if self.effective_to < self.effective_from or self.version < 1:
            raise ValidationError("نسخه و بازه اثر معتبر لازم است.")
        if self.sha256 != rule_digest(self):
            raise ValidationError("چکیده قانون معتبر نیست.")


class IndexationCalculation(IndexationHistory):
    rule = models.ForeignKey(IndexationRuleVersion, on_delete=models.PROTECT)
    operation = models.CharField(
        max_length=12,
        choices=[("calculate", "محاسبه"), ("correct", "اصلاح"), ("reverse", "برگشت")],
    )
    prior = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacement",
    )
    calculation_date = models.DateField()
    idempotency_key = models.CharField(max_length=100)
    request_sha256 = models.CharField(max_length=64)
    snapshot = models.JSONField()
    sha256 = models.CharField(max_length=64)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "contract", "idempotency_key"],
                name="idx_calculation_key_uq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(operation="calculate", prior__isnull=True)
                    | Q(operation__in=["correct", "reverse"], prior__isnull=False)
                ),
                name="idx_operation_lineage",
            ),
        ]

    def clean(self):
        super().clean()
        from .indexation import digest, validate_calculation_snapshot

        validate_related_organizations(self, rule=self.rule, prior=self.prior)
        if self.rule.contract_id != self.contract_id or (
            self.prior_id
            and (
                self.prior.contract_id != self.contract_id
                or self.prior_id == self.pk
                or self.prior.operation == "reverse"
            )
        ):
            raise ValidationError("پیوند قرارداد و سابقه معتبر نیست.")
        if (self.operation == "calculate") != (self.prior_id is None):
            raise ValidationError("عملیات و سابقه سازگار نیست.")
        validate_calculation_snapshot(self)
        if self.sha256 != digest(self.snapshot):
            raise ValidationError("چکیده محاسبه معتبر نیست.")


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
    CONTRACTUAL_INSURANCE = "contractual_insurance", "کسور بیمه قراردادی"
    STATUTORY_INSURANCE = "statutory_insurance", "کسور بیمه مقرراتی"
    INSURANCE = "insurance", "بیمه قدیمی"
    ADVANCE_RECOVERY = "advance_recovery", "بازیافت پیش‌پرداخت"
    PENALTY = "penalty", "جرایم"
    OTHER = "other", "سایر"


class ClaimSettlementAllocationStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    REVERSED = "reversed", "برگشت‌خورده"


class ProgressClaimCorrectionKind(models.TextChoices):
    ORDINARY = "ordinary", "عادی"
    REPLACEMENT = "replacement", "اصلاح جایگزین"
    CANCELLATION = "cancellation", "ابطال"


class TenantBillingConfiguration(UUIDModel, TimeStampedModel):
    """Tenant-owned presentation and numbering defaults, never commercial rules."""

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="billing_configuration",
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
    currency_decimal_places = models.PositiveSmallIntegerField(default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="billing_configurations_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(currency_decimal_places__gte=0)
                & Q(currency_decimal_places__lte=4),
                name="billing_config_currency_places_range",
            ),
        ]


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
    correction_kind = models.CharField(
        max_length=20,
        choices=ProgressClaimCorrectionKind.choices,
        default=ProgressClaimCorrectionKind.ORDINARY,
    )
    corrects = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="correction_claims",
    )
    correction_reason = models.TextField(blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    measurement_cutoff = models.DateField()
    billing_configuration_snapshot = models.JSONField(default=dict)
    calculation_snapshot = models.JSONField(default=dict, blank=True)
    contract_term_version = models.ForeignKey(
        "contracts.ContractTermVersion",
        on_delete=models.PROTECT,
        related_name="progress_claims",
    )
    regulatory_rule_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="progress_claims",
    )
    party_identity_snapshot = models.ForeignKey(
        "parties.PartyIdentitySnapshot",
        on_delete=models.PROTECT,
        related_name="progress_claims",
    )
    currency_code = models.CharField(max_length=3)
    due_date = models.DateField(null=True, blank=True)
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
            ("superseded", "جایگزین‌شده با اصلاح"),
            ("cancelled", "باطل‌شده با سند پیوندخورده"),
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
            self,
            project=self.project,
            contract=self.contract,
            baseline=self.baseline,
            contract_term_version=self.contract_term_version,
            party_identity_snapshot=self.party_identity_snapshot,
            corrects=self.corrects if self.corrects_id else None,
        )
        if (
            self.contract.project_id != self.project_id
            or self.baseline.contract_id != self.contract_id
        ):
            raise ValidationError(
                "پروژه، قرارداد و مبنای صورت‌وضعیت باید هم‌راستا باشند."
            )
        if (
            not self.contract_term_version_id
            or self.contract_term_version.contract_id != self.contract_id
        ):
            raise ValidationError("نسخه شرایط باید متعلق به قرارداد صورت‌وضعیت باشد.")
        if (
            not self.regulatory_rule_version_id
            or not self.party_identity_snapshot_id
            or self.party_identity_snapshot.party_id != self.contract.party_id
        ):
            raise ValidationError("تصویر هویت باید متعلق به طرف قرارداد باشد.")
        if not self.currency_code or len(self.currency_code) != 3:
            raise ValidationError("کد ارز تصویرشده باید سه‌حرفی باشد.")
        if self.correction_kind == ProgressClaimCorrectionKind.ORDINARY:
            if self.corrects_id or self.correction_reason:
                raise ValidationError("صورت‌وضعیت عادی نباید پیوند اصلاح داشته باشد.")
        elif not self.corrects_id or not self.correction_reason.strip():
            raise ValidationError("اصلاح یا ابطال باید به سند پیشین و دلیل متصل باشد.")
        elif (
            self.corrects_id == self.pk
            or self.corrects.organization_id != self.organization_id
            or self.corrects.contract_id != self.contract_id
            or self.corrects.claim_number != self.claim_number
            or self.corrects.revision_number >= self.revision_number
        ):
            raise ValidationError("زنجیره اصلاح صورت‌وضعیت نامعتبر است.")
        if self.correction_kind == ProgressClaimCorrectionKind.CANCELLATION and any(
            value != 0
            for value in (self.gross_amount, self.adjustment_amount, self.net_amount)
        ):
            raise ValidationError("سند ابطال باید مبالغ صفر داشته باشد.")
        if self.net_amount < 0:
            raise ValidationError("صورت‌وضعیت عادی نمی‌تواند مبلغ خالص منفی داشته باشد.")
        if self.status == "submitted" and (
            not self.submitted_by_id
            or not self.submitted_at
            or not self.submission_snapshot
        ):
            raise ValidationError(
                "صورت‌وضعیت ارسالی باید تصویر و شواهد ارسال داشته باشد."
            )
        if self.status == "approved" and (
            not self.approved_by_id
            or not self.approved_at
            or not self.approval_reason
            or not self.due_date
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
            if previous.status in {
                "approved",
                "returned",
                "superseded",
                "cancelled",
            }:
                raise ValidationError("صورت‌وضعیت نهایی‌شده قابل تغییر نیست.")
            if previous.status == "submitted":
                permitted = {
                    "status",
                    "approved_by_id",
                    "approved_at",
                    "due_date",
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


class PayableMeasurementStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    VERIFIED = "verified", "راستی‌آزمایی‌شده"
    REJECTED = "rejected", "ردشده"


class PayableCertificateStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده برای تأیید"
    APPROVED = "approved", "تأییدشده"
    RETURNED = "returned", "بازگردانده‌شده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    CANCELLED = "cancelled", "باطل‌شده"


class PayableCertificateCorrectionKind(models.TextChoices):
    ORDINARY = "ordinary", "عادی"
    REPLACEMENT = "replacement", "اصلاح جایگزین"
    CANCELLATION = "cancellation", "ابطال پیوندخورده"


class PayableCertificateAdjustmentType(models.TextChoices):
    RETENTION = "retention", "کسور تضمین"
    ADVANCE_RECOVERY = "advance_recovery", "بازیافت پیش‌پرداخت"
    BACK_CHARGE = "back_charge", "کسر هزینه قابل برگشت"


class PayableMeasurement(UUIDModel, TimeStampedModel):
    """Subcontractor measured-work evidence; separate from receivable progress."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payable_measurements",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="payable_measurements",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.PROTECT,
        related_name="payable_measurements",
    )
    contract_item = models.ForeignKey(
        "contracts.ContractItem",
        on_delete=models.PROTECT,
        related_name="payable_measurements",
    )
    measured_on = models.DateField()
    period_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    cumulative_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    evidence_reference = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=PayableMeasurementStatus.choices,
        default=PayableMeasurementStatus.DRAFT,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payable_measurements_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payable_measurements_verified",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payable_measurements_created",
    )

    class Meta:
        ordering = ["contract_item_id", "measured_on", "created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(period_quantity__gt=0) & Q(cumulative_quantity__gt=0),
                name="pay_measure_quantities_positive",
            ),
            models.UniqueConstraint(
                fields=["organization", "contract_item", "measured_on"],
                condition=Q(status=PayableMeasurementStatus.VERIFIED),
                name="pay_measure_one_verified_per_day",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "contract", "status", "measured_on"],
                name="pay_measure_ct_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            project=self.project,
            contract=self.contract,
            contract_item=self.contract_item,
        )
        if (
            self.contract.direction != ContractDirection.PAYABLE
            or self.contract.contract_type != "subcontract"
            or self.contract.project_id != self.project_id
            or self.contract_item.contract_id != self.contract_id
        ):
            raise ValidationError("اندازه‌گیری بای ردیف پیمان جزء هم‌راست نیست.")
        if self.period_quantity <= 0 or self.cumulative_quantity <= 0:
            raise ValidationError("مقدار اندازه‌گیری باید مثبت باشد.")
        if self.cumulative_quantity > self.contract_item.quantity:
            raise ValidationError("مقدار تجمعی از مقدار ردیف پیمان بیشتر است.")
        if not self.evidence_reference.strip():
            raise ValidationError("مرجع شواهد اندازه‌گیری الزامی است.")
        if self.verified_by_id == self.created_by_id and self.verified_by_id:
            raise ValidationError(
                "ثبت‌کننده نمی‌تواند اندازه‌گیری خود را راستی‌آزمایی کند."
            )
        if self.status == PayableMeasurementStatus.SUBMITTED and (
            not self.submitted_by_id or not self.submitted_at
        ):
            raise ValidationError("اندازه‌گیری ارسالی باید شواهد ارسال داشته باشد.")
        if self.status in {
            PayableMeasurementStatus.VERIFIED,
            PayableMeasurementStatus.REJECTED,
        } and (
            not self.verified_by_id or not self.verified_at or not self.decision_reason
        ):
            raise ValidationError("تصمیم اندازه‌گیری باید شواهد کامل داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                PayableMeasurementStatus.VERIFIED,
                PayableMeasurementStatus.REJECTED,
            }:
                raise ValidationError("شواهد اندازه‌گیری نهایی تغییرناپذیر است.")
            if previous.status == PayableMeasurementStatus.SUBMITTED:
                permitted = {
                    "status",
                    "verified_by_id",
                    "verified_at",
                    "decision_reason",
                    "updated_at",
                }
                changed = {
                    field.attname
                    for field in self._meta.concrete_fields
                    if getattr(previous, field.attname) != getattr(self, field.attname)
                }
                if changed - permitted:
                    raise ValidationError("شواهد ارسال‌شده قابل ویرایش نیست.")
        self.evidence_reference = self.evidence_reference.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != PayableMeasurementStatus.DRAFT:
            raise ValidationError("اندازه‌گیری ارسالی یا نهایی‌شده حذف نمی‌شود.")
        return super().delete(*args, **kwargs)


class PayableCertificate(UUIDModel, TimeStampedModel):
    """Cumulative subcontract payable certification, never a receivable claim."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payable_certificates",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="payable_certificates",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.PROTECT,
        related_name="payable_certificates",
    )
    contract_term_version = models.ForeignKey(
        "contracts.ContractTermVersion",
        on_delete=models.PROTECT,
        related_name="payable_certificates",
    )
    party_identity_snapshot = models.ForeignKey(
        "parties.PartyIdentitySnapshot",
        on_delete=models.PROTECT,
        related_name="payable_certificates",
    )
    certificate_number = models.PositiveIntegerField()
    revision_number = models.PositiveIntegerField(default=1)
    correction_kind = models.CharField(
        max_length=20,
        choices=PayableCertificateCorrectionKind.choices,
        default=PayableCertificateCorrectionKind.ORDINARY,
    )
    corrects = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="correction_certificates",
    )
    correction_reason = models.TextField(blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    measurement_cutoff = models.DateField()
    currency_code = models.CharField(max_length=3)
    due_date = models.DateField(null=True, blank=True)
    gross_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    adjustment_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    net_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal(0)
    )
    calculation_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PayableCertificateStatus.choices,
        default=PayableCertificateStatus.DRAFT,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payable_certificates_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_snapshot = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payable_certificates_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_reason = models.TextField(blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payable_certificates_returned",
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
        on_delete=models.PROTECT,
        related_name="payable_certificates_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payable_certificates_updated",
    )

    class Meta:
        ordering = ["contract_id", "certificate_number", "revision_number"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "contract",
                    "certificate_number",
                    "revision_number",
                ],
                name="pay_cert_contract_number_revision_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "contract", "certificate_number"],
                condition=Q(status=PayableCertificateStatus.APPROVED),
                name="pay_cert_one_approved_revision_uq",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start"))
                & Q(measurement_cutoff__gte=F("period_start"))
                & Q(measurement_cutoff__lte=F("period_end")),
                name="pay_cert_period_cutoff_valid",
            ),
            models.CheckConstraint(
                condition=Q(net_amount__gte=0),
                name="pay_cert_net_nonnegative",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "contract", "status"],
                name="pay_cert_contract_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            project=self.project,
            contract=self.contract,
            contract_term_version=self.contract_term_version,
            party_identity_snapshot=self.party_identity_snapshot,
            corrects=self.corrects if self.corrects_id else None,
        )
        if (
            self.contract.direction != ContractDirection.PAYABLE
            or self.contract.contract_type != "subcontract"
            or self.contract.project_id != self.project_id
            or self.contract_term_version.contract_id != self.contract_id
            or self.party_identity_snapshot.party_id != self.contract.party_id
        ):
            raise ValidationError(
                "پروژه، پیمان، طرف و نسخه شرایط گواهی پرداخت هم‌راست نیست."
            )
        if len(self.currency_code) != 3:
            raise ValidationError("کد ارز باید سه‌حرفی باشد.")
        if self.correction_kind == PayableCertificateCorrectionKind.ORDINARY:
            if self.corrects_id or self.correction_reason:
                raise ValidationError("گواهی عادی نباید پیوند اصلاح داشته باشد.")
        elif not self.corrects_id or not self.correction_reason.strip():
            raise ValidationError(
                "اصلاح یا ابطال باید به گواهی پیشین و دلیل متصل باشد."
            )
        elif (
            self.corrects_id == self.pk
            or self.corrects.contract_id != self.contract_id
            or self.corrects.certificate_number != self.certificate_number
            or self.corrects.revision_number >= self.revision_number
        ):
            raise ValidationError("زنجیره اصلاح گواهی پرداخت نامعتبر است.")
        if (
            self.correction_kind == PayableCertificateCorrectionKind.CANCELLATION
            and any(
                value != 0
                for value in (
                    self.gross_amount,
                    self.adjustment_amount,
                    self.net_amount,
                )
            )
        ):
            raise ValidationError("سند ابطال باید مبالغ صفر داشته باشد.")
        if self.status == PayableCertificateStatus.SUBMITTED and (
            not self.submitted_by_id
            or not self.submitted_at
            or not self.submission_snapshot
        ):
            raise ValidationError("گواهی ارسالی باید تصویر و شواهد ارسال داشته باشد.")
        if self.status == PayableCertificateStatus.APPROVED and (
            not self.approved_by_id
            or not self.approved_at
            or not self.approval_reason
            or not self.due_date
        ):
            raise ValidationError("گواهی تأییدشده باید شواهد کامل تصمیم داشته باشد.")
        if self.status == PayableCertificateStatus.RETURNED and (
            not self.returned_by_id
            or not self.returned_at
            or not self.return_reason
            or not self.returned_revision_id
        ):
            raise ValidationError(
                "بازگردانی باید به نسخه بعدی و شواهد تصمیم متصل باشد."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                PayableCertificateStatus.APPROVED,
                PayableCertificateStatus.RETURNED,
                PayableCertificateStatus.SUPERSEDED,
                PayableCertificateStatus.CANCELLED,
            }:
                raise ValidationError("گواهی پرداخت نهایی تغییرناپذیر است.")
            if previous.status == PayableCertificateStatus.SUBMITTED:
                permitted = {
                    "status",
                    "approved_by_id",
                    "approved_at",
                    "approval_reason",
                    "due_date",
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
                if changed - permitted:
                    raise ValidationError("تصویر گواهی ارسال‌شده قابل ویرایش نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != PayableCertificateStatus.DRAFT:
            raise ValidationError("گواهی پرداخت ارسالی یا نهایی‌شده حذف نمی‌شود.")
        return super().delete(*args, **kwargs)


class PayableCertificateItem(UUIDModel, TimeStampedModel):
    certificate = models.ForeignKey(
        PayableCertificate, on_delete=models.CASCADE, related_name="items"
    )
    contract_item = models.ForeignKey(
        "contracts.ContractItem",
        on_delete=models.PROTECT,
        related_name="payable_certificate_items",
    )
    measurement = models.ForeignKey(
        PayableMeasurement,
        on_delete=models.PROTECT,
        related_name="certificate_items",
    )
    stable_line_id = models.UUIDField()
    previous_cumulative_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    current_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    new_cumulative_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_rate_snapshot = models.DecimalField(max_digits=18, decimal_places=4)
    current_amount = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["certificate", "stable_line_id"],
                name="pay_cert_stable_line_uq",
            )
        ]

    def _assert_draft(self) -> None:
        if (
            self.certificate_id
            and self.certificate.status != PayableCertificateStatus.DRAFT
        ):
            raise ValidationError("ردیف گواهی نهایی قابل تغییر نیست.")

    def clean(self) -> None:
        super().clean()
        if (
            self.contract_item_id
            and self.certificate_id
            and self.contract_item.contract_id != self.certificate.contract_id
        ):
            raise ValidationError("ردیف پیمان و گواهی پرداخت هم‌راستا نیستند.")
        if self.measurement_id and (
            self.measurement.contract_item_id != self.contract_item_id
            or self.measurement.contract_id != self.certificate.contract_id
            or self.measurement.status != PayableMeasurementStatus.VERIFIED
        ):
            raise ValidationError("شاهد اندازه‌گیری ردیف گواهی معتبر نیست.")
        if self.stable_line_id != self.contract_item_id:
            raise ValidationError("شناسه پایدار ردیف باید شناسه ردیف پیمان باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        self._assert_draft()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        self._assert_draft()
        return super().delete(*args, **kwargs)


class PayableCertificateAdjustment(UUIDModel, TimeStampedModel):
    certificate = models.ForeignKey(
        PayableCertificate, on_delete=models.CASCADE, related_name="adjustments"
    )
    adjustment_type = models.CharField(
        max_length=30, choices=PayableCertificateAdjustmentType.choices
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
                fields=["certificate", "sequence"],
                name="pay_cert_adjustment_sequence_uq",
            ),
            models.CheckConstraint(
                condition=Q(amount__lt=0),
                name="pay_cert_adjustment_negative",
            ),
        ]

    def _assert_draft(self) -> None:
        if (
            self.certificate_id
            and self.certificate.status != PayableCertificateStatus.DRAFT
        ):
            raise ValidationError("کسر گواهی نهایی قابل تغییر نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        self._assert_draft()
        if self.amount >= 0:
            raise ValidationError("کسر گواهی باید منفی باشد.")
        if (
            self.adjustment_type == PayableCertificateAdjustmentType.BACK_CHARGE
            and not self.evidence.strip()
        ):
            raise ValidationError("کسر هزینه بدون مرجع شواهد مجاز نیست.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        self._assert_draft()
        return super().delete(*args, **kwargs)


class GuaranteeType(models.TextChoices):
    BID = "bid", "ضمانت‌نامه شرکت در مناقصه"
    PERFORMANCE = "performance", "ضمانت‌نامه حسن انجام تعهدات"
    ADVANCE_PAYMENT = "advance_payment", "ضمانت‌نامه پیش‌پرداخت"
    RETENTION = "retention", "ضمانت‌نامه کسور تضمین"


class GuaranteeExposureSide(models.TextChoices):
    ISSUED = "issued", "صادرشده از طرف سازمان"
    RECEIVED = "received", "دریافت‌شده به نفع سازمان"


class EvidenceExpiryKind(models.TextChoices):
    DATED = "dated", "دارای تاریخ انقضا"
    OPEN_ENDED = "open_ended", "بدون تاریخ انقضای قراردادی"


class AssuranceRevisionAction(models.TextChoices):
    ORIGINAL = "original", "ثبت اولیه"
    CORRECTION = "correction", "اصلاح"
    RENEWAL = "renewal", "تمدید"
    RELEASE = "release", "آزادسازی"


class GuaranteeStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    ACTIVE = "active", "فعال"
    RETURNED = "returned", "بازگردانده‌شده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    EXPIRED = "expired", "منقضی‌شده"
    RELEASED = "released", "آزادشده"


class ContractGuarantee(UUIDModel, TimeStampedModel):
    """Versioned contract guarantee and explicit operational exposure evidence."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="guarantees",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="guarantees"
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.PROTECT, related_name="guarantees"
    )
    party_identity_snapshot = models.ForeignKey(
        "parties.PartyIdentitySnapshot",
        on_delete=models.PROTECT,
        related_name="guarantees",
    )
    series_id = models.UUIDField(default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(default=1)
    revision_action = models.CharField(
        max_length=20,
        choices=AssuranceRevisionAction.choices,
        default=AssuranceRevisionAction.ORIGINAL,
    )
    predecessor = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successor_versions",
    )
    revision_reason = models.TextField()
    guarantee_type = models.CharField(max_length=24, choices=GuaranteeType.choices)
    exposure_side = models.CharField(
        max_length=16, choices=GuaranteeExposureSide.choices
    )
    instrument_reference = models.CharField(max_length=120)
    issuer_name = models.CharField(max_length=255)
    currency_code = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    issued_on = models.DateField()
    effective_from = models.DateField()
    expiry_kind = models.CharField(max_length=20, choices=EvidenceExpiryKind.choices)
    expires_on = models.DateField(null=True, blank=True)
    evidence_document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="contract_guarantee_versions",
    )
    status = models.CharField(
        max_length=20,
        choices=GuaranteeStatus.choices,
        default=GuaranteeStatus.DRAFT,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="guarantees_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_snapshot = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="guarantees_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="guarantees_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="guarantees_updated",
    )

    class Meta:
        ordering = ["contract_id", "series_id", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "contract", "series_id", "version"],
                name="guarantee_series_version_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "series_id"],
                condition=Q(status=GuaranteeStatus.ACTIVE),
                name="guarantee_one_active_version_uq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(revision_action=AssuranceRevisionAction.RELEASE, amount=0)
                    | (
                        ~Q(revision_action=AssuranceRevisionAction.RELEASE)
                        & Q(amount__gt=0)
                    )
                ),
                name="guarantee_amount_action_valid",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status", "expires_on"],
                name="guarantee_expiry_work_idx",
            ),
            models.Index(
                fields=["organization", "project", "exposure_side", "status"],
                name="guarantee_exposure_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            project=self.project,
            contract=self.contract,
            party_identity_snapshot=self.party_identity_snapshot,
            evidence_document_version=self.evidence_document_version,
            predecessor=self.predecessor if self.predecessor_id else None,
        )
        if (
            self.contract.project_id != self.project_id
            or not self.contract.party_id
            or self.party_identity_snapshot.party_id != self.contract.party_id
        ):
            raise ValidationError("دامنه پروژه، قرارداد و طرف ضمانت‌نامه هم‌راستا نیست.")
        if len(self.currency_code) != 3:
            raise ValidationError("کد ارز ضمانت‌نامه باید سه‌حرفی باشد.")
        if self.expiry_kind == EvidenceExpiryKind.DATED:
            if not self.expires_on or self.expires_on < self.effective_from:
                raise ValidationError("تاریخ انقضای ضمانت‌نامه معتبر نیست.")
        elif self.expires_on is not None:
            raise ValidationError("ضمانت‌نامه بدون انقضا نباید تاریخ انقضا داشته باشد.")
        if self.revision_action == AssuranceRevisionAction.ORIGINAL:
            if self.predecessor_id or self.version != 1:
                raise ValidationError(
                    "ثبت اولیه ضمانت‌نامه نباید نسخه پیشین داشته باشد."
                )
        elif not self.predecessor_id or not self.revision_reason.strip():
            raise ValidationError(
                "نسخه اصلاح، تمدید یا آزادسازی به سابقه و دلیل نیاز دارد."
            )
        elif (
            self.predecessor.series_id != self.series_id
            or self.predecessor.contract_id != self.contract_id
            or self.predecessor.version >= self.version
        ):
            raise ValidationError("زنجیره نسخه ضمانت‌نامه معتبر نیست.")
        if self.status == GuaranteeStatus.SUBMITTED and (
            not self.submitted_by_id
            or not self.submitted_at
            or not self.submission_snapshot
        ):
            raise ValidationError("ضمانت‌نامه ارسالی باید شواهد ارسال داشته باشد.")
        if self.status in {GuaranteeStatus.ACTIVE, GuaranteeStatus.RELEASED} and (
            not self.approved_by_id or not self.approved_at or not self.decision_reason
        ):
            raise ValidationError("نسخه نهایی ضمانت‌نامه باید شواهد تصمیم داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                GuaranteeStatus.ACTIVE,
                GuaranteeStatus.RETURNED,
                GuaranteeStatus.SUPERSEDED,
                GuaranteeStatus.EXPIRED,
                GuaranteeStatus.RELEASED,
            }:
                raise ValidationError("سابقه نهایی ضمانت‌نامه تغییرناپذیر است.")
            if previous.status == GuaranteeStatus.SUBMITTED:
                permitted = {
                    "status",
                    "approved_by_id",
                    "approved_at",
                    "decision_reason",
                    "updated_by_id",
                    "updated_at",
                }
                changed = {
                    field.attname
                    for field in self._meta.concrete_fields
                    if getattr(previous, field.attname) != getattr(self, field.attname)
                }
                if changed - permitted:
                    raise ValidationError("تصویر ضمانت‌نامه ارسالی قابل ویرایش نیست.")
        self.instrument_reference = self.instrument_reference.strip()
        self.issuer_name = self.issuer_name.strip()
        self.revision_reason = self.revision_reason.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != GuaranteeStatus.DRAFT:
            raise ValidationError("ضمانت‌نامه ارسالی یا نهایی‌شده حذف نمی‌شود.")
        return super().delete(*args, **kwargs)


class ComplianceEvidenceKind(models.TextChoices):
    INSURANCE = "insurance", "شاهد بیمه قراردادی"
    CLEARANCE = "clearance", "شاهد مفاصاحساب"


class ComplianceEvidenceStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"
    RETURNED = "returned", "بازگردانده‌شده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    EXPIRED = "expired", "منقضی‌شده"


class ContractComplianceEvidence(UUIDModel, TimeStampedModel):
    """Versioned insurance or clearance evidence without inferred statutory effect."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="contract_compliance_evidence",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="contract_compliance_evidence",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.PROTECT,
        related_name="compliance_evidence",
    )
    party_identity_snapshot = models.ForeignKey(
        "parties.PartyIdentitySnapshot",
        on_delete=models.PROTECT,
        related_name="contract_compliance_evidence",
    )
    series_id = models.UUIDField(default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(default=1)
    revision_action = models.CharField(
        max_length=20,
        choices=AssuranceRevisionAction.choices,
        default=AssuranceRevisionAction.ORIGINAL,
    )
    predecessor = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successor_versions",
    )
    revision_reason = models.TextField()
    evidence_kind = models.CharField(
        max_length=20, choices=ComplianceEvidenceKind.choices
    )
    reference = models.CharField(max_length=120)
    issuing_authority = models.CharField(max_length=255)
    effective_from = models.DateField()
    expiry_kind = models.CharField(max_length=20, choices=EvidenceExpiryKind.choices)
    expires_on = models.DateField(null=True, blank=True)
    document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="contract_compliance_evidence",
    )
    status = models.CharField(
        max_length=20,
        choices=ComplianceEvidenceStatus.choices,
        default=ComplianceEvidenceStatus.DRAFT,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contract_compliance_evidence_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_snapshot = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contract_compliance_evidence_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contract_compliance_evidence_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contract_compliance_evidence_updated",
    )

    class Meta:
        ordering = ["contract_id", "series_id", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "contract", "series_id", "version"],
                name="compliance_evidence_series_version_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "series_id"],
                condition=Q(status=ComplianceEvidenceStatus.APPROVED),
                name="compliance_evidence_one_approved_uq",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status", "expires_on"],
                name="compliance_expiry_work_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            project=self.project,
            contract=self.contract,
            party_identity_snapshot=self.party_identity_snapshot,
            document_version=self.document_version,
            predecessor=self.predecessor if self.predecessor_id else None,
        )
        if (
            self.contract.project_id != self.project_id
            or not self.contract.party_id
            or self.party_identity_snapshot.party_id != self.contract.party_id
        ):
            raise ValidationError(
                "دامنه پروژه، قرارداد و طرف شاهد انطباق هم‌راستا نیست."
            )
        if self.expiry_kind == EvidenceExpiryKind.DATED:
            if not self.expires_on or self.expires_on < self.effective_from:
                raise ValidationError("تاریخ انقضای شاهد انطباق معتبر نیست.")
        elif self.expires_on is not None:
            raise ValidationError("شاهد بدون انقضا نباید تاریخ انقضا داشته باشد.")
        if self.revision_action == AssuranceRevisionAction.ORIGINAL:
            if self.predecessor_id or self.version != 1:
                raise ValidationError("ثبت اولیه شاهد نباید نسخه پیشین داشته باشد.")
        elif (
            self.revision_action == AssuranceRevisionAction.RELEASE
            or not self.predecessor_id
            or not self.revision_reason.strip()
        ):
            raise ValidationError("نسخه شاهد فقط می‌تواند اصلاح یا تمدید مستند باشد.")
        elif (
            self.predecessor.series_id != self.series_id
            or self.predecessor.contract_id != self.contract_id
            or self.predecessor.version >= self.version
        ):
            raise ValidationError("زنجیره نسخه شاهد انطباق معتبر نیست.")
        if self.status == ComplianceEvidenceStatus.SUBMITTED and (
            not self.submitted_by_id
            or not self.submitted_at
            or not self.submission_snapshot
        ):
            raise ValidationError("شاهد ارسالی باید شواهد ارسال داشته باشد.")
        if self.status == ComplianceEvidenceStatus.APPROVED and (
            not self.approved_by_id or not self.approved_at or not self.decision_reason
        ):
            raise ValidationError("شاهد تأییدشده باید شواهد تصمیم داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                ComplianceEvidenceStatus.APPROVED,
                ComplianceEvidenceStatus.RETURNED,
                ComplianceEvidenceStatus.SUPERSEDED,
                ComplianceEvidenceStatus.EXPIRED,
            }:
                raise ValidationError("شاهد نهایی انطباق تغییرناپذیر است.")
            if previous.status == ComplianceEvidenceStatus.SUBMITTED:
                permitted = {
                    "status",
                    "approved_by_id",
                    "approved_at",
                    "decision_reason",
                    "updated_by_id",
                    "updated_at",
                }
                changed = {
                    field.attname
                    for field in self._meta.concrete_fields
                    if getattr(previous, field.attname) != getattr(self, field.attname)
                }
                if changed - permitted:
                    raise ValidationError("تصویر شاهد ارسالی قابل ویرایش نیست.")
        self.reference = self.reference.strip()
        self.issuing_authority = self.issuing_authority.strip()
        self.revision_reason = self.revision_reason.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != ComplianceEvidenceStatus.DRAFT:
            raise ValidationError("شاهد ارسالی یا نهایی‌شده حذف نمی‌شود.")
        return super().delete(*args, **kwargs)


class RetentionReleaseStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"
    RETURNED = "returned", "بازگردانده‌شده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    CANCELLED = "cancelled", "باطل‌شده"


class RetentionReleaseCorrectionKind(models.TextChoices):
    ORDINARY = "ordinary", "عادی"
    REPLACEMENT = "replacement", "اصلاح جایگزین"
    CANCELLATION = "cancellation", "ابطال پیوندخورده"


class RetentionRelease(UUIDModel, TimeStampedModel):
    """Controlled release of retained payable-certificate value; never AP or GL."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="retention_releases",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="retention_releases"
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.PROTECT,
        related_name="retention_releases",
    )
    contract_term_version = models.ForeignKey(
        "contracts.ContractTermVersion",
        on_delete=models.PROTECT,
        related_name="retention_releases",
    )
    party_identity_snapshot = models.ForeignKey(
        "parties.PartyIdentitySnapshot",
        on_delete=models.PROTECT,
        related_name="retention_releases",
    )
    release_number = models.PositiveIntegerField()
    revision_number = models.PositiveIntegerField(default=1)
    correction_kind = models.CharField(
        max_length=20,
        choices=RetentionReleaseCorrectionKind.choices,
        default=RetentionReleaseCorrectionKind.ORDINARY,
    )
    corrects = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="correction_releases",
    )
    correction_reason = models.TextField(blank=True)
    release_date = models.DateField()
    currency_code = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    retained_total_snapshot = models.DecimalField(max_digits=18, decimal_places=4)
    prior_release_total_snapshot = models.DecimalField(max_digits=18, decimal_places=4)
    available_amount_snapshot = models.DecimalField(max_digits=18, decimal_places=4)
    calculation_snapshot = models.JSONField(default=dict)
    evidence_document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="retention_release_evidence",
    )
    clearance_evidence = models.ForeignKey(
        ContractComplianceEvidence,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="retention_releases",
    )
    status = models.CharField(
        max_length=20,
        choices=RetentionReleaseStatus.choices,
        default=RetentionReleaseStatus.DRAFT,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="retention_releases_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_snapshot = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="retention_releases_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retention_releases_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retention_releases_updated",
    )

    class Meta:
        ordering = ["contract_id", "release_number", "revision_number"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "contract",
                    "release_number",
                    "revision_number",
                ],
                name="retention_release_number_revision_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "contract", "release_number"],
                condition=Q(status=RetentionReleaseStatus.APPROVED),
                name="retention_release_one_approved_uq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        correction_kind=RetentionReleaseCorrectionKind.CANCELLATION,
                        amount=0,
                    )
                    | (
                        ~Q(correction_kind=RetentionReleaseCorrectionKind.CANCELLATION)
                        & Q(amount__gt=0)
                    )
                ),
                name="retention_release_amount_kind_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(retained_total_snapshot__gte=0)
                    & Q(prior_release_total_snapshot__gte=0)
                    & Q(available_amount_snapshot__gte=0)
                ),
                name="retention_release_snapshots_nonnegative",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "contract", "status"],
                name="retention_release_status_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            project=self.project,
            contract=self.contract,
            contract_term_version=self.contract_term_version,
            party_identity_snapshot=self.party_identity_snapshot,
            evidence_document_version=self.evidence_document_version,
            clearance_evidence=self.clearance_evidence
            if self.clearance_evidence_id
            else None,
            corrects=self.corrects if self.corrects_id else None,
        )
        if (
            self.contract.project_id != self.project_id
            or not self.contract.party_id
            or self.party_identity_snapshot.party_id != self.contract.party_id
            or self.contract_term_version.contract_id != self.contract_id
        ):
            raise ValidationError(
                "دامنه پروژه، قرارداد، طرف و شرایط آزادسازی هم‌راستا نیست."
            )
        if len(self.currency_code) != 3:
            raise ValidationError("کد ارز آزادسازی باید سه‌حرفی باشد.")
        if self.clearance_evidence_id and (
            self.clearance_evidence.contract_id != self.contract_id
            or self.clearance_evidence.evidence_kind != ComplianceEvidenceKind.CLEARANCE
            or self.clearance_evidence.status != ComplianceEvidenceStatus.APPROVED
        ):
            raise ValidationError("شاهد مفاصاحساب آزادسازی معتبر نیست.")
        if self.correction_kind == RetentionReleaseCorrectionKind.ORDINARY:
            if self.corrects_id or self.correction_reason:
                raise ValidationError("آزادسازی عادی نباید پیوند اصلاح داشته باشد.")
        elif not self.corrects_id or not self.correction_reason.strip():
            raise ValidationError("اصلاح آزادسازی باید به سابقه و دلیل متصل باشد.")
        elif (
            self.corrects.contract_id != self.contract_id
            or self.corrects.release_number != self.release_number
            or self.corrects.revision_number >= self.revision_number
        ):
            raise ValidationError("زنجیره اصلاح آزادسازی معتبر نیست.")
        if self.status == RetentionReleaseStatus.SUBMITTED and (
            not self.submitted_by_id
            or not self.submitted_at
            or not self.submission_snapshot
        ):
            raise ValidationError("آزادسازی ارسالی باید شواهد ارسال داشته باشد.")
        if self.status == RetentionReleaseStatus.APPROVED and (
            not self.approved_by_id or not self.approved_at or not self.decision_reason
        ):
            raise ValidationError("آزادسازی تأییدشده باید شواهد تصمیم داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                RetentionReleaseStatus.APPROVED,
                RetentionReleaseStatus.RETURNED,
                RetentionReleaseStatus.SUPERSEDED,
                RetentionReleaseStatus.CANCELLED,
            }:
                raise ValidationError("سابقه نهایی آزادسازی تغییرناپذیر است.")
            if previous.status == RetentionReleaseStatus.SUBMITTED:
                permitted = {
                    "status",
                    "approved_by_id",
                    "approved_at",
                    "decision_reason",
                    "updated_by_id",
                    "updated_at",
                }
                changed = {
                    field.attname
                    for field in self._meta.concrete_fields
                    if getattr(previous, field.attname) != getattr(self, field.attname)
                }
                if changed - permitted:
                    raise ValidationError("تصویر آزادسازی ارسالی قابل ویرایش نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != RetentionReleaseStatus.DRAFT:
            raise ValidationError("آزادسازی ارسالی یا نهایی‌شده حذف نمی‌شود.")
        return super().delete(*args, **kwargs)


class StatutoryRecordKind(models.TextChoices):
    ORIGINAL = "original", "اصلی"
    CORRECTION = "correction", "اصلاحی"
    CANCELLATION = "cancellation", "ابطالی"


class StatutoryRecordStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده برای تأیید"
    APPROVED = "approved", "آماده خروجی/ارسال"
    RETURNED = "returned", "بازگردانده‌شده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    CANCELLED = "cancelled", "باطل‌شده"


class TaxpayerInvoice(UUIDModel, TimeStampedModel):
    """Immutable approved statutory derivative of one commercial claim revision."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="taxpayer_invoices",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="taxpayer_invoices"
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.PROTECT, related_name="taxpayer_invoices"
    )
    source_claim = models.OneToOneField(
        ProgressClaim, on_delete=models.PROTECT, related_name="taxpayer_invoice"
    )
    party_identity_snapshot = models.ForeignKey(
        "parties.PartyIdentitySnapshot",
        on_delete=models.PROTECT,
        related_name="taxpayer_invoices",
    )
    policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="taxpayer_invoices",
    )
    series_id = models.UUIDField(default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(default=1)
    record_kind = models.CharField(max_length=20, choices=StatutoryRecordKind.choices)
    corrects = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="corrections",
    )
    reason = models.TextField()
    schema_identifier = models.CharField(max_length=255)
    tax_code = models.CharField(max_length=120)
    currency_code = models.CharField(max_length=3)
    taxable_amount = models.DecimalField(max_digits=18, decimal_places=4)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4)
    total_amount = models.DecimalField(max_digits=18, decimal_places=4)
    payload_snapshot = models.JSONField(default=dict)
    preflight_snapshot = models.JSONField(default=dict)
    submission_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatutoryRecordStatus.choices,
        default=StatutoryRecordStatus.DRAFT,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="taxpayer_invoices_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="taxpayer_invoices_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="taxpayer_invoices_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="taxpayer_invoices_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "series_id", "version"],
                name="taxpayer_invoice_series_version_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "series_id"],
                condition=Q(status=StatutoryRecordStatus.APPROVED),
                name="taxpayer_invoice_one_approved_uq",
            ),
            models.CheckConstraint(
                condition=Q(taxable_amount__gte=0)
                & Q(tax_amount__gte=0)
                & Q(total_amount__gte=0),
                name="taxpayer_invoice_amounts_nonnegative",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status", "created_at"],
                name="taxpayer_invoice_work_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            project=self.project,
            contract=self.contract,
            source_claim=self.source_claim,
            party_identity_snapshot=self.party_identity_snapshot,
            corrects=self.corrects if self.corrects_id else None,
        )
        if (
            self.contract.project_id != self.project_id
            or self.source_claim.contract_id != self.contract_id
            or self.source_claim.project_id != self.project_id
            or not self.contract.party_id
            or self.party_identity_snapshot.party_id != self.contract.party_id
        ):
            raise ValidationError(
                "دامنه Tenant، پروژه، قرارداد، سند و طرف صورتحساب هم‌راستا نیست."
            )
        if len(self.currency_code) != 3:
            raise ValidationError("کد ارز صورتحساب باید سه‌حرفی باشد.")
        if self.record_kind == StatutoryRecordKind.ORIGINAL:
            if self.corrects_id or self.version != 1:
                raise ValidationError("صورتحساب اصلی نباید سابقه اصلاح داشته باشد.")
        elif (
            not self.corrects_id
            or not self.reason.strip()
            or self.corrects.series_id != self.series_id
            or self.corrects.version >= self.version
            or self.corrects.contract_id != self.contract_id
        ):
            raise ValidationError("زنجیره اصلاح/ابطال صورتحساب معتبر نیست.")
        if self.record_kind == StatutoryRecordKind.CANCELLATION and any(
            value != 0
            for value in (self.taxable_amount, self.tax_amount, self.total_amount)
        ):
            raise ValidationError("صورتحساب ابطالی باید مبالغ صفر داشته باشد.")
        if self.total_amount != self.taxable_amount + self.tax_amount:
            raise ValidationError("جمع صورتحساب با مبلغ مشمول و مالیات هم‌خوان نیست.")
        if self.status == StatutoryRecordStatus.SUBMITTED and (
            not self.submitted_by_id
            or not self.submitted_at
            or not self.preflight_snapshot
        ):
            raise ValidationError("صورتحساب ارسالی باید شواهد preflight داشته باشد.")
        if self.status == StatutoryRecordStatus.APPROVED and (
            not self.approved_by_id or not self.approved_at or not self.decision_reason
        ):
            raise ValidationError("صورتحساب آماده باید شواهد تصمیم داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                StatutoryRecordStatus.APPROVED,
                StatutoryRecordStatus.RETURNED,
                StatutoryRecordStatus.SUPERSEDED,
                StatutoryRecordStatus.CANCELLED,
            }:
                raise ValidationError("سابقه نهایی صورتحساب مؤدیان تغییرناپذیر است.")
            if previous.status == StatutoryRecordStatus.SUBMITTED:
                permitted = {
                    "status",
                    "approved_by_id",
                    "approved_at",
                    "decision_reason",
                    "updated_by_id",
                    "updated_at",
                }
                changed = {
                    field.attname
                    for field in self._meta.concrete_fields
                    if getattr(previous, field.attname) != getattr(self, field.attname)
                }
                if changed - permitted:
                    raise ValidationError(
                        "تصویر preflight صورتحساب ارسالی قابل تغییر نیست."
                    )
        self.reason = self.reason.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        if self.status != StatutoryRecordStatus.DRAFT:
            raise ValidationError("صورتحساب ارسالی یا نهایی‌شده حذف نمی‌شود.")
        return super().delete(*args, **kwargs)


class ContractorComplianceAssessment(UUIDModel, TimeStampedModel):
    """Reviewed-policy contractor insurance fact; it has no AP/GL effect."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="contractor_compliance_assessments",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="contractor_compliance_assessments",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.PROTECT,
        related_name="contractor_compliance_assessments",
    )
    source_certificate = models.OneToOneField(
        PayableCertificate,
        on_delete=models.PROTECT,
        related_name="contractor_compliance_assessment",
    )
    party_identity_snapshot = models.ForeignKey(
        "parties.PartyIdentitySnapshot",
        on_delete=models.PROTECT,
        related_name="contractor_compliance_assessments",
    )
    policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="contractor_compliance_assessments",
    )
    clearance_evidence = models.ForeignKey(
        ContractComplianceEvidence,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contractor_assessments",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    basis_amount = models.DecimalField(max_digits=18, decimal_places=4)
    deduction_rate = models.DecimalField(max_digits=9, decimal_places=6)
    deduction_amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency_code = models.CharField(max_length=3)
    clearance_required = models.BooleanField()
    calculation_snapshot = models.JSONField(default=dict)
    submission_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatutoryRecordStatus.choices,
        default=StatutoryRecordStatus.DRAFT,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contractor_compliance_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contractor_compliance_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contractor_compliance_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contractor_compliance_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start")),
                name="contractor_compliance_period_valid",
            ),
            models.CheckConstraint(
                condition=Q(basis_amount__gte=0)
                & Q(deduction_rate__gte=0)
                & Q(deduction_amount__gte=0),
                name="contractor_compliance_values_nonnegative",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status", "period_end"],
                name="contractor_compliance_work_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            project=self.project,
            contract=self.contract,
            source_certificate=self.source_certificate,
            party_identity_snapshot=self.party_identity_snapshot,
            clearance_evidence=self.clearance_evidence
            if self.clearance_evidence_id
            else None,
        )
        if (
            self.contract.project_id != self.project_id
            or self.source_certificate.contract_id != self.contract_id
            or self.source_certificate.project_id != self.project_id
            or not self.contract.party_id
            or self.party_identity_snapshot.party_id != self.contract.party_id
        ):
            raise ValidationError("دامنه ارزیابی بیمه پیمانکار هم‌راستا نیست.")
        if len(self.currency_code) != 3 or self.period_end < self.period_start:
            raise ValidationError("ارز یا دوره ارزیابی معتبر نیست.")
        if self.clearance_evidence_id and (
            self.clearance_evidence.contract_id != self.contract_id
            or self.clearance_evidence.evidence_kind != ComplianceEvidenceKind.CLEARANCE
            or self.clearance_evidence.status != ComplianceEvidenceStatus.APPROVED
        ):
            raise ValidationError("شاهد مفاصاحساب ارزیابی معتبر نیست.")
        if self.clearance_required and not self.clearance_evidence_id:
            raise ValidationError(
                "سیاست بررسی‌شده برای این ارزیابی مفاصاحساب معتبر می‌خواهد."
            )
        if self.status == StatutoryRecordStatus.SUBMITTED and (
            not self.submitted_by_id
            or not self.submitted_at
            or not self.submission_snapshot
        ):
            raise ValidationError("ارزیابی ارسالی باید تصویر محاسبه داشته باشد.")
        if self.status == StatutoryRecordStatus.APPROVED and (
            not self.approved_by_id or not self.approved_at or not self.decision_reason
        ):
            raise ValidationError("ارزیابی نهایی باید شواهد تصمیم داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                StatutoryRecordStatus.APPROVED,
                StatutoryRecordStatus.RETURNED,
            }:
                raise ValidationError("ارزیابی نهایی بیمه پیمانکار تغییرناپذیر است.")
            if previous.status == StatutoryRecordStatus.SUBMITTED:
                permitted = {
                    "status",
                    "approved_by_id",
                    "approved_at",
                    "decision_reason",
                    "updated_by_id",
                    "updated_at",
                }
                changed = {
                    field.attname
                    for field in self._meta.concrete_fields
                    if getattr(previous, field.attname) != getattr(self, field.attname)
                }
                if changed - permitted:
                    raise ValidationError("تصویر ارزیابی ارسالی قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class StatutorySubmissionStatus(models.TextChoices):
    EXPORTED = "exported", "خروجی ثبت‌شده"
    ACCEPTED = "accepted", "پذیرفته‌شده توسط adapter آزمون"
    REJECTED = "rejected", "ردشده توسط adapter آزمون"
    PROVIDER_ERROR = "provider_error", "خطای adapter/ارائه‌دهنده"


class StatutorySubmissionEvidence(UUIDModel):
    """Append-only export/test-adapter attempt; contains no credentials."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="statutory_submission_evidence",
    )
    taxpayer_invoice = models.ForeignKey(
        TaxpayerInvoice,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="submission_evidence",
    )
    contractor_assessment = models.ForeignKey(
        ContractorComplianceAssessment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="submission_evidence",
    )
    retry_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="retries"
    )
    attempt_number = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=255)
    correlation_id = models.UUIDField()
    schema_identifier = models.CharField(max_length=255)
    provider_key = models.CharField(max_length=120, blank=True)
    request_payload = models.JSONField()
    request_sha256 = models.CharField(max_length=64)
    response_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, choices=StatutorySubmissionStatus.choices)
    provider_reference = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=120, blank=True)
    error_message = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="statutory_submission_evidence_recorded",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="statutory_submission_idempotency_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "correlation_id"],
                name="statutory_submission_correlation_uq",
            ),
            models.UniqueConstraint(
                fields=["taxpayer_invoice", "attempt_number"],
                name="taxpayer_submission_attempt_uq",
            ),
            models.UniqueConstraint(
                fields=["contractor_assessment", "attempt_number"],
                name="contractor_submission_attempt_uq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        taxpayer_invoice__isnull=False,
                        contractor_assessment__isnull=True,
                    )
                    | Q(
                        taxpayer_invoice__isnull=True,
                        contractor_assessment__isnull=False,
                    )
                ),
                name="statutory_submission_exactly_one_target",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status", "recorded_at"],
                name="statutory_submission_queue_idx",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("شاهد خروجی/ارسال تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("شاهد خروجی/ارسال قابل حذف نیست.")


class SubmissionResolutionAction(models.TextChoices):
    RETRY_AUTHORIZED = "retry_authorized", "اجازه تلاش مجدد"
    CLOSED_NO_RETRY = "closed_no_retry", "بسته‌شده بدون تلاش مجدد"
    OUTCOME_NOTED = "outcome_noted", "نتیجه بیرونی ثبت شد"


class StatutorySubmissionResolution(UUIDModel):
    submission = models.ForeignKey(
        StatutorySubmissionEvidence,
        on_delete=models.PROTECT,
        related_name="resolutions",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="statutory_submission_resolutions",
    )
    action = models.CharField(max_length=30, choices=SubmissionResolutionAction.choices)
    note = models.TextField()
    provider_reference = models.CharField(max_length=255, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="statutory_submission_resolutions",
    )
    resolved_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("شاهد حل انسانی تغییرناپذیر است.")
        if (
            self.submission_id
            and self.organization_id != self.submission.organization_id
        ):
            raise ValidationError("حل انسانی و ارسال باید متعلق به یک Tenant باشند.")
        if not self.note.strip():
            raise ValidationError("شرح حل انسانی الزامی است.")
        self.note = self.note.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("شاهد حل انسانی قابل حذف نیست.")


from .variation_models import VariationBillingEligibility  # noqa: F401
