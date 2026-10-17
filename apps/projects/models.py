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


class ProjectSiteDocumentLink(AbstractTypedDocumentLink):
    """Project-site photo/evidence context without owning document bytes."""

    target_field_name = "project_site"
    project_site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        related_name="typed_document_links",
    )

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["document", "project_site"],
                name="project_site_document_link_uq",
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "document"],
                name="project_site_doc_org_idx",
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


class CostStructureStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    LOCKED = "locked", "قفل‌شده"


class CostStructureVersion(UUIDModel, TimeStampedModel):
    """Tenant-owned, version-pinned CBS and cost-center planning structure."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="cost_structure_versions",
    )
    code = models.CharField(max_length=50)
    version = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=16,
        choices=CostStructureStatus.choices,
        default=CostStructureStatus.DRAFT,
    )
    governance_reference = models.CharField(max_length=255)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cost_structures_locked",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cost_structures_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code", "version"],
                name="cost_structure_org_code_ver_uq",
            )
        ]

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        self.governance_reference = self.governance_reference.strip()
        if not self.code or not self.name or not self.governance_reference:
            raise ValidationError("Code, name, and governance reference are required.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status == CostStructureStatus.LOCKED:
                raise ValidationError("A locked cost structure is immutable.")
        self.full_clean()
        super().save(*args, **kwargs)


class CBSNode(UUIDModel, TimeStampedModel):
    """A cost-classification node; it is never a WBS or ledger account."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    structure_version = models.ForeignKey(
        CostStructureVersion, on_delete=models.PROTECT, related_name="cbs_nodes"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    is_leaf = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["structure_version", "code"], name="cbs_structure_code_uq"
            )
        ]
        ordering = ["sort_order", "code"]  # noqa: RUF012

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("CBS code and name are required.")
        if self.structure_version_id:
            validate_related_organizations(
                self, structure_version=self.structure_version
            )
        if self.parent_id and (
            self.parent_id == self.pk
            or self.parent.structure_version_id != self.structure_version_id
            or self.parent.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"parent": "The CBS parent must belong to this version."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.structure_version.status != CostStructureStatus.DRAFT:
            raise ValidationError("Nodes of a locked cost structure are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)


class CostCenter(UUIDModel, TimeStampedModel):
    """Versioned responsibility classification, independent of workforce and GL."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    structure_version = models.ForeignKey(
        CostStructureVersion, on_delete=models.PROTECT, related_name="cost_centers"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["structure_version", "code"],
                name="cost_center_structure_code_uq",
            )
        ]

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("Cost-center code and name are required.")
        if self.structure_version_id:
            validate_related_organizations(
                self, structure_version=self.structure_version
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.structure_version.status != CostStructureStatus.DRAFT:
            raise ValidationError("Cost centers of a locked structure are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)


class BudgetVersionStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    ACCEPTED = "accepted", "پذیرفته‌شده"


class BudgetVersion(UUIDModel, TimeStampedModel):
    """A planning-only budget revision; accepted payloads are immutable."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="budget_versions",
    )
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="budget_versions"
    )
    version_number = models.PositiveIntegerField()
    predecessor = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successors",
    )
    structure_version = models.ForeignKey(
        CostStructureVersion, on_delete=models.PROTECT
    )
    handoff_id = models.CharField(max_length=100)
    submission_version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=BudgetVersionStatus.choices,
        default=BudgetVersionStatus.DRAFT,
    )
    currency = models.CharField(max_length=3)
    rounding_policy_reference = models.CharField(max_length=255)
    governance_reference = models.CharField(max_length=255)
    cost_center_required = models.BooleanField()
    reason = models.TextField()
    payload_hash = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="budget_versions_created",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="budget_versions_submitted",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="budget_versions_accepted",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "project", "version_number"],
                name="budget_org_project_version_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "project", "handoff_id", "submission_version"],
                name="budget_handoff_submission_uq",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "status"],
                name="budget_org_project_status_idx",
            )
        ]

    def clean(self) -> None:
        self.currency = canonicalize_upper_identifier(self.currency)
        self.handoff_id = self.handoff_id.strip()
        self.rounding_policy_reference = self.rounding_policy_reference.strip()
        self.governance_reference = self.governance_reference.strip()
        self.reason = self.reason.strip()
        if not all(
            (
                self.currency,
                self.handoff_id,
                self.rounding_policy_reference,
                self.governance_reference,
                self.reason,
            )
        ):
            raise ValidationError("Budget policy references and reason are required.")
        validate_related_organizations(
            self, project=self.project, structure_version=self.structure_version
        )
        if self.predecessor_id and (
            self.predecessor.organization_id != self.organization_id
            or self.predecessor.project_id != self.project_id
            or self.predecessor.status != BudgetVersionStatus.ACCEPTED
        ):
            raise ValidationError(
                {"predecessor": "The predecessor must be an accepted project budget."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status == BudgetVersionStatus.ACCEPTED:
                raise ValidationError("An accepted budget version is immutable.")
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectBudgetControl(UUIDModel, TimeStampedModel):
    """Mutable project pointer to the one governing accepted planning baseline."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.OneToOneField(
        Project, on_delete=models.PROTECT, related_name="budget_control"
    )
    governing_budget = models.ForeignKey(
        BudgetVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="governing_for",
    )

    def clean(self) -> None:
        validate_related_organizations(self, project=self.project)
        if self.governing_budget_id and (
            self.governing_budget.organization_id != self.organization_id
            or self.governing_budget.project_id != self.project_id
            or self.governing_budget.status != BudgetVersionStatus.ACCEPTED
        ):
            raise ValidationError(
                {
                    "governing_budget": "The governing budget must be accepted for this project."
                }
            )


class BudgetSourceManifest(UUIDModel, TimeStampedModel):
    """Pinned estimate-revision source identity for one budget version."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    budget = models.OneToOneField(
        BudgetVersion, on_delete=models.PROTECT, related_name="source_manifest"
    )
    estimate = models.ForeignKey("estimates.Estimate", on_delete=models.PROTECT)
    estimate_revision = models.ForeignKey(
        "estimates.EstimateRevision", on_delete=models.PROTECT
    )
    estimate_revision_number = models.PositiveIntegerField()
    source_reference = models.CharField(max_length=255)

    def clean(self) -> None:
        validate_related_organizations(
            self,
            budget=self.budget,
            estimate=self.estimate,
            estimate_revision=self.estimate_revision,
        )
        if (
            self.budget.project_id != self.estimate.project_id
            or self.estimate_revision.estimate_id != self.estimate_id
        ):
            raise ValidationError(
                "The estimate source must belong to the budget project and revision."
            )


class BudgetManifestDisposition(models.TextChoices):
    PENDING = "pending", "در انتظار تعیین تکلیف"
    INCLUDED = "included", "منظورشده"
    EXCLUDED = "excluded", "حذف‌شده"


class BudgetManifestLine(UUIDModel, TimeStampedModel):
    """Complete source-line manifest with immutable estimate snapshots."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    manifest = models.ForeignKey(
        BudgetSourceManifest, on_delete=models.PROTECT, related_name="lines"
    )
    estimate_item = models.ForeignKey(
        "estimates.EstimateItem", on_delete=models.PROTECT
    )
    source_description = models.CharField(max_length=255)
    source_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    source_unit = models.CharField(max_length=80)
    source_unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    source_amount = models.DecimalField(max_digits=20, decimal_places=2)
    disposition = models.CharField(
        max_length=16,
        choices=BudgetManifestDisposition.choices,
        default=BudgetManifestDisposition.PENDING,
    )
    exclusion_reason = models.TextField(blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["manifest", "estimate_item"], name="budget_manifest_item_uq"
            )
        ]


class BudgetAllocation(UUIDModel, TimeStampedModel):
    """Conserved planning allocation from one included source line."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    manifest_line = models.ForeignKey(
        BudgetManifestLine, on_delete=models.PROTECT, related_name="allocations"
    )
    sequence = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    cbs_node = models.ForeignKey(CBSNode, on_delete=models.PROTECT)
    wbs_node = models.ForeignKey(WBSNode, on_delete=models.PROTECT)
    cost_center = models.ForeignKey(
        CostCenter, null=True, blank=True, on_delete=models.PROTECT
    )
    allocation_basis_reference = models.CharField(max_length=255)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["manifest_line", "sequence"],
                name="budget_allocation_line_seq_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=Decimal("0.00")),
                name="budget_allocation_amount_positive",
            ),
        ]


class ProjectCostMeasure(models.TextChoices):
    COMMITMENT = "commitment", "تعهد"
    ACCRUAL = "accrual", "هزینه تعهدشده تحقق‌یافته"
    ACTUAL = "actual", "هزینه واقعی"


class ProjectCostSourceContractStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    APPROVED = "approved", "تأییدشده"


class ProjectCostSourceContract(UUIDModel, TimeStampedModel):
    """Versioned, code-registered producer contract; never source-domain authority."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    producer_key = models.CharField(max_length=100)
    version = models.PositiveIntegerField()
    measure = models.CharField(max_length=16, choices=ProjectCostMeasure.choices)
    source_model = models.CharField(max_length=100)
    event_schema = models.CharField(max_length=100)
    classification_policy_reference = models.CharField(max_length=255)
    recognition_policy_reference = models.CharField(max_length=255)
    reconciliation_policy_reference = models.CharField(max_length=255)
    requires_financial_evidence = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16,
        choices=ProjectCostSourceContractStatus.choices,
        default=ProjectCostSourceContractStatus.DRAFT,
    )
    payload_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="project_cost_source_contracts_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="project_cost_source_contracts_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "producer_key", "version"],
                name="project_cost_source_contract_uq",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="draft",
                        approved_by__isnull=True,
                        approved_at__isnull=True,
                    )
                    | (
                        models.Q(
                            status="approved",
                            approved_by__isnull=False,
                            approved_at__isnull=False,
                        )
                        & ~models.Q(approved_by=models.F("created_by"))
                    )
                ),
                name="project_cost_contract_approval_ck",
            ),
        ]

    def clean(self) -> None:
        self.producer_key = self.producer_key.strip().lower()
        self.source_model = self.source_model.strip().lower()
        self.event_schema = self.event_schema.strip()
        for field in (
            "classification_policy_reference",
            "recognition_policy_reference",
            "reconciliation_policy_reference",
        ):
            setattr(self, field, getattr(self, field).strip())
        if not all(
            (
                self.producer_key,
                self.source_model,
                self.event_schema,
                self.classification_policy_reference,
                self.recognition_policy_reference,
                self.reconciliation_policy_reference,
            )
        ):
            raise ValidationError("All producer contract references are required.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status == ProjectCostSourceContractStatus.APPROVED:
                raise ValidationError("An approved producer contract is immutable.")
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectCostFactKind(models.TextChoices):
    COMMITMENT_AUTHORIZED = "commitment_authorized", "تعهد مجاز"
    COMMITMENT_ADJUSTMENT = "commitment_adjustment", "تعدیل تعهد"
    COMMITMENT_RELIEF = "commitment_relief", "رفع تعهد"
    ACCRUAL_RECOGNIZED = "accrual_recognized", "شناسایی هزینه تحقق‌یافته"
    ACCRUAL_REVERSAL = "accrual_reversal", "برگشت هزینه تحقق‌یافته"
    ACTUAL_RECOGNIZED = "actual_recognized", "شناسایی هزینه واقعی"
    ACTUAL_REVERSAL = "actual_reversal", "برگشت هزینه واقعی"


class ProjectCostFact(UUIDModel, TimeStampedModel):
    """Append-only classified projection retaining exact producer lineage."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="cost_facts"
    )
    contract = models.ForeignKey(
        ProjectCostSourceContract, on_delete=models.PROTECT, related_name="facts"
    )
    kind = models.CharField(max_length=32, choices=ProjectCostFactKind.choices)
    source_id = models.CharField(max_length=100)
    source_version = models.CharField(max_length=100)
    source_line_id = models.CharField(max_length=100)
    economic_event_id = models.CharField(max_length=100)
    occurrence_id = models.CharField(max_length=100)
    recognition_date = models.DateField()
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    cbs_node = models.ForeignKey(CBSNode, on_delete=models.PROTECT)
    wbs_node = models.ForeignKey(WBSNode, on_delete=models.PROTECT)
    cost_center = models.ForeignKey(
        CostCenter, null=True, blank=True, on_delete=models.PROTECT
    )
    classification_version = models.CharField(max_length=100)
    valuation_reference = models.CharField(max_length=255)
    financial_evidence_reference = models.CharField(max_length=255, blank=True)
    reverses = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    replaces_accrual = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="replacement_actual",
    )
    payload_hash = models.CharField(max_length=64)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "contract", "occurrence_id"],
                name="project_cost_fact_occurrence_uq",
            ),
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "project",
                    "economic_event_id",
                    "kind",
                    "source_line_id",
                ],
                name="project_cost_fact_event_line_uq",
            ),
            models.CheckConstraint(
                condition=~models.Q(amount=Decimal("0.00")),
                name="project_cost_fact_nonzero",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind__in=["accrual_reversal", "actual_reversal"],
                        amount__lt=Decimal("0.00"),
                    )
                    | models.Q(
                        kind__in=[
                            "commitment_authorized",
                            "commitment_relief",
                            "accrual_recognized",
                            "actual_recognized",
                        ],
                        amount__gt=Decimal("0.00"),
                    )
                    | models.Q(kind="commitment_adjustment")
                ),
                name="project_cost_fact_kind_sign_ck",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "project", "recognition_date"],
                name="project_cost_project_date_idx",
            ),
            models.Index(
                fields=["economic_event_id", "kind"],
                name="project_cost_event_kind_idx",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            project=self.project,
            contract=self.contract,
            cbs_node=self.cbs_node,
            wbs_node=self.wbs_node,
            cost_center=self.cost_center,
        )
        if self.wbs_node.project_id != self.project_id:
            raise ValidationError("The WBS classification belongs to another project.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("Project cost facts are append-only.")
        self.currency = canonicalize_upper_identifier(self.currency)
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectCostCoverageStatus(models.TextChoices):
    NOT_STARTED = "not_started", "شروع‌نشده"
    PARTIAL = "partial", "ناقص"
    COMPLETE = "complete", "کامل"


class ProjectCostCoverage(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="cost_coverage"
    )
    contract = models.ForeignKey(ProjectCostSourceContract, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=16,
        choices=ProjectCostCoverageStatus.choices,
        default=ProjectCostCoverageStatus.NOT_STARTED,
    )
    watermark = models.CharField(max_length=255, blank=True)
    cutoff_at = models.DateTimeField(null=True, blank=True)
    exception_note = models.TextField(blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["project", "contract"], name="project_cost_coverage_uq"
            ),
            models.CheckConstraint(
                condition=~models.Q(status="complete"),
                name="project_cost_coverage_no_complete",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, project=self.project, contract=self.contract
        )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectCostForecast(UUIDModel, TimeStampedModel):
    """Immutable source snapshot for the governed forecast review lifecycle."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="cost_forecasts"
    )
    budget = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT)
    version_number = models.PositiveIntegerField()
    cutoff_date = models.DateField()
    currency = models.CharField(max_length=3)
    actual_cost = models.DecimalField(max_digits=20, decimal_places=2)
    open_commitment = models.DecimalField(max_digits=20, decimal_places=2)
    remaining_committed_etc = models.DecimalField(max_digits=20, decimal_places=2)
    uncommitted_etc = models.DecimalField(max_digits=20, decimal_places=2)
    eac = models.DecimalField(max_digits=20, decimal_places=2)
    assumptions = models.TextField()
    source_watermark = models.CharField(max_length=255)
    coverage_complete = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["project", "version_number"],
                name="project_cost_forecast_version_uq",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("Forecast snapshots are immutable.")
        validate_related_organizations(self, project=self.project, budget=self.budget)
        if self.budget.project_id != self.project_id:
            raise ValidationError("The forecast budget belongs to another project.")
        if (
            self.actual_cost < 0
            or self.open_commitment < 0
            or self.remaining_committed_etc < 0
            or self.uncommitted_etc < 0
            or self.eac
            != self.actual_cost + self.remaining_committed_etc + self.uncommitted_etc
        ):
            raise ValidationError("Forecast totals are invalid.")
        self.full_clean()
        super().save(*args, **kwargs)


class ForecastReviewStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    SUBMITTED = "submitted", "ارسال‌شده"
    UNDER_REVIEW = "under_review", "در حال بررسی"
    APPROVED = "approved", "تأییدشده"
    REJECTED = "rejected", "ردشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class ProjectForecastReview(UUIDModel, TimeStampedModel):
    """Mutable lifecycle pointer; the forecast snapshot remains immutable."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    forecast = models.OneToOneField(
        ProjectCostForecast, on_delete=models.PROTECT, related_name="review"
    )
    predecessor = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successors",
    )
    status = models.CharField(
        max_length=20,
        choices=ForecastReviewStatus.choices,
        default=ForecastReviewStatus.DRAFT,
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(status="approved"),
                name="one_current_approved_forecast_per_project",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, project=self.project, forecast=self.forecast
        )
        if self.forecast.project_id != self.project_id:
            raise ValidationError("Forecast and review project must match.")
        if self.predecessor_id and (
            self.predecessor.organization_id != self.organization_id
            or self.predecessor.project_id != self.project_id
            or self.predecessor.forecast.version_number >= self.forecast.version_number
        ):
            raise ValidationError("Predecessor must be an older same-project forecast.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if (
                previous.forecast_id != self.forecast_id
                or previous.predecessor_id != self.predecessor_id
                or previous.organization_id != self.organization_id
                or previous.project_id != self.project_id
            ):
                raise ValidationError("Forecast review source identity is immutable.")
            if previous.status != self.status and not getattr(
                self, "_transition_authorized", False
            ):
                raise ValidationError(
                    "Forecast review transitions require the domain service."
                )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("Forecast review history cannot be deleted.")


class ProjectForecastTransition(UUIDModel, TimeStampedModel):
    """Append-only decision evidence for one immutable forecast version."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    review = models.ForeignKey(
        ProjectForecastReview, on_delete=models.PROTECT, related_name="transitions"
    )
    sequence = models.PositiveIntegerField()
    previous_status = models.CharField(
        max_length=20, choices=ForecastReviewStatus.choices
    )
    new_status = models.CharField(max_length=20, choices=ForecastReviewStatus.choices)
    reason = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["review", "sequence"], name="forecast_transition_sequence_uq"
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("Forecast transition history is immutable.")
        validate_related_organizations(self, review=self.review)
        if not self.reason.strip():
            raise ValidationError("A transition reason is required.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("Forecast transition history cannot be deleted.")


class ProjectScheduleStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    ACCEPTED = "accepted", "مبنای پذیرفته‌شده"


class ProjectScheduleRevision(UUIDModel, TimeStampedModel):
    """Versioned schedule evidence; baseline acceptance is currently fail-closed."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="schedule_revisions"
    )
    version_number = models.PositiveIntegerField()
    occurrence_id = models.CharField(max_length=100)
    status = models.CharField(
        max_length=16,
        choices=ProjectScheduleStatus.choices,
        default=ProjectScheduleStatus.DRAFT,
    )
    data_date = models.DateField()
    planned_start = models.DateField()
    planned_finish = models.DateField()
    calendar_reference = models.CharField(max_length=255)
    assumptions = models.TextField()
    predecessor = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT
    )
    payload_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="project_schedule_revisions_created",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="project_schedule_revisions_accepted",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["project", "version_number"],
                name="project_schedule_version_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "occurrence_id"],
                name="project_schedule_occurrence_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_finish__gte=models.F("planned_start")),
                name="project_schedule_date_order_ck",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="draft",
                        accepted_by__isnull=True,
                        accepted_at__isnull=True,
                    )
                    | models.Q(
                        status="accepted",
                        accepted_by__isnull=False,
                        accepted_at__isnull=False,
                    )
                ),
                name="project_schedule_acceptance_ck",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, project=self.project, predecessor=self.predecessor
        )
        if self.predecessor and self.predecessor.project_id != self.project_id:
            raise ValidationError("The predecessor belongs to another project.")
        if self.planned_finish < self.planned_start:
            raise ValidationError("Schedule finish cannot precede schedule start.")
        if not self.calendar_reference.strip() or not self.assumptions.strip():
            raise ValidationError("Calendar reference and assumptions are required.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError(
                "Schedule revisions are immutable; create a revision."
            )
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectScheduleItem(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    schedule = models.ForeignKey(
        ProjectScheduleRevision, on_delete=models.PROTECT, related_name="items"
    )
    wbs_node = models.ForeignKey(
        WBSNode, null=True, blank=True, on_delete=models.PROTECT
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    is_milestone = models.BooleanField(default=False)
    planned_start = models.DateField()
    planned_finish = models.DateField()
    source_reference = models.CharField(max_length=255)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["schedule", "code"], name="project_schedule_item_code_uq"
            ),
            models.CheckConstraint(
                condition=models.Q(planned_finish__gte=models.F("planned_start")),
                name="project_schedule_item_date_order_ck",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_milestone=False)
                    | models.Q(planned_finish=models.F("planned_start"))
                ),
                name="project_schedule_milestone_date_ck",
            ),
        ]

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        validate_related_organizations(
            self,
            project=self.project,
            schedule=self.schedule,
            wbs_node=self.wbs_node,
        )
        if self.schedule.project_id != self.project_id:
            raise ValidationError("The schedule belongs to another project.")
        if self.wbs_node and self.wbs_node.project_id != self.project_id:
            raise ValidationError("The WBS node belongs to another project.")
        if self.schedule.status != ProjectScheduleStatus.DRAFT:
            raise ValidationError("Accepted schedule payload is immutable.")
        if (
            self.planned_start < self.schedule.planned_start
            or self.planned_finish > self.schedule.planned_finish
        ):
            raise ValidationError("Schedule item dates exceed the revision boundary.")
        if self.is_milestone and self.planned_start != self.planned_finish:
            raise ValidationError("A milestone must have one date.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("Schedule items are append-only within a revision.")
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectScheduleDependencyType(models.TextChoices):
    FINISH_START = "finish_start", "پایان به شروع"
    START_START = "start_start", "شروع به شروع"
    FINISH_FINISH = "finish_finish", "پایان به پایان"
    START_FINISH = "start_finish", "شروع به پایان"


class ProjectScheduleDependency(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    schedule = models.ForeignKey(
        ProjectScheduleRevision,
        on_delete=models.PROTECT,
        related_name="dependencies",
    )
    predecessor_item = models.ForeignKey(
        ProjectScheduleItem, on_delete=models.PROTECT, related_name="successor_links"
    )
    successor_item = models.ForeignKey(
        ProjectScheduleItem, on_delete=models.PROTECT, related_name="predecessor_links"
    )
    dependency_type = models.CharField(
        max_length=16, choices=ProjectScheduleDependencyType.choices
    )
    lag_days = models.IntegerField(default=0)
    rationale = models.CharField(max_length=255)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=[
                    "schedule",
                    "predecessor_item",
                    "successor_item",
                    "dependency_type",
                ],
                name="project_schedule_dependency_uq",
            ),
            models.CheckConstraint(
                condition=~models.Q(predecessor_item=models.F("successor_item")),
                name="project_schedule_dependency_not_self_ck",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            project=self.project,
            schedule=self.schedule,
            predecessor_item=self.predecessor_item,
            successor_item=self.successor_item,
        )
        if (
            self.schedule.project_id != self.project_id
            or self.predecessor_item.schedule_id != self.schedule_id
            or self.successor_item.schedule_id != self.schedule_id
        ):
            raise ValidationError("Dependency endpoints must share one schedule.")
        if self.predecessor_item_id == self.successor_item_id:
            raise ValidationError("A schedule item cannot depend on itself.")
        if self.schedule.status != ProjectScheduleStatus.DRAFT:
            raise ValidationError("Accepted schedule payload is immutable.")
        if not self.rationale.strip():
            raise ValidationError("Dependency rationale is required.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("Schedule dependencies are append-only.")
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectControlItemKind(models.TextChoices):
    CONSTRAINT = "constraint", "محدودیت"
    ISSUE = "issue", "مسئله"
    RISK = "risk", "ریسک"
    DELAY = "delay", "تأخیر"


class ProjectControlItemStatus(models.TextChoices):
    OPEN = "open", "باز"
    CLOSED = "closed", "بسته"


class ProjectControlItem(UUIDModel, TimeStampedModel):
    """Immutable observation; status is append-only in ProjectControlStatusEvent."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="control_register_items"
    )
    schedule_item = models.ForeignKey(
        ProjectScheduleItem, null=True, blank=True, on_delete=models.PROTECT
    )
    kind = models.CharField(max_length=16, choices=ProjectControlItemKind.choices)
    occurrence_id = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    description = models.TextField()
    identified_on = models.DateField()
    observed_from = models.DateField(null=True, blank=True)
    observed_to = models.DateField(null=True, blank=True)
    owner_reference = models.CharField(max_length=255)
    evidence_reference = models.CharField(max_length=255)
    schedule_impact_description = models.TextField(blank=True)
    responsibility_status = models.CharField(
        max_length=16, default="undetermined", editable=False
    )
    contractual_impact_status = models.CharField(
        max_length=16, default="unassessed", editable=False
    )
    payload_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "project", "occurrence_id"],
                name="project_control_item_occurrence_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(responsibility_status="undetermined"),
                name="project_control_responsibility_fail_closed_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(contractual_impact_status="unassessed"),
                name="project_control_contract_fail_closed_ck",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, project=self.project, schedule_item=self.schedule_item
        )
        if self.schedule_item and self.schedule_item.project_id != self.project_id:
            raise ValidationError("The schedule item belongs to another project.")
        if self.observed_to and not self.observed_from:
            raise ValidationError("Observed-from is required when observed-to is set.")
        if (
            self.observed_from
            and self.observed_to
            and self.observed_to < self.observed_from
        ):
            raise ValidationError("Observed-to cannot precede observed-from.")
        if self.kind == ProjectControlItemKind.DELAY and not (
            self.observed_from and self.evidence_reference.strip()
        ):
            raise ValidationError("Delay observations require a date and evidence.")
        if not all(
            (
                self.title.strip(),
                self.description.strip(),
                self.owner_reference.strip(),
                self.evidence_reference.strip(),
            )
        ):
            raise ValidationError("Register identity, owner and evidence are required.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("Project control observations are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectControlStatusEvent(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    item = models.ForeignKey(
        ProjectControlItem, on_delete=models.PROTECT, related_name="status_events"
    )
    sequence = models.PositiveIntegerField()
    occurrence_id = models.CharField(max_length=100)
    from_status = models.CharField(
        max_length=16, choices=ProjectControlItemStatus.choices, blank=True
    )
    to_status = models.CharField(
        max_length=16, choices=ProjectControlItemStatus.choices
    )
    reason = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["item", "sequence"], name="project_control_status_seq_uq"
            ),
            models.UniqueConstraint(
                fields=["item", "occurrence_id"],
                name="project_control_status_occurrence_uq",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("Control status evidence is append-only.")
        validate_related_organizations(self, item=self.item)
        self.full_clean()
        super().save(*args, **kwargs)


class ProjectChangeProposal(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="change_proposals"
    )
    occurrence_id = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    reason = models.TextField()
    evidence_reference = models.CharField(max_length=255)
    schedule_impact_description = models.TextField()
    cost_impact_description = models.TextField(blank=True)
    contractual_impact_status = models.CharField(
        max_length=16, default="unassessed", editable=False
    )
    financial_effect_status = models.CharField(
        max_length=20, default="observation_only", editable=False
    )
    payload_hash = models.CharField(max_length=64)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "project", "occurrence_id"],
                name="project_change_occurrence_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(contractual_impact_status="unassessed"),
                name="project_change_contract_fail_closed_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(financial_effect_status="observation_only"),
                name="project_change_finance_fail_closed_ck",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("Change proposals are immutable evidence.")
        validate_related_organizations(self, project=self.project)
        self.full_clean()
        super().save(*args, **kwargs)


class ScheduleRebaselineProposal(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name="rebaseline_proposals"
    )
    occurrence_id = models.CharField(max_length=100)
    current_baseline = models.ForeignKey(
        ProjectScheduleRevision,
        on_delete=models.PROTECT,
        related_name="rebaseline_sources",
    )
    candidate_revision = models.ForeignKey(
        ProjectScheduleRevision,
        on_delete=models.PROTECT,
        related_name="rebaseline_candidates",
    )
    change_proposal = models.ForeignKey(
        ProjectChangeProposal, null=True, blank=True, on_delete=models.PROTECT
    )
    reason = models.TextField()
    evidence_reference = models.CharField(max_length=255)
    payload_hash = models.CharField(max_length=64)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "project", "occurrence_id"],
                name="project_rebaseline_occurrence_uq",
            ),
            models.CheckConstraint(
                condition=~models.Q(current_baseline=models.F("candidate_revision")),
                name="project_rebaseline_distinct_revision_ck",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            project=self.project,
            current_baseline=self.current_baseline,
            candidate_revision=self.candidate_revision,
            change_proposal=self.change_proposal,
        )
        if (
            self.current_baseline.project_id != self.project_id
            or self.candidate_revision.project_id != self.project_id
            or (
                self.change_proposal
                and self.change_proposal.project_id != self.project_id
            )
        ):
            raise ValidationError("Rebaseline evidence must share one project.")
        if self.current_baseline.status != ProjectScheduleStatus.ACCEPTED:
            raise ValidationError("A rebaseline requires a retained accepted baseline.")
        if self.candidate_revision.status != ProjectScheduleStatus.DRAFT:
            raise ValidationError("The rebaseline candidate must remain draft.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("Rebaseline proposals are immutable evidence.")
        self.full_clean()
        super().save(*args, **kwargs)
