from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class EmployeeStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    TERMINATED = "terminated", "Terminated"


class AssignmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class Department(UUIDModel, TimeStampedModel):
    """An optional tenant-owned organizational unit."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="departments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_department_code_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "is_active"],
                name="department_org_active_idx",
            ),
        ]
        ordering = ["name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("Department code and name are required.")
        if self.parent_id:
            validate_related_organizations(self, parent=self.parent)
            if self.parent_id == self.pk:
                raise ValidationError(
                    {"parent": "A department cannot be its own parent."}
                )
            ancestor = self.parent
            visited: set[object] = {self.pk}
            while ancestor is not None:
                if ancestor.pk in visited:
                    raise ValidationError(
                        {"parent": "A department hierarchy cannot contain a cycle."}
                    )
                visited.add(ancestor.pk)
                ancestor = ancestor.parent

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Position(UUIDModel, TimeStampedModel):
    """A tenant-owned job position, optionally attached to a department."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="positions",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="positions",
    )
    code = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positions_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positions_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_position_code_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "is_active"],
                name="position_org_active_idx",
            ),
        ]
        ordering = ["title"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.title = self.title.strip()
        if not self.code or not self.title:
            raise ValidationError("Position code and title are required.")
        if self.department_id:
            validate_related_organizations(self, department=self.department)

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} - {self.title}"


class WorkTeam(UUIDModel, TimeStampedModel):
    """A tenant-owned team with an optional department and employee lead."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="work_teams",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="work_teams",
    )
    lead = models.ForeignKey(
        "Employee",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="teams_led",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_teams_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_teams_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_work_team_code_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "is_active"],
                name="work_team_org_active_idx",
            ),
        ]
        ordering = ["name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("Work team code and name are required.")
        relations = {}
        if self.department_id:
            relations["department"] = self.department
        if self.lead_id:
            relations["lead"] = self.lead
        validate_related_organizations(self, **relations)

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Employee(UUIDModel, TimeStampedModel):
    """Personnel data kept separate from optional authentication identity."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="employees",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_profiles",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employees",
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employees",
    )
    work_team = models.ForeignKey(
        WorkTeam,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="members",
    )
    employee_number = models.CharField(max_length=50)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    termination_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.ACTIVE,
        db_index=True,
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "employee_number"],
                name="unique_employee_number_per_organization",
            ),
            models.UniqueConstraint(
                fields=["organization", "user"],
                condition=Q(user__isnull=False),
                name="unique_employee_user_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status"],
                name="employee_org_status_idx",
            ),
            models.Index(
                fields=["organization", "archived_at"],
                name="employee_org_archived_idx",
            ),
        ]
        ordering = ["last_name", "first_name", "employee_number"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.employee_number = canonicalize_upper_identifier(self.employee_number)
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        if not self.employee_number or not self.first_name or not self.last_name:
            raise ValidationError(
                "Employee number, first name, and last name are required."
            )
        relations = {}
        if self.department_id:
            relations["department"] = self.department
        if self.position_id:
            relations["position"] = self.position
        if self.work_team_id:
            relations["work_team"] = self.work_team
        validate_related_organizations(self, **relations)
        if (
            self.position_id
            and self.department_id
            and self.position.department_id
            and self.position.department_id != self.department_id
        ):
            raise ValidationError(
                {"position": "Position must belong to the selected department."}
            )
        if (
            self.user_id
            and not self.organization.memberships.filter(
                user_id=self.user_id,
                status="active",
            ).exists()
        ):
            raise ValidationError(
                {"user": "Employee user must be an active organization member."}
            )
        if (
            self.hire_date
            and self.termination_date
            and self.termination_date < self.hire_date
        ):
            raise ValidationError(
                {"termination_date": "Termination date cannot be before hire date."}
            )
        if self.status == EmployeeStatus.TERMINATED and not self.termination_date:
            raise ValidationError(
                {"termination_date": "Termination date is required when terminated."}
            )
        if self.status != EmployeeStatus.TERMINATED and self.termination_date:
            raise ValidationError(
                {"termination_date": "Only terminated employees can have this date."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.employee_number} - {self.first_name} {self.last_name}"


class EmployeeProjectAssignment(UUIDModel, TimeStampedModel):
    """An employee's tenant-safe assignment to a project and optional worksite."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="employee_project_assignments",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="project_assignments",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="employee_assignments",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employee_assignments",
    )
    role_title = models.CharField(max_length=255, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.ACTIVE,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_project_assignments_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_project_assignments_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["employee", "project"],
                condition=Q(status=AssignmentStatus.ACTIVE, site__isnull=True),
                name="unique_active_employee_project_assignment",
            ),
            models.UniqueConstraint(
                fields=["employee", "project", "site"],
                condition=Q(status=AssignmentStatus.ACTIVE, site__isnull=False),
                name="unique_active_employee_site_assignment",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "status"],
                name="employee_assign_org_proj_idx",
            ),
        ]
        ordering = ["-start_date", "employee__last_name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            employee=self.employee if self.employee_id else None,
            project=self.project if self.project_id else None,
            site=self.site if self.site_id else None,
        )
        if self.site_id and self.project_id and self.site.project_id != self.project_id:
            raise ValidationError({"site": "Worksite must belong to the project."})
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})
        if self.status == AssignmentStatus.ACTIVE and self.end_date:
            raise ValidationError(
                {"end_date": "Active assignments cannot have an end date."}
            )
        if self.status != AssignmentStatus.ACTIVE and not self.end_date:
            raise ValidationError(
                {"end_date": "Completed or cancelled assignments require an end date."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.employee} · {self.project}"
