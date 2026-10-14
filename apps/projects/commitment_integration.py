"""INT-B11 root. Source-specific producers must be registered by approved code.

No production/source producer is activated here. Audit attempts are committed
before the target transaction; callers must invoke the root outside atomic().
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID, uuid4

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
)
from apps.projects.models import (
    CBSNode,
    CostCenter,
    Project,
    ProjectBudgetControl,
    ProjectCostFact,
    ProjectCostFactKind,
    ProjectCostMeasure,
    ProjectCostSourceContract,
    ProjectCostSourceContractStatus,
    WBSNode,
)
from apps.projects.services import (
    _require_budget_access,
    _stable_payload_hash,
    _validate_cost_dimensions,
    record_project_cost_fact,
)


@dataclass(frozen=True)
class CostEffect:
    amount: Decimal
    currency: str
    recognition_date: date
    cbs_node: CBSNode
    wbs_node: WBSNode
    cost_center: CostCenter | None
    classification_reference: str
    valuation_reference: str
    financial_evidence_reference: str = ""


@dataclass(frozen=True)
class SourceInstruction:
    """Validated source evidence returned by a trusted, source-owned adapter."""

    source_version: str
    active_source_version: str
    eligibility: str
    operation: str
    effects: tuple[CostEffect, ...]
    predecessor_version: str = ""
    prior_fact_ids: tuple[str, ...] = ()
    source_line_reference: str = ""
    cutoff_required: bool = False
    cutoff_reference: str = ""
    effective_at: datetime | None = None


@dataclass(frozen=True)
class Producer:
    """Code-owned child binding; validate may read/lock, never mutate source state."""

    source_domain: str
    source_type: str
    event_schema: str
    validate: Callable[..., SourceInstruction]


# Deliberately inert. Only a separately approved child package may add adapters.
PRODUCERS: Mapping[str, Producer] = MappingProxyType({})
FAMILIES = {
    "pcp-po-commitment": "procurement",
    "pcp-subcontract-commitment": "contracts",
}
ACTION = AuditAction.PROJECT_COST_INTEGRATION_ATTEMPT
ENTITY = "project_cost_commitment_root"


class CommitmentRejected(ValueError):
    """Stable, non-sensitive validation reason retained in durable audit evidence."""


@dataclass(frozen=True)
class CommitmentResult:
    attempt_id: str
    outcome: str
    fact_ids: tuple[str, ...]
    source_version: str


def canonical_key(
    contract_id: str,
    source_type: str,
    source_id: str,
    source_version: str,
    recognition_type: str,
) -> tuple[str, ...]:
    """The five approved components, without event/line/project/time extensions."""
    return contract_id, source_type, source_id, source_version, recognition_type


def _events(organization: Organization) -> QuerySet[AuditEvent]:
    return AuditEvent.objects.filter(
        organization=organization, action=ACTION, entity_type=ENTITY
    )


def _emit(
    *,
    organization: Organization,
    actor: User | None,
    attempt_id: str,
    correlation_id: UUID,
    metadata: dict[str, object],
) -> AuditEvent:
    return record_audit_event(
        action=ACTION,
        entity_type=ENTITY,
        entity_id=attempt_id,
        organization=organization,
        actor=actor,
        correlation_id=correlation_id,
        metadata=metadata,
    )


def _producer(contract: ProjectCostSourceContract) -> Producer:
    producer = PRODUCERS.get(contract.producer_key)
    if (
        producer is None
        or FAMILIES.get(contract.producer_key) != producer.source_domain
        or producer.source_type != contract.source_model
        or producer.event_schema != contract.event_schema
        or contract.status != ProjectCostSourceContractStatus.APPROVED
        or contract.measure != ProjectCostMeasure.COMMITMENT
    ):
        raise CommitmentRejected("unapproved_producer")
    return producer


def _payload(instruction: SourceInstruction, project: Project) -> str:
    effects = []
    for effect in instruction.effects:
        effects.append(
            {
                "amount": str(effect.amount),
                "currency": effect.currency,
                "date": str(effect.recognition_date),
                "cbs": str(effect.cbs_node.pk),
                "wbs": str(effect.wbs_node.pk),
                "cost_center": str(getattr(effect.cost_center, "pk", "")),
                "classification": effect.classification_reference,
                "valuation": effect.valuation_reference,
                "financial_evidence": effect.financial_evidence_reference,
            }
        )
    return _stable_payload_hash(
        {
            "project": str(project.pk),
            "operation": instruction.operation,
            "effects": effects,
            "predecessor": instruction.predecessor_version,
            "prior_facts": instruction.prior_fact_ids,
            "source_line": instruction.source_line_reference,
            "cutoff": instruction.cutoff_reference,
            "effective_at": instruction.effective_at.isoformat()
            if instruction.effective_at
            else None,
        }
    )


def process_commitment(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    contract_id: str,
    source_id: str,
    source_version: str,
    recognition_type: str = "COMMITMENT",
    correlation_id: UUID | None = None,
    retry_of: str = "",
) -> CommitmentResult:
    """Apply one approved occurrence; never changes a source business record.

    Failure evidence survives target rollback. Refuse enclosing transactions:
    otherwise caller rollback could erase the promised durable attempt/result.
    """
    if transaction.get_connection().in_atomic_block:
        raise CommitmentRejected("requires_autocommit_boundary")
    organization = Organization.objects.get(pk=organization.pk)
    actor = User.objects.get(pk=actor.pk)
    _require_budget_access(
        organization=organization,
        project=project,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_COST_FACTS_RECORD,
    )
    attempt_id, correlation_id = str(uuid4()), correlation_id or uuid4()
    base = {
        "stage": "attempted",
        "contract_id": str(contract_id),
        "source_id": source_id,
        "source_version": source_version,
        "recognition_type": recognition_type,
        "project_id": str(project.pk),
        "retry_of": retry_of,
        "integration_id": "INT-B11",
        "integration_level": "L2",
    }
    # If this persistence fails, no target transaction is started.
    _emit(
        organization=organization,
        actor=actor,
        attempt_id=attempt_id,
        correlation_id=correlation_id,
        metadata=base,
    )
    try:
        with transaction.atomic():
            # Serialize cross-contract transitions for one tenant without
            # blocking the FK key-share locks used by normal audit inserts.
            organization = Organization.objects.select_for_update(no_key=True).get(
                pk=organization.pk
            )
            actor = User.objects.get(pk=actor.pk)
            # Match the existing fact service's project -> contract lock order.
            project = Project.objects.select_for_update().get(
                pk=project.pk, organization=organization
            )
            _require_budget_access(
                organization=organization,
                project=project,
                actor=actor,
                permission=BusinessPermissionCode.PROJECT_COST_FACTS_RECORD,
            )
            contract = (
                ProjectCostSourceContract.objects.select_for_update()
                .filter(pk=contract_id, organization=organization)
                .first()
            )
            if contract is None:
                raise CommitmentRejected("missing_contract")
            producer = _producer(contract)
            if (
                not source_id.strip()
                or not source_version.strip()
                or recognition_type != "COMMITMENT"
            ):
                raise CommitmentRejected("invalid_identity")
            if (
                retry_of
                and not _events(organization)
                .filter(
                    entity_id=retry_of,
                    metadata__contract_id=str(contract_id),
                    metadata__source_id=source_id,
                    metadata__source_version=source_version,
                    metadata__recognition_type=recognition_type,
                    metadata__stage__in=("failed", "rejected"),
                )
                .exists()
            ):
                raise CommitmentRejected("invalid_retry_link")
            instruction = producer.validate(
                organization=organization,
                project=project,
                actor=actor,
                contract=contract,
                source_id=source_id,
                source_version=source_version,
            )
            if instruction.source_version != source_version:
                raise CommitmentRejected("source_version_mismatch")
            if instruction.effective_at is not None and (
                not isinstance(instruction.effective_at, datetime)
                or not timezone.is_aware(instruction.effective_at)
            ):
                raise CommitmentRejected("invalid_source_effective_time")
            budget = ProjectBudgetControl.objects.get(
                organization=organization, project=project
            ).governing_budget
            if budget is None or not instruction.effects:
                raise CommitmentRejected("missing_mapping")
            for effect in instruction.effects:
                _validate_cost_dimensions(
                    project=project,
                    budget=budget,
                    cbs_node=effect.cbs_node,
                    wbs_node=effect.wbs_node,
                    cost_center=effect.cost_center,
                )
                if (
                    effect.currency != budget.currency
                    or not effect.classification_reference.strip()
                    or not effect.valuation_reference.strip()
                    or not isinstance(effect.amount, Decimal)
                    or not effect.amount.is_finite()
                    or (
                        contract.requires_financial_evidence
                        and not effect.financial_evidence_reference
                    )
                ):
                    raise CommitmentRejected("invalid_mapping")
            key = canonical_key(
                str(contract.pk),
                producer.source_type,
                source_id,
                source_version,
                recognition_type,
            )
            key_hash = _stable_payload_hash({"key": key})
            stream = _stable_payload_hash(
                {
                    "stream": (
                        producer.source_domain,
                        producer.source_type,
                        source_id,
                        recognition_type,
                    )
                }
            )
            fingerprint = _payload(instruction, project)
            success_events = _events(organization).filter(metadata__stage="succeeded")
            accepted = success_events.filter(metadata__key_hash=key_hash).first()
            if instruction.eligibility not in {"eligible", "cancelled", "superseded"}:
                raise CommitmentRejected("source_ineligible")
            if instruction.cutoff_required and not instruction.cutoff_reference:
                raise CommitmentRejected("missing_cutoff")
            if accepted:
                if accepted.metadata["payload_hash"] != fingerprint:
                    raise CommitmentRejected("payload_conflict")
                fact_ids = tuple(accepted.metadata["fact_ids"])
                if ProjectCostFact.objects.filter(
                    organization=organization,
                    project=project,
                    contract=contract,
                    pk__in=fact_ids,
                ).count() != len(fact_ids):
                    raise CommitmentRejected("lineage_inconsistency")
                outcome = "replayed"
            else:
                if (
                    instruction.active_source_version != source_version
                    or instruction.eligibility == "superseded"
                ):
                    raise CommitmentRejected("stale_source_version")
                previous = (
                    success_events.filter(metadata__stream=stream)
                    .order_by("-created_at", "-pk")
                    .first()
                )
                if previous and previous.metadata["contract_id"] != str(contract.pk):
                    raise CommitmentRejected("unapproved_contract_transition")
                expected = previous.metadata["source_version"] if previous else ""
                if instruction.predecessor_version != expected:
                    raise CommitmentRejected("invalid_predecessor")
                if (
                    instruction.eligibility == "cancelled"
                    and instruction.operation != "RELEASE"
                ):
                    raise CommitmentRejected("cancellation_requires_release")
                if (instruction.operation == "CREATE") != (previous is None):
                    raise CommitmentRejected("invalid_initial_operation")
                prior_ids = tuple(instruction.prior_fact_ids)
                prior = list(
                    ProjectCostFact.objects.filter(
                        organization=organization,
                        project=project,
                        contract=contract,
                        source_id=source_id,
                        pk__in=prior_ids,
                    )
                )
                if len(prior) != len(set(prior_ids)):
                    raise CommitmentRejected("invalid_correction_link")
                prior_root_ids = {
                    fact_id
                    for event in success_events.filter(metadata__stream=stream)
                    for fact_id in event.metadata["fact_ids"]
                }
                if previous and prior_root_ids and not prior_ids:
                    raise CommitmentRejected("missing_correction_link")
                if not set(prior_ids).issubset(prior_root_ids):
                    raise CommitmentRejected("foreign_correction_link")
                if instruction.eligibility == "cancelled":
                    _validate_cancellation(
                        instruction.effects,
                        list(
                            ProjectCostFact.objects.filter(
                                organization=organization,
                                project=project,
                                contract=contract,
                                pk__in=prior_root_ids,
                            )
                        ),
                    )
                if instruction.operation == "REVERSE":
                    reversed_ids = {
                        fact_id
                        for event in success_events.filter(
                            metadata__stream=stream, metadata__operation="REVERSE"
                        )
                        for fact_id in event.metadata["prior_fact_ids"]
                    }
                    if set(prior_ids) & reversed_ids:
                        raise CommitmentRejected("already_reversed")
                    _validate_reversal(instruction.effects, prior)
                kinds = {
                    "CREATE": ProjectCostFactKind.COMMITMENT_AUTHORIZED,
                    "ADJUST": ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
                    "SUPERSEDE": ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
                    "REVERSE": ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
                    "RELEASE": ProjectCostFactKind.COMMITMENT_RELIEF,
                }
                if instruction.operation not in kinds or not instruction.effects:
                    raise CommitmentRejected("invalid_effect_mapping")
                facts = []
                event_identity = _stable_payload_hash({"stream": stream})
                for index, effect in enumerate(instruction.effects):
                    if (
                        not isinstance(effect.amount, Decimal)
                        or not effect.amount.is_finite()
                    ):
                        raise CommitmentRejected("invalid_decimal")
                    if not effect.amount:
                        # Explicit source-mapped zero; never inferred from missing evidence.
                        continue
                    # Fact storage identifiers are derived from the common key;
                    # line/index provenance cannot mint another root occurrence.
                    fact = record_project_cost_fact(
                        organization=organization,
                        project=project,
                        actor=actor,
                        contract=contract,
                        kind=kinds[instruction.operation],
                        source_id=source_id,
                        source_version=source_version,
                        source_line_id=f"{key_hash}:{index}",
                        economic_event_id=event_identity,
                        occurrence_id=f"{key_hash}:{index}",
                        recognition_date=effect.recognition_date,
                        currency=effect.currency,
                        amount=effect.amount,
                        cbs_node=effect.cbs_node,
                        wbs_node=effect.wbs_node,
                        cost_center=effect.cost_center,
                        classification_version=effect.classification_reference,
                        valuation_reference=effect.valuation_reference,
                        financial_evidence_reference=effect.financial_evidence_reference,
                    )
                    facts.append(str(fact.pk))
                fact_ids, outcome = tuple(facts), "succeeded"
            metadata = {
                **base,
                "stage": outcome,
                "key": list(key),
                "key_hash": key_hash,
                "source_domain": producer.source_domain,
                "source_type": producer.source_type,
                "contract_version": contract.version,
                "stream": stream,
                "payload_hash": fingerprint,
                "fact_ids": list(fact_ids),
                "operation": instruction.operation,
                "predecessor_version": instruction.predecessor_version,
                "prior_fact_ids": list(instruction.prior_fact_ids),
                "source_line_reference": instruction.source_line_reference,
                "cutoff_reference": instruction.cutoff_reference,
                "source_effective_at": instruction.effective_at.isoformat()
                if instruction.effective_at
                else None,
            }
            _emit(
                organization=organization,
                actor=actor,
                attempt_id=attempt_id,
                correlation_id=correlation_id,
                metadata=metadata,
            )
        return CommitmentResult(attempt_id, outcome, fact_ids, source_version)
    except Exception as exc:
        # Never retain arbitrary exception messages or source payloads in logs.
        reason = str(exc) if isinstance(exc, CommitmentRejected) else type(exc).__name__
        evidence_actor = (
            actor
            if organization.memberships.filter(
                user=actor, status=MembershipStatus.ACTIVE
            ).exists()
            else None
        )
        _emit(
            organization=organization,
            actor=evidence_actor,
            attempt_id=attempt_id,
            correlation_id=correlation_id,
            metadata={
                **base,
                "stage": "rejected"
                if isinstance(exc, CommitmentRejected)
                else "failed",
                "reason": reason,
            },
        )
        raise


def _dimension(item: ProjectCostFact) -> tuple[str, ...]:
    return (
        str(item.cbs_node_id),
        str(item.wbs_node_id),
        str(item.cost_center_id or ""),
        item.currency,
    )


def _validate_reversal(
    effects: tuple[CostEffect, ...], prior: list[ProjectCostFact]
) -> None:
    expected, actual = {}, {}
    for fact in prior:
        sign = -1 if fact.kind == ProjectCostFactKind.COMMITMENT_RELIEF else 1
        key = _dimension(fact)
        expected[key] = expected.get(key, Decimal(0)) - sign * fact.amount
    for effect in effects:
        key = (
            str(effect.cbs_node.pk),
            str(effect.wbs_node.pk),
            str(getattr(effect.cost_center, "pk", "")),
            effect.currency,
        )
        actual[key] = actual.get(key, Decimal(0)) + effect.amount
    if not prior or expected != actual:
        raise CommitmentRejected("reversal_must_offset_linked_effects")


def _validate_cancellation(
    effects: tuple[CostEffect, ...], facts: list[ProjectCostFact]
) -> None:
    remaining: dict[tuple[str, ...], Decimal] = {}
    mapped: dict[tuple[str, ...], Decimal] = {}
    for fact in facts:
        key = _dimension(fact)
        amount = (
            -fact.amount
            if fact.kind == ProjectCostFactKind.COMMITMENT_RELIEF
            else fact.amount
        )
        remaining[key] = remaining.get(key, Decimal(0)) + amount
    for effect in effects:
        key = (
            str(effect.cbs_node.pk),
            str(effect.wbs_node.pk),
            str(getattr(effect.cost_center, "pk", "")),
            effect.currency,
        )
        mapped[key] = mapped.get(key, Decimal(0)) + effect.amount
    if remaining != mapped:
        raise CommitmentRejected("cancellation_must_release_remaining")


def reconcile_commitment(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    contract_id: str,
    source_id: str,
    source_version: str,
) -> dict[str, object]:
    """Compare one authoritative source snapshot with immutable root/fact evidence."""
    organization = Organization.objects.get(pk=organization.pk)
    actor = User.objects.get(pk=actor.pk)
    _require_budget_access(
        organization=organization,
        project=project,
        actor=actor,
        permission=BusinessPermissionCode.PROJECT_COST_RECONCILIATIONS_VIEW,
    )
    contract = ProjectCostSourceContract.objects.get(
        pk=contract_id, organization=organization
    )
    producer = _producer(contract)
    source = producer.validate(
        organization=organization,
        project=project,
        actor=actor,
        contract=contract,
        source_id=source_id,
        source_version=source_version,
    )
    events = list(
        _events(organization)
        .filter(
            metadata__contract_id=str(contract.pk),
            metadata__source_id=source_id,
            metadata__project_id=str(project.pk),
            metadata__stage="succeeded",
        )
        .order_by("created_at", "pk")
    )
    latest = events[-1].metadata if events else None
    issues = set()
    if latest is None:
        if source.eligibility in {"eligible", "cancelled"}:
            issues.add("missing_target_effect")
    elif latest["source_version"] != source.active_source_version:
        issues.update(("source_version_mismatch", "stale_target_effect"))
    elif (
        source.source_version == source.active_source_version
        and _payload(source, project) != latest["payload_hash"]
    ):
        issues.add("source_payload_mismatch")
    seen, prior_ids, lineage = set(), set(), []
    total = Decimal(0)
    for event in events:
        data = event.metadata
        if data["key_hash"] in seen:
            issues.add("duplicate_target_effect")
        seen.add(data["key_hash"])
        if not set(data["prior_fact_ids"]).issubset(prior_ids):
            issues.add("lineage_inconsistency")
        facts = list(
            ProjectCostFact.objects.filter(
                organization=organization,
                project=project,
                contract=contract,
                pk__in=data["fact_ids"],
                source_id=source_id,
                source_version=data["source_version"],
            )
        )
        if len(facts) != len(data["fact_ids"]):
            issues.add("lineage_inconsistency")
        total += sum(
            (
                -fact.amount
                if fact.kind == ProjectCostFactKind.COMMITMENT_RELIEF
                else fact.amount
                for fact in facts
            ),
            Decimal(0),
        )
        prior_ids.update(data["fact_ids"])
        lineage.append(
            {
                "source_version": data["source_version"],
                "operation": data["operation"],
                "fact_ids": data["fact_ids"],
                "prior_fact_ids": data["prior_fact_ids"],
                "predecessor_version": data["predecessor_version"],
            }
        )
    unlinked = ProjectCostFact.objects.filter(
        organization=organization,
        project=project,
        contract=contract,
        source_id=source_id,
    ).exclude(pk__in=prior_ids)
    if unlinked.exists():
        issues.add("lineage_inconsistency")
        versions = {event.metadata["source_version"] for event in events}
        if unlinked.filter(source_version__in=versions).exists():
            issues.add("duplicate_target_effect")
        else:
            issues.add("source_version_mismatch")
    return {
        "active_source_version": source.active_source_version,
        "source_eligibility": source.eligibility,
        "target_source_version": latest["source_version"] if latest else None,
        "active_target_fact_ids": sorted(prior_ids),
        "current_instruction_fact_ids": latest["fact_ids"] if latest else [],
        "effective_commitment": None
        if issues & {"duplicate_target_effect", "lineage_inconsistency"}
        else total,
        "lineage": lineage,
        "issues": sorted(issues),
        "coverage": "bounded",
    }
