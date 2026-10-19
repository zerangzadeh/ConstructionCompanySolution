"""L2 Actual candidates and explicit Project Controls consumption.

No source hook is wired. No default mapping, cutoff, allocation or recognition
policy is selected. Policy bindings are code-owned and ship unconfigured.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from uuid import uuid4

from django.db import transaction

from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.authorization import get_active_membership
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization

from .actual_sources import (
    INTEGRATIONS,
    SOURCE_MODELS,
    ActualRejected,
    NativeActualSource,
    native_lineage,
    read_native_actual,
)
from .models import (
    CBSNode,
    CostCenter,
    Project,
    ProjectCostFact,
    ProjectCostSourceContract,
    WBSNode,
)
from .services import (
    _require_budget_access,
    _stable_payload_hash,
    record_project_cost_fact,
)


@dataclass(frozen=True)
class ActualEffect:
    line_reference: str
    project: Project
    cbs_node: CBSNode
    wbs_node: WBSNode
    cost_center: CostCenter | None
    amount: Decimal
    currency: str
    recognition_date: date
    valuation_reference: str
    financial_evidence_reference: str


@dataclass(frozen=True)
class ActualMapping:
    effects: tuple[ActualEffect, ...]
    cutoff_reference: str
    effective_date_rule_reference: str
    unit_value_rate_book_reference: str
    project_attribution_version: str


@dataclass(frozen=True)
class ActualPolicyBinding:
    """Approved code-owned source policy, not a tenant-authored expression.

    map_source must read/validate approved mapping evidence, including source
    occurrence eligibility, value/rate/allocation and cutoff/date rules. It must
    not mutate source state. This infrastructure does not supply those rules.
    """

    map_source: Callable[..., ActualMapping]


# (producer key, classification policy, recognition policy, reconciliation policy)
# No permissive fallback, default grant or automatic policy activation.
POLICIES: Mapping[tuple[str, ...], ActualPolicyBinding] = MappingProxyType({})
ENTITY = "project_cost_actual_integration"
ACTION = AuditAction.PROJECT_COST_INTEGRATION_ATTEMPT


@dataclass(frozen=True)
class ActualCandidate:
    contract_id: str
    producer_key: str
    source_id: str
    source_version: str
    identity: str
    payload_hash: str
    source: NativeActualSource
    mapping: ActualMapping


@dataclass(frozen=True)
class ActualResult:
    attempt_id: str
    outcome: str
    fact_ids: tuple[str, ...]
    candidate_identity: str


def _events(organization):
    return AuditEvent.objects.filter(
        organization=organization, action=ACTION, entity_type=ENTITY
    )


def _identity(contract, source):
    # Exact SPEC008 identity; projects/lines/timestamps do not extend the key.
    return _stable_payload_hash(
        {
            "key": (
                str(contract.pk),
                source.source_type,
                source.source_id,
                source.source_version,
                "ACTUAL",
            )
        }
    )


def _payload(source, mapping, contract):
    effects = []
    for effect in mapping.effects:
        if (
            not isinstance(effect, ActualEffect)
            or type(effect.recognition_date) is not date
        ):
            raise ActualRejected("explicit_mapped_effect_and_date_required")
        effects.append(
            {
                "line": effect.line_reference,
                "project": str(effect.project.pk),
                "cbs": str(effect.cbs_node.pk),
                "wbs": str(effect.wbs_node.pk),
                "cost_center": str(getattr(effect.cost_center, "pk", "")),
                "amount": str(effect.amount),
                "currency": effect.currency,
                "date": str(effect.recognition_date),
                "valuation": effect.valuation_reference,
                "financial_evidence": effect.financial_evidence_reference,
            }
        )
    payload = {
        "source_version": source.source_version,
        "operation": source.operation,
        "predecessor": source.predecessor_id,
        "effects": effects,
        "contract_payload_hash": contract.payload_hash,
        "cutoff": mapping.cutoff_reference,
        "date_rule": mapping.effective_date_rule_reference,
        "basis": mapping.unit_value_rate_book_reference,
        "attribution_version": mapping.project_attribution_version,
    }
    # Existing three-family payloads retain their original exact hash contract.
    if source.required_reversal_source_id:
        payload["required_reversal_source_id"] = source.required_reversal_source_id
    return _stable_payload_hash(payload)


def _build(*, organization, actor, contract_id, source_id, permission):
    get_active_membership(user=actor, organization=organization)
    try:
        contract = ProjectCostSourceContract.objects.get(
            organization=organization,
            pk=contract_id,
            status="approved",
            measure="actual",
        )
    except ProjectCostSourceContract.DoesNotExist as exc:
        raise ActualRejected("approved_actual_contract_required") from exc
    if (
        contract.producer_key not in SOURCE_MODELS
        or contract.source_model != SOURCE_MODELS[contract.producer_key]
        or contract.event_schema != f"{contract.producer_key}.v1"
    ):
        raise ActualRejected("actual_native_contract_mismatch")
    binding = POLICIES.get(
        (
            contract.producer_key,
            contract.classification_policy_reference,
            contract.recognition_policy_reference,
            contract.reconciliation_policy_reference,
        )
    )
    if binding is None:
        raise ActualRejected("approved_mapping_cutoff_classification_required")
    source = read_native_actual(
        organization=organization,
        actor=actor,
        producer_key=contract.producer_key,
        source_id=source_id,
    )
    if source.operation not in {"recognize", "reverse", "replace", "replace_reversed"}:
        raise ActualRejected("approved_correction_operation_required")
    mapping = binding.map_source(
        organization=organization, actor=actor, contract=contract, source=source
    )
    if not isinstance(mapping, ActualMapping) or not mapping.effects:
        raise ActualRejected("approved_mapping_evidence_required")
    if (
        not all(
            (
                mapping.cutoff_reference,
                mapping.unit_value_rate_book_reference,
                mapping.project_attribution_version,
            )
        )
        or mapping.effective_date_rule_reference
        != contract.recognition_policy_reference
    ):
        raise ActualRejected("mapping_basis_cutoff_date_attribution_required")
    lines = set()
    for effect in mapping.effects:
        if not effect.line_reference or effect.line_reference in lines:
            raise ActualRejected("ambiguous_mapping_line")
        lines.add(effect.line_reference)
        _require_budget_access(
            organization=organization,
            project=effect.project,
            actor=actor,
            permission=permission,
        )
        if (
            any(
                item.organization_id != organization.pk
                for item in (effect.cbs_node, effect.wbs_node, effect.cost_center)
                if item is not None
            )
            or effect.wbs_node.project_id != effect.project.pk
        ):
            raise ActualRejected("mapped_dimension_scope_mismatch")
        if source.project_id and source.project_id != str(effect.project.pk):
            raise ActualRejected("source_project_mapping_mismatch")
        if effect.currency != source.currency or not effect.valuation_reference:
            raise ActualRejected("source_currency_or_valuation_mismatch")
        if (
            not isinstance(effect.amount, Decimal)
            or not effect.amount.is_finite()
            or effect.amount == 0
        ):
            raise ActualRejected("invalid_mapped_amount")
        # No inferred rounding from native4/6 decimal evidence to the existing
        # two-place fact model. A mapping must supply an exact representable value.
        if effect.amount != effect.amount.quantize(Decimal("0.01")):
            raise ActualRejected("explicit_fact_precision_mapping_required")
    after = read_native_actual(
        organization=organization,
        actor=actor,
        producer_key=contract.producer_key,
        source_id=source_id,
    )
    if after != source:
        raise ActualRejected("policy_mutated_source")
    return ActualCandidate(
        str(contract.pk),
        contract.producer_key,
        source.source_id,
        source.source_version,
        _identity(contract, source),
        _payload(source, mapping, contract),
        source,
        mapping,
    ), contract


@transaction.atomic
def prepare_actual_candidate(
    *, organization, actor, contract_id, source_id
) -> ActualCandidate:
    """Read-only derived L2 candidate; never records a recognized financial fact."""
    candidate, _ = _build(
        organization=organization,
        actor=actor,
        contract_id=contract_id,
        source_id=source_id,
        permission=P.PROJECT_COSTS_VIEW,
    )
    if not candidate.source.active:
        raise ActualRejected("inactive_source")
    return candidate


def _emit(organization, actor, attempt_id, metadata):
    return record_audit_event(
        action=ACTION,
        entity_type=ENTITY,
        entity_id=attempt_id,
        organization=organization,
        actor=actor,
        metadata=metadata,
    )


def _successful(organization):
    return _events(organization).filter(metadata__stage="succeeded")


def consume_actual_candidate(
    *, organization, actor, candidate: ActualCandidate, retry_of=""
) -> ActualResult:
    """Explicit target-authorized record operation; no source calls this function.

    An L2 candidate is input evidence, not authority. Reload sources/contract and
    resolve the registered approved policy again inside the target transaction.
    """
    if transaction.get_connection().in_atomic_block:
        raise ActualRejected("requires_autocommit_boundary")
    get_active_membership(user=actor, organization=organization)
    attempt_id = str(uuid4())
    base = {
        "integration_id": INTEGRATIONS.get(candidate.producer_key, ""),
        "integration_level": "L2",
        "contract_id": candidate.contract_id,
        "source_id": candidate.source_id,
        "source_version": candidate.source_version,
        "candidate_identity": candidate.identity,
        "retry_of": retry_of,
    }
    _emit(organization, actor, attempt_id, {**base, "stage": "attempted"})
    try:
        with transaction.atomic():
            organization = Organization.objects.select_for_update(no_key=True).get(
                pk=organization.pk
            )
            fresh, contract = _build(
                organization=organization,
                actor=actor,
                contract_id=candidate.contract_id,
                source_id=candidate.source_id,
                permission=P.PROJECT_COST_FACTS_RECORD,
            )
            # Match the existing target service's Project -> Contract lock order.
            list(
                Project.objects.select_for_update()
                .filter(
                    organization=organization,
                    pk__in={effect.project.pk for effect in fresh.mapping.effects},
                )
                .order_by("pk")
            )
            locked_contract = ProjectCostSourceContract.objects.select_for_update().get(
                organization=organization,
                pk=contract.pk,
                status="approved",
                measure="actual",
            )
            if locked_contract.payload_hash != contract.payload_hash:
                raise ActualRejected("contract_changed_during_validation")
            contract = locked_contract
            if (
                candidate.identity != fresh.identity
                or candidate.payload_hash != fresh.payload_hash
            ):
                raise ActualRejected("candidate_source_or_policy_drift")
            prior = (
                _successful(organization)
                .filter(metadata__candidate_identity=fresh.identity)
                .first()
            )
            if prior:
                if prior.metadata["payload_hash"] != fresh.payload_hash:
                    raise ActualRejected("conflicting_replay")
                fact_ids = tuple(prior.metadata["fact_ids"])
                if ProjectCostFact.objects.filter(
                    organization=organization,
                    contract=contract,
                    pk__in=fact_ids,
                    source_id=fresh.source_id,
                    source_version=fresh.source_version,
                ).count() != len(fact_ids):
                    raise ActualRejected("target_lineage_missing")
                _emit(
                    organization,
                    actor,
                    attempt_id,
                    {**base, "stage": "replayed", "fact_ids": fact_ids},
                )
                return ActualResult(attempt_id, "replayed", fact_ids, fresh.identity)
            if not fresh.source.active:
                raise ActualRejected("inactive_source")
            consumed = _successful(organization).filter(
                metadata__producer_key=fresh.producer_key,
                metadata__source_id=fresh.source_id,
            )
            if consumed.exists():
                raise ActualRejected(
                    "source_version_or_contract_changed_without_successor"
                )
            # ProjectCostFact remains authoritative even when a pre-existing
            # fact was recorded outside this integration's audit path. Missing
            # integration lineage never permits a second recognition.
            if ProjectCostFact.objects.filter(
                organization=organization,
                contract__producer_key=fresh.producer_key,
                source_id=fresh.source_id,
            ).exists():
                raise ActualRejected("source_facts_without_integration_lineage")
            original_by_line = {}
            if fresh.source.predecessor_id:
                parent = (
                    _successful(organization)
                    .filter(
                        metadata__producer_key=fresh.producer_key,
                        metadata__source_id=fresh.source.predecessor_id,
                    )
                    .first()
                )
                if (
                    parent is None
                    or parent.metadata["contract_id"] != fresh.contract_id
                ):
                    raise ActualRejected("recognized_predecessor_required")
                for line, fact_id in parent.metadata["recognition_lines"].items():
                    original_by_line[line] = (
                        ProjectCostFact.objects.select_for_update().get(
                            organization=organization,
                            contract=contract,
                            pk=fact_id,
                            kind="actual_recognized",
                        )
                    )
                if fresh.source.operation != "replace_reversed" and set(
                    original_by_line
                ) != {e.line_reference for e in fresh.mapping.effects}:
                    raise ActualRejected("predecessor_mapping_lines_mismatch")
            if fresh.source.operation == "replace_reversed":
                # Payroll publishes the full source inverse separately. Its
                # replacement must not create a second target inverse.
                for original in original_by_line.values():
                    _require_budget_access(
                        organization=organization,
                        actor=actor,
                        project=original.project,
                        permission=P.PROJECT_COST_FACTS_RECORD,
                    )
                prerequisite = (
                    _successful(organization)
                    .filter(
                        metadata__producer_key=fresh.producer_key,
                        metadata__source_id=fresh.source.required_reversal_source_id,
                        metadata__predecessor_id=fresh.source.predecessor_id,
                        metadata__operation="reverse",
                        metadata__contract_id=fresh.contract_id,
                    )
                    .first()
                )
                reversals = ProjectCostFact.objects.filter(
                    organization=organization,
                    contract=contract,
                    source_id=fresh.source.required_reversal_source_id,
                    kind="actual_reversal",
                    reverses_id__in=[fact.pk for fact in original_by_line.values()],
                )
                inverse_ids = {str(pk) for pk in reversals.values_list("pk", flat=True)}
                if (
                    not original_by_line
                    or not fresh.source.required_reversal_source_id
                    or prerequisite is None
                    or inverse_ids != set(prerequisite.metadata["fact_ids"])
                    or len(inverse_ids) != len(original_by_line)
                ):
                    raise ActualRejected("recognized_native_reversal_required")
            facts, recognition_lines = [], {}
            for effect in fresh.mapping.effects:
                old = original_by_line.get(effect.line_reference)
                if fresh.source.operation in {"reverse", "replace"} and old is None:
                    raise ActualRejected("explicit_predecessor_required")
                common = {
                    "organization": organization,
                    "actor": actor,
                    "contract": contract,
                    "project": effect.project,
                    "source_id": fresh.source_id,
                    "source_version": fresh.source_version,
                    "recognition_date": effect.recognition_date,
                    "currency": effect.currency,
                    "cbs_node": effect.cbs_node,
                    "wbs_node": effect.wbs_node,
                    "cost_center": effect.cost_center,
                    "classification_version": contract.classification_policy_reference,
                    "valuation_reference": effect.valuation_reference,
                    "financial_evidence_reference": effect.financial_evidence_reference,
                }
                line_key = _stable_payload_hash(
                    {"candidate": fresh.identity, "line": effect.line_reference}
                )
                if old and fresh.source.operation != "replace_reversed":
                    amount = (
                        effect.amount
                        if fresh.source.operation == "reverse"
                        else -old.amount
                    )
                    reversal = record_project_cost_fact(
                        **common,
                        kind="actual_reversal",
                        # _build proved exact two-place representability. Trim
                        # native trailing zeroes without changing monetary value.
                        amount=amount.quantize(Decimal("0.01")),
                        reverses=old,
                        economic_event_id=old.economic_event_id,
                        source_line_id=old.source_line_id,
                        occurrence_id=f"{line_key}:reverse",
                    )
                    facts.append(str(reversal.pk))
                if fresh.source.operation != "reverse":
                    fact = record_project_cost_fact(
                        **common,
                        kind="actual_recognized",
                        amount=effect.amount.quantize(Decimal("0.01")),
                        economic_event_id=fresh.identity,
                        source_line_id=line_key,
                        occurrence_id=f"{line_key}:actual",
                    )
                    facts.append(str(fact.pk))
                    recognition_lines[effect.line_reference] = str(fact.pk)
            metadata = {
                **base,
                "stage": "succeeded",
                "producer_key": fresh.producer_key,
                "payload_hash": fresh.payload_hash,
                "fact_ids": facts,
                "recognition_lines": recognition_lines,
                "operation": fresh.source.operation,
                "predecessor_id": fresh.source.predecessor_id,
                "required_reversal_source_id": fresh.source.required_reversal_source_id,
                "cutoff": fresh.mapping.cutoff_reference,
                "effective_date_rule": fresh.mapping.effective_date_rule_reference,
                "basis": fresh.mapping.unit_value_rate_book_reference,
                "attribution_version": fresh.mapping.project_attribution_version,
                "source_evidence_hash": fresh.source.source_version,
                "native_lineage": native_lineage(fresh.source),
            }
            _emit(organization, actor, attempt_id, metadata)
            return ActualResult(attempt_id, "recorded", tuple(facts), fresh.identity)
    except Exception as exc:
        code = str(exc) if isinstance(exc, ActualRejected) else "target_failure"
        _emit(
            organization,
            actor,
            attempt_id,
            {**base, "stage": "failed", "error_code": code},
        )
        raise


def reconcile_actual_candidate(*, organization, actor, contract_id, source_id) -> dict:
    """Read-only reconciliation; never repairs or creates a source or target."""
    with transaction.atomic():
        candidate, _ = _build(
            organization=organization,
            actor=actor,
            contract_id=contract_id,
            source_id=source_id,
            permission=P.PROJECT_COST_RECONCILIATIONS_VIEW,
        )
        results = list(
            _successful(organization).filter(
                metadata__candidate_identity=candidate.identity
            )
        )
        ids = tuple(results[0].metadata["fact_ids"]) if results else ()
        other_results = tuple(
            _successful(organization)
            .filter(
                metadata__producer_key=candidate.producer_key,
                metadata__source_id=candidate.source_id,
            )
            .exclude(metadata__candidate_identity=candidate.identity)
        )
        facts = tuple(
            ProjectCostFact.objects.filter(organization=organization, pk__in=ids)
        )
        inverse_ids = tuple(
            str(pk)
            for pk in ProjectCostFact.objects.filter(
                organization=organization,
                reverses_id__in=ids,
            ).values_list("pk", flat=True)
        )
        successors, pending, seen = [], [candidate.source_id], {candidate.source_id}
        lineage_cycle = False
        while pending:
            parent_id = pending.pop()
            for event in _successful(organization).filter(
                metadata__producer_key=candidate.producer_key,
                metadata__predecessor_id=parent_id,
            ):
                child_id = event.metadata["source_id"]
                if child_id in seen:
                    lineage_cycle = True
                    continue
                seen.add(child_id)
                pending.append(child_id)
                successors.append(event)
        linked_ids = set(ids) | set(inverse_ids)
        for event in (*successors, *other_results):
            linked_ids.update(event.metadata["fact_ids"])
        linked_facts = tuple(
            ProjectCostFact.objects.filter(
                organization=organization,
                pk__in=linked_ids,
            ).select_related("project")
        )
        unlinked_facts = tuple(
            ProjectCostFact.objects.filter(
                organization=organization,
                contract__producer_key=candidate.producer_key,
                source_id=candidate.source_id,
            )
            .exclude(pk__in=linked_ids)
            .select_related("project")
            .order_by("pk")
        )
        for project in {fact.project for fact in (*linked_facts, *unlinked_facts)}:
            _require_budget_access(
                organization=organization,
                actor=actor,
                project=project,
                permission=P.PROJECT_COST_RECONCILIATIONS_VIEW,
            )
        successor_states = []
        active_versions = []
        if candidate.source.active:
            active_versions.append(
                {
                    "source_id": candidate.source_id,
                    "source_version": candidate.source_version,
                }
            )
        for event in successors:
            state = {
                "source_id": event.metadata["source_id"],
                "recorded_source_version": event.metadata["source_version"],
                "operation": event.metadata["operation"],
                "fact_ids": event.metadata["fact_ids"],
            }
            try:
                native = read_native_actual(
                    organization=organization,
                    actor=actor,
                    producer_key=candidate.producer_key,
                    source_id=state["source_id"],
                )
            except ActualRejected:
                state.update(
                    source_active=None,
                    source_version=None,
                    source_evidence_unavailable=True,
                )
            else:
                state.update(
                    source_active=native.active,
                    source_version=native.source_version,
                    recorded_version_matches=native.source_version
                    == state["recorded_source_version"],
                )
                if native.active:
                    active_versions.append(
                        {
                            "source_id": native.source_id,
                            "source_version": native.source_version,
                        }
                    )
            successor_states.append(state)
        recognized = sum(
            (f.amount for f in facts if f.kind == "actual_recognized"), Decimal(0)
        )
        reversed_amount = sum(
            (f.amount for f in facts if f.kind == "actual_reversal"), Decimal(0)
        )
        expected = sum(
            (effect.amount for effect in candidate.mapping.effects), Decimal(0)
        )
        compared = (
            reversed_amount if candidate.source.operation == "reverse" else recognized
        )
        return {
            "source_id": candidate.source_id,
            "source_version": candidate.source_version,
            "active_source_version": candidate.source_version
            if candidate.source.active
            else None,
            "active_source_versions": tuple(active_versions),
            "source_active": candidate.source.active,
            "native_amount": str(candidate.source.amount),
            "mapped_amount": str(expected),
            "target_recognized_amount": str(recognized),
            "target_reversal_amount": str(reversed_amount),
            "lineage_net_amount": str(
                sum((fact.amount for fact in linked_facts), Decimal(0))
            ),
            "mapped_target_difference": str(expected - compared),
            "approved_cutoff": candidate.mapping.cutoff_reference,
            "unit_value_rate_book_reference": candidate.mapping.unit_value_rate_book_reference,
            "project_attribution_version": candidate.mapping.project_attribution_version,
            "operation": candidate.source.operation,
            "predecessor_id": candidate.source.predecessor_id,
            "target_fact_ids": ids,
            "unlinked_target_fact_ids": tuple(str(f.pk) for f in unlinked_facts),
            "target_reversals": tuple(
                str(f.pk) for f in linked_facts if f.kind == "actual_reversal"
            ),
            "corresponding_successors": tuple(successor_states),
            "other_recorded_source_versions": tuple(
                {
                    "contract_id": event.metadata["contract_id"],
                    "source_version": event.metadata["source_version"],
                    "fact_ids": event.metadata["fact_ids"],
                }
                for event in other_results
            ),
            "unlinked_version_or_contract_drift": bool(other_results),
            "target_payload_matches": bool(results)
            and results[0].metadata["payload_hash"] == candidate.payload_hash,
            "missing_target": not results,
            "duplicate_results": len(results) > 1,
            "lineage_cycle": lineage_cycle,
            "target_lineage_missing": len(linked_facts) != len(linked_ids),
        }
