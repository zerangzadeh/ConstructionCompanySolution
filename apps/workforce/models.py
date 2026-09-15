import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.accounts.models import validate_profile_image
from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


def employee_profile_image_upload_path(instance: "Employee", filename: str) -> str:
    """Store employee images under opaque tenant-scoped names."""

    extension = Path(filename).suffix.lower()
    return (
        f"organizations/{instance.organization_id}/employees/{instance.pk}/"
        f"profile/{uuid.uuid4()}{extension}"
    )


class EmployeeStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    INACTIVE = "inactive", "غیرفعال"
    TERMINATED = "terminated", "خاتمه همکاری"


class AssignmentStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    COMPLETED = "completed", "پایان تخصیص"
    CANCELLED = "cancelled", "لغوشده"


class PositionAssignmentStatus(models.TextChoices):
    ACTIVE = "active", "فعال"
    ENDED = "ended", "پایان‌یافته"


class Department(UUIDModel, TimeStampedModel):
    """An optional tenant-owned organizational unit."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="departments",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="واحد سازمانی والد",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    code = models.CharField("کد واحد سازمانی", max_length=50)
    name = models.CharField("نام واحد سازمانی", max_length=255)
    description = models.TextField("شرح", blank=True)
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments_updated",
    )

    class Meta:
        verbose_name = "واحد سازمانی"
        verbose_name_plural = "واحدهای سازمانی"
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
            raise ValidationError("وارد کردن کد و نام واحد سازمانی الزامی است.")
        if self.parent_id:
            validate_related_organizations(self, parent=self.parent)
            if self.parent_id == self.pk:
                raise ValidationError(
                    {"parent": "واحد سازمانی نمی‌تواند والد خودش باشد."}
                )
            ancestor = self.parent
            visited: set[object] = {self.pk}
            while ancestor is not None:
                if ancestor.pk in visited:
                    raise ValidationError(
                        {"parent": "ساختار واحدهای سازمانی نمی‌تواند شامل چرخه باشد."}
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
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="positions",
    )
    department = models.ForeignKey(
        Department,
        verbose_name="واحد سازمانی",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="positions",
    )
    code = models.CharField("کد سمت", max_length=50)
    title = models.CharField("عنوان سمت", max_length=255)
    description = models.TextField("شرح", blank=True)
    is_single_holder = models.BooleanField(
        "سمت تک‌متصدی",
        default=False,
        help_text="برای سمت‌هایی مانند مدیرعامل که فقط یک متصدی فعال دارند.",
    )
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positions_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positions_updated",
    )

    class Meta:
        verbose_name = "سمت شغلی"
        verbose_name_plural = "سمت‌های شغلی"
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
            raise ValidationError("وارد کردن کد و عنوان سمت شغلی الزامی است.")
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
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="work_teams",
    )
    department = models.ForeignKey(
        Department,
        verbose_name="واحد سازمانی",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="work_teams",
    )
    lead = models.ForeignKey(
        "Employee",
        verbose_name="سرپرست گروه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="teams_led",
    )
    code = models.CharField("کد گروه کاری", max_length=50)
    name = models.CharField("نام گروه کاری", max_length=255)
    description = models.TextField("شرح", blank=True)
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_teams_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_teams_updated",
    )

    class Meta:
        verbose_name = "گروه کاری"
        verbose_name_plural = "گروه‌های کاری"
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
            raise ValidationError("وارد کردن کد و نام گروه کاری الزامی است.")
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
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="employees",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="حساب کاربری",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_profiles",
    )
    department = models.ForeignKey(
        Department,
        verbose_name="واحد سازمانی",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employees",
    )
    position = models.ForeignKey(
        Position,
        verbose_name="سمت شغلی",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employees",
    )
    work_team = models.ForeignKey(
        WorkTeam,
        verbose_name="گروه کاری",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="members",
    )
    employee_number = models.CharField("شماره پرسنلی", max_length=50)
    first_name = models.CharField("نام", max_length=150)
    last_name = models.CharField("نام خانوادگی", max_length=150)
    email = models.EmailField("ایمیل", blank=True)
    phone_number = models.CharField("شماره تلفن", max_length=32, blank=True)
    profile_image = models.FileField(
        "عکس پرسنلی",
        upload_to=employee_profile_image_upload_path,
        validators=[validate_profile_image],
        max_length=255,
        blank=True,
        help_text="فرمت PNG، JPEG یا WebP با حداکثر حجم ۲ مگابایت.",
    )
    hire_date = models.DateField("تاریخ استخدام", null=True, blank=True)
    termination_date = models.DateField("تاریخ خاتمه همکاری", null=True, blank=True)
    status = models.CharField(
        "وضعیت اشتغال",
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.ACTIVE,
        db_index=True,
    )
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees_updated",
    )

    class Meta:
        verbose_name = "کارمند"
        verbose_name_plural = "کارکنان"
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
                "وارد کردن شماره پرسنلی، نام و نام خانوادگی الزامی است."
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
                {"position": "سمت شغلی باید متعلق به واحد سازمانی انتخاب‌شده باشد."}
            )
        if (
            self.user_id
            and not self.organization.memberships.filter(
                user_id=self.user_id,
                status="active",
            ).exists()
        ):
            raise ValidationError(
                {"user": "حساب کاربری کارمند باید عضو فعال سازمان باشد."}
            )
        if (
            self.hire_date
            and self.termination_date
            and self.termination_date < self.hire_date
        ):
            raise ValidationError(
                {
                    "termination_date": "تاریخ خاتمه همکاری نمی‌تواند پیش از تاریخ استخدام باشد."
                }
            )
        if self.status == EmployeeStatus.TERMINATED and not self.termination_date:
            raise ValidationError(
                {
                    "termination_date": "برای وضعیت خاتمه همکاری، وارد کردن تاریخ الزامی است."
                }
            )
        if self.status != EmployeeStatus.TERMINATED and self.termination_date:
            raise ValidationError(
                {
                    "termination_date": "تاریخ خاتمه همکاری فقط برای کارکنان خاتمه‌یافته مجاز است."
                }
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.employee_number} - {self.first_name} {self.last_name}"


class EmployeePositionAssignment(UUIDModel, TimeStampedModel):
    """A dated, tenant-safe job-position assignment for an employee."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="employee_position_assignments",
    )
    employee = models.ForeignKey(
        Employee,
        verbose_name="کارمند",
        on_delete=models.PROTECT,
        related_name="position_assignments",
    )
    position = models.ForeignKey(
        Position,
        verbose_name="سمت شغلی",
        on_delete=models.PROTECT,
        related_name="employee_assignments",
    )
    start_date = models.DateField("تاریخ شروع")
    end_date = models.DateField("تاریخ پایان", null=True, blank=True)
    status = models.CharField(
        "وضعیت تخصیص سمت",
        max_length=20,
        choices=PositionAssignmentStatus.choices,
        default=PositionAssignmentStatus.ACTIVE,
        db_index=True,
    )
    is_primary = models.BooleanField("سمت اصلی", default=False)
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_position_assignments_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_position_assignments_updated",
    )

    class Meta:
        verbose_name = "تخصیص سمت شغلی کارمند"
        verbose_name_plural = "تخصیص‌های سمت شغلی کارکنان"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["employee", "position"],
                condition=Q(status=PositionAssignmentStatus.ACTIVE),
                name="unique_active_employee_position",
            ),
            models.UniqueConstraint(
                fields=["employee"],
                condition=Q(
                    status=PositionAssignmentStatus.ACTIVE,
                    is_primary=True,
                ),
                name="unique_active_primary_position",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=PositionAssignmentStatus.ACTIVE, end_date__isnull=True)
                    | Q(status=PositionAssignmentStatus.ENDED, end_date__isnull=False)
                ),
                name="employee_position_status_dates",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True)
                | Q(end_date__gte=models.F("start_date")),
                name="employee_position_date_order",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "employee", "status"],
                name="employee_pos_org_emp_idx",
            ),
            models.Index(
                fields=["organization", "position", "status"],
                name="employee_pos_org_role_idx",
            ),
        ]
        ordering = ["-is_primary", "-start_date", "position__title"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(
            self,
            employee=self.employee if self.employee_id else None,
            position=self.position if self.position_id else None,
        )
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": "تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد."}
            )
        if self.status == PositionAssignmentStatus.ACTIVE and self.end_date:
            raise ValidationError(
                {"end_date": "تخصیص فعال سمت نمی‌تواند تاریخ پایان داشته باشد."}
            )
        if self.status == PositionAssignmentStatus.ENDED and not self.end_date:
            raise ValidationError(
                {"end_date": "برای تخصیص پایان‌یافته، تاریخ پایان الزامی است."}
            )
        if self.status == PositionAssignmentStatus.ENDED and self.is_primary:
            raise ValidationError(
                {"is_primary": "تخصیص پایان‌یافته نمی‌تواند سمت اصلی باشد."}
            )
        if (
            self.status == PositionAssignmentStatus.ACTIVE
            and self.position_id
            and self.position.is_single_holder
            and EmployeePositionAssignment.objects.filter(
                organization_id=self.organization_id,
                position_id=self.position_id,
                status=PositionAssignmentStatus.ACTIVE,
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                {"position": "این سمت تک‌متصدی در حال حاضر متصدی فعال دارد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.employee} · {self.position}"


class EmployeeProjectAssignment(UUIDModel, TimeStampedModel):
    """An employee's tenant-safe assignment to a project and optional worksite."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="employee_project_assignments",
    )
    employee = models.ForeignKey(
        Employee,
        verbose_name="کارمند",
        on_delete=models.PROTECT,
        related_name="project_assignments",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.PROTECT,
        related_name="employee_assignments",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        verbose_name="کارگاه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="employee_assignments",
    )
    role_title = models.CharField("مسئولیت در پروژه", max_length=255, blank=True)
    start_date = models.DateField("تاریخ شروع تخصیص")
    end_date = models.DateField("تاریخ پایان تخصیص", null=True, blank=True)
    status = models.CharField(
        "وضعیت تخصیص",
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.ACTIVE,
        db_index=True,
    )
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_project_assignments_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_project_assignments_updated",
    )

    class Meta:
        verbose_name = "تخصیص کارمند به پروژه"
        verbose_name_plural = "تخصیص کارکنان به پروژه‌ها"
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
            raise ValidationError({"site": "کارگاه باید متعلق به پروژه باشد."})
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": "تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد."}
            )
        if self.status == AssignmentStatus.ACTIVE and self.end_date:
            raise ValidationError(
                {"end_date": "تخصیص فعال نمی‌تواند تاریخ پایان داشته باشد."}
            )
        if self.status != AssignmentStatus.ACTIVE and not self.end_date:
            raise ValidationError(
                {"end_date": "برای تخصیص پایان‌یافته یا لغوشده، تاریخ پایان الزامی است."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.employee} · {self.project}"
