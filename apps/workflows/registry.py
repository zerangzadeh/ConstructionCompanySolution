from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError

_FORBIDDEN_KEYS = frozenset(
    {"code", "expression", "javascript", "network", "python", "sql", "template", "url"}
)


@dataclass(frozen=True, slots=True)
class ConfigField:
    value_type: type | tuple[type, ...]
    required: bool = False
    choices: frozenset[object] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ConfigSchema:
    fields: dict[str, ConfigField] = field(default_factory=dict)
    allow_extra: bool = False

    def validate(self, value: object, *, label: str) -> None:
        if not isinstance(value, dict):
            raise ValidationError(f"{label} باید یک شیء JSON باشد.")
        _reject_executable_content(value, label=label)
        unknown = set(value) - set(self.fields)
        if unknown and not self.allow_extra:
            raise ValidationError(
                f"کلیدهای ثبت‌نشده در {label}: {', '.join(sorted(unknown))}"
            )
        for name, specification in self.fields.items():
            if specification.required and name not in value:
                raise ValidationError(f"فیلد {name} در {label} الزامی است.")
            if name not in value:
                continue
            candidate = value[name]
            allowed_types = specification.value_type
            allowed_types = (
                allowed_types if isinstance(allowed_types, tuple) else (allowed_types,)
            )
            if isinstance(candidate, bool) and bool not in allowed_types:
                raise ValidationError(f"نوع فیلد {name} در {label} معتبر نیست.")
            if not isinstance(candidate, specification.value_type):
                raise ValidationError(f"نوع فیلد {name} در {label} معتبر نیست.")
            if specification.choices and candidate not in specification.choices:
                raise ValidationError(f"مقدار فیلد {name} در {label} ثبت نشده است.")


def _reject_executable_content(value: object, *, label: str) -> None:
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key).casefold()
            if key in _FORBIDDEN_KEYS or any(
                part in key for part in ("script", "query")
            ):
                raise ValidationError(f"محتوای اجرایی در {label} مجاز نیست.")
            _reject_executable_content(nested, label=label)
    elif isinstance(value, list):
        for nested in value:
            _reject_executable_content(nested, label=label)


@dataclass(frozen=True, slots=True)
class SubjectSnapshot:
    subject: Any
    subject_id: str
    organization_id: str
    attributes: dict[str, object] = field(default_factory=dict)
    creator_membership_id: str | None = None
    submitter_membership_id: str | None = None
    display: str = ""


SubjectLoader = Callable[..., SubjectSnapshot]
DomainCommandExecutor = Callable[..., object]


@dataclass(frozen=True, slots=True)
class WorkflowTypeSpec:
    code: str
    subject_type: str
    subject_adapter: str
    allowed_scope_fields: frozenset[str]
    domain_commands: frozenset[str]


@dataclass(frozen=True, slots=True)
class SubjectAdapterSpec:
    key: str
    subject_type: str
    exposed_attributes: frozenset[str]
    loader: SubjectLoader | None = None
    start_permission: str = ""
    view_permission: str = ""
    detail_url_name: str = ""
    detail_url_kwarg: str = "subject_id"


@dataclass(frozen=True, slots=True)
class DomainCommandSpec:
    key: str
    workflow_type: str
    from_states: frozenset[str] = field(default_factory=frozenset)
    to_state: str = ""
    executor: DomainCommandExecutor | None = None


@dataclass(frozen=True, slots=True)
class StepTypeSpec:
    key: str
    schema: ConfigSchema = field(default_factory=ConfigSchema)
    requires_routing: bool = False
    allows_command: bool = False


@dataclass(frozen=True, slots=True)
class ConditionTypeSpec:
    key: str
    schema: ConfigSchema


@dataclass(frozen=True, slots=True)
class RoutingResolverSpec:
    key: str
    schema: ConfigSchema
    requires_fallback: bool = False


class WorkflowRegistry:
    """Code-owned allow-list. Tenant data can reference but cannot extend it."""

    def __init__(self) -> None:
        self.workflow_types: dict[str, WorkflowTypeSpec] = {}
        self.subject_adapters: dict[str, SubjectAdapterSpec] = {}
        self.domain_commands: dict[str, DomainCommandSpec] = {}
        self.step_types: dict[str, StepTypeSpec] = {}
        self.condition_types: dict[str, ConditionTypeSpec] = {}
        self.routing_resolvers: dict[str, RoutingResolverSpec] = {}

    @staticmethod
    def _register(target: dict[str, Any], key: str, specification: Any) -> None:
        if key in target:
            raise RuntimeError(f"نوع registry تکراری است: {key}")
        target[key] = specification

    def register_workflow_type(self, specification: WorkflowTypeSpec) -> None:
        self._register(self.workflow_types, specification.code, specification)

    def register_subject_adapter(self, specification: SubjectAdapterSpec) -> None:
        self._register(self.subject_adapters, specification.key, specification)

    def register_domain_command(self, specification: DomainCommandSpec) -> None:
        self._register(self.domain_commands, specification.key, specification)

    def register_step_type(self, specification: StepTypeSpec) -> None:
        self._register(self.step_types, specification.key, specification)

    def register_condition_type(self, specification: ConditionTypeSpec) -> None:
        self._register(self.condition_types, specification.key, specification)

    def register_routing_resolver(self, specification: RoutingResolverSpec) -> None:
        self._register(self.routing_resolvers, specification.key, specification)

    def bind_subject_loader(self, key: str, loader: SubjectLoader) -> None:
        """Bind a code-owned runtime adapter without changing tenant configuration."""
        specification = self.subject_adapters[key]
        self.subject_adapters[key] = replace(specification, loader=loader)

    def bind_domain_command(self, key: str, executor: DomainCommandExecutor) -> None:
        """Bind a domain application-service callback to a registered command."""
        specification = self.domain_commands[key]
        self.domain_commands[key] = replace(specification, executor=executor)


registry = WorkflowRegistry()

registry.register_subject_adapter(
    SubjectAdapterSpec(
        key="procurement.purchase_request",
        subject_type="procurement.purchase_request",
        exposed_attributes=frozenset({"project_id", "status", "created_by_id"}),
        start_permission="purchase_requests.submit",
        view_permission="purchase_requests.view",
        detail_url_name="procurement:request_detail",
        detail_url_kwarg="request_id",
    )
)
registry.register_workflow_type(
    WorkflowTypeSpec(
        code="procurement.purchase_request_approval",
        subject_type="procurement.purchase_request",
        subject_adapter="procurement.purchase_request",
        allowed_scope_fields=frozenset({"project_id"}),
        domain_commands=frozenset(
            {
                "procurement.purchase_request.submit",
                "procurement.purchase_request.approve",
                "procurement.purchase_request.reject",
                "procurement.purchase_request.cancel",
            }
        ),
    )
)
for command_key, from_states, to_state in (
    ("procurement.purchase_request.submit", frozenset({"draft"}), "submitted"),
    (
        "procurement.purchase_request.approve",
        frozenset({"submitted"}),
        "approved",
    ),
    (
        "procurement.purchase_request.reject",
        frozenset({"submitted"}),
        "rejected",
    ),
    (
        "procurement.purchase_request.cancel",
        frozenset({"draft", "submitted"}),
        "cancelled",
    ),
):
    registry.register_domain_command(
        DomainCommandSpec(
            key=command_key,
            workflow_type="procurement.purchase_request_approval",
            from_states=from_states,
            to_state=to_state,
        )
    )

registry.register_step_type(StepTypeSpec(key="start"))
registry.register_step_type(
    StepTypeSpec(
        key="approval",
        schema=ConfigSchema(
            fields={
                "decision_policy": ConfigField(
                    str,
                    choices=frozenset({"any", "all", "minimum_count"}),
                ),
                "minimum_approvals": ConfigField(int),
                "due_hours": ConfigField(int),
                "priority": ConfigField(int),
                "exclude_creator": ConfigField(bool),
                "exclude_submitter": ConfigField(bool),
                "exclude_starter": ConfigField(bool),
            }
        ),
        requires_routing=True,
        allows_command=True,
    )
)
registry.register_step_type(StepTypeSpec(key="end"))

registry.register_condition_type(ConditionTypeSpec(key="always", schema=ConfigSchema()))
registry.register_condition_type(
    ConditionTypeSpec(
        key="subject_attribute_equals",
        schema=ConfigSchema(
            fields={
                "attribute": ConfigField(str, required=True),
                "value": ConfigField((str, int, bool), required=True),
            }
        ),
    )
)
registry.register_condition_type(
    ConditionTypeSpec(
        key="amount_threshold",
        schema=ConfigSchema(
            fields={
                "operator": ConfigField(
                    str,
                    required=True,
                    choices=frozenset({"eq", "gt", "gte", "lt", "lte"}),
                ),
                "amount": ConfigField((str, int, Decimal), required=True),
            }
        ),
    )
)

registry.register_routing_resolver(
    RoutingResolverSpec(key="organization_owner", schema=ConfigSchema())
)
registry.register_routing_resolver(
    RoutingResolverSpec(
        key="business_permission",
        schema=ConfigSchema(fields={"permission": ConfigField(str, required=True)}),
        requires_fallback=True,
    )
)
registry.register_routing_resolver(
    RoutingResolverSpec(
        key="explicit_membership",
        schema=ConfigSchema(fields={"membership_id": ConfigField(str, required=True)}),
        requires_fallback=True,
    )
)
registry.register_routing_resolver(
    RoutingResolverSpec(
        key="work_team",
        schema=ConfigSchema(
            fields={
                "work_team_id": ConfigField(str, required=True),
                "mode": ConfigField(
                    str,
                    required=True,
                    choices=frozenset({"lead", "members"}),
                ),
            }
        ),
        requires_fallback=True,
    )
)
registry.register_routing_resolver(
    RoutingResolverSpec(
        key="record_creator", schema=ConfigSchema(), requires_fallback=True
    )
)
registry.register_routing_resolver(
    RoutingResolverSpec(
        key="record_submitter", schema=ConfigSchema(), requires_fallback=True
    )
)
registry.register_routing_resolver(
    RoutingResolverSpec(
        key="organization_role",
        schema=ConfigSchema(fields={"role_code": ConfigField(str, required=True)}),
        requires_fallback=True,
    )
)
registry.register_routing_resolver(
    RoutingResolverSpec(
        key="position",
        schema=ConfigSchema(fields={"position_id": ConfigField(str, required=True)}),
        requires_fallback=True,
    )
)
