"""Inert budget-control decision contract for explicitly enrolled source events.

The Human-approved initial enrolled-event set is empty. Source domains remain
transaction owners; Project Controls may only return a result/evidence tuple.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.organizations.policy_services import resolve_active_tenant_policy
from apps.organizations.policy_specs import (
    PROJECT_BUDGET_OVERRIDE_POLICY_CODE,
    PROJECT_BUDGET_RESPONSE_POLICY_CODE,
)
from apps.projects.models import (
    BudgetAllocation,
    CBSNode,
    Project,
    ProjectBudgetControl,
    ProjectCostFact,
    ProjectCostFactKind,
)
from apps.projects.services import _require_budget_access

# Decision-02: no active producer/control contract is enrolled at this checkpoint.
APPROVED_CONTROL_EVENTS: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class BudgetControlResult:
    disposition: str
    budget_amount: Decimal
    exposure_amount: Decimal
    overrun_amount: Decimal
    response: str
    override_used: bool
    budget_id: str
    policy_version_ids: tuple[str, str]


def _classify_overrun(
    *,
    budget_amount: Decimal,
    actual_cost: Decimal,
    open_commitment: Decimal,
    actual_delta: Decimal,
    open_commitment_delta: Decimal,
    response: str,
    override_enabled: bool,
    override_requested: bool,
) -> tuple[str, Decimal, Decimal]:
    """Count actual plus remaining open commitment exactly once at zero tolerance."""
    amounts = (
        budget_amount,
        actual_cost,
        open_commitment,
        actual_delta,
        open_commitment_delta,
    )
    if not all(isinstance(value, Decimal) for value in amounts):
        raise ValidationError("Budget control requires Decimal amounts.")
    if budget_amount < 0 or actual_cost < 0 or open_commitment < 0:
        raise ValidationError("Budget and existing exposure must be non-negative.")
    if response not in {"WARNING", "HARD_STOP"} or type(override_enabled) is not bool:
        raise ValidationError("Approved explicit budget control policy is required.")
    next_actual = actual_cost + actual_delta
    next_open = open_commitment + open_commitment_delta
    if next_actual < 0 or next_open < 0:
        raise ValidationError("A proposed event cannot create negative exposure.")
    exposure = next_actual + next_open
    overrun = max(exposure - budget_amount, Decimal("0.00"))
    if override_requested and (not override_enabled or overrun == 0):
        raise PermissionDenied("Budget override is not enabled for this overrun.")
    if overrun == 0:
        disposition = "ALLOW"
    elif override_requested:
        disposition = "OVERRIDE"
    elif response == "HARD_STOP":
        disposition = "BLOCK"
    else:
        disposition = "WARN"
    return disposition, exposure, overrun


@transaction.atomic
def evaluate_budget_control(
    *,
    organization: Organization,
    project: Project,
    cbs_node: CBSNode,
    actor: User,
    event_key: str,
    source_id: str,
    source_version: str,
    actual_delta: Decimal,
    open_commitment_delta: Decimal,
    override_requested: bool = False,
    override_reason: str = "",
) -> BudgetControlResult:
    """Evaluate only a code-enrolled event; never post, settle or mutate Budget."""
    project = Project.objects.select_for_update().get(pk=project.pk)
    _require_budget_access(
        organization=organization,
        actor=actor,
        project=project,
        permission=BusinessPermissionCode.PROJECT_COSTS_VIEW,
    )
    if event_key not in APPROVED_CONTROL_EVENTS:
        raise PermissionDenied("No approved active producer/control event is enrolled.")
    if not source_id.strip() or not source_version.strip():
        raise ValidationError("Source identity and version are required.")
    control = (
        ProjectBudgetControl.objects.select_for_update(of=("self",))
        .select_related("governing_budget")
        .get(organization=organization, project=project)
    )
    budget = control.governing_budget
    if (
        budget is None
        or cbs_node.organization_id != organization.pk
        or (cbs_node.structure_version_id != budget.structure_version_id)
    ):
        raise PermissionDenied("Governing Budget and CBS scope are required.")
    response_version = resolve_active_tenant_policy(
        organization=organization, policy_code=PROJECT_BUDGET_RESPONSE_POLICY_CODE
    )
    override_version = resolve_active_tenant_policy(
        organization=organization, policy_code=PROJECT_BUDGET_OVERRIDE_POLICY_CODE
    )
    response = response_version.parameters.get("response")
    override_enabled = override_version.parameters.get("override_enabled")
    if override_requested and (
        not override_reason.strip()
        or not has_business_permission(
            user=actor,
            organization=organization,
            permission=BusinessPermissionCode.PROJECT_BUDGET_OVERRIDES_APPROVE,
            project=project,
        )
    ):
        raise PermissionDenied("Explicit override permission and reason are required.")
    budget_amount = BudgetAllocation.objects.filter(
        organization=organization,
        manifest_line__manifest__budget=budget,
        cbs_node=cbs_node,
    ).aggregate(value=Sum("amount"))["value"] or Decimal("0.00")
    facts = ProjectCostFact.objects.filter(
        organization=organization,
        project=project,
        cbs_node=cbs_node,
        currency=budget.currency,
    )
    actual = sum(
        (
            fact.amount
            for fact in facts
            if fact.kind
            in {
                ProjectCostFactKind.ACTUAL_RECOGNIZED,
                ProjectCostFactKind.ACTUAL_REVERSAL,
            }
        ),
        Decimal("0.00"),
    )
    open_commitment = sum(
        (
            fact.amount
            for fact in facts
            if fact.kind
            in {
                ProjectCostFactKind.COMMITMENT_AUTHORIZED,
                ProjectCostFactKind.COMMITMENT_ADJUSTMENT,
            }
        ),
        Decimal("0.00"),
    ) - sum(
        (
            fact.amount
            for fact in facts
            if fact.kind == ProjectCostFactKind.COMMITMENT_RELIEF
        ),
        Decimal("0.00"),
    )
    disposition, exposure, overrun = _classify_overrun(
        budget_amount=budget_amount,
        actual_cost=actual,
        open_commitment=open_commitment,
        actual_delta=actual_delta,
        open_commitment_delta=open_commitment_delta,
        response=response,
        override_enabled=override_enabled,
        override_requested=override_requested,
    )
    result = BudgetControlResult(
        disposition=disposition,
        budget_amount=budget_amount,
        exposure_amount=exposure,
        overrun_amount=overrun,
        response=response,
        override_used=override_requested,
        budget_id=str(budget.pk),
        policy_version_ids=(str(response_version.pk), str(override_version.pk)),
    )
    record_audit_event(
        action=(
            AuditAction.PROJECT_BUDGET_CONTROL_OVERRIDE
            if override_requested
            else AuditAction.PROJECT_BUDGET_CONTROL_EVALUATED
        ),
        entity_type="project_budget_control",
        entity_id=control.pk,
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "cbs_node_id": str(cbs_node.pk),
            "budget_id": str(budget.pk),
            "source_id": source_id.strip(),
            "source_version": source_version.strip(),
            "event_key": event_key,
            "disposition": disposition,
            "overrun": str(overrun),
            "override_reason": override_reason.strip() if override_requested else "",
            "policy_version_ids": result.policy_version_ids,
        },
    )
    return result
