from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.organizations.models import MembershipStatus, OrganizationMembership
from apps.workforce.models import (
    Employee,
    EmployeePositionAssignment,
    EmployeeStatus,
    PositionAssignmentStatus,
    WorkTeam,
)

from .models import WorkflowDelegation, WorkflowInstance, WorkflowRoutingRule


@dataclass(slots=True)
class ResolvedCandidate:
    membership: OrganizationMembership
    routing_basis: list[dict[str, str]] = field(default_factory=list)
    position_assignment: EmployeePositionAssignment | None = None


@dataclass(frozen=True, slots=True)
class RoutingResult:
    candidates: tuple[ResolvedCandidate, ...]
    used_fallback: bool
    attempted_rules: tuple[str, ...]


def _active_memberships(instance: WorkflowInstance) -> QuerySet[OrganizationMembership]:
    return OrganizationMembership.objects.filter(
        organization_id=instance.organization_id,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
    ).select_related("user", "role_definition")


def _memberships_by_user(
    *, instance: WorkflowInstance, employees: list[Employee]
) -> dict[object, OrganizationMembership]:
    user_ids = [
        item.user_id
        for item in employees
        if item.user_id
        and item.organization_id == instance.organization_id
        and item.status == EmployeeStatus.ACTIVE
        and item.archived_at is None
    ]
    return {
        item.user_id: item
        for item in _active_memberships(instance).filter(user_id__in=user_ids)
    }


def _resolve_rule(
    *, instance: WorkflowInstance, rule: WorkflowRoutingRule
) -> list[ResolvedCandidate]:
    memberships = _active_memberships(instance)
    configuration = rule.configuration
    basis = {
        "resolver": rule.resolver_type,
        "rule_id": str(rule.pk),
        "fallback": str(rule.is_fallback).lower(),
    }
    if rule.resolver_type == "organization_owner":
        return [
            ResolvedCandidate(item, [basis])
            for item in memberships.filter(role_definition__is_owner=True)
        ]
    if rule.resolver_type == "explicit_membership":
        item = memberships.filter(pk=configuration["membership_id"]).first()
        return [ResolvedCandidate(item, [basis])] if item else []
    if rule.resolver_type == "organization_role":
        return [
            ResolvedCandidate(item, [basis])
            for item in memberships.filter(
                role_definition__code=configuration["role_code"]
            )
        ]
    if rule.resolver_type == "position":
        today = timezone.localdate()
        assignments = (
            EmployeePositionAssignment.objects.filter(
                organization_id=instance.organization_id,
                position_id=configuration["position_id"],
                position__is_active=True,
                employee__status=EmployeeStatus.ACTIVE,
                employee__archived_at__isnull=True,
                employee__user__isnull=False,
                status=PositionAssignmentStatus.ACTIVE,
                start_date__lte=today,
            )
            .select_related("employee__user", "position")
            .order_by("pk")
        )
        assignment_list = list(assignments)
        memberships_by_user = _memberships_by_user(
            instance=instance,
            employees=[item.employee for item in assignment_list],
        )
        resolved: list[ResolvedCandidate] = []
        for assignment in assignment_list:
            membership = memberships_by_user.get(assignment.employee.user_id)
            if membership:
                position_basis = basis | {
                    "position_id": str(assignment.position_id),
                    "position_assignment_id": str(assignment.pk),
                }
                resolved.append(
                    ResolvedCandidate(membership, [position_basis], assignment)
                )
        return resolved
    if rule.resolver_type == "work_team":
        team = (
            WorkTeam.objects.filter(
                pk=configuration["work_team_id"],
                organization_id=instance.organization_id,
                is_active=True,
                archived_at__isnull=True,
            )
            .select_related("lead__user")
            .first()
        )
        if not team:
            return []
        if configuration["mode"] == "lead":
            employees = [team.lead] if team.lead else []
        else:
            employees = list(
                Employee.objects.filter(
                    organization_id=instance.organization_id,
                    work_team=team,
                    status=EmployeeStatus.ACTIVE,
                    archived_at__isnull=True,
                    user__isnull=False,
                ).select_related("user")
            )
        memberships_by_user = _memberships_by_user(
            instance=instance, employees=[item for item in employees if item]
        )
        resolved = []
        for employee in employees:
            membership = memberships_by_user.get(employee.user_id)
            if membership:
                resolved.append(
                    ResolvedCandidate(
                        membership,
                        [basis | {"work_team_id": str(team.pk)}],
                    )
                )
        return resolved
    if rule.resolver_type in ("record_creator", "record_submitter"):
        context_key = (
            "creator_membership_id"
            if rule.resolver_type == "record_creator"
            else "submitter_membership_id"
        )
        membership_id = instance.subject_context.get(context_key)
        item = memberships.filter(pk=membership_id).first() if membership_id else None
        return [ResolvedCandidate(item, [basis])] if item else []
    raise ValidationError(f"مسیریاب ثبت‌شده اجرا نشده است: {rule.resolver_type}")


def _merge_candidates(
    target: dict[str, ResolvedCandidate], candidates: list[ResolvedCandidate]
) -> None:
    for candidate in candidates:
        key = str(candidate.membership.pk)
        existing = target.get(key)
        if existing is None:
            target[key] = candidate
            continue
        known = {tuple(sorted(item.items())) for item in existing.routing_basis}
        existing.routing_basis.extend(
            item
            for item in candidate.routing_basis
            if tuple(sorted(item.items())) not in known
        )
        if existing.position_assignment is None:
            existing.position_assignment = candidate.position_assignment


def _scope_matches(scope: dict[str, Any], context: dict[str, Any]) -> bool:
    return all(context.get(key) == value for key, value in scope.items())


def _apply_delegations(
    *,
    instance: WorkflowInstance,
    candidates: dict[str, ResolvedCandidate],
    permission: str,
) -> None:
    if not candidates:
        return
    now = timezone.now()
    delegations = (
        WorkflowDelegation.objects.filter(
            organization_id=instance.organization_id,
            delegator_id__in=list(candidates),
            starts_at__lte=now,
            ends_at__gt=now,
            revoked_at__isnull=True,
        )
        .filter(
            Q(workflow_type__isnull=True)
            | Q(workflow_type=instance.definition.workflow_type)
        )
        .filter(Q(permission__isnull=True) | Q(permission__code=permission))
        .select_related("delegate__user", "delegate__role_definition")
        .order_by("pk")
    )
    active_ids = set(
        _active_memberships(instance)
        .filter(pk__in=[item.delegate_id for item in delegations])
        .values_list("pk", flat=True)
    )
    additions: list[ResolvedCandidate] = []
    for delegation in delegations:
        if delegation.delegate_id not in active_ids or not _scope_matches(
            delegation.scope, instance.subject_context
        ):
            continue
        source = candidates[str(delegation.delegator_id)]
        additions.append(
            ResolvedCandidate(
                delegation.delegate,
                [
                    {
                        "resolver": "delegation",
                        "delegation_id": str(delegation.pk),
                        "delegator_membership_id": str(delegation.delegator_id),
                        "source_resolvers": ",".join(
                            sorted({item["resolver"] for item in source.routing_basis})
                        ),
                    }
                ],
            )
        )
    _merge_candidates(candidates, additions)


def resolve_step_candidates(
    *, instance: WorkflowInstance, step_id: object, required_permission: str
) -> RoutingResult:
    """Resolve ordered routes, deduplicate memberships, and retain all evidence."""
    rules = list(
        WorkflowRoutingRule.objects.filter(
            organization_id=instance.organization_id,
            version_id=instance.version_id,
            step_id=step_id,
        ).order_by("order", "pk")
    )
    primary = [item for item in rules if not item.is_fallback]
    fallbacks = [item for item in rules if item.is_fallback]
    resolved: dict[str, ResolvedCandidate] = {}
    attempted: list[str] = []
    for rule in primary:
        attempted.append(str(rule.pk))
        _merge_candidates(resolved, _resolve_rule(instance=instance, rule=rule))
    used_fallback = False
    if not resolved:
        for rule in fallbacks:
            attempted.append(str(rule.pk))
            fallback_candidates = _resolve_rule(instance=instance, rule=rule)
            if fallback_candidates:
                _merge_candidates(resolved, fallback_candidates)
                used_fallback = True
                break
    _apply_delegations(
        instance=instance, candidates=resolved, permission=required_permission
    )
    return RoutingResult(
        candidates=tuple(resolved[key] for key in sorted(resolved)),
        used_fallback=used_fallback,
        attempted_rules=tuple(attempted),
    )
