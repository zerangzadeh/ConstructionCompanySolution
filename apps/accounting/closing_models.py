"""Accounting-owned year-end configuration, linkage and append-only evidence."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class ClosingStatus(models.TextChoices):
    PREPARED = "prepared", "در انتظار تأیید بستن"
    CANCELLED = "cancelled", "درخواست پس گرفته شده"
    CLOSED = "closed", "سال بسته؛ در انتظار افتتاحیه"
    ROLLED_FORWARD = "rolled_forward", "افتتاحیه پذیرفته و تطبیق شده"
    REVERSED = "reversed", "برگشت و بازگشایی شده"


class FiscalClosingConfiguration(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    fiscal_year = models.ForeignKey(
        "accounting.FiscalYear",
        on_delete=models.PROTECT,
        related_name="closing_configurations",
    )
    version = models.PositiveIntegerField(default=1)
    result_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.PROTECT,
        related_name="year_end_result_configurations",
    )
    retained_account = models.ForeignKey(
        "accounting.Account",
        on_delete=models.PROTECT,
        related_name="retained_earnings_configurations",
    )
    configured_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    reason = models.TextField()

    class Meta:
        ordering = ["-version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["fiscal_year", "version"], name="year_end_configuration_version"
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            fiscal_year=self.fiscal_year,
            result_account=self.result_account,
            retained_account=self.retained_account,
            configured_by=self.configured_by,
        )
        if (
            self.result_account_id == self.retained_account_id
            or not self.reason.strip()
        ):
            raise ValidationError(
                "حساب نتیجه و سود انباشته باید متمایز و دلیل ثبت شود."
            )
        for account in (self.result_account, self.retained_account):
            if (
                account.account_type != "equity"
                or not account.is_posting
                or account.archived_at
            ):
                raise ValidationError(
                    "حساب نتیجه و سود انباشته باید حساب برگ فعال حقوق مالکانه باشند."
                )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("تنظیمات بستن سال تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("تنظیمات بستن سال قابل حذف نیست.")


class FiscalYearClosing(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    source_year = models.ForeignKey(
        "accounting.FiscalYear",
        on_delete=models.PROTECT,
        related_name="year_end_closings",
    )
    target_year = models.ForeignKey(
        "accounting.FiscalYear",
        on_delete=models.PROTECT,
        related_name="incoming_year_end_closings",
    )
    configuration = models.ForeignKey(
        FiscalClosingConfiguration, on_delete=models.PROTECT
    )
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20, choices=ClosingStatus.choices, default=ClosingStatus.PREPARED
    )
    cutoff_date = models.DateField()
    initiated_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="year_end_initiated",
    )
    close_approved_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="year_end_approved",
    )
    opening_approved_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="year_end_openings_approved",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    rolled_forward_at = models.DateTimeField(null=True, blank=True)
    closing_journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fiscal_closing",
    )
    opening_journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fiscal_opening",
    )
    closing_reversal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fiscal_closing_reversal",
    )
    opening_reversal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fiscal_opening_reversal",
    )
    source_snapshot = models.JSONField()
    final_snapshot = models.JSONField(default=dict, blank=True)
    reconciliation = models.JSONField(default=dict, blank=True)
    annual_result = models.DecimalField(max_digits=24, decimal_places=6)
    reason = models.TextField()

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["source_year", "version"], name="year_end_unique_version"
            ),
            models.UniqueConstraint(
                fields=["source_year"],
                condition=~Q(status__in=["reversed", "cancelled"]),
                name="year_end_active_source",
            ),
            models.UniqueConstraint(
                fields=["target_year"],
                condition=~Q(status__in=["reversed", "cancelled"]),
                name="year_end_active_target",
            ),
            models.CheckConstraint(
                condition=~Q(initiated_by=models.F("close_approved_by")),
                name="year_end_close_independent",
            ),
            models.CheckConstraint(
                condition=~Q(initiated_by=models.F("opening_approved_by")),
                name="year_end_opening_independent",
            ),
            models.CheckConstraint(
                condition=~Q(source_year=models.F("target_year")),
                name="year_end_distinct_years",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1), name="year_end_positive_version"
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=["prepared", "cancelled"],
                    closing_journal__isnull=True,
                    close_approved_by__isnull=True,
                    closed_at__isnull=True,
                    opening_journal__isnull=True,
                )
                | Q(
                    status__in=["closed", "rolled_forward", "reversed"],
                    close_approved_by__isnull=False,
                    closed_at__isnull=False,
                ),
                name="year_end_close_state",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["prepared", "cancelled"])
                | Q(closing_journal__isnull=False)
                | Q(
                    source_snapshot__has_key="nominal_balance_count",
                    source_snapshot__nominal_balance_count=0,
                    annual_result=0,
                ),
                name="year_end_closing_entry_required",
            ),
            models.CheckConstraint(
                condition=~Q(status="rolled_forward")
                | Q(
                    opening_approved_by__isnull=False,
                    rolled_forward_at__isnull=False,
                ),
                name="year_end_opening_state",
            ),
            models.CheckConstraint(
                condition=~Q(status="rolled_forward")
                | Q(opening_journal__isnull=False)
                | Q(final_snapshot__has_key="balances", final_snapshot__balances=[]),
                name="year_end_opening_entry_required",
            ),
            models.CheckConstraint(
                condition=~Q(status="reversed")
                | Q(closing_reversal__isnull=False)
                | Q(closing_journal__isnull=True),
                name="year_end_reversal_state",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            source_year=self.source_year,
            target_year=self.target_year,
            configuration=self.configuration,
            initiated_by=self.initiated_by,
        )
        if (
            self.configuration.fiscal_year_id != self.source_year_id
            or self.cutoff_date != self.source_year.ends_on
        ):
            raise ValidationError("تنظیمات و تاریخ برش باید با سال مبدأ یکسان باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("پرونده بستن سال فقط از خدمت حاکم‌شده تغییر می‌کند.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("سابقه بستن سال قابل حذف نیست.")


class FiscalYearClosingEvent(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    closing = models.ForeignKey(
        FiscalYearClosing, on_delete=models.PROTECT, related_name="events"
    )
    sequence = models.PositiveIntegerField()
    actor = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    reason = models.TextField()
    evidence = models.JSONField()
    evidence_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["sequence"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["closing", "sequence"], name="year_end_event_sequence"
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("سابقه بستن سال تغییرناپذیر است.")
        validate_related_organizations(self, closing=self.closing, actor=self.actor)
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("سابقه بستن سال قابل حذف نیست.")
