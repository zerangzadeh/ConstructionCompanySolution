"""SPEC018 durable routing evidence; monetary target domains retain authority."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import CreatedAtModel, UUIDModel
from core.tenant_validation import validate_related_organizations

# ruff: noqa: RUF012


class MissionEvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Mission effect history is immutable.")

    def delete(self):
        raise ValidationError("Mission effect history cannot be deleted.")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("Mission evidence requires validated service creation.")


class MissionEvidence(UUIDModel, CreatedAtModel):
    objects = models.Manager.from_queryset(MissionEvidenceQuerySet)()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                "Mission history is immutable; retain a correction event."
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Mission effect history cannot be deleted.")


class MissionEffect(MissionEvidence):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    mission = models.ForeignKey(
        "timekeeping.LeaveMissionRequest",
        on_delete=models.PROTECT,
        related_name="financial_effects",
    )
    mission_version = models.CharField(max_length=100)
    effect_id = models.UUIDField()
    effect_type = models.CharField(max_length=64)
    route = models.CharField(
        max_length=16,
        choices=(
            ("payroll", "Payroll component"),
            ("expense", "Direct reimbursement"),
            ("treasury", "Treasury advance settlement"),
        ),
    )
    identity_hash = models.CharField(max_length=64, unique=True)
    payload_hash = models.CharField(max_length=64)
    source_snapshot = models.JSONField()
    policy_reference = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=24, decimal_places=8)
    currency = models.CharField(max_length=3)
    payroll_target = models.OneToOneField(
        "payroll.PayrollAdjustment",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="mission_effect",
    )
    expense_target = models.OneToOneField(
        "expenses.Expense",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="mission_effect",
    )
    treasury_target = models.OneToOneField(
        "treasury.PaymentRequest",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="mission_effect",
    )
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "mission",
                    "mission_version",
                    "effect_id",
                    "effect_type",
                ],
                name="mission_effect_identity_uq",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="mission_effect_positive_ck"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        route="payroll",
                        payroll_target__isnull=False,
                        expense_target__isnull=True,
                        treasury_target__isnull=True,
                    )
                    | Q(
                        route="expense",
                        payroll_target__isnull=True,
                        expense_target__isnull=False,
                        treasury_target__isnull=True,
                    )
                    | Q(
                        route="treasury",
                        payroll_target__isnull=True,
                        expense_target__isnull=True,
                        treasury_target__isnull=False,
                    )
                ),
                name="mission_effect_one_route_ck",
            ),
        ]

    def clean(self):
        from .mission_routing import digest, effect_identity

        validate_related_organizations(
            self,
            mission=self.mission,
            payroll_target=self.payroll_target,
            expense_target=self.expense_target,
            treasury_target=self.treasury_target,
        )
        if self.mission.kind != "mission" or self.mission.state != "approved":
            raise ValidationError("Only an approved native Mission can own an effect.")
        if (
            not self.mission_version.strip()
            or not self.effect_type.strip()
            or not self.policy_reference.strip()
            or digest(self.source_snapshot) != self.payload_hash
            or effect_identity(
                self.organization_id,
                self.mission_id,
                self.mission_version,
                self.effect_id,
                self.effect_type,
            )
            != self.identity_hash
        ):
            raise ValidationError(
                "Exact Mission identity and immutable approved source evidence required."
            )
        links = (
            bool(self.payroll_target_id),
            bool(self.expense_target_id),
            bool(self.treasury_target_id),
        )
        if links != {
            "payroll": (True, False, False),
            "expense": (False, True, False),
            "treasury": (False, False, True),
        }.get(self.route):
            raise ValidationError(
                "Exactly one native target must match the approved route."
            )
        target = self.payroll_target or self.expense_target or self.treasury_target
        if target is None:
            raise ValidationError("One typed native target is required.")
        employee_id = (
            target.employee_id
            if self.route != "expense"
            else target.reimbursement_employee_id
        )
        if employee_id != self.mission.employee_id or target.amount != self.amount:
            raise ValidationError(
                "Target employee/amount must match the approved effect."
            )
        if self.route == "payroll":
            if (
                target.run.currency != self.currency
                or target.source_payload.get("mission_effect_identity")
                != self.identity_hash
            ):
                raise ValidationError(
                    "Payroll target source identity/currency mismatch."
                )
        elif target.project_id != self.mission.project_id or (
            self.route == "treasury"
            and (
                target.site_id != self.mission.site_id
                or target.kind != "employee_advance"
            )
        ):
            raise ValidationError(
                "Mission target project/site or native advance classification mismatch."
            )


class MissionEffectEvent(MissionEvidence):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    mission = models.ForeignKey(
        "timekeeping.LeaveMissionRequest",
        on_delete=models.PROTECT,
        related_name="financial_effect_events",
    )
    effect = models.ForeignKey(
        MissionEffect,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="events",
    )
    identity_hash = models.CharField(max_length=64)
    kind = models.CharField(
        max_length=16,
        choices=(
            ("created", "Created"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
            ("replaced", "Replaced"),
        ),
    )
    replacement = models.OneToOneField(
        MissionEffect,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="predecessor_event",
    )
    payroll_inverse = models.OneToOneField(
        "payroll.PayrollAdjustment",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="mission_inverse_event",
    )
    treasury_reversal = models.OneToOneField(
        "treasury.TreasuryMovement",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="mission_reversal_event",
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    error_code = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["effect"],
                condition=Q(kind__in=("cancelled", "replaced")),
                name="mission_effect_terminal_uq",
            ),
            models.UniqueConstraint(
                fields=["effect"],
                condition=Q(kind="created"),
                name="mission_effect_created_uq",
            ),
            models.CheckConstraint(
                condition=Q(kind="failed") | Q(effect__isnull=False),
                name="mission_event_effect_ck",
            ),
            models.CheckConstraint(
                condition=Q(kind="replaced", replacement__isnull=False)
                | (~Q(kind="replaced") & Q(replacement__isnull=True)),
                name="mission_event_replacement_ck",
            ),
        ]

    def clean(self):
        validate_related_organizations(
            self,
            mission=self.mission,
            effect=self.effect,
            replacement=self.replacement,
            payroll_inverse=self.payroll_inverse,
            treasury_reversal=self.treasury_reversal,
        )
        if not self.reason.strip():
            raise ValidationError("Mission event reason required.")
        if self.effect_id and (
            self.effect.mission_id != self.mission_id
            or self.effect.identity_hash != self.identity_hash
        ):
            raise ValidationError("Mission event source mismatch.")
        if self.replacement_id and (
            self.replacement.mission_id != self.mission_id
            or self.replacement.effect_id != self.effect.effect_id
            or self.replacement.effect_type != self.effect.effect_type
            or self.replacement.mission_version == self.effect.mission_version
        ):
            raise ValidationError(
                "Replacement must retain effect identity in a distinct approved Mission version."
            )
        if self.kind in {"cancelled", "replaced"}:
            target = self.effect
            if target.route == "payroll":
                inverse = self.payroll_inverse
                if (
                    inverse is None
                    or inverse.employee_id != target.payroll_target.employee_id
                    or inverse.component_id != target.payroll_target.component_id
                    or inverse.amount != -target.amount
                    or inverse.source_payload.get("reverses_mission_effect")
                    != target.identity_hash
                ):
                    raise ValidationError(
                        "Exact native Payroll inverse evidence required."
                    )
            if target.route == "expense" and target.expense_target.status != "void":
                raise ValidationError("Native Expense void evidence required.")
            if (
                target.route == "treasury"
                and target.treasury_target.status not in {"cancelled", "rejected"}
                and (
                    self.treasury_reversal is None
                    or not target.treasury_target.released_movement_id
                    or self.treasury_reversal.reverses_id
                    != target.treasury_target.released_movement_id
                    or self.treasury_reversal.status != "posted"
                )
            ):
                raise ValidationError("Native Treasury reversal evidence required.")
