"""CEP-023 authoritative leave records; no statutory or profile defaults."""

# Django model Meta declarations are class-level collections.
# ruff: noqa: RUF012

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class LeaveHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Leave history requires an appended correction.")

    def delete(self):
        raise ValidationError("Leave history cannot be deleted.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("Leave history requires validated individual records.")


class LeaveHistory(UUIDModel, CreatedAtModel):
    objects = models.Manager.from_queryset(LeaveHistoryQuerySet)()
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField(max_length=2000)
    evidence_reference = models.CharField(max_length=255)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Leave history is immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Leave history cannot be deleted.")


class LeavePolicyVersion(LeaveHistory):
    category_code = models.CharField(max_length=50)
    version = models.PositiveIntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField()
    unit = models.CharField(
        max_length=20, choices=[("minutes", "Minutes"), ("days", "Days")]
    )
    accrual_preset = models.CharField(
        max_length=20,
        choices=[(v, v) for v in ("FULL_CREDIT", "ZERO_ACCRUAL", "POLICY_DEFINED")],
    )
    # A reference is evidence, never executable tenant code or an inferred rate.
    entitlement_rule_reference = models.CharField(max_length=255)
    accrual_rule_reference = models.CharField(max_length=255, blank=True)
    negative_balance_threshold = models.DecimalField(max_digits=14, decimal_places=4)
    carry_forward_limit = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True
    )
    expiry_rule_reference = models.CharField(max_length=255, blank=True)
    supersedes = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacement",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "category_code", "version"],
                name="leave_policy_version_uq",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__gt=models.F("effective_from")),
                name="leave_policy_dates_ck",
            ),
            models.CheckConstraint(
                condition=Q(negative_balance_threshold__lte=0),
                name="leave_policy_floor_ck",
            ),
            models.CheckConstraint(
                condition=Q(carry_forward_limit__isnull=True)
                | Q(carry_forward_limit__gte=0),
                name="leave_policy_carry_ck",
            ),
        ]

    def clean(self):
        validate_related_organizations(
            self, supersedes=self.supersedes if self.supersedes_id else None
        )
        if (
            self.accrual_preset == "POLICY_DEFINED"
            and not self.accrual_rule_reference.strip()
        ):
            raise ValidationError("An explicit approved accrual rule is required.")
        if self.supersedes_id and (
            self.supersedes.category_code != self.category_code
            or self.version != self.supersedes.version + 1
            or self.unit != self.supersedes.unit
        ):
            raise ValidationError(
                "A replacement must retain its policy identity and unit."
            )


class LeaveEntryKind(models.TextChoices):
    OPENING = "opening", "Controlled opening evidence (CEP-057 producer)"
    ENTITLEMENT = "entitlement", "Entitlement"
    ACCRUAL = "accrual", "Accrual"
    CARRY_FORWARD = "carry_forward", "Carry forward"
    EXPIRY = "expiry", "Expiry"
    ADJUSTMENT = "adjustment", "Adjustment"
    REVERSAL = "reversal", "Reversal"
    RESERVATION = "reservation", "Reservation"
    RELEASE = "release", "Reservation release"
    CONSUMPTION = "consumption", "Approved occurrence consumption"
    REINSTATEMENT = "reinstatement", "Cancellation reinstatement"


class LeaveBalanceEntry(LeaveHistory):
    relationship = models.ForeignKey(
        "workforce.WorkRelationship",
        on_delete=models.PROTECT,
        related_name="leave_entries",
    )
    policy = models.ForeignKey(LeavePolicyVersion, on_delete=models.PROTECT)
    effective_on = models.DateField()
    kind = models.CharField(max_length=24, choices=LeaveEntryKind.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    reserved_quantity = models.DecimalField(max_digits=14, decimal_places=4)
    source_key = models.CharField(max_length=200)
    request_snapshot = models.JSONField(default=dict, blank=True)
    request = models.ForeignKey(
        "timekeeping.LeaveMissionRequest",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="balance_entries",
    )
    reverses = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversal"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_key"], name="leave_entry_source_uq"
            ),
            models.CheckConstraint(
                condition=~(Q(quantity=0) & Q(reserved_quantity=0)),
                name="leave_entry_nonzero_ck",
            ),
            models.UniqueConstraint(
                fields=["request", "kind"],
                condition=Q(request__isnull=False),
                name="leave_request_kind_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "relationship", "effective_on"],
                name="leave_balance_asof_idx",
            )
        ]

    def clean(self):
        validate_related_organizations(
            self,
            relationship=self.relationship if self.relationship_id else None,
            policy=self.policy if self.policy_id else None,
            request=self.request if self.request_id else None,
            reverses=self.reverses if self.reverses_id else None,
        )
        if (
            self.request_id
            and self.relationship.legacy_employee_id != self.request.employee_id
        ):
            raise ValidationError(
                "The request requires an explicit legacy identity link."
            )
        if self.reverses_id and (
            self.reverses.relationship_id != self.relationship_id
            or self.reverses.policy_id != self.policy_id
            or self.quantity != -self.reverses.quantity
            or self.reserved_quantity != -self.reverses.reserved_quantity
        ):
            raise ValidationError(
                "Reversal must exactly retain and reverse its source."
            )
        request_kinds = {
            LeaveEntryKind.RESERVATION,
            LeaveEntryKind.RELEASE,
            LeaveEntryKind.CONSUMPTION,
            LeaveEntryKind.REINSTATEMENT,
        }
        if (self.kind in request_kinds) != bool(self.request_id):
            raise ValidationError(
                "Request movements require an explicit native source."
            )
        if self.kind == LeaveEntryKind.RESERVATION and (
            self.quantity != 0 or self.reserved_quantity <= 0 or self.reverses_id
        ):
            raise ValidationError("A reservation only increases reserved quantity.")
        if self.kind == LeaveEntryKind.RELEASE and (
            self.quantity != 0
            or self.reserved_quantity >= 0
            or not self.reverses_id
            or self.reverses.kind != LeaveEntryKind.RESERVATION
        ):
            raise ValidationError("A release must reverse its exact reservation.")
        if self.kind == LeaveEntryKind.CONSUMPTION and (
            self.quantity >= 0
            or self.reserved_quantity != 0
            or self.reverses_id
            or self.request.state != "approved"
        ):
            raise ValidationError("Consumption requires an approved native occurrence.")
        if self.kind == LeaveEntryKind.REINSTATEMENT and (
            self.quantity <= 0
            or self.reserved_quantity != 0
            or not self.reverses_id
            or self.reverses.kind != LeaveEntryKind.CONSUMPTION
        ):
            raise ValidationError("Reinstatement must reverse its exact consumption.")
        if self.kind not in request_kinds and self.reserved_quantity != 0:
            raise ValidationError("Non-request sources cannot change reservations.")
