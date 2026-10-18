"""AP-owned immutable INT-B07 enrollment, drafts and correction lineage."""

# ruff: noqa: RUF012

from django.core.exceptions import ValidationError
from django.db import models

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class PayrollAPEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Payroll AP evidence is immutable.")

    def delete(self):
        raise ValidationError("Payroll AP evidence cannot be deleted.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("Use the AP application service.")


class PayrollAPEvidence(UUIDModel, CreatedAtModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    actor = models.ForeignKey(
        "organizations.OrganizationMembership", on_delete=models.PROTECT
    )
    objects = PayrollAPEvidenceQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not getattr(self, "_ap_service", False):
            raise ValidationError("Use the AP application service.")
        if not self._state.adding:
            raise ValidationError("Payroll AP evidence is immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Payroll AP evidence cannot be deleted.")

    def clean(self):
        related = {
            f.name: getattr(self, f.name)
            for f in self._meta.fields
            if f.is_relation and f.name != "organization" and getattr(self, f.attname)
        }
        validate_related_organizations(self, **related)


class PayrollAPEnrollment(PayrollAPEvidence):
    category = models.CharField(max_length=40)
    version = models.PositiveIntegerField()
    # Exact Payroll liability line UUID -> explicit AP terms plus source hash.
    assignments = models.JSONField()
    evidence_reference = models.CharField(max_length=500)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "category", "version"],
                name="payroll_ap_enrollment_version_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="payroll_ap_enrollment_version_ck",
            ),
        ]

    def clean(self):
        super().clean()
        from .payroll_handoffs import validate_assignments

        validate_assignments(self)
        if not self.evidence_reference.strip():
            raise ValidationError("Explicit enrollment policy evidence is required.")


class PayrollAPEnrollmentEvent(PayrollAPEvidence):
    enrollment = models.ForeignKey(
        PayrollAPEnrollment, on_delete=models.PROTECT, related_name="events"
    )
    kind = models.CharField(
        max_length=12, choices=[("activate", "Activate"), ("withdraw", "Withdraw")]
    )
    effective_at = models.DateTimeField()
    reason = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "kind"], name="payroll_ap_enrollment_event_uq"
            )
        ]

    def clean(self):
        super().clean()
        if not self.reason.strip() or self.kind not in {"activate", "withdraw"}:
            raise ValidationError("Explicit AP enrollment event and reason required.")


class PayrollAPDraft(PayrollAPEvidence):
    source_line = models.OneToOneField(
        "payroll.FinancialHandoffLine",
        on_delete=models.PROTECT,
        related_name="ap_draft",
    )
    enrollment = models.ForeignKey(PayrollAPEnrollment, on_delete=models.PROTECT)
    predecessor = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacements",
    )
    source_version = models.CharField(max_length=64)
    payload_hash = models.CharField(max_length=64)
    snapshot = models.JSONField()
    amount = models.DecimalField(max_digits=24, decimal_places=2)
    currency = models.CharField(max_length=3)
    party = models.ForeignKey("parties.BusinessParty", on_delete=models.PROTECT)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True
    )
    recognized_on = models.DateField()
    due_date = models.DateField()
    grouping_reference = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="payroll_ap_draft_positive_ck"
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.source_line.proposal.family != "liability"
            or self.source_line.line_kind != self.enrollment.category
            or self.currency != "IRR"
            or self.amount <= 0
            or not self.grouping_reference.strip()
        ):
            raise ValidationError(
                "Draft must pin an eligible explicit Payroll liability."
            )


class PayrollAPReversal(PayrollAPEvidence):
    draft = models.OneToOneField(
        PayrollAPDraft, on_delete=models.PROTECT, related_name="source_reversal"
    )
    obligation = models.OneToOneField(
        "subledgers.Obligation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payroll_source_reversal",
    )
    source_proposal = models.ForeignKey(
        "payroll.FinancialHandoffProposal", on_delete=models.PROTECT
    )
    effective_date = models.DateField()
    reason = models.TextField()
    payload_hash = models.CharField(max_length=64)

    def clean(self):
        super().clean()
        if (
            not self.reason.strip()
            or self.effective_date < self.draft.recognized_on
            or (
                self.obligation_id
                and (
                    self.obligation.source_kind != "payroll.liability.v1"
                    or self.obligation.source_uuid != self.draft_id
                )
            )
        ):
            raise ValidationError("Payroll AP reversal identity/date is invalid.")


class PayrollAPOperation(PayrollAPEvidence):
    source_proposal = models.OneToOneField(
        "payroll.FinancialHandoffProposal",
        on_delete=models.PROTECT,
        related_name="ap_operation",
    )
    reversal_proposal = models.ForeignKey(
        "payroll.FinancialHandoffProposal",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ap_corrections",
    )
    source_hash = models.CharField(max_length=64)
    payload_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    result = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="payroll_ap_operation_key_uq",
            )
        ]
