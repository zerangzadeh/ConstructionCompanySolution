from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.subledgers.models import (
    AgingRun,
    Obligation,
    ObligationDirection,
    SettlementAllocation,
    SettlementReversal,
    SubledgerReconciliationReview,
    SubledgerReconciliationRun,
    WriteOffDecisionKind,
    WriteOffProposal,
)
from apps.treasury.models import (
    TreasuryMovement,
    TreasuryMovementKind,
    TreasuryMovementStatus,
)

ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class ObligationSourceSnapshot:
    source_kind: str
    source_uuid: UUID
    source_version: int
    source_line_key: str
    source_status: str
    direction: str
    amount: Decimal
    currency: str
    recognized_on: date
    due_date: date | None
    party_id: UUID | None
    party_name: str
    party_tax_identifier: str
    project_id: UUID | None
    contract_id: UUID | None
    source_snapshot: dict[str, object]


SourceResolver = Callable[[Organization, UUID, int, str], ObligationSourceSnapshot]
_SOURCE_RESOLVERS: dict[str, SourceResolver] = {}
_UNRESOLVED_WRITE_OFF_PERMISSIONS = (
    BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_APPROVE,
    BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_REVERSE,
)


def register_source_resolver(source_kind: str, resolver: SourceResolver) -> None:
    """Register a code-owned exact source adapter; duplicate registration is invalid."""

    normalized = source_kind.strip()
    if not normalized or normalized in _SOURCE_RESOLVERS:
        raise ValidationError("منبع تعهد نامعتبر یا تکراری است.")
    _SOURCE_RESOLVERS[normalized] = resolver


def registered_source_kinds() -> tuple[str, ...]:
    return tuple(sorted(_SOURCE_RESOLVERS))


def obligation_queryset(*, organization: Organization, actor):
    """Return only obligations visible in the actor's active Tenant/object scope."""

    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_VIEW,
        message="اختیار مشاهده تعهدات AP/AR را ندارید.",
        allow_any_scope=True,
    )
    from apps.organizations.authorization import scope_queryset

    return scope_queryset(
        Obligation.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    )


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _required_text(value: str, *, message: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValidationError(message)
    return normalized


def _lock_organization(organization: Organization) -> Organization:
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    if not locked.is_active:
        raise PermissionDenied("Tenant غیرفعال است.")
    return locked


def _lock_membership(
    *, organization: Organization, membership: OrganizationMembership
) -> OrganizationMembership:
    locked = (
        OrganizationMembership.objects.select_for_update()
        .select_related("user")
        .get(pk=membership.pk)
    )
    if (
        locked.organization_id != organization.pk
        or locked.status != MembershipStatus.ACTIVE
        or not locked.user.is_active
    ):
        raise PermissionDenied("عضویت فعال همین Tenant الزامی است.")
    return locked


def _active_settlement_amount(
    *, obligation: Obligation | None = None, movement: TreasuryMovement | None = None
) -> Decimal:
    queryset = SettlementAllocation.objects.filter(
        organization_id=(obligation or movement).organization_id
    )
    if obligation is not None:
        queryset = queryset.filter(obligation=obligation)
    if movement is not None:
        queryset = queryset.filter(treasury_movement=movement)
    return (
        queryset.filter(reversal__isnull=True).aggregate(total=Sum("amount"))["total"]
        or ZERO
    )


def _approved_writeoff_amount(*, obligation: Obligation) -> Decimal:
    return (
        WriteOffProposal.objects.filter(
            obligation=obligation,
            decision__decision=WriteOffDecisionKind.APPROVED,
            decision__reversal__isnull=True,
        ).aggregate(total=Sum("amount"))["total"]
        or ZERO
    )


@transaction.atomic
def recognize_obligation(
    *,
    organization: Organization,
    actor,
    source_kind: str,
    source_uuid: UUID,
    source_version: int,
    source_line_key: str = "",
    idempotency_key: str,
) -> Obligation:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_OBLIGATIONS_RECOGNIZE,
        message="اختیار شناسایی تعهد AP/AR را ندارید.",
        allow_any_scope=True,
    )
    membership = _lock_membership(organization=organization, membership=membership)
    source_kind = _required_text(source_kind, message="نوع منبع تعهد الزامی است.")
    idempotency_key = _required_text(
        idempotency_key, message="کلید idempotency تعهد الزامی است."
    )
    resolver = _SOURCE_RESOLVERS.get(source_kind)
    if resolver is None:
        raise ValidationError(
            "منبع تعهد ثبت نشده است؛ تصمیم P3-S27-Q01 برای فعال‌سازی لازم است."
        )
    snapshot = resolver(organization, source_uuid, source_version, source_line_key)
    if (
        snapshot.source_kind != source_kind
        or snapshot.source_uuid != source_uuid
        or snapshot.source_version != source_version
        or snapshot.source_line_key != source_line_key
        or snapshot.direction not in ObligationDirection.values
        or snapshot.amount <= 0
        or snapshot.currency != "IRR"
        or not snapshot.party_name.strip()
    ):
        raise ValidationError("تصویر منبع تعهد با قرارداد ثبت‌شده هم‌خوان نیست.")

    payload = asdict(snapshot)
    payload_hash = _canonical_hash(payload)
    existing = Obligation.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise ValidationError(
                "کلید idempotency تعهد با محتوای متفاوت استفاده شده است."
            )
        return existing
    source_existing = Obligation.objects.filter(
        organization=organization,
        source_kind=source_kind,
        source_uuid=source_uuid,
        source_version=source_version,
        source_line_key=source_line_key,
        direction=snapshot.direction,
    ).first()
    if source_existing:
        if source_existing.payload_hash != payload_hash:
            raise ValidationError("هویت منبع تعهد با تصویر متفاوت قبلاً ثبت شده است.")
        return source_existing

    from apps.contracts.models import Contract
    from apps.parties.models import BusinessParty
    from apps.projects.models import Project

    project = (
        Project.objects.select_for_update().get(pk=snapshot.project_id)
        if snapshot.project_id
        else None
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_OBLIGATIONS_RECOGNIZE,
        message="دامنه پروژه برای شناسایی تعهد مجاز نیست.",
        project=project,
    )
    party = (
        BusinessParty.objects.select_for_update().get(pk=snapshot.party_id)
        if snapshot.party_id
        else None
    )
    contract = (
        Contract.objects.select_for_update().get(pk=snapshot.contract_id)
        if snapshot.contract_id
        else None
    )
    obligation = Obligation.objects.create(
        organization=organization,
        direction=snapshot.direction,
        source_kind=source_kind,
        source_uuid=source_uuid,
        source_version=source_version,
        source_line_key=source_line_key,
        source_status=snapshot.source_status,
        source_hash=_canonical_hash(snapshot.source_snapshot),
        source_snapshot=snapshot.source_snapshot,
        party=party,
        party_name_snapshot=snapshot.party_name.strip(),
        party_tax_identifier_snapshot=snapshot.party_tax_identifier.strip(),
        project=project,
        contract=contract,
        original_amount=snapshot.amount,
        recognized_on=snapshot.recognized_on,
        due_date=snapshot.due_date,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        recognized_by=membership,
    )
    record_audit_event(
        action=AuditAction.SUBLEDGER_OBLIGATION_RECOGNIZED,
        entity_type="subledgers.Obligation",
        entity_id=obligation.pk,
        organization=organization,
        actor=actor,
        metadata={"source_kind": source_kind, "source_uuid": str(source_uuid)},
    )
    return obligation


@transaction.atomic
def allocate_settlement(
    *,
    organization: Organization,
    actor,
    obligation: Obligation,
    movement: TreasuryMovement,
    amount: Decimal,
    effective_date: date,
    reason: str,
    idempotency_key: str,
) -> SettlementAllocation:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_SETTLEMENTS_ALLOCATE,
        message="اختیار تخصیص تسویه AP/AR را ندارید.",
        project=obligation.project,
    )
    membership = _lock_membership(organization=organization, membership=membership)
    obligation = Obligation.objects.select_for_update().get(pk=obligation.pk)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_SETTLEMENTS_ALLOCATE,
        message="دامنه پروژه برای تخصیص تسویه مجاز نیست.",
        project=obligation.project,
    )
    movement = TreasuryMovement.objects.select_for_update().get(pk=movement.pk)
    if (
        obligation.organization_id != organization.pk
        or movement.organization_id != organization.pk
    ):
        raise PermissionDenied("تعهد و حرکت خزانه‌داری باید متعلق به همین Tenant باشند.")
    expected_kind = (
        TreasuryMovementKind.RECEIPT
        if obligation.direction == ObligationDirection.RECEIVABLE
        else TreasuryMovementKind.DISBURSEMENT
    )
    if (
        movement.kind != expected_kind
        or movement.status != TreasuryMovementStatus.POSTED
        or hasattr(movement, "reversal_movement")
        or movement.reverses_id is not None
    ):
        raise ValidationError("حرکت خزانه‌داری قطعی و سازگار برای تسویه الزامی است.")
    if obligation.project_id and movement.project_id != obligation.project_id:
        raise ValidationError("پروژه حرکت خزانه‌داری با تعهد هم‌راستا نیست.")
    if obligation.party_id and movement.party_id != obligation.party_id:
        raise ValidationError("طرف حرکت خزانه‌داری با تعهد هم‌راستا نیست.")
    if amount <= 0:
        raise ValidationError("مبلغ تخصیص باید مثبت باشد.")
    reason = _required_text(reason, message="دلیل تخصیص الزامی است.")
    idempotency_key = _required_text(
        idempotency_key, message="کلید idempotency تخصیص الزامی است."
    )
    payload_hash = _canonical_hash(
        {
            "obligation": obligation.pk,
            "movement": movement.pk,
            "amount": amount,
            "effective_date": effective_date,
            "reason": reason,
        }
    )
    existing = SettlementAllocation.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise ValidationError(
                "کلید idempotency تخصیص با محتوای متفاوت استفاده شده است."
            )
        return existing
    obligation_used = _active_settlement_amount(
        obligation=obligation
    ) + _approved_writeoff_amount(obligation=obligation)
    movement_used = _active_settlement_amount(movement=movement)
    if obligation_used + amount > obligation.original_amount:
        raise ValidationError("مبلغ تخصیص از مانده تعهد بیشتر است.")
    if movement_used + amount > movement.amount:
        raise ValidationError("مبلغ تخصیص از ظرفیت حرکت خزانه‌داری بیشتر است.")
    allocation = SettlementAllocation.objects.create(
        organization=organization,
        obligation=obligation,
        treasury_movement=movement,
        amount=amount,
        effective_date=effective_date,
        reason=reason,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        created_by=membership,
    )
    record_audit_event(
        action=AuditAction.SUBLEDGER_SETTLEMENT_ALLOCATED,
        entity_type="subledgers.SettlementAllocation",
        entity_id=allocation.pk,
        organization=organization,
        actor=actor,
        metadata={"obligation": str(obligation.pk), "movement": str(movement.pk)},
    )
    return allocation


@transaction.atomic
def reverse_settlement(
    *,
    organization: Organization,
    actor,
    allocation: SettlementAllocation,
    effective_date: date,
    reason: str,
    idempotency_key: str,
) -> SettlementReversal:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_SETTLEMENTS_REVERSE,
        message="اختیار برگشت تخصیص AP/AR را ندارید.",
        project=allocation.obligation.project,
    )
    membership = _lock_membership(organization=organization, membership=membership)
    obligation = Obligation.objects.select_for_update().get(pk=allocation.obligation_id)
    allocation = (
        SettlementAllocation.objects.select_for_update()
        .select_related("obligation")
        .get(pk=allocation.pk)
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_SETTLEMENTS_REVERSE,
        message="دامنه پروژه برای برگشت تخصیص مجاز نیست.",
        project=obligation.project,
    )
    if allocation.organization_id != organization.pk:
        raise PermissionDenied("تخصیص متعلق به Tenant دیگری است.")
    reason = _required_text(reason, message="دلیل برگشت الزامی است.")
    idempotency_key = _required_text(
        idempotency_key, message="کلید idempotency برگشت الزامی است."
    )
    payload_hash = _canonical_hash(
        {
            "allocation": allocation.pk,
            "effective_date": effective_date,
            "reason": reason,
        }
    )
    existing = SettlementReversal.objects.filter(allocation=allocation).first()
    if existing:
        if (
            existing.idempotency_key != idempotency_key
            or existing.payload_hash != payload_hash
        ):
            raise ValidationError("تخصیص قبلاً با رخداد دیگری برگشت شده است.")
        return existing
    reversal = SettlementReversal.objects.create(
        organization=organization,
        allocation=allocation,
        effective_date=effective_date,
        reason=reason,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        reversed_by=membership,
    )
    record_audit_event(
        action=AuditAction.SUBLEDGER_SETTLEMENT_REVERSED,
        entity_type="subledgers.SettlementAllocation",
        entity_id=allocation.pk,
        organization=organization,
        actor=actor,
        metadata={"reversal": str(reversal.pk), "reason": reversal.reason},
    )
    return reversal


@transaction.atomic
def propose_write_off(
    *,
    organization: Organization,
    actor,
    obligation: Obligation,
    amount: Decimal,
    effective_date: date,
    reason: str,
    idempotency_key: str,
) -> WriteOffProposal:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_PROPOSE,
        message="اختیار پیشنهاد سوخت AP/AR را ندارید.",
        project=obligation.project,
    )
    membership = _lock_membership(organization=organization, membership=membership)
    obligation = Obligation.objects.select_for_update().get(pk=obligation.pk)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_WRITEOFFS_PROPOSE,
        message="دامنه پروژه برای پیشنهاد سوخت مجاز نیست.",
        project=obligation.project,
    )
    if obligation.organization_id != organization.pk or amount <= 0:
        raise ValidationError("تعهد یا مبلغ پیشنهاد سوخت نامعتبر است.")
    reason = _required_text(reason, message="دلیل پیشنهاد سوخت الزامی است.")
    idempotency_key = _required_text(
        idempotency_key, message="کلید idempotency پیشنهاد سوخت الزامی است."
    )
    payload_hash = _canonical_hash(
        {
            "obligation": obligation.pk,
            "amount": amount,
            "date": effective_date,
            "reason": reason,
        }
    )
    existing = WriteOffProposal.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.payload_hash != payload_hash:
            raise ValidationError(
                "کلید idempotency سوخت با محتوای متفاوت استفاده شده است."
            )
        return existing
    remaining = (
        obligation.original_amount
        - _active_settlement_amount(obligation=obligation)
        - _approved_writeoff_amount(obligation=obligation)
    )
    if amount > remaining:
        raise ValidationError("مبلغ پیشنهاد سوخت از مانده تعهد بیشتر است.")
    proposal = WriteOffProposal.objects.create(
        organization=organization,
        obligation=obligation,
        amount=amount,
        effective_date=effective_date,
        reason=reason,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        proposed_by=membership,
    )
    record_audit_event(
        action=AuditAction.SUBLEDGER_WRITEOFF_PROPOSED,
        entity_type="subledgers.WriteOffProposal",
        entity_id=proposal.pk,
        organization=organization,
        actor=actor,
        metadata={"obligation": str(obligation.pk)},
    )
    return proposal


def approve_write_off(*args: object, **kwargs: object) -> None:
    del args, kwargs
    assert _UNRESOLVED_WRITE_OFF_PERMISSIONS
    raise ValidationError(
        "اختیار و سیاست سوخت هنوز تصویب نشده است؛ تصمیم P3-S27-Q03 لازم است."
    )


def reverse_write_off(*args: object, **kwargs: object) -> None:
    del args, kwargs
    raise ValidationError(
        "اختیار و سیاست برگشت سوخت هنوز تصویب نشده است؛ تصمیم P3-S27-Q03 لازم است."
    )


def _amounts_as_of(obligation: Obligation, as_of_date: date) -> tuple[Decimal, Decimal]:
    settled = ZERO
    allocations = obligation.settlement_allocations.filter(
        effective_date__lte=as_of_date
    ).select_related("reversal")
    for allocation in allocations:
        reversal = getattr(allocation, "reversal", None)
        if reversal is None or reversal.effective_date > as_of_date:
            settled += allocation.amount
    written_off = ZERO
    proposals = obligation.write_off_proposals.filter(
        effective_date__lte=as_of_date,
        decision__decision=WriteOffDecisionKind.APPROVED,
    ).select_related("decision__reversal")
    for proposal in proposals:
        reversal = getattr(proposal.decision, "reversal", None)
        if reversal is None or reversal.effective_date > as_of_date:
            written_off += proposal.amount
    return settled, written_off


@transaction.atomic
def run_aging(
    *,
    organization: Organization,
    actor,
    direction: str,
    as_of_date: date,
    idempotency_key: str,
) -> AgingRun:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_AGING_RUN,
        message="اختیار اجرای aging AP/AR را ندارید.",
    )
    membership = _lock_membership(organization=organization, membership=membership)
    if direction not in ObligationDirection.values:
        raise ValidationError("جهت aging نامعتبر است.")
    idempotency_key = _required_text(
        idempotency_key, message="کلید idempotency aging الزامی است."
    )
    existing = AgingRun.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    from apps.organizations.authorization import scope_queryset

    obligations = list(
        scope_queryset(
            Obligation.objects.select_for_update().filter(
                organization=organization,
                direction=direction,
                recognized_on__lte=as_of_date,
            ),
            membership=membership,
            project_lookup="project_id",
        ).order_by("recognized_on", "pk")
    )
    items: list[dict[str, object]] = []
    original_total = settled_total = written_off_total = outstanding_total = ZERO
    for obligation in obligations:
        settled, written_off = _amounts_as_of(obligation, as_of_date)
        outstanding = obligation.original_amount - settled - written_off
        item = {
            "obligation_id": str(obligation.pk),
            "original_amount": str(obligation.original_amount),
            "settled_amount": str(settled),
            "written_off_amount": str(written_off),
            "outstanding_amount": str(outstanding),
            "due_date": obligation.due_date.isoformat()
            if obligation.due_date
            else None,
            "days_past_due": (
                max((as_of_date - obligation.due_date).days, 0)
                if obligation.due_date
                else None
            ),
            "undated": obligation.due_date is None,
        }
        items.append(item)
        original_total += obligation.original_amount
        settled_total += settled
        written_off_total += written_off
        outstanding_total += outstanding
    payload = {
        "direction": direction,
        "as_of_date": as_of_date,
        "items": items,
        "original_total": original_total,
        "settled_total": settled_total,
        "written_off_total": written_off_total,
        "outstanding_total": outstanding_total,
    }
    evidence_hash = _canonical_hash(payload)
    if existing:
        if existing.evidence_hash != evidence_hash:
            raise ValidationError(
                "کلید idempotency aging با نتیجه متفاوت استفاده شده است."
            )
        return existing
    run = AgingRun.objects.create(
        organization=organization,
        direction=direction,
        as_of_date=as_of_date,
        obligation_count=len(items),
        original_total=original_total,
        settled_total=settled_total,
        written_off_total=written_off_total,
        outstanding_total=outstanding_total,
        item_snapshots=items,
        evidence_hash=evidence_hash,
        idempotency_key=idempotency_key,
        created_by=membership,
    )
    record_audit_event(
        action=AuditAction.SUBLEDGER_AGING_RETAINED,
        entity_type="subledgers.AgingRun",
        entity_id=run.pk,
        organization=organization,
        actor=actor,
        metadata={"direction": direction, "as_of_date": as_of_date.isoformat()},
    )
    return run


@transaction.atomic
def run_subledger_reconciliation(
    *,
    organization: Organization,
    actor,
    direction: str,
    as_of_date: date,
    idempotency_key: str,
) -> SubledgerReconciliationRun:
    organization = _lock_organization(organization)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_RECONCILIATIONS_RUN,
        message="اختیار اجرای تطبیق AP/AR را ندارید.",
    )
    membership = _lock_membership(organization=organization, membership=membership)
    idempotency_key = _required_text(
        idempotency_key, message="کلید idempotency تطبیق الزامی است."
    )
    existing = SubledgerReconciliationRun.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    from apps.organizations.authorization import scope_queryset

    obligations = list(
        scope_queryset(
            Obligation.objects.select_for_update().filter(
                organization=organization,
                direction=direction,
                recognized_on__lte=as_of_date,
            ),
            membership=membership,
            project_lookup="project_id",
        ).order_by("pk")
    )
    outstanding_total = ZERO
    journal_ids: list[str] = []
    exceptions: list[dict[str, str]] = []
    for obligation in obligations:
        settled, written_off = _amounts_as_of(obligation, as_of_date)
        outstanding_total += obligation.original_amount - settled - written_off
        if obligation.recognition_journal_id:
            journal_ids.append(str(obligation.recognition_journal_id))
            exceptions.append(
                {
                    "obligation_id": str(obligation.pk),
                    "code": "CONTROL_MAPPING_NOT_APPROVED",
                }
            )
        else:
            exceptions.append(
                {
                    "obligation_id": str(obligation.pk),
                    "code": "MISSING_RECOGNITION_JOURNAL",
                }
            )
    linked_gl_total = ZERO
    payload = {
        "direction": direction,
        "as_of_date": as_of_date,
        "obligations": [str(item.pk) for item in obligations],
        "journals": journal_ids,
        "subledger_total": outstanding_total,
        "linked_gl_total": linked_gl_total,
        "exceptions": exceptions,
    }
    evidence_hash = _canonical_hash(payload)
    if existing:
        if existing.evidence_hash != evidence_hash:
            raise ValidationError(
                "کلید idempotency تطبیق با نتیجه متفاوت استفاده شده است."
            )
        return existing
    run = SubledgerReconciliationRun.objects.create(
        organization=organization,
        direction=direction,
        as_of_date=as_of_date,
        subledger_outstanding_total=outstanding_total,
        linked_gl_total=linked_gl_total,
        difference=outstanding_total - linked_gl_total,
        exception_snapshots=exceptions,
        obligation_ids=[str(item.pk) for item in obligations],
        journal_ids=journal_ids,
        evidence_hash=evidence_hash,
        idempotency_key=idempotency_key,
        created_by=membership,
    )
    record_audit_event(
        action=AuditAction.SUBLEDGER_RECONCILIATION_RETAINED,
        entity_type="subledgers.SubledgerReconciliationRun",
        entity_id=run.pk,
        organization=organization,
        actor=actor,
        metadata={"direction": direction, "as_of_date": as_of_date.isoformat()},
    )
    return run


def _subledger_reconciliation_review_hash(run: SubledgerReconciliationRun) -> str:
    return _canonical_hash(
        {
            "run": str(run.pk),
            "direction": run.direction,
            "as_of_date": run.as_of_date,
            "subledger_outstanding_total": run.subledger_outstanding_total,
            "linked_gl_total": run.linked_gl_total,
            "difference": run.difference,
            "exceptions": run.exception_snapshots,
            "obligations": run.obligation_ids,
            "journals": run.journal_ids,
            "evidence_hash": run.evidence_hash,
            "created_by": str(run.created_by_id),
        }
    )


@transaction.atomic
def review_subledger_reconciliation(
    *,
    organization: Organization,
    actor,
    run: SubledgerReconciliationRun,
    reason: str,
) -> SubledgerReconciliationReview:
    """Independently sign one immutable retained AP/AR reconciliation run."""

    organization = _lock_organization(organization)
    reviewer = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_RECONCILIATIONS_REVIEW,
        message="اختیار بررسی مستقل تطبیق AP/AR را ندارید.",
    )
    reviewer = _lock_membership(organization=organization, membership=reviewer)
    run = (
        SubledgerReconciliationRun.objects.select_for_update()
        .select_related("created_by")
        .get(pk=run.pk)
    )
    if run.organization_id != organization.pk:
        raise PermissionDenied("اجرای تطبیق متعلق به Tenant دیگری است.")
    if reviewer.pk == run.created_by_id:
        raise PermissionDenied("اجراکننده تطبیق نمی‌تواند همان اجرا را بررسی کند.")
    reason = _required_text(reason, message="دلیل بررسی تطبیق الزامی است.")
    signed_hash = _subledger_reconciliation_review_hash(run)
    existing = SubledgerReconciliationReview.objects.filter(run=run).first()
    if existing:
        if (
            existing.reviewed_by_id == reviewer.pk
            and existing.reason == reason
            and existing.run_evidence_hash == run.evidence_hash
            and existing.signed_evidence_hash == signed_hash
        ):
            return existing
        raise ValidationError("اجرای تطبیق قبلاً بررسی شده است.")
    review = SubledgerReconciliationReview.objects.create(
        organization=organization,
        run=run,
        reason=reason,
        run_evidence_hash=run.evidence_hash,
        signed_evidence_hash=signed_hash,
        reviewed_by=reviewer,
    )
    record_audit_event(
        action=AuditAction.SUBLEDGER_RECONCILIATION_REVIEWED,
        entity_type="subledgers.SubledgerReconciliationReview",
        entity_id=review.pk,
        organization=organization,
        actor=actor,
        metadata={
            "run": str(run.pk),
            "reason": reason,
            "reviewed_by": str(reviewer.pk),
            "run_evidence_hash": run.evidence_hash,
            "signed_evidence_hash": signed_hash,
        },
    )
    return review


def verify_subledger_reconciliation_review(
    *, organization: Organization, run: SubledgerReconciliationRun
) -> SubledgerReconciliationReview:
    run = SubledgerReconciliationRun.objects.get(
        pk=run.pk, organization=organization
    )
    try:
        review = run.review
    except SubledgerReconciliationReview.DoesNotExist as exc:
        raise ValidationError("اجرای تطبیق فاقد بررسی مستقل است.") from exc
    if (
        review.run_evidence_hash != run.evidence_hash
        or review.signed_evidence_hash != _subledger_reconciliation_review_hash(run)
    ):
        raise ValidationError("بررسی مستقل با شواهد نگهداری‌شده سازگار نیست.")
    return review
