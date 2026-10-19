"""Closed native source readers for INT-B04/B05/B06/B08; never mutate sources.

These readers prove source identity and evidence. Eligibility, classification,
allocation and effective-date policy still require an approved registered binding.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction

from apps.equipment.models import EquipmentCostAllocation, EquipmentCostSourceEnvelope
from apps.fixed_assets.models import FixedAssetSourceEnvelope
from apps.inventory.models import DownstreamCostSourceEnvelope, InventoryValuationEvent
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P

from .services import _stable_payload_hash

SOURCE_MODELS = {
    "pcp-fin-actual": "financial.recognition_occurrence",
    "pcp-inv-actual": "inventory.inventoryvaluationevent",
    "pcp-eqp-actual": "equipment.equipmentcostallocation",
    "pcp-fa-actual": "fixed_assets.fixedassetsourceenvelope",
    "pcp-payr-actual": "payroll.financialhandoffproposal",
}
INTEGRATIONS = {
    "pcp-fin-actual": "INT-B03",
    "pcp-inv-actual": "INT-B04",
    "pcp-eqp-actual": "INT-B05",
    "pcp-fa-actual": "INT-B06",
    "pcp-payr-actual": "INT-B08",
}
REVIEWED = {"reviewed", "acknowledged", "reconciled"}


class ActualRejected(ValueError):
    """Stable diagnostic code; no protected names or confidential values."""


@dataclass(frozen=True)
class NativeActualSource:
    producer_key: str
    source_type: str
    source_id: str
    source_version: str
    evidence: dict[str, Any]
    amount: Decimal
    currency: str
    project_id: str
    active: bool
    operation: str
    predecessor_id: str = ""
    required_reversal_source_id: str = ""


def _row(record) -> dict[str, str]:
    # Mutable lifecycle/audit presentation does not create a new economic version.
    ignored = {
        "status",
        "updated_at",
        "updated_by_id",
        "reversed_by_id",
        "reversed_at",
        "reason",
        "reversal_reason",
        "consumer_reference",
        "reconciliation_note",
    }
    return {
        field.attname: str(getattr(record, field.attname))
        for field in record._meta.concrete_fields
        if field.attname not in ignored
    }


def _same_tenant(organization, *records):
    if any(record.organization_id != organization.pk for record in records):
        raise ActualRejected("source_tenant_mismatch")


def _read_permission(actor, organization, permission, project=None):
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        message="اجازه خواندن منبع هزینه در این دامنه را ندارید.",
    )


def _snapshot(
    key,
    source_id,
    evidence,
    amount,
    currency,
    project_id,
    active,
    operation,
    predecessor="",
):
    return NativeActualSource(
        key,
        SOURCE_MODELS[key],
        str(source_id),
        _stable_payload_hash(evidence),
        evidence,
        amount,
        currency,
        str(project_id or ""),
        active,
        operation,
        str(predecessor or ""),
    )


def _inventory(*, organization, actor, source_id):
    event = InventoryValuationEvent.objects.select_for_update().get(
        organization=organization, pk=source_id
    )
    movement = (
        type(event.stock_transaction)
        .objects.select_for_update()
        .get(organization=organization, pk=event.stock_transaction_id)
    )
    _read_permission(actor, organization, P.INVENTORY_VALUATION_VIEW, movement.project)
    envelope = DownstreamCostSourceEnvelope.objects.select_for_update().get(
        organization=organization, consumer="project_controls", valuation_event=event
    )
    _same_tenant(organization, event, movement, envelope, event.material)
    if event.material_id != movement.material_id or envelope.payload != {
        "valuation_event_id": str(event.pk),
        "amount": str(event.value_amount),
        "currency": event.currency,
        "source_version": event.source_version,
    }:
        raise ActualRejected("inventory_value_proposal_mismatch")
    if not movement.project_id or envelope.project_id != movement.project_id:
        raise ActualRejected("inventory_project_evidence_required")
    if not event.source_reference or not event.source_version:
        raise ActualRejected("inventory_unit_value_source_version_required")
    predecessor = ""
    operation = "recognize"
    if event.reversal_of_id:
        original = InventoryValuationEvent.objects.select_for_update().get(
            organization=organization, pk=event.reversal_of_id
        )
        if (
            event.event_type != "reversal"
            or movement.transaction_type != "reversal"
            or original.event_type != "issue"
            or movement.reversal_of_id != original.stock_transaction_id
            or event.value_amount != original.value_amount
            or event.quantity != original.quantity
            or event.currency != original.currency
            or event.material_id != original.material_id
            or event.unit_cost != original.unit_cost
            or event.monetary_precision_version_id
            != original.monetary_precision_version_id
            or event.rounding_policy_version_id != original.rounding_policy_version_id
        ):
            raise ActualRejected("inventory_inverse_lineage_mismatch")
        predecessor = original.pk
        operation = "reverse"
    elif event.event_type != "issue" or movement.transaction_type != "issue":
        raise ActualRejected("not_project_consumption")
    if movement.status not in {"posted", "reversed"}:
        raise ActualRejected("consumption_not_posted")
    evidence = {
        "valuation": _row(event),
        "movement": _row(movement),
        "proposal": _row(envelope),
        "unit_value_policies": {
            "precision": str(event.monetary_precision_version_id),
            "rounding": str(event.rounding_policy_version_id),
        },
    }
    return _snapshot(
        "pcp-inv-actual",
        event.pk,
        evidence,
        event.value_amount,
        event.currency,
        movement.project_id,
        event.status == "finalized" and movement.status == "posted",
        operation,
        predecessor,
    )


def _equipment(*, organization, actor, source_id):
    allocation = EquipmentCostAllocation.objects.select_for_update().get(
        organization=organization, pk=source_id
    )
    _read_permission(
        actor, organization, P.EQUIPMENT_COST_ALLOCATION_VIEW, allocation.project
    )
    envelope = EquipmentCostSourceEnvelope.objects.select_for_update().get(
        organization=organization, allocation=allocation, consumer="project_cost"
    )
    _same_tenant(organization, allocation, envelope, allocation.usage, allocation.rate)
    if envelope.status not in REVIEWED or not envelope.reviewed_by_id:
        raise ActualRejected("equipment_proposal_not_reviewed")
    if (
        envelope.source_amount != allocation.amount
        or not allocation.finalized_at
        or not allocation.reviewed_by_id
    ):
        raise ActualRejected("equipment_source_amount_or_approval_mismatch")
    rate = allocation.rate
    _same_tenant(organization, rate.policy)
    operation, predecessor = "recognize", ""
    if allocation.correction_of_id:
        original = EquipmentCostAllocation.objects.select_for_update().get(
            organization=organization, pk=allocation.correction_of_id
        )
        if allocation.amount != -original.amount or allocation.amount >= 0:
            raise ActualRejected("unsupported_equipment_correction")
        if allocation.rate_snapshot != -original.rate_snapshot or any(
            getattr(allocation, field) != getattr(original, field)
            for field in (
                "usage_id",
                "rate_id",
                "project_id",
                "site_id",
                "wbs_node_id",
                "activity_id",
                "cost_center_id",
                "measure",
                "currency_code",
            )
        ):
            raise ActualRejected("equipment_inverse_basis_or_dimension_mismatch")
        operation, predecessor = "reverse", original.pk
    elif envelope.supersedes_id:
        previous = EquipmentCostSourceEnvelope.objects.get(
            organization=organization,
            pk=envelope.supersedes_id,
            consumer="project_cost",
        )
        operation, predecessor = "replace", previous.allocation_id
    evidence = {
        "allocation": _row(allocation),
        "proposal": _row(envelope),
        "usage": _row(allocation.usage),
        "rate": _row(rate),
        "rate_policy": _row(rate.policy),
    }
    active = (
        allocation.status == "finalized"
        and not envelope.successors.filter(
            organization=organization, status__in=REVIEWED
        ).exists()
    )
    return _snapshot(
        "pcp-eqp-actual",
        allocation.pk,
        evidence,
        allocation.amount,
        allocation.currency_code,
        allocation.project_id,
        active,
        operation,
        predecessor,
    )


def _assets(*, organization, actor, source_id):
    envelope = FixedAssetSourceEnvelope.objects.select_for_update().get(
        organization=organization, pk=source_id, consumer="project_cost"
    )
    _read_permission(actor, organization, P.FIXED_ASSETS_VIEW)
    if envelope.status not in REVIEWED or not envelope.reviewed_by_id:
        raise ActualRejected("asset_proposal_not_reviewed")
    predecessor = ""
    operation = "recognize"
    if envelope.depreciation_line_id:
        line = envelope.depreciation_line
        run = (
            type(line.run)
            .objects.select_for_update()
            .get(organization=organization, pk=line.run_id)
        )
        _same_tenant(organization, line, run, line.asset, run.book_policy)
        if run.status not in {"finalized", "reversed"} or not run.finalized_by_id:
            raise ActualRejected("depreciation_not_approved")
        if envelope.amount != line.depreciation_amount:
            raise ActualRejected("depreciation_amount_mismatch")
        if run.reversal_of_id:
            previous = type(line).objects.get(
                organization=organization,
                run_id=run.reversal_of_id,
                asset_id=line.asset_id,
            )
            predecessor = FixedAssetSourceEnvelope.objects.get(
                organization=organization,
                consumer="project_cost",
                depreciation_line=previous,
            ).pk
            if (
                line.depreciation_amount != -previous.depreciation_amount
                or run.book_policy_id != previous.run.book_policy_id
            ):
                raise ActualRejected("depreciation_inverse_mismatch")
            operation = "reverse"
        evidence = {
            "proposal": _row(envelope),
            "depreciation_line": _row(line),
            "run": _row(run),
            "book_policy": _row(run.book_policy),
            # No current mutable Asset.project is substituted for attribution policy.
            "native_kind": "depreciation",
            "asset_id": str(line.asset_id),
        }
        active = run.status == "finalized"
        currency = run.book_policy.currency_code
    else:
        # A generic capitalization/disposal/transfer event is not approved asset
        # allocation evidence. No such equivalence is inferred by this adapter.
        raise ActualRejected("approved_asset_allocation_evidence_required")
    if envelope.supersedes_id and not predecessor:
        operation, predecessor = "replace", envelope.supersedes_id
    active = (
        active
        and not envelope.successors.filter(
            organization=organization, status__in=REVIEWED
        ).exists()
    )
    return _snapshot(
        "pcp-fa-actual",
        envelope.pk,
        evidence,
        envelope.amount,
        currency,
        "",
        active,
        operation,
        predecessor,
    )


@transaction.atomic
def read_native_actual(
    *, organization, actor, producer_key: str, source_id
) -> NativeActualSource:
    from .financial_actual_source import read_financial_actual
    from .payroll_actual_source import read_payroll_actual

    reader = {
        "pcp-fin-actual": read_financial_actual,
        "pcp-inv-actual": _inventory,
        "pcp-eqp-actual": _equipment,
        "pcp-fa-actual": _assets,
        "pcp-payr-actual": read_payroll_actual,
    }.get(producer_key)
    if reader is None:
        raise ActualRejected("unregistered_actual_source_family")
    try:
        return reader(organization=organization, actor=actor, source_id=source_id)
    except (ObjectDoesNotExist, ValidationError, TypeError) as exc:
        raise ActualRejected("native_source_evidence_unavailable") from exc


def native_lineage(source: NativeActualSource) -> dict:
    """Retain native version labels alongside the complete snapshot fingerprint.

    Select lineage/value basis only, excluding free text and unrelated source data.
    The fingerprint is the composite immutable version used for duplicate control.
    """
    fields = {
        "financial": (
            "source_family",
            "economic_occurrence",
            "source_identity",
            "source_version",
            "recognition_type",
            "recognition_owner",
            "exclusive_coverage_reference",
            "covered_sources",
        ),
        "valuation": (
            "id",
            "source_reference",
            "source_version",
            "unit_cost",
            "quantity",
            "monetary_precision_version_id",
            "rounding_policy_version_id",
        ),
        "movement": ("id", "unit_of_measure_id", "project_id"),
        "proposal": ("id", "source_version", "occurrence_key", "supersedes_id"),
        "allocation": (
            "id",
            "source_key",
            "correction_of_id",
            "measure",
            "rate_snapshot",
            "site_id",
            "activity_id",
        ),
        "usage": ("id", "source_key", "runtime_hours"),
        "rate": ("id", "policy_id"),
        "rate_policy": ("id", "code", "version", "effective_from"),
        "depreciation_line": (
            "id",
            "asset_id",
            "run_id",
            "basis_snapshot",
            "useful_life_months_snapshot",
        ),
        "run": (
            "id",
            "occurrence_key",
            "source_watermark",
            "reversal_of_id",
            "book_policy_id",
        ),
        "book_policy": (
            "id",
            "code",
            "version",
            "effective_from",
            "method",
            "convention",
        ),
        "payroll": (
            "run_id",
            "calculation_digest",
            "period_id",
            "source_digest",
            "precision_policy_version_id",
            "rounding_policy_version_id",
            "allocation_line_ids",
            "predecessor_id",
            "required_reversal_source_id",
        ),
    }
    return {
        name: {
            key: value for key, value in source.evidence[name].items() if key in keys
        }
        for name, keys in fields.items()
        if isinstance(source.evidence.get(name), dict)
    }
