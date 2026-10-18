from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.documents.models import AbstractTypedDocumentLink
from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class EstimateDocumentLink(AbstractTypedDocumentLink):
    """Estimate-owned append-only evidence link."""

    target_field_name = "estimate"
    estimate = models.ForeignKey(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="typed_document_links",
    )

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["document", "estimate"], name="estimate_document_link_uq"
            )
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "document"],
                name="estimate_doclink_org_doc_idx",
            )
        ]


class EstimateStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    APPROVED = "approved", "تأییدشده"
    REVISED = "revised", "بازنگری‌شده"
    ARCHIVED = "archived", "بایگانی‌شده"


class Estimate(UUIDModel, TimeStampedModel):
    """A project estimate belonging to exactly one organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="estimates",
    )
    project = models.ForeignKey(
        "projects.Project",
        verbose_name="پروژه",
        on_delete=models.CASCADE,
        related_name="estimates",
    )
    phase = models.ForeignKey(
        "projects.ProjectPhase",
        verbose_name="فاز پروژه",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        verbose_name="قرارداد",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates",
    )
    estimate_number = models.CharField("شماره برآورد", max_length=80)
    title = models.CharField("عنوان برآورد", max_length=255)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=EstimateStatus.choices,
        default=EstimateStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField("یادداشت‌ها", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates_updated",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تأییدکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimates_approved",
    )
    approved_at = models.DateTimeField("زمان تأیید", null=True, blank=True)
    deleted_at = models.DateTimeField("زمان حذف", null=True, blank=True)
    current_revision = models.ForeignKey(
        "EstimateRevision",
        verbose_name="بازنگری جاری",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_for_estimates",
    )

    class Meta:
        verbose_name = "برآورد"
        verbose_name_plural = "برآوردها"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "estimate_number"],
                name="unique_estimate_number_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "status"],
                name="estimate_org_status_idx",
            ),
            models.Index(
                fields=["organization", "deleted_at"],
                name="estimate_org_deleted_idx",
            ),
            models.Index(
                fields=["organization", "phase", "status"],
                name="estimate_org_phase_status_idx",
            ),
        ]
        ordering = ["-created_at"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.estimate_number = canonicalize_upper_identifier(self.estimate_number)
        relations = {}
        if self.project_id:
            relations["project"] = self.project
        if self.phase_id:
            relations["phase"] = self.phase
        if self.contract_id:
            relations["contract"] = self.contract
        validate_related_organizations(self, **relations)
        if self.phase_id and self.phase.site.project_id != self.project_id:
            raise ValidationError({"phase": "فاز باید متعلق به پروژه انتخاب‌شده باشد."})
        if self.contract_id and self.contract.project_id != self.project_id:
            raise ValidationError(
                {"contract": "قرارداد باید متعلق به پروژه انتخاب‌شده باشد."}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        self.estimate_number = canonicalize_upper_identifier(self.estimate_number)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.estimate_number} - {self.title}"

    @property
    def total_amount(self) -> Decimal:
        if self.current_revision_id:
            return self.current_revision.total_amount
        return sum(
            (item.line_total for item in self.items.all()),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class EstimateRevisionStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    APPROVED = "approved", "تأییدشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class EstimateRevision(UUIDModel, TimeStampedModel):
    """Versioned estimate terms; approvals remain immutable historical evidence."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="estimate_revisions",
    )
    estimate = models.ForeignKey(
        Estimate,
        verbose_name="برآورد",
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField("شماره بازنگری")
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=EstimateRevisionStatus.choices,
        default=EstimateRevisionStatus.DRAFT,
    )
    notes = models.TextField("یادداشت‌ها", blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="تأییدکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimate_revisions_approved",
    )
    approved_at = models.DateTimeField("زمان تأیید", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimate_revisions_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estimate_revisions_updated",
    )

    class Meta:
        verbose_name = "بازنگری برآورد"
        verbose_name_plural = "بازنگری‌های برآورد"
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["estimate", "revision_number"],
                name="unique_estimate_revision_number",
            )
        ]
        ordering = ["revision_number"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        if self.estimate_id:
            validate_related_organizations(self, estimate=self.estimate)

    @property
    def total_amount(self) -> Decimal:
        return sum(
            (item.line_total for item in self.items.all()), Decimal("0.00")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if previous.status in {
                EstimateRevisionStatus.APPROVED,
                EstimateRevisionStatus.SUPERSEDED,
            }:
                raise ValidationError("بازنگری نهایی‌شده برآورد قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class EstimateItem(UUIDModel, TimeStampedModel):
    """A priced line item belonging to one estimate and organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="estimate_items",
    )
    estimate = models.ForeignKey(
        Estimate,
        verbose_name="برآورد",
        on_delete=models.CASCADE,
        related_name="items",
    )
    revision = models.ForeignKey(
        EstimateRevision,
        verbose_name="بازنگری",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    description = models.CharField("شرح ردیف", max_length=255)
    quantity = models.DecimalField("مقدار", max_digits=18, decimal_places=4)
    unit = models.CharField("واحد قدیمی", max_length=30, default="unit")
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure",
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="estimate_items",
    )
    unit_price = models.DecimalField("قیمت واحد", max_digits=18, decimal_places=2)
    sort_order = models.PositiveIntegerField("ترتیب نمایش", default=0)

    price_book_mapping = models.ForeignKey(
        "EstimatePriceBookMapping",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="current_uses",
    )

    class Meta:
        verbose_name = "ردیف برآورد"
        verbose_name_plural = "ردیف‌های برآورد"
        ordering = ["sort_order", "created_at"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "estimate"],
                name="estimate_item_org_est_idx",
            ),
        ]

    @property
    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def __str__(self) -> str:
        return f"{self.description} ({self.line_total})"

    def clean(self) -> None:
        super().clean()
        if self.estimate_id:
            relations = {"estimate": self.estimate}
            if self.revision_id:
                relations["revision"] = self.revision
            if self.unit_of_measure_id:
                relations["unit_of_measure"] = self.unit_of_measure
            validate_related_organizations(self, **relations)
            if self.revision_id and self.revision.estimate_id != self.estimate_id:
                raise ValidationError(
                    {"revision": "بازنگری باید متعلق به همین برآورد باشد."}
                )
            if self.unit_of_measure_id and (
                not self.unit_of_measure.is_active or self.unit_of_measure.archived_at
            ):
                raise ValidationError(
                    {"unit_of_measure": "واحد اندازه‌گیری باید فعال باشد."}
                )

        if self.price_book_mapping_id:
            mapping = self.price_book_mapping
            if (
                mapping.organization_id != self.organization_id
                or mapping.source_item_id != self.pk
                or mapping.source_revision_id != self.revision_id
            ):
                raise ValidationError("نگاشت باید متعلق به همین ردیف و بازنگری باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if (
            self.pk
            and not self._state.adding
            and self.revision_id
            and self.revision.status != EstimateRevisionStatus.DRAFT
        ):
            raise ValidationError("ردیف بازنگری نهایی‌شده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class EstimateResourceType(models.TextChoices):
    LABOR = "labor", "نیروی کار"
    MATERIAL = "material", "مصالح"
    EQUIPMENT = "equipment", "تجهیزات"


class EstimatePriceSource(UUIDModel, TimeStampedModel):
    """Versioned provenance only; it does not activate a price book."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    code = models.CharField("کد منبع", max_length=50)
    name = models.CharField("نام منبع", max_length=255)
    version = models.CharField("نسخه منبع", max_length=80)
    source_reference = models.CharField("مرجع منبع", max_length=255)
    license_reference = models.CharField("مرجع مجوز", max_length=255)
    is_external = models.BooleanField("منبع خارجی", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="estimate_price_sources_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code", "version"],
                name="estimate_price_source_org_code_ver_uq",
            )
        ]

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        self.version = self.version.strip()
        self.source_reference = self.source_reference.strip()
        self.license_reference = self.license_reference.strip()
        if not all(
            (
                self.code,
                self.name,
                self.version,
                self.source_reference,
                self.license_reference,
            )
        ):
            raise ValidationError("کد، نام، نسخه، مرجع و مجوز منبع قیمت الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("منبع قیمت قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class EstimateRate(UUIDModel, TimeStampedModel):
    """Immutable rate-lineage record. Application awaits P4-G02."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    price_source = models.ForeignKey(
        EstimatePriceSource, on_delete=models.PROTECT, related_name="rates"
    )
    resource_type = models.CharField(
        max_length=20, choices=EstimateResourceType.choices
    )
    code = models.CharField("کد نرخ", max_length=80)
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure", on_delete=models.PROTECT
    )
    rate = models.DecimalField("نرخ", max_digits=18, decimal_places=4)
    source_version_snapshot = models.CharField("نسخه ثبت‌شده", max_length=80)
    source_reference_snapshot = models.CharField("مرجع ثبت‌شده", max_length=255)
    license_reference_snapshot = models.CharField("مجوز ثبت‌شده", max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="estimate_rates_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["price_source", "code"], name="estimate_rate_source_code_uq"
            )
        ]

    def clean(self) -> None:
        self.code = canonicalize_upper_identifier(self.code)
        if (
            self.organization_id != self.price_source.organization_id
            or self.organization_id != self.unit_of_measure.organization_id
        ):
            raise ValidationError("منبع نرخ و واحد باید متعلق به همین سازمان باشند.")
        if self.rate < Decimal(0):
            raise ValidationError({"rate": "نرخ نمی‌تواند منفی باشد."})
        if not all(
            (
                self.source_version_snapshot.strip(),
                self.source_reference_snapshot.strip(),
                self.license_reference_snapshot.strip(),
            )
        ):
            raise ValidationError("نسخه، مرجع و مجوز ثبت‌شده نرخ الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            raise ValidationError("رکورد نرخ قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class EstimateResource(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    estimate_item = models.ForeignKey(
        EstimateItem, on_delete=models.CASCADE, related_name="resources"
    )
    resource_type = models.CharField(
        max_length=20, choices=EstimateResourceType.choices
    )
    description = models.CharField("شرح منبع", max_length=255)
    quantity = models.DecimalField("مقدار", max_digits=18, decimal_places=4)
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure", on_delete=models.PROTECT
    )
    material = models.ForeignKey(
        "materials.Material", null=True, blank=True, on_delete=models.PROTECT
    )
    activity = models.ForeignKey(
        "projects.Activity", null=True, blank=True, on_delete=models.PROTECT
    )
    equipment = models.ForeignKey(
        "equipment.Equipment", null=True, blank=True, on_delete=models.PROTECT
    )
    rate = models.ForeignKey(
        EstimateRate, null=True, blank=True, on_delete=models.PROTECT
    )

    def clean(self) -> None:
        item = self.estimate_item
        if (
            self.organization_id != item.organization_id
            or self.organization_id != self.unit_of_measure.organization_id
        ):
            raise ValidationError("منبع و واحد باید متعلق به سازمان ردیف برآورد باشند.")
        if item.revision_id and item.revision.status != EstimateRevisionStatus.DRAFT:
            raise ValidationError("منابع بازنگری نهایی‌شده قابل تغییر نیستند.")
        if self.quantity <= Decimal(0):
            raise ValidationError({"quantity": "مقدار منبع باید مثبت باشد."})
        if self.material_id and (
            self.resource_type != EstimateResourceType.MATERIAL
            or self.material.organization_id != self.organization_id
            or self.material.unit_of_measure_id != self.unit_of_measure_id
        ):
            raise ValidationError(
                "مصالح باید با نوع منبع، سازمان و واحد پایه سازگار باشد."
            )
        if self.equipment_id and (
            self.resource_type != EstimateResourceType.EQUIPMENT
            or self.equipment.organization_id != self.organization_id
        ):
            raise ValidationError("تجهیز باید با نوع منبع و سازمان سازگار باشد.")
        if self.activity_id and (
            self.activity.organization_id != self.organization_id
            or self.activity.project_id != item.estimate.project_id
        ):
            raise ValidationError("فعالیت باید متعلق به پروژه همین برآورد باشد.")
        if self.rate_id and (
            self.rate.organization_id != self.organization_id
            or self.rate.unit_of_measure_id != self.unit_of_measure_id
        ):
            raise ValidationError("نرخ باید متعلق به سازمان و واحد منبع باشد.")

    def save(self, *args: object, **kwargs: object) -> None:
        if (
            self.pk
            and not self._state.adding
            and self.estimate_item.revision.status != EstimateRevisionStatus.DRAFT
        ):
            raise ValidationError("منابع بازنگری نهایی‌شده قابل تغییر نیستند.")
        self.full_clean()
        super().save(*args, **kwargs)


class EstimateAssumptionKind(models.TextChoices):
    COEFFICIENT = "coefficient", "ضریب"
    ASSUMPTION = "assumption", "فرض"


class EstimateAssumption(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    revision = models.ForeignKey(
        EstimateRevision, on_delete=models.CASCADE, related_name="assumptions"
    )
    kind = models.CharField(max_length=20, choices=EstimateAssumptionKind.choices)
    name = models.CharField("نام", max_length=255)
    decimal_value = models.DecimalField(
        "مقدار", max_digits=18, decimal_places=6, null=True, blank=True
    )
    sequence = models.PositiveIntegerField("ترتیب", default=0)
    rationale = models.TextField("مبنای فرض")
    source_reference = models.CharField("مرجع", max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="estimate_assumptions_created",
    )

    def clean(self) -> None:
        if self.organization_id != self.revision.organization_id:
            raise ValidationError("فرض باید متعلق به سازمان بازنگری باشد.")
        if self.revision.status != EstimateRevisionStatus.DRAFT:
            raise ValidationError("فرض بازنگری نهایی‌شده قابل تغییر نیست.")
        if not all(
            (self.name.strip(), self.rationale.strip(), self.source_reference.strip())
        ):
            raise ValidationError("نام، مبنا و مرجع فرض الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if (
            self.pk
            and not self._state.adding
            and self.revision.status != EstimateRevisionStatus.DRAFT
        ):
            raise ValidationError("فرض بازنگری نهایی‌شده قابل تغییر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


from .price_book_models import (  # noqa: F401
    EstimatePriceBookMapping,
    PriceBook,
    PriceBookActivation,
    PriceBookRow,
    PriceBookVersion,
)
