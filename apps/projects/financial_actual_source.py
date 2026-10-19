"""INT-B03: explicitly enrolled, source-owned financial occurrences only.

No journal, cash movement or recognition draft is automatically a cost. Approved
code-owned bindings must validate the native occurrence and its exclusive producer
ownership. The registry intentionally ships empty (EXT-0010).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from django.core.exceptions import ValidationError

from apps.accounting.recognition_registry import (
    RecognitionRequest,
    resolve_recognition_owner,
)
from apps.audit.models import AuditEvent
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P

from .actual_sources import ActualRejected, NativeActualSource
from .models import ProjectCostFact


@dataclass(frozen=True)
class FinancialOccurrence:
    source: NativeActualSource
    recognition: RecognitionRequest
    # Native producer identities covered by this occurrence. The binding must
    # prove complete/exclusive coverage; a journal alias cannot create a second
    # cost for a source already owned by another actual producer.
    covered_sources: tuple[tuple[str, str], ...]
    exclusive_coverage_reference: str


@dataclass(frozen=True)
class FinancialSourceBinding:
    read_occurrence: Callable[..., FinancialOccurrence]


# Source model / identity / version / eligibility are explicit contract bindings,
# never guesses from journal description, amount, username or cash status.
BINDINGS: Mapping[str, FinancialSourceBinding] = MappingProxyType({})
KEY = "pcp-fin-actual"


def read_financial_actual(*, organization, actor, source_id) -> NativeActualSource:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=P.PROJECT_COSTS_VIEW,
        allow_any_scope=True,
        message="اجازه خواندن منبع مالی هزینه پروژه را ندارید.",
    )
    # source_id is an exact registered occurrence identity, not a request to
    # discover or infer a source from an arbitrary financial record.
    binding = BINDINGS.get(str(source_id))
    if binding is None:
        raise ActualRejected("approved_financial_occurrence_binding_required")
    occurrence = binding.read_occurrence(
        organization=organization, actor=actor, source_id=source_id
    )
    if not isinstance(occurrence, FinancialOccurrence):
        raise ActualRejected("typed_financial_occurrence_required")
    source, request = occurrence.source, occurrence.recognition
    if (
        not isinstance(source, NativeActualSource)
        or source.producer_key != KEY
        or source.source_type != "financial.recognition_occurrence"
        or source.source_id != str(source_id)
        or not source.source_version
        or not isinstance(request, RecognitionRequest)
        or request.organization_id != organization.pk
        or request.source_organization_id != organization.pk
        or not occurrence.exclusive_coverage_reference
        or not occurrence.covered_sources
        or any(
            not model or not identity for model, identity in occurrence.covered_sources
        )
    ):
        raise ActualRejected("financial_identity_owner_or_coverage_required")
    try:
        resolution = resolve_recognition_owner(request=request)
    except ValidationError as exc:
        raise ActualRejected("approved_recognition_owner_required") from exc
    policy = resolution.policy
    if (
        policy.source_family == "Treasury Cash Movement"
        or "settlement" in policy.recognition_type.lower()
        or policy.creates_accounting_entry.startswith("NO")
    ):
        raise ActualRejected("cash_settlement_is_not_project_cost")
    if not any(
        identity == str(request.source_identity)
        for _, identity in occurrence.covered_sources
    ):
        raise ActualRejected("recognition_identity_not_in_coverage")
    if (
        AuditEvent.objects.filter(
            organization=organization,
            entity_type="project_cost_actual_integration",
            metadata__stage="succeeded",
            metadata__producer_key=KEY,
            metadata__native_lineage__financial__source_identity=str(
                request.source_identity
            ),
            metadata__native_lineage__financial__source_version=request.source_version,
            metadata__native_lineage__financial__economic_occurrence=request.economic_occurrence,
            metadata__native_lineage__financial__recognition_type=request.recognition_type,
        )
        .exclude(metadata__source_id=source.source_id)
        .exists()
    ):
        raise ActualRejected("financial_occurrence_alias_already_consumed")
    # Native source reads and object permission checks belong to the registered
    # binding. Repeated reads inside the target transaction detect source drift.
    for model, identity in occurrence.covered_sources:
        if (
            ProjectCostFact.objects.filter(
                organization=organization,
                contract__source_model=model,
                source_id=identity,
            )
            .exclude(contract__producer_key=KEY)
            .exists()
        ):
            raise ActualRejected("economic_occurrence_already_has_actual_producer")
    expected = {
        **resolution.audit_metadata(),
        "exclusive_coverage_reference": occurrence.exclusive_coverage_reference,
        "covered_sources": occurrence.covered_sources,
    }
    if source.evidence.get("financial") != expected:
        raise ActualRejected("financial_source_version_lineage_mismatch")
    # Version must fingerprint the complete native evidence, including the
    # canonical recognition owner and exclusive source coverage.
    from .services import _stable_payload_hash

    if source.source_version != _stable_payload_hash(source.evidence):
        raise ActualRejected("financial_source_version_lineage_mismatch")
    return source
