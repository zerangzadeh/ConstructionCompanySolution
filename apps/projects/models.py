from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.documents.models import AbstractTypedDocumentLink
from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class ProjectStatus(models.TextChoices):
    PLANNING = "planning", "در حال برنامه‌ریزی"
    ACTIVE = "active", "فعال"
    ON_HOLD = "on_hold", "متوقف‌شده"
    COMPLETED = "completed", "تکمیل‌شده"
    CANCELLED = "cancelled", "لغوشده"


class ProjectDocumentLink(AbstractTypedDocumentLink):
    """Project-owned evidence link; its UUID survives legacy migration."""

    target_field_name = "project"
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="typed_document_links",
    )

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["document", "project"], name="project_document_link_uq"
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "document"],
                name="project_doclink_org_doc_idx",
            )
        ]


class Project(UUIDModel, TimeStampedModel):
    """A construction project belonging to exactly one organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="projects",
    )
    code = models.CharField("کد پروژه", max_length=50)
    name = models.CharField("نام پروژه", max_length=255)
    description = models.TextField("شرح", blank=True)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=ProjectStatus.choices,
        default=ProjectStatus.PLANNING,
        db_index=True,
    )
    start_date = models.DateField("تاریخ شروع", null=True, blank=True)
    end_date = models.DateField("تاریخ پایان", null=True, blank=True)
    estimated_budget = models.DecimalField(
        "بودجه تخمینی",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    actual_budget = models.DecimalField(
        "بودجه واقعی",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects_updated",
    )
    deleted_at = models.DateTimeField("زمان حذف", null=True, blank=True)

    class Meta:
        verbose_name = "پروژه"
        verbose_name_plural = "پروژه‌ها"
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
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="project_sites",
    )
    project = models.ForeignKey(
        Project,
        verbose_name="پروژه",
        on_delete=models.CASCADE,
        related_name="sites",
    )
    code = models.CharField("کد کارگاه", max_length=50)
    name = models.CharField("نام کارگاه", max_length=255)
    address = models.TextField("نشانی", blank=True)
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_sites_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_sites_updated",
    )

    class Meta:
        verbose_name = "کارگاه پروژه"
        verbose_name_plural = "کارگاه‌های پروژه"
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
    PLANNING = "planning", "در حال برنامه‌ریزی"
    ACTIVE = "active", "فعال"
    ON_HOLD = "on_hold", "متوقف‌شده"
    COMPLETED = "completed", "تکمیل‌شده"


class ProjectPhase(UUIDModel, TimeStampedModel):
    """A planned or active execution phase within one project worksite."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="project_phases",
    )
    site = models.ForeignKey(
        ProjectSite,
        verbose_name="کارگاه",
        on_delete=models.CASCADE,
        related_name="phases",
    )
    code = models.CharField("کد فاز", max_length=50)
    name = models.CharField("نام فاز", max_length=255)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=ProjectPhaseStatus.choices,
        default=ProjectPhaseStatus.PLANNING,
        db_index=True,
    )
    planned_start_date = models.DateField(
        "تاریخ شروع برنامه‌ریزی‌شده", null=True, blank=True
    )
    planned_end_date = models.DateField(
        "تاریخ پایان برنامه‌ریزی‌شده", null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_phases_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_phases_updated",
    )

    class Meta:
        verbose_name = "فاز پروژه"
        verbose_name_plural = "فازهای پروژه"
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
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="wbs_nodes",
    )
    project = models.ForeignKey(
        Project,
        verbose_name="پروژه",
        on_delete=models.CASCADE,
        related_name="wbs_nodes",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="گره والد",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    code = models.CharField("کد WBS", max_length=50)
    title = models.CharField("عنوان", max_length=255)
    sort_order = models.PositiveIntegerField("ترتیب نمایش", default=0)
    is_active = models.BooleanField("فعال", default=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wbs_nodes_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wbs_nodes_updated",
    )

    class Meta:
        verbose_name = "گره ساختار شکست کار"
        verbose_name_plural = "گره‌های ساختار شکست کار"
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
            raise ValidationError("وارد کردن کد و عنوان ساختار شکست کار الزامی است.")
        if self.project_id:
            validate_related_organizations(self, project=self.project)
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError(
                    {"parent": "گره ساختار شکست نمی‌تواند والد خودش باشد."}
                )
            if (
                self.parent.organization_id != self.organization_id
                or self.parent.project_id != self.project_id
            ):
                raise ValidationError(
                    {"parent": "گره والد ساختار شکست باید متعلق به همین پروژه باشد."}
                )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} — {self.title}"


class ActivityStatus(models.TextChoices):
    PLANNING = "planning", "در حال برنامه‌ریزی"
    ACTIVE = "active", "فعال"
    ON_HOLD = "on_hold", "متوقف‌شده"
    COMPLETED = "completed", "تکمیل‌شده"
    CANCELLED = "cancelled", "لغوشده"


class Activity(UUIDModel, TimeStampedModel):
    """A planned work item in a project's WBS, optionally scoped to site/phase."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="activities",
    )
    project = models.ForeignKey(
        Project,
        verbose_name="پروژه",
        on_delete=models.CASCADE,
        related_name="activities",
    )
    wbs_node = models.ForeignKey(
        WBSNode,
        verbose_name="گره ساختار شکست کار",
        on_delete=models.PROTECT,
        related_name="activities",
    )
    site = models.ForeignKey(
        ProjectSite,
        verbose_name="کارگاه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="activities",
    )
    phase = models.ForeignKey(
        ProjectPhase,
        verbose_name="فاز پروژه",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="activities",
    )
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="activities",
    )
    code = models.CharField("کد فعالیت", max_length=50)
    name = models.CharField("نام فعالیت", max_length=255)
    planned_quantity = models.DecimalField(
        "مقدار برنامه‌ریزی‌شده", max_digits=18, decimal_places=4, null=True, blank=True
    )
    planned_start_date = models.DateField(
        "تاریخ شروع برنامه‌ریزی‌شده", null=True, blank=True
    )
    planned_end_date = models.DateField(
        "تاریخ پایان برنامه‌ریزی‌شده", null=True, blank=True
    )
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=ActivityStatus.choices,
        default=ActivityStatus.PLANNING,
        db_index=True,
    )
    is_active = models.BooleanField("فعال", default=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities_updated",
    )

    class Meta:
        verbose_name = "فعالیت"
        verbose_name_plural = "فعالیت‌ها"
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
            raise ValidationError("وارد کردن کد و نام فعالیت الزامی است.")
        if self.project_id and self.wbs_node_id:
            validate_related_organizations(
                self, project=self.project, wbs_node=self.wbs_node
            )
            if self.wbs_node.project_id != self.project_id:
                raise ValidationError(
                    {"wbs_node": "گره ساختار شکست باید متعلق به همین پروژه باشد."}
                )
        if self.site_id:
            validate_related_organizations(self, site=self.site)
            if self.project_id and self.site.project_id != self.project_id:
                raise ValidationError({"site": "کارگاه باید متعلق به همین پروژه باشد."})
        if self.phase_id:
            validate_related_organizations(self, phase=self.phase)
            if not self.site_id or self.phase.site_id != self.site_id:
                raise ValidationError(
                    {"phase": "فاز باید متعلق به کارگاه انتخاب‌شده باشد."}
                )
        if self.unit_of_measure_id:
            validate_related_organizations(self, unit_of_measure=self.unit_of_measure)
            if not self.unit_of_measure.is_active or self.unit_of_measure.archived_at:
                raise ValidationError(
                    {"unit_of_measure": "واحد اندازه‌گیری باید فعال باشد."}
                )
        if self.planned_quantity is not None:
            if self.planned_quantity <= 0:
                raise ValidationError(
                    {"planned_quantity": "مقدار برنامه‌ریزی‌شده باید مثبت باشد."}
                )
            if not self.unit_of_measure_id:
                raise ValidationError(
                    {
                        "unit_of_measure": "برای مقدار برنامه‌ریزی‌شده، انتخاب واحد الزامی است."
                    }
                )
        elif self.unit_of_measure_id:
            raise ValidationError(
                {
                    "planned_quantity": "با انتخاب واحد، وارد کردن مقدار برنامه‌ریزی‌شده الزامی است."
                }
            )
        if (
            self.planned_start_date
            and self.planned_end_date
            and self.planned_end_date < self.planned_start_date
        ):
            raise ValidationError(
                {
                    "planned_end_date": "تاریخ پایان فعالیت نمی‌تواند پیش از تاریخ شروع باشد."
                }
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"
