"""CEP-042 immutable mapping inputs and Accounting-owned draft lineage."""

from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class RecognitionEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("شواهد شناسایی تغییرناپذیر است.")

    def delete(self):
        raise ValidationError("شواهد شناسایی حذف‌پذیر نیست.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("ثبت شناسایی فقط از سرویس مجاز است.")


class RecognitionEvidence(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    objects = RecognitionEvidenceQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("شواهد شناسایی تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("شواهد شناسایی حذف‌پذیر نیست.")


class RecognitionMappingVersion(RecognitionEvidence):
    """Explicit tenant account assignments; no default accounts or expressions."""

    source_family = models.CharField(max_length=40)
    source_event = models.CharField(max_length=40)
    version = models.PositiveIntegerField()
    effective_from = models.DateField()
    # Exact source measure key -> explicit debit/credit ledger UUIDs. Immutable.
    account_assignments = models.JSONField()
    evidence_reference = models.CharField(max_length=500)
    prepared_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "source_family", "source_event", "version"],
                name="recognition_mapping_version_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="recognition_mapping_positive_v",
            ),
        ]

    def clean(self):
        from .recognition_sources import validate_mapping_assignments

        validate_related_organizations(self, prepared_by=self.prepared_by)
        if not self.evidence_reference.strip():
            raise ValidationError("مرجع پذیرش نگاشت الزامی است.")
        validate_mapping_assignments(self)


class RecognitionMappingApproval(RecognitionEvidence):
    mapping = models.OneToOneField(
        RecognitionMappingVersion, on_delete=models.PROTECT, related_name="approval"
    )
    approved_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    reason = models.TextField()

    def clean(self):
        validate_related_organizations(
            self, mapping=self.mapping, approved_by=self.approved_by
        )
        if (
            self.mapping.prepared_by_id == self.approved_by_id
            or not self.reason.strip()
        ):
            raise ValidationError("پذیرش مستقل نگاشت با دلیل الزامی است.")


class SourceRecognitionDraft(RecognitionEvidence):
    """One immutable, mapped source occurrence; never a posting authority."""

    source_kind = models.CharField(max_length=30)
    source_uuid = models.UUIDField()
    source_event = models.CharField(max_length=40)
    source_version_reference = models.CharField(max_length=255)
    source_snapshot = models.JSONField()
    source_sha256 = models.CharField(max_length=64)
    mapping = models.ForeignKey(RecognitionMappingVersion, on_delete=models.PROTECT)
    journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        related_name="recognition_source",
    )
    predecessor = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successors",
    )
    is_reversal = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    # Expected mapped target rows, including retained source dimensions.
    target_snapshot = models.JSONField()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "source_kind", "source_uuid", "source_event"],
                name="recognition_source_occurrence_uq",
            ),
            models.UniqueConstraint(
                fields=["predecessor"],
                condition=models.Q(is_reversal=True),
                name="recognition_one_reversal_uq",
            ),
        ]

    def clean(self):
        from .recognition_sources import digest

        validate_related_organizations(
            self,
            mapping=self.mapping,
            journal=self.journal,
            predecessor=self.predecessor,
            created_by=self.created_by,
        )
        if self.source_sha256 != digest(self.source_snapshot):
            raise ValidationError("هش منبع شناسایی معتبر نیست.")
        if self.is_reversal and not self.predecessor_id:
            raise ValidationError("برگشت باید رخداد پیشین داشته باشد.")
        if (
            self.journal.status != "draft"
            or self.journal.source_uuid != self.source_uuid
        ):
            raise ValidationError("خروجی شناسایی باید پیش‌نویس همان منبع باشد.")
