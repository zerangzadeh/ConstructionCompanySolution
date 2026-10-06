from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Max, Q, QuerySet, Sum
from django.utils import timezone

from apps.accounting.policy_calculations import (
    preserve_intermediate_calculation,
    resolve_monetary_policies,
    round_final_monetary_amount,
)
from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.inventory.models import (
    DownstreamCostConsumer,
    DownstreamCostSourceEnvelope,
    InventoryCount,
    InventoryCountLine,
    InventoryCountStatus,
    InventoryLot,
    InventoryReservation,
    InventoryReservationAllocation,
    InventorySerial,
    InventoryTransfer,
    InventoryTransferLine,
    InventoryTransferStatus,
    InventoryValuationEvent,
    InventoryValuationEventType,
    InventoryValuationException,
    InventoryValuationPool,
    InventoryValuationStatus,
    MaterialTraceabilityProfile,
    ReservationAllocationStatus,
    ReservationStatus,
    StockTraceAllocation,
    StockTransaction,
    StockTransactionStatus,
    StockTransactionType,
    TraceabilityMode,
    TraceAllocationDirection,
    TraceQualityStatus,
    TransferExceptionCode,
    Warehouse,
    WarehouseBin,
)
from apps.inventory.services import (
    _get_warehouse,
    _stock_balance_value,
    _validate_material,
    create_stock_transaction,
    post_stock_transaction,
)
from apps.materials.models import Material
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.models import Activity, Project, ProjectSite, WBSNode

INVENTORY_VALUATION_CONSUMER = "inventory.valuation.finalize"


@transaction.atomic
def record_missing_cost_exception(
    *,
    organization: Organization,
    actor: User,
    stock_transaction: StockTransaction,
    reason: str,
    source_reference: str = "",
    source_version: str = "",
) -> InventoryValuationException:
    """Persist a fail-closed source-cost gap without changing quantity or value."""
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_VALUATION_PREPARE,
        project=stock_transaction.project,
    )
    stock = StockTransaction.objects.select_for_update().get(
        pk=stock_transaction.pk,
        organization=organization,
        status=StockTransactionStatus.POSTED,
    )
    if InventoryValuationEvent.objects.filter(stock_transaction=stock).exists():
        raise ValueError("حرکت نهایی ارزش‌گذاری شده و نمی‌تواند استثنای هزینه بگیرد.")
    exception, _ = InventoryValuationException.objects.get_or_create(
        organization=organization,
        stock_transaction=stock,
        defaults={
            "material": stock.material,
            "reason": reason.strip() or "missing_cost",
            "required_authority": "procurement.versioned_commercial_source",
            "source_reference": source_reference.strip(),
            "source_version": source_version.strip(),
        },
    )
    return exception


def _valuation_type(stock: StockTransaction) -> InventoryValuationEventType:
    return {
        StockTransactionType.RECEIPT: InventoryValuationEventType.RECEIPT,
        StockTransactionType.ISSUE: InventoryValuationEventType.ISSUE,
        StockTransactionType.TRANSFER: InventoryValuationEventType.TRANSFER,
        StockTransactionType.ADJUSTMENT_IN: InventoryValuationEventType.COUNT_ADJUSTMENT,
        StockTransactionType.ADJUSTMENT_OUT: InventoryValuationEventType.COUNT_ADJUSTMENT,
        StockTransactionType.REVERSAL: InventoryValuationEventType.REVERSAL,
    }.get(stock.transaction_type, InventoryValuationEventType.COUNT_ADJUSTMENT)


@transaction.atomic
def finalize_valuation(
    *,
    organization: Organization,
    actor: User,
    stock_transaction: StockTransaction,
    source_reference: str,
    source_version: str,
    unit_cost: Decimal,
    idempotency_key: str,
    transfer_value_only: bool = False,
) -> InventoryValuationEvent:
    """Finalise one value record only when authoritative quantity/source/policy exist."""
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_VALUATION_PREPARE,
        project=stock_transaction.project,
    )
    stock = StockTransaction.objects.select_for_update().get(
        pk=stock_transaction.pk, organization=organization
    )
    if stock.status != StockTransactionStatus.POSTED:
        raise ValueError("فقط حرکت ثبت‌شده قابل ارزش‌گذاری است.")
    if (
        not transfer_value_only
        and InventoryTransferLine.objects.filter(
            Q(dispatch_transaction=stock) | Q(receipt_transaction=stock)
        ).exists()
    ):
        raise ValueError("ترانزیت داخلی باید فقط از جفت انتقال ارزش‌گذاری شود.")
    existing = InventoryValuationEvent.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.stock_transaction_id != stock.pk:
            raise ValueError("کلید تکرارپذیری به حرکت دیگری تعلق دارد.")
        return existing
    if not source_reference.strip() or not source_version.strip() or unit_cost < 0:
        raise ValueError("منبع هزینه نسخه‌دار و مبلغ غیرمنفی الزامی است.")
    precision, rounding = resolve_monetary_policies(
        organization=organization, consumer=INVENTORY_VALUATION_CONSUMER
    )
    pool, _ = InventoryValuationPool.objects.select_for_update().get_or_create(
        organization=organization,
        material=stock.material,
        defaults={
            "currency": organization.settings.currency,
            "monetary_precision_version": precision.version,
            "rounding_policy_version": rounding.version,
        },
    )
    if pool.currency != organization.settings.currency:
        raise ValueError("ارز استخر ارزش‌گذاری با ارز عملیاتی سازمان سازگار نیست.")
    inbound = stock.transaction_type in {
        StockTransactionType.RECEIPT,
        StockTransactionType.ADJUSTMENT_IN,
    }
    outbound = stock.transaction_type in {
        StockTransactionType.ISSUE,
        StockTransactionType.ADJUSTMENT_OUT,
    }
    q_before, v_before = pool.quantity, pool.value_amount
    event_unit_cost = unit_cost
    if transfer_value_only:
        event_unit_cost = pool.average_cost
        amount = round_final_monetary_amount(
            preserve_intermediate_calculation(
                stock.quantity * pool.average_cost, precision=precision
            ),
            precision=precision,
            rounding=rounding,
        )
        q_after, v_after = q_before, v_before
    elif inbound:
        amount = round_final_monetary_amount(
            preserve_intermediate_calculation(
                stock.quantity * unit_cost, precision=precision
            ),
            precision=precision,
            rounding=rounding,
        )
        q_after, v_after = q_before + stock.quantity, v_before + amount
    elif outbound:
        if q_before < stock.quantity:
            raise ValueError("موجودی منفی برای ارزش‌گذاری مجاز نیست.")
        amount = round_final_monetary_amount(
            preserve_intermediate_calculation(
                stock.quantity * pool.average_cost, precision=precision
            ),
            precision=precision,
            rounding=rounding,
        )
        q_after, v_after = q_before - stock.quantity, v_before - amount
    else:  # Internal custody transfer carries WAC value without changing the pool.
        event_unit_cost = pool.average_cost
        amount = round_final_monetary_amount(
            preserve_intermediate_calculation(
                stock.quantity * pool.average_cost, precision=precision
            ),
            precision=precision,
            rounding=rounding,
        )
        q_after, v_after = q_before, v_before
    if q_after < 0 or v_after < 0:
        raise ValueError("حالت منفی موجودی یا ارزش مجاز نیست.")
    average = (
        Decimal(0)
        if q_after == 0
        else preserve_intermediate_calculation(v_after / q_after, precision=precision)
    )
    pool.quantity, pool.value_amount, pool.average_cost = q_after, v_after, average
    pool.monetary_precision_version, pool.rounding_policy_version = (
        precision.version,
        rounding.version,
    )
    pool.save(
        update_fields=[
            "quantity",
            "value_amount",
            "average_cost",
            "monetary_precision_version",
            "rounding_policy_version",
            "updated_at",
        ]
    )
    return InventoryValuationEvent.objects.create(
        organization=organization,
        stock_transaction=stock,
        material=stock.material,
        event_type=(
            InventoryValuationEventType.TRANSFER
            if transfer_value_only
            else _valuation_type(stock)
        ),
        quantity=stock.quantity,
        unit_cost=event_unit_cost,
        value_amount=amount,
        currency=organization.settings.currency,
        source_reference=source_reference.strip(),
        source_version=source_version.strip(),
        idempotency_key=idempotency_key,
        monetary_precision_version=precision.version,
        rounding_policy_version=rounding.version,
        finalized_by=actor,
        finalized_at=timezone.now(),
        quantity_before=q_before,
        value_before=v_before,
        quantity_after=q_after,
        value_after=v_after,
        average_cost_after=average,
    )


@transaction.atomic
def supply_cost_envelope(
    *,
    organization: Organization,
    actor: User,
    valuation_event: InventoryValuationEvent,
    consumer: str,
    idempotency_key: str,
) -> DownstreamCostSourceEnvelope:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_VALUATION_SUPPLY,
    )
    event = InventoryValuationEvent.objects.select_for_update().get(
        pk=valuation_event.pk,
        organization=organization,
        status=InventoryValuationStatus.FINALIZED,
    )
    try:
        target = DownstreamCostConsumer(consumer)
    except ValueError as exc:
        raise ValueError("مصرف‌کننده پیشنهاد هزینه معتبر نیست.") from exc
    source_envelope = DownstreamCostSourceEnvelope.objects.filter(
        organization=organization, consumer=target, valuation_event=event
    ).first()
    if source_envelope and source_envelope.idempotency_key != idempotency_key:
        raise ValueError(
            "یک منبع ارزش‌گذاری نمی‌تواند برای یک مصرف‌کننده دوباره پیشنهاد شود."
        )
    envelope, _ = DownstreamCostSourceEnvelope.objects.get_or_create(
        organization=organization,
        consumer=target,
        idempotency_key=idempotency_key,
        defaults={
            "valuation_event": event,
            "project": event.stock_transaction.project,
            "supplied_by": actor,
            "supplied_at": timezone.now(),
            "payload": {
                "valuation_event_id": str(event.pk),
                "amount": str(event.value_amount),
                "currency": event.currency,
                "source_version": event.source_version,
            },
        },
    )
    if envelope.valuation_event_id != event.pk:
        raise ValueError("کلید تکرارپذیری به پیشنهاد دیگری تعلق دارد.")
    return envelope


@transaction.atomic
def reverse_valuation(
    *,
    organization: Organization,
    actor: User,
    stock_transaction: StockTransaction,
    idempotency_key: str,
) -> InventoryValuationEvent:
    """Reverse only an authoritative equal-and-opposite custody reversal."""
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_VALUATION_REVERSE,
        project=stock_transaction.project,
    )
    reversal = (
        StockTransaction.objects.select_for_update(of=("self",))
        .select_related("reversal_of")
        .get(
            pk=stock_transaction.pk,
            organization=organization,
            transaction_type=StockTransactionType.REVERSAL,
            status=StockTransactionStatus.POSTED,
        )
    )
    original = reversal.reversal_of
    predecessor = InventoryValuationEvent.objects.select_for_update().get(
        stock_transaction=original,
        organization=organization,
        status=InventoryValuationStatus.FINALIZED,
    )
    if InventoryValuationEvent.objects.filter(stock_transaction=reversal).exists():
        return InventoryValuationEvent.objects.get(stock_transaction=reversal)
    pool = InventoryValuationPool.objects.select_for_update().get(
        organization=organization, material=original.material
    )
    q_before, v_before = pool.quantity, pool.value_amount
    original = predecessor.stock_transaction
    if original.destination_warehouse_id and not original.source_warehouse_id:
        if (
            pool.quantity < predecessor.quantity
            or pool.value_amount < predecessor.value_amount
        ):
            raise ValueError("بازگردانی ارزش‌گذاری به حالت منفی منتهی می‌شود.")
        pool.quantity -= predecessor.quantity
        pool.value_amount -= predecessor.value_amount
    elif original.source_warehouse_id and not original.destination_warehouse_id:
        pool.quantity += predecessor.quantity
        pool.value_amount += predecessor.value_amount
    # Reversing an internal transfer changes custody only; the global pool is stable.
    pool.average_cost = (
        Decimal(0) if pool.quantity == 0 else pool.value_amount / pool.quantity
    )
    pool.save(update_fields=["quantity", "value_amount", "average_cost", "updated_at"])
    return InventoryValuationEvent.objects.create(
        organization=organization,
        stock_transaction=reversal,
        material=original.material,
        event_type=InventoryValuationEventType.REVERSAL,
        quantity=predecessor.quantity,
        unit_cost=predecessor.unit_cost,
        value_amount=predecessor.value_amount,
        currency=predecessor.currency,
        source_reference=predecessor.source_reference,
        source_version=predecessor.source_version,
        idempotency_key=idempotency_key,
        reversal_of=predecessor,
        monetary_precision_version=predecessor.monetary_precision_version,
        rounding_policy_version=predecessor.rounding_policy_version,
        finalized_by=actor,
        finalized_at=timezone.now(),
        quantity_before=q_before,
        value_before=v_before,
        quantity_after=pool.quantity,
        value_after=pool.value_amount,
        average_cost_after=pool.average_cost,
    )


@transaction.atomic
def finalize_transfer_valuation(
    *,
    organization: Organization,
    actor: User,
    line: InventoryTransferLine,
    idempotency_key: str,
) -> tuple[InventoryValuationEvent, InventoryValuationEvent]:
    """Value only the durable dispatch/receipt pair; receipt reuses dispatch basis."""
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_VALUATION_PREPARE,
    )
    locked = (
        InventoryTransferLine.objects.select_for_update(of=("self",))
        .select_related("dispatch_transaction", "receipt_transaction", "material")
        .get(pk=line.pk, organization=organization)
    )
    if (
        not locked.dispatch_transaction_id
        or not locked.receipt_transaction_id
        or locked.accepted_quantity != locked.quantity
    ):
        raise ValueError("جفت انتقال کامل و پذیرفته‌شده برای ارزش‌گذاری لازم است.")
    dispatch = finalize_valuation(
        organization=organization,
        actor=actor,
        stock_transaction=locked.dispatch_transaction,
        source_reference=f"transfer:{locked.pk}",
        source_version="custody-line-v1",
        unit_cost=Decimal(0),
        idempotency_key=f"{idempotency_key}:dispatch",
        transfer_value_only=True,
    )
    existing = InventoryValuationEvent.objects.filter(
        stock_transaction=locked.receipt_transaction
    ).first()
    if existing:
        return dispatch, existing
    pool = InventoryValuationPool.objects.select_for_update().get(
        organization=organization, material=locked.material
    )
    q_before, v_before = pool.quantity, pool.value_amount
    receipt = InventoryValuationEvent.objects.create(
        organization=organization,
        stock_transaction=locked.receipt_transaction,
        material=locked.material,
        event_type=InventoryValuationEventType.TRANSFER,
        quantity=dispatch.quantity,
        unit_cost=dispatch.unit_cost,
        value_amount=dispatch.value_amount,
        currency=dispatch.currency,
        source_reference=f"transfer:{locked.pk}:dispatch:{dispatch.pk}",
        source_version=dispatch.source_version,
        idempotency_key=f"{idempotency_key}:receipt",
        monetary_precision_version=dispatch.monetary_precision_version,
        rounding_policy_version=dispatch.rounding_policy_version,
        finalized_by=actor,
        finalized_at=timezone.now(),
        quantity_before=q_before,
        value_before=v_before,
        quantity_after=q_before,
        value_after=v_before,
        average_cost_after=pool.average_cost,
    )
    return dispatch, receipt


def valuation_reconciliation(
    *, organization: Organization, actor: User
) -> dict[str, object]:
    """Read-only evidence; no balance or lifecycle mutation."""
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_VALUATION_RECONCILE,
    )
    posted = StockTransaction.objects.filter(
        organization=organization, status=StockTransactionStatus.POSTED
    )
    events = InventoryValuationEvent.objects.filter(
        organization=organization
    ).select_related("stock_transaction", "reversal_of")
    valued_ids = events.values("stock_transaction_id")
    findings: dict[str, list[str]] = {
        "movements_without_valuation": [
            str(pk)
            for pk in posted.exclude(pk__in=valued_ids).values_list("pk", flat=True)
        ],
        "invalid_valuations": [],
        "pool_mismatches": [],
        "invalid_reversals": [],
        "transfer_mismatches": [],
        "proposal_mismatches": [],
        "unsupported_return_lineage": [],
        "unsupported_replacement_lineage": [],
        "accounting_proposal_anomalies": [],
        "project_cost_proposal_anomalies": [],
    }
    for event in events:
        if (
            event.stock_transaction.status != StockTransactionStatus.POSTED
            or event.quantity != event.stock_transaction.quantity
        ):
            findings["invalid_valuations"].append(str(event.pk))
        if event.event_type == InventoryValuationEventType.REVERSAL and (
            not event.reversal_of_id
            or event.reversal_of.stock_transaction.status
            != StockTransactionStatus.REVERSED
        ):
            findings["invalid_reversals"].append(str(event.pk))
        if event.event_type == InventoryValuationEventType.RETURN and (
            not event.reversal_of_id
            or event.stock_transaction.transaction_type != StockTransactionType.REVERSAL
        ):
            findings["unsupported_return_lineage"].append(str(event.pk))
        if not event.source_version or not event.currency:
            findings["invalid_valuations"].append(str(event.pk))
    for pool in InventoryValuationPool.objects.filter(organization=organization):
        latest = events.filter(material=pool.material).order_by("-finalized_at").first()
        if latest and (
            pool.quantity != latest.quantity_after
            or pool.value_amount != latest.value_after
            or (
                pool.quantity and pool.average_cost != pool.value_amount / pool.quantity
            )
        ):
            findings["pool_mismatches"].append(str(pool.pk))
    for line in InventoryTransferLine.objects.filter(
        organization=organization
    ).select_related("dispatch_transaction", "receipt_transaction"):
        if not line.dispatch_transaction_id or not line.receipt_transaction_id:
            findings["transfer_mismatches"].append(str(line.pk))
            continue
        dispatch = events.filter(stock_transaction=line.dispatch_transaction).first()
        receipt = events.filter(stock_transaction=line.receipt_transaction).first()
        if (
            not dispatch
            or not receipt
            or dispatch.quantity != receipt.quantity
            or dispatch.value_amount != receipt.value_amount
        ):
            findings["transfer_mismatches"].append(str(line.pk))
    reversal_ids = set(
        events.filter(event_type=InventoryValuationEventType.REVERSAL).values_list(
            "reversal_of_id", flat=True
        )
    )
    for consumer, key in (
        (DownstreamCostConsumer.ACCOUNTING, "accounting_proposal_anomalies"),
        (DownstreamCostConsumer.PROJECT_CONTROLS, "project_cost_proposal_anomalies"),
    ):
        seen: set[object] = set()
        for envelope in DownstreamCostSourceEnvelope.objects.filter(
            organization=organization, consumer=consumer
        ).select_related("valuation_event"):
            event = envelope.valuation_event
            payload = envelope.payload
            invalid = (
                event.status != InventoryValuationStatus.FINALIZED
                or event.pk in reversal_ids
                or payload.get("valuation_event_id") != str(event.pk)
                or payload.get("amount") != str(event.value_amount)
                or payload.get("currency") != event.currency
                or payload.get("source_version") != event.source_version
            )
            if event.pk in seen or invalid:
                findings[key].append(str(envelope.pk))
            seen.add(event.pk)
    return {
        **findings,
        "unresolved_exceptions": [
            str(pk)
            for pk in InventoryValuationException.objects.filter(
                organization=organization, resolved_at__isnull=True
            ).values_list("pk", flat=True)
        ],
    }


@dataclass(frozen=True, slots=True)
class TraceAllocationSpec:
    quantity: Decimal
    bin: WarehouseBin | None = None
    lot: InventoryLot | None = None
    serial: InventorySerial | None = None
    is_legacy_unknown: bool = False


@dataclass(frozen=True, slots=True)
class TransferLineSpec:
    material: Material
    quantity: Decimal
    source_bin: WarehouseBin | None = None
    destination_bin: WarehouseBin | None = None
    lot: InventoryLot | None = None
    serial: InventorySerial | None = None


def _require(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
    project: Project | None = None,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        allow_any_scope=project is None,
        message="اجازه انجام این عملیات کنترل موجودی را ندارید.",
    )


def _save(instance: object, message: str) -> None:
    try:
        instance.full_clean()
        instance.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(message) from exc


def _audit(
    *,
    action: AuditAction,
    entity_type: str,
    entity_id: object,
    organization: Organization,
    actor: User,
    metadata: dict[str, object],
) -> None:
    record_audit_event(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        organization=organization,
        actor=actor,
        metadata=metadata,
    )


def effective_traceability_profile(
    *, material: Material, at=None
) -> MaterialTraceabilityProfile | None:
    instant = at or timezone.now()
    return (
        MaterialTraceabilityProfile.objects.filter(
            organization_id=material.organization_id,
            material=material,
            effective_from__lte=instant,
        )
        .filter(Q(effective_until__isnull=True) | Q(effective_until__gt=instant))
        .order_by("-effective_from", "-version")
        .first()
    )


@transaction.atomic
def create_warehouse_bin(
    *,
    organization: Organization,
    actor: User,
    warehouse: Warehouse,
    code: str,
    name: str,
    is_legacy_unlocated: bool = False,
) -> WarehouseBin:
    stored_warehouse = _get_warehouse(organization=organization, warehouse=warehouse)
    assert stored_warehouse is not None
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRACEABILITY_MANAGE,
        project=stored_warehouse.project,
    )
    record = WarehouseBin(
        organization=organization,
        warehouse=stored_warehouse,
        code=code,
        name=name,
        is_legacy_unlocated=is_legacy_unlocated,
        created_by=actor,
    )
    _save(record, "مکان انبار معتبر نیست یا تکراری است.")
    _audit(
        action=AuditAction.INVENTORY_TRACEABILITY_CONFIGURED,
        entity_type="warehouse_bin",
        entity_id=record.pk,
        organization=organization,
        actor=actor,
        metadata={"warehouse_id": str(stored_warehouse.pk), "code": record.code},
    )
    return record


@transaction.atomic
def create_traceability_profile(
    *,
    organization: Organization,
    actor: User,
    material: Material,
    mode: str,
    expiry_controlled: bool,
    effective_from,
    reason: str,
) -> MaterialTraceabilityProfile:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRACEABILITY_MANAGE,
    )
    stored_material = (
        Material.objects.select_for_update(of=("self",))
        .select_related("unit_of_measure")
        .filter(pk=material.pk, organization=organization)
        .first()
    )
    if stored_material is None:
        raise PermissionDenied("مصالح متعلق به این سازمان نیست.")
    if mode not in TraceabilityMode.values:
        raise ValueError("نوع رهگیری معتبر نیست.")
    if timezone.is_naive(effective_from):
        raise ValueError("زمان شروع سیاست رهگیری باید دارای منطقه زمانی باشد.")
    previous = (
        MaterialTraceabilityProfile.objects.select_for_update(of=("self",))
        .filter(material=stored_material)
        .order_by("-version")
        .first()
    )
    if previous and effective_from <= previous.effective_from:
        raise ValueError("نسخه جدید باید پس از نسخه پیشین آغاز شود.")
    if previous and previous.effective_until is None:
        MaterialTraceabilityProfile.objects.filter(pk=previous.pk).update(
            effective_until=effective_from
        )
    record = MaterialTraceabilityProfile(
        organization=organization,
        material=stored_material,
        version=(previous.version + 1) if previous else 1,
        mode=mode,
        expiry_controlled=expiry_controlled,
        effective_from=effective_from,
        reason=reason.strip(),
        activated_by=actor,
        activated_at=timezone.now(),
    )
    _save(record, "نسخه سیاست رهگیری معتبر نیست.")
    _audit(
        action=AuditAction.INVENTORY_TRACEABILITY_CONFIGURED,
        entity_type="material_traceability_profile",
        entity_id=record.pk,
        organization=organization,
        actor=actor,
        metadata={
            "material_id": str(stored_material.pk),
            "version": record.version,
            "mode": record.mode,
            "expiry_controlled": record.expiry_controlled,
        },
    )
    return record


@transaction.atomic
def create_inventory_lot(
    *,
    organization: Organization,
    actor: User,
    material: Material,
    lot_code: str,
    expires_on: date | None = None,
    manufactured_on: date | None = None,
) -> InventoryLot:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRACEABILITY_MANAGE,
    )
    profile = effective_traceability_profile(material=material)
    if material.organization_id != organization.pk or profile is None:
        raise PermissionDenied("سیاست رهگیری فعال برای این مصالح یافت نشد.")
    record = InventoryLot(
        organization=organization,
        material=material,
        profile=profile,
        lot_code=lot_code,
        manufactured_on=manufactured_on,
        expires_on=expires_on,
        created_by=actor,
    )
    _save(record, "بچ موجودی معتبر نیست یا تکراری است.")
    return record


@transaction.atomic
def create_inventory_serial(
    *,
    organization: Organization,
    actor: User,
    material: Material,
    serial_number: str,
    expires_on: date | None = None,
) -> InventorySerial:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRACEABILITY_MANAGE,
    )
    profile = effective_traceability_profile(material=material)
    if material.organization_id != organization.pk or profile is None:
        raise PermissionDenied("سیاست رهگیری فعال برای این مصالح یافت نشد.")
    record = InventorySerial(
        organization=organization,
        material=material,
        profile=profile,
        serial_number=serial_number,
        expires_on=expires_on,
        created_by=actor,
    )
    _save(record, "سریال موجودی معتبر نیست یا تکراری است.")
    return record


@transaction.atomic
def set_trace_quality_status(
    *,
    organization: Organization,
    actor: User,
    trace: InventoryLot | InventorySerial,
    status: str,
    reason: str,
) -> InventoryLot | InventorySerial:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRACEABILITY_DISPOSE,
    )
    if status not in TraceQualityStatus.values or status == trace.status:
        raise ValueError("وضعیت رهگیری مقصد معتبر نیست.")
    if not reason.strip():
        raise ValueError("دلیل تغییر وضعیت رهگیری الزامی است.")
    stored = (
        type(trace)
        .objects.select_for_update(of=("self",))
        .filter(pk=trace.pk, organization=organization)
        .first()
    )
    if stored is None:
        raise PermissionDenied("رهگیری متعلق به این سازمان نیست.")
    if stored.status == TraceQualityStatus.CLOSED:
        raise ValueError("رهگیری بسته‌شده قابل بازگشایی نیست.")
    stored.status = status
    stored.save(update_fields=["status", "updated_at"])
    _audit(
        action=AuditAction.INVENTORY_TRACEABILITY_CONFIGURED,
        entity_type=(
            "inventory_lot" if isinstance(stored, InventoryLot) else "inventory_serial"
        ),
        entity_id=stored.pk,
        organization=organization,
        actor=actor,
        metadata={"status": status, "reason": reason.strip()},
    )
    return stored


@transaction.atomic
def add_stock_trace_allocation(
    *,
    organization: Organization,
    actor: User,
    stock_transaction: StockTransaction,
    direction: str,
    spec: TraceAllocationSpec,
) -> StockTraceAllocation:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRACEABILITY_MANAGE,
        project=stock_transaction.project,
    )
    record = (
        StockTransaction.objects.select_for_update(of=("self",))
        .filter(pk=stock_transaction.pk, organization=organization)
        .first()
    )
    if record is None:
        raise PermissionDenied("تراکنش انبار متعلق به این سازمان نیست.")
    if record.status != StockTransactionStatus.DRAFT:
        raise ValueError("رهگیری فقط پیش از ثبت نهایی تراکنش قابل افزودن است.")
    if direction not in TraceAllocationDirection.values:
        raise ValueError("جهت تخصیص رهگیری معتبر نیست.")
    warehouse = (
        record.source_warehouse
        if direction == TraceAllocationDirection.SOURCE
        else record.destination_warehouse
    )
    if warehouse is None:
        raise ValueError("تراکنش در این جهت انبار ندارد.")
    allocation = StockTraceAllocation(
        organization=organization,
        stock_transaction=record,
        direction=direction,
        warehouse=warehouse,
        bin=spec.bin,
        lot=spec.lot,
        serial=spec.serial,
        quantity=spec.quantity,
        is_legacy_unknown=spec.is_legacy_unknown,
        created_by=actor,
    )
    _save(allocation, "تخصیص رهگیری تراکنش معتبر نیست.")
    return allocation


def _allocation_sum(*, transaction_record: StockTransaction, direction: str) -> Decimal:
    return transaction_record.trace_allocations.filter(direction=direction).aggregate(
        total=Sum("quantity")
    )["total"] or Decimal("0.0000")


def _trace_bucket_balance(
    *,
    organization: Organization,
    warehouse: Warehouse,
    material: Material,
    bin: WarehouseBin | None = None,
    lot: InventoryLot | None = None,
    serial: InventorySerial | None = None,
) -> Decimal:
    base = StockTraceAllocation.objects.filter(
        organization=organization,
        warehouse=warehouse,
        stock_transaction__material=material,
        stock_transaction__status__in=[
            StockTransactionStatus.POSTED,
            StockTransactionStatus.REVERSED,
        ],
        bin=bin,
        lot=lot,
        serial=serial,
    )
    incoming = base.filter(direction=TraceAllocationDirection.DESTINATION).aggregate(
        total=Sum("quantity")
    )["total"] or Decimal("0.0000")
    outgoing = base.filter(direction=TraceAllocationDirection.SOURCE).aggregate(
        total=Sum("quantity")
    )["total"] or Decimal("0.0000")
    return incoming - outgoing


def validate_stock_trace_allocations_for_post(
    transaction_record: StockTransaction,
) -> None:
    profile = effective_traceability_profile(
        material=transaction_record.material, at=transaction_record.occurred_at
    )
    for direction, warehouse in (
        (TraceAllocationDirection.SOURCE, transaction_record.source_warehouse),
        (
            TraceAllocationDirection.DESTINATION,
            transaction_record.destination_warehouse,
        ),
    ):
        if warehouse is None:
            continue
        allocations = list(
            transaction_record.trace_allocations.filter(
                direction=direction
            ).select_related("bin", "lot", "serial")
        )
        requires_allocations = bool(warehouse.bins.filter(is_active=True).exists()) or (
            profile is not None and profile.mode != TraceabilityMode.NONE
        )
        if not allocations and not requires_allocations:
            continue
        if (
            sum((item.quantity for item in allocations), Decimal("0.0000"))
            != transaction_record.quantity
        ):
            raise ValueError("جمع تخصیص‌های رهگیری باید با مقدار تراکنش برابر باشد.")
        for item in allocations:
            if item.bin_id and not item.bin.is_active:
                raise ValueError("مکان غیرفعال در تراکنش موجودی مجاز نیست.")
            if profile is None or profile.mode == TraceabilityMode.NONE:
                if item.lot_id or item.serial_id:
                    raise ValueError("سیاست فعال این مصالح رهگیری بچ یا سریال ندارد.")
            elif profile.mode == TraceabilityMode.LOT and not item.lot_id:
                raise ValueError("این مصالح به بچ نیاز دارد.")
            elif profile.mode == TraceabilityMode.SERIAL and not item.serial_id:
                raise ValueError("این مصالح به سریال نیاز دارد.")
            if item.lot_id and item.lot.profile_id != profile.pk:
                raise ValueError("بچ باید به نسخه فعال سیاست رهگیری متصل باشد.")
            if item.serial_id and item.serial.profile_id != profile.pk:
                raise ValueError("سریال باید به نسخه فعال سیاست رهگیری متصل باشد.")
            trace = item.lot or item.serial
            if direction == TraceAllocationDirection.SOURCE and trace is not None:
                if trace.status != TraceQualityStatus.AVAILABLE:
                    raise ValueError("موجودی قرنطینه یا بسته قابل خروج نیست.")
                if (
                    profile.expiry_controlled
                    and trace.expires_on < transaction_record.occurred_at.date()
                ):
                    raise ValueError("خروج موجودی منقضی‌شده مسدود است.")
                available = _trace_bucket_balance(
                    organization=transaction_record.organization,
                    warehouse=warehouse,
                    material=transaction_record.material,
                    bin=item.bin,
                    lot=item.lot,
                    serial=item.serial,
                )
                if available < item.quantity:
                    raise ValueError("موجودی رهگیری‌شده برای خروج کافی نیست.")


def copy_reversal_trace_allocations(
    *, original: StockTransaction, reversal: StockTransaction, actor: User
) -> None:
    for source in original.trace_allocations.all():
        direction = (
            TraceAllocationDirection.DESTINATION
            if source.direction == TraceAllocationDirection.SOURCE
            else TraceAllocationDirection.SOURCE
        )
        warehouse = (
            reversal.source_warehouse
            if direction == TraceAllocationDirection.SOURCE
            else reversal.destination_warehouse
        )
        StockTraceAllocation.objects.create(
            organization=reversal.organization,
            stock_transaction=reversal,
            direction=direction,
            warehouse=warehouse,
            bin=source.bin,
            lot=source.lot,
            serial=source.serial,
            quantity=source.quantity,
            is_legacy_unknown=source.is_legacy_unknown,
            created_by=actor,
        )


def _reserved_open_quantity(
    *,
    organization: Organization,
    warehouse: Warehouse,
    material: Material,
    bin: WarehouseBin | None = None,
    lot: InventoryLot | None = None,
    serial: InventorySerial | None = None,
) -> Decimal:
    rows = InventoryReservationAllocation.objects.filter(
        organization=organization,
        reservation__warehouse=warehouse,
        reservation__material=material,
        reservation__status__in=[
            ReservationStatus.ACTIVE,
            ReservationStatus.PARTIALLY_FULFILLED,
        ],
        bin=bin,
        lot=lot,
        serial=serial,
    )
    total = Decimal("0.0000")
    for row in rows:
        total += row.open_quantity
    return total


def available_to_reserve(
    *,
    organization: Organization,
    warehouse: Warehouse,
    material: Material,
    bin: WarehouseBin | None = None,
    lot: InventoryLot | None = None,
    serial: InventorySerial | None = None,
) -> Decimal:
    if any((bin, lot, serial)):
        on_hand = _trace_bucket_balance(
            organization=organization,
            warehouse=warehouse,
            material=material,
            bin=bin,
            lot=lot,
            serial=serial,
        )
    else:
        on_hand = _stock_balance_value(
            organization=organization, warehouse=warehouse, material=material
        )
    return on_hand - _reserved_open_quantity(
        organization=organization,
        warehouse=warehouse,
        material=material,
        bin=bin,
        lot=lot,
        serial=serial,
    )


@transaction.atomic
def create_reservation(
    *,
    organization: Organization,
    actor: User,
    reservation_number: str,
    project: Project,
    warehouse: Warehouse,
    material: Material,
    quantity: Decimal,
    site: ProjectSite | None = None,
    wbs_node: WBSNode | None = None,
    activity: Activity | None = None,
    need_by: date | None = None,
    expires_at=None,
) -> InventoryReservation:
    stored_warehouse = _get_warehouse(organization=organization, warehouse=warehouse)
    assert stored_warehouse is not None
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_RESERVATIONS_MANAGE,
        project=project,
    )
    stored_material, unit = _validate_material(
        organization=organization,
        material=material,
        unit_of_measure=material.unit_of_measure,
    )
    record = InventoryReservation(
        organization=organization,
        reservation_number=reservation_number,
        project=project,
        site=site,
        wbs_node=wbs_node,
        activity=activity,
        warehouse=stored_warehouse,
        material=stored_material,
        unit_of_measure=unit,
        quantity=quantity,
        need_by=need_by,
        expires_at=expires_at,
        created_by=actor,
        updated_by=actor,
    )
    _save(record, "رزرو موجودی معتبر نیست یا شماره آن تکراری است.")
    _audit(
        action=AuditAction.INVENTORY_RESERVATION_TRANSITIONED,
        entity_type="inventory_reservation",
        entity_id=record.pk,
        organization=organization,
        actor=actor,
        metadata={"status": record.status, "quantity": str(record.quantity)},
    )
    return record


@transaction.atomic
def activate_reservation(
    *,
    organization: Organization,
    actor: User,
    reservation: InventoryReservation,
    allocations: Iterable[TraceAllocationSpec],
) -> InventoryReservation:
    locked = (
        InventoryReservation.objects.select_for_update(of=("self",))
        .select_related("project", "warehouse", "material")
        .filter(pk=reservation.pk, organization=organization)
        .first()
    )
    if locked is None:
        raise PermissionDenied("رزرو متعلق به این سازمان نیست.")
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_RESERVATIONS_MANAGE,
        project=locked.project,
    )
    if locked.status != ReservationStatus.DRAFT:
        raise ValueError("فقط رزرو پیش‌نویس قابل فعال‌سازی است.")
    Warehouse.objects.select_for_update(of=("self",)).get(pk=locked.warehouse_id)
    specs = tuple(allocations)
    if (
        not specs
        or sum((item.quantity for item in specs), Decimal("0.0000")) != locked.quantity
    ):
        raise ValueError("جمع تخصیص‌های رزرو باید با مقدار رزرو برابر باشد.")
    profile = effective_traceability_profile(material=locked.material)
    for spec in specs:
        if profile and profile.mode == TraceabilityMode.LOT and spec.lot is None:
            raise ValueError("سیاست فعال این مصالح تخصیص بچ را الزامی می‌کند.")
        if profile and profile.mode == TraceabilityMode.SERIAL and spec.serial is None:
            raise ValueError("سیاست فعال این مصالح تخصیص سریال را الزامی می‌کند.")
        if locked.warehouse.bins.filter(is_active=True).exists() and spec.bin is None:
            raise ValueError("انبار دارای مکان فعال است و تخصیص مکان الزامی است.")
        if (
            available_to_reserve(
                organization=organization,
                warehouse=locked.warehouse,
                material=locked.material,
                bin=spec.bin,
                lot=spec.lot,
                serial=spec.serial,
            )
            < spec.quantity
        ):
            raise ValueError("موجودی قابل رزرو کافی نیست.")
        trace = spec.lot or spec.serial
        if trace is not None:
            if trace.status != TraceQualityStatus.AVAILABLE:
                raise ValueError("موجودی قرنطینه یا بسته قابل رزرو نیست.")
            if (
                profile
                and profile.expiry_controlled
                and trace.expires_on < timezone.localdate()
            ):
                raise ValueError("رزرو موجودی منقضی‌شده مسدود است.")
        allocation = InventoryReservationAllocation(
            organization=organization,
            reservation=locked,
            bin=spec.bin,
            lot=spec.lot,
            serial=spec.serial,
            quantity=spec.quantity,
        )
        _save(allocation, "تخصیص رزرو معتبر نیست.")
    locked.status = ReservationStatus.ACTIVE
    locked.activated_at = timezone.now()
    locked.updated_by = actor
    locked.save(update_fields=["status", "activated_at", "updated_by", "updated_at"])
    _audit(
        action=AuditAction.INVENTORY_RESERVATION_TRANSITIONED,
        entity_type="inventory_reservation",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"status": locked.status},
    )
    return locked


@transaction.atomic
def fulfill_reservation_allocation(
    *,
    organization: Organization,
    actor: User,
    allocation: InventoryReservationAllocation,
    stock_transaction: StockTransaction,
    quantity: Decimal,
) -> InventoryReservation:
    locked = (
        InventoryReservationAllocation.objects.select_for_update(of=("self",))
        .select_related(
            "reservation__project", "reservation__warehouse", "reservation__material"
        )
        .filter(pk=allocation.pk, organization=organization)
        .first()
    )
    if locked is None:
        raise PermissionDenied("تخصیص رزرو متعلق به این سازمان نیست.")
    reservation = locked.reservation
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_RESERVATIONS_MANAGE,
        project=reservation.project,
    )
    movement = StockTransaction.objects.filter(
        pk=stock_transaction.pk,
        organization=organization,
        status=StockTransactionStatus.POSTED,
        transaction_type=StockTransactionType.ISSUE,
        source_warehouse=reservation.warehouse,
        material=reservation.material,
        project=reservation.project,
    ).first()
    if movement is None:
        raise ValueError("تأمین رزرو به حواله خروج نهایی‌شده سازگار نیاز دارد.")
    if quantity <= 0 or quantity > locked.open_quantity:
        raise ValueError("مقدار تأمین رزرو معتبر نیست.")
    locked.fulfilled_quantity += quantity
    locked.fulfillment_transaction = movement
    if locked.open_quantity == Decimal("0.0000"):
        locked.status = ReservationAllocationStatus.FULFILLED
    locked.save(
        update_fields=[
            "fulfilled_quantity",
            "fulfillment_transaction",
            "status",
            "updated_at",
        ]
    )
    open_quantity = sum(
        (item.open_quantity for item in reservation.allocations.all()),
        Decimal("0.0000"),
    )
    fulfilled = sum(
        (item.fulfilled_quantity for item in reservation.allocations.all()),
        Decimal("0.0000"),
    )
    reservation.status = (
        ReservationStatus.FULFILLED
        if open_quantity == Decimal("0.0000") and fulfilled == reservation.quantity
        else ReservationStatus.PARTIALLY_FULFILLED
    )
    if reservation.status == ReservationStatus.FULFILLED:
        reservation.fulfilled_at = timezone.now()
    reservation.updated_by = actor
    reservation.save(
        update_fields=["status", "fulfilled_at", "updated_by", "updated_at"]
    )
    _audit(
        action=AuditAction.INVENTORY_RESERVATION_TRANSITIONED,
        entity_type="inventory_reservation",
        entity_id=reservation.pk,
        organization=organization,
        actor=actor,
        metadata={"status": reservation.status, "quantity": str(quantity)},
    )
    return reservation


@transaction.atomic
def release_reservation(
    *,
    organization: Organization,
    actor: User,
    reservation: InventoryReservation,
    reason: str,
    expired: bool = False,
) -> InventoryReservation:
    locked = (
        InventoryReservation.objects.select_for_update(of=("self",))
        .select_related("project")
        .filter(pk=reservation.pk, organization=organization)
        .first()
    )
    if locked is None:
        raise PermissionDenied("رزرو متعلق به این سازمان نیست.")
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_RESERVATIONS_RELEASE,
        project=locked.project,
    )
    if locked.status not in {
        ReservationStatus.ACTIVE,
        ReservationStatus.PARTIALLY_FULFILLED,
    }:
        raise ValueError("این رزرو قابل آزادسازی نیست.")
    if not reason.strip():
        raise ValueError("دلیل آزادسازی رزرو الزامی است.")
    for allocation in locked.allocations.select_for_update(of=("self",)):
        if allocation.open_quantity > 0:
            allocation.released_quantity += allocation.open_quantity
            allocation.status = ReservationAllocationStatus.RELEASED
            allocation.release_reason = reason.strip()
            allocation.save(
                update_fields=[
                    "released_quantity",
                    "status",
                    "release_reason",
                    "updated_at",
                ]
            )
    locked.status = (
        ReservationStatus.EXPIRED if expired else ReservationStatus.CANCELLED
    )
    locked.cancelled_at = timezone.now()
    locked.cancellation_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancellation_reason",
            "updated_by",
            "updated_at",
        ]
    )
    _audit(
        action=AuditAction.INVENTORY_RESERVATION_TRANSITIONED,
        entity_type="inventory_reservation",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"status": locked.status, "reason": reason.strip()},
    )
    return locked


def expire_due_reservations(*, organization: Organization, actor: User, at=None) -> int:
    instant = at or timezone.now()
    due = list(
        InventoryReservation.objects.filter(
            organization=organization,
            status__in=[
                ReservationStatus.ACTIVE,
                ReservationStatus.PARTIALLY_FULFILLED,
            ],
            expires_at__lte=instant,
        ).only("pk")
    )
    for item in due:
        release_reservation(
            organization=organization,
            actor=actor,
            reservation=item,
            reason="انقضای زمان رزرو",
            expired=True,
        )
    return len(due)


@transaction.atomic
def create_inventory_count(
    *,
    organization: Organization,
    actor: User,
    count_number: str,
    warehouse: Warehouse,
    bin: WarehouseBin | None = None,
) -> InventoryCount:
    stored = _get_warehouse(organization=organization, warehouse=warehouse)
    assert stored is not None
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_COUNTS_PREPARE,
        project=stored.project,
    )
    record = InventoryCount(
        organization=organization,
        count_number=count_number,
        warehouse=stored,
        bin=bin,
        created_by=actor,
    )
    _save(record, "شمارش موجودی معتبر نیست یا شماره آن تکراری است.")
    _audit(
        action=AuditAction.INVENTORY_COUNT_TRANSITIONED,
        entity_type="inventory_count",
        entity_id=record.pk,
        organization=organization,
        actor=actor,
        metadata={"status": record.status},
    )
    return record


@transaction.atomic
def freeze_inventory_count(
    *, organization: Organization, actor: User, inventory_count: InventoryCount
) -> InventoryCount:
    locked = (
        InventoryCount.objects.select_for_update(of=("self",))
        .select_related("warehouse__project", "bin")
        .filter(pk=inventory_count.pk, organization=organization)
        .first()
    )
    if locked is None:
        raise PermissionDenied("شمارش متعلق به این سازمان نیست.")
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_COUNTS_PREPARE,
        project=locked.warehouse.project,
    )
    if locked.status != InventoryCountStatus.DRAFT:
        raise ValueError("فقط شمارش پیش‌نویس قابل انجماد است.")
    Warehouse.objects.select_for_update(of=("self",)).get(pk=locked.warehouse_id)
    movements = StockTransaction.objects.filter(
        organization=organization,
        status__in=[StockTransactionStatus.POSTED, StockTransactionStatus.REVERSED],
    ).filter(
        Q(source_warehouse=locked.warehouse) | Q(destination_warehouse=locked.warehouse)
    )
    material_ids = movements.values_list("material_id", flat=True).distinct()
    for material in Material.objects.filter(pk__in=material_ids).select_related(
        "unit_of_measure"
    ):
        allocation_rows = StockTraceAllocation.objects.filter(
            organization=organization,
            warehouse=locked.warehouse,
            stock_transaction__material=material,
            stock_transaction__status__in=[
                StockTransactionStatus.POSTED,
                StockTransactionStatus.REVERSED,
            ],
        )
        if locked.bin_id:
            allocation_rows = allocation_rows.filter(bin=locked.bin)
        grouped = allocation_rows.values(
            "bin_id", "lot_id", "serial_id", "direction"
        ).annotate(total=Sum("quantity"))
        bucket_totals: dict[tuple[object, object, object], Decimal] = {}
        for row in grouped:
            key = (row["bin_id"], row["lot_id"], row["serial_id"])
            sign = (
                Decimal("1.0000")
                if row["direction"] == TraceAllocationDirection.DESTINATION
                else Decimal("-1.0000")
            )
            bucket_totals[key] = bucket_totals.get(key, Decimal("0.0000")) + (
                sign * row["total"]
            )
        if bucket_totals:
            for (bin_id, lot_id, serial_id), expected in bucket_totals.items():
                if expected == Decimal("0.0000"):
                    continue
                InventoryCountLine.objects.create(
                    organization=organization,
                    inventory_count=locked,
                    material=material,
                    unit_of_measure=material.unit_of_measure,
                    bin_id=bin_id,
                    lot_id=lot_id,
                    serial_id=serial_id,
                    expected_quantity=expected,
                )
        elif not locked.bin_id:
            expected = _stock_balance_value(
                organization=organization,
                warehouse=locked.warehouse,
                material=material,
            )
            if expected == Decimal("0.0000"):
                continue
            InventoryCountLine.objects.create(
                organization=organization,
                inventory_count=locked,
                material=material,
                unit_of_measure=material.unit_of_measure,
                expected_quantity=expected,
            )
    watermark = movements.aggregate(value=Max("posted_at"))["value"]
    locked.status = InventoryCountStatus.FROZEN
    locked.frozen_at = timezone.now()
    locked.stock_watermark = watermark
    locked.save(update_fields=["status", "frozen_at", "stock_watermark", "updated_at"])
    _audit(
        action=AuditAction.INVENTORY_COUNT_TRANSITIONED,
        entity_type="inventory_count",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"status": locked.status, "line_count": locked.lines.count()},
    )
    return locked


@transaction.atomic
def record_counted_quantity(
    *,
    organization: Organization,
    actor: User,
    line: InventoryCountLine,
    counted_quantity: Decimal,
    variance_reason: str = "",
) -> InventoryCountLine:
    locked = (
        InventoryCountLine.objects.select_for_update(of=("self",))
        .select_related("inventory_count__warehouse__project")
        .filter(pk=line.pk, organization=organization)
        .first()
    )
    if locked is None:
        raise PermissionDenied("خط شمارش متعلق به این سازمان نیست.")
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_COUNTS_PREPARE,
        project=locked.inventory_count.warehouse.project,
    )
    if locked.inventory_count.status not in {
        InventoryCountStatus.FROZEN,
        InventoryCountStatus.COUNTED,
    }:
        raise ValueError("ثبت مقدار فقط در مرحله شمارش مجاز است.")
    if counted_quantity < 0:
        raise ValueError("مقدار شمارش نمی‌تواند منفی باشد.")
    if counted_quantity != locked.expected_quantity and not variance_reason.strip():
        raise ValueError("برای مغایرت شمارش دلیل الزامی است.")
    locked.counted_quantity = counted_quantity
    locked.variance_reason = variance_reason.strip()
    locked.save(update_fields=["counted_quantity", "variance_reason", "updated_at"])
    inventory_count = locked.inventory_count
    if not inventory_count.lines.filter(counted_quantity__isnull=True).exists():
        inventory_count.status = InventoryCountStatus.COUNTED
        inventory_count.save(update_fields=["status", "updated_at"])
        _audit(
            action=AuditAction.INVENTORY_COUNT_TRANSITIONED,
            entity_type="inventory_count",
            entity_id=inventory_count.pk,
            organization=organization,
            actor=actor,
            metadata={"status": inventory_count.status},
        )
    return locked


@transaction.atomic
def submit_inventory_count(
    *, organization: Organization, actor: User, inventory_count: InventoryCount
) -> InventoryCount:
    locked = (
        InventoryCount.objects.select_for_update(of=("self",))
        .select_related("warehouse__project")
        .get(pk=inventory_count.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_COUNTS_PREPARE,
        project=locked.warehouse.project,
    )
    if locked.status != InventoryCountStatus.COUNTED:
        raise ValueError("فقط شمارش کامل قابل ارسال است.")
    locked.status = InventoryCountStatus.SUBMITTED
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
    _audit(
        action=AuditAction.INVENTORY_COUNT_TRANSITIONED,
        entity_type="inventory_count",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"status": locked.status},
    )
    return locked


@transaction.atomic
def approve_inventory_count(
    *, organization: Organization, actor: User, inventory_count: InventoryCount
) -> InventoryCount:
    locked = (
        InventoryCount.objects.select_for_update(of=("self",))
        .select_related("warehouse__project")
        .get(pk=inventory_count.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_COUNTS_APPROVE,
        project=locked.warehouse.project,
    )
    if locked.status != InventoryCountStatus.SUBMITTED:
        raise ValueError("فقط شمارش ارسال‌شده قابل تأیید است.")
    if actor.pk in {locked.created_by_id, locked.submitted_by_id}:
        raise PermissionDenied("تهیه‌کننده یا ارسال‌کننده نمی‌تواند شمارش را تأیید کند.")
    locked.status = InventoryCountStatus.APPROVED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    _audit(
        action=AuditAction.INVENTORY_COUNT_TRANSITIONED,
        entity_type="inventory_count",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"status": locked.status},
    )
    return locked


@transaction.atomic
def post_inventory_count(
    *, organization: Organization, actor: User, inventory_count: InventoryCount
) -> InventoryCount:
    locked = (
        InventoryCount.objects.select_for_update(of=("self",))
        .select_related("warehouse__project")
        .get(pk=inventory_count.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_COUNTS_POST,
        project=locked.warehouse.project,
    )
    if locked.status != InventoryCountStatus.APPROVED:
        raise ValueError("فقط شمارش تأییدشده قابل ثبت است.")
    if actor.pk == locked.created_by_id:
        raise PermissionDenied("تهیه‌کننده نمی‌تواند تعدیل شمارش را ثبت کند.")
    Warehouse.objects.select_for_update(of=("self",)).get(pk=locked.warehouse_id)
    intervening = StockTransaction.objects.filter(
        organization=organization,
        status__in=[StockTransactionStatus.POSTED, StockTransactionStatus.REVERSED],
        posted_at__gt=locked.frozen_at,
    ).filter(
        Q(source_warehouse=locked.warehouse) | Q(destination_warehouse=locked.warehouse)
    )
    if intervening.exists():
        raise ValueError(
            "پس از انجماد شمارش گردش موجودی ثبت شده است؛ شمارش باید تکرار شود."
        )
    for index, line in enumerate(
        locked.lines.select_for_update(of=("self",)).select_related(
            "material__unit_of_measure"
        ),
        start=1,
    ):
        variance = line.variance
        if variance is None or variance == Decimal("0.0000"):
            continue
        movement = create_stock_transaction(
            organization=organization,
            actor=actor,
            transaction_number=f"{locked.count_number}-{index}",
            transaction_type=(
                StockTransactionType.ADJUSTMENT_IN
                if variance > 0
                else StockTransactionType.ADJUSTMENT_OUT
            ),
            source_warehouse=locked.warehouse if variance < 0 else None,
            destination_warehouse=locked.warehouse if variance > 0 else None,
            material=line.material,
            unit_of_measure=line.unit_of_measure,
            project=locked.warehouse.project,
            quantity=abs(variance),
            occurred_at=timezone.now(),
            reference=locked.count_number,
            notes=line.variance_reason,
        )
        direction = (
            TraceAllocationDirection.DESTINATION
            if variance > 0
            else TraceAllocationDirection.SOURCE
        )
        if any((line.bin_id, line.lot_id, line.serial_id)):
            add_stock_trace_allocation(
                organization=organization,
                actor=actor,
                stock_transaction=movement,
                direction=direction,
                spec=TraceAllocationSpec(
                    quantity=abs(variance),
                    bin=line.bin,
                    lot=line.lot,
                    serial=line.serial,
                ),
            )
        movement = post_stock_transaction(
            organization=organization, actor=actor, stock_transaction=movement
        )
        line.adjustment_transaction = movement
        line.save(update_fields=["adjustment_transaction", "updated_at"])
    locked.status = InventoryCountStatus.POSTED
    locked.posted_by = actor
    locked.posted_at = timezone.now()
    locked.save(update_fields=["status", "posted_by", "posted_at", "updated_at"])
    _audit(
        action=AuditAction.INVENTORY_COUNT_TRANSITIONED,
        entity_type="inventory_count",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"status": locked.status},
    )
    return locked


@transaction.atomic
def create_inventory_transfer(
    *,
    organization: Organization,
    actor: User,
    transfer_number: str,
    source_warehouse: Warehouse,
    destination_warehouse: Warehouse,
    lines: Iterable[TransferLineSpec],
) -> InventoryTransfer:
    source = _get_warehouse(organization=organization, warehouse=source_warehouse)
    destination = _get_warehouse(
        organization=organization, warehouse=destination_warehouse
    )
    assert source is not None and destination is not None
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRANSFERS_PREPARE,
        project=source.project,
    )
    if source.pk == destination.pk:
        raise ValueError("انبار مبدأ و مقصد انتقال باید متفاوت باشند.")
    record = InventoryTransfer(
        organization=organization,
        transfer_number=transfer_number,
        source_warehouse=source,
        destination_warehouse=destination,
        created_by=actor,
    )
    _save(record, "انتقال موجودی معتبر نیست یا شماره آن تکراری است.")
    line_specs = tuple(lines)
    if not line_specs:
        raise ValueError("انتقال باید حداقل یک ردیف داشته باشد.")
    for spec in line_specs:
        stored_material, unit = _validate_material(
            organization=organization,
            material=spec.material,
            unit_of_measure=spec.material.unit_of_measure,
        )
        line = InventoryTransferLine(
            organization=organization,
            transfer=record,
            material=stored_material,
            unit_of_measure=unit,
            quantity=spec.quantity,
            source_bin=spec.source_bin,
            destination_bin=spec.destination_bin,
            lot=spec.lot,
            serial=spec.serial,
        )
        _save(line, "ردیف انتقال موجودی معتبر نیست.")
    _audit(
        action=AuditAction.INVENTORY_TRANSFER_TRANSITIONED,
        entity_type="inventory_transfer",
        entity_id=record.pk,
        organization=organization,
        actor=actor,
        metadata={"status": record.status},
    )
    return record


@transaction.atomic
def dispatch_inventory_transfer(
    *, organization: Organization, actor: User, inventory_transfer: InventoryTransfer
) -> InventoryTransfer:
    locked = (
        InventoryTransfer.objects.select_for_update(of=("self",))
        .select_related("source_warehouse__project", "destination_warehouse")
        .get(pk=inventory_transfer.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRANSFERS_DISPATCH,
        project=locked.source_warehouse.project,
    )
    if locked.status != InventoryTransferStatus.DRAFT:
        raise ValueError("فقط انتقال پیش‌نویس قابل ارسال است.")
    for index, line in enumerate(
        locked.lines.select_for_update(of=("self",)).select_related(
            "material__unit_of_measure"
        ),
        start=1,
    ):
        movement = create_stock_transaction(
            organization=organization,
            actor=actor,
            transaction_number=f"{locked.transfer_number}-D{index}",
            transaction_type=StockTransactionType.ADJUSTMENT_OUT,
            source_warehouse=locked.source_warehouse,
            material=line.material,
            unit_of_measure=line.unit_of_measure,
            project=locked.source_warehouse.project,
            quantity=line.quantity,
            occurred_at=timezone.now(),
            reference=locked.transfer_number,
            notes="ارسال انتقال امانی موجودی",
        )
        if any((line.source_bin_id, line.lot_id, line.serial_id)):
            add_stock_trace_allocation(
                organization=organization,
                actor=actor,
                stock_transaction=movement,
                direction=TraceAllocationDirection.SOURCE,
                spec=TraceAllocationSpec(
                    quantity=line.quantity,
                    bin=line.source_bin,
                    lot=line.lot,
                    serial=line.serial,
                ),
            )
        line.dispatch_transaction = post_stock_transaction(
            organization=organization, actor=actor, stock_transaction=movement
        )
        line.save(update_fields=["dispatch_transaction", "updated_at"])
    locked.status = InventoryTransferStatus.DISPATCHED
    locked.dispatched_by = actor
    locked.dispatched_at = timezone.now()
    locked.save(
        update_fields=["status", "dispatched_by", "dispatched_at", "updated_at"]
    )
    _audit(
        action=AuditAction.INVENTORY_TRANSFER_TRANSITIONED,
        entity_type="inventory_transfer",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"status": locked.status},
    )
    return locked


@transaction.atomic
def mark_transfer_in_transit(
    *, organization: Organization, actor: User, inventory_transfer: InventoryTransfer
) -> InventoryTransfer:
    locked = (
        InventoryTransfer.objects.select_for_update(of=("self",))
        .select_related("source_warehouse__project")
        .get(pk=inventory_transfer.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRANSFERS_DISPATCH,
        project=locked.source_warehouse.project,
    )
    if locked.status != InventoryTransferStatus.DISPATCHED:
        raise ValueError("فقط انتقال ارسال‌شده وارد وضعیت در راه می‌شود.")
    locked.status = InventoryTransferStatus.IN_TRANSIT
    locked.in_transit_at = timezone.now()
    locked.save(update_fields=["status", "in_transit_at", "updated_at"])
    _audit(
        action=AuditAction.INVENTORY_TRANSFER_TRANSITIONED,
        entity_type="inventory_transfer",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"status": locked.status},
    )
    return locked


@transaction.atomic
def accept_inventory_transfer(
    *,
    organization: Organization,
    actor: User,
    inventory_transfer: InventoryTransfer,
    outcomes: dict[object, tuple[Decimal, str, str]],
) -> InventoryTransfer:
    locked = (
        InventoryTransfer.objects.select_for_update(of=("self",))
        .select_related("destination_warehouse__project")
        .get(pk=inventory_transfer.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRANSFERS_ACCEPT,
        project=locked.destination_warehouse.project,
    )
    if locked.status != InventoryTransferStatus.IN_TRANSIT:
        raise ValueError("فقط انتقال در راه قابل پذیرش است.")
    if actor.pk == locked.dispatched_by_id:
        raise PermissionDenied("ارسال‌کننده نمی‌تواند همان انتقال را پذیرش کند.")
    for index, line in enumerate(
        locked.lines.select_for_update(of=("self",)).select_related(
            "material__unit_of_measure"
        ),
        start=1,
    ):
        try:
            accepted_quantity, exception_code, exception_reason = outcomes[line.pk]
        except KeyError as exc:
            raise ValueError("نتیجه پذیرش همه ردیف‌های انتقال الزامی است.") from exc
        if accepted_quantity < 0 or accepted_quantity > line.quantity:
            raise ValueError("مقدار پذیرش انتقال معتبر نیست.")
        if accepted_quantity < line.quantity and (
            exception_code == TransferExceptionCode.NONE or not exception_reason.strip()
        ):
            raise ValueError("کسری انتقال به نوع و دلیل مغایرت نیاز دارد.")
        if (
            accepted_quantity == line.quantity
            and exception_code != TransferExceptionCode.NONE
        ):
            raise ValueError("انتقال کامل نباید نوع مغایرت داشته باشد.")
        line.accepted_quantity = accepted_quantity
        line.exception_code = exception_code
        line.exception_reason = exception_reason.strip()
        if accepted_quantity > 0:
            movement = create_stock_transaction(
                organization=organization,
                actor=actor,
                transaction_number=f"{locked.transfer_number}-R{index}",
                transaction_type=StockTransactionType.ADJUSTMENT_IN,
                destination_warehouse=locked.destination_warehouse,
                material=line.material,
                unit_of_measure=line.unit_of_measure,
                project=locked.destination_warehouse.project,
                quantity=accepted_quantity,
                occurred_at=timezone.now(),
                reference=locked.transfer_number,
                notes="پذیرش انتقال امانی موجودی",
            )
            if any((line.destination_bin_id, line.lot_id, line.serial_id)):
                add_stock_trace_allocation(
                    organization=organization,
                    actor=actor,
                    stock_transaction=movement,
                    direction=TraceAllocationDirection.DESTINATION,
                    spec=TraceAllocationSpec(
                        quantity=accepted_quantity,
                        bin=line.destination_bin,
                        lot=line.lot,
                        serial=line.serial,
                    ),
                )
            line.receipt_transaction = post_stock_transaction(
                organization=organization, actor=actor, stock_transaction=movement
            )
        line.save(
            update_fields=[
                "accepted_quantity",
                "exception_code",
                "exception_reason",
                "receipt_transaction",
                "updated_at",
            ]
        )
    locked.status = InventoryTransferStatus.ACCEPTED
    locked.accepted_by = actor
    locked.accepted_at = timezone.now()
    locked.save(update_fields=["status", "accepted_by", "accepted_at", "updated_at"])
    _audit(
        action=AuditAction.INVENTORY_TRANSFER_TRANSITIONED,
        entity_type="inventory_transfer",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"status": locked.status},
    )
    return locked


@transaction.atomic
def resolve_transfer_exception(
    *,
    organization: Organization,
    actor: User,
    line: InventoryTransferLine,
    resolution: str,
) -> InventoryTransferLine:
    locked = (
        InventoryTransferLine.objects.select_for_update(of=("self",))
        .select_related("transfer__destination_warehouse__project")
        .get(pk=line.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRANSFERS_RESOLVE,
        project=locked.transfer.destination_warehouse.project,
    )
    if (
        locked.transfer.status != InventoryTransferStatus.ACCEPTED
        or locked.exception_quantity <= 0
    ):
        raise ValueError("این ردیف مغایرت قابل تعیین تکلیف ندارد.")
    if locked.exception_resolved_at:
        raise ValueError("مغایرت از قبل تعیین تکلیف شده است.")
    if not resolution.strip():
        raise ValueError("شرح تعیین تکلیف مغایرت الزامی است.")
    locked.exception_reason = (
        f"{locked.exception_reason}\nتعیین تکلیف: {resolution.strip()}"
    )
    locked.exception_resolved_at = timezone.now()
    locked.exception_resolved_by = actor
    locked.save(
        update_fields=[
            "exception_reason",
            "exception_resolved_at",
            "exception_resolved_by",
            "updated_at",
        ]
    )
    _audit(
        action=AuditAction.INVENTORY_TRANSFER_TRANSITIONED,
        entity_type="inventory_transfer_exception",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"resolution": resolution.strip()},
    )
    return locked


@transaction.atomic
def backfill_legacy_unlocated_allocations(
    *,
    organization: Organization,
    actor: User,
    warehouse: Warehouse | None = None,
) -> int:
    """Record unknown legacy custody without inventing bin, lot, or serial facts."""

    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.INVENTORY_TRACEABILITY_MANAGE,
    )
    if warehouse is not None:
        warehouse = _get_warehouse(organization=organization, warehouse=warehouse)
    movements = StockTransaction.objects.select_for_update(of=("self",)).filter(
        organization=organization,
        status__in=[StockTransactionStatus.POSTED, StockTransactionStatus.REVERSED],
    )
    if warehouse is not None:
        movements = movements.filter(
            Q(source_warehouse=warehouse) | Q(destination_warehouse=warehouse)
        )

    created = 0
    legacy_bins: dict[object, WarehouseBin] = {}
    for movement in movements.order_by("created_at", "pk"):
        for direction, movement_warehouse in (
            (TraceAllocationDirection.SOURCE, movement.source_warehouse),
            (TraceAllocationDirection.DESTINATION, movement.destination_warehouse),
        ):
            if (
                movement_warehouse is None
                or movement.trace_allocations.filter(direction=direction).exists()
            ):
                continue
            legacy_bin = legacy_bins.get(movement_warehouse.pk)
            if legacy_bin is None:
                legacy_bin = WarehouseBin.objects.filter(
                    organization=organization,
                    warehouse=movement_warehouse,
                    is_legacy_unlocated=True,
                ).first()
                if legacy_bin is None:
                    legacy_bin = WarehouseBin(
                        organization=organization,
                        warehouse=movement_warehouse,
                        code="LEGACY-UNLOCATED",
                        name="مکان نامشخص میراثی",
                        is_legacy_unlocated=True,
                        created_by=actor,
                    )
                    _save(legacy_bin, "ایجاد مکان نامشخص میراثی ممکن نشد.")
                legacy_bins[movement_warehouse.pk] = legacy_bin
            allocation = StockTraceAllocation(
                organization=organization,
                stock_transaction=movement,
                direction=direction,
                warehouse=movement_warehouse,
                bin=legacy_bin,
                quantity=movement.quantity,
                is_legacy_unknown=True,
                created_by=actor,
            )
            _save(allocation, "ثبت وضعیت نامشخص میراثی ممکن نشد.")
            created += 1

    _audit(
        action=AuditAction.INVENTORY_TRACEABILITY_CONFIGURED,
        entity_type="legacy_unlocated_backfill",
        entity_id=warehouse.pk if warehouse else organization.pk,
        organization=organization,
        actor=actor,
        metadata={"created_allocations": created},
    )
    return created


def inventory_reconciliation(
    *, organization: Organization, user: User
) -> dict[str, object]:
    _require(
        organization=organization,
        actor=user,
        permission=BusinessPermissionCode.INVENTORY_RECONCILIATIONS_VIEW,
    )
    allocation_mismatches: list[dict[str, object]] = []
    unallocated_positions: list[dict[str, object]] = []
    transactions = StockTransaction.objects.filter(
        organization=organization,
        status__in=[StockTransactionStatus.POSTED, StockTransactionStatus.REVERSED],
    )
    for record in transactions.prefetch_related("trace_allocations"):
        for direction, warehouse_id in (
            (TraceAllocationDirection.SOURCE, record.source_warehouse_id),
            (TraceAllocationDirection.DESTINATION, record.destination_warehouse_id),
        ):
            if warehouse_id is None:
                continue
            total = _allocation_sum(transaction_record=record, direction=direction)
            if total == Decimal("0.0000"):
                unallocated_positions.append(
                    {
                        "transaction_id": str(record.pk),
                        "direction": direction,
                        "movement_quantity": record.quantity,
                    }
                )
            elif total != record.quantity:
                allocation_mismatches.append(
                    {
                        "transaction_id": str(record.pk),
                        "direction": direction,
                        "movement_quantity": record.quantity,
                        "allocated_quantity": total,
                    }
                )
    open_in_transit = InventoryTransfer.objects.filter(
        organization=organization,
        status__in=[
            InventoryTransferStatus.DISPATCHED,
            InventoryTransferStatus.IN_TRANSIT,
        ],
    ).count()
    unresolved_transfer_exceptions = InventoryTransferLine.objects.filter(
        organization=organization,
        transfer__status=InventoryTransferStatus.ACCEPTED,
        accepted_quantity__lt=F("quantity"),
        exception_resolved_at__isnull=True,
    ).count()
    return {
        "allocation_mismatches": allocation_mismatches,
        "unallocated_positions": unallocated_positions,
        "legacy_unknown_allocations": StockTraceAllocation.objects.filter(
            organization=organization, is_legacy_unknown=True
        ).count(),
        "open_in_transit": open_in_transit,
        "unresolved_transfer_exceptions": unresolved_transfer_exceptions,
        "active_reservations": InventoryReservation.objects.filter(
            organization=organization,
            status__in=[
                ReservationStatus.ACTIVE,
                ReservationStatus.PARTIALLY_FULFILLED,
            ],
        ).count(),
    }


def get_reservations(
    *, organization: Organization, user: User
) -> QuerySet[InventoryReservation]:
    _require(
        organization=organization,
        actor=user,
        permission=BusinessPermissionCode.INVENTORY_RESERVATIONS_VIEW,
    )
    membership = get_active_membership(user=user, organization=organization)
    return scope_queryset(
        queryset=InventoryReservation.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "warehouse", "material", "unit_of_measure")


def get_inventory_counts(
    *, organization: Organization, user: User
) -> QuerySet[InventoryCount]:
    _require(
        organization=organization,
        actor=user,
        permission=BusinessPermissionCode.INVENTORY_COUNTS_VIEW,
    )
    membership = get_active_membership(user=user, organization=organization)
    return scope_queryset(
        queryset=InventoryCount.objects.filter(organization=organization),
        membership=membership,
        project_lookup="warehouse__project_id",
    ).select_related("warehouse", "bin")


def get_inventory_transfers(
    *, organization: Organization, user: User
) -> QuerySet[InventoryTransfer]:
    _require(
        organization=organization,
        actor=user,
        permission=BusinessPermissionCode.INVENTORY_TRANSFERS_VIEW,
    )
    membership = get_active_membership(user=user, organization=organization)
    return scope_queryset(
        queryset=InventoryTransfer.objects.filter(organization=organization),
        membership=membership,
        project_lookup="source_warehouse__project_id",
    ).select_related("source_warehouse", "destination_warehouse")
