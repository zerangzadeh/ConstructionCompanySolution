from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

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
    InvoiceMatchStatus,
    MatchDiscrepancy,
    MatchDiscrepancyCode,
    MatchTolerancePolicy,
    Obligation,
    ObligationDirection,
    SettlementAllocation,
    SettlementReversal,
    SubledgerReconciliationAccountSlice,
    SubledgerReconciliationJournalLineEvidence,
    SubledgerReconciliationObligationEvidence,
    SubledgerReconciliationReview,
    SubledgerReconciliationRun,
    SubledgerReconciliationRunProvenance,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierInvoiceLineKind,
    SupplierInvoiceMatch,
    SupplierInvoiceMatchLine,
    SupplierInvoiceStatus,
    SupplierInvoiceVersion,
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

    from apps.accounting.services import resolve_control_account_mapping

    control_mapping = resolve_control_account_mapping(
        organization=organization,
        source_kind=source_kind,
        direction=snapshot.direction,
        effective_on=snapshot.recognized_on,
    )

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
        control_account=control_mapping.control_account,
        control_account_mapping=control_mapping,
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


def resolve_pinned_control_account_for_posting(
    *, organization: Organization, obligation: Obligation
):
    """Return the one historical control-account pin that an AP/AR post may use."""

    obligation = Obligation.objects.select_related(
        "control_account", "control_account_mapping"
    ).get(pk=obligation.pk)
    if obligation.organization_id != organization.pk:
        raise PermissionDenied("تعهد متعلق به Tenant دیگری است.")
    if not obligation.control_account_id or not obligation.control_account_mapping_id:
        raise ValidationError("تعهد فاقد شواهد نگاشت حساب کنترل تأییدشده است.")
    mapping = obligation.control_account_mapping
    if (
        mapping.organization_id != organization.pk
        or mapping.control_account_id != obligation.control_account_id
        or mapping.source_kind != obligation.source_kind
        or mapping.direction != obligation.direction
    ):
        raise ValidationError("شواهد پین حساب کنترل تعهد معتبر نیست.")
    return obligation.control_account


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
    from apps.accounting.models import JournalLine

    grouped: dict[object, list[tuple[Obligation, Decimal]]] = {}
    journal_ids: list[str] = []
    exceptions: list[dict[str, str]] = []
    for obligation in obligations:
        settled, written_off = _amounts_as_of(obligation, as_of_date)
        outstanding = obligation.original_amount - settled - written_off
        if (
            not obligation.control_account_id
            or not obligation.control_account_mapping_id
        ):
            exceptions.append(
                {
                    "obligation_id": str(obligation.pk),
                    "code": "CONTROL_MAPPING_NOT_APPROVED",
                }
            )
            continue
        grouped.setdefault(obligation.control_account, []).append(
            (obligation, outstanding)
        )

    slice_payloads: list[dict[str, object]] = []
    outstanding_total = linked_gl_total = ZERO
    for control_account, members in grouped.items():
        slice_outstanding = sum((item[1] for item in members), ZERO)
        slice_gl = ZERO
        line_evidence: list[tuple[Obligation, object]] = []
        for obligation, _outstanding in members:
            if not obligation.recognition_journal_id:
                exceptions.append(
                    {
                        "obligation_id": str(obligation.pk),
                        "code": "MISSING_RECOGNITION_JOURNAL",
                    }
                )
                continue
            journal_ids.append(str(obligation.recognition_journal_id))
            lines = list(
                JournalLine.objects.filter(
                    journal_id=obligation.recognition_journal_id,
                    account_id=control_account.pk,
                ).select_related("journal")
            )
            if not lines:
                exceptions.append(
                    {
                        "obligation_id": str(obligation.pk),
                        "code": "MISSING_CONTROL_ACCOUNT_LINE",
                    }
                )
                continue
            for line in lines:
                # PD-006-CAM-02 pins a receivable debit balance and a payable credit balance.
                slice_gl += (
                    line.debit - line.credit
                    if obligation.direction == ObligationDirection.RECEIVABLE
                    else line.credit - line.debit
                )
                line_evidence.append((obligation, line))
        prior = (
            SubledgerReconciliationAccountSlice.objects.select_for_update(of=("self",))
            .filter(
                organization=organization,
                direction=direction,
                as_of_date=as_of_date,
                control_account=control_account,
                invalidation__isnull=True,
            )
            .order_by("-grain_revision")
            .first()
        )
        revision = (prior.grain_revision if prior else 0) + 1
        payload = {
            "control_account": str(control_account.pk),
            "revision": revision,
            "obligations": [str(obligation.pk) for obligation, _ in members],
            "journal_lines": [str(line.pk) for _, line in line_evidence],
            "subledger_total": str(slice_outstanding),
            "gl_total": str(slice_gl),
        }
        slice_payloads.append(
            {
                "account": control_account,
                "members": members,
                "lines": line_evidence,
                "outstanding": slice_outstanding,
                "gl": slice_gl,
                "prior": prior,
                "revision": revision,
                "hash": _canonical_hash(payload),
            }
        )
        outstanding_total += slice_outstanding
        linked_gl_total += slice_gl
    payload = {
        "direction": direction,
        "as_of_date": as_of_date,
        "obligations": [
            str(item.pk) for item in obligations if item.control_account_id
        ],
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
    for data in slice_payloads:
        control_account = data["account"]
        slice = SubledgerReconciliationAccountSlice.objects.create(
            run=run,
            organization=organization,
            direction=direction,
            as_of_date=as_of_date,
            control_account=control_account,
            subledger_outstanding_total=data["outstanding"],
            linked_gl_total=data["gl"],
            difference=data["outstanding"] - data["gl"],
            evidence_hash=data["hash"],
            grain_revision=data["revision"],
            supersedes=data["prior"],
        )
        for obligation, outstanding in data["members"]:
            SubledgerReconciliationObligationEvidence.objects.create(
                slice=slice,
                organization=organization,
                obligation=obligation,
                source_kind=obligation.source_kind,
                source_uuid=obligation.source_uuid,
                source_version=obligation.source_version,
                source_line_key=obligation.source_line_key,
                source_hash=obligation.source_hash,
                outstanding_amount=outstanding,
            )
        for obligation, line in data["lines"]:
            SubledgerReconciliationJournalLineEvidence.objects.create(
                slice=slice,
                organization=organization,
                obligation=obligation,
                journal=line.journal,
                journal_line=line,
                journal_source_uuid=line.journal.source_uuid,
                journal_source_version=line.journal.source_version,
                debit=line.debit,
                credit=line.credit,
            )
    SubledgerReconciliationRunProvenance.objects.create(
        run=run,
        classification=SubledgerReconciliationRunProvenance.PROSPECTIVE,
        evidence_hash=evidence_hash,
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
    run = SubledgerReconciliationRun.objects.get(pk=run.pk, organization=organization)
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


def _invoice_payload_hash(payload: object) -> str:
    return _canonical_hash(payload)


def supplier_invoice_queryset(*, organization: Organization, actor):
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUPPLIER_INVOICES_VIEW,
        message="اختیار مشاهده صورتحساب تأمین‌کننده را ندارید.",
        allow_any_scope=True,
    )
    from apps.organizations.authorization import scope_queryset

    return scope_queryset(
        SupplierInvoice.objects.filter(organization=organization),
        membership=membership,
        project_lookup="project_id",
    )


def supplier_invoice_match_queryset(*, organization: Organization, actor):
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.INVOICE_MATCHES_VIEW,
        message="اختیار مشاهده تطبیق صورتحساب را ندارید.",
        allow_any_scope=True,
    )
    from apps.organizations.authorization import scope_queryset

    return scope_queryset(
        SupplierInvoiceMatch.objects.filter(organization=organization),
        membership=membership,
        project_lookup="invoice_version__invoice__project_id",
    )


@transaction.atomic
def prepare_supplier_invoice(
    *,
    organization: Organization,
    actor,
    supplier,
    project,
    invoice_number: str,
    invoice_date: date,
    due_date: date | None,
    lines: list[dict[str, object]],
    idempotency_key: str,
    supersedes: SupplierInvoiceVersion | None = None,
) -> SupplierInvoiceVersion:
    """Retain AP-owned asserted invoice evidence without creating a payable."""

    organization = _lock_organization(organization)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUPPLIER_INVOICES_PREPARE,
        message="اختیار آماده‌سازی صورتحساب تأمین‌کننده را ندارید.",
        project=project,
    )
    if (
        supplier.organization_id != organization.pk
        or project.organization_id != organization.pk
    ):
        raise PermissionDenied("تأمین‌کننده و پروژه باید متعلق به همین Tenant باشند.")
    number = invoice_number.strip().upper()
    key = idempotency_key.strip()
    if not number or not key or not lines:
        raise ValidationError("شماره، ردیف و کلید idempotency صورتحساب الزامی است.")
    invoice, _ = SupplierInvoice.objects.get_or_create(
        organization=organization,
        supplier=supplier,
        invoice_number=number,
        defaults={"project": project, "created_by": actor},
    )
    if invoice.project_id != project.pk:
        raise ValidationError("هویت صورتحساب قبلاً برای پروژه دیگری ثبت شده است.")
    locked_invoice = SupplierInvoice.objects.select_for_update().get(pk=invoice.pk)
    normalized_lines = []
    for position, raw in enumerate(lines, start=1):
        po_line = raw["purchase_order_version_line"]
        quantity = Decimal(raw["quantity"])
        unit_price = Decimal(raw["unit_price"])
        kind = str(raw["kind"])
        if kind not in SupplierInvoiceLineKind.values:
            raise ValidationError("نوع ردیف صورتحساب معتبر نیست.")
        if (
            po_line.organization_id != organization.pk
            or po_line.version.purchase_order.supplier_id != supplier.pk
            or po_line.version.purchase_order.project_id != project.pk
        ):
            raise PermissionDenied("ردیف سفارش با صورتحساب هم‌دامنه نیست.")
        normalized_lines.append(
            {
                "line_number": int(raw.get("line_number", position)),
                "kind": kind,
                "purchase_order_version_line": str(po_line.pk),
                "description": str(raw.get("description", po_line.description)).strip(),
                "quantity": str(quantity),
                "unit_price": str(unit_price),
                "tax_amount": str(Decimal(raw.get("tax_amount", 0))),
                "freight_amount": str(Decimal(raw.get("freight_amount", 0))),
                "other_charge_amount": str(Decimal(raw.get("other_charge_amount", 0))),
            }
        )
    payload = {
        "invoice": str(locked_invoice.pk),
        "invoice_date": str(invoice_date),
        "due_date": str(due_date or ""),
        "currency": "IRR",
        "supersedes": str(supersedes.pk) if supersedes else "",
        "lines": normalized_lines,
    }
    fingerprint = _invoice_payload_hash(payload)
    existing = SupplierInvoiceVersion.objects.filter(
        organization=organization, idempotency_key=key
    ).first()
    if existing:
        if existing.source_hash != fingerprint:
            raise ValidationError(
                "کلید idempotency صورتحساب با محتوای متفاوت استفاده شده است."
            )
        return existing
    latest = locked_invoice.versions.order_by("-version_number").first()
    if supersedes:
        supersedes = SupplierInvoiceVersion.objects.select_for_update().get(
            pk=supersedes.pk, invoice=locked_invoice, organization=organization
        )
        if latest and latest.pk != supersedes.pk:
            raise ValidationError("اصلاح باید آخرین نسخه صورتحساب را جانشین کند.")
    elif latest:
        raise ValidationError("صورتحساب موجود فقط با اصلاح جانشین قابل نسخه‌گذاری است.")
    version = SupplierInvoiceVersion.objects.create(
        organization=organization,
        invoice=locked_invoice,
        version_number=(supersedes.version_number + 1 if supersedes else 1),
        supersedes=supersedes,
        invoice_date=invoice_date,
        due_date=due_date,
        currency="IRR",
        source_hash=fingerprint,
        idempotency_key=key,
        prepared_by=actor,
    )
    from apps.procurement.models import PurchaseOrderVersionLine

    po_lines = {
        str(item.pk): item
        for item in PurchaseOrderVersionLine.objects.select_for_update()
        .select_related("version__purchase_order")
        .filter(pk__in=[row["purchase_order_version_line"] for row in normalized_lines])
    }
    if len(po_lines) != len(
        {row["purchase_order_version_line"] for row in normalized_lines}
    ):
        raise PermissionDenied("یک یا چند ردیف سفارش معتبر نیست.")
    for row in normalized_lines:
        SupplierInvoiceLine.objects.create(
            organization=organization,
            invoice_version=version,
            line_number=row["line_number"],
            kind=row["kind"],
            purchase_order_version_line=po_lines[row["purchase_order_version_line"]],
            description=row["description"],
            quantity=Decimal(row["quantity"]),
            unit_price=Decimal(row["unit_price"]),
            tax_amount=Decimal(row["tax_amount"]),
            freight_amount=Decimal(row["freight_amount"]),
            other_charge_amount=Decimal(row["other_charge_amount"]),
        )
    record_audit_event(
        action="supplier_invoice.prepared",
        entity_type="subledgers.SupplierInvoiceVersion",
        entity_id=version.pk,
        organization=organization,
        actor=actor,
        metadata={
            "invoice_id": str(locked_invoice.pk),
            "version": version.version_number,
        },
    )
    return version


@transaction.atomic
def submit_supplier_invoice(
    *, organization: Organization, actor, invoice_version: SupplierInvoiceVersion
) -> SupplierInvoiceVersion:
    version = (
        SupplierInvoiceVersion.objects.select_for_update()
        .select_related("invoice__project")
        .get(pk=invoice_version.pk, organization=organization)
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUPPLIER_INVOICES_PREPARE,
        message="اختیار ارسال صورتحساب تأمین‌کننده را ندارید.",
        project=version.invoice.project,
    )
    if version.prepared_by_id != actor.pk:
        raise PermissionDenied("فقط آماده‌کننده می‌تواند نسخه پیش‌نویس را ارسال کند.")
    if version.status != SupplierInvoiceStatus.DRAFT or not version.lines.exists():
        raise ValidationError("فقط نسخه پیش‌نویس دارای ردیف قابل ارسال است.")
    version.status = SupplierInvoiceStatus.SUBMITTED
    version.submitted_at = timezone.now()
    version.save(update_fields=["status", "submitted_at"])
    return version


@transaction.atomic
def decide_supplier_invoice(
    *,
    organization: Organization,
    actor,
    invoice_version: SupplierInvoiceVersion,
    approve: bool,
    reason: str,
) -> SupplierInvoiceVersion:
    version = (
        SupplierInvoiceVersion.objects.select_for_update()
        .select_related("invoice__project")
        .get(pk=invoice_version.pk, organization=organization)
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUPPLIER_INVOICES_APPROVE,
        message="اختیار تعیین تکلیف صورتحساب تأمین‌کننده را ندارید.",
        project=version.invoice.project,
    )
    if version.status != SupplierInvoiceStatus.SUBMITTED:
        if version.status in {
            SupplierInvoiceStatus.APPROVED,
            SupplierInvoiceStatus.REJECTED,
        }:
            return version
        raise ValidationError("فقط صورتحساب ارسال‌شده قابل تعیین تکلیف است.")
    if version.prepared_by_id == actor.pk:
        raise PermissionDenied(
            "خودتأییدی صورتحساب تا تصمیم سیاستی جداگانه fail-closed است."
        )
    if not reason.strip():
        raise ValidationError("دلیل تصمیم صورتحساب الزامی است.")
    version.status = (
        SupplierInvoiceStatus.APPROVED if approve else SupplierInvoiceStatus.REJECTED
    )
    version.approved_by = actor
    version.approved_at = timezone.now()
    version.decision_reason = reason.strip()
    version.save(
        update_fields=["status", "approved_by", "approved_at", "decision_reason"]
    )
    record_audit_event(
        action="supplier_invoice.decided",
        entity_type="subledgers.SupplierInvoiceVersion",
        entity_id=version.pk,
        organization=organization,
        actor=actor,
        metadata={"approved": approve},
    )
    return version


@transaction.atomic
def prepare_match_tolerance_policy(
    *,
    organization: Organization,
    actor,
    effective_from: date,
    effective_to: date | None,
    quantity_tolerance_bps: int,
    unit_price_tolerance_bps: int,
    reason: str,
) -> MatchTolerancePolicy:
    organization = _lock_organization(organization)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.INVOICE_MATCH_POLICIES_MANAGE,
        message="اختیار آماده‌سازی سیاست رواداری تطبیق را ندارید.",
        allow_any_scope=True,
    )
    if (
        not 0 <= quantity_tolerance_bps <= 10000
        or not 0 <= unit_price_tolerance_bps <= 10000
    ):
        raise ValidationError("رواداری باید بر حسب basis point بین صفر و ده‌هزار باشد.")
    version_number = (
        MatchTolerancePolicy.objects.select_for_update()
        .filter(organization=organization)
        .order_by("-version_number")
        .values_list("version_number", flat=True)
        .first()
        or 0
    ) + 1
    payload = {
        "version": version_number,
        "effective_from": str(effective_from),
        "effective_to": str(effective_to or ""),
        "quantity_tolerance_bps": quantity_tolerance_bps,
        "unit_price_tolerance_bps": unit_price_tolerance_bps,
    }
    return MatchTolerancePolicy.objects.create(
        organization=organization,
        version_number=version_number,
        effective_from=effective_from,
        effective_to=effective_to,
        quantity_tolerance_bps=quantity_tolerance_bps,
        unit_price_tolerance_bps=unit_price_tolerance_bps,
        prepared_by=actor,
        reason=reason.strip(),
        payload_hash=_canonical_hash(payload),
    )


@transaction.atomic
def approve_match_tolerance_policy(
    *, organization: Organization, actor, policy: MatchTolerancePolicy
) -> MatchTolerancePolicy:
    policy = MatchTolerancePolicy.objects.select_for_update().get(
        pk=policy.pk, organization=organization
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.INVOICE_MATCH_POLICIES_APPROVE,
        message="اختیار تأیید سیاست رواداری تطبیق را ندارید.",
        allow_any_scope=True,
    )
    if policy.is_approved:
        return policy
    if policy.prepared_by_id == actor.pk:
        raise PermissionDenied("سیاست رواداری نیازمند تأییدکننده مستقل است.")
    overlap = MatchTolerancePolicy.objects.filter(
        organization=organization,
        is_approved=True,
        effective_from__lte=policy.effective_to or date.max,
    ).filter(effective_to__isnull=True) | MatchTolerancePolicy.objects.filter(
        organization=organization,
        is_approved=True,
        effective_from__lte=policy.effective_to or date.max,
        effective_to__gte=policy.effective_from,
    )
    if overlap.exists():
        raise ValidationError("بازه اثر سیاست رواداری با نسخه تأییدشده هم‌پوشانی دارد.")
    policy.is_approved = True
    policy.approved_by = actor
    policy.approved_at = timezone.now()
    policy.save(update_fields=["is_approved", "approved_by", "approved_at"])
    return policy


def _variance_bps(*, actual: Decimal, baseline: Decimal) -> Decimal:
    if actual <= baseline:
        return ZERO
    if baseline == 0:
        return Decimal(10000)
    return ((actual - baseline) * Decimal(10000)) / baseline


@transaction.atomic
def run_supplier_invoice_match(
    *,
    organization: Organization,
    actor,
    invoice_version: SupplierInvoiceVersion,
    idempotency_key: str,
) -> SupplierInvoiceMatch:
    version = (
        SupplierInvoiceVersion.objects.select_for_update()
        .select_related("invoice__project")
        .get(pk=invoice_version.pk, organization=organization)
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.INVOICE_MATCHES_RUN,
        message="اختیار اجرای تطبیق صورتحساب را ندارید.",
        project=version.invoice.project,
    )
    if version.status != SupplierInvoiceStatus.APPROVED:
        raise ValidationError("فقط صورتحساب تأییدشده قابل تطبیق است.")
    policies = (
        MatchTolerancePolicy.objects.select_for_update()
        .filter(
            organization=organization,
            is_approved=True,
            effective_from__lte=version.invoice_date,
        )
        .filter(
            models.Q(effective_to__isnull=True)
            | models.Q(effective_to__gte=version.invoice_date)
        )
    )
    if policies.count() != 1:
        raise ValidationError("دقیقاً یک سیاست رواداری مؤثر برای تطبیق لازم است.")
    policy = policies.get()
    key = idempotency_key.strip()
    if not key:
        raise ValidationError("کلید idempotency تطبیق الزامی است.")
    from apps.procurement.models import (
        GoodsReceiptItem,
        GoodsReceiptStatus,
        ServiceAcceptanceItem,
        ServiceAcceptanceStatus,
    )

    invoice_lines = list(
        version.lines.select_for_update().select_related(
            "purchase_order_version_line__source_item"
        )
    )
    source_payload = {
        "invoice_hash": version.source_hash,
        "policy_hash": policy.payload_hash,
        "lines": [str(line.pk) for line in invoice_lines],
    }
    fingerprint = _canonical_hash(source_payload)
    existing = SupplierInvoiceMatch.objects.filter(
        organization=organization, idempotency_key=key
    ).first()
    if existing:
        if existing.source_fingerprint != fingerprint:
            raise ValidationError(
                "کلید idempotency تطبیق با منبع متفاوت استفاده شده است."
            )
        return existing
    previous_match = version.matches.order_by("-version_number").first()
    match = SupplierInvoiceMatch.objects.create(
        organization=organization,
        invoice_version=version,
        tolerance_policy=policy,
        version_number=(previous_match.version_number + 1 if previous_match else 1),
        supersedes=previous_match,
        status=InvoiceMatchStatus.MATCHED,
        source_fingerprint=fingerprint,
        idempotency_key=key,
        matched_by=actor,
        matched_at=timezone.now(),
    )
    overall = InvoiceMatchStatus.MATCHED
    for invoice_line in invoice_lines:
        po_line = invoice_line.purchase_order_version_line
        if invoice_line.kind == SupplierInvoiceLineKind.GOODS:
            accepted = (
                GoodsReceiptItem.objects.filter(
                    purchase_order_item=po_line.source_item,
                    goods_receipt__status=GoodsReceiptStatus.POSTED,
                ).aggregate(total=Sum("quantity"))["total"]
                or ZERO
            )
        else:
            accepted = (
                ServiceAcceptanceItem.objects.filter(
                    purchase_order_version_line__source_item=po_line.source_item,
                    acceptance__status=ServiceAcceptanceStatus.ACCEPTED,
                ).aggregate(total=Sum("quantity"))["total"]
                or ZERO
            )
        previous_quantity = (
            SupplierInvoiceMatchLine.objects.filter(
                invoice_line__purchase_order_version_line=po_line,
                match__status__in=[
                    InvoiceMatchStatus.MATCHED,
                    InvoiceMatchStatus.WITHIN_TOLERANCE,
                ],
                match__superseded_by__isnull=True,
                invoice_line__invoice_version__status=SupplierInvoiceStatus.APPROVED,
                invoice_line__invoice_version__superseded_by__isnull=True,
            )
            .exclude(invoice_line__invoice_version=version)
            .aggregate(total=Sum("invoiced_quantity"))["total"]
            or ZERO
        )
        cumulative = previous_quantity + invoice_line.quantity
        qty_variance = _variance_bps(actual=cumulative, baseline=accepted)
        price_variance = _variance_bps(
            actual=invoice_line.unit_price, baseline=po_line.unit_price
        )
        status = InvoiceMatchStatus.MATCHED
        discrepancies: list[tuple[str, bool, dict[str, object]]] = []
        if accepted == 0:
            status = InvoiceMatchStatus.INCOMPLETE
            discrepancies.append(
                (MatchDiscrepancyCode.MISSING_ACCEPTANCE, True, {"accepted": "0"})
            )
        elif cumulative > po_line.quantity:
            status = InvoiceMatchStatus.BLOCKED
            discrepancies.append(
                (
                    MatchDiscrepancyCode.CUMULATIVE_OVERBILLING,
                    True,
                    {"cumulative": str(cumulative), "ordered": str(po_line.quantity)},
                )
            )
        elif qty_variance > policy.quantity_tolerance_bps:
            status = InvoiceMatchStatus.BLOCKED
            discrepancies.append(
                (
                    MatchDiscrepancyCode.QUANTITY_VARIANCE,
                    True,
                    {"bps": str(qty_variance)},
                )
            )
        elif qty_variance > 0:
            status = InvoiceMatchStatus.WITHIN_TOLERANCE
            discrepancies.append(
                (
                    MatchDiscrepancyCode.QUANTITY_VARIANCE,
                    False,
                    {"bps": str(qty_variance)},
                )
            )
        if price_variance > policy.unit_price_tolerance_bps:
            status = InvoiceMatchStatus.BLOCKED
            discrepancies.append(
                (
                    MatchDiscrepancyCode.UNIT_PRICE_VARIANCE,
                    True,
                    {"bps": str(price_variance)},
                )
            )
        elif price_variance > 0 and status == InvoiceMatchStatus.MATCHED:
            status = InvoiceMatchStatus.WITHIN_TOLERANCE
            discrepancies.append(
                (
                    MatchDiscrepancyCode.UNIT_PRICE_VARIANCE,
                    False,
                    {"bps": str(price_variance)},
                )
            )
        if any(
            value > 0
            for value in (
                invoice_line.tax_amount,
                invoice_line.freight_amount,
                invoice_line.other_charge_amount,
            )
        ):
            status = InvoiceMatchStatus.INCOMPLETE
            discrepancies.append(
                (MatchDiscrepancyCode.UNSUPPORTED_CHARGES, True, {"policy": "missing"})
            )
        line_evidence = SupplierInvoiceMatchLine.objects.create(
            organization=organization,
            match=match,
            invoice_line=invoice_line,
            ordered_quantity=po_line.quantity,
            accepted_quantity=accepted,
            previously_invoiced_quantity=previous_quantity,
            invoiced_quantity=invoice_line.quantity,
            ordered_unit_price=po_line.unit_price,
            invoiced_unit_price=invoice_line.unit_price,
            quantity_variance_bps=qty_variance.quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            ),
            unit_price_variance_bps=price_variance.quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            ),
            status=status,
            calculation_lineage={
                "policy_version": policy.version_number,
                "po_version_line": str(po_line.pk),
                "source_item": str(po_line.source_item_id),
            },
        )
        for code, blocking, evidence in discrepancies:
            MatchDiscrepancy.objects.create(
                organization=organization,
                match_line=line_evidence,
                code=code,
                blocking=blocking,
                evidence=evidence,
            )
        if status == InvoiceMatchStatus.INCOMPLETE:
            overall = InvoiceMatchStatus.INCOMPLETE
        elif (
            status == InvoiceMatchStatus.BLOCKED
            and overall != InvoiceMatchStatus.INCOMPLETE
        ):
            overall = InvoiceMatchStatus.BLOCKED
        elif (
            status == InvoiceMatchStatus.WITHIN_TOLERANCE
            and overall == InvoiceMatchStatus.MATCHED
        ):
            overall = InvoiceMatchStatus.WITHIN_TOLERANCE
    SupplierInvoiceMatch.objects.filter(pk=match.pk).update(status=overall)
    match.status = overall
    record_audit_event(
        action="supplier_invoice.match_retained",
        entity_type="subledgers.SupplierInvoiceMatch",
        entity_id=match.pk,
        organization=organization,
        actor=actor,
        metadata={"status": overall},
    )
    return match
