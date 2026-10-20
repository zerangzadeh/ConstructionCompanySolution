"""Immutable planning supplements and retained comparisons under CEP065-CASHFLOW-v1."""

from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class CashflowEvidence(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    policy_version = models.CharField(max_length=40, default="CEP065-CASHFLOW-v1")
    payload_hash = models.CharField(max_length=64)

    class Meta:
        abstract = True

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ValidationError(
                "Cash-flow evidence is immutable; create a successor."
            )
        validate_related_organizations(self, project=self.project)
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ValidationError("Cash-flow evidence cannot be deleted.")


class ProjectCashflowSupplement(CashflowEvidence):
    forecast = models.OneToOneField(
        "projects.ProjectCostForecast",
        on_delete=models.PROTECT,
        related_name="cashflow_supplement",
    )
    predecessor = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT
    )
    manifest = models.JSONField()

    def clean(self) -> None:
        validate_related_organizations(
            self, forecast=self.forecast, predecessor=self.predecessor
        )
        if self.forecast.project_id != self.project_id:
            raise ValidationError("Cash supplement and forecast must share a project.")
        if self.predecessor and (
            self.predecessor.project_id != self.project_id
            or self.predecessor.forecast.version_number >= self.forecast.version_number
        ):
            raise ValidationError(
                "A predecessor must be an older same-project supplement."
            )


class ProjectCashflowSnapshot(CashflowEvidence):
    baseline = models.ForeignKey(
        ProjectCashflowSupplement,
        on_delete=models.PROTECT,
        related_name="baseline_snapshots",
    )
    forecast = models.ForeignKey(
        ProjectCashflowSupplement,
        on_delete=models.PROTECT,
        related_name="forecast_snapshots",
    )
    knowledge_as_of = models.DateTimeField()
    horizon_start = models.DateField()
    horizon_end = models.DateField()
    timezone_name = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    manifest = models.JSONField()
    result = models.JSONField()

    class Meta:
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=["organization", "project", "idempotency_key"],
                name="cashflow_snapshot_retry_uq",
            ),
            models.CheckConstraint(
                condition=models.Q(horizon_end__gt=models.F("horizon_start")),
                name="cashflow_horizon_order_ck",
            ),
        ]

    def clean(self) -> None:
        validate_related_organizations(
            self, baseline=self.baseline, forecast=self.forecast
        )
        if any(s.project_id != self.project_id for s in (self.baseline, self.forecast)):
            raise ValidationError("Comparison sources must share one project.")
        if self.horizon_start.day != 1 or self.horizon_end.day != 1:
            raise ValidationError("Cash-flow horizons must start on month boundaries.")
