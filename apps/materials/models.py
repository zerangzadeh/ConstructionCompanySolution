from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel


class UnitCategory(models.TextChoices):
    COUNT = "count", "Count"
    LENGTH = "length", "Length"
    AREA = "area", "Area"
    VOLUME = "volume", "Volume"
    WEIGHT = "weight", "Weight"
    TIME = "time", "Time"
    OTHER = "other", "Other"


class UnitOfMeasure(UUIDModel, TimeStampedModel):
    """A tenant-owned canonical unit vocabulary without conversion behavior."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="units_of_measure",
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20)
    category = models.CharField(max_length=20, choices=UnitCategory.choices)
    decimal_places = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="units_of_measure_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="units_of_measure_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_uom_code_per_organization",
            ),
            models.UniqueConstraint(
                fields=["organization", "symbol"],
                name="unique_uom_symbol_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "is_active"],
                name="uom_org_active_idx",
            ),
        ]
        ordering = ["name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.symbol = self.symbol.strip()
        if not self.code or not self.name.strip() or not self.symbol:
            raise ValidationError("Unit code, name, and symbol are required.")
        if self.decimal_places > 6:
            raise ValidationError({"decimal_places": "Precision cannot exceed 6."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} ({self.symbol})"


class MaterialCategory(UUIDModel, TimeStampedModel):
    """An optional, tenant-owned grouping for the material catalog."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="material_categories",
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_categories_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_categories_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_material_category_code_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "is_active"],
                name="matcat_org_active_idx",
            ),
        ]
        ordering = ["name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("Material category code and name are required.")
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError(
                    {"parent": "A category cannot be its own parent."}
                )
            if self.organization_id != self.parent.organization_id:
                raise ValidationError(
                    {"parent": "Parent category must belong to the same organization."}
                )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Material(UUIDModel, TimeStampedModel):
    """A tenant-owned material with one canonical unit of measure."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="materials",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        MaterialCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="materials",
    )
    unit_of_measure = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    specifications = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materials_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materials_updated",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_material_code_per_organization",
            ),
        ]
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "is_active"], name="material_org_active_idx"
            ),
            models.Index(fields=["organization", "name"], name="material_org_name_idx"),
        ]
        ordering = ["name"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        self.specifications = self.specifications.strip()
        if not self.code or not self.name:
            raise ValidationError("Material code and name are required.")
        if self.organization_id != self.unit_of_measure.organization_id:
            raise ValidationError(
                {
                    "unit_of_measure": "Unit of measure must belong to the same organization."
                }
            )
        if (
            self.unit_of_measure.archived_at is not None
            or not self.unit_of_measure.is_active
        ):
            raise ValidationError(
                {"unit_of_measure": "Unit of measure must be active."}
            )
        if self.category_id:
            if self.organization_id != self.category.organization_id:
                raise ValidationError(
                    {
                        "category": "Material category must belong to the same organization."
                    }
                )
            if self.category.archived_at is not None or not self.category.is_active:
                raise ValidationError({"category": "Material category must be active."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"
