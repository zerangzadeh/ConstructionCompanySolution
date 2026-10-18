import uuid
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import validate_profile_image
from apps.documents.models import AbstractTypedDocumentLink
from core.identifiers import canonicalize_upper_identifier
from core.models import CreatedAtModel, TimeStampedModel, UUIDModel
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


class QualificationKind(models.TextChoices):
    QUALIFICATION = "qualification", "صلاحیت"
    CERTIFICATE = "certificate", "گواهی"
    LICENSE = "license", "مجوز"


class QualificationLifecycleEventKind(models.TextChoices):
    ISSUED = "issued", "ثبت‌شده"
    REVOKED = "revoked", "لغوشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class TrainingOutcome(models.TextChoices):
    ATTENDED = "attended", "شرکت‌کرده"
    COMPLETED = "completed", "تکمیل‌شده"
    NOT_COMPLETED = "not_completed", "تکمیل‌نشده"


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
    parent_position = models.ForeignKey(
        "self",
        verbose_name="سمت بالادست",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="child_positions",
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
        if self.parent_position_id:
            validate_related_organizations(self, parent_position=self.parent_position)
            if self.parent_position_id == self.pk:
                raise ValidationError(
                    {"parent_position": "سمت شغلی نمی‌تواند والد خودش باشد."}
                )
            if (
                not self.parent_position.is_active
                or self.parent_position.archived_at is not None
            ):
                raise ValidationError(
                    {"parent_position": "سمت بالادست باید فعال و بایگانی‌نشده باشد."}
                )
            ancestor = self.parent_position
            visited: set[object] = {self.pk}
            while ancestor is not None:
                if ancestor.pk in visited:
                    raise ValidationError(
                        {"parent_position": "ساختار سمت‌ها نمی‌تواند شامل چرخه باشد."}
                    )
                visited.add(ancestor.pk)
                ancestor = ancestor.parent_position

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
    address = models.TextField("نشانی", blank=True, max_length=1000)
    emergency_contact = models.TextField("تماس اضطراری", blank=True, max_length=1000)
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


class Person(UUIDModel, TimeStampedModel):
    """Stable tenant-owned worker identity, independent of employment episodes."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="people"
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workforce_people",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "user"],
                condition=Q(user__isnull=False),
                name="unique_person_user_per_org",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        if not self.first_name or not self.last_name:
            raise ValidationError("Person name is required.")
        if (
            self.user_id
            and not self.organization.memberships.filter(
                user_id=self.user_id, status="active"
            ).exists()
        ):
            raise ValidationError(
                {"user": "User must be an active organization member."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class WorkRelationship(UUIDModel, TimeStampedModel):
    """One effective-dated episode; identity fields cannot be rewritten."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="work_relationships",
    )
    person = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="work_relationships"
    )
    employee_number = models.CharField(max_length=50)
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)
    legacy_employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="work_relationships",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(effective_end__isnull=True)
                | Q(effective_end__gte=models.F("effective_start")),
                name="work_rel_end_not_before_start",
            ),
            models.UniqueConstraint(
                fields=["person", "organization", "effective_start"],
                name="unique_work_rel_person_start",
            ),
            models.UniqueConstraint(
                fields=["organization", "employee_number", "effective_start"],
                name="unique_work_rel_number_start",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "person", "effective_start"],
                name="work_rel_org_person_start_idx",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.employee_number = canonicalize_upper_identifier(self.employee_number)
        if not self.employee_number:
            raise ValidationError({"employee_number": "Employee number is required."})
        if self.effective_end and self.effective_end < self.effective_start:
            raise ValidationError({"effective_end": "End cannot precede start."})
        relations = {"person": self.person}
        if self.legacy_employee_id:
            relations["legacy_employee"] = self.legacy_employee
            if self.legacy_employee.employee_number != self.employee_number:
                raise ValidationError(
                    {
                        "legacy_employee": "Employee number does not match legacy identity."
                    }
                )
            if WorkRelationship.objects.filter(
                legacy_employee_id=self.legacy_employee_id
            ).exclude(person_id=self.person_id).exists():
                raise ValidationError(
                    {"legacy_employee": "Legacy Employee is linked to another Person."}
                )
            if (
                self.person.user_id
                and self.legacy_employee.user_id
                and self.person.user_id != self.legacy_employee.user_id
            ):
                raise ValidationError(
                    {"legacy_employee": "Legacy User link conflicts with Person."}
                )
        validate_related_organizations(self, **relations)

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        if self._state.adding is False:
            raise ValidationError(
                "WorkRelationship changes require a versioned service."
            )
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("WorkRelationship history cannot be deleted.")


class WorkRelationshipRevision(UUIDModel):
    """Append-only effective-date snapshot for an episode."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="work_relationship_revisions",
    )
    relationship = models.ForeignKey(
        WorkRelationship, on_delete=models.PROTECT, related_name="revisions"
    )
    version = models.PositiveIntegerField()
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="work_relationship_revisions",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["relationship", "version"], name="unique_work_rel_revision"
            ),
            models.CheckConstraint(
                condition=Q(effective_end__isnull=True)
                | Q(effective_end__gte=models.F("effective_start")),
                name="work_rel_revision_dates_valid",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, relationship=self.relationship)
        if self.effective_start != self.relationship.effective_start:
            raise ValidationError(
                {"effective_start": "Revision start must match episode."}
            )
        if self.effective_end != self.relationship.effective_end:
            raise ValidationError(
                {"effective_end": "Revision end must match episode state."}
            )
        if self.effective_end and self.effective_end < self.effective_start:
            raise ValidationError({"effective_end": "End cannot precede start."})
        next_version = (
            WorkRelationshipRevision.objects.filter(relationship=self.relationship)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
            or 0
        ) + 1
        if self.version != next_version:
            raise ValidationError({"version": "Revision version must be consecutive."})
        if not self.organization.memberships.filter(
            user_id=self.recorded_by_id, status="active"
        ).exists():
            raise ValidationError(
                {"recorded_by": "Actor must be an active organization member."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("WorkRelationship revisions are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("WorkRelationship revisions cannot be deleted.")


class WorkforceCatalogueBase(UUIDModel, TimeStampedModel):
    """Shared tenant-safe catalogue fields for Workforce reference facts."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="+"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        abstract = True
        ordering = ["name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("کد و نام باید وارد شوند.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)


class Skill(WorkforceCatalogueBase):
    """Workforce-owned skill definition; never an authorization grant."""

    class Meta(WorkforceCatalogueBase.Meta):
        verbose_name = "مهارت"
        verbose_name_plural = "مهارت‌ها"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(fields=["organization", "code"], name="workforce_skill_org_code_uq")
        ]


class Competency(WorkforceCatalogueBase):
    """Workforce-owned competency definition; never an authorization grant."""

    class Meta(WorkforceCatalogueBase.Meta):
        verbose_name = "شایستگی"
        verbose_name_plural = "شایستگی‌ها"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(fields=["organization", "code"], name="workforce_competency_org_code_uq")
        ]


class EmployeeSkillRecord(UUIDModel, TimeStampedModel):
    """Append-only, effective-dated employee proficiency history."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="employee_skill_records")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="skill_records")
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT, related_name="employee_records")
    competency = models.ForeignKey(Competency, on_delete=models.PROTECT, null=True, blank=True, related_name="employee_skill_records")
    proficiency_level = models.PositiveSmallIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="employee_skill_records_recorded")

    class Meta:
        verbose_name = "سابقه مهارت کارمند"
        verbose_name_plural = "سوابق مهارت کارکنان"
        constraints = [  # noqa: RUF012
            models.CheckConstraint(condition=Q(proficiency_level__gte=1, proficiency_level__lte=5), name="employee_skill_proficiency_range"),
            models.CheckConstraint(condition=Q(effective_to__isnull=True) | Q(effective_to__gte=models.F("effective_from")), name="employee_skill_effective_dates"),
        ]
        indexes = [models.Index(fields=["organization", "employee", "skill", "effective_from"], name="employee_skill_effective_idx")]  # noqa: RUF012
        ordering = ["employee", "skill", "-effective_from"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, employee=self.employee, skill=self.skill, competency=self.competency)
        if not 1 <= self.proficiency_level <= 5:
            raise ValidationError({"proficiency_level": "سطح مهارت باید بین ۱ تا ۵ باشد."})
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("سابقه مهارت تغییرپذیر نیست؛ سابقه اصلاحی جدید ثبت کنید.")
        self.full_clean()
        super().save(*args, **kwargs)


class EmployeeQualification(UUIDModel, TimeStampedModel):
    """Immutable qualification/certificate/license fact for one employee."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="employee_qualifications")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="qualifications")
    kind = models.CharField(max_length=20, choices=QualificationKind.choices)
    title = models.CharField(max_length=255)
    issuer = models.CharField(max_length=255, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="employee_qualifications_recorded")

    class Meta:
        verbose_name = "صلاحیت کارمند"
        verbose_name_plural = "صلاحیت‌های کارکنان"
        constraints = [  # noqa: RUF012
            models.CheckConstraint(condition=Q(valid_until__isnull=True) | Q(issued_on__isnull=True) | Q(valid_until__gte=models.F("issued_on")), name="employee_qualification_validity_dates"),
        ]
        indexes = [models.Index(fields=["organization", "employee", "valid_until"], name="employee_qualification_idx")]  # noqa: RUF012
        ordering = ["employee", "title", "-issued_on"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, employee=self.employee)
        self.title = self.title.strip()
        self.issuer = self.issuer.strip()
        self.reference_number = self.reference_number.strip()
        if not self.title:
            raise ValidationError({"title": "عنوان صلاحیت الزامی است."})
        if self.issued_on and self.valid_until and self.valid_until < self.issued_on:
            raise ValidationError({"valid_until": "تاریخ اعتبار نمی‌تواند پیش از صدور باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("صلاحیت ثبت‌شده تغییرپذیر نیست؛ رویداد اصلاحی یا ابطال ثبت کنید.")
        self.full_clean()
        super().save(*args, **kwargs)

    def is_valid_on(self, on_date: date) -> bool:
        if self.valid_until and self.valid_until < on_date:
            return False
        return not self.lifecycle_events.filter(kind__in=[QualificationLifecycleEventKind.REVOKED, QualificationLifecycleEventKind.SUPERSEDED]).exists()

    @property
    def validity_status(self) -> str:
        if self.lifecycle_events.filter(
            kind__in=[
                QualificationLifecycleEventKind.REVOKED,
                QualificationLifecycleEventKind.SUPERSEDED,
            ]
        ).exists():
            return "revoked"
        if self.valid_until and self.valid_until < timezone.localdate():
            return "expired"
        return "valid"


class EmployeeQualificationLifecycleEvent(UUIDModel, TimeStampedModel):
    """Append-only revocation/supersession history for a qualification fact."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="employee_qualification_events")
    qualification = models.ForeignKey(EmployeeQualification, on_delete=models.PROTECT, related_name="lifecycle_events")
    kind = models.CharField(max_length=20, choices=QualificationLifecycleEventKind.choices)
    occurred_on = models.DateField()
    reason = models.TextField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="employee_qualification_events_recorded")

    class Meta:
        verbose_name = "رویداد صلاحیت کارمند"
        verbose_name_plural = "رویدادهای صلاحیت کارکنان"
        constraints = [models.UniqueConstraint(fields=["qualification", "kind"], name="employee_qualification_event_once_uq")]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, qualification=self.qualification)
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValidationError({"reason": "علت رویداد الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("رویداد صلاحیت تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class TrainingRequirement(WorkforceCatalogueBase):
    competency = models.ForeignKey(Competency, on_delete=models.PROTECT, null=True, blank=True, related_name="training_requirements")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, null=True, blank=True, related_name="training_requirements")
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, null=True, blank=True, related_name="training_requirements")

    class Meta(WorkforceCatalogueBase.Meta):
        verbose_name = "الزام آموزشی"
        verbose_name_plural = "الزامات آموزشی"
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="training_requirement_org_code_uq")]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, competency=self.competency, position=self.position, project=self.project)


class EmployeeTrainingRecord(UUIDModel, TimeStampedModel):
    """Immutable attendance/completion evidence for a training requirement."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="employee_training_records")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="training_records")
    requirement = models.ForeignKey(TrainingRequirement, on_delete=models.PROTECT, related_name="employee_records")
    occurred_on = models.DateField()
    outcome = models.CharField(max_length=20, choices=TrainingOutcome.choices)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="employee_training_records_recorded")

    class Meta:
        verbose_name = "سابقه آموزش کارمند"
        verbose_name_plural = "سوابق آموزش کارکنان"
        indexes = [models.Index(fields=["organization", "employee", "occurred_on"], name="employee_training_date_idx")]  # noqa: RUF012
        ordering = ["-occurred_on"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, employee=self.employee, requirement=self.requirement)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("سابقه آموزش تغییرپذیر نیست؛ سابقه اصلاحی جدید ثبت کنید.")
        self.full_clean()
        super().save(*args, **kwargs)


class PerformanceEvaluation(UUIDModel, TimeStampedModel):
    """Sensitive, immutable Workforce evaluation without downstream authority."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="performance_evaluations")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="performance_evaluations")
    period_start = models.DateField()
    period_end = models.DateField()
    criteria_snapshot = models.JSONField(default=dict)
    result_summary = models.TextField()
    evaluated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="performance_evaluations_made")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="performance_evaluations_recorded")

    class Meta:
        verbose_name = "ارزیابی عملکرد"
        verbose_name_plural = "ارزیابی‌های عملکرد"
        constraints = [models.CheckConstraint(condition=Q(period_end__gte=models.F("period_start")), name="performance_evaluation_period_dates")]  # noqa: RUF012
        indexes = [models.Index(fields=["organization", "employee", "period_start"], name="performance_evaluation_idx")]  # noqa: RUF012
        ordering = ["-period_end"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, employee=self.employee)
        self.result_summary = self.result_summary.strip()
        if not isinstance(self.criteria_snapshot, dict) or not self.criteria_snapshot:
            raise ValidationError({"criteria_snapshot": "شواهد معیارهای ارزیابی الزامی است."})
        if not self.result_summary:
            raise ValidationError({"result_summary": "نتیجه ارزیابی الزامی است."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("ارزیابی عملکرد نهایی تغییرپذیر نیست؛ سابقه اصلاحی جدید ثبت کنید.")
        self.full_clean()
        super().save(*args, **kwargs)


class LaborRateVersion(UUIDModel, TimeStampedModel):
    """Sensitive, effective-dated Workforce cost reference with no financial effect."""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="labor_rate_versions")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="labor_rate_versions")
    component_name = models.CharField(max_length=255)
    unit_label = models.CharField(max_length=50)
    currency_code = models.CharField(max_length=3)
    rate_amount = models.DecimalField(max_digits=18, decimal_places=2)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="labor_rate_versions_recorded")

    class Meta:
        verbose_name = "نسخه نرخ نیروی کار"
        verbose_name_plural = "نسخه‌های نرخ نیروی کار"
        constraints = [  # noqa: RUF012
            models.CheckConstraint(condition=Q(rate_amount__gte=0), name="labor_rate_amount_nonnegative"),
            models.CheckConstraint(condition=Q(effective_to__isnull=True) | Q(effective_to__gte=models.F("effective_from")), name="labor_rate_effective_dates"),
        ]
        indexes = [models.Index(fields=["organization", "employee", "component_name", "effective_from"], name="labor_rate_effective_idx")]  # noqa: RUF012
        ordering = ["employee", "component_name", "-effective_from"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        validate_related_organizations(self, employee=self.employee)
        self.component_name = self.component_name.strip()
        self.unit_label = self.unit_label.strip()
        self.currency_code = self.currency_code.strip().upper()
        if not self.component_name or not self.unit_label or len(self.currency_code) != 3:
            raise ValidationError("عنوان جزء، واحد و کد سه‌حرفی ارز الزامی است.")
        if self.rate_amount < 0:
            raise ValidationError({"rate_amount": "نرخ نمی‌تواند منفی باشد."})
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("نسخه نرخ تغییرپذیر نیست؛ نسخه مؤثر جدید ثبت کنید.")
        self.full_clean()
        super().save(*args, **kwargs)


class WorkRelationshipDocumentLink(AbstractTypedDocumentLink):
    """Immutable DMS link to one employment episode."""

    target_field_name = "work_relationship"
    work_relationship = models.ForeignKey(
        WorkRelationship, on_delete=models.PROTECT, related_name="typed_document_links"
    )

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["document", "work_relationship"],
                name="work_relationship_document_uq",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "document"],
                name="work_relationship_doc_idx",
            )
        ]


class EmployeeQualificationDocumentLink(AbstractTypedDocumentLink):
    """Workforce-owned, immutable DMS evidence link for a qualification."""

    target_field_name = "qualification"
    qualification = models.ForeignKey(EmployeeQualification, on_delete=models.PROTECT, related_name="typed_document_links")
    document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [models.UniqueConstraint(fields=["document", "qualification"], name="employee_qualification_document_uq")]  # noqa: RUF012
        indexes = [models.Index(fields=["organization", "document"], name="employee_qualification_doc_idx")]  # noqa: RUF012


class EmployeeTrainingDocumentLink(AbstractTypedDocumentLink):
    """Workforce-owned, immutable DMS evidence link for a training record."""

    target_field_name = "training_record"
    training_record = models.ForeignKey(EmployeeTrainingRecord, on_delete=models.PROTECT, related_name="typed_document_links")
    document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [models.UniqueConstraint(fields=["document", "training_record"], name="employee_training_document_uq")]  # noqa: RUF012
        indexes = [models.Index(fields=["organization", "document"], name="employee_training_doc_idx")]  # noqa: RUF012


class PerformanceEvaluationDocumentLink(AbstractTypedDocumentLink):
    """Workforce-owned, immutable DMS evidence link for sensitive evaluation evidence."""

    target_field_name = "performance_evaluation"
    performance_evaluation = models.ForeignKey(PerformanceEvaluation, on_delete=models.PROTECT, related_name="typed_document_links")
    document_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [models.UniqueConstraint(fields=["document", "performance_evaluation"], name="performance_evaluation_document_uq")]  # noqa: RUF012
        indexes = [models.Index(fields=["organization", "document"], name="performance_evaluation_doc_idx")]  # noqa: RUF012


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


# Source-bound request history, not another contact master or Workflow engine.
class PersonalDataHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("سابقه درخواست اطلاعات شخصی تغییرپذیر نیست.")

    def delete(self):
        raise ValidationError("سابقه درخواست اطلاعات شخصی حذف‌پذیر نیست.")


class PersonalDataRecord(UUIDModel, CreatedAtModel):
    objects = models.Manager.from_queryset(PersonalDataHistoryQuerySet)()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("سابقه درخواست اطلاعات شخصی تغییرپذیر نیست.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("سابقه درخواست اطلاعات شخصی حذف‌پذیر نیست.")


class PersonalDataEnrollment(PersonalDataRecord):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    family = models.CharField(
        max_length=30,
        choices=[
            ("phone", "تلفن"),
            ("email", "ایمیل"),
            ("address", "نشانی"),
            ("emergency", "تماس اضطراری"),
            ("enrolled_contact", "فیلد ارتباطی ثبت‌شده"),
        ],
    )
    source_field = models.CharField(
        max_length=30,
        choices=[
            ("phone_number", "تلفن"),
            ("email", "ایمیل"),
            ("address", "نشانی"),
            ("emergency_contact", "تماس اضطراری"),
        ],
    )
    version = models.PositiveIntegerField()
    workflow_version = models.ForeignKey(
        "workflows.WorkflowVersion", on_delete=models.PROTECT
    )
    cancellation_allowed = models.BooleanField(default=False)
    reason = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "family", "source_field", "version"],
                name="personal_data_enrollment_version_uq",
            )
        ]

    def clean(self):
        validate_related_organizations(self, workflow_version=self.workflow_version)
        expected = {
            "phone": "phone_number",
            "email": "email",
            "address": "address",
            "emergency": "emergency_contact",
        }
        if self.family in expected and expected[self.family] != self.source_field:
            raise ValidationError("خانواده و فیلد منبع هم‌خوان نیستند.")
        if (
            self.workflow_version.status != "published"
            or self.workflow_version.definition.workflow_type.code
            != "workforce.personal_data_change"
            or not self.reason.strip()
        ):
            raise ValidationError("نسخه مجاز گردش‌کار و دلیل ثبت لازم است.")

    def __str__(self):
        return self.get_source_field_display()


class PersonalDataRequest(PersonalDataRecord):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    work_relationship = models.ForeignKey(WorkRelationship, on_delete=models.PROTECT)
    enrollment = models.ForeignKey(PersonalDataEnrollment, on_delete=models.PROTECT)
    previous_value = models.TextField(blank=True, max_length=1000)
    proposed_value = models.TextField(blank=True, max_length=1000)
    reason = models.TextField(max_length=2000)
    idempotency_key = models.CharField(max_length=128)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "requested_by", "idempotency_key"],
                name="personal_data_request_key_uq",
            )
        ]

    def clean(self):
        validate_related_organizations(
            self,
            person=self.person,
            work_relationship=self.work_relationship,
            enrollment=self.enrollment,
        )
        if (
            self.work_relationship.person_id != self.person_id
            or self.person.user_id != self.requested_by_id
            or not self.work_relationship.legacy_employee_id
        ):
            raise ValidationError("پیوند صریح هویت و منبع لازم است.")
        if (
            not self.reason.strip()
            or self.previous_value == self.proposed_value
            or not self.idempotency_key.strip()
        ):
            raise ValidationError("تغییر واقعی، دلیل و کلید تکرارپذیری لازم است.")


class PersonalDataDecision(PersonalDataRecord):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    request = models.OneToOneField(
        PersonalDataRequest, on_delete=models.PROTECT, related_name="decision"
    )
    action = models.CharField(
        max_length=20,
        choices=[
            ("accepted", "پذیرفته"),
            ("rejected", "ردشده"),
            ("cancelled", "لغوشده"),
        ],
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    work_item = models.ForeignKey(
        "workflows.WorkItem", on_delete=models.PROTECT, null=True, blank=True
    )
    reason = models.TextField(max_length=2000)

    def clean(self):
        validate_related_organizations(
            self,
            request=self.request,
            work_item=self.work_item if self.work_item_id else None,
        )
        if not self.reason.strip():
            raise ValidationError("دلیل تصمیم لازم است.")
        if self.work_item_id and (
            self.work_item.instance.subject_id != self.request_id
            or self.work_item.instance.subject_type != "workforce.personal_data_change"
        ):
            raise ValidationError("کار تصمیم متعلق به همین درخواست نیست.")
