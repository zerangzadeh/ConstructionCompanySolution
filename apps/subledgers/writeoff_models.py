"""AP/AR-owned immutable economic correction identity; never a cash authority."""

from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class WriteOffCorrectionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Write-off correction evidence is immutable.")

    def delete(self):
        raise ValidationError("Write-off correction evidence cannot be deleted.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("Use the governed write-off service.")

    def bulk_update(self, *args, **kwargs):
        raise ValidationError("Write-off correction evidence is immutable.")


class WriteOffCorrection(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    original = models.OneToOneField(
        "subledgers.WriteOffDecision",
        on_delete=models.PROTECT,
        related_name="correction_set",
    )
    reversal = models.OneToOneField(
        "subledgers.WriteOffReversal",
        on_delete=models.PROTECT,
        related_name="correction_set",
    )
    replacement = models.OneToOneField(
        "subledgers.WriteOffDecision",
        on_delete=models.PROTECT,
        related_name="replaces_set",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    effective_date = models.DateField()
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    source_snapshot = models.JSONField()
    policy_evidence = models.JSONField()
    accounting_evidence = models.JSONField()
    objects = WriteOffCorrectionQuerySet.as_manager()

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="writeoff_correction_idem_uq",
            ),
        ]

    def clean(self):
        validate_related_organizations(
            self,
            original=self.original,
            reversal=self.reversal,
            replacement=self.replacement if self.replacement_id else None,
            actor=self.actor,
        )
        if (
            self.original.decision != "approved"
            or self.reversal.decision_id != self.original_id
            or self.reversal.effective_date != self.effective_date
            or not self.reason.strip()
        ):
            raise ValidationError(
                "Exact original/reversal correction lineage is required."
            )
        if self.replacement_id and (
            self.replacement.decision != "approved"
            or self.replacement.proposal.corrects_id != self.original_id
            or self.replacement.proposal.obligation_id
            != self.original.proposal.obligation_id
            or self.replacement.proposal.effective_date != self.effective_date
        ):
            raise ValidationError(
                "Replacement must pin the same source and correction date."
            )

    def save(self, *args, **kwargs):
        if not self._state.adding or not getattr(self, "_writeoff_service", False):
            raise ValidationError(
                "Use the governed write-off service; evidence is immutable."
            )
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Write-off correction evidence cannot be deleted.")
