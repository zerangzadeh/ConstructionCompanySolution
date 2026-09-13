from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class SafetyIncidentSeverity(models.TextChoices):
    LOW = "low", "کم"
    MEDIUM = "medium", "متوسط"
    HIGH = "high", "زیاد"
    CRITICAL = "critical", "بحرانی"
    FATAL = "fatal", "منجر به فوت"


class SafetyIncidentType(models.TextChoices):
    NEAR_MISS = "near_miss", "شبه‌حادثه"
    INJURY = "injury", "آسیب انسانی"
    OCCUPATIONAL_ILLNESS = "occupational_illness", "بیماری شغلی"
    PROPERTY_DAMAGE = "property_damage", "خسارت مالی"
    FIRE = "fire", "آتش‌سوزی"
    UNSAFE_CONDITION = "unsafe_condition", "شرایط ناایمن"
    OTHER = "other", "سایر"


class SafetyIncidentStatus(models.TextChoices):
    REPORTED = "reported", "ثبت‌شده"
    UNDER_REVIEW = "under_review", "در حال بررسی"
    ASSIGNED = "assigned", "تخصیص‌یافته"
    ACTION_IN_PROGRESS = "action_in_progress", "اقدام اصلاحی در حال انجام"
    RESOLVED = "resolved", "رفع‌شده"
    CLOSED = "closed", "بسته‌شده"


class SafetyIncidentQuerySet(models.QuerySet):
    """Prevent lifecycle and immutable history from being bypassed in bulk."""

    def update(self, **kwargs: object) -> int:
        raise ValidationError("حوادث ایمنی باید فقط از طریق سرویس ایمنی تغییر کنند.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("سوابق حوادث ایمنی قابل حذف نیستند.")


class SafetyIncident(UUIDModel, TimeStampedModel):
    """A tenant-owned safety incident with a controlled corrective workflow."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.PROTECT,
        related_name="safety_incidents",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        related_name="safety_incidents",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        verbose_name="کارگاه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="safety_incidents",
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        verbose_name="فاز پروژه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="safety_incidents",
    )
    activity = models.ForeignKey(
        "projects.Activity",
        verbose_name="فعالیت",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="safety_incidents",
    )
    daily_report = models.ForeignKey(
        "daily_reports.DailyReport",
        verbose_name="گزارش روزانه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="safety_incidents",
    )
    incident_number = models.CharField("شماره حادثه", max_length=50)
    occurred_at = models.DateTimeField("زمان وقوع", db_index=True)
    incident_type = models.CharField(
        "نوع حادثه", max_length=32, choices=SafetyIncidentType.choices
    )
    severity = models.CharField(
        "شدت", max_length=20, choices=SafetyIncidentSeverity.choices, db_index=True
    )
    description = models.TextField("شرح حادثه")
    immediate_action = models.TextField("اقدام فوری", blank=True)
    corrective_action = models.TextField("اقدام اصلاحی", blank=True)
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر مسئول",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="responsible_safety_incidents",
    )
    responsible_employee = models.ForeignKey(
        "workforce.Employee",
        verbose_name="کارمند مسئول",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="responsible_safety_incidents",
    )
    responsible_party = models.ForeignKey(
        "parties.BusinessParty",
        verbose_name="طرف تجاری مسئول",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="responsible_safety_incidents",
    )
    due_date = models.DateField("مهلت اقدام", null=True, blank=True, db_index=True)
    status = models.CharField(
        "وضعیت",
        max_length=24,
        choices=SafetyIncidentStatus.choices,
        default=SafetyIncidentStatus.REPORTED,
        db_index=True,
    )
    reviewed_at = models.DateTimeField("زمان بررسی", null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بررسی‌کننده",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="safety_incidents_reviewed",
    )
    resolution_summary = models.TextField("شرح رفع حادثه", blank=True)
    resolved_at = models.DateTimeField("زمان رفع", null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="رفع‌کننده",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="safety_incidents_resolved",
    )
    closure_summary = models.TextField("جمع‌بندی بستن", blank=True)
    closed_at = models.DateTimeField("زمان بستن", null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بسته‌شده توسط",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="safety_incidents_closed",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.PROTECT,
        related_name="safety_incidents_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.PROTECT,
        related_name="safety_incidents_updated",
    )

    objects = SafetyIncidentQuerySet.as_manager()

    class Meta:
        verbose_name = "حادثه ایمنی"
        verbose_name_plural = "حوادث ایمنی"
        ordering = ["-occurred_at", "-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "incident_number"],
                name="uq_safety_incident_org_number",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=SafetyIncidentStatus.CLOSED, closed_at__isnull=False)
                    | ~Q(status=SafetyIncidentStatus.CLOSED)
                ),
                name="safety_closed_requires_timestamp",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "status"],
                name="safety_org_project_status_idx",
            ),
            models.Index(
                fields=["organization", "severity", "status"],
                name="safety_org_severity_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.incident_number} - {self.get_incident_type_display()}"

    def clean(self) -> None:
        super().clean()
        self.incident_number = canonicalize_upper_identifier(self.incident_number)
        self.description = self.description.strip()
        self.immediate_action = self.immediate_action.strip()
        self.corrective_action = self.corrective_action.strip()
        self.resolution_summary = self.resolution_summary.strip()
        self.closure_summary = self.closure_summary.strip()
        if not self.incident_number or not self.description:
            raise ValidationError("شماره و شرح حادثه الزامی است.")
        if self.occurred_at and (
            timezone.is_naive(self.occurred_at) or self.occurred_at > timezone.now()
        ):
            raise ValidationError(
                {"occurred_at": "زمان وقوع باید timezone-aware و در گذشته باشد."}
            )
        validate_related_organizations(
            self,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
            phase=self.phase if self.phase_id else None,
            activity=self.activity if self.activity_id else None,
            daily_report=self.daily_report if self.daily_report_id else None,
            responsible_employee=(
                self.responsible_employee if self.responsible_employee_id else None
            ),
            responsible_party=(
                self.responsible_party if self.responsible_party_id else None
            ),
        )
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه حادثه باشد."})
        if self.phase_id and (not self.site_id or self.phase.site_id != self.site_id):
            raise ValidationError({"phase": "فاز باید متعلق به کارگاه حادثه باشد."})
        if self.activity_id:
            if self.activity.project_id != self.project_id:
                raise ValidationError(
                    {"activity": "فعالیت باید متعلق به پروژه حادثه باشد."}
                )
            if self.activity.site_id and self.activity.site_id != self.site_id:
                raise ValidationError(
                    {"activity": "کارگاه فعالیت با کارگاه حادثه سازگار نیست."}
                )
            if self.activity.phase_id and self.activity.phase_id != self.phase_id:
                raise ValidationError(
                    {"activity": "فاز فعالیت با فاز حادثه سازگار نیست."}
                )
        if self.daily_report_id:
            if self.daily_report.project_id != self.project_id:
                raise ValidationError(
                    {"daily_report": "گزارش روزانه باید متعلق به پروژه حادثه باشد."}
                )
            if self.daily_report.site_id != self.site_id:
                raise ValidationError(
                    {"daily_report": "کارگاه گزارش روزانه با حادثه سازگار نیست."}
                )
            if self.daily_report.phase_id != self.phase_id:
                raise ValidationError(
                    {"daily_report": "فاز گزارش روزانه با حادثه سازگار نیست."}
                )
        if (
            self.responsible_user_id
            and not self.organization.memberships.filter(
                user_id=self.responsible_user_id,
                status="active",
                role_definition__is_active=True,
            ).exists()
        ):
            raise ValidationError(
                {"responsible_user": "کاربر مسئول باید عضو فعال همین سازمان باشد."}
            )
        if self.responsible_employee_id and self.responsible_employee.archived_at:
            raise ValidationError(
                {"responsible_employee": "کارمند مسئول نباید بایگانی‌شده باشد."}
            )
        if self.responsible_party_id and self.responsible_party.archived_at:
            raise ValidationError(
                {"responsible_party": "طرف مسئول نباید بایگانی‌شده باشد."}
            )
        for field_name in (
            "created_by",
            "updated_by",
            "reviewed_by",
            "resolved_by",
            "closed_by",
        ):
            user_id = getattr(self, f"{field_name}_id")
            if (
                user_id
                and not getattr(self, field_name).is_superuser
                and not self.organization.memberships.filter(user_id=user_id).exists()
            ):
                raise ValidationError(
                    {field_name: "کاربر ثبت‌شده باید عضوی از همین سازمان باشد."}
                )
        if self.status != SafetyIncidentStatus.REPORTED and (
            not self.reviewed_at or not self.reviewed_by_id
        ):
            raise ValidationError("زمان و عامل بررسی حادثه الزامی است.")
        if self.status in {
            SafetyIncidentStatus.ASSIGNED,
            SafetyIncidentStatus.ACTION_IN_PROGRESS,
            SafetyIncidentStatus.RESOLVED,
            SafetyIncidentStatus.CLOSED,
        } and not any(
            (
                self.responsible_user_id,
                self.responsible_employee_id,
                self.responsible_party_id,
            )
        ):
            raise ValidationError("برای این وضعیت تعیین مسئول الزامی است.")
        if (
            self.status
            in {
                SafetyIncidentStatus.ASSIGNED,
                SafetyIncidentStatus.ACTION_IN_PROGRESS,
                SafetyIncidentStatus.RESOLVED,
                SafetyIncidentStatus.CLOSED,
            }
            and not self.due_date
        ):
            raise ValidationError("مهلت انجام اقدام اصلاحی الزامی است.")
        if (
            self.status
            in {
                SafetyIncidentStatus.ACTION_IN_PROGRESS,
                SafetyIncidentStatus.RESOLVED,
                SafetyIncidentStatus.CLOSED,
            }
            and not self.corrective_action
        ):
            raise ValidationError("شرح اقدام اصلاحی الزامی است.")
        if (
            self.status
            in {
                SafetyIncidentStatus.RESOLVED,
                SafetyIncidentStatus.CLOSED,
            }
            and not self.resolution_summary
        ):
            raise ValidationError("شرح رفع حادثه الزامی است.")
        if self.status in {
            SafetyIncidentStatus.RESOLVED,
            SafetyIncidentStatus.CLOSED,
        } and (not self.resolved_at or not self.resolved_by_id):
            raise ValidationError("زمان و عامل رفع حادثه الزامی است.")
        if self.status == SafetyIncidentStatus.CLOSED and (
            not self.closure_summary or not self.closed_at or not self.closed_by_id
        ):
            raise ValidationError("جمع‌بندی، زمان و عامل بستن حادثه الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self._state.adding and self.status != SafetyIncidentStatus.REPORTED:
            raise ValidationError("حادثه جدید باید در وضعیت ثبت‌شده ایجاد شود.")
        if self.pk and not self._state.adding:
            previous_status = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )
            if previous_status == SafetyIncidentStatus.CLOSED:
                raise ValidationError("حادثه بسته‌شده قابل تغییر نیست.")
            if previous_status != self.status and not getattr(
                self, "_service_transition", False
            ):
                raise ValidationError("تغییر وضعیت فقط از طریق سرویس ایمنی مجاز است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("سوابق حوادث ایمنی قابل حذف نیستند.")
