"""INT-C02 immutable source-availability occurrences, never billing amounts."""

from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class VariationEligibilityQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("شواهد اهلیت تغییرناپذیر است.")

    def delete(self):
        raise ValidationError("شواهد اهلیت حذف‌پذیر نیست.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("ثبت اهلیت فقط از سرویس مجاز است.")


class VariationBillingEligibility(UUIDModel, CreatedAtModel):
    """Historical eligibility at a source occurrence; current state is source-derived."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT)
    contract = models.ForeignKey("contracts.Contract", on_delete=models.PROTECT)
    source = models.OneToOneField(
        "contracts.ContractualRecord",
        on_delete=models.PROTECT,
        related_name="billing_eligibility",
    )
    series_id = models.UUIDField()
    source_version = models.PositiveIntegerField()
    source_snapshot = models.JSONField()
    source_sha256 = models.CharField(max_length=64)
    active_at_occurrence = models.BooleanField()
    predecessor = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successor",
    )
    idempotency_key = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    objects = VariationEligibilityQuerySet.as_manager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "series_id", "source_version"],
                name="variation_eligibility_occurrence_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="variation_eligibility_key_uq",
            ),
        ]

    def clean(self):
        from .variation_handoffs import eligibility_for_source, source_digest

        validate_related_organizations(
            self,
            source=self.source,
            project=self.project,
            contract=self.contract,
            created_by=self.created_by,
            predecessor=self.predecessor,
        )
        if (
            self.source.kind != "variation"
            or self.source.series_id != self.series_id
            or self.source.version != self.source_version
            or self.source.project_id != self.project_id
            or self.source.contract_id != self.contract_id
            or not self.source.approved_at
            or not self.source.approved_by_id
            or not self.idempotency_key.strip()
            or self.active_at_occurrence != eligibility_for_source(self.source)
            or self.source_sha256 != source_digest(self.source_snapshot)
        ):
            raise ValidationError("هویت یا شواهد رخداد اهلیت معتبر نیست.")
        if self.predecessor_id and (
            self.predecessor.series_id != self.series_id
            or self.predecessor.contract_id != self.contract_id
            or self.predecessor.source_version >= self.source_version
        ):
            raise ValidationError("زنجیره اهلیت معتبر نیست.")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("شواهد اهلیت تغییرناپذیر است.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("شواهد اهلیت حذف‌پذیر نیست.")
