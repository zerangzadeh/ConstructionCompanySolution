"""Read-only, versioned preparation for legacy Payment disposition (CEP-028).

This module never creates a Treasury movement or changes a legacy reference.
Its inventory is a stable input to a separately authorized migration/cutover.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from apps.audit.models import AuditEvent
from apps.billing.models import ClaimSettlementAllocation
from apps.payments.models import Payment, PaymentAllocation, PaymentDocumentLink
from apps.treasury.models import TreasuryMovement, TreasuryMovementStatus

PLAN_VERSION = "legacy-payment-disposition-v1"


@dataclass(frozen=True, slots=True)
class SourceRow:
    payment_id: UUID
    organization_id: UUID
    direction: str
    amount: Decimal
    paid_on: date
    status: str
    party_id: UUID | None
    project_id: UUID
    allocation_ids: tuple[str, ...]
    settlement_ids: tuple[str, ...]
    document_link_ids: tuple[str, ...]
    audit_event_ids: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ExactMatchProof:
    source_payment_id: UUID
    source_fingerprint: str
    cash_account_id: UUID
    fiscal_period_id: UUID
    source_version_reference: str
    irr_basis_reference: str
    status_chain_reference: str
    supporting_evidence_reference: str


@dataclass(frozen=True, slots=True)
class Disposition:
    payment_id: UUID
    kind: str  # mapped, opening, exception, excluded
    source_fingerprint: str
    reviewer_id: UUID | None
    evidence_reference: str
    target_movement_id: UUID | None = None
    reason: str = ""
    exact_match_proof: ExactMatchProof | None = None


@dataclass(frozen=True, slots=True)
class Reconciliation:
    plan_version: str
    source_count: int
    mapped_count: int
    opening_count: int
    excluded_count: int
    exception_count: int
    source_amount: Decimal
    mapped_amount: Decimal
    exceptions: tuple[tuple[str, str], ...]
    source_to_target: tuple[tuple[str, str], ...]


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def inventory_legacy_payments(
    *, organization_id: UUID, cutoff: date
) -> tuple[SourceRow, ...]:
    """Inventory every pre-cutoff Payment and its retained dependent identities."""
    payments: QuerySet[Payment] = Payment.objects.filter(
        organization_id=organization_id, paid_on__lt=cutoff
    ).order_by("pk")
    rows: list[SourceRow] = []
    for payment in payments.iterator():
        allocations = tuple(
            (str(pk), str(amount), status, str(contract_id))
            for pk, amount, status, contract_id in PaymentAllocation.objects.filter(
                organization_id=organization_id, payment_id=payment.pk
            )
            .order_by("pk")
            .values_list("pk", "amount", "status", "contract_id")
        )
        allocation_ids = tuple(item[0] for item in allocations)
        settlements = tuple(
            (str(pk), str(amount), status, str(claim_id))
            for pk, amount, status, claim_id in ClaimSettlementAllocation.objects.filter(
                organization_id=organization_id,
                payment_allocation_id__in=allocation_ids,
            )
            .order_by("pk")
            .values_list("pk", "amount", "status", "claim_id")
        )
        settlement_ids = tuple(item[0] for item in settlements)
        document_links = tuple(
            (str(pk), str(document_id))
            for pk, document_id in PaymentDocumentLink.objects.filter(
                organization_id=organization_id, payment_id=payment.pk
            )
            .order_by("pk")
            .values_list("pk", "document_id")
        )
        document_link_ids = tuple(item[0] for item in document_links)
        audit_event_ids = tuple(
            str(pk)
            for pk in AuditEvent.objects.filter(
                organization_id=organization_id,
                entity_id=str(payment.pk),
            )
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        source = {
            "payment_id": str(payment.pk),
            "organization_id": str(organization_id),
            "direction": payment.direction,
            "amount": str(payment.amount),
            "paid_on": payment.paid_on.isoformat(),
            "status": payment.status,
            "party_id": str(payment.party_id or ""),
            "project_id": str(payment.project_id),
            "allocations": allocations,
            "settlements": settlements,
            "document_links": document_links,
            "audit_event_ids": audit_event_ids,
        }
        rows.append(
            SourceRow(
                payment_id=payment.pk,
                organization_id=organization_id,
                direction=payment.direction,
                amount=payment.amount,
                paid_on=payment.paid_on,
                status=payment.status,
                party_id=payment.party_id,
                project_id=payment.project_id,
                allocation_ids=allocation_ids,
                settlement_ids=settlement_ids,
                document_link_ids=document_link_ids,
                audit_event_ids=audit_event_ids,
                fingerprint=_digest(source),
            )
        )
    return tuple(rows)


def reconcile_dispositions(
    *,
    sources: Iterable[SourceRow],
    dispositions: Iterable[Disposition],
    targets: Iterable[TreasuryMovement] = (),
    accepted_exact_match_evidence: frozenset[str] = frozenset(),
    accepted_opening_evidence: frozenset[str] = frozenset(),
    accepted_exclusion_evidence: frozenset[str] = frozenset(),
) -> Reconciliation:
    """Fail closed on stale/duplicate/unsupported mappings; preserve exceptions."""
    source_rows = tuple(sources)
    source_by_id = {row.payment_id: row for row in source_rows}
    if len(source_by_id) != len(source_rows):
        raise ValueError("Duplicate source Payment identity")
    target_by_id = {movement.pk: movement for movement in targets}
    plans = tuple(dispositions)
    plan_by_id = {plan.payment_id: plan for plan in plans}
    if len(plan_by_id) != len(plans) or set(plan_by_id) - set(source_by_id):
        raise ValueError("Duplicate or out-of-inventory disposition")
    exceptions: list[tuple[str, str]] = []
    links: list[tuple[str, str]] = []
    used_targets: set[UUID] = set()
    counts = {kind: 0 for kind in ("mapped", "opening", "excluded", "exception")}
    mapped_amount = Decimal(0)
    for row in source_rows:
        plan = plan_by_id.get(row.payment_id)
        if plan is None:
            exceptions.append((str(row.payment_id), "missing_disposition"))
            continue
        if plan.source_fingerprint != row.fingerprint:
            exceptions.append((str(row.payment_id), "stale_source_fingerprint"))
            continue
        if plan.kind not in counts:
            raise ValueError("Unsupported disposition")
        if plan.kind == "exception":
            exceptions.append((str(row.payment_id), plan.reason or "unresolved"))
            counts["exception"] += 1
            continue
        if not plan.reviewer_id or not plan.evidence_reference.strip():
            exceptions.append((str(row.payment_id), "missing_review_or_evidence"))
            continue
        if plan.kind == "opening" and plan.evidence_reference not in accepted_opening_evidence:
            exceptions.append((str(row.payment_id), "unaccepted_opening_evidence"))
            continue
        if plan.kind == "excluded" and plan.evidence_reference not in accepted_exclusion_evidence:
            exceptions.append((str(row.payment_id), "unaccepted_exclusion_evidence"))
            continue
        if plan.kind == "mapped":
            if plan.evidence_reference not in accepted_exact_match_evidence:
                exceptions.append((str(row.payment_id), "unaccepted_exact_match_evidence"))
                continue
            proof = plan.exact_match_proof
            if (
                proof is None
                or proof.source_payment_id != row.payment_id
                or proof.source_fingerprint != row.fingerprint
                or not proof.source_version_reference.strip()
                or not proof.irr_basis_reference.strip()
                or not proof.status_chain_reference.strip()
                or not proof.supporting_evidence_reference.strip()
            ):
                exceptions.append((str(row.payment_id), "incomplete_exact_match_proof"))
                continue
            movement = target_by_id.get(plan.target_movement_id)
            if movement is None:
                exceptions.append((str(row.payment_id), "missing_target"))
                continue
            if movement.pk in used_targets:
                raise ValueError("One Treasury movement cannot map two Payments")
            used_targets.add(movement.pk)
            if (
                movement.organization_id != row.organization_id
                or movement.kind != row.direction
                or movement.amount != row.amount
                or movement.movement_date != row.paid_on
                or movement.project_id != row.project_id
                or movement.party_id != row.party_id
                or movement.currency != "IRR"
                or movement.status != TreasuryMovementStatus.POSTED
                or movement.journal_id is None
                or row.status != "posted"
                or movement.journal.period_id != proof.fiscal_period_id
                or not movement.legs.filter(account_id=proof.cash_account_id).exists()
            ):
                exceptions.append((str(row.payment_id), "target_mismatch"))
                continue
            links.append((str(row.payment_id), str(movement.pk)))
            mapped_amount += row.amount
        elif plan.target_movement_id is not None:
            raise ValueError("Only exact mapped disposition may name a movement")
        counts[plan.kind] += 1
    return Reconciliation(
        plan_version=PLAN_VERSION,
        source_count=len(source_rows),
        mapped_count=counts["mapped"],
        opening_count=counts["opening"],
        excluded_count=counts["excluded"],
        exception_count=len(exceptions),
        source_amount=sum((row.amount for row in source_rows), Decimal(0)),
        mapped_amount=mapped_amount,
        exceptions=tuple(exceptions),
        source_to_target=tuple(links),
    )
