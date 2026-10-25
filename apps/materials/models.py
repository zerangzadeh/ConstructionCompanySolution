from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.identifiers import canonicalize_upper_identifier
from core.models import TimeStampedModel, UUIDModel


class UnitCategory(models.TextChoices):
    COUNT = "count", "تعداد"
    LENGTH = "length", "طول"
    AREA = "area", "مساحت"
    VOLUME = "volume", "حجم"
    WEIGHT = "weight", "وزن"
    TIME = "time", "زمان"
    OTHER = "other", "سایر"


class UnitDimension(models.TextChoices):
    COUNT = "count", "تعداد"
    LENGTH = "length", "طول"
    AREA = "area", "مساحت"
    VOLUME = "volume", "حجم"
    WEIGHT = "weight", "وزن"
    TIME = "time", "زمان"
    DIMENSIONLESS = "dimensionless", "بدون بعد"
    ISOLATED = "isolated", "غیرقابل تبدیل"


class QuantityRoundingMode(models.TextChoices):
    HALF_UP = "half_up", "نیم به بالا"
    HALF_EVEN = "half_even", "نیم به زوج"
    DOWN = "down", "به پایین"
    UP = "up", "به بالا"


class MaterialAttributeValueType(models.TextChoices):
    TEXT = "text", "متن"
    DECIMAL = "decimal", "عدد اعشاری"
    INTEGER = "integer", "عدد صحیح"
    BOOLEAN = "boolean", "بله/خیر"
    CHOICE = "choice", "گزینه بسته"


class MaterialAttributeOperator(models.TextChoices):
    EQUALS = "equals", "برابر"
    CONTAINS = "contains", "شامل"
    GREATER_THAN = "gt", "بزرگ‌تر از"
    GREATER_THAN_OR_EQUAL = "gte", "بزرگ‌تر یا برابر"
    LESS_THAN = "lt", "کوچک‌تر از"
    LESS_THAN_OR_EQUAL = "lte", "کوچک‌تر یا برابر"


ATTRIBUTE_OPERATORS_BY_TYPE = {
    MaterialAttributeValueType.TEXT: {
        MaterialAttributeOperator.EQUALS,
        MaterialAttributeOperator.CONTAINS,
    },
    MaterialAttributeValueType.DECIMAL: {
        MaterialAttributeOperator.EQUALS,
        MaterialAttributeOperator.GREATER_THAN,
        MaterialAttributeOperator.GREATER_THAN_OR_EQUAL,
        MaterialAttributeOperator.LESS_THAN,
        MaterialAttributeOperator.LESS_THAN_OR_EQUAL,
    },
    MaterialAttributeValueType.INTEGER: {
        MaterialAttributeOperator.EQUALS,
        MaterialAttributeOperator.GREATER_THAN,
        MaterialAttributeOperator.GREATER_THAN_OR_EQUAL,
        MaterialAttributeOperator.LESS_THAN,
        MaterialAttributeOperator.LESS_THAN_OR_EQUAL,
    },
    MaterialAttributeValueType.BOOLEAN: {MaterialAttributeOperator.EQUALS},
    MaterialAttributeValueType.CHOICE: {MaterialAttributeOperator.EQUALS},
}


class UnitFamily(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="unit_families"
    )
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    dimension = models.CharField(max_length=20, choices=UnitDimension.choices)
    base_unit = models.OneToOneField(
        "UnitOfMeasure",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="base_for_family",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="unit_families_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"], name="unit_family_org_code_uq"
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if self.base_unit_id and self.base_unit.organization_id != self.organization_id:
            raise ValidationError("واحد مبنا و خانواده باید متعلق به یک سازمان باشند.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class UnitOfMeasure(UUIDModel, TimeStampedModel):
    """A tenant-owned canonical unit vocabulary without conversion behavior."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="units_of_measure",
    )
    code = models.CharField("کد", max_length=20)
    name = models.CharField("نام", max_length=100)
    symbol = models.CharField("نماد", max_length=20)
    category = models.CharField("دسته‌بندی", max_length=20, choices=UnitCategory.choices)
    family = models.ForeignKey(
        UnitFamily,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="units",
    )
    decimal_places = models.PositiveSmallIntegerField("تعداد رقم اعشار", default=0)
    is_active = models.BooleanField("فعال", default=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="units_of_measure_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="units_of_measure_updated",
    )

    class Meta:
        verbose_name = "واحد اندازه‌گیری"
        verbose_name_plural = "واحدهای اندازه‌گیری"
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
            raise ValidationError("وارد کردن کد، نام و نماد واحد الزامی است.")
        if self.decimal_places > 6:
            raise ValidationError(
                {"decimal_places": "تعداد رقم اعشار نمی‌تواند بیشتر از ۶ باشد."}
            )
        if self.family_id and self.family.organization_id != self.organization_id:
            raise ValidationError({"family": "خانواده واحد باید متعلق به همین سازمان باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} ({self.symbol})"


class MaterialCategory(UUIDModel, TimeStampedModel):
    """An optional, tenant-owned grouping for the material catalog."""

    organization = models.ForeignKey(
        "organizations.Organization",
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="material_categories",
    )
    code = models.CharField("کد", max_length=30)
    name = models.CharField("نام", max_length=100)
    parent = models.ForeignKey(
        "self",
        verbose_name="دسته‌بندی والد",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    is_active = models.BooleanField("فعال", default=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_categories_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_categories_updated",
    )

    class Meta:
        verbose_name = "دسته‌بندی مصالح"
        verbose_name_plural = "دسته‌بندی‌های مصالح"
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
            raise ValidationError("وارد کردن کد و نام دسته‌بندی مصالح الزامی است.")
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "دسته‌بندی نمی‌تواند والد خودش باشد."})
            if self.organization_id != self.parent.organization_id:
                raise ValidationError(
                    {"parent": "دسته‌بندی والد باید متعلق به همین سازمان باشد."}
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
        verbose_name="سازمان",
        on_delete=models.CASCADE,
        related_name="materials",
    )
    code = models.CharField("کد", max_length=50)
    name = models.CharField("نام مصالح", max_length=255)
    category = models.ForeignKey(
        MaterialCategory,
        verbose_name="دسته‌بندی",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="materials",
    )
    unit_of_measure = models.ForeignKey(
        UnitOfMeasure,
        verbose_name="واحد اندازه‌گیری",
        on_delete=models.PROTECT,
        related_name="materials",
    )
    specifications = models.TextField("مشخصات فنی", blank=True)
    is_active = models.BooleanField("فعال", default=True)
    archived_at = models.DateTimeField("زمان بایگانی", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ایجادکننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materials_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="آخرین ویرایش‌کننده",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materials_updated",
    )

    class Meta:
        verbose_name = "مصالح"
        verbose_name_plural = "مصالح"
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
            raise ValidationError("وارد کردن کد و نام مصالح الزامی است.")
        if not self.unit_of_measure_id:
            raise ValidationError(
                {"unit_of_measure": "انتخاب واحد اندازه‌گیری الزامی است."}
            )
        if self.organization_id != self.unit_of_measure.organization_id:
            raise ValidationError(
                {"unit_of_measure": "واحد اندازه‌گیری باید متعلق به همین سازمان باشد."}
            )
        if (
            self.unit_of_measure.archived_at is not None
            or not self.unit_of_measure.is_active
        ):
            raise ValidationError(
                {"unit_of_measure": "واحد اندازه‌گیری باید فعال باشد."}
            )
        if self.category_id:
            if self.organization_id != self.category.organization_id:
                raise ValidationError(
                    {"category": "دسته‌بندی مصالح باید متعلق به همین سازمان باشد."}
                )
            if self.category.archived_at is not None or not self.category.is_active:
                raise ValidationError({"category": "دسته‌بندی مصالح باید فعال باشد."})

    def save(self, *args: object, **kwargs: object) -> None:
        if self.pk and not self._state.adding:
            original_code = (
                type(self).objects.filter(pk=self.pk).values_list("code", flat=True).first()
            )
            if original_code and canonicalize_upper_identifier(self.code) != original_code:
                transactional_relations = (
                    "purchase_request_items",
                    "purchase_order_items",
                    "goods_receipt_items",
                    "stock_transactions",
                    "daily_report_entries",
                )
                if any(
                    getattr(self, relation).exists()
                    for relation in transactional_relations
                ):
                    raise ValidationError(
                        {"code": "کد مصالح پس از نخستین استفاده تراکنشی تغییرپذیر نیست."}
                    )
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class MaterialAlias(UUIDModel, TimeStampedModel):
    """Immutable Tenant-local alternate identifier resolving to a material."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="material_aliases",
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="aliases"
    )
    code = models.CharField(max_length=50)
    label = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="material_aliases_created",
    )
    reason = models.TextField()

    class Meta:
        ordering = ["code"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"], name="material_alias_org_code_uq"
            )
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.label = self.label.strip()
        if self.organization_id != self.material.organization_id:
            raise ValidationError("شناسه جایگزین و مصالح باید متعلق به یک سازمان باشند.")
        if not self.code or not self.reason.strip():
            raise ValidationError("کد جایگزین و دلیل ثبت آن الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("شناسه جایگزین مصالح تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("شناسه جایگزین مصالح حذف‌پذیر نیست.")


class MaterialDuplicateCandidate(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "باز"
        DISMISSED = "dismissed", "ردشده"
        SUPERSEDED = "superseded", "جایگزین‌شده"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="material_duplicate_candidates",
    )
    left = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="duplicate_candidates_left"
    )
    right = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="duplicate_candidates_right"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    evidence = models.JSONField(default=dict)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="material_duplicate_candidates_reviewed",
    )
    review_reason = models.TextField(blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "left", "right"],
                name="material_duplicate_pair_uq",
            ),
            models.CheckConstraint(
                condition=~models.Q(left=models.F("right")),
                name="material_duplicate_distinct_records",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.left_id and self.right_id and self.left_id.hex > self.right_id.hex:
            raise ValidationError("ترتیب شناسه‌های نامزد تکراری معتبر نیست.")
        if (
            self.organization_id != self.left.organization_id
            or self.organization_id != self.right.organization_id
        ):
            raise ValidationError("نامزدهای تکراری باید متعلق به یک سازمان باشند.")


class MaterialSupersession(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="material_supersessions",
    )
    source = models.OneToOneField(
        Material, on_delete=models.PROTECT, related_name="supersession"
    )
    survivor = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="superseded_materials"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="material_supersessions_created",
    )
    reason = models.TextField()

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=~models.Q(source=models.F("survivor")),
                name="material_supersession_distinct_records",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.organization_id != self.source.organization_id
            or self.organization_id != self.survivor.organization_id
        ):
            raise ValidationError("مصالح جایگزین‌شده باید متعلق به یک سازمان باشند.")
        current = self.survivor
        visited = {self.source_id}
        while hasattr(current, "supersession"):
            if current.pk in visited:
                raise ValidationError("زنجیره جایگزینی مصالح نمی‌تواند چرخه داشته باشد.")
            visited.add(current.pk)
            current = current.supersession.survivor

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("جایگزینی مصالح تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("جایگزینی مصالح حذف‌پذیر نیست.")


class UnitConversionVersion(UUIDModel, TimeStampedModel):
    """Immutable directed factor from one unit to its family base."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="unit_conversion_versions",
    )
    family = models.ForeignKey(
        UnitFamily, on_delete=models.PROTECT, related_name="conversion_versions"
    )
    unit = models.ForeignKey(
        UnitOfMeasure, on_delete=models.PROTECT, related_name="conversion_versions"
    )
    version = models.PositiveIntegerField()
    factor_to_base = models.DecimalField(max_digits=30, decimal_places=15)
    effective_from = models.DateTimeField()
    effective_until = models.DateTimeField(null=True, blank=True)
    source_reference = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="unit_conversion_versions_created",
    )

    class Meta:
        ordering = ["unit", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["unit", "version"], name="unit_conversion_version_uq"
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1), name="unit_conversion_version_positive"
            ),
            models.CheckConstraint(
                condition=Q(factor_to_base__gt=0),
                name="unit_conversion_factor_positive",
            ),
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gt=models.F("effective_from")),
                name="unit_conversion_effective_interval",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.organization_id != self.family.organization_id
            or self.organization_id != self.unit.organization_id
            or self.unit.family_id != self.family_id
        ):
            raise ValidationError("نسخه تبدیل، واحد و خانواده باید هم‌سازمان باشند.")
        if self.family.base_unit_id == self.unit_id:
            raise ValidationError("واحد مبنا به ضریب تبدیل مستقل نیاز ندارد.")
        if not self.source_reference.strip():
            raise ValidationError("مرجع منبع ضریب تبدیل الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("نسخه ضریب تبدیل تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class QuantityRoundingPolicyVersion(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="quantity_rounding_policy_versions",
    )
    code = models.CharField(max_length=50)
    version = models.PositiveIntegerField()
    scale = models.PositiveSmallIntegerField()
    mode = models.CharField(max_length=20, choices=QuantityRoundingMode.choices)
    effective_from = models.DateTimeField()
    effective_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quantity_rounding_policies_created",
    )

    class Meta:
        ordering = ["code", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code", "version"],
                name="quantity_rounding_policy_version_uq",
            ),
            models.CheckConstraint(
                condition=Q(scale__lte=12), name="quantity_rounding_scale_limit"
            ),
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gt=models.F("effective_from")),
                name="quantity_rounding_effective_interval",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("نسخه سیاست گرد کردن تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class QuantityConversionSnapshot(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="quantity_conversion_snapshots",
    )
    context_key = models.CharField(max_length=160)
    input_unit = models.ForeignKey(
        UnitOfMeasure, on_delete=models.PROTECT, related_name="conversion_inputs"
    )
    output_unit = models.ForeignKey(
        UnitOfMeasure, on_delete=models.PROTECT, related_name="conversion_outputs"
    )
    input_conversion_version = models.ForeignKey(
        UnitConversionVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="input_snapshots",
    )
    output_conversion_version = models.ForeignKey(
        UnitConversionVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="output_snapshots",
    )
    rounding_policy_version = models.ForeignKey(
        QuantityRoundingPolicyVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="conversion_snapshots",
    )
    input_quantity = models.DecimalField(max_digits=36, decimal_places=18)
    unrounded_result = models.DecimalField(max_digits=36, decimal_places=18)
    output_quantity = models.DecimalField(max_digits=36, decimal_places=18)
    converted_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quantity_conversion_snapshots_created",
    )

    class Meta:
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "context_key"],
                name="qty_conversion_org_context_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        related = (
            self.input_unit,
            self.output_unit,
            self.input_conversion_version,
            self.output_conversion_version,
            self.rounding_policy_version,
        )
        if any(
            item is not None and item.organization_id != self.organization_id
            for item in related
        ):
            raise ValidationError("تصویر تبدیل فقط می‌تواند به داده‌های همان سازمان ارجاع دهد.")
        if (
            self.input_unit_id
            and self.output_unit_id
            and self.input_unit.family_id != self.output_unit.family_id
        ):
            raise ValidationError("واحدهای تصویر تبدیل باید هم‌خانواده باشند.")
        if (
            self.input_conversion_version_id
            and self.input_conversion_version.unit_id != self.input_unit_id
        ) or (
            self.output_conversion_version_id
            and self.output_conversion_version.unit_id != self.output_unit_id
        ):
            raise ValidationError("نسخه ضریب تبدیل با واحد تصویر هم‌خوان نیست.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("تصویر تبدیل کمیت تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class MaterialAttributeDefinition(UUIDModel, TimeStampedModel):
    """Tenant-owned category attribute identity; meaning lives in immutable versions."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="material_attribute_definitions",
    )
    category = models.ForeignKey(
        MaterialCategory,
        on_delete=models.PROTECT,
        related_name="attribute_definitions",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="material_attribute_definitions_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "category", "code"],
                name="material_attribute_definition_category_code_uq",
            )
        ]
        ordering = ["category", "code"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        self.code = canonicalize_upper_identifier(self.code)
        self.name = self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("کد و نام تعریف ویژگی مصالح الزامی است.")
        if self.organization_id != self.category.organization_id:
            raise ValidationError("تعریف ویژگی و دسته‌بندی باید متعلق به یک سازمان باشند.")

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class MaterialAttributeDefinitionVersion(UUIDModel, TimeStampedModel):
    definition = models.ForeignKey(
        MaterialAttributeDefinition,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version = models.PositiveIntegerField()
    value_type = models.CharField(max_length=20, choices=MaterialAttributeValueType.choices)
    allowed_operators = models.JSONField(default=list)
    choice_values = models.JSONField(default=list)
    effective_from = models.DateTimeField()
    effective_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="material_attribute_definition_versions_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["definition", "version"],
                name="material_attribute_definition_version_uq",
            ),
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gt=models.F("effective_from")),
                name="material_attribute_definition_effective_interval",
            ),
        ]
        ordering = ["definition", "version"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        if self.value_type not in MaterialAttributeValueType.values:
            raise ValidationError("نوع مقدار ویژگی مصالح معتبر نیست.")
        if not isinstance(self.allowed_operators, list) or any(
            not isinstance(operator, str) for operator in self.allowed_operators
        ):
            raise ValidationError("عملگرهای تعریف ویژگی مصالح معتبر نیستند.")
        operators = set(self.allowed_operators)
        allowed = ATTRIBUTE_OPERATORS_BY_TYPE[self.value_type]
        if not operators or not operators <= allowed:
            raise ValidationError("عملگرهای تعریف ویژگی مصالح معتبر نیستند.")
        if self.value_type == MaterialAttributeValueType.CHOICE:
            if (
                not isinstance(self.choice_values, list)
                or not self.choice_values
                or any(not isinstance(item, str) or not item.strip() for item in self.choice_values)
                or len({item.strip() for item in self.choice_values}) != len(self.choice_values)
            ):
                raise ValidationError("گزینه‌های بسته ویژگی مصالح معتبر نیستند.")
        elif self.choice_values:
            raise ValidationError("فقط ویژگی گزینه‌بسته می‌تواند گزینه تعریف کند.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("نسخه تعریف ویژگی مصالح تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class MaterialAttributeValue(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="material_attribute_values",
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="attribute_values"
    )
    definition = models.ForeignKey(
        MaterialAttributeDefinition,
        on_delete=models.PROTECT,
        related_name="values",
    )
    definition_version = models.ForeignKey(
        MaterialAttributeDefinitionVersion,
        on_delete=models.PROTECT,
        related_name="values",
    )
    value = models.JSONField()
    normalized_value = models.CharField(max_length=500, blank=True)
    source_reference = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="material_attribute_values_created",
    )

    class Meta:
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "definition", "normalized_value"],
                name="mat_attr_value_search_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.organization_id != self.material.organization_id
            or self.organization_id != self.definition.organization_id
            or self.definition_version.definition_id != self.definition_id
        ):
            raise ValidationError("مقدار، تعریف و مصالح باید هم‌سازمان و هم‌نسخه باشند.")
        if self.material.category_id != self.definition.category_id:
            raise ValidationError("ویژگی فقط برای دسته‌بندی تعریف‌شده مصالح مجاز است.")
        value_type = self.definition_version.value_type
        if value_type == MaterialAttributeValueType.TEXT:
            if not isinstance(self.value, str) or not self.value.strip():
                raise ValidationError("مقدار متن ویژگی معتبر نیست.")
            self.normalized_value = self.value.strip()
        elif value_type == MaterialAttributeValueType.DECIMAL:
            if not isinstance(self.value, str):
                raise ValidationError("مقدار اعشاری ویژگی باید به‌صورت رشته دقیق باشد.")
            try:
                normalized = str(Decimal(self.value))
            except InvalidOperation as exc:
                raise ValidationError("مقدار اعشاری ویژگی معتبر نیست.") from exc
            self.value = normalized
            self.normalized_value = normalized
        elif value_type == MaterialAttributeValueType.INTEGER:
            if isinstance(self.value, bool) or not isinstance(self.value, int):
                raise ValidationError("مقدار صحیح ویژگی معتبر نیست.")
            self.normalized_value = str(self.value)
        elif value_type == MaterialAttributeValueType.BOOLEAN:
            if not isinstance(self.value, bool):
                raise ValidationError("مقدار بله/خیر ویژگی معتبر نیست.")
            self.normalized_value = str(self.value).lower()
        elif value_type == MaterialAttributeValueType.CHOICE:
            if (
                not isinstance(self.value, str)
                or self.value.strip() not in self.definition_version.choice_values
            ):
                raise ValidationError("گزینه ویژگی مصالح معتبر نیست.")
            self.value = self.value.strip()
            self.normalized_value = self.value

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("مقدار ویژگی مصالح تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class MaterialAttributeImportRun(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="material_attribute_import_runs",
    )
    idempotency_key = models.CharField(max_length=100)
    source_label = models.CharField(max_length=255)
    total_rows = models.PositiveIntegerField(default=0)
    accepted_rows = models.PositiveIntegerField(default=0)
    rejected_rows = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="material_attribute_import_runs_created",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="material_attribute_import_idempotency_uq",
            )
        ]


class MaterialAttributeImportRow(UUIDModel, TimeStampedModel):
    run = models.ForeignKey(
        MaterialAttributeImportRun, on_delete=models.PROTECT, related_name="rows"
    )
    row_number = models.PositiveIntegerField()
    material_identifier = models.CharField(max_length=100)
    definition_code = models.CharField(max_length=50)
    supplied_value = models.JSONField()
    accepted_value = models.ForeignKey(
        MaterialAttributeValue,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="import_rows",
    )
    error = models.TextField(blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["run", "row_number"], name="material_attribute_import_row_uq"
            )
        ]


class MaterialPriceObservation(UUIDModel, TimeStampedModel):
    """Sourced market/reference observation; intentionally not a quote or ledger fact."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="material_price_observations",
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="price_observations"
    )
    unit = models.ForeignKey(
        UnitOfMeasure, on_delete=models.PROTECT, related_name="material_price_observations"
    )
    amount = models.DecimalField(max_digits=20, decimal_places=4)
    currency = models.CharField(max_length=3)
    source_reference = models.CharField(max_length=255)
    observed_at = models.DateTimeField()
    effective_from = models.DateTimeField()
    effective_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="material_price_observations_created",
    )

    class Meta:
        indexes = [  # noqa: RUF012
            models.Index(
                fields=["organization", "material", "effective_from"],
                name="mat_price_observation_idx",
            )
        ]
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="material_price_observation_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gt=models.F("effective_from")),
                name="material_price_observation_effective_interval",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self.currency = self.currency.strip().upper()
        self.source_reference = self.source_reference.strip()
        if (
            self.organization_id != self.material.organization_id
            or self.organization_id != self.unit.organization_id
        ):
            raise ValidationError("مشاهده قیمت، مصالح و واحد باید متعلق به یک سازمان باشند.")
        if self.unit_id != self.material.unit_of_measure_id:
            raise ValidationError("واحد مشاهده قیمت باید واحد معیار مصالح باشد.")
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.source_reference:
            raise ValidationError("ارز سه‌حرفی و مرجع مشاهده قیمت الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("مشاهده قیمت مصالح تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class MaterialRelationshipType(models.TextChoices):
    EQUIVALENT = "equivalent", "هم‌ارز"
    SUBSTITUTE = "substitute", "جایگزین پیشنهادی"


class MaterialRelationship(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    source = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="relationships_from")
    candidate = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="relationships_to")
    relationship_type = models.CharField(max_length=20, choices=MaterialRelationshipType.choices)
    reason = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(fields=["organization", "source", "candidate", "relationship_type"], name="material_relationship_uq"),
            models.CheckConstraint(condition=~Q(source=models.F("candidate")), name="material_relationship_distinct"),
        ]

    def clean(self) -> None:
        super().clean()
        if self.organization_id != self.source.organization_id or self.organization_id != self.candidate.organization_id:
            raise ValidationError("رابطه مصالح باید Tenant-local باشد.")
        if not self.reason.strip():
            raise ValidationError("دلیل رابطه مصالح الزامی است.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("رابطه مصالح تغییرپذیر نیست.")
        self.full_clean()
        super().save(*args, **kwargs)


class MaterialTechnicalApprovalStatus(models.TextChoices):
    LEGACY_UNREVIEWED = "legacy_unreviewed", "قدیمیِ بررسی‌نشده"
    DRAFT = "draft", "پیش‌نویس"
    REVIEW = "review", "در بررسی"
    APPROVED = "approved", "تأییدشده"
    REJECTED = "rejected", "ردشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class MaterialTechnicalApproval(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="technical_approvals")
    revision = models.PositiveIntegerField()
    status = models.CharField(max_length=24, choices=MaterialTechnicalApprovalStatus.choices)
    scope_project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.PROTECT)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="material_technical_submissions")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="material_technical_reviews")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="material_technical_decisions")
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["material", "revision"], name="material_technical_approval_revision_uq"
            )
        ]
        ordering = ["material", "revision"]  # noqa: RUF012

    def clean(self) -> None:
        super().clean()
        if self.organization_id != self.material.organization_id or (self.scope_project_id and self.scope_project.organization_id != self.organization_id):
            raise ValidationError("تأیید فنی و دامنه آن باید Tenant-local باشند.")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("بازبینی فنی مصالح با گذار کنترل‌شده تغییر می‌کند.")
        self.full_clean()
        super().save(*args, **kwargs)


from apps.documents.models import AbstractTypedDocumentLink


class MaterialDocumentLink(AbstractTypedDocumentLink):
    target_field_name = "material"
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="document_links")
    document_version = models.ForeignKey("documents.DocumentVersion", on_delete=models.PROTECT, related_name="material_links")

    class Meta(AbstractTypedDocumentLink.Meta):
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["document", "material", "document_version"], name="material_document_link_uq"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.document_version.document_id != self.document_id:
            raise ValidationError("نسخه سند باید به همان سند لینک‌شده تعلق داشته باشد.")
