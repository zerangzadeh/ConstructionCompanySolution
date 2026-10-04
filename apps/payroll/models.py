from __future__ import annotations

import hashlib
import json
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

# Django Meta options intentionally use class-level mutable declarations.
# ruff: noqa: RUF012


class DateRangeExpression(models.Func):
    function = "DATERANGE"
    output_field = DateRangeField()


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        raise ValidationError("سابقه قطعی حقوق و دستمزد قابل تغییر نیست.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("سابقه قطعی حقوق و دستمزد قابل حذف نیست.")


class ImmutableManager(models.Manager.from_queryset(ImmutableQuerySet)):
    pass


class ImmutablePayrollRecord(UUIDModel, CreatedAtModel):
    objects = ImmutableManager()

    class Meta:
        abstract = True

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("سابقه قطعی حقوق و دستمزد قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("سابقه قطعی حقوق و دستمزد قابل حذف نیست.")


class PayModel(models.TextChoices):
    SALARIED = "salaried", "حقوق ثابت"
    HOURLY = "hourly", "ساعتی"
    DAILY = "daily", "روزانه"
    PROJECT_LINKED = "project_linked", "وابسته به پروژه"
    OTHER = "other", "سایر تنظیم صریح"


class ConfigurationStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ACTIVE = "active", "فعال"
    RETIRED = "retired", "بازنشسته"


class EmploymentPayConfiguration(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_employment_configurations",
    )
    employee = models.ForeignKey(
        "workforce.Employee",
        on_delete=models.PROTECT,
        related_name="payroll_configurations",
    )
    version = models.PositiveIntegerField()
    predecessor = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successors",
    )
    pay_model = models.CharField(max_length=30, choices=PayModel.choices)
    base_rate = models.DecimalField(max_digits=24, decimal_places=8)
    rate_unit = models.CharField(max_length=40)
    currency = models.CharField(max_length=3, default="IRR")
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_employment_configurations",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_employment_configurations",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ConfigurationStatus.choices,
        default=ConfigurationStatus.DRAFT,
        db_index=True,
    )
    source_reference = models.CharField(max_length=255)
    evidence = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_employment_configurations_created",
    )
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_employment_configurations_activated",
    )
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["employee", "-effective_from", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "employee", "version"],
                name="payroll_emp_config_version_uq",
            ),
            models.CheckConstraint(
                condition=Q(base_rate__gte=0), name="payroll_emp_base_rate_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gte=models.F("effective_from")),
                name="payroll_emp_config_dates_ck",
            ),
            ExclusionConstraint(
                name="payroll_active_emp_config_no_overlap",
                expressions=[
                    ("employee", RangeOperators.EQUAL),
                    (
                        DateRangeExpression(
                            "effective_from",
                            "effective_to",
                            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=Q(
                    status__in=[
                        ConfigurationStatus.ACTIVE,
                        ConfigurationStatus.RETIRED,
                    ]
                ),
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            employee=self.employee if self.employee_id else None,
            predecessor=self.predecessor if self.predecessor_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
        )
        self.currency = self.currency.strip().upper()
        self.rate_unit = self.rate_unit.strip()
        self.source_reference = self.source_reference.strip()
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه انتخاب‌شده باشد."})
        if self.pay_model == PayModel.PROJECT_LINKED and not self.project_id:
            raise ValidationError({"project": "مدل پرداخت پروژه‌ای به پروژه صریح نیاز دارد."})
        if not self.rate_unit or not self.source_reference:
            raise ValidationError("واحد نرخ و مرجع منبع الزامی است.")
        if self.organization_id and self.currency != self.organization.settings.currency:
            raise ValidationError({"currency": "ارز باید با ارز مبنای شرکت یکسان باشد."})
        if self.predecessor_id:
            if self.predecessor.employee_id != self.employee_id:
                raise ValidationError({"predecessor": "نسخه پیشین باید برای همین کارمند باشد."})
            if self.version <= self.predecessor.version:
                raise ValidationError({"version": "شماره نسخه باید از نسخه پیشین بزرگ‌تر باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = EmploymentPayConfiguration.objects.get(pk=self.pk)
            if original.status in {ConfigurationStatus.ACTIVE, ConfigurationStatus.RETIRED}:
                raise ValidationError("نسخه فعال یا بازنشسته قابل ویرایش نیست؛ نسخه جدید بسازید.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class ComponentKind(models.TextChoices):
    EARNING = "earning", "مزدی"
    ALLOWANCE = "allowance", "مزایا"
    DEDUCTION = "deduction", "کسور"
    REIMBURSEMENT = "reimbursement", "بازپرداخت هزینه"
    EMPLOYER = "employer", "سهم کارفرما"
    INFORMATIONAL = "informational", "اطلاعاتی غیرقابل‌پرداخت"


class NetEffect(models.TextChoices):
    ADD = "add", "افزاینده خالص"
    SUBTRACT = "subtract", "کاهنده خالص"
    NONE = "none", "بدون اثر بر خالص"


class PayrollComponent(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_components"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=30, choices=ComponentKind.choices)
    net_effect = models.CharField(max_length=20, choices=NetEffect.choices)
    is_statutory_reserved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_components_created",
    )

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="payroll_component_org_code_uq"
            )
        ]

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("کد و نام جزء حقوق الزامی است.")
        expected = {
            ComponentKind.EARNING: NetEffect.ADD,
            ComponentKind.ALLOWANCE: NetEffect.ADD,
            ComponentKind.DEDUCTION: NetEffect.SUBTRACT,
            ComponentKind.REIMBURSEMENT: NetEffect.ADD,
            ComponentKind.EMPLOYER: NetEffect.NONE,
            ComponentKind.INFORMATIONAL: NetEffect.NONE,
        }[self.kind]
        if self.net_effect != expected:
            raise ValidationError({"net_effect": "اثر خالص با نوع جزء حقوق سازگار نیست."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class RuleStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ACTIVE = "active", "فعال"
    RETIRED = "retired", "بازنشسته"


class CalculationMethod(models.TextChoices):
    FIXED_AMOUNT = "fixed_amount", "مبلغ ثابت"
    QUANTITY_TIMES_RATE = "quantity_times_rate", "مقدار × نرخ"
    PERCENT_OF_COMPONENT = "percent_of_component", "درصد از جزء مبنا"


class RateSource(models.TextChoices):
    RULE = "rule", "نرخ نسخه قاعده"
    EMPLOYMENT = "employment", "نرخ نسخه پیکربندی پرداخت"


class PayrollRule(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_rules"
    )
    component = models.ForeignKey(
        PayrollComponent, on_delete=models.PROTECT, related_name="rules"
    )
    code = models.CharField(max_length=50)
    version = models.PositiveIntegerField()
    predecessor = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors"
    )
    name = models.CharField(max_length=255)
    sequence = models.PositiveIntegerField(default=100)
    method = models.CharField(max_length=30, choices=CalculationMethod.choices)
    fixed_amount = models.DecimalField(
        max_digits=24, decimal_places=8, null=True, blank=True
    )
    rate_source = models.CharField(
        max_length=20, choices=RateSource.choices, default=RateSource.RULE
    )
    rate = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    percentage = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True
    )
    basis_component = models.ForeignKey(
        PayrollComponent,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dependent_rules",
    )
    applicable_pay_models = models.JSONField(default=list, blank=True)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_rules",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_rules",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=RuleStatus.choices, default=RuleStatus.DRAFT, db_index=True
    )
    source_reference = models.CharField(max_length=255)
    evidence = models.JSONField(default=dict, blank=True)
    requires_statutory_authority = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_rules_created",
    )
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_rules_activated",
    )
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sequence", "code", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code", "version"],
                name="payroll_rule_version_uq",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gte=models.F("effective_from")),
                name="payroll_rule_dates_ck",
            ),
            models.CheckConstraint(
                condition=Q(fixed_amount__isnull=True) | Q(fixed_amount__gte=0),
                name="payroll_rule_fixed_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(rate__isnull=True) | Q(rate__gte=0),
                name="payroll_rule_rate_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(percentage__isnull=True) | Q(percentage__gte=0),
                name="payroll_rule_percentage_nonnegative",
            ),
            ExclusionConstraint(
                name="payroll_active_rule_no_overlap",
                expressions=[
                    ("component", RangeOperators.EQUAL),
                    (
                        DateRangeExpression(
                            "effective_from",
                            "effective_to",
                            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=Q(status__in=[RuleStatus.ACTIVE, RuleStatus.RETIRED]),
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            component=self.component if self.component_id else None,
            predecessor=self.predecessor if self.predecessor_id else None,
            basis_component=self.basis_component if self.basis_component_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
        )
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        self.source_reference = self.source_reference.strip()
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه قاعده باشد."})
        invalid_models = set(self.applicable_pay_models) - set(PayModel.values)
        if invalid_models:
            raise ValidationError({"applicable_pay_models": "مدل پرداخت نامعتبر است."})
        if self.method == CalculationMethod.FIXED_AMOUNT:
            if self.fixed_amount is None:
                raise ValidationError({"fixed_amount": "مبلغ ثابت الزامی است."})
        elif self.method == CalculationMethod.QUANTITY_TIMES_RATE:
            if self.rate_source == RateSource.RULE and self.rate is None:
                raise ValidationError({"rate": "نرخ نسخه قاعده الزامی است."})
        elif self.method == CalculationMethod.PERCENT_OF_COMPONENT:
            if self.percentage is None or not self.basis_component_id:
                raise ValidationError("درصد و جزء مبنا الزامی است.")
            if self.basis_component_id == self.component_id:
                raise ValidationError({"basis_component": "جزء نمی‌تواند مبنای خودش باشد."})
        if not self.source_reference:
            raise ValidationError({"source_reference": "مرجع منبع قاعده الزامی است."})
        if self.predecessor_id:
            if self.predecessor.code != self.code:
                raise ValidationError({"predecessor": "نسخه پیشین باید همین کد قاعده را داشته باشد."})
            if self.version <= self.predecessor.version:
                raise ValidationError({"version": "شماره نسخه باید افزایش یابد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = PayrollRule.objects.get(pk=self.pk)
            if original.status in {RuleStatus.ACTIVE, RuleStatus.RETIRED}:
                raise ValidationError("نسخه فعال یا بازنشسته قاعده قابل ویرایش نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class PayrollPeriodStatus(models.TextChoices):
    OPEN = "open", "باز"
    LOCKED = "locked", "قفل‌شده"
    FINALIZED = "finalized", "قطعی"
    CANCELLED = "cancelled", "لغوشده"


class PayrollPeriod(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_periods"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    starts_on = models.DateField()
    ends_on = models.DateField()
    cutoff_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=PayrollPeriodStatus.choices,
        default=PayrollPeriodStatus.OPEN,
        db_index=True,
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payroll_periods_created"
    )

    class Meta:
        ordering = ["-starts_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="payroll_period_org_code_uq"
            ),
            models.CheckConstraint(
                condition=Q(ends_on__gte=models.F("starts_on")),
                name="payroll_period_dates_ck",
            ),
            ExclusionConstraint(
                name="payroll_period_active_no_overlap",
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
                condition=Q(
                    status__in=[
                        PayrollPeriodStatus.OPEN,
                        PayrollPeriodStatus.LOCKED,
                        PayrollPeriodStatus.FINALIZED,
                    ]
                ),
            ),
        ]

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("کد و نام دوره حقوق الزامی است.")
        if self.cutoff_at and self.cutoff_at.tzinfo is None:
            raise ValidationError({"cutoff_at": "زمان قطع ورودی باید timezone-aware باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = PayrollPeriod.objects.get(pk=self.pk)
            if original.status in {PayrollPeriodStatus.LOCKED, PayrollPeriodStatus.FINALIZED}:
                raise ValidationError("دوره قفل یا قطعی‌شده قابل ویرایش نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class PayrollRunKind(models.TextChoices):
    REGULAR = "regular", "عادی"
    OFF_CYCLE = "off_cycle", "خارج از چرخه"
    ADJUSTMENT = "adjustment", "تعدیل/معوقه"
    REVERSAL = "reversal", "برگشت"
    REPLACEMENT = "replacement", "جایگزین"


class PayrollRunStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    INPUTS_LOCKED = "inputs_locked", "ورودی قفل‌شده"
    CALCULATED = "calculated", "محاسبه‌شده"
    EXCEPTION = "exception", "دارای استثنا"
    IN_REVIEW = "in_review", "در بررسی"
    APPROVED = "approved", "تأییدشده"
    FINALIZED = "finalized", "قطعی"
    REVERSED = "reversed", "برگشت‌شده"
    CANCELLED = "cancelled", "لغوشده"


class PayrollRun(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_runs"
    )
    period = models.ForeignKey(
        PayrollPeriod, on_delete=models.PROTECT, related_name="runs"
    )
    code = models.CharField(max_length=60)
    kind = models.CharField(
        max_length=20, choices=PayrollRunKind.choices, default=PayrollRunKind.REGULAR
    )
    status = models.CharField(
        max_length=20, choices=PayrollRunStatus.choices, default=PayrollRunStatus.DRAFT, db_index=True
    )
    idempotency_key = models.CharField(max_length=100)
    predecessor = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor_runs"
    )
    reversal_of = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversal_run"
    )
    replaces = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="replacement_run"
    )
    input_digest = models.CharField(max_length=64, blank=True)
    calculation_digest = models.CharField(max_length=64, blank=True)
    precision_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_precision_evidence",
    )
    rounding_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_rounding_evidence",
    )
    monetary_policy_snapshot = models.JSONField(default=dict, blank=True)
    currency = models.CharField(max_length=3, default="IRR")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payroll_runs_created"
    )
    inputs_locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_runs_locked",
    )
    inputs_locked_at = models.DateTimeField(null=True, blank=True)
    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_runs_calculated",
    )
    calculated_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_runs_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_runs_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_runs_finalized",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="payroll_run_org_code_uq"
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"], name="payroll_run_org_idem_uq"
            ),
            models.UniqueConstraint(
                fields=["period"],
                condition=Q(kind=PayrollRunKind.REGULAR),
                name="payroll_one_regular_run_per_period",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            period=self.period if self.period_id else None,
            predecessor=self.predecessor if self.predecessor_id else None,
            reversal_of=self.reversal_of if self.reversal_of_id else None,
            replaces=self.replaces if self.replaces_id else None,
        )
        self.code = canonicalize_upper_identifier(self.code)
        self.currency = self.currency.strip().upper()
        if self.organization_id and self.currency != self.organization.settings.currency:
            raise ValidationError({"currency": "ارز اجرای حقوق باید ارز مبنای شرکت باشد."})
        if self.kind == PayrollRunKind.REVERSAL and not self.reversal_of_id:
            raise ValidationError({"reversal_of": "اجرای برگشت باید اجرای اصلی را مشخص کند."})
        if self.kind == PayrollRunKind.REPLACEMENT and not self.replaces_id:
            raise ValidationError({"replaces": "اجرای جایگزین باید اجرای اصلی را مشخص کند."})

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = PayrollRun.objects.get(pk=self.pk)
            if original.status in {PayrollRunStatus.FINALIZED, PayrollRunStatus.REVERSED}:
                raise ValidationError("اجرای قطعی قابل ویرایش نیست؛ از برگشت/جایگزین استفاده کنید.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class ResultStatus(models.TextChoices):
    PENDING = "pending", "در انتظار"
    READY = "ready", "آماده"
    EXCEPTION = "exception", "دارای استثنا"
    CALCULATED = "calculated", "محاسبه‌شده"
    FINALIZED = "finalized", "قطعی"
    REVERSED = "reversed", "برگشت‌شده"


class PayrollRunEmployee(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_run_employees"
    )
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="employee_results")
    employee = models.ForeignKey(
        "workforce.Employee", on_delete=models.PROTECT, related_name="payroll_results"
    )
    employment_configuration = models.ForeignKey(
        EmploymentPayConfiguration,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_results",
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True, related_name="payroll_results"
    )
    site = models.ForeignKey(
        "projects.ProjectSite", on_delete=models.PROTECT, null=True, blank=True, related_name="payroll_results"
    )
    status = models.CharField(max_length=20, choices=ResultStatus.choices, default=ResultStatus.PENDING)
    gross_amount = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal(0))
    deduction_amount = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal(0))
    reimbursement_amount = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal(0))
    employer_amount = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal(0))
    informational_amount = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal(0))
    net_amount = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal(0))
    predecessor_result = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor_results"
    )

    class Meta:
        ordering = ["employee"]
        constraints = [
            models.UniqueConstraint(fields=["run", "employee"], name="payroll_run_employee_uq")
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run if self.run_id else None,
            employee=self.employee if self.employee_id else None,
            employment_configuration=(
                self.employment_configuration if self.employment_configuration_id else None
            ),
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
            predecessor_result=self.predecessor_result if self.predecessor_result_id else None,
        )
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError({"site": "کارگاه نتیجه باید متعلق به پروژه نتیجه باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = PayrollRunEmployee.objects.select_related("run").get(pk=self.pk)
            if original.run.status in {PayrollRunStatus.FINALIZED, PayrollRunStatus.REVERSED}:
                raise ValidationError("نتیجه اجرای قطعی قابل ویرایش نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        if self.run.status != PayrollRunStatus.DRAFT:
            raise ValidationError("عضو اجرای قفل‌شده قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class PayrollInputSource(models.TextChoices):
    EXPLICIT = "explicit", "ورودی صریح حقوق"
    APPROVED_TIMESHEET = "approved_timesheet", "کارکرد تأییدشده"
    FINAL_ATTENDANCE = "final_attendance", "حضور قطعی"
    OPENING_BALANCE = "opening_balance", "مانده افتتاحیه صریح"


class PayrollInput(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_inputs"
    )
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="inputs")
    employee = models.ForeignKey(
        "workforce.Employee", on_delete=models.PROTECT, related_name="payroll_inputs"
    )
    rule = models.ForeignKey(PayrollRule, on_delete=models.PROTECT, related_name="inputs")
    quantity = models.DecimalField(max_digits=24, decimal_places=8)
    source_type = models.CharField(max_length=30, choices=PayrollInputSource.choices)
    source_reference = models.CharField(max_length=255)
    source_version = models.CharField(max_length=100)
    source_status = models.CharField(max_length=20)
    source_payload = models.JSONField(default=dict)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True, related_name="payroll_inputs"
    )
    site = models.ForeignKey(
        "projects.ProjectSite", on_delete=models.PROTECT, null=True, blank=True, related_name="payroll_inputs"
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payroll_inputs_recorded"
    )

    class Meta:
        ordering = ["employee", "rule__sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "employee", "rule"], name="payroll_input_run_employee_rule_uq"
            ),
            models.CheckConstraint(condition=Q(quantity__gte=0), name="payroll_input_quantity_nonnegative"),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run if self.run_id else None,
            employee=self.employee if self.employee_id else None,
            rule=self.rule if self.rule_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
        )
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError({"site": "کارگاه ورودی باید متعلق به پروژه باشد."})
        if self.run_id and self.run.status != PayrollRunStatus.DRAFT:
            raise ValidationError("ورودی فقط در اجرای پیش‌نویس قابل ثبت است.")
        if self.rule_id and self.rule.method != CalculationMethod.QUANTITY_TIMES_RATE:
            raise ValidationError({"rule": "فقط قاعده مقدار × نرخ ورودی مقداری می‌پذیرد."})
        if self.source_status not in {"approved", "final"}:
            raise ValidationError({"source_status": "منبع ورودی باید صریحاً تأیید یا قطعی باشد."})
        if not self.source_reference.strip() or not self.source_version.strip():
            raise ValidationError("مرجع و نسخه منبع ورودی الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            original = PayrollInput.objects.select_related("run").get(pk=self.pk)
            if original.run.status != PayrollRunStatus.DRAFT:
                raise ValidationError("ورودی قفل‌شده قابل ویرایش نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        if self.run.status != PayrollRunStatus.DRAFT:
            raise ValidationError("ورودی قفل‌شده قابل حذف نیست.")
        return super().delete(*args, **kwargs)


class AdjustmentKind(models.TextChoices):
    ARREARS = "arrears", "معوقه"
    RETROACTIVE = "retroactive", "تعدیل عطف‌به‌ماسبق"
    OFF_CYCLE = "off_cycle", "خارج از چرخه"
    CORRECTION = "correction", "اصلاح"
    OPENING = "opening", "مانده افتتاحیه"


class PayrollAdjustment(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_adjustments"
    )
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="adjustments")
    employee = models.ForeignKey(
        "workforce.Employee", on_delete=models.PROTECT, related_name="payroll_adjustments"
    )
    component = models.ForeignKey(
        PayrollComponent, on_delete=models.PROTECT, related_name="adjustments"
    )
    original_result = models.ForeignKey(
        PayrollRunEmployee,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="adjustments",
    )
    kind = models.CharField(max_length=20, choices=AdjustmentKind.choices)
    amount = models.DecimalField(max_digits=24, decimal_places=8)
    effective_on = models.DateField()
    source_reference = models.CharField(max_length=255)
    source_payload = models.JSONField(default=dict, blank=True)
    reason = models.TextField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payroll_adjustments_recorded"
    )

    class Meta:
        ordering = ["employee", "created_at"]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run if self.run_id else None,
            employee=self.employee if self.employee_id else None,
            component=self.component if self.component_id else None,
            original_result=self.original_result if self.original_result_id else None,
        )
        if self.run_id and self.run.status != PayrollRunStatus.DRAFT:
            raise ValidationError("تعدیل فقط پیش از قفل ورودی ثبت می‌شود.")
        if self.run_id and self.run.kind not in {
            PayrollRunKind.OFF_CYCLE,
            PayrollRunKind.ADJUSTMENT,
            PayrollRunKind.REPLACEMENT,
        }:
            raise ValidationError({"run": "تعدیل باید در اجرای خارج از چرخه، تعدیلی یا جایگزین باشد."})
        if not self.reason.strip() or not self.source_reference.strip():
            raise ValidationError("دلیل و مرجع منبع تعدیل الزامی است.")
        if self.original_result_id and self.original_result.status not in {
            ResultStatus.FINALIZED,
            ResultStatus.REVERSED,
        }:
            raise ValidationError({"original_result": "مبنای تعدیل باید نتیجه قطعی باشد."})


class PayrollInputSnapshot(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_input_snapshots"
    )
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="input_snapshots")
    run_employee = models.ForeignKey(
        PayrollRunEmployee, on_delete=models.PROTECT, related_name="input_snapshots"
    )
    employment_configuration = models.ForeignKey(
        EmploymentPayConfiguration, on_delete=models.PROTECT, related_name="input_snapshots"
    )
    component = models.ForeignKey(
        PayrollComponent, on_delete=models.PROTECT, related_name="input_snapshots"
    )
    rule = models.ForeignKey(
        PayrollRule, on_delete=models.PROTECT, null=True, blank=True, related_name="input_snapshots"
    )
    adjustment = models.OneToOneField(
        PayrollAdjustment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="snapshot",
    )
    sequence = models.PositiveIntegerField()
    quantity = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    rate = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    basis = models.DecimalField(max_digits=28, decimal_places=8, null=True, blank=True)
    fixed_value = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    rule_version = models.PositiveIntegerField(null=True, blank=True)
    employment_version = models.PositiveIntegerField()
    source_type = models.CharField(max_length=30)
    source_reference = models.CharField(max_length=255)
    source_version = models.CharField(max_length=100)
    source_payload = models.JSONField(default=dict, blank=True)
    snapshot_payload = models.JSONField(default=dict)
    digest = models.CharField(max_length=64)

    class Meta:
        ordering = ["run_employee", "sequence", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["run_employee", "rule"],
                condition=Q(rule__isnull=False),
                name="payroll_snapshot_employee_rule_uq",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run if self.run_id else None,
            run_employee=self.run_employee if self.run_employee_id else None,
            employment_configuration=(
                self.employment_configuration if self.employment_configuration_id else None
            ),
            component=self.component if self.component_id else None,
            rule=self.rule if self.rule_id else None,
            adjustment=self.adjustment if self.adjustment_id else None,
        )
        if bool(self.rule_id) == bool(self.adjustment_id):
            raise ValidationError("هر snapshot باید دقیقاً قاعده یا تعدیل داشته باشد.")


class PayrollResultLine(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_result_lines"
    )
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="result_lines")
    run_employee = models.ForeignKey(
        PayrollRunEmployee, on_delete=models.PROTECT, related_name="lines"
    )
    component = models.ForeignKey(
        PayrollComponent, on_delete=models.PROTECT, related_name="result_lines"
    )
    rule = models.ForeignKey(
        PayrollRule, on_delete=models.PROTECT, null=True, blank=True, related_name="result_lines"
    )
    snapshot = models.ForeignKey(
        PayrollInputSnapshot, on_delete=models.PROTECT, null=True, blank=True, related_name="result_lines"
    )
    sequence = models.PositiveIntegerField()
    component_kind = models.CharField(max_length=30, choices=ComponentKind.choices)
    rule_version = models.PositiveIntegerField(null=True, blank=True)
    basis = models.DecimalField(max_digits=28, decimal_places=8, null=True, blank=True)
    quantity = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    rate = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True)
    unrounded_amount = models.DecimalField(max_digits=28, decimal_places=8)
    amount = models.DecimalField(max_digits=24, decimal_places=2)
    explanation = models.JSONField(default=dict)
    is_reversal = models.BooleanField(default=False)

    class Meta:
        ordering = ["run_employee", "sequence", "created_at"]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run if self.run_id else None,
            run_employee=self.run_employee if self.run_employee_id else None,
            component=self.component if self.component_id else None,
            rule=self.rule if self.rule_id else None,
            snapshot=self.snapshot if self.snapshot_id else None,
        )


class PayrollExceptionSeverity(models.TextChoices):
    ERROR = "error", "خطا"
    WARNING = "warning", "هشدار"


class PayrollException(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_exceptions"
    )
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="exceptions")
    run_employee = models.ForeignKey(
        PayrollRunEmployee,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="exceptions",
    )
    code = models.CharField(max_length=60)
    severity = models.CharField(max_length=20, choices=PayrollExceptionSeverity.choices)
    message = models.TextField()
    details = models.JSONField(default=dict)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_exceptions_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(blank=True)

    class Meta:
        ordering = ["is_resolved", "severity", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "run_employee", "code"],
                condition=Q(is_resolved=False),
                name="payroll_open_exception_uq",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run if self.run_id else None,
            run_employee=self.run_employee if self.run_employee_id else None,
        )


class Payslip(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payslips"
    )
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="payslips")
    run_employee = models.OneToOneField(
        PayrollRunEmployee, on_delete=models.PROTECT, related_name="payslip"
    )
    number = models.CharField(max_length=100)
    issued_at = models.DateTimeField()
    content_digest = models.CharField(max_length=64)
    presentation_snapshot = models.JSONField(default=dict)

    class Meta:
        ordering = ["-issued_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"], name="payroll_payslip_org_number_uq"
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run if self.run_id else None,
            run_employee=self.run_employee if self.run_employee_id else None,
        )

    @staticmethod
    def digest_payload(payload: dict[str, object]) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(serialized.encode()).hexdigest()


class PayrollReversal(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_reversals"
    )
    original_run = models.OneToOneField(
        PayrollRun, on_delete=models.PROTECT, related_name="reversal_record"
    )
    reversal_run = models.OneToOneField(
        PayrollRun, on_delete=models.PROTECT, related_name="reversal_evidence"
    )
    replacement_run = models.OneToOneField(
        PayrollRun,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacement_evidence",
    )
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=100)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payroll_reversals_created"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="payroll_reversal_org_idem_uq",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            original_run=self.original_run if self.original_run_id else None,
            reversal_run=self.reversal_run if self.reversal_run_id else None,
            replacement_run=self.replacement_run if self.replacement_run_id else None,
        )
        if self.original_run_id == self.reversal_run_id:
            raise ValidationError("اجرای برگشت باید رکوردی مستقل باشد.")
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل برگشت الزامی است."})


class StatutoryCalculationKind(models.TextChoices):
    PAYROLL_TAX = "payroll_tax", "مالیات حقوق"
    EMPLOYEE_INSURANCE = "employee_insurance", "بیمه کارکنان"


class StatutoryRecordKind(models.TextChoices):
    ORIGINAL = "original", "اصلی"
    CORRECTION = "correction", "اصلاحی"
    CANCELLATION = "cancellation", "ابطالی"


class StatutoryCalculation(ImmutablePayrollRecord):
    """Immutable, version-pinned derivative of one finalized Payroll run."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_calculations",
    )
    run = models.ForeignKey(
        PayrollRun, on_delete=models.PROTECT, related_name="statutory_calculations"
    )
    kind = models.CharField(max_length=30, choices=StatutoryCalculationKind.choices)
    policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_calculations",
    )
    series_id = models.UUIDField(default=uuid.uuid4, editable=False)
    revision = models.PositiveIntegerField(default=1)
    record_kind = models.CharField(
        max_length=20, choices=StatutoryRecordKind.choices
    )
    corrects = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successors",
    )
    effective_on = models.DateField()
    currency = models.CharField(max_length=3)
    total_basis = models.DecimalField(max_digits=28, decimal_places=8)
    employee_amount = models.DecimalField(max_digits=24, decimal_places=2)
    employer_amount = models.DecimalField(max_digits=24, decimal_places=2)
    other_amount = models.DecimalField(max_digits=24, decimal_places=2)
    policy_snapshot = models.JSONField()
    source_snapshot = models.JSONField()
    monetary_policy_snapshot = models.JSONField()
    content_digest = models.CharField(max_length=64)
    reason = models.TextField()
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_statutory_calculations_prepared",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "series_id", "revision"],
                name="payroll_statutory_series_revision_uq",
            ),
            models.UniqueConstraint(
                fields=["run", "kind"],
                condition=Q(record_kind=StatutoryRecordKind.ORIGINAL),
                name="payroll_statutory_original_run_kind_uq",
            ),
            models.CheckConstraint(
                condition=Q(total_basis__gte=0)
                & Q(employee_amount__gte=0)
                & Q(employer_amount__gte=0)
                & Q(other_amount__gte=0),
                name="payroll_statutory_amounts_nonnegative",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run if self.run_id else None,
            corrects=self.corrects if self.corrects_id else None,
        )
        if self.run_id and self.run.status != PayrollRunStatus.FINALIZED:
            raise ValidationError("فقط اجرای قطعی حقوق منبع محاسبه مقرراتی است.")
        if self.record_kind == StatutoryRecordKind.ORIGINAL:
            if self.corrects_id or self.revision != 1:
                raise ValidationError("سابقه اصلی نباید مبنای اصلاح داشته باشد.")
        elif (
            not self.corrects_id
            or self.corrects.series_id != self.series_id
            or self.corrects.kind != self.kind
            or self.corrects.revision >= self.revision
        ):
            raise ValidationError("زنجیره اصلاح/ابطال محاسبه مقرراتی معتبر نیست.")
        if self.record_kind == StatutoryRecordKind.CANCELLATION and any(
            value != 0
            for value in (
                self.total_basis,
                self.employee_amount,
                self.employer_amount,
                self.other_amount,
            )
        ):
            raise ValidationError("سابقه ابطالی باید مبالغ صفر داشته باشد.")
        if not self.reason.strip() or len(self.currency) != 3:
            raise ValidationError("دلیل و ارز محاسبه مقرراتی الزامی است.")


class StatutoryEmployeeResult(ImmutablePayrollRecord):
    calculation = models.ForeignKey(
        StatutoryCalculation, on_delete=models.PROTECT, related_name="employee_results"
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_employee_results",
    )
    run_employee = models.ForeignKey(
        PayrollRunEmployee,
        on_delete=models.PROTECT,
        related_name="statutory_results",
    )
    basis_amount = models.DecimalField(max_digits=28, decimal_places=8)
    work_days = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    employee_amount = models.DecimalField(max_digits=24, decimal_places=2)
    employer_amount = models.DecimalField(max_digits=24, decimal_places=2)
    other_amount = models.DecimalField(max_digits=24, decimal_places=2)
    calculation_snapshot = models.JSONField()
    source_digest = models.CharField(max_length=64)

    class Meta:
        ordering = ["run_employee__employee"]
        constraints = [
            models.UniqueConstraint(
                fields=["calculation", "run_employee"],
                name="payroll_statutory_employee_result_uq",
            ),
            models.CheckConstraint(
                condition=Q(basis_amount__gte=0)
                & Q(employee_amount__gte=0)
                & Q(employer_amount__gte=0)
                & Q(other_amount__gte=0),
                name="payroll_statutory_employee_nonnegative",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            calculation=self.calculation if self.calculation_id else None,
            run_employee=self.run_employee if self.run_employee_id else None,
        )
        if (
            self.calculation_id
            and self.run_employee_id
            and self.calculation.run_id != self.run_employee.run_id
        ):
            raise ValidationError("نتیجه قانونی باید از همان اجرای حقوق باشد.")


class StatutoryCalculationLine(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_calculation_lines",
    )
    employee_result = models.ForeignKey(
        StatutoryEmployeeResult, on_delete=models.PROTECT, related_name="lines"
    )
    component = models.ForeignKey(
        PayrollComponent,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="statutory_lines",
    )
    line_code = models.CharField(max_length=100)
    classification = models.CharField(max_length=40)
    payer = models.CharField(max_length=20, blank=True)
    basis_amount = models.DecimalField(max_digits=28, decimal_places=8)
    rate = models.DecimalField(max_digits=18, decimal_places=10, null=True, blank=True)
    unrounded_amount = models.DecimalField(max_digits=28, decimal_places=8)
    amount = models.DecimalField(max_digits=24, decimal_places=2)
    evidence = models.JSONField()

    class Meta:
        ordering = ["employee_result", "created_at"]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            employee_result=self.employee_result if self.employee_result_id else None,
            component=self.component if self.component_id else None,
        )


class StatutoryReviewDisposition(models.TextChoices):
    ACCEPTED = "accepted", "پذیرفته"
    REJECTED = "rejected", "ردشده"


class StatutoryReviewEvidence(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_reviews",
    )
    calculation = models.OneToOneField(
        StatutoryCalculation, on_delete=models.PROTECT, related_name="review"
    )
    disposition = models.CharField(
        max_length=20, choices=StatutoryReviewDisposition.choices
    )
    reason = models.TextField()
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_statutory_reviews",
    )
    reviewed_at = models.DateTimeField()

    def clean(self) -> None:
        validate_related_organizations(
            self, calculation=self.calculation if self.calculation_id else None
        )
        if not self.reason.strip():
            raise ValidationError("دلیل بررسی الزامی است.")


class StatutoryIdentitySubject(models.TextChoices):
    EMPLOYER = "employer", "کارفرما/کارگاه"
    EMPLOYEE = "employee", "کارمند"


class StatutoryIdentityEvidence(ImmutablePayrollRecord):
    """Versioned tenant identity values only when an official schema names them."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_identity_evidence",
    )
    employee = models.ForeignKey(
        "workforce.Employee",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="statutory_identity_evidence",
    )
    subject = models.CharField(max_length=20, choices=StatutoryIdentitySubject.choices)
    kind = models.CharField(max_length=30, choices=StatutoryCalculationKind.choices)
    schema_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_identity_evidence",
    )
    version = models.PositiveIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    identifiers = models.JSONField()
    source_reference = models.CharField(max_length=500)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successors",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_statutory_identity_evidence_recorded",
    )

    class Meta:
        ordering = ["kind", "subject", "-effective_from", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "kind", "version"],
                condition=Q(subject=StatutoryIdentitySubject.EMPLOYER),
                name="payroll_statutory_employer_identity_version_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "employee", "kind", "version"],
                condition=Q(subject=StatutoryIdentitySubject.EMPLOYEE),
                name="payroll_statutory_employee_identity_version_uq",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gt=models.F("effective_from")),
                name="payroll_statutory_identity_dates_ck",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            employee=self.employee if self.employee_id else None,
            supersedes=self.supersedes if self.supersedes_id else None,
        )
        if self.subject == StatutoryIdentitySubject.EMPLOYER and self.employee_id:
            raise ValidationError("هویت کارفرما/کارگاه نباید کارمند داشته باشد.")
        if self.subject == StatutoryIdentitySubject.EMPLOYEE and not self.employee_id:
            raise ValidationError("هویت کارمند باید کارمند را مشخص کند.")
        if not isinstance(self.identifiers, dict) or not self.identifiers:
            raise ValidationError("شناسه‌های رسمی باید صریح و غیرخالی باشند.")
        if any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(value, str)
            or not value.strip()
            for key, value in self.identifiers.items()
        ):
            raise ValidationError("کلید و مقدار شناسه رسمی باید رشته غیرخالی باشد.")
        if not self.source_reference.strip():
            raise ValidationError("مرجع منبع شناسه رسمی الزامی است.")
        if self.supersedes_id and (
            self.supersedes.kind != self.kind
            or self.supersedes.subject != self.subject
            or self.supersedes.employee_id != self.employee_id
            or self.supersedes.version >= self.version
        ):
            raise ValidationError("زنجیره نسخه هویت مقرراتی معتبر نیست.")


class StatutoryOutput(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_outputs",
    )
    calculation = models.OneToOneField(
        StatutoryCalculation, on_delete=models.PROTECT, related_name="output"
    )
    schema_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_outputs",
    )
    output_identifier = models.CharField(max_length=150)
    series_id = models.UUIDField(default=uuid.uuid4, editable=False)
    revision = models.PositiveIntegerField(default=1)
    record_kind = models.CharField(
        max_length=20, choices=StatutoryRecordKind.choices
    )
    corrects = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successors",
    )
    schema_identifier = models.CharField(max_length=255)
    schema_snapshot = models.JSONField()
    payload = models.JSONField()
    content_digest = models.CharField(max_length=64)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_statutory_outputs_generated",
    )
    generated_at = models.DateTimeField()

    class Meta:
        ordering = ["-generated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "output_identifier"],
                name="payroll_statutory_output_identifier_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "series_id", "revision"],
                name="payroll_statutory_output_series_revision_uq",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            calculation=self.calculation if self.calculation_id else None,
            corrects=self.corrects if self.corrects_id else None,
        )
        if self.record_kind == StatutoryRecordKind.ORIGINAL:
            if self.corrects_id or self.revision != 1:
                raise ValidationError("خروجی اصلی نباید مبنای اصلاح داشته باشد.")
        elif (
            not self.corrects_id
            or self.corrects.series_id != self.series_id
            or self.corrects.revision >= self.revision
        ):
            raise ValidationError("زنجیره اصلاح/ابطال خروجی معتبر نیست.")


class StatutoryExportStatus(models.TextChoices):
    EXPORTED = "exported", "خروجی ثبت شد"
    MANUALLY_ACCEPTED = "manually_accepted", "پذیرش دستی ثبت شد"
    REJECTED = "rejected", "رد شد"
    PROVIDER_ERROR = "provider_error", "خطای ارائه‌دهنده ثبت شد"


class StatutoryExportEvidence(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_export_evidence",
    )
    output = models.ForeignKey(
        StatutoryOutput, on_delete=models.PROTECT, related_name="export_evidence"
    )
    retry_of = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="retries"
    )
    attempt_number = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=255)
    correlation_id = models.CharField(max_length=255)
    status = models.CharField(max_length=30, choices=StatutoryExportStatus.choices)
    artifact_name = models.CharField(max_length=255)
    artifact_media_type = models.CharField(max_length=120)
    artifact_digest = models.CharField(max_length=64)
    artifact_snapshot = models.JSONField()
    provider_reference = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=120, blank=True)
    error_message = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_statutory_exports_recorded",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="payroll_statutory_export_idem_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "correlation_id"],
                name="payroll_statutory_export_correlation_uq",
            ),
            models.UniqueConstraint(
                fields=["output", "attempt_number"],
                name="payroll_statutory_export_attempt_uq",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            output=self.output if self.output_id else None,
            retry_of=self.retry_of if self.retry_of_id else None,
        )
        if self.retry_of_id and self.retry_of.output_id != self.output_id:
            raise ValidationError("تلاش مجدد باید برای همان خروجی باشد.")
        if self.status in {
            StatutoryExportStatus.REJECTED,
            StatutoryExportStatus.PROVIDER_ERROR,
        } and not self.error_message.strip():
            raise ValidationError("شاهد رد/خطا باید شرح خطا داشته باشد.")


class StatutoryResolutionAction(models.TextChoices):
    RETRY_AUTHORIZED = "retry_authorized", "تلاش مجدد مجاز شد"
    CLOSED = "closed", "بسته شد"
    OUTCOME_RECORDED = "outcome_recorded", "نتیجه ثبت شد"


class StatutorySubmissionResolution(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_resolutions",
    )
    export_evidence = models.ForeignKey(
        StatutoryExportEvidence, on_delete=models.PROTECT, related_name="resolutions"
    )
    action = models.CharField(max_length=30, choices=StatutoryResolutionAction.choices)
    note = models.TextField()
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_statutory_resolutions",
    )

    def clean(self) -> None:
        validate_related_organizations(
            self,
            export_evidence=self.export_evidence if self.export_evidence_id else None,
        )
        if not self.note.strip():
            raise ValidationError("شرح تعیین تکلیف انسانی الزامی است.")


class StatutoryReconciliationStatus(models.TextChoices):
    MATCHED = "matched", "تطبیق کامل"
    EXCEPTION = "exception", "دارای مغایرت"


class StatutoryReconciliation(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_statutory_reconciliations",
    )
    output = models.OneToOneField(
        StatutoryOutput, on_delete=models.PROTECT, related_name="reconciliation"
    )
    calculation_total = models.DecimalField(max_digits=24, decimal_places=2)
    output_total = models.DecimalField(max_digits=24, decimal_places=2)
    difference = models.DecimalField(max_digits=24, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=StatutoryReconciliationStatus.choices
    )
    evidence = models.JSONField()
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_statutory_reconciliations",
    )

    def clean(self) -> None:
        validate_related_organizations(
            self, output=self.output if self.output_id else None
        )
        if self.difference != self.output_total - self.calculation_total:
            raise ValidationError("اختلاف تطبیق با جمع‌های ثبت‌شده هم‌خوان نیست.")
        expected = (
            StatutoryReconciliationStatus.MATCHED
            if self.difference == 0
            else StatutoryReconciliationStatus.EXCEPTION
        )
        if self.status != expected:
            raise ValidationError("وضعیت تطبیق با اختلاف ثبت‌شده هم‌خوان نیست.")


class FinancialHandoffFamily(models.TextChoices):
    LIABILITY = "liability", "پیشنهاد بدهی / AP"
    ACCOUNTING = "accounting", "پیشنهاد منبع حسابداری"
    PAYMENT = "payment", "پیشنهاد پرداخت خزانه"
    PROJECT_COST = "project_cost", "پیشنهاد هزینه کار پروژه"


class FinancialHandoffRecordKind(models.TextChoices):
    ORIGINAL = "original", "اصلی"
    CORRECTION = "correction", "اصلاحی"
    REVERSAL = "reversal", "برگشتی"
    REPLACEMENT = "replacement", "جایگزین"


class FinancialHandoffProposal(ImmutablePayrollRecord):
    """Immutable Payroll proposal; it is never a downstream financial record."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_financial_handoffs"
    )
    family = models.CharField(max_length=20, choices=FinancialHandoffFamily.choices)
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="financial_handoffs")
    record_kind = models.CharField(max_length=20, choices=FinancialHandoffRecordKind.choices)
    predecessor = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors"
    )
    idempotency_key = models.CharField(max_length=120)
    source_digest = models.CharField(max_length=64)
    currency = models.CharField(max_length=3)
    precision_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion", on_delete=models.PROTECT,
        related_name="payroll_handoff_precision_evidence",
    )
    rounding_policy_version = models.ForeignKey(
        "organizations.PlatformPolicyVersion", on_delete=models.PROTECT,
        related_name="payroll_handoff_rounding_evidence",
    )
    monetary_policy_snapshot = models.JSONField()
    proposed_accounting_date = models.DateField(null=True, blank=True)
    mapping_reference = models.CharField(max_length=255, blank=True)
    total_amount = models.DecimalField(max_digits=24, decimal_places=2)
    allocated_amount = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal(0))
    unallocated_amount = models.DecimalField(max_digits=24, decimal_places=2, default=Decimal(0))
    has_exceptions = models.BooleanField(default=False)
    exception_codes = models.JSONField(default=list, blank=True)
    source_snapshot = models.JSONField()
    reason = models.TextField()
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payroll_financial_handoffs_prepared"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "family", "idempotency_key"], name="payroll_handoff_org_family_idem_uq"),
            models.UniqueConstraint(fields=["organization", "family", "run"], name="payroll_handoff_org_family_run_uq"),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            run=self.run if self.run_id else None,
            predecessor=self.predecessor if self.predecessor_id else None,
        )
        if self.run_id and self.run.status != PayrollRunStatus.FINALIZED:
            raise ValidationError("فقط اجرای قطعی حقوق منبع تحویل مالی است.")
        if self.predecessor_id and self.predecessor.family != self.family:
            raise ValidationError("خانواده سابقه پیشین با پیشنهاد سازگار نیست.")
        if self.record_kind == FinancialHandoffRecordKind.ORIGINAL and self.predecessor_id:
            raise ValidationError("پیشنهاد اصلی سابقه پیشین ندارد.")
        if self.record_kind != FinancialHandoffRecordKind.ORIGINAL and not self.predecessor_id:
            raise ValidationError("اصلاح، برگشت یا جایگزین باید سابقه پیشین داشته باشد.")
        if self.allocated_amount + self.unallocated_amount != self.total_amount:
            raise ValidationError("جمع مبلغ تخصیص‌یافته و تخصیص‌نیافته باید با مبلغ کل برابر باشد.")
        if not self.reason.strip() or not self.idempotency_key.strip():
            raise ValidationError("دلیل و کلید تکرارناپذیری الزامی است.")


class FinancialHandoffLine(ImmutablePayrollRecord):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payroll_financial_handoff_lines"
    )
    proposal = models.ForeignKey(FinancialHandoffProposal, on_delete=models.PROTECT, related_name="lines")
    run_employee = models.ForeignKey(PayrollRunEmployee, on_delete=models.PROTECT, related_name="financial_handoff_lines")
    employee = models.ForeignKey("workforce.Employee", on_delete=models.PROTECT, related_name="payroll_financial_handoff_lines")
    result_line = models.ForeignKey(PayrollResultLine, on_delete=models.PROTECT, null=True, blank=True, related_name="financial_handoff_lines")
    statutory_result = models.ForeignKey(StatutoryEmployeeResult, on_delete=models.PROTECT, null=True, blank=True, related_name="financial_handoff_lines")
    timesheet = models.ForeignKey("timekeeping.Timesheet", on_delete=models.PROTECT, null=True, blank=True, related_name="payroll_financial_handoff_lines")
    timesheet_entry = models.ForeignKey("timekeeping.TimesheetEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="payroll_financial_handoff_lines")
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, null=True, blank=True, related_name="payroll_labor_cost_proposal_lines")
    site = models.ForeignKey("projects.ProjectSite", on_delete=models.PROTECT, null=True, blank=True, related_name="payroll_labor_cost_proposal_lines")
    activity = models.ForeignKey("projects.Activity", on_delete=models.PROTECT, null=True, blank=True, related_name="payroll_labor_cost_proposal_lines")
    line_kind = models.CharField(max_length=40)
    payee_reference = models.CharField(max_length=255, blank=True)
    component_reference = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=24, decimal_places=2)
    allocation_minutes = models.PositiveIntegerField(null=True, blank=True)
    source_lineage = models.JSONField()
    content_digest = models.CharField(max_length=64)

    class Meta:
        ordering = ["proposal", "employee", "created_at"]
        constraints = [models.UniqueConstraint(fields=["proposal", "content_digest"], name="payroll_handoff_line_digest_uq")]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            proposal=self.proposal if self.proposal_id else None,
            run_employee=self.run_employee if self.run_employee_id else None,
            employee=self.employee if self.employee_id else None,
            result_line=self.result_line if self.result_line_id else None,
            statutory_result=self.statutory_result if self.statutory_result_id else None,
            timesheet=self.timesheet if self.timesheet_id else None,
            timesheet_entry=self.timesheet_entry if self.timesheet_entry_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
            activity=self.activity if self.activity_id else None,
        )
        if self.proposal_id and self.run_employee.run_id != self.proposal.run_id:
            raise ValidationError("ردیف تحویل باید متعلق به همان اجرای حقوق باشد.")
        if self.employee_id != self.run_employee.employee_id:
            raise ValidationError("کارمند ردیف با نتیجه حقوق سازگار نیست.")
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError("کارگاه ردیف باید متعلق به پروژه باشد.")
        if self.activity_id and self.activity.project_id != self.project_id:
            raise ValidationError("فعالیت ردیف باید متعلق به پروژه باشد.")


class FinancialHandoffReview(ImmutablePayrollRecord):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    proposal = models.OneToOneField(FinancialHandoffProposal, on_delete=models.PROTECT, related_name="review")
    disposition = models.CharField(max_length=20, choices=(("accepted", "پذیرفته"), ("rejected", "ردشده")))
    reason = models.TextField()
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField()

    def clean(self) -> None:
        validate_related_organizations(self, proposal=self.proposal if self.proposal_id else None)
        if self.disposition == "accepted" and self.proposal.has_exceptions:
            raise ValidationError("پیشنهاد دارای استثنا قابل پذیرش نیست.")


class FinancialHandoffAcknowledgement(ImmutablePayrollRecord):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    proposal = models.ForeignKey(FinancialHandoffProposal, on_delete=models.PROTECT, related_name="acknowledgements")
    downstream_reference = models.CharField(max_length=255)
    downstream_status = models.CharField(max_length=40)
    acknowledged_source_digest = models.CharField(max_length=64)
    acknowledged_amount = models.DecimalField(max_digits=24, decimal_places=2)
    evidence = models.JSONField(default=dict, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["proposal", "downstream_reference"], name="payroll_handoff_ack_reference_uq")]

    def clean(self) -> None:
        validate_related_organizations(self, proposal=self.proposal if self.proposal_id else None)
        if not self.downstream_reference.strip():
            raise ValidationError("مرجع دریافت پایین‌دست الزامی است.")


class FinancialHandoffReconciliation(ImmutablePayrollRecord):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    proposal = models.ForeignKey(FinancialHandoffProposal, on_delete=models.PROTECT, related_name="reconciliations")
    acknowledgement = models.ForeignKey(FinancialHandoffAcknowledgement, on_delete=models.PROTECT, null=True, blank=True, related_name="reconciliations")
    status = models.CharField(max_length=20, choices=(("matched", "منطبق"), ("exception", "استثنا")))
    issue_codes = models.JSONField(default=list, blank=True)
    expected_amount = models.DecimalField(max_digits=24, decimal_places=2)
    observed_amount = models.DecimalField(max_digits=24, decimal_places=2, null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payroll_handoff_reconciliations_prepared")

    def clean(self) -> None:
        validate_related_organizations(
            self,
            proposal=self.proposal if self.proposal_id else None,
            acknowledgement=self.acknowledgement if self.acknowledgement_id else None,
        )
        if self.acknowledgement_id and self.acknowledgement.proposal_id != self.proposal_id:
            raise ValidationError("شاهد دریافت با پیشنهاد تطبیق سازگار نیست.")
        if self.status == "matched" and self.issue_codes:
            raise ValidationError("تطبیق موفق نباید کد استثنا داشته باشد.")


class FinancialHandoffReconciliationReview(ImmutablePayrollRecord):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    reconciliation = models.OneToOneField(FinancialHandoffReconciliation, on_delete=models.PROTECT, related_name="review")
    disposition = models.CharField(max_length=20, choices=(("accepted", "پذیرفته"), ("rejected", "ردشده")))
    reason = models.TextField()
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reviewed_at = models.DateTimeField()

    def clean(self) -> None:
        validate_related_organizations(self, reconciliation=self.reconciliation if self.reconciliation_id else None)
