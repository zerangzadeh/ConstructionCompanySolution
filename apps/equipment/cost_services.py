"""P8-S24 Equipment cost proposals. No consumer fact is created here."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.equipment.p8_models import (
    CostAllocationStatus,
    CostPolicyStatus,
    EquipmentCostAllocation,
    EquipmentCostPolicyVersion,
    EquipmentCostRate,
    EquipmentCostSourceEnvelope,
    EquipmentUsageLog,
    ProposalStatus,
)
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization


def _require(*, organization, actor, permission, project=None):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        allow_any_scope=project is None,
        allow_site_parent=True,
        message="اجازه عملیات هزینه تجهیز را ندارید.",
    )


@transaction.atomic
def create_cost_policy(
    *,
    organization: Organization,
    actor,
    code: str,
    version: int,
    effective_from: date,
    monetary_policy_code: str,
    monetary_policy_version: str,
    decimal_places: int = 0,
    effective_to: date | None = None,
) -> EquipmentCostPolicyVersion:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EQUIPMENT_COST_POLICY_MANAGE,
    )
    policy = EquipmentCostPolicyVersion(
        organization=organization,
        code=code,
        version=version,
        effective_from=effective_from,
        effective_to=effective_to,
        monetary_policy_code=monetary_policy_code,
        monetary_policy_version=monetary_policy_version,
        decimal_places=decimal_places,
        prepared_by=actor,
    )
    policy.full_clean()
    policy.save()
    return policy


@transaction.atomic
def review_cost_policy(
    *, organization: Organization, actor, policy: EquipmentCostPolicyVersion
) -> EquipmentCostPolicyVersion:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EQUIPMENT_COST_POLICY_PUBLISH,
    )
    locked = EquipmentCostPolicyVersion.objects.select_for_update().get(
        pk=policy.pk, organization=organization
    )
    if locked.status != CostPolicyStatus.DRAFT or locked.prepared_by_id == actor.pk:
        raise ValueError("بررسی مستقل فقط برای پیش‌نویس مجاز است.")
    locked.status = CostPolicyStatus.REVIEWED
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    _audit_policy(locked, actor)
    return locked


@transaction.atomic
def publish_cost_policy(
    *, organization: Organization, actor, policy: EquipmentCostPolicyVersion
) -> EquipmentCostPolicyVersion:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EQUIPMENT_COST_POLICY_PUBLISH,
    )
    locked = EquipmentCostPolicyVersion.objects.select_for_update().get(
        pk=policy.pk, organization=organization
    )
    if locked.status != CostPolicyStatus.REVIEWED or not locked.rates.exists():
        raise ValueError("فقط سیاست بررسی‌شده دارای نرخ قابل انتشار است.")
    if locked.prepared_by_id == actor.pk:
        raise ValueError("تهیه‌کننده نمی‌تواند سیاست را منتشر کند.")
    EquipmentCostPolicyVersion.objects.filter(
        organization=organization, code=locked.code, status=CostPolicyStatus.PUBLISHED
    ).exclude(pk=locked.pk).update(status=CostPolicyStatus.SUPERSEDED)
    locked.status = CostPolicyStatus.PUBLISHED
    locked.published_by = actor
    locked.published_at = timezone.now()
    locked.save(update_fields=["status", "published_by", "published_at", "updated_at"])
    _audit_policy(locked, actor)
    return locked


def _audit_policy(policy, actor):
    record_audit_event(
        action=AuditAction.EQUIPMENT_COST_POLICY_TRANSITIONED,
        entity_type="equipment_cost_policy",
        entity_id=policy.pk,
        organization=policy.organization,
        actor=actor,
        metadata={
            "code": policy.code,
            "version": policy.version,
            "status": policy.status,
        },
    )


@transaction.atomic
def create_cost_rate(
    *,
    organization: Organization,
    actor,
    policy: EquipmentCostPolicyVersion,
    rate_amount: Decimal,
    component_snapshot: dict[str, str | int | Decimal],
    effective_from: date,
    equipment=None,
    equipment_category: str = "",
    effective_to: date | None = None,
    measure_unit: str = "hour",
) -> EquipmentCostRate:
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EQUIPMENT_COST_POLICY_MANAGE,
    )
    locked = EquipmentCostPolicyVersion.objects.select_for_update().get(
        pk=policy.pk, organization=organization
    )
    if locked.status not in {CostPolicyStatus.DRAFT, CostPolicyStatus.REVIEWED}:
        raise ValueError("نرخ سیاست منتشرشده قابل تغییر نیست.")
    overlapping = EquipmentCostRate.objects.filter(
        organization=organization,
        equipment=equipment,
        equipment_category=equipment_category,
        effective_from__lte=effective_to or date.max,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from))
    if overlapping.exists():
        raise ValueError("بازه نرخ با نرخ موجود همان تجهیز/طبقه هم‌پوشانی دارد.")
    rate = EquipmentCostRate(
        organization=organization,
        policy=locked,
        equipment=equipment,
        equipment_category=equipment_category,
        measure_unit=measure_unit,
        rate_amount=rate_amount,
        component_snapshot={
            key: str(value) for key, value in component_snapshot.items()
        },
        effective_from=effective_from,
        effective_to=effective_to,
        prepared_by=actor,
    )
    rate.full_clean()
    rate.save()
    return rate


def _rate_for_usage(organization, usage):
    day = usage.started_at.date()
    rates = (
        EquipmentCostRate.objects.select_related("policy")
        .filter(
            organization=organization,
            policy__status=CostPolicyStatus.PUBLISHED,
            effective_from__lte=day,
            policy__effective_from__lte=day,
        )
        .filter(equipment=usage.equipment)
        .filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=day),
            Q(policy__effective_to__isnull=True) | Q(policy__effective_to__gte=day),
        )
    )
    rate = rates.order_by("-policy__version", "-effective_from").first()
    if rate is None:
        rate = (
            EquipmentCostRate.objects.select_related("policy")
            .filter(
                organization=organization,
                equipment__isnull=True,
                equipment_category=usage.equipment.category,
                policy__status=CostPolicyStatus.PUBLISHED,
                effective_from__lte=day,
            )
            .filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=day),
                Q(policy__effective_to__isnull=True) | Q(policy__effective_to__gte=day),
            )
            .order_by("-policy__version", "-effective_from")
            .first()
        )
    return rate


@transaction.atomic
def prepare_cost_allocation(
    *,
    organization: Organization,
    actor,
    usage: EquipmentUsageLog,
    source_key: str,
    wbs_node=None,
    activity=None,
    cost_center=None,
) -> EquipmentCostAllocation:
    try:
        locked_usage = EquipmentUsageLog.objects.select_for_update().get(
            pk=usage.pk, organization=organization
        )
    except EquipmentUsageLog.DoesNotExist as exc:
        raise PermissionDenied("کارکرد متعلق به این سازمان نیست.") from exc
    if locked_usage.deployment_id is None:
        raise ValueError("تخصیص هزینه فقط برای کارکرد دارای استقرار بررسی‌شده مجاز است.")
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_PREPARE,
        project=locked_usage.deployment.project,
    )
    existing = EquipmentCostAllocation.objects.filter(
        organization=organization, source_key=source_key
    ).first()
    rate = _rate_for_usage(organization, locked_usage)
    if rate is None:
        raise ValueError("نرخ منتشرشده مؤثر برای کارکرد یافت نشد.")
    quantum = Decimal(1).scaleb(-rate.policy.decimal_places)
    amount = (locked_usage.runtime_hours * rate.rate_amount).quantize(
        quantum, rounding=ROUND_HALF_UP
    )
    if existing:
        if (
            existing.usage_id == locked_usage.pk
            and existing.rate_id == rate.pk
            and existing.amount == amount
            and existing.wbs_node_id == getattr(wbs_node, "pk", None)
            and existing.activity_id == getattr(activity, "pk", None)
            and existing.cost_center_id == getattr(cost_center, "pk", None)
        ):
            return existing
        raise ValueError("کلید رخداد تخصیص با محتوای متفاوت تکرار شده است.")
    allocation = EquipmentCostAllocation(
        organization=organization,
        usage=locked_usage,
        rate=rate,
        project=locked_usage.deployment.project,
        site=locked_usage.deployment.site,
        wbs_node=wbs_node,
        activity=activity,
        cost_center=cost_center,
        measure=locked_usage.runtime_hours,
        rate_snapshot=rate.rate_amount,
        amount=amount,
        source_key=source_key,
        prepared_by=actor,
    )
    allocation.full_clean()
    allocation.save()
    return allocation


@transaction.atomic
def finalize_cost_allocation(
    *, organization: Organization, actor, allocation: EquipmentCostAllocation
) -> EquipmentCostAllocation:
    locked = (
        EquipmentCostAllocation.objects.select_for_update()
        .select_related("project")
        .get(pk=allocation.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_REVIEW,
        project=locked.project,
    )
    if locked.status != CostAllocationStatus.DRAFT or locked.prepared_by_id == actor.pk:
        raise ValueError("نهایی‌سازی مستقل فقط برای پیش‌نویس مجاز است.")
    locked.status = CostAllocationStatus.FINALIZED
    locked.reviewed_by = actor
    locked.finalized_at = timezone.now()
    locked.save(update_fields=["status", "reviewed_by", "finalized_at", "updated_at"])
    _audit_allocation(locked, actor)
    return locked


@transaction.atomic
def reverse_cost_allocation(
    *,
    organization: Organization,
    actor,
    allocation: EquipmentCostAllocation,
    reason: str,
    reversal_source_key: str | None = None,
) -> EquipmentCostAllocation:
    locked = (
        EquipmentCostAllocation.objects.select_for_update()
        .select_related("project")
        .get(pk=allocation.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EQUIPMENT_COST_ALLOCATION_REVERSE,
        project=locked.project,
    )
    reversal_key = reversal_source_key or f"reverse:{locked.source_key}"
    existing = EquipmentCostAllocation.objects.filter(
        organization=organization, source_key=reversal_key
    ).first()
    if existing:
        if existing.correction_of_id == locked.pk and existing.amount == -locked.amount:
            return existing
        raise ValueError("کلید برگشت تخصیص با محتوای متفاوت تکرار شده است.")
    if (
        locked.status != CostAllocationStatus.FINALIZED
        or locked.reviewed_by_id == actor.pk
        or not reason.strip()
    ):
        raise ValueError("برگشت مستقل تخصیص نهایی همراه علت الزامی است.")
    reversal = EquipmentCostAllocation(
        organization=organization,
        usage=locked.usage,
        rate=locked.rate,
        project=locked.project,
        site=locked.site,
        wbs_node=locked.wbs_node,
        activity=locked.activity,
        cost_center=locked.cost_center,
        measure=locked.measure,
        rate_snapshot=-locked.rate_snapshot,
        amount=-locked.amount,
        status=CostAllocationStatus.FINALIZED,
        source_key=reversal_key,
        correction_of=locked,
        reason=reason.strip(),
        prepared_by=actor,
        reviewed_by=actor,
        finalized_at=timezone.now(),
    )
    reversal.full_clean()
    reversal.save()
    locked.status = CostAllocationStatus.REVERSED
    locked.reversed_by = actor
    locked.reversed_at = timezone.now()
    locked.reason = reason.strip()
    locked.save(
        update_fields=["status", "reversed_by", "reversed_at", "reason", "updated_at"]
    )
    _audit_allocation(reversal, actor)
    return reversal


def _audit_allocation(allocation, actor):
    record_audit_event(
        action=AuditAction.EQUIPMENT_COST_ALLOCATION_TRANSITIONED,
        entity_type="equipment_cost_allocation",
        entity_id=allocation.pk,
        organization=allocation.organization,
        actor=actor,
        metadata={
            "source_key": allocation.source_key,
            "status": allocation.status,
            "amount": str(allocation.amount),
        },
    )


@transaction.atomic
def prepare_cost_handoff(
    *,
    organization: Organization,
    actor,
    allocation: EquipmentCostAllocation,
    occurrence_key: str,
) -> EquipmentCostSourceEnvelope:
    locked = (
        EquipmentCostAllocation.objects.select_for_update()
        .select_related("project")
        .get(pk=allocation.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EQUIPMENT_COST_HANDOFF_PREPARE,
        project=locked.project,
    )
    if locked.status != CostAllocationStatus.FINALIZED:
        raise ValueError("فقط تخصیص نهایی قابل پیشنهاد است.")
    duplicate_source = EquipmentCostSourceEnvelope.objects.filter(
        organization=organization,
        consumer="project_cost",
        allocation=locked,
    ).first()
    if duplicate_source and duplicate_source.occurrence_key != occurrence_key:
        raise ValueError(
            "یک تخصیص نهایی نمی‌تواند دوباره به همان مصرف‌کننده پیشنهاد شود."
        )
    envelope = EquipmentCostSourceEnvelope.objects.filter(
        organization=organization,
        consumer="project_cost",
        occurrence_key=occurrence_key,
    ).first()
    if envelope:
        if (
            envelope.allocation_id != locked.pk
            or envelope.source_amount != locked.amount
        ):
            raise ValueError("کلید پیشنهاد با محتوای متفاوت تکرار شده است.")
        return envelope
    envelope = EquipmentCostSourceEnvelope(
        organization=organization,
        consumer="project_cost",
        occurrence_key=occurrence_key,
        allocation=locked,
        source_amount=locked.amount,
        prepared_by=actor,
    )
    envelope.full_clean()
    envelope.save()
    return envelope


@transaction.atomic
def review_cost_handoff(
    *, organization: Organization, actor, envelope: EquipmentCostSourceEnvelope
) -> EquipmentCostSourceEnvelope:
    locked = (
        EquipmentCostSourceEnvelope.objects.select_for_update()
        .select_related("allocation__project")
        .get(pk=envelope.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EQUIPMENT_COST_HANDOFF_REVIEW,
        project=locked.allocation.project,
    )
    if locked.status != ProposalStatus.PREPARED or locked.prepared_by_id == actor.pk:
        raise ValueError("بررسی مستقل فقط برای پیشنهاد تهیه‌شده مجاز است.")
    locked.status = ProposalStatus.REVIEWED
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    record_audit_event(
        action=AuditAction.EQUIPMENT_COST_HANDOFF_TRANSITIONED,
        entity_type="equipment_cost_handoff",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"occurrence_key": locked.occurrence_key, "status": locked.status},
    )
    return locked


@transaction.atomic
def reconcile_cost_handoff(
    *,
    organization: Organization,
    actor,
    envelope: EquipmentCostSourceEnvelope,
    consumer_reference: str,
    reconciliation_note: str = "",
) -> EquipmentCostSourceEnvelope:
    locked = (
        EquipmentCostSourceEnvelope.objects.select_for_update()
        .select_related("allocation__project")
        .get(pk=envelope.pk, organization=organization)
    )
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.EQUIPMENT_COST_HANDOFF_RECONCILE,
        project=locked.allocation.project,
    )
    if (
        locked.status
        not in {
            ProposalStatus.REVIEWED,
            ProposalStatus.ACKNOWLEDGED,
            ProposalStatus.REJECTED,
        }
        or not consumer_reference.strip()
    ):
        raise ValueError(
            "تطبیق فقط برای پیشنهاد بررسی‌شده و با مرجع مصرف‌کننده مجاز است."
        )
    locked.status = ProposalStatus.RECONCILED
    locked.consumer_reference = consumer_reference.strip()
    locked.reconciliation_note = reconciliation_note.strip()
    locked.save(
        update_fields=[
            "status",
            "consumer_reference",
            "reconciliation_note",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.EQUIPMENT_COST_HANDOFF_TRANSITIONED,
        entity_type="equipment_cost_handoff",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "occurrence_key": locked.occurrence_key,
            "status": locked.status,
            "consumer_reference": locked.consumer_reference,
        },
    )
    return locked
