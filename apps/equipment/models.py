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
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class DateRangeExpression(models.Func):
    function = "DATERANGE"
    output_field = DateRangeField()


class EquipmentOwnershipType(models.TextChoices):
    OWNED = "owned", "ملکی"
    RENTED = "rented", "اجاره‌ای"
    LEASED = "leased", "لیزینگ"


class EquipmentStatus(models.TextChoices):
    AVAILABLE = "available", "آماده‌به‌کار"
    ASSIGNED = "assigned", "تخصیص‌یافته"
    MAINTENANCE = "maintenance", "در حال سرویس یا تعمیر"
    INACTIVE = "inactive", "غیرفعال"
    RETIRED = "retired", "از رده خارج"


class EquipmentAssignmentStatus(models.TextChoices):
    SCHEDULED = "scheduled", "برنامه‌ریزی‌شده"
    ACTIVE = "active", "فعال"
    COMPLETED = "completed", "تکمیل‌شده"
    CANCELLED = "cancelled", "لغوشده"


class MaintenanceType(models.TextChoices):
    PREVENTIVE = "preventive", "سرویس پیشگیرانه"
    CORRECTIVE = "corrective", "تعمیر اصلاحی"
    INSPECTION = "inspection", "بازرسی فنی"


class MaintenanceStatus(models.TextChoices):
    SCHEDULED = "scheduled", "برنامه‌ریزی‌شده"
    IN_PROGRESS = "in_progress", "در حال انجام"
    COMPLETED = "completed", "تکمیل‌شده"
    CANCELLED = "cancelled", "لغوشده"


class EquipmentMeterKind(models.TextChoices):
    HOURS = "hours", "ساعت کار"
    DISTANCE = "distance", "مسافت"
    CYCLES = "cycles", "چرخه"


class WorkOrderStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SCHEDULED = "scheduled", "برنامه‌ریزی‌شده"
    IN_PROGRESS = "in_progress", "در حال انجام"
    COMPLETED = "completed", "تکمیل‌شده"
    CANCELLED = "cancelled", "لغوشده"


class Equipment(UUIDModel, TimeStampedModel):
    """A tenant-owned equipment master without a denormalized current project."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="equipment",
    )
    code = models.CharField("کد تجهیز", max_length=50)
    name = models.CharField("نام تجهیز", max_length=255)
    category = models.CharField("دسته تجهیز", max_length=120)
    manufacturer = models.CharField("سازنده", max_length=120, blank=True)
    model = models.CharField("مدل", max_length=120, blank=True)
    serial_number = models.CharField("شماره سریال", max_length=120, blank=True)
    registration_number = models.CharField(
        "شماره پلاک یا ثبت", max_length=64, blank=True
    )
    ownership_type = models.CharField(
        "نوع مالکیت",
        max_length=20,
        choices=EquipmentOwnershipType.choices,
        default=EquipmentOwnershipType.OWNED,
    )
    acquired_on = models.DateField("تاریخ تملک یا شروع اجاره", null=True, blank=True)
    status = models.CharField(
        "وضعیت تجهیز",
        max_length=20,
        choices=EquipmentStatus.choices,
        default=EquipmentStatus.AVAILABLE,
        db_index=True,
    )
    notes = models.TextField("یادداشت‌ها", blank=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_updated",
    )

    class Meta:
        verbose_name = "تجهیز"
        verbose_name_plural = "تجهیزات"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="uq_equipment_org_code",
            ),
            models.UniqueConstraint(
                fields=["organization", "serial_number"],
                condition=~Q(serial_number=""),
                name="uq_equipment_org_serial",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status"],
                name="equipment_org_status_idx",
            ),
            models.Index(
                fields=["organization", "archived_at"],
                name="equipment_org_archived_idx",
            ),
        ]
        ordering = ["name", "code"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        self.category = self.category.strip()
        self.manufacturer = self.manufacturer.strip()
        self.model = self.model.strip()
        self.serial_number = canonicalize_upper_identifier(self.serial_number)
        self.registration_number = canonicalize_upper_identifier(
            self.registration_number
        )
        self.notes = self.notes.strip()
        if not self.code or not self.name or not self.category:
            raise ValidationError("وارد کردن کد، نام و دسته تجهیز الزامی است.")
        if self.archived_at and self.status != EquipmentStatus.RETIRED:
            raise ValidationError(
                {"status": "فقط تجهیز از رده خارج را می‌توان بایگانی کرد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class EquipmentAssignment(UUIDModel, TimeStampedModel):
    """A conflict-safe historical deployment of equipment to a project/site."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="equipment_assignments",
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="تجهیز",
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        related_name="equipment_assignments",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        verbose_name="کارگاه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_assignments",
    )
    start_date = models.DateField("تاریخ شروع تخصیص")
    end_date = models.DateField("تاریخ پایان تخصیص", null=True, blank=True)
    status = models.CharField(
        "وضعیت تخصیص",
        max_length=20,
        choices=EquipmentAssignmentStatus.choices,
        default=EquipmentAssignmentStatus.SCHEDULED,
        db_index=True,
    )
    purpose = models.CharField("هدف تخصیص", max_length=255, blank=True)
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_assignments_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_assignments_updated",
    )

    class Meta:
        verbose_name = "تخصیص تجهیز"
        verbose_name_plural = "تخصیص‌های تجهیزات"
        constraints = [  # noqa: RUF012
            ExclusionConstraint(
                name="exclude_overlapping_equipment_assignments",
                expressions=[
                    ("equipment", RangeOperators.EQUAL),
                    (
                        DateRangeExpression(
                            "start_date",
                            "end_date",
                            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=~Q(status=EquipmentAssignmentStatus.CANCELLED),
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "status"],
                name="equip_assign_org_proj_idx",
            ),
            models.Index(
                fields=["organization", "equipment", "start_date"],
                name="equip_assign_org_eq_idx",
            ),
        ]
        ordering = ["-start_date", "-created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            equipment=self.equipment if self.equipment_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
        )
        self.purpose = self.purpose.strip()
        self.notes = self.notes.strip()
        if self.site_id and self.project_id and self.site.project_id != self.project_id:
            raise ValidationError(
                {"site": "کارگاه باید متعلق به پروژه انتخاب‌شده باشد."}
            )
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": "تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد."}
            )
        if self.status == EquipmentAssignmentStatus.COMPLETED and not self.end_date:
            raise ValidationError(
                {"end_date": "برای تخصیص تکمیل‌شده تاریخ پایان الزامی است."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                EquipmentAssignmentStatus.COMPLETED,
                EquipmentAssignmentStatus.CANCELLED,
            }:
                raise ValidationError("سابقه نهایی‌شده تخصیص تجهیز قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("سوابق تخصیص تجهیزات قابل حذف نیستند.")

    def __str__(self) -> str:
        return f"{self.equipment} · {self.project}"


class MaintenanceRecord(UUIDModel, TimeStampedModel):
    """Preserved service, repair, or inspection history for one equipment."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="maintenance_records",
    )
    equipment = models.ForeignKey(
        Equipment,
        verbose_name="تجهیز",
        on_delete=models.PROTECT,
        related_name="maintenance_records",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_maintenance_records",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        verbose_name="کارگاه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_maintenance_records",
    )
    provider = models.ForeignKey(
        "parties.BusinessParty",
        verbose_name="ارائه‌دهنده خدمت",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_maintenance_records",
    )
    record_number = models.CharField("شماره سرویس نگهداری", max_length=50)
    maintenance_type = models.CharField(
        "نوع نگهداری",
        max_length=20,
        choices=MaintenanceType.choices,
    )
    status = models.CharField(
        "وضعیت نگهداری",
        max_length=20,
        choices=MaintenanceStatus.choices,
        default=MaintenanceStatus.SCHEDULED,
        db_index=True,
    )
    summary = models.CharField("عنوان خدمت یا تعمیر", max_length=255)
    description = models.TextField("شرح کار", blank=True)
    scheduled_date = models.DateField("تاریخ برنامه‌ریزی‌شده")
    started_date = models.DateField("تاریخ شروع", null=True, blank=True)
    completed_date = models.DateField("تاریخ پایان", null=True, blank=True)
    cost = models.DecimalField(
        "هزینه",
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records_updated",
    )

    class Meta:
        verbose_name = "سابقه سرویس و تعمیر"
        verbose_name_plural = "سوابق سرویس و تعمیر"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "record_number"],
                name="uq_maintenance_org_number",
            ),
            models.CheckConstraint(
                condition=Q(cost__isnull=True) | Q(cost__gte=Decimal("0.00")),
                name="maintenance_cost_nonnegative",
            ),
            models.UniqueConstraint(
                fields=["equipment"],
                condition=Q(status=MaintenanceStatus.IN_PROGRESS),
                name="uq_equipment_in_progress_maintenance",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "equipment", "status"],
                name="maintenance_org_eq_status_idx",
            ),
            models.Index(
                fields=["organization", "scheduled_date"],
                name="maintenance_org_date_idx",
            ),
        ]
        ordering = ["-scheduled_date", "-created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.record_number = canonicalize_upper_identifier(self.record_number)
        self.summary = self.summary.strip()
        self.description = self.description.strip()
        self.notes = self.notes.strip()
        validate_related_organizations(
            self,
            equipment=self.equipment if self.equipment_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
            provider=self.provider if self.provider_id else None,
        )
        if not self.record_number or not self.summary:
            raise ValidationError("وارد کردن شماره سرویس  و عنوان سرویس الزامی است.")
        if self.site_id and (
            not self.project_id or self.site.project_id != self.project_id
        ):
            raise ValidationError(
                {"site": "کارگاه باید متعلق به پروژه انتخاب‌شده باشد."}
            )
        if self.cost is not None and self.cost < Decimal("0.00"):
            raise ValidationError({"cost": "هزینه نمی‌تواند منفی باشد."})
        if (
            self.started_date
            and self.completed_date
            and self.completed_date < self.started_date
        ):
            raise ValidationError(
                {"completed_date": "تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد."}
            )
        if self.status == MaintenanceStatus.SCHEDULED and (
            self.started_date or self.completed_date
        ):
            raise ValidationError("سابقه برنامه‌ریزی‌شده نباید تاریخ اجرا داشته باشد.")
        if self.status == MaintenanceStatus.IN_PROGRESS and (
            not self.started_date or self.completed_date
        ):
            raise ValidationError("نگهداری در حال انجام به تاریخ شروع نیاز دارد.")
        if self.status == MaintenanceStatus.COMPLETED and (
            not self.started_date or not self.completed_date
        ):
            raise ValidationError("نگهداری تکمیل‌شده به تاریخ شروع و پایان نیاز دارد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                MaintenanceStatus.COMPLETED,
                MaintenanceStatus.CANCELLED,
            }:
                raise ValidationError("سابقه نهایی‌شده سرویس یا تعمیر قابل تغییر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("سوابق سرویس و تعمیر قابل حذف نیستند.")

    def __str__(self) -> str:
        return f"{self.record_number} - {self.equipment}"


# Kept separate to make the P8 operational extension easy to identify while Django
# still registers the models under the existing Equipment app.
from apps.equipment.p8_models import (  # noqa: F401
    CostAllocationStatus,
    CostPolicyStatus,
    DowntimeEvent,
    EquipmentCostAllocation,
    EquipmentCostPolicyVersion,
    EquipmentCostRate,
    EquipmentCostSourceEnvelope,
    EquipmentMeter,
    EquipmentUsageLog,
    EquipmentWorkOrder,
    FuelLog,
    MaintenancePlan,
    MaintenanceSparePartReference,
    MaintenanceWorkOrderEvidence,
    MeterReading,
    OperatorEquipmentQualification,
    ProposalStatus,
)
