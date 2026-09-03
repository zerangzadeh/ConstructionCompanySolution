from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel, UUIDModel


class ProjectStatus(models.TextChoices):
    PLANNING = "planning", "Planning"
    ACTIVE = "active", "Active"
    ON_HOLD = "on_hold", "On hold"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class Project(UUIDModel, TimeStampedModel):
    """A construction project belonging to exactly one organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="projects",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=ProjectStatus.choices,
        default=ProjectStatus.PLANNING,
        db_index=True,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects_updated",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_project_code_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status"],
                name="project_org_status_idx",
            ),
            models.Index(
                fields=["organization", "deleted_at"],
                name="project_org_deleted_idx",
            ),
        ]
        ordering = ["name"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class ProjectSite(UUIDModel, TimeStampedModel):
    """A worksite belonging to one project and its organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="project_sites",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="sites",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_sites_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_sites_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "project", "code"],
                name="unique_site_code_per_project",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "is_active"],
                name="site_org_project_active_idx",
            ),
        ]
        ordering = ["name"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.project.code} · {self.code} - {self.name}"


class ProjectPhaseStatus(models.TextChoices):
    PLANNING = "planning", "Planning"
    ACTIVE = "active", "Active"
    ON_HOLD = "on_hold", "On hold"
    COMPLETED = "completed", "Completed"


class ProjectPhase(UUIDModel, TimeStampedModel):
    """A planned or active execution phase within one project worksite."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="project_phases",
    )
    site = models.ForeignKey(
        ProjectSite,
        on_delete=models.CASCADE,
        related_name="phases",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=ProjectPhaseStatus.choices,
        default=ProjectPhaseStatus.PLANNING,
        db_index=True,
    )
    planned_start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_phases_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_phases_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "site", "code"],
                name="unique_phase_code_per_site",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "site", "status"],
                name="phase_org_site_status_idx",
            ),
        ]
        ordering = ["name"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.site.code} · {self.code} - {self.name}"
