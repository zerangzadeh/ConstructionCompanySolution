from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


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

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

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

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        if self.project_id:
            validate_related_organizations(self, project=self.project)

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

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

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        if self.site_id:
            validate_related_organizations(self, site=self.site)

    def save(self, *args: object, **kwargs: object) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.site.code} · {self.code} - {self.name}"


class WBSNode(UUIDModel, TimeStampedModel):
    """A project-specific work-breakdown node, separate from project phases."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="wbs_nodes"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="wbs_nodes"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    code = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wbs_nodes_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wbs_nodes_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["project", "code"], name="unique_wbs_code_per_project"
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "is_active"],
                name="wbs_org_project_active_idx",
            ),
            models.Index(
                fields=["project", "parent", "sort_order"],
                name="wbs_project_parent_order_idx",
            ),
        ]
        ordering = ["sort_order", "code"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.title = self.title.strip()
        if not self.code or not self.title:
            raise ValidationError("WBS code and title are required.")
        if self.project_id:
            validate_related_organizations(self, project=self.project)
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError(
                    {"parent": "A WBS node cannot be its own parent."}
                )
            if (
                self.parent.organization_id != self.organization_id
                or self.parent.project_id != self.project_id
            ):
                raise ValidationError(
                    {"parent": "Parent WBS node must belong to the same project."}
                )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} — {self.title}"


class ActivityStatus(models.TextChoices):
    PLANNING = "planning", "Planning"
    ACTIVE = "active", "Active"
    ON_HOLD = "on_hold", "On hold"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class Activity(UUIDModel, TimeStampedModel):
    """A planned work item in a project's WBS, optionally scoped to site/phase."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="activities",
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="activities"
    )
    wbs_node = models.ForeignKey(
        WBSNode, on_delete=models.PROTECT, related_name="activities"
    )
    site = models.ForeignKey(
        ProjectSite,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="activities",
    )
    phase = models.ForeignKey(
        ProjectPhase,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="activities",
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="activities",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    planned_quantity = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    planned_start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ActivityStatus.choices,
        default=ActivityStatus.PLANNING,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["project", "code"], name="unique_activity_code_per_project"
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "status"],
                name="activity_org_proj_status_idx",
            ),
            models.Index(
                fields=["organization", "wbs_node"], name="activity_org_wbs_idx"
            ),
        ]
        ordering = ["code"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("Activity code and name are required.")
        if self.project_id and self.wbs_node_id:
            validate_related_organizations(
                self, project=self.project, wbs_node=self.wbs_node
            )
            if self.wbs_node.project_id != self.project_id:
                raise ValidationError(
                    {"wbs_node": "WBS node must belong to the same project."}
                )
        if self.site_id:
            validate_related_organizations(self, site=self.site)
            if self.project_id and self.site.project_id != self.project_id:
                raise ValidationError(
                    {"site": "Worksite must belong to the same project."}
                )
        if self.phase_id:
            validate_related_organizations(self, phase=self.phase)
            if not self.site_id or self.phase.site_id != self.site_id:
                raise ValidationError(
                    {"phase": "Phase must belong to the selected worksite."}
                )
        if self.unit_of_measure_id:
            validate_related_organizations(self, unit_of_measure=self.unit_of_measure)
            if not self.unit_of_measure.is_active or self.unit_of_measure.archived_at:
                raise ValidationError(
                    {"unit_of_measure": "Unit of measure must be active."}
                )
        if self.planned_quantity is not None:
            if self.planned_quantity <= 0:
                raise ValidationError(
                    {"planned_quantity": "Planned quantity must be positive."}
                )
            if not self.unit_of_measure_id:
                raise ValidationError(
                    {"unit_of_measure": "A unit is required for planned quantity."}
                )
        elif self.unit_of_measure_id:
            raise ValidationError(
                {"planned_quantity": "Planned quantity is required with a unit."}
            )
        if (
            self.planned_start_date
            and self.planned_end_date
            and self.planned_end_date < self.planned_start_date
        ):
            raise ValidationError(
                {"planned_end_date": "Activity end date cannot be before start date."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"
