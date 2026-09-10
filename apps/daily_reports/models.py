from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class DailyReportStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأییدشده"


class DailyReport(UUIDModel, TimeStampedModel):
    """An operational report for one project on one reporting date."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="daily_reports",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.CASCADE,
        related_name="daily_reports",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        verbose_name="کارگاه",
        on_delete=models.PROTECT,
        related_name="daily_reports",
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        verbose_name="فاز پروژه",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_reports",
    )
    reporting_date = models.DateField("تاریخ گزارش")
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=DailyReportStatus.choices,
        default=DailyReportStatus.DRAFT,
        db_index=True,
    )
    weather_conditions = models.CharField("شرایط آب‌وهوا", max_length=255, blank=True)
    labor_count = models.PositiveIntegerField("تعداد نیروی انسانی", default=0)
    work_performed = models.TextField("کارهای انجام‌شده")
    progress_summary = models.TextField("خلاصه پیشرفت", blank=True)
    issues_and_delays = models.TextField("مسائل و تأخیرها", blank=True)
    safety_notes = models.TextField("یادداشت‌های ایمنی", blank=True)
    quality_notes = models.TextField("یادداشت‌های کیفیت", blank=True)
    submitted_at = models.DateTimeField("زمان ارسال", null=True, blank=True)
    approved_at = models.DateTimeField("زمان تأیید", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تأییدکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_reports_approved",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_reports_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_reports_updated",
    )

    class Meta:
        verbose_name = "گزارش روزانه"
        verbose_name_plural = "گزارش‌های روزانه"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "site", "reporting_date"],
                name="daily_report_org_site_date_uq",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "reporting_date"],
                name="daily_report_org_date_idx",
            ),
            models.Index(
                fields=["organization", "status"],
                name="daily_report_org_status_idx",
            ),
            models.Index(
                fields=["organization", "phase", "reporting_date"],
                name="dailyrep_org_phase_date_idx",
            ),
        ]
        ordering = ["-reporting_date", "-created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.site} - {self.reporting_date}"

    def clean(self) -> None:
        super().clean()
        relations = {}
        if self.project_id:
            relations["project"] = self.project
        if self.site_id:
            relations["site"] = self.site
        if self.phase_id:
            relations["phase"] = self.phase
        validate_related_organizations(self, **relations)
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError(
                {"site": "کارگاه باید متعلق به پروژه انتخاب‌شده باشد."}
            )
        if self.phase_id and self.phase.site_id != self.site_id:
            raise ValidationError(
                {"phase": "فاز باید متعلق به کارگاه انتخاب‌شده باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class DailyReportLaborEntry(UUIDModel, CreatedAtModel):
    """Labor recorded against a daily report while it is still a draft."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="daily_report_labor_entries",
    )
    report = models.ForeignKey(
        DailyReport,
        verbose_name="گزارش روزانه",
        on_delete=models.CASCADE,
        related_name="labor_entries",
    )
    team_name = models.CharField("نام گروه کاری", max_length=120)
    worker_count = models.PositiveIntegerField("تعداد نیرو")
    hours_worked = models.DecimalField("ساعات کارکرد", max_digits=8, decimal_places=2)
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_report_labor_entries_created",
    )

    class Meta:
        verbose_name = "رکورد نیروی انسانی گزارش روزانه"
        verbose_name_plural = "رکوردهای نیروی انسانی گزارش روزانه"
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "report"],
                name="daily_labor_org_report_idx",
            ),
        ]
        ordering = ["created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.team_name} ({self.worker_count})"

    def clean(self) -> None:
        super().clean()
        if self.report_id:
            validate_related_organizations(self, report=self.report)

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class DailyReportEquipmentEntry(UUIDModel, CreatedAtModel):
    """Equipment usage recorded against a daily report draft."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="daily_report_equipment_entries",
    )
    report = models.ForeignKey(
        DailyReport,
        verbose_name="گزارش روزانه",
        on_delete=models.CASCADE,
        related_name="equipment_entries",
    )
    equipment_name = models.CharField("نام تجهیز", max_length=255)
    hours_used = models.DecimalField("ساعات کارکرد", max_digits=8, decimal_places=2)
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_report_equipment_entries_created",
    )

    class Meta:
        verbose_name = "رکورد تجهیز گزارش روزانه"
        verbose_name_plural = "رکوردهای تجهیزات گزارش روزانه"
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "report"],
                name="daily_equipment_org_report_idx",
            ),
        ]
        ordering = ["created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.equipment_name} ({self.hours_used} ساعت)"

    def clean(self) -> None:
        super().clean()
        if self.report_id:
            validate_related_organizations(self, report=self.report)

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class DailyReportMaterialEntry(UUIDModel, CreatedAtModel):
    """Material consumption recorded against a daily report draft."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="daily_report_material_entries",
    )
    report = models.ForeignKey(
        DailyReport,
        verbose_name="گزارش روزانه",
        on_delete=models.CASCADE,
        related_name="material_entries",
    )
    material_name = models.CharField("نام مصالح", max_length=255)
    material = models.ForeignKey(
        "materials.Material",
        verbose_name="مصالح",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_report_entries",
    )
    quantity = models.DecimalField(
        "مقدار مصرف",
        max_digits=18,
        decimal_places=4,
        default=Decimal("0.0000"),
    )
    unit = models.CharField("واحد قدیمی", max_length=30)
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_report_entries",
    )
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_report_material_entries_created",
    )

    class Meta:
        verbose_name = "رکورد مصالح گزارش روزانه"
        verbose_name_plural = "رکوردهای مصالح گزارش روزانه"
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "report"],
                name="daily_material_org_report_idx",
            ),
        ]
        ordering = ["created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.material_name} ({self.quantity} {self.unit})"

    def clean(self) -> None:
        super().clean()
        if self.report_id:
            validate_related_organizations(self, report=self.report)
        if self.material_id:
            validate_related_organizations(self, material=self.material)
            if not self.material.is_active or self.material.archived_at:
                raise ValidationError({"material": "مصالح باید فعال باشد."})
        if self.unit_of_measure_id:
            validate_related_organizations(self, unit_of_measure=self.unit_of_measure)
            if not self.unit_of_measure.is_active or self.unit_of_measure.archived_at:
                raise ValidationError(
                    {"unit_of_measure": "واحد اندازه‌گیری باید فعال باشد."}
                )
        if (
            self.material_id
            and self.unit_of_measure_id
            and self.material.unit_of_measure_id != self.unit_of_measure_id
        ):
            raise ValidationError(
                {"unit_of_measure": "واحد باید با واحد اصلی مصالح مطابقت داشته باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class DailyActivity(UUIDModel, CreatedAtModel):
    """A structured, draft-only activity observation for a daily report."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="daily_activities",
    )
    report = models.ForeignKey(
        DailyReport,
        verbose_name="گزارش روزانه",
        on_delete=models.CASCADE,
        related_name="daily_activities",
    )
    activity = models.ForeignKey(
        "projects.Activity",
        verbose_name="فعالیت",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_entries",
    )
    description = models.TextField("شرح فعالیت")
    quantity = models.DecimalField(
        "مقدار",
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_activities",
    )
    progress_percent = models.DecimalField(
        "درصد پیشرفت",
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_activities_created",
    )

    class Meta:
        verbose_name = "فعالیت روزانه"
        verbose_name_plural = "فعالیت‌های روزانه"
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "report"], name="daily_activity_org_report_idx"
            )
        ]
        ordering = ["created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.description = self.description.strip()
        if not self.description:
            raise ValidationError({"description": "وارد کردن شرح فعالیت الزامی است."})
        relations = {}
        if self.report_id:
            relations["report"] = self.report
        if self.activity_id:
            relations["activity"] = self.activity
            if not self.activity.is_active or self.activity.archived_at:
                raise ValidationError({"activity": "فعالیت باید فعال باشد."})
        if self.unit_of_measure_id:
            relations["unit_of_measure"] = self.unit_of_measure
            if not self.unit_of_measure.is_active or self.unit_of_measure.archived_at:
                raise ValidationError(
                    {"unit_of_measure": "واحد اندازه‌گیری باید فعال باشد."}
                )
        validate_related_organizations(self, **relations)
        if (
            self.report_id
            and self.activity_id
            and self.activity.project_id != self.report.project_id
        ):
            raise ValidationError(
                {"activity": "فعالیت باید متعلق به پروژه گزارش باشد."}
            )
        if self.quantity is not None:
            if self.quantity <= Decimal("0.0000"):
                raise ValidationError({"quantity": "مقدار باید مثبت باشد."})
            if not self.unit_of_measure_id:
                raise ValidationError(
                    {"unit_of_measure": "برای مقدار واردشده، انتخاب واحد الزامی است."}
                )
        elif self.unit_of_measure_id:
            raise ValidationError({"quantity": "با انتخاب واحد، وارد کردن مقدار الزامی است."})
        if self.progress_percent is not None and not Decimal(
            0
        ) <= self.progress_percent <= Decimal(100):
            raise ValidationError(
                {"progress_percent": "درصد پیشرفت باید بین ۰ تا ۱۰۰ باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class DelayEventStatus(models.TextChoices):
    OPEN = "open", "باز"
    RESOLVED = "resolved", "رفع‌شده"


class DelayEvent(UUIDModel, CreatedAtModel):
    """A structured delay observation retained alongside legacy report narrative."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="delay_events",
    )
    report = models.ForeignKey(
        DailyReport,
        verbose_name="گزارش روزانه",
        on_delete=models.CASCADE,
        related_name="delay_events",
    )
    activity = models.ForeignKey(
        "projects.Activity",
        verbose_name="فعالیت",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="delay_events",
    )
    occurred_on = models.DateField("تاریخ وقوع")
    category = models.CharField("دسته تأخیر", max_length=100, blank=True)
    cause = models.TextField("علت تأخیر")
    impact = models.TextField("اثر تأخیر", blank=True)
    responsible_party = models.CharField("طرف مسئول", max_length=255, blank=True)
    duration_hours = models.DecimalField(
        "مدت تأخیر (ساعت)",
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        "وضعیت", max_length=20, choices=DelayEventStatus.choices, default=DelayEventStatus.OPEN
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ثبت‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delay_events_created",
    )

    class Meta:
        verbose_name = "رویداد تأخیر"
        verbose_name_plural = "رویدادهای تأخیر"
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "report"], name="delay_event_org_report_idx"
            )
        ]
        ordering = ["occurred_on", "created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.category, self.cause, self.impact = (
            self.category.strip(),
            self.cause.strip(),
            self.impact.strip(),
        )
        self.responsible_party = self.responsible_party.strip()
        if not self.cause:
            raise ValidationError({"cause": "وارد کردن علت تأخیر الزامی است."})
        relations = {"report": self.report} if self.report_id else {}
        if self.activity_id:
            relations["activity"] = self.activity
            if not self.activity.is_active or self.activity.archived_at:
                raise ValidationError({"activity": "فعالیت باید فعال باشد."})
        validate_related_organizations(self, **relations)
        if (
            self.report_id
            and self.activity_id
            and self.activity.project_id != self.report.project_id
        ):
            raise ValidationError(
                {"activity": "فعالیت باید متعلق به پروژه گزارش باشد."}
            )
        if self.duration_hours is not None and self.duration_hours <= Decimal("0.00"):
            raise ValidationError(
                {"duration_hours": "مدت تأخیر باید مثبت باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
