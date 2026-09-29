from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class QualityIssueType(models.TextChoices):
    NONCONFORMANCE = "nonconformance", "عدم انطباق"
    DEFECT = "defect", "نقص اجرایی"
    MATERIAL = "material", "مصالح"
    WORKMANSHIP = "workmanship", "کیفیت اجرا"
    INSPECTION = "inspection", "بازرسی"
    TEST_RESULT = "test_result", "نتیجه آزمون"
    DOCUMENTATION = "documentation", "مستندات"
    OTHER = "other", "سایر"


class QualityIssueSeverity(models.TextChoices):
    MINOR = "minor", "جزئی"
    MAJOR = "major", "عمده"
    CRITICAL = "critical", "بحرانی"


class QualityIssueStatus(models.TextChoices):
    REPORTED = "reported", "ثبت‌شده"
    UNDER_REVIEW = "under_review", "در حال بررسی"
    ASSIGNED = "assigned", "تخصیص‌یافته"
    ACTION_IN_PROGRESS = "action_in_progress", "اقدام اصلاحی در حال انجام"
    AWAITING_VERIFICATION = "awaiting_verification", "در انتظار راستی‌آزمایی"
    VERIFIED = "verified", "راستی‌آزمایی‌شده"
    CLOSED = "closed", "بسته‌شده"


class QualityIssueQuerySet(models.QuerySet):
    """Prevent lifecycle controls and retained history from being bypassed."""

    def update(self, **kwargs: object) -> int:
        raise ValidationError("مسائل کیفیت باید فقط از طریق سرویس کیفیت تغییر کنند.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("سوابق مسائل کیفیت قابل حذف نیستند.")


class QualityIssue(UUIDModel, TimeStampedModel):
    """A tenant-owned quality issue with corrective and verification workflow."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.PROTECT,
        related_name="quality_issues",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        related_name="quality_issues",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        verbose_name="کارگاه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quality_issues",
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        verbose_name="فاز پروژه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quality_issues",
    )
    activity = models.ForeignKey(
        "projects.Activity",
        verbose_name="فعالیت",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quality_issues",
    )
    daily_report = models.ForeignKey(
        "daily_reports.DailyReport",
        verbose_name="گزارش روزانه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quality_issues",
    )
    issue_number = models.CharField("شماره مسئله", max_length=50)
    identified_at = models.DateTimeField("زمان شناسایی", db_index=True)
    issue_type = models.CharField(
        "نوع مسئله", max_length=32, choices=QualityIssueType.choices
    )
    severity = models.CharField(
        "شدت", max_length=20, choices=QualityIssueSeverity.choices, db_index=True
    )
    description = models.TextField("شرح مسئله")
    specification_reference = models.TextField("مشخصات یا مرجع", blank=True)
    corrective_action = models.TextField("اقدام اصلاحی", blank=True)
    corrective_action_result = models.TextField("نتیجه اقدام اصلاحی", blank=True)
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="کاربر مسئول",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="responsible_quality_issues",
    )
    responsible_employee = models.ForeignKey(
        "workforce.Employee",
        verbose_name="کارمند مسئول",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="responsible_quality_issues",
    )
    responsible_party = models.ForeignKey(
        "parties.BusinessParty",
        verbose_name="طرف تجاری مسئول",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="responsible_quality_issues",
    )
    due_date = models.DateField("مهلت اقدام", null=True, blank=True, db_index=True)
    status = models.CharField(
        "وضعیت",
        max_length=24,
        choices=QualityIssueStatus.choices,
        default=QualityIssueStatus.REPORTED,
        db_index=True,
    )
    reviewed_at = models.DateTimeField("زمان بررسی", null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بررسی‌کننده",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quality_issues_reviewed",
    )
    submitted_for_verification_at = models.DateTimeField(
        "زمان ارسال برای راستی‌آزمایی", null=True, blank=True
    )
    submitted_for_verification_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ارسال‌کننده برای راستی‌آزمایی",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quality_issues_submitted_for_verification",
    )
    verification_summary = models.TextField("نتیجه راستی‌آزمایی", blank=True)
    verified_at = models.DateTimeField("زمان راستی‌آزمایی", null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="راستی‌آزمایی‌کننده",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quality_issues_verified",
    )
    closure_summary = models.TextField("جمع‌بندی بستن", blank=True)
    closed_at = models.DateTimeField("زمان بستن", null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="بسته‌شده توسط",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quality_issues_closed",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.PROTECT,
        related_name="quality_issues_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.PROTECT,
        related_name="quality_issues_updated",
    )

    objects = QualityIssueQuerySet.as_manager()

    class Meta:
        verbose_name = "مسئله کیفیت"
        verbose_name_plural = "مسائل کیفیت"
        ordering = ["-identified_at", "-created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "issue_number"],
                name="uq_quality_issue_org_number",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=QualityIssueStatus.CLOSED, closed_at__isnull=False)
                    | ~Q(status=QualityIssueStatus.CLOSED)
                ),
                name="quality_closed_requires_timestamp",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=QualityIssueStatus.VERIFIED, verified_at__isnull=False)
                    | Q(status=QualityIssueStatus.CLOSED, verified_at__isnull=False)
                    | ~Q(
                        status__in=[
                            QualityIssueStatus.VERIFIED,
                            QualityIssueStatus.CLOSED,
                        ]
                    )
                ),
                name="quality_verified_requires_time",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "status"],
                name="quality_org_project_status_idx",
            ),
            models.Index(
                fields=["organization", "severity", "status"],
                name="quality_org_sev_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.issue_number} - {self.get_issue_type_display()}"

    def clean(self) -> None:
        super().clean()
        self.issue_number = canonicalize_upper_identifier(self.issue_number)
        for field_name in (
            "description",
            "specification_reference",
            "corrective_action",
            "corrective_action_result",
            "verification_summary",
            "closure_summary",
        ):
            setattr(self, field_name, getattr(self, field_name).strip())
        if not self.issue_number or not self.description:
            raise ValidationError("شماره و شرح مسئله کیفیت الزامی است.")
        if self.identified_at and (
            timezone.is_naive(self.identified_at) or self.identified_at > timezone.now()
        ):
            raise ValidationError(
                {"identified_at": "زمان شناسایی باید timezone-aware و در گذشته باشد."}
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
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه مسئله باشد."})
        if self.phase_id and (not self.site_id or self.phase.site_id != self.site_id):
            raise ValidationError({"phase": "فاز باید متعلق به کارگاه مسئله باشد."})
        if self.activity_id:
            if self.activity.project_id != self.project_id:
                raise ValidationError(
                    {"activity": "فعالیت باید متعلق به پروژه مسئله باشد."}
                )
            if self.activity.site_id and self.activity.site_id != self.site_id:
                raise ValidationError(
                    {"activity": "کارگاه فعالیت با مسئله کیفیت سازگار نیست."}
                )
            if self.activity.phase_id and self.activity.phase_id != self.phase_id:
                raise ValidationError(
                    {"activity": "فاز فعالیت با مسئله کیفیت سازگار نیست."}
                )
        if self.daily_report_id:
            if self.daily_report.project_id != self.project_id:
                raise ValidationError(
                    {"daily_report": "گزارش روزانه باید متعلق به پروژه مسئله باشد."}
                )
            if self.daily_report.site_id != self.site_id:
                raise ValidationError(
                    {"daily_report": "کارگاه گزارش روزانه با مسئله سازگار نیست."}
                )
            if self.daily_report.phase_id != self.phase_id:
                raise ValidationError(
                    {"daily_report": "فاز گزارش روزانه با مسئله سازگار نیست."}
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
            "submitted_for_verification_by",
            "verified_by",
            "closed_by",
        ):
            user_id = getattr(self, f"{field_name}_id")
            if (
                user_id
                and not self.organization.memberships.filter(user_id=user_id).exists()
            ):
                raise ValidationError(
                    {field_name: "کاربر ثبت‌شده باید عضوی از همین سازمان باشد."}
                )
        if self.status != QualityIssueStatus.REPORTED and (
            not self.reviewed_at or not self.reviewed_by_id
        ):
            raise ValidationError("زمان و عامل بررسی مسئله کیفیت الزامی است.")
        assigned_statuses = {
            QualityIssueStatus.ASSIGNED,
            QualityIssueStatus.ACTION_IN_PROGRESS,
            QualityIssueStatus.AWAITING_VERIFICATION,
            QualityIssueStatus.VERIFIED,
            QualityIssueStatus.CLOSED,
        }
        if self.status in assigned_statuses and not any(
            (
                self.responsible_user_id,
                self.responsible_employee_id,
                self.responsible_party_id,
            )
        ):
            raise ValidationError("برای این وضعیت تعیین مسئول الزامی است.")
        if self.status in assigned_statuses and not self.due_date:
            raise ValidationError("مهلت انجام اقدام اصلاحی الزامی است.")
        action_statuses = assigned_statuses - {QualityIssueStatus.ASSIGNED}
        if self.status in action_statuses and not self.corrective_action:
            raise ValidationError("شرح اقدام اصلاحی الزامی است.")
        verification_pending_statuses = {
            QualityIssueStatus.AWAITING_VERIFICATION,
            QualityIssueStatus.VERIFIED,
            QualityIssueStatus.CLOSED,
        }
        if self.status in verification_pending_statuses and (
            not self.corrective_action_result
            or not self.submitted_for_verification_at
            or not self.submitted_for_verification_by_id
        ):
            raise ValidationError("نتیجه و اطلاعات ارسال برای راستی‌آزمایی الزامی است.")
        if self.status in {QualityIssueStatus.VERIFIED, QualityIssueStatus.CLOSED} and (
            not self.verification_summary
            or not self.verified_at
            or not self.verified_by_id
        ):
            raise ValidationError("نتیجه، زمان و عامل راستی‌آزمایی الزامی است.")
        if self.status == QualityIssueStatus.CLOSED and (
            not self.closure_summary or not self.closed_at or not self.closed_by_id
        ):
            raise ValidationError("جمع‌بندی، زمان و عامل بستن مسئله الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self._state.adding and self.status != QualityIssueStatus.REPORTED:
            raise ValidationError("مسئله جدید باید در وضعیت ثبت‌شده ایجاد شود.")
        if self.pk and not self._state.adding:
            previous_status = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )
            if previous_status == QualityIssueStatus.CLOSED:
                raise ValidationError("مسئله کیفیت بسته‌شده قابل تغییر نیست.")
            if previous_status != self.status and not getattr(
                self, "_service_transition", False
            ):
                raise ValidationError("تغییر وضعیت فقط از طریق سرویس کیفیت مجاز است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("سوابق مسائل کیفیت قابل حذف نیستند.")
