"""P8 operational commands.  They deliberately contain no financial consumer call."""

from datetime import datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.equipment.models import Equipment, EquipmentAssignment
from apps.equipment.p8_models import (
    DowntimeEvent,
    EquipmentMeter,
    EquipmentUsageLog,
    EquipmentWorkOrder,
    FuelLog,
    MaintenanceSparePartReference,
    MaintenanceWorkOrderEvidence,
    MeterReading,
    OperatorEquipmentQualification,
)
from apps.inventory.models import (
    StockTransaction,
    StockTransactionStatus,
    StockTransactionType,
)
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization


def _require(
    organization: Organization,
    actor,
    code: BusinessPermissionCode,
    equipment: Equipment,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=code,
        project=None,
        site=None,
        allow_any_scope=True,
        allow_site_parent=True,
        message="اجازه عملیات تجهیز را ندارید.",
    )
    if equipment.organization_id != organization.pk:
        raise PermissionDenied("تجهیز متعلق به این سازمان نیست.")


@transaction.atomic
def record_meter_reading(
    *,
    organization: Organization,
    actor,
    meter: EquipmentMeter,
    value: Decimal,
    observed_at: datetime,
    source_key: str,
    deployment: EquipmentAssignment | None = None,
    evidence_reference: str = "",
    correction_of: MeterReading | None = None,
    correction_reason: str = "",
) -> MeterReading:
    _require(
        organization,
        actor,
        BusinessPermissionCode.EQUIPMENT_METERS_CORRECT
        if correction_of
        else BusinessPermissionCode.EQUIPMENT_METERS_RECORD,
        meter.equipment,
    )
    if timezone.is_naive(observed_at):
        raise ValueError("زمان قرائت باید دارای منطقه زمانی باشد.")
    locked = (
        EquipmentMeter.objects.select_for_update()
        .select_related("equipment")
        .get(pk=meter.pk, organization=organization)
    )
    if MeterReading.objects.filter(
        organization=organization, source_key=source_key
    ).exists():
        existing = MeterReading.objects.get(
            organization=organization, source_key=source_key
        )
        if existing.meter_id == locked.pk and existing.value == value:
            return existing
        raise ValueError("کلید منبع قرائت تکراری است.")
    previous = (
        MeterReading.objects.select_for_update()
        .filter(meter=locked, finalized_at__isnull=False, correction_of__isnull=True)
        .order_by("-observed_at", "-created_at")
        .first()
    )
    if not correction_of and previous and value < previous.value:
        raise ValueError(
            "قرائت نهایی کنتور نمی‌تواند کاهش یابد؛ رویداد بازنشانی/اصلاح ثبت کنید."
        )
    reading = MeterReading(
        organization=organization,
        meter=locked,
        deployment=deployment,
        observed_at=observed_at,
        value=value,
        source_key=source_key,
        evidence_reference=evidence_reference,
        correction_of=correction_of,
        correction_reason=correction_reason,
        finalized_at=timezone.now(),
        created_by=actor,
    )
    reading.full_clean()
    reading.save()
    record_audit_event(
        action=AuditAction.EQUIPMENT_OPERATION_CORRECTED
        if correction_of
        else AuditAction.EQUIPMENT_OPERATION_RECORDED,
        entity_type="equipment_meter_reading",
        entity_id=reading.pk,
        organization=organization,
        actor=actor,
        metadata={"meter_id": str(locked.pk), "source_key": source_key},
    )
    return reading


@transaction.atomic
def record_usage(
    *,
    organization: Organization,
    actor,
    equipment: Equipment,
    started_at: datetime,
    ended_at: datetime,
    runtime_hours: Decimal,
    source_key: str,
    deployment: EquipmentAssignment | None = None,
    operator=None,
    evidence_reference: str = "",
) -> EquipmentUsageLog:
    _require(
        organization, actor, BusinessPermissionCode.EQUIPMENT_USAGE_RECORD, equipment
    )
    existing = EquipmentUsageLog.objects.filter(
        organization=organization, source_key=source_key
    ).first()
    if existing:
        return existing
    log = EquipmentUsageLog(
        organization=organization,
        equipment=equipment,
        deployment=deployment,
        operator=operator,
        started_at=started_at,
        ended_at=ended_at,
        runtime_hours=runtime_hours,
        source_key=source_key,
        evidence_reference=evidence_reference,
        created_by=actor,
    )
    log.full_clean()
    log.save()
    record_audit_event(
        action=AuditAction.EQUIPMENT_OPERATION_RECORDED,
        entity_type="equipment_usage",
        entity_id=log.pk,
        organization=organization,
        actor=actor,
        metadata={"equipment_id": str(equipment.pk), "source_key": source_key},
    )
    return log


@transaction.atomic
def record_fuel(
    *,
    organization: Organization,
    actor,
    equipment: Equipment,
    occurred_at: datetime,
    quantity: Decimal,
    unit: str,
    source_key: str,
    deployment: EquipmentAssignment | None = None,
    inventory_transaction: StockTransaction | None = None,
    evidence_reference: str = "",
) -> FuelLog:
    _require(
        organization, actor, BusinessPermissionCode.EQUIPMENT_FUEL_RECORD, equipment
    )
    existing = FuelLog.objects.filter(
        organization=organization, source_key=source_key
    ).first()
    if existing:
        return existing
    if inventory_transaction and (
        inventory_transaction.organization_id != organization.pk
        or inventory_transaction.status != StockTransactionStatus.POSTED
    ):
        raise ValueError("فقط تراکنش انبار نهایی‌شده همین سازمان قابل ارجاع است.")
    record = FuelLog(
        organization=organization,
        equipment=equipment,
        deployment=deployment,
        occurred_at=occurred_at,
        quantity=quantity,
        unit=unit,
        source_key=source_key,
        inventory_transaction=inventory_transaction,
        evidence_reference=evidence_reference,
        created_by=actor,
    )
    record.full_clean()
    record.save()
    record_audit_event(
        action=AuditAction.EQUIPMENT_OPERATION_RECORDED,
        entity_type="equipment_fuel",
        entity_id=record.pk,
        organization=organization,
        actor=actor,
        metadata={"equipment_id": str(equipment.pk), "source_key": source_key},
    )
    return record


@transaction.atomic
def link_spare_part(
    *,
    organization: Organization,
    actor,
    work_order: EquipmentWorkOrder,
    inventory_transaction: StockTransaction,
) -> MaintenanceSparePartReference:
    _require(
        organization,
        actor,
        BusinessPermissionCode.EQUIPMENT_SPARE_LINKS_MANAGE,
        work_order.equipment,
    )
    locked_order = (
        EquipmentWorkOrder.objects.select_for_update()
        .select_related("equipment")
        .get(pk=work_order.pk, organization=organization)
    )
    try:
        transaction_record = (
            StockTransaction.objects.select_for_update()
            .select_related("material", "unit_of_measure")
            .get(pk=inventory_transaction.pk, organization=organization)
        )
    except StockTransaction.DoesNotExist as exc:
        raise PermissionDenied("تراکنش انبار متعلق به این سازمان نیست.") from exc
    if (
        transaction_record.status != StockTransactionStatus.POSTED
        or transaction_record.transaction_type
        not in {StockTransactionType.ISSUE, StockTransactionType.REVERSAL}
    ):
        raise ValueError("فقط حواله خروج/برگشت نهایی‌شده قابل پیوند است.")
    try:
        reference = MaintenanceSparePartReference(
            organization=organization,
            work_order=locked_order,
            inventory_transaction=transaction_record,
            material=transaction_record.material,
            quantity_snapshot=transaction_record.quantity,
            unit_snapshot=transaction_record.unit_of_measure.code,
            created_by=actor,
        )
        reference.full_clean()
        reference.save()
        record_audit_event(
            action=AuditAction.EQUIPMENT_SPARE_PART_LINKED,
            entity_type="maintenance_spare_reference",
            entity_id=reference.pk,
            organization=organization,
            actor=actor,
            metadata={
                "work_order_id": str(locked_order.pk),
                "inventory_transaction_id": str(transaction_record.pk),
            },
        )
        return reference
    except (IntegrityError, ValidationError) as exc:
        if MaintenanceSparePartReference.objects.filter(
            work_order=locked_order,
            inventory_transaction=transaction_record,
        ).exists():
            raise ValueError(
                "این تراکنش انبار پیش‌تر به دستورکار پیوند شده است."
            ) from exc
        raise


@transaction.atomic
def create_maintenance_plan(
    *,
    organization: Organization,
    actor,
    equipment: Equipment,
    name: str,
    maintenance_type: str,
    interval_days: int | None = None,
    meter_interval: Decimal | None = None,
):
    from apps.equipment.p8_models import MaintenancePlan

    _require(
        organization,
        actor,
        BusinessPermissionCode.EQUIPMENT_MAINTENANCE_PLANS_MANAGE,
        equipment,
    )
    plan = MaintenancePlan(
        organization=organization,
        equipment=equipment,
        name=name,
        maintenance_type=maintenance_type,
        interval_days=interval_days,
        meter_interval=meter_interval,
        created_by=actor,
    )
    plan.full_clean()
    plan.save()
    record_audit_event(
        action=AuditAction.EQUIPMENT_OPERATION_RECORDED,
        entity_type="maintenance_plan",
        entity_id=plan.pk,
        organization=organization,
        actor=actor,
        metadata={"equipment_id": str(equipment.pk), "version": plan.version},
    )
    return plan


@transaction.atomic
def create_work_order(
    *,
    organization: Organization,
    actor,
    equipment: Equipment,
    number: str,
    summary: str,
    plan=None,
    deployment=None,
    scheduled_for=None,
):
    _require(
        organization,
        actor,
        BusinessPermissionCode.EQUIPMENT_WORK_ORDERS_MANAGE,
        equipment,
    )
    order = EquipmentWorkOrder(
        organization=organization,
        equipment=equipment,
        plan=plan,
        deployment=deployment,
        number=number,
        summary=summary,
        scheduled_for=scheduled_for,
        created_by=actor,
    )
    order.full_clean()
    order.save()
    record_audit_event(
        action=AuditAction.EQUIPMENT_OPERATION_RECORDED,
        entity_type="equipment_work_order",
        entity_id=order.pk,
        organization=organization,
        actor=actor,
        metadata={"equipment_id": str(equipment.pk)},
    )
    return order


@transaction.atomic
def transition_work_order(
    *,
    organization: Organization,
    actor,
    work_order: EquipmentWorkOrder,
    target_status: str,
    completion_notes: str = "",
):
    _require(
        organization,
        actor,
        BusinessPermissionCode.EQUIPMENT_WORK_ORDERS_COMPLETE
        if target_status == "completed"
        else BusinessPermissionCode.EQUIPMENT_WORK_ORDERS_MANAGE,
        work_order.equipment,
    )
    order = (
        EquipmentWorkOrder.objects.select_for_update()
        .select_related("equipment")
        .get(pk=work_order.pk, organization=organization)
    )
    allowed = {
        "draft": {"scheduled", "cancelled"},
        "scheduled": {"in_progress", "cancelled"},
        "in_progress": {"completed", "cancelled"},
    }
    if target_status not in allowed.get(order.status, set()):
        raise ValueError("گذار وضعیت دستورکار معتبر نیست.")
    previous = order.status
    order.status = target_status
    if target_status == "completed":
        order.completed_at = timezone.now()
        order.completion_notes = completion_notes.strip()
    order.full_clean()
    order.save()
    record_audit_event(
        action=AuditAction.EQUIPMENT_WORK_ORDER_TRANSITIONED,
        entity_type="equipment_work_order",
        entity_id=order.pk,
        organization=organization,
        actor=actor,
        metadata={"previous": previous, "current": target_status},
    )
    return order


@transaction.atomic
def record_operator_qualification(
    *,
    organization: Organization,
    actor,
    equipment: Equipment,
    employee,
    workforce_qualification,
    effective_from,
    effective_to=None,
    reason: str = "",
):
    _require(
        organization,
        actor,
        BusinessPermissionCode.EQUIPMENT_QUALIFICATIONS_MANAGE,
        equipment,
    )
    qualification = OperatorEquipmentQualification(
        organization=organization,
        equipment=equipment,
        employee=employee,
        workforce_qualification=workforce_qualification,
        effective_from=effective_from,
        effective_to=effective_to,
        reason=reason,
        created_by=actor,
    )
    qualification.full_clean()
    if not workforce_qualification.is_valid_on(effective_from):
        raise ValueError("صلاحیت منبع در تاریخ اثر معتبر نیست.")
    qualification.save()
    record_audit_event(
        action=AuditAction.EQUIPMENT_OPERATION_RECORDED,
        entity_type="operator_equipment_qualification",
        entity_id=qualification.pk,
        organization=organization,
        actor=actor,
        metadata={"equipment_id": str(equipment.pk), "employee_id": str(employee.pk)},
    )
    return qualification


@transaction.atomic
def record_downtime(
    *,
    organization: Organization,
    actor,
    equipment: Equipment,
    reason_code: str,
    started_at: datetime,
    deployment: EquipmentAssignment | None = None,
    evidence_reference: str = "",
    reason: str = "",
):
    _require(
        organization, actor, BusinessPermissionCode.EQUIPMENT_DOWNTIME_MANAGE, equipment
    )
    locked_equipment = Equipment.objects.select_for_update().get(
        pk=equipment.pk, organization=organization
    )
    if (
        DowntimeEvent.objects.select_for_update()
        .filter(
            organization=organization,
            equipment=locked_equipment,
            ended_at__isnull=True,
            cancelled_at__isnull=True,
        )
        .exists()
    ):
        raise ValueError("برای تجهیز یک توقف باز وجود دارد.")
    event = DowntimeEvent(
        organization=organization,
        equipment=locked_equipment,
        deployment=deployment,
        reason_code=reason_code.strip(),
        started_at=started_at,
        evidence_reference=evidence_reference,
        reason=reason,
        created_by=actor,
    )
    event.full_clean()
    event.save()
    record_audit_event(
        action=AuditAction.EQUIPMENT_OPERATION_RECORDED,
        entity_type="equipment_downtime",
        entity_id=event.pk,
        organization=organization,
        actor=actor,
        metadata={"equipment_id": str(equipment.pk), "reason_code": event.reason_code},
    )
    return event


@transaction.atomic
def close_downtime(
    *,
    organization: Organization,
    actor,
    event: DowntimeEvent,
    ended_at: datetime,
    reason: str = "",
):
    _require(
        organization,
        actor,
        BusinessPermissionCode.EQUIPMENT_DOWNTIME_MANAGE,
        event.equipment,
    )
    locked = (
        DowntimeEvent.objects.select_for_update()
        .select_related("equipment")
        .get(pk=event.pk, organization=organization)
    )
    if locked.ended_at or locked.cancelled_at:
        raise ValueError("توقف نهایی‌شده قابل ویرایش نیست.")
    if ended_at <= locked.started_at:
        raise ValueError("پایان توقف باید پس از شروع باشد.")
    locked.ended_at = ended_at
    locked.reason = reason.strip() or locked.reason
    locked.full_clean()
    locked.save()
    record_audit_event(
        action=AuditAction.EQUIPMENT_OPERATION_CORRECTED,
        entity_type="equipment_downtime",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"state": "closed"},
    )
    return locked


@transaction.atomic
def add_work_order_evidence(
    *,
    organization: Organization,
    actor,
    work_order: EquipmentWorkOrder,
    reference: str,
    result_notes: str = "",
):
    _require(
        organization,
        actor,
        BusinessPermissionCode.EQUIPMENT_WORK_ORDERS_MANAGE,
        work_order.equipment,
    )
    locked = (
        EquipmentWorkOrder.objects.select_for_update()
        .select_related("equipment")
        .get(pk=work_order.pk, organization=organization)
    )
    evidence = MaintenanceWorkOrderEvidence(
        organization=organization,
        work_order=locked,
        reference=reference,
        result_notes=result_notes,
        recorded_by=actor,
    )
    evidence.full_clean()
    evidence.save()
    record_audit_event(
        action=AuditAction.EQUIPMENT_OPERATION_RECORDED,
        entity_type="maintenance_work_order_evidence",
        entity_id=evidence.pk,
        organization=organization,
        actor=actor,
        metadata={"work_order_id": str(locked.pk)},
    )
    return evidence
