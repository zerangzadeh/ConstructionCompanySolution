from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import CreatedAtModel, TimeStampedModel, UUIDModel


class DailyReportStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"


class DailyReport(UUIDModel, TimeStampedModel):
    """An operational report for one project on one reporting date."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="daily_reports",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="daily_reports",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        related_name="daily_reports",
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_reports",
    )
    reporting_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=DailyReportStatus.choices,
        default=DailyReportStatus.DRAFT,
        db_index=True,
    )
    weather_conditions = models.CharField(max_length=255, blank=True)
    labor_count = models.PositiveIntegerField(default=0)
    work_performed = models.TextField()
    progress_summary = models.TextField(blank=True)
    issues_and_delays = models.TextField(blank=True)
    safety_notes = models.TextField(blank=True)
    quality_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_reports_approved",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_reports_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_reports_updated",
    )

    class Meta:
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


class DailyReportLaborEntry(UUIDModel, CreatedAtModel):
    """Labor recorded against a daily report while it is still a draft."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="daily_report_labor_entries",
    )
    report = models.ForeignKey(
        DailyReport,
        on_delete=models.CASCADE,
        related_name="labor_entries",
    )
    team_name = models.CharField(max_length=120)
    worker_count = models.PositiveIntegerField()
    hours_worked = models.DecimalField(max_digits=8, decimal_places=2)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_report_labor_entries_created",
    )

    class Meta:
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "report"],
                name="daily_labor_org_report_idx",
            ),
        ]
        ordering = ["created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.team_name} ({self.worker_count})"


class DailyReportEquipmentEntry(UUIDModel, CreatedAtModel):
    """Equipment usage recorded against a daily report draft."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="daily_report_equipment_entries",
    )
    report = models.ForeignKey(
        DailyReport,
        on_delete=models.CASCADE,
        related_name="equipment_entries",
    )
    equipment_name = models.CharField(max_length=255)
    hours_used = models.DecimalField(max_digits=8, decimal_places=2)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_report_equipment_entries_created",
    )

    class Meta:
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "report"],
                name="daily_equipment_org_report_idx",
            ),
        ]
        ordering = ["created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.equipment_name} ({self.hours_used} h)"


class DailyReportMaterialEntry(UUIDModel, CreatedAtModel):
    """Material consumption recorded against a daily report draft."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="daily_report_material_entries",
    )
    report = models.ForeignKey(
        DailyReport,
        on_delete=models.CASCADE,
        related_name="material_entries",
    )
    material_name = models.CharField(max_length=255)
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0.0000"),
    )
    unit = models.CharField(max_length=30)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_report_material_entries_created",
    )

    class Meta:
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "report"],
                name="daily_material_org_report_idx",
            ),
        ]
        ordering = ["created_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.material_name} ({self.quantity} {self.unit})"
