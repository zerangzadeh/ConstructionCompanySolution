"""Tenant administration reads; lifecycle mutations stay in workflow services."""

from django.db.models import QuerySet

from apps.accounts.models import User
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization

from .models import WorkflowVersion


def visible_versions(*, actor: User, organization: Organization) -> QuerySet:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=P.WORKFLOWS_VIEW,
        message="اجازه مشاهدهٔ تعریف‌های گردش‌کار این شرکت را ندارید.",
    )
    return (
        WorkflowVersion.objects.filter(
            organization=organization, definition__organization=organization
        )
        .select_related("definition__workflow_type", "published_by", "retired_by")
        .order_by("definition__code", "-version_number")
    )


def configuration_payload(version: WorkflowVersion) -> dict:
    """Round-trip existing service fields, including ordered routing/conditions."""
    steps = []
    for step in version.steps.prefetch_related("routing_rules").order_by("key"):
        steps.append(
            {
                "key": step.key,
                "name": step.name,
                "step_type": step.step_type,
                "is_start": step.is_start,
                "is_terminal": step.is_terminal,
                "domain_command": step.domain_command,
                "required_permission": step.required_permission,
                "configuration": step.configuration,
                "routing": [
                    {
                        "resolver_type": rule.resolver_type,
                        "configuration": rule.configuration,
                        "order": rule.order,
                        "is_fallback": rule.is_fallback,
                    }
                    for rule in step.routing_rules.order_by("order", "pk")
                ],
            }
        )
    transitions = []
    for item in version.transitions.select_related(
        "source_step", "target_step"
    ).prefetch_related("conditions"):
        transitions.append(
            {
                "source": item.source_step.key,
                "target": item.target_step.key,
                "outcome": item.outcome,
                "domain_command": item.domain_command,
                "required_permission": item.required_permission,
                "priority": item.priority,
                "is_default": item.is_default,
                "conditions": [
                    {
                        "condition_type": condition.condition_type,
                        "configuration": condition.configuration,
                        "order": condition.order,
                        "negate": condition.negate,
                    }
                    for condition in item.conditions.order_by("order", "pk")
                ],
            }
        )
    return {"steps": steps, "transitions": transitions}
