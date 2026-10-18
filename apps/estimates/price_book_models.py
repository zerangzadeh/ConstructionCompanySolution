"""Governed tenant Price Book sources and immutable mapping history (PD-017)."""

import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class PriceBookEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("شواهد فهرست‌بها تغییرناپذیر است.")

    def delete(self):
        raise ValidationError("شواهد فهرست‌بها حذف‌پذیر نیست.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("ثبت شواهد فقط از سرویس مجاز است.")


class PriceBookEvidence(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="+",
    )
    objects = PriceBookEvidenceQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("شواهد فهرست‌بها تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("شواهد فهرست‌بها حذف‌پذیر نیست.")

    def clean(self):
        validate_related_organizations(self, created_by=self.created_by)


class PriceBook(PriceBookEvidence):
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=255)
    source_authority = models.CharField(max_length=255)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "code"], name="price_book_tenant_code_uq"
            )
        ]

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()
        if not all((self.code, self.name.strip(), self.source_authority.strip())):
            raise ValidationError("هویت و مرجع فهرست‌بها الزامی است.")


class PriceBookVersion(PriceBookEvidence):
    book = models.ForeignKey(
        PriceBook, on_delete=models.PROTECT, related_name="versions"
    )
    version = models.CharField(max_length=80)
    publication_year = models.CharField(max_length=20)
    publication_reference = models.CharField(max_length=255)
    effective_from = models.DateField()
    effective_to = models.DateField()
    currency = models.CharField(max_length=3)
    source_reference = models.TextField()
    artifact_sha256 = models.CharField(max_length=64)
    content_sha256 = models.CharField(max_length=64)
    rows_sha256 = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successors",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["book", "version"], name="pb_version_identity_uq"
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"], name="pb_version_key_uq"
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__gte=models.F("effective_from")),
                name="pb_effective_dates_valid",
            ),
        ]

    def clean(self):
        super().clean()
        validate_related_organizations(self, book=self.book, supersedes=self.supersedes)
        if not all(
            str(getattr(self, n)).strip()
            for n in (
                "version",
                "publication_year",
                "publication_reference",
                "source_reference",
                "idempotency_key",
            )
        ) or not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValidationError("هویت انتشار، ارز و شواهد منبع الزامی است.")
        if any(
            not re.fullmatch(r"[0-9a-f]{64}", getattr(self, n))
            for n in ("artifact_sha256", "content_sha256", "rows_sha256")
        ):
            raise ValidationError("اثر انگشت منبع معتبر نیست.")
        if self.effective_to < self.effective_from:
            raise ValidationError("بازه اثر معتبر نیست.")
        if self.supersedes_id and (
            self.supersedes.book_id != self.book_id or self.supersedes_id == self.pk
        ):
            raise ValidationError("جانشینی باید به نسخه قبلی همان فهرست‌بها اشاره کند.")


class PriceBookRow(PriceBookEvidence):
    version = models.ForeignKey(
        PriceBookVersion, on_delete=models.PROTECT, related_name="rows"
    )
    code = models.CharField(max_length=80)
    chapter = models.CharField(max_length=120)
    description = models.CharField(max_length=255)
    unit_of_measure = models.ForeignKey(
        "materials.UnitOfMeasure", on_delete=models.PROTECT
    )
    value = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["version", "code"], name="pb_row_version_code_uq"
            ),
            models.CheckConstraint(
                condition=models.Q(value__gte=0), name="pb_row_nonnegative_value"
            ),
        ]

    def clean(self):
        super().clean()
        validate_related_organizations(
            self, version=self.version, unit_of_measure=self.unit_of_measure
        )
        if not all((self.code.strip(), self.chapter.strip(), self.description.strip())):
            raise ValidationError("کد، فصل و شرح ردیف الزامی است.")
        if PriceBookActivation.objects.filter(version=self.version).exists():
            raise ValidationError("ردیف نسخه فعال قابل افزودن نیست.")
        if self.value < 0 or not self.value.is_finite():
            raise ValidationError("مقدار ردیف معتبر نیست.")


class PriceBookActivation(PriceBookEvidence):
    version = models.OneToOneField(
        PriceBookVersion, on_delete=models.PROTECT, related_name="activation"
    )
    approval_reference = models.TextField()
    reviewed_artifact_sha256 = models.CharField(max_length=64)
    reviewed_content_sha256 = models.CharField(max_length=64)

    def clean(self):
        super().clean()
        validate_related_organizations(self, version=self.version)
        if (
            not self.approval_reference.strip()
            or self.reviewed_artifact_sha256 != self.version.artifact_sha256
            or self.reviewed_content_sha256 != self.version.content_sha256
            or not self.version.rows.exists()
        ):
            raise ValidationError("تأیید مستند منبع و محتوای واردشده الزامی است.")


class EstimatePriceBookMapping(PriceBookEvidence):
    identity = models.UUIDField(default=uuid.uuid4)
    version = models.PositiveIntegerField()
    source_item = models.ForeignKey(
        "estimates.EstimateItem",
        on_delete=models.PROTECT,
        related_name="price_book_history",
    )
    source_revision = models.ForeignKey(
        "estimates.EstimateRevision",
        on_delete=models.PROTECT,
        related_name="price_book_mappings",
    )
    row = models.ForeignKey(
        PriceBookRow, on_delete=models.PROTECT, related_name="mappings"
    )
    effective_date = models.DateField()
    evidence_reference = models.TextField()
    source_snapshot = models.JSONField()
    supersedes = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successor",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["identity", "version"], name="pb_mapping_identity_version_uq"
            )
        ]

    def clean(self):
        super().clean()
        validate_related_organizations(
            self,
            source_item=self.source_item,
            source_revision=self.source_revision,
            row=self.row,
            supersedes=self.supersedes,
        )
        if (
            self.source_item.revision_id != self.source_revision_id
            or self.source_item.unit_of_measure_id != self.row.unit_of_measure_id
            or not self.evidence_reference.strip()
            or not self.row.version.effective_from
            <= self.effective_date
            <= self.row.version.effective_to
            or not PriceBookActivation.objects.filter(version=self.row.version).exists()
        ):
            raise ValidationError(
                "ردیف، بازنگری، تاریخ و منبع فعال نگاشت باید معتبر باشد."
            )
        if self.supersedes_id:
            if (
                self.supersedes.organization_id != self.organization_id
                or self.supersedes.identity != self.identity
                or self.supersedes.version + 1 != self.version
                or self.supersedes.source_item.estimate_id
                != self.source_item.estimate_id
            ):
                raise ValidationError("زنجیره نسخه نگاشت معتبر نیست.")
        elif self.version != 1:
            raise ValidationError("نسخه نخست نگاشت باید یک باشد.")
