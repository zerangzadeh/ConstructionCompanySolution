from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class ObligationDirection(models.TextChoices):
    RECEIVABLE = "receivable", "دریافتنی"
    PAYABLE = "payable", "پرداختنی"


class WriteOffDecisionKind(models.TextChoices):
    REJECTED = "rejected", "ردشده"
    APPROVED = "approved", "تأییدشده"


class ImmutableSubledgerEvidence:
    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError("شواهد زیر‌دفتر تغییرناپذیر است.")
        self.full_clean(validate_constraints=False)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ValidationError("شواهد زیر‌دفتر قابل حذف نیست.")


class Obligation(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="obligations",
    )
    direction = models.CharField(max_length=16, choices=ObligationDirection.choices)
    source_kind = models.CharField(max_length=80)
    source_uuid = models.UUIDField()
    source_version = models.PositiveIntegerField()
    source_line_key = models.CharField(max_length=120, blank=True)
    source_status = models.CharField(max_length=80)
    source_hash = models.CharField(max_length=64)
    source_snapshot = models.JSONField()
    party = models.ForeignKey(
        "parties.BusinessParty", on_delete=models.PROTECT, null=True, blank=True
    )
    party_name_snapshot = models.CharField(max_length=255)
    party_tax_identifier_snapshot = models.CharField(max_length=100, blank=True)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True
    )
    contract = models.ForeignKey(
        "contracts.Contract", on_delete=models.PROTECT, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="IRR")
    original_amount = models.DecimalField(max_digits=24, decimal_places=6)
    recognized_on = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    recognized_by = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="subledger_obligations_recognized",
    )
    recognition_journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_recognition",
    )

    class Meta:
        ordering = ["recognized_on", "created_at"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "source_kind",
                    "source_uuid",
                    "source_version",
                    "source_line_key",
                    "direction",
                ],
                name="subledger_obligation_unique_source",
            ),
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_obligation_unique_idempotency",
            ),
            models.CheckConstraint(
                condition=Q(original_amount__gt=0),
                name="subledger_obligation_positive_amount",
            ),
            models.CheckConstraint(
                condition=Q(currency="IRR"), name="subledger_obligation_irr_only"
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            party=self.party,
            project=self.project,
            contract=self.contract,
            recognized_by=self.recognized_by,
            recognition_journal=self.recognition_journal,
        )
        if (
            self.contract_id
            and self.project_id
            and self.contract.project_id != self.project_id
        ):
            raise ValidationError("قرارداد و پروژه تعهد باید هم‌راستا باشند.")
        if not self.party_name_snapshot.strip():
            raise ValidationError({"party_name_snapshot": "تصویر نام طرف الزامی است."})
        if self.original_amount <= 0:
            raise ValidationError({"original_amount": "مبلغ تعهد باید مثبت باشد."})

    @property
    def outstanding_amount(self):
        settled = (
            self.settlement_allocations.filter(reversal__isnull=True).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        written_off = (
            self.write_off_proposals.filter(
                decision__decision=WriteOffDecisionKind.APPROVED,
                decision__reversal__isnull=True,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        return self.original_amount - settled - written_off

    @property
    def settlement_status(self) -> str:
        outstanding = self.outstanding_amount
        if outstanding == self.original_amount:
            return "open"
        if outstanding == 0:
            return "settled"
        return "partial"


class SettlementAllocation(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    obligation = models.ForeignKey(
        Obligation, on_delete=models.PROTECT, related_name="settlement_allocations"
    )
    treasury_movement = models.ForeignKey(
        "treasury.TreasuryMovement",
        on_delete=models.PROTECT,
        related_name="subledger_allocations",
    )
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    effective_date = models.DateField()
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    settlement_journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_settlement",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_allocation_unique_idempotency",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="subledger_allocation_positive_amount"
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            obligation=self.obligation,
            treasury_movement=self.treasury_movement,
            created_by=self.created_by,
            settlement_journal=self.settlement_journal,
        )
        if self.amount <= 0:
            raise ValidationError({"amount": "مبلغ تخصیص باید مثبت باشد."})
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل تخصیص الزامی است."})


class SettlementReversal(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    allocation = models.OneToOneField(
        SettlementAllocation, on_delete=models.PROTECT, related_name="reversal"
    )
    effective_date = models.DateField()
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    reversed_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    reversal_journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_settlement_reversal",
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_allocation_reversal_unique_idempotency",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self,
            allocation=self.allocation,
            reversed_by=self.reversed_by,
            reversal_journal=self.reversal_journal,
        )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل برگشت الزامی است."})


class WriteOffProposal(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    obligation = models.ForeignKey(
        Obligation, on_delete=models.PROTECT, related_name="write_off_proposals"
    )
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    effective_date = models.DateField()
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    proposed_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_writeoff_unique_idempotency",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="subledger_writeoff_positive_amount"
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, obligation=self.obligation, proposed_by=self.proposed_by
        )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل پیشنهاد سوخت الزامی است."})


class WriteOffDecision(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    proposal = models.OneToOneField(
        WriteOffProposal, on_delete=models.PROTECT, related_name="decision"
    )
    decision = models.CharField(max_length=16, choices=WriteOffDecisionKind.choices)
    reason = models.TextField()
    decided_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_write_off",
    )

    def clean(self) -> None:
        validate_related_organizations(
            self,
            proposal=self.proposal,
            decided_by=self.decided_by,
            journal=self.journal,
        )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل تصمیم سوخت الزامی است."})
        if self.decision == WriteOffDecisionKind.APPROVED:
            raise ValidationError(
                "اختیار سوخت هنوز تصویب نشده است؛ تصمیم P3-S27-Q03 لازم است."
            )


class WriteOffReversal(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    decision = models.OneToOneField(
        WriteOffDecision, on_delete=models.PROTECT, related_name="reversal"
    )
    effective_date = models.DateField()
    reason = models.TextField()
    reversed_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    journal = models.OneToOneField(
        "accounting.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subledger_write_off_reversal",
    )

    def clean(self) -> None:
        validate_related_organizations(
            self,
            decision=self.decision,
            reversed_by=self.reversed_by,
            journal=self.journal,
        )
        raise ValidationError(
            "اختیار برگشت سوخت هنوز تصویب نشده است؛ تصمیم P3-S27-Q03 لازم است."
        )


class AgingRun(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    direction = models.CharField(max_length=16, choices=ObligationDirection.choices)
    as_of_date = models.DateField()
    obligation_count = models.PositiveIntegerField()
    original_total = models.DecimalField(max_digits=30, decimal_places=6)
    settled_total = models.DecimalField(max_digits=30, decimal_places=6)
    written_off_total = models.DecimalField(max_digits=30, decimal_places=6)
    outstanding_total = models.DecimalField(max_digits=30, decimal_places=6)
    item_snapshots = models.JSONField(blank=True)
    evidence_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_aging_unique_idempotency",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(self, created_by=self.created_by)


class SubledgerReconciliationRun(ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    direction = models.CharField(max_length=16, choices=ObligationDirection.choices)
    as_of_date = models.DateField()
    subledger_outstanding_total = models.DecimalField(max_digits=30, decimal_places=6)
    linked_gl_total = models.DecimalField(max_digits=30, decimal_places=6)
    difference = models.DecimalField(max_digits=30, decimal_places=6)
    exception_snapshots = models.JSONField(blank=True)
    obligation_ids = models.JSONField(blank=True)
    journal_ids = models.JSONField(blank=True)
    evidence_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="subledger_recon_unique_idempotency",
            )
        ]

    def clean(self) -> None:
        validate_related_organizations(self, created_by=self.created_by)


class SubledgerReconciliationReview(
    ImmutableSubledgerEvidence, UUIDModel, CreatedAtModel
):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    run = models.OneToOneField(
        SubledgerReconciliationRun, on_delete=models.PROTECT, related_name="review"
    )
    reason = models.TextField()
    run_evidence_hash = models.CharField(max_length=64)
    signed_evidence_hash = models.CharField(max_length=64)
    reviewed_by = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )

    def clean(self) -> None:
        validate_related_organizations(
            self, run=self.run, reviewed_by=self.reviewed_by
        )
        if not self.reason.strip():
            raise ValidationError({"reason": "دلیل بررسی تطبیق الزامی است."})
        if self.reviewed_by_id == self.run.created_by_id:
            raise ValidationError("اجراکننده تطبیق نمی‌تواند همان اجرا را بررسی کند.")
