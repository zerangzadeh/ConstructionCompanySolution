from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode

from .models import (
    WorkflowDefinition,
    WorkflowTemplate,
    WorkflowVersion,
    WorkflowVersionStatus,
)
from .validators import evaluate_condition, validate_workflow_version


def simulate_workflow_selection(
    *, actor: Any, organization: Any, workflow_type_code: str, context: dict[str, Any]
) -> dict[str, Any]:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_VIEW,
        message="اجازه مشاهده گردش‌کارهای این شرکت را ندارید.",
    )
    candidates: list[tuple[int, WorkflowVersion]] = []
    definitions = WorkflowDefinition.objects.filter(
        organization=organization,
        workflow_type__code=workflow_type_code,
        versions__status=WorkflowVersionStatus.PUBLISHED,
    ).prefetch_related("versions")
    for definition in definitions:
        if all(context.get(key) == value for key, value in definition.scope.items()):
            version = next(
                item
                for item in definition.versions.all()
                if item.status == WorkflowVersionStatus.PUBLISHED
            )
            candidates.append((len(definition.scope), version))
    if not candidates:
        template = (
            WorkflowTemplate.objects.filter(
                workflow_type__code=workflow_type_code,
                is_active=True,
            )
            .order_by("code")
            .first()
        )
        return {
            "selected_version": None,
            "starter_template": str(template.pk) if template else None,
            "reason": (
                "platform_starter_fallback" if template else "no_matching_version"
            ),
        }
    specificity = max(item[0] for item in candidates)
    selected = [version for score, version in candidates if score == specificity]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار مبهم است.")
    return {
        "selected_version": str(selected[0].pk),
        "definition": selected[0].definition.code,
        "specificity": specificity,
        "reason": "most_specific_scope",
    }


def simulate_workflow_version(
    *, actor: Any, organization: Any, version: WorkflowVersion, context: dict[str, Any]
) -> dict[str, Any]:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_VIEW,
        message="اجازه مشاهده گردش‌کارهای این شرکت را ندارید.",
    )
    if version.organization_id != organization.pk:
        raise ValidationError("نسخه گردش‌کار متعلق به این شرکت نیست.")
    issues = validate_workflow_version(version)
    steps: list[dict[str, Any]] = []
    for step in version.steps.prefetch_related(
        "routing_rules", "outgoing_transitions__conditions"
    ):
        transitions = []
        for transition in step.outgoing_transitions.all():
            condition_results = [
                {
                    "type": condition.condition_type,
                    "matched": evaluate_condition(
                        condition.condition_type, condition.configuration, context
                    )
                    != condition.negate,
                }
                for condition in transition.conditions.all()
            ]
            transitions.append(
                {
                    "outcome": transition.outcome,
                    "target": transition.target_step.key,
                    "conditions": condition_results,
                    "expected": transition.is_default
                    or (
                        bool(condition_results)
                        and all(item["matched"] for item in condition_results)
                    ),
                }
            )
        routes = [
            {
                "resolver": rule.resolver_type,
                "fallback": rule.is_fallback,
                "candidates": "runtime_resolution_deferred_to_W2",
            }
            for rule in step.routing_rules.all()
        ]
        steps.append({"key": step.key, "routing": routes, "transitions": transitions})
    return {
        "version": str(version.pk),
        "valid": not issues,
        "issues": [issue.as_dict() for issue in issues],
        "steps": steps,
        "mutated": False,
    }
