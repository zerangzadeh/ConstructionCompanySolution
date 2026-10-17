from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import Q

from core.identifiers import canonicalize_upper_identifier
from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations

# Django Meta options intentionally use class-level mutable declarations.
# ruff: noqa: RUF012


def _tenant_timezone(organization) -> str:
    try:
        return organization.settings.timezone
    except ObjectDoesNotExist:
        return organization.timezone


class AppendOnlyModel(UUIDModel, CreatedAtModel):
    class Meta:
        abstract = True

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError(
                "سابقه قطعی قابل ویرایش نیست؛ رکورد اصلاحی جدید ثبت کنید."
            )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("سابقه قطعی قابل حذف نیست.")


class WorkCalendar(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="work_calendars",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    timezone = models.CharField(max_length=64)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    working_weekdays = models.JSONField(
        default=list, help_text="ISO weekday numbers 1..7"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="work_calendars_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="time_calendar_org_code_uq"
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gte=models.F("effective_from")),
                name="time_calendar_dates_ck",
            ),
            models.CheckConstraint(
                condition=(
                    Q(is_active=True, archived_at__isnull=True)
                    | Q(is_active=False, archived_at__isnull=False)
                ),
                name="time_calendar_archive_ck",
            ),
        ]
        ordering = ["name"]

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("کد و نام تقویم الزامی است.")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError({"timezone": "منطقه زمانی IANA معتبر نیست."}) from exc
        if self.organization_id and self.timezone != _tenant_timezone(
            self.organization
        ):
            raise ValidationError(
                {"timezone": "تقویم باید از منطقه زمانی تنظیمات شرکت استفاده کند."}
            )
        weekdays = self.working_weekdays
        if not isinstance(weekdays, list) or any(
            type(day) is not int or day < 1 or day > 7 for day in weekdays
        ):
            raise ValidationError(
                {"working_weekdays": "روزهای کاری باید فهرستی از اعداد ۱ تا ۷ باشند."}
            )
        if len(weekdays) != len(set(weekdays)):
            raise ValidationError({"working_weekdays": "روز کاری تکراری مجاز نیست."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class CalendarHoliday(AppendOnlyModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="calendar_holidays",
    )
    calendar = models.ForeignKey(
        WorkCalendar, on_delete=models.PROTECT, related_name="holidays"
    )
    date = models.DateField()
    name = models.CharField(max_length=255)
    is_working_override = models.BooleanField(default=False)
    source_reference = models.CharField(max_length=255, blank=True)
    reason = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="calendar_holidays_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "date"], name="time_holiday_calendar_date_uq"
            )
        ]
        ordering = ["date"]

    def clean(self) -> None:
        validate_related_organizations(
            self, calendar=self.calendar if self.calendar_id else None
        )
        if not self.reason.strip():
            raise ValidationError(
                {"reason": "دلیل ثبت یا اصلاح روز تقویمی الزامی است."}
            )


class ShiftDefinition(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="shift_definitions",
    )
    calendar = models.ForeignKey(
        WorkCalendar, on_delete=models.PROTECT, related_name="shifts"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    crosses_midnight = models.BooleanField(default=False)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shift_definitions_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="time_shift_org_code_uq"
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gte=models.F("effective_from")),
                name="time_shift_dates_ck",
            ),
        ]
        ordering = ["name"]

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        validate_related_organizations(
            self, calendar=self.calendar if self.calendar_id else None
        )
        if self.starts_at == self.ends_at:
            raise ValidationError("شیفت صفر یا ۲۴ ساعته مجاز نیست.")
        actual_crossing = self.ends_at < self.starts_at
        if actual_crossing != self.crosses_midnight:
            raise ValidationError(
                {
                    "crosses_midnight": "عبور شیفت از نیمه‌شب باید صریح و سازگار با زمان‌ها باشد."
                }
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def interval_for(self, work_date):
        zone = ZoneInfo(self.calendar.timezone)
        start = datetime.combine(work_date, self.starts_at, zone)
        end_date = work_date + timedelta(days=1 if self.crosses_midnight else 0)
        return start, datetime.combine(end_date, self.ends_at, zone)


class ShiftBreak(AppendOnlyModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="shift_breaks",
    )
    shift = models.ForeignKey(
        ShiftDefinition, on_delete=models.PROTECT, related_name="breaks"
    )
    sequence = models.PositiveSmallIntegerField()
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    ends_next_day = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shift_breaks_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["shift", "sequence"], name="time_shift_break_seq_uq"
            )
        ]
        ordering = ["sequence"]

    def clean(self) -> None:
        validate_related_organizations(
            self, shift=self.shift if self.shift_id else None
        )
        if not self.shift_id:
            return
        base_date = date(2000, 1, 1)
        shift_start = datetime.combine(base_date, self.shift.starts_at)
        shift_end = datetime.combine(
            base_date + timedelta(days=self.shift.crosses_midnight), self.shift.ends_at
        )
        starts_next_day = (
            self.shift.crosses_midnight and self.starts_at < self.shift.starts_at
        )
        break_start = datetime.combine(
            base_date + timedelta(days=starts_next_day), self.starts_at
        )
        break_end = datetime.combine(
            base_date + timedelta(days=self.ends_next_day), self.ends_at
        )
        if (
            break_end <= break_start
            or break_start < shift_start
            or break_end > shift_end
        ):
            raise ValidationError("بازه استراحت باید مثبت و کاملاً داخل بازه شیفت باشد.")


class AttendanceState(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    EXCEPTION = "exception", "نیازمند رسیدگی"
    FINALIZED = "finalized", "قطعی"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    REVERSED = "reversed", "برگشت‌شده"


class AttendanceSource(models.TextChoices):
    MANUAL = "manual", "ثبت دستی کنترل‌شده"
    IMPORT = "import", "درون‌ریزی قراردادی"


class AttendanceRecord(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    employee = models.ForeignKey(
        "workforce.Employee",
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    calendar = models.ForeignKey(
        WorkCalendar, on_delete=models.PROTECT, related_name="attendance_records"
    )
    shift = models.ForeignKey(
        ShiftDefinition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_records",
    )
    work_date = models.DateField()
    check_in_at = models.DateTimeField()
    check_out_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=20, choices=AttendanceSource.choices)
    source_reference = models.CharField(max_length=255, blank=True)
    state = models.CharField(
        max_length=20,
        choices=AttendanceState.choices,
        default=AttendanceState.DRAFT,
        db_index=True,
    )
    exception_code = models.CharField(max_length=50, blank=True)
    exception_notes = models.TextField(blank=True)
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_records_captured",
    )
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_records_finalized",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(check_out_at__isnull=True)
                | Q(check_out_at__gt=models.F("check_in_at")),
                name="time_attendance_interval_ck",
            ),
            models.CheckConstraint(
                condition=(
                    Q(project__isnull=True, site__isnull=True)
                    | Q(project__isnull=False)
                ),
                name="time_attendance_site_project_ck",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "employee", "work_date"],
                name="time_attendance_employee_idx",
            )
        ]
        ordering = ["-work_date", "-check_in_at"]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            employee=self.employee if self.employee_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
            calendar=self.calendar if self.calendar_id else None,
            shift=self.shift if self.shift_id else None,
        )
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError(
                {"site": "کارگاه باید متعلق به پروژه انتخاب‌شده باشد."}
            )
        if self.shift_id and self.shift.calendar_id != self.calendar_id:
            raise ValidationError({"shift": "شیفت باید متعلق به تقویم انتخاب‌شده باشد."})
        if self.check_in_at and self.check_in_at.tzinfo is None:
            raise ValidationError(
                {"check_in_at": "زمان ورود باید timezone-aware باشد."}
            )
        if self.check_out_at and self.check_out_at.tzinfo is None:
            raise ValidationError(
                {"check_out_at": "زمان خروج باید timezone-aware باشد."}
            )
        if self.calendar_id and self.check_in_at:
            local_date = self.check_in_at.astimezone(
                ZoneInfo(self.calendar.timezone)
            ).date()
            if local_date != self.work_date:
                raise ValidationError(
                    {
                        "work_date": "تاریخ کار باید از زمان ورود در منطقه زمانی شرکت استخراج شود."
                    }
                )
        if self.state == AttendanceState.EXCEPTION and not self.exception_code:
            raise ValidationError(
                {"exception_code": "برای رکورد استثنا، کد استثنا الزامی است."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            original = AttendanceRecord.objects.filter(pk=self.pk).only("state").first()
            if original and original.state in {
                AttendanceState.FINALIZED,
                AttendanceState.SUPERSEDED,
                AttendanceState.REVERSED,
            }:
                raise ValidationError(
                    "حضور قطعی قابل ویرایش نیست؛ اصلاح کنترل‌شده ثبت کنید."
                )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class RequestKind(models.TextChoices):
    LEAVE = "leave", "مرخصی"
    MISSION = "mission", "مأموریت"


class RequestState(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأیید‌شده"
    REJECTED = "rejected", "ردشده"
    CANCELLED = "cancelled", "لغوشده"


class LeaveMissionRequest(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="leave_mission_requests",
    )
    employee = models.ForeignKey(
        "workforce.Employee",
        on_delete=models.PROTECT,
        related_name="leave_mission_requests",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="leave_mission_requests",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="leave_mission_requests",
    )
    kind = models.CharField(max_length=20, choices=RequestKind.choices)
    category_code = models.CharField(max_length=50)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.TextField()
    policy_reference = models.CharField(max_length=255, blank=True)
    state = models.CharField(
        max_length=20,
        choices=RequestState.choices,
        default=RequestState.DRAFT,
        db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leave_mission_requests_created",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="leave_mission_requests_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")),
                name="time_leave_interval_ck",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "employee", "starts_at"],
                name="time_leave_employee_idx",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            employee=self.employee if self.employee_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
        )
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            original = (
                LeaveMissionRequest.objects.filter(pk=self.pk).only("state").first()
            )
            if original and original.state in {
                RequestState.APPROVED,
                RequestState.REJECTED,
                RequestState.CANCELLED,
            }:
                raise ValidationError("درخواست تعیین‌تکلیف‌شده قابل ویرایش نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class OvertimeRequest(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="overtime_requests",
    )
    employee = models.ForeignKey(
        "workforce.Employee", on_delete=models.PROTECT, related_name="overtime_requests"
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="overtime_requests",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="overtime_requests",
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.TextField()
    policy_reference = models.CharField(max_length=255, blank=True)
    state = models.CharField(
        max_length=20,
        choices=RequestState.choices,
        default=RequestState.DRAFT,
        db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="overtime_requests_created",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="overtime_requests_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")),
                name="time_overtime_interval_ck",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "employee", "starts_at"],
                name="time_overtime_employee_idx",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            employee=self.employee if self.employee_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
        )
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            original = OvertimeRequest.objects.filter(pk=self.pk).only("state").first()
            if original and original.state in {
                RequestState.APPROVED,
                RequestState.REJECTED,
                RequestState.CANCELLED,
            }:
                raise ValidationError("درخواست تعیین‌تکلیف‌شده قابل ویرایش نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class ImportState(models.TextChoices):
    PROCESSING = "processing", "در حال پردازش"
    COMPLETED = "completed", "تکمیل‌شده"
    EXCEPTION = "exception", "دارای استثنا"


class AttendanceImportBatch(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_import_batches",
    )
    idempotency_key = models.CharField(max_length=100)
    source_label = models.CharField(max_length=255)
    source_digest = models.CharField(max_length=64)
    state = models.CharField(
        max_length=20, choices=ImportState.choices, default=ImportState.PROCESSING
    )
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_import_batches",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="time_import_org_key_uq",
            )
        ]
        ordering = ["-created_at"]


class AttendanceImportRow(AppendOnlyModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_import_rows",
    )
    batch = models.ForeignKey(
        AttendanceImportBatch, on_delete=models.PROTECT, related_name="rows"
    )
    row_number = models.PositiveIntegerField()
    source_reference = models.CharField(max_length=255)
    payload_digest = models.CharField(max_length=64)
    outcome = models.CharField(
        max_length=20, choices=(("created", "ایجاد شد"), ("exception", "استثنا"))
    )
    exception_code = models.CharField(max_length=50, blank=True)
    exception_detail = models.TextField(blank=True)
    attendance = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="import_rows",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "row_number"], name="time_import_row_uq"
            )
        ]
        ordering = ["row_number"]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            batch=self.batch if self.batch_id else None,
            attendance=self.attendance if self.attendance_id else None,
        )


class AttendanceAdjustment(AppendOnlyModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_adjustments",
    )
    attendance = models.ForeignKey(
        AttendanceRecord, on_delete=models.PROTECT, related_name="adjustments"
    )
    replacement = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacement_for",
    )
    kind = models.CharField(
        max_length=20, choices=(("correction", "اصلاح"), ("reversal", "برگشت"))
    )
    reason = models.TextField()
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_adjustments_requested",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_adjustments_approved",
    )
    approved_at = models.DateTimeField()

    def clean(self) -> None:
        validate_related_organizations(
            self,
            attendance=self.attendance if self.attendance_id else None,
            replacement=self.replacement if self.replacement_id else None,
        )
        if self.requested_by_id == self.approved_by_id:
            raise ValidationError(
                {"approved_by": "درخواست‌کننده نمی‌تواند اصلاح خود را تأیید کند."}
            )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل اصلاح یا برگشت الزامی است."})


class AttendanceCorrectionRequest(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_correction_requests",
    )
    attendance = models.ForeignKey(
        AttendanceRecord, on_delete=models.PROTECT, related_name="correction_requests"
    )
    kind = models.CharField(
        max_length=20,
        choices=(("correction", "اصلاح"), ("reversal", "برگشت")),
    )
    reason = models.TextField()
    replacement_work_date = models.DateField(null=True, blank=True)
    replacement_check_in_at = models.DateTimeField(null=True, blank=True)
    replacement_check_out_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=(("pending", "در انتظار"), ("approved", "تأیید"), ("rejected", "رد")),
        default="pending",
        db_index=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_corrections_requested",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_corrections_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True)
    adjustment = models.OneToOneField(
        AttendanceAdjustment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="correction_request",
    )

    def clean(self) -> None:
        validate_related_organizations(
            self, attendance=self.attendance if self.attendance_id else None
        )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل اصلاح یا برگشت الزامی است."})
        if self.kind == "correction" and not (
            self.replacement_check_in_at and self.replacement_check_out_at
        ):
            raise ValidationError("اصلاح باید بازه جایگزین کامل داشته باشد.")
        if self.kind == "reversal" and any(
            (
                self.replacement_work_date,
                self.replacement_check_in_at,
                self.replacement_check_out_at,
            )
        ):
            raise ValidationError("برگشت نباید بازه جایگزین داشته باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            original = (
                AttendanceCorrectionRequest.objects.filter(pk=self.pk)
                .only("status")
                .first()
            )
            if original and original.status != "pending":
                raise ValidationError("درخواست اصلاح تعیین‌تکلیف‌شده قابل ویرایش نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class AttendanceReconciliation(AppendOnlyModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="attendance_reconciliations",
    )
    attendance = models.ForeignKey(
        AttendanceRecord, on_delete=models.PROTECT, related_name="reconciliations"
    )
    outcome = models.CharField(
        max_length=20,
        choices=(("matched", "تطبیق"), ("exception", "استثنا"), ("resolved", "حل‌شده")),
    )
    reason = models.TextField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_reconciliations",
    )

    def clean(self) -> None:
        validate_related_organizations(
            self, attendance=self.attendance if self.attendance_id else None
        )


class TimesheetState(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    APPROVED = "approved", "تأیید‌شده"
    REJECTED = "rejected", "ردشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class Timesheet(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="timesheets",
    )
    employee = models.ForeignKey(
        "workforce.Employee", on_delete=models.PROTECT, related_name="timesheets"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    revision = models.PositiveIntegerField(default=1)
    declared_minutes = models.PositiveIntegerField()
    state = models.CharField(
        max_length=20,
        choices=TimesheetState.choices,
        default=TimesheetState.DRAFT,
        db_index=True,
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="timesheets_prepared",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="timesheets_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseded_by",
    )
    correction_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="time_sheet_period_ck",
            ),
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "employee",
                    "period_start",
                    "period_end",
                    "revision",
                ],
                name="time_sheet_revision_uq",
            ),
        ]
        ordering = ["-period_start", "employee"]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            employee=self.employee if self.employee_id else None,
            supersedes=self.supersedes if self.supersedes_id else None,
        )
        if self.revision > 1 and (
            not self.supersedes_id or not self.correction_reason.strip()
        ):
            raise ValidationError(
                "نسخه اصلاحی باید به نسخه قبلی و دلیل اصلاح متصل باشد."
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk:
            original = Timesheet.objects.filter(pk=self.pk).only("state").first()
            if original and original.state != TimesheetState.DRAFT:
                raise ValidationError(
                    "کارکرد ارسال‌شده قابل ویرایش نیست؛ نسخه اصلاحی بسازید."
                )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class TimesheetEntry(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="timesheet_entries",
    )
    timesheet = models.ForeignKey(
        Timesheet, on_delete=models.PROTECT, related_name="entries"
    )
    work_date = models.DateField()
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, related_name="timesheet_entries"
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="timesheet_entries",
    )
    activity = models.ForeignKey(
        "projects.Activity",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="timesheet_entries",
    )
    minutes = models.PositiveIntegerField()
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(minutes__gt=0), name="time_entry_minutes_ck"
            ),
            models.UniqueConstraint(
                fields=["timesheet", "work_date", "project", "site", "activity"],
                name="time_entry_allocation_uq",
            ),
        ]
        ordering = ["work_date", "project", "site", "activity"]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            timesheet=self.timesheet if self.timesheet_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
            activity=self.activity if self.activity_id else None,
        )
        if self.timesheet_id:
            if self.timesheet.state != TimesheetState.DRAFT:
                raise ValidationError("ردیف‌های کارکرد ارسال‌شده قابل ویرایش نیستند.")
            if (
                not self.timesheet.period_start
                <= self.work_date
                <= self.timesheet.period_end
            ):
                raise ValidationError(
                    {"work_date": "تاریخ ردیف خارج از دوره کارکرد است."}
                )
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه باشد."})
        if self.activity_id and self.activity.project_id != self.project_id:
            raise ValidationError({"activity": "فعالیت باید متعلق به پروژه باشد."})
        if self.activity_id and self.activity.site_id != self.site_id:
            raise ValidationError(
                {
                    "activity": "فعالیت باید با کارگاه انتخاب‌شده سازگار باشد؛ کارگاه فعالیت قابل استنباط نیست."
                }
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class TimesheetReview(AppendOnlyModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="timesheet_reviews",
    )
    timesheet = models.ForeignKey(
        Timesheet, on_delete=models.PROTECT, related_name="reviews"
    )
    decision = models.CharField(
        max_length=20, choices=(("approved", "تأیید"), ("rejected", "رد"))
    )
    reason = models.TextField()
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="timesheet_reviews",
    )

    def clean(self) -> None:
        validate_related_organizations(
            self, timesheet=self.timesheet if self.timesheet_id else None
        )
        if self.timesheet_id and self.reviewer_id in {
            self.timesheet.prepared_by_id,
            self.timesheet.submitted_by_id,
        }:
            raise ValidationError(
                {
                    "reviewer": "تهیه‌کننده یا ارسال‌کننده نمی‌تواند کارکرد خود را بررسی کند."
                }
            )


class LaborDistributionPreview(AppendOnlyModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="labor_distribution_previews",
    )
    timesheet = models.ForeignKey(
        Timesheet, on_delete=models.PROTECT, related_name="distribution_previews"
    )
    total_minutes = models.PositiveIntegerField()
    policy_gate = models.CharField(
        max_length=100, default="RATE_AND_PROJECT_COST_POLICY_UNRESOLVED"
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="labor_distribution_previews",
    )

    def clean(self) -> None:
        validate_related_organizations(
            self, timesheet=self.timesheet if self.timesheet_id else None
        )
        if self.timesheet_id and self.timesheet.state != TimesheetState.APPROVED:
            raise ValidationError("پیش‌نمایش فقط از کارکرد تأییدشده ساخته می‌شود.")


class LaborDistributionPreviewLine(AppendOnlyModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="labor_distribution_preview_lines",
    )
    preview = models.ForeignKey(
        LaborDistributionPreview, on_delete=models.PROTECT, related_name="lines"
    )
    timesheet_entry = models.ForeignKey(
        TimesheetEntry,
        on_delete=models.PROTECT,
        related_name="distribution_preview_lines",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="labor_distribution_preview_lines",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="labor_distribution_preview_lines",
    )
    activity = models.ForeignKey(
        "projects.Activity",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="labor_distribution_preview_lines",
    )
    minutes = models.PositiveIntegerField()

    def clean(self) -> None:
        validate_related_organizations(
            self,
            preview=self.preview if self.preview_id else None,
            timesheet_entry=self.timesheet_entry if self.timesheet_entry_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
            activity=self.activity if self.activity_id else None,
        )
