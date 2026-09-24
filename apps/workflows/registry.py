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
        key="estimates.estimate",
        subject_type="estimates.estimate",
        exposed_attributes=frozenset(
            {
                "project_id",
                "phase_id",
                "contract_id",
                "status",
                "current_revision_id",
                "created_by_id",
            }
        ),
        start_permission="estimates.revise",
        view_permission="estimates.view",
        detail_url_name="estimates:detail",
        detail_url_kwarg="estimate_id",
    )
)
registry.register_workflow_type(
    WorkflowTypeSpec(
        code="estimates.estimate_approval",
        subject_type="estimates.estimate",
        subject_adapter="estimates.estimate",
        allowed_scope_fields=frozenset({"project_id", "phase_id", "contract_id"}),
        domain_commands=frozenset({"estimates.estimate.approve"}),
    )
)
registry.register_domain_command(
    DomainCommandSpec(
        key="estimates.estimate.approve",
        workflow_type="estimates.estimate_approval",
        from_states=frozenset({"draft"}),
        to_state="approved",
    )
)
registry.register_subject_adapter(
    SubjectAdapterSpec(
        key="contracts.contract_amendment",
        subject_type="contracts.contract_amendment",
        exposed_attributes=frozenset(
            {"project_id", "contract_id", "status", "created_by_id"}
        ),
        start_permission="contracts.change",
        view_permission="contracts.view",
    )
)
registry.register_workflow_type(
    WorkflowTypeSpec(
        code="contracts.contract_amendment_approval",
        subject_type="contracts.contract_amendment",
        subject_adapter="contracts.contract_amendment",
        allowed_scope_fields=frozenset({"project_id", "contract_id"}),
        domain_commands=frozenset({"contracts.contract_amendment.approve"}),
    )
)
registry.register_domain_command(
    DomainCommandSpec(
        key="contracts.contract_amendment.approve",
        workflow_type="contracts.contract_amendment_approval",
        from_states=frozenset({"draft"}),
        to_state="approved",
    )
)
registry.register_subject_adapter(
    SubjectAdapterSpec(
        key="billing.project_baseline",
        subject_type="billing.project_baseline",
        exposed_attributes=frozenset(
            {"project_id", "contract_id", "status", "version", "created_by_id"}
        ),
        start_permission="baselines.manage",
        view_permission="baselines.view",
    )
)
registry.register_workflow_type(
    WorkflowTypeSpec(
        code="billing.project_baseline_approval",
        subject_type="billing.project_baseline",
        subject_adapter="billing.project_baseline",
        allowed_scope_fields=frozenset({"project_id", "contract_id"}),
        domain_commands=frozenset({"billing.project_baseline.approve"}),
    )
)
registry.register_domain_command(
    DomainCommandSpec(
        key="billing.project_baseline.approve",
        workflow_type="billing.project_baseline_approval",
        from_states=frozenset({"draft"}),
        to_state="approved",
    )
)
registry.register_subject_adapter(
    SubjectAdapterSpec(
        key="billing.progress_record",
        subject_type="billing.progress_record",
        exposed_attributes=frozenset(
            {
                "project_id",
                "contract_id",
                "baseline_id",
                "baseline_item_id",
                "status",
                "created_by_id",
            }
        ),
        start_permission="progress.record",
        view_permission="progress.view",
        detail_url_name="billing:progress_detail",
        detail_url_kwarg="record_id",
    )
)
registry.register_workflow_type(
    WorkflowTypeSpec(
        code="billing.progress_verification",
        subject_type="billing.progress_record",
        subject_adapter="billing.progress_record",
        allowed_scope_fields=frozenset({"project_id", "contract_id", "baseline_id"}),
        domain_commands=frozenset(
            {"billing.progress.verify", "billing.progress.reject"}
        ),
    )
)
for command_key, to_state in (
    ("billing.progress.verify", "verified"),
    ("billing.progress.reject", "rejected"),
):
    registry.register_domain_command(
        DomainCommandSpec(
            key=command_key,
            workflow_type="billing.progress_verification",
            from_states=frozenset({"submitted"}),
            to_state=to_state,
        )
    )
registry.register_subject_adapter(
    SubjectAdapterSpec(
        key="billing.progress_claim",
        subject_type="billing.progress_claim",
        exposed_attributes=frozenset(
            {
                "project_id",
                "contract_id",
                "baseline_id",
                "status",
                "claim_number",
                "revision_number",
                "created_by_id",
                "submitted_by_id",
            }
        ),
        start_permission="claims.submit",
        view_permission="claims.view",
    )
)
registry.register_workflow_type(
    WorkflowTypeSpec(
        code="billing.progress_claim_approval",
        subject_type="billing.progress_claim",
        subject_adapter="billing.progress_claim",
        allowed_scope_fields=frozenset({"project_id", "contract_id", "baseline_id"}),
        domain_commands=frozenset(
            {"billing.progress_claim.approve", "billing.progress_claim.return"}
        ),
    )
)
for command_key, to_state in (
    ("billing.progress_claim.approve", "approved"),
    ("billing.progress_claim.return", "returned"),
):
    registry.register_domain_command(
        DomainCommandSpec(
            key=command_key,
            workflow_type="billing.progress_claim_approval",
            from_states=frozenset({"submitted"}),
            to_state=to_state,
        )
    )
registry.register_subject_adapter(
    SubjectAdapterSpec(
        key="inventory.stock_transaction",
        subject_type="inventory.stock_transaction",
        exposed_attributes=frozenset(
            {"project_id", "transaction_type", "status", "created_by_id"}
        ),
        # Posting and reversal have distinct service-bound start permissions.
        start_permission="",
        view_permission="stock_transactions.view",
        detail_url_name="inventory:transaction_detail",
        detail_url_kwarg="transaction_id",
    )
)
for workflow_code, command_key, from_state, to_state in (
    (
        "inventory.stock_transaction_posting",
        "inventory.stock_transaction.post",
        "draft",
        "posted",
    ),
    (
        "inventory.stock_transaction_reversal",
        "inventory.stock_transaction.reverse",
        "posted",
        "reversed",
    ),
):
    registry.register_workflow_type(
        WorkflowTypeSpec(
            code=workflow_code,
            subject_type="inventory.stock_transaction",
            subject_adapter="inventory.stock_transaction",
            allowed_scope_fields=frozenset({"project_id", "transaction_type"}),
            domain_commands=frozenset({command_key}),
        )
    )
    registry.register_domain_command(
        DomainCommandSpec(
            key=command_key,
            workflow_type=workflow_code,
            from_states=frozenset({from_state}),
            to_state=to_state,
        )
    )
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
registry.register_subject_adapter(
    SubjectAdapterSpec(
        key="equipment.maintenance_record",
        subject_type="equipment.maintenance_record",
        exposed_attributes=frozenset(
            {
                "project_id",
                "site_id",
                "maintenance_type",
                "status",
                "scheduled_date",
                "created_by_id",
            }
        ),
        # Starting an assignment does not itself perform a maintenance state
        # change; the domain command rechecks the transition permission later.
        start_permission="maintenance_records.view",
        view_permission="maintenance_records.view",
        detail_url_name="equipment:maintenance_status_change",
        detail_url_kwarg="record_id",
    )
)
registry.register_workflow_type(
    WorkflowTypeSpec(
        code="equipment.maintenance_record_lifecycle",
        subject_type="equipment.maintenance_record",
        subject_adapter="equipment.maintenance_record",
        allowed_scope_fields=frozenset({"project_id", "site_id", "maintenance_type"}),
        domain_commands=frozenset(
            {
                "equipment.maintenance_record.start",
                "equipment.maintenance_record.complete",
                "equipment.maintenance_record.cancel",
            }
        ),
    )
)
for command_key, from_states, to_state in (
    (
        "equipment.maintenance_record.start",
        frozenset({"scheduled"}),
        "in_progress",
    ),
    (
        "equipment.maintenance_record.complete",
        frozenset({"scheduled", "in_progress"}),
        "completed",
    ),
    (
        "equipment.maintenance_record.cancel",
        frozenset({"scheduled", "in_progress"}),
        "cancelled",
    ),
):
    registry.register_domain_command(
        DomainCommandSpec(
            key=command_key,
            workflow_type="equipment.maintenance_record_lifecycle",
            from_states=from_states,
            to_state=to_state,
        )
    )
registry.register_subject_adapter(
    SubjectAdapterSpec(
        key="daily_reports.daily_report",
        subject_type="daily_reports.daily_report",
        exposed_attributes=frozenset(
            {"project_id", "site_id", "status", "created_by_id"}
        ),
        start_permission="daily_reports.submit",
        view_permission="daily_reports.view",
        detail_url_name="daily_reports:detail",
        detail_url_kwarg="report_id",
    )
)
registry.register_subject_adapter(
    SubjectAdapterSpec(
        key="safety.safety_incident",
        subject_type="safety.safety_incident",
        exposed_attributes=frozenset(
            {
                "project_id",
                "site_id",
                "status",
                "created_by_id",
                "responsible_display",
            }
        ),
        start_permission="safety_incidents.view",
        view_permission="safety_incidents.view",
        detail_url_name="safety:detail",
        detail_url_kwarg="incident_id",
    )
)
registry.register_workflow_type(
    WorkflowTypeSpec(
        code="safety.safety_incident_lifecycle",
        subject_type="safety.safety_incident",
        subject_adapter="safety.safety_incident",
        allowed_scope_fields=frozenset({"project_id", "site_id"}),
        domain_commands=frozenset(
            f"safety.safety_incident.{action}"
            for action in ("review", "assign", "start_action", "resolve", "close")
        ),
    )
)
for action, from_state, to_state in (
    ("review", "reported", "under_review"),
    ("assign", "under_review", "assigned"),
    ("start_action", "assigned", "action_in_progress"),
    ("resolve", "action_in_progress", "resolved"),
    ("close", "resolved", "closed"),
):
    registry.register_domain_command(
        DomainCommandSpec(
            key=f"safety.safety_incident.{action}",
            workflow_type="safety.safety_incident_lifecycle",
            from_states=frozenset({from_state}),
            to_state=to_state,
        )
    )
registry.register_subject_adapter(
    SubjectAdapterSpec(
        key="quality.quality_issue",
        subject_type="quality.quality_issue",
        exposed_attributes=frozenset(
            {
                "project_id",
                "site_id",
                "status",
                "created_by_id",
                "responsible_display",
            }
        ),
        start_permission="quality_issues.view",
        view_permission="quality_issues.view",
        detail_url_name="quality:detail",
        detail_url_kwarg="issue_id",
    )
)
registry.register_workflow_type(
    WorkflowTypeSpec(
        code="quality.quality_issue_lifecycle",
        subject_type="quality.quality_issue",
        subject_adapter="quality.quality_issue",
        allowed_scope_fields=frozenset({"project_id", "site_id"}),
        domain_commands=frozenset(
            f"quality.quality_issue.{action}"
            for action in (
                "review",
                "assign",
                "start_action",
                "submit_for_verification",
                "verify",
                "close",
            )
        ),
    )
)
for action, from_state, to_state in (
    ("review", "reported", "under_review"),
    ("assign", "under_review", "assigned"),
    ("start_action", "assigned", "action_in_progress"),
    ("submit_for_verification", "action_in_progress", "awaiting_verification"),
    ("verify", "awaiting_verification", "verified"),
    ("close", "verified", "closed"),
):
    registry.register_domain_command(
        DomainCommandSpec(
            key=f"quality.quality_issue.{action}",
            workflow_type="quality.quality_issue_lifecycle",
            from_states=frozenset({from_state}),
            to_state=to_state,
        )
    )
registry.register_workflow_type(
    WorkflowTypeSpec(
        code="daily_reports.daily_report_approval",
        subject_type="daily_reports.daily_report",
        subject_adapter="daily_reports.daily_report",
        allowed_scope_fields=frozenset({"project_id", "site_id"}),
        domain_commands=frozenset(
            {
                "daily_reports.daily_report.submit",
                "daily_reports.daily_report.approve",
            }
        ),
    )
)
for command_key, from_state, to_state in (
    ("daily_reports.daily_report.submit", "draft", "submitted"),
    ("daily_reports.daily_report.approve", "submitted", "approved"),
):
    registry.register_domain_command(
        DomainCommandSpec(
            key=command_key,
            workflow_type="daily_reports.daily_report_approval",
            from_states=frozenset({from_state}),
            to_state=to_state,
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
                "allow_submitter_if_no_other_candidate": ConfigField(bool),
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
        schema=ConfigSchema(
            fields={
                "permission": ConfigField(str, required=True),
                "exclude_submitter_unless_no_other": ConfigField(bool),
            }
        ),
        requires_fallback=True,
    )
)
registry.register_routing_resolver(
    RoutingResolverSpec(
        key="submitter_primary_position_manager",
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
