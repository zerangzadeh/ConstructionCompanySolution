from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.apps import apps
from django.core.exceptions import ValidationError

from apps.organizations.models import BusinessPermission, BusinessPermissionCode

from .registry import registry


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    path: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def validate_configuration_payload(payload: object, *, workflow_type_code: str) -> None:
    """Validate a normalized template payload without persisting tenant data."""

    if workflow_type_code not in registry.workflow_types:
        raise ValidationError("نوع گردش‌کار در registry ثبت نشده است.")
    if not isinstance(payload, dict):
        raise ValidationError("پیکربندی template باید یک شیء JSON باشد.")
    unknown = set(payload) - {"steps", "transitions"}
    if unknown:
        raise ValidationError(f"کلیدهای پیکربندی ثبت‌نشده: {', '.join(sorted(unknown))}")
    steps = payload.get("steps", [])
    transitions = payload.get("transitions", [])
    if not isinstance(steps, list) or not isinstance(transitions, list):
        raise ValidationError("steps و transitions باید آرایه باشند.")
    step_keys: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValidationError(f"گام {index} معتبر نیست.")
        unknown_step = set(step) - {
            "key",
            "name",
            "step_type",
            "is_start",
            "is_terminal",
            "domain_command",
            "required_permission",
            "configuration",
            "routing",
        }
        if unknown_step:
            raise ValidationError(f"فیلد ثبت‌نشده در گام {index}.")
        key = step.get("key")
        step_type = step.get("step_type")
        if not isinstance(key, str) or not key or key in step_keys:
            raise ValidationError(f"کلید گام {index} نامعتبر یا تکراری است.")
        step_keys.add(key)
        specification = registry.step_types.get(str(step_type))
        if specification is None:
            raise ValidationError(f"نوع گام {index} ثبت نشده است.")
        specification.schema.validate(
            step.get("configuration", {}), label=f"پیکربندی گام {index}"
        )
        command_key = step.get("domain_command", "")
        if command_key:
            command = registry.domain_commands.get(str(command_key))
            if command is None or command.workflow_type != workflow_type_code:
                raise ValidationError(f"فرمان دامنه گام {index} ثبت نشده است.")
        required_permission = step.get("required_permission", "")
        if (
            required_permission
            and required_permission not in BusinessPermissionCode.values
        ):
            raise ValidationError(f"مجوز گام {index} ثبت نشده است.")
        routing = step.get("routing", [])
        if not isinstance(routing, list):
            raise ValidationError(f"مسیریابی گام {index} باید آرایه باشد.")
        for routing_index, rule in enumerate(routing):
            if not isinstance(rule, dict):
                raise ValidationError("قاعده مسیریابی معتبر نیست.")
            if set(rule) - {
                "resolver_type",
                "configuration",
                "order",
                "is_fallback",
            }:
                raise ValidationError("فیلد ثبت‌نشده در قاعده مسیریابی وجود دارد.")
            resolver = registry.routing_resolvers.get(str(rule.get("resolver_type")))
            if resolver is None:
                raise ValidationError("نوع مسیریاب ثبت نشده است.")
            resolver.schema.validate(
                rule.get("configuration", {}),
                label=f"مسیریابی {index}.{routing_index}",
            )
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            raise ValidationError(f"انتقال {index} معتبر نیست.")
        unknown_transition = set(transition) - {
            "source",
            "target",
            "outcome",
            "domain_command",
            "required_permission",
            "priority",
            "is_default",
            "conditions",
        }
        if unknown_transition:
            raise ValidationError(f"فیلد ثبت‌نشده در انتقال {index}.")
        if (
            transition.get("source") not in step_keys
            or transition.get("target") not in step_keys
        ):
            raise ValidationError(f"گام انتقال {index} وجود ندارد.")
        command_key = transition.get("domain_command", "")
        if command_key:
            command = registry.domain_commands.get(str(command_key))
            if command is None or command.workflow_type != workflow_type_code:
                raise ValidationError(f"فرمان دامنه انتقال {index} ثبت نشده است.")
        required_permission = transition.get("required_permission", "")
        if (
            required_permission
            and required_permission not in BusinessPermissionCode.values
        ):
            raise ValidationError(f"مجوز انتقال {index} ثبت نشده است.")
        conditions = transition.get("conditions", [])
        if not isinstance(conditions, list):
            raise ValidationError(f"شرط‌های انتقال {index} باید آرایه باشد.")
        for condition_index, condition in enumerate(conditions):
            if not isinstance(condition, dict):
                raise ValidationError("شرط معتبر نیست.")
            if set(condition) - {
                "condition_type",
                "configuration",
                "order",
                "negate",
            }:
                raise ValidationError("فیلد ثبت‌نشده در شرط وجود دارد.")
            specification = registry.condition_types.get(
                str(condition.get("condition_type"))
            )
            if specification is None:
                raise ValidationError("نوع شرط ثبت نشده است.")
            specification.schema.validate(
                condition.get("configuration", {}),
                label=f"شرط {index}.{condition_index}",
            )


def _scopes_overlap(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return all(first[key] == second[key] for key in set(first) & set(second))


def _has_invalid_cycle(adjacency: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> bool:
        if key in visiting:
            return True
        if key in visited:
            return False
        visiting.add(key)
        if any(visit(target) for target in adjacency.get(key, set())):
            return True
        visiting.remove(key)
        visited.add(key)
        return False

    return any(visit(key) for key in adjacency)


def _routing_target_issue(rule: Any) -> ValidationIssue | None:
    configuration = rule.configuration
    lookup: tuple[str, str, str] | None = None
    if rule.resolver_type == "explicit_membership":
        lookup = ("organizations", "OrganizationMembership", "membership_id")
    elif rule.resolver_type == "position":
        lookup = ("workforce", "Position", "position_id")
    if lookup is None:
        return None
    app_label, model_name, field = lookup
    model = apps.get_model(app_label, model_name)
    try:
        target = model.objects.get(pk=configuration[field])
    except (model.DoesNotExist, ValueError, TypeError, KeyError):
        return ValidationIssue(
            "routing_target_missing",
            "هدف مسیریابی وجود ندارد یا معتبر نیست.",
            f"routing.{rule.pk}",
        )
    if target.organization_id != rule.organization_id:
        return ValidationIssue(
            "routing_target_cross_tenant",
            "هدف مسیریابی متعلق به سازمان دیگری است.",
            f"routing.{rule.pk}",
        )
    if hasattr(target, "status") and target.status != "active":
        return ValidationIssue(
            "routing_target_inactive",
            "هدف مسیریابی فعال نیست.",
            f"routing.{rule.pk}",
        )
    if hasattr(target, "is_active") and not target.is_active:
        return ValidationIssue(
            "routing_target_inactive",
            "هدف مسیریابی فعال نیست.",
            f"routing.{rule.pk}",
        )
    return None


def validate_workflow_version(version: Any) -> list[ValidationIssue]:
    """Return deterministic publication errors without mutating the version."""

    issues: list[ValidationIssue] = []
    workflow_type = registry.workflow_types.get(version.definition.workflow_type.code)
    if workflow_type is None:
        return [
            ValidationIssue("workflow_type_unregistered", "نوع گردش‌کار ثبت نشده است.")
        ]

    steps = list(version.steps.all())
    transitions = list(version.transitions.prefetch_related("conditions"))
    routing_rules = list(version.routing_rules.select_related("step"))
    step_by_key = {step.key: step for step in steps}
    starts = [step for step in steps if step.is_start]
    terminals = [step for step in steps if step.is_terminal]
    if len(starts) != 1:
        issues.append(
            ValidationIssue(
                "invalid_start", "گردش‌کار باید دقیقاً یک گام شروع داشته باشد."
            )
        )
    if not terminals:
        issues.append(
            ValidationIssue(
                "missing_terminal", "گردش‌کار باید حداقل یک گام پایانی داشته باشد."
            )
        )

    adjacency = {key: set() for key in step_by_key}
    outgoing: dict[str, list[Any]] = {key: [] for key in step_by_key}
    for transition in transitions:
        if transition.source_step_id not in {
            step.pk for step in steps
        } or transition.target_step_id not in {step.pk for step in steps}:
            issues.append(
                ValidationIssue(
                    "cross_version_transition", "انتقال میان نسخه‌ها مجاز نیست."
                )
            )
            continue
        adjacency[transition.source_step.key].add(transition.target_step.key)
        outgoing[transition.source_step.key].append(transition)
        if transition.domain_command:
            command = registry.domain_commands.get(transition.domain_command)
            if command is None or command.workflow_type != workflow_type.code:
                issues.append(
                    ValidationIssue(
                        "command_unregistered",
                        f"فرمان انتقال {transition.outcome} ثبت نشده است.",
                    )
                )
        if transition.required_permission and transition.required_permission not in set(
            BusinessPermission.objects.filter(is_active=True).values_list(
                "code", flat=True
            )
        ):
            issues.append(
                ValidationIssue(
                    "permission_missing",
                    f"مجوز انتقال {transition.outcome} فعال نیست.",
                )
            )
    if starts:
        reachable: set[str] = set()
        pending = [starts[0].key]
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(adjacency.get(current, set()) - reachable)
        for key in sorted(set(step_by_key) - reachable):
            issues.append(
                ValidationIssue(
                    "unreachable_step", f"گام {key} قابل دسترسی نیست.", f"steps.{key}"
                )
            )
    if _has_invalid_cycle(adjacency):
        issues.append(
            ValidationIssue("invalid_cycle", "چرخه در graph این نسخه مجاز نیست.")
        )

    active_permissions = set(
        BusinessPermission.objects.filter(is_active=True).values_list("code", flat=True)
    )
    rules_by_step: dict[Any, list[Any]] = {}
    for rule in routing_rules:
        rules_by_step.setdefault(rule.step_id, []).append(rule)
        specification = registry.routing_resolvers.get(rule.resolver_type)
        if specification is None:
            issues.append(
                ValidationIssue("routing_unregistered", "نوع مسیریاب ثبت نشده است.")
            )
            continue
        try:
            specification.schema.validate(rule.configuration, label="پیکربندی مسیریابی")
        except ValidationError as error:
            issues.append(ValidationIssue("routing_schema", "; ".join(error.messages)))
        target_issue = _routing_target_issue(rule)
        if target_issue:
            issues.append(target_issue)

    for step in steps:
        specification = registry.step_types.get(step.step_type)
        if specification is None:
            issues.append(
                ValidationIssue(
                    "step_type_unregistered", f"نوع گام {step.key} ثبت نشده است."
                )
            )
            continue
        try:
            specification.schema.validate(step.configuration, label="پیکربندی گام")
        except ValidationError as error:
            issues.append(
                ValidationIssue(
                    "step_schema", "; ".join(error.messages), f"steps.{step.key}"
                )
            )
        if step.domain_command:
            command = registry.domain_commands.get(step.domain_command)
            if command is None or command.workflow_type != workflow_type.code:
                issues.append(
                    ValidationIssue(
                        "command_unregistered", f"فرمان گام {step.key} ثبت نشده است."
                    )
                )
            elif not specification.allows_command:
                issues.append(
                    ValidationIssue(
                        "command_not_allowed", f"گام {step.key} فرمان دامنه نمی‌پذیرد."
                    )
                )
        if (
            step.required_permission
            and step.required_permission not in active_permissions
        ):
            issues.append(
                ValidationIssue("permission_missing", f"مجوز گام {step.key} فعال نیست.")
            )
        step_rules = rules_by_step.get(step.pk, [])
        if specification.requires_routing and not step_rules:
            issues.append(
                ValidationIssue("routing_missing", f"گام {step.key} مسیریابی ندارد.")
            )
        if any(
            registry.routing_resolvers[r.resolver_type].requires_fallback
            for r in step_rules
            if r.resolver_type in registry.routing_resolvers
        ) and not any(rule.is_fallback for rule in step_rules):
            issues.append(
                ValidationIssue(
                    "routing_fallback_missing", f"گام {step.key} fallback ندارد."
                )
            )
        if step.is_terminal and outgoing[step.key]:
            issues.append(
                ValidationIssue(
                    "terminal_has_transition", f"گام پایانی {step.key} خروجی دارد."
                )
            )
        if not step.is_terminal and not outgoing[step.key]:
            issues.append(
                ValidationIssue("dead_end", f"گام {step.key} مسیر خروجی ندارد.")
            )
        defaults = [
            transition for transition in outgoing[step.key] if transition.is_default
        ]
        unconditional = [
            transition
            for transition in outgoing[step.key]
            if transition.is_default or not list(transition.conditions.all())
        ]
        if len(defaults) > 1 or (
            step.step_type != "approval" and len(unconditional) > 1
        ):
            issues.append(
                ValidationIssue(
                    "ambiguous_transition", f"انتقال‌های گام {step.key} مبهم هستند."
                )
            )

    adapter = registry.subject_adapters.get(workflow_type.subject_adapter)
    for transition in transitions:
        for condition in transition.conditions.all():
            specification = registry.condition_types.get(condition.condition_type)
            if specification is None:
                issues.append(
                    ValidationIssue("condition_unregistered", "نوع شرط ثبت نشده است.")
                )
                continue
            try:
                specification.schema.validate(
                    condition.configuration, label="پیکربندی شرط"
                )
            except ValidationError as error:
                issues.append(
                    ValidationIssue("condition_schema", "; ".join(error.messages))
                )
            attribute = condition.configuration.get("attribute")
            if attribute and (
                adapter is None or attribute not in adapter.exposed_attributes
            ):
                issues.append(
                    ValidationIssue(
                        "subject_attribute_unregistered",
                        f"ویژگی {attribute} ثبت نشده است.",
                    )
                )

    definition = version.definition
    peers = (
        type(definition)
        .objects.filter(
            organization=version.organization,
            workflow_type=definition.workflow_type,
            versions__status="published",
        )
        .exclude(pk=definition.pk)
        .distinct()
    )
    for peer in peers:
        if len(peer.scope) == len(definition.scope) and _scopes_overlap(
            peer.scope, definition.scope
        ):
            issues.append(
                ValidationIssue(
                    "scope_ambiguity", f"محدوده با تعریف {peer.code} مبهم است."
                )
            )
    return issues


def evaluate_condition(
    condition_type: str, configuration: dict[str, Any], context: dict[str, Any]
) -> bool:
    if condition_type == "always":
        return True
    if condition_type == "subject_attribute_equals":
        return context.get(configuration["attribute"]) == configuration["value"]
    if condition_type == "amount_threshold":
        try:
            left = Decimal(str(context.get("amount")))
            right = Decimal(str(configuration["amount"]))
        except (InvalidOperation, TypeError):
            return False
        return {
            "eq": left == right,
            "gt": left > right,
            "gte": left >= right,
            "lt": left < right,
            "lte": left <= right,
        }[configuration["operator"]]
    raise ValidationError("نوع شرط ثبت نشده است.")
