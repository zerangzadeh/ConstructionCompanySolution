from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import (
    get_active_membership,
    membership_has_permission,
    membership_has_scope,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.projects.models import Project, ProjectSite

from .models import (
    WorkflowDelegation,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowStepDefinition,
    WorkflowStepInstance,
    WorkflowStepInstanceStatus,
    WorkflowTransitionDefinition,
    WorkflowType,
    WorkflowVersion,
    WorkflowVersionStatus,
    WorkItem,
    WorkItemAssignmentAction,
    WorkItemAssignmentHistory,
    WorkItemCandidate,
    WorkItemStatus,
)
from .registry import SubjectSnapshot, registry
from .routing import ResolvedCandidate, resolve_step_candidates
from .scope import scope_work_item_queryset, workflow_scope_objects
from .validators import evaluate_condition, validate_workflow_version


class WorkflowConflict(ValidationError):
    """A stale or competing runtime mutation lost a deterministic race."""


def _require_membership(
    *, actor: User, organization: Organization
) -> OrganizationMembership:
    # Runtime evidence always names a tenant membership, including for staff users.
    return get_active_membership(user=actor, organization=organization)


def _require_permission(
    *,
    actor: User,
    organization: Organization,
    permission: str | BusinessPermissionCode,
    project: Any | None = None,
    site: Any | None = None,
    allow_any_scope: bool = False,
) -> OrganizationMembership:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="مجوز لازم برای عملیات گردش‌کار را ندارید.",
        project=project,
        site=site,
        allow_any_scope=allow_any_scope,
    )
    return membership


def _require_instance_permission(
    *,
    actor: User,
    organization: Organization,
    instance: WorkflowInstance,
    permission: str | BusinessPermissionCode,
) -> OrganizationMembership:
    project, site = workflow_scope_objects(instance)
    return _require_permission(
        actor=actor,
        organization=organization,
        permission=permission,
        project=project,
        site=site,
    )


def _lock_membership_authority(
    *, organization: Organization, membership_id: object
) -> None:
    """Linearize a runtime decision with role/grant assignment and revocation."""

    try:
        OrganizationMembership.objects.select_for_update().get(
            pk=membership_id,
            organization=organization,
            status=MembershipStatus.ACTIVE,
            user__is_active=True,
        )
    except (ValueError, OrganizationMembership.DoesNotExist) as exc:
        raise PermissionDenied("عضویت فعال و متعلق به این سازمان یافت نشد.") from exc
    list(
        MembershipRoleAssignment.objects.select_for_update()
        .filter(membership_id=membership_id, revoked_at__isnull=True)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    list(
        MembershipScopeGrant.objects.select_for_update()
        .filter(membership_id=membership_id, revoked_at__isnull=True)
        .order_by("pk")
        .values_list("pk", flat=True)
    )


def _audit(
    *,
    action: str,
    entity_type: str,
    entity_id: object,
    organization: Organization,
    actor: User,
    actor_membership: OrganizationMembership,
    metadata: dict[str, Any] | None = None,
) -> None:
    record_audit_event(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        organization=organization,
        actor=actor,
        metadata={
            "actor_membership_id": str(actor_membership.pk),
            **(metadata or {}),
        },
    )


def _idempotency_key(*parts: object) -> str:
    return sha256(":".join(str(item) for item in parts).encode()).hexdigest()


def _load_subject(
    *,
    organization: Organization,
    version: WorkflowVersion,
    subject_id: UUID,
    actor: User,
    for_update: bool,
    check_start_permission: bool = False,
) -> SubjectSnapshot:
    workflow_spec = registry.workflow_types.get(version.definition.workflow_type.code)
    if workflow_spec is None:
        raise ValidationError("نوع گردش‌کار در کد ثبت نشده است.")
    adapter = registry.subject_adapters.get(workflow_spec.subject_adapter)
    if adapter is None or adapter.loader is None:
        raise ValidationError("آداپتور runtime این دامنه هنوز ثبت نشده است.")
    snapshot = adapter.loader(
        organization=organization,
        subject_id=subject_id,
        actor=actor,
        for_update=for_update,
    )
    if str(snapshot.organization_id) != str(organization.pk):
        raise PermissionDenied("موضوع متعلق به سازمان دیگری است.")
    if str(snapshot.subject_id) != str(subject_id):
        raise ValidationError("آداپتور شناسه موضوع ناسازگار برگرداند.")
    unknown = set(snapshot.attributes) - set(adapter.exposed_attributes)
    if unknown:
        raise ValidationError("آداپتور ویژگی ثبت‌نشده برگرداند.")
    if check_start_permission and adapter.start_permission:
        scope_instance = WorkflowInstance(
            organization=organization, subject_context=dict(snapshot.attributes)
        )
        project, site = workflow_scope_objects(scope_instance)
        if (snapshot.attributes.get("project_id") and project is None) or (
            snapshot.attributes.get("site_id") and site is None
        ):
            raise PermissionDenied("دامنه موضوع گردش‌کار معتبر نیست.")
        _require_permission(
            actor=actor,
            organization=organization,
            permission=adapter.start_permission,
            project=project,
            site=site,
        )
    return snapshot


def _subject_context(
    *, snapshot: SubjectSnapshot, starter: OrganizationMembership
) -> dict[str, Any]:
    context = dict(snapshot.attributes)
    context.update(
        {
            "creator_membership_id": snapshot.creator_membership_id,
            "submitter_membership_id": snapshot.submitter_membership_id,
            "starter_membership_id": str(starter.pk),
            "subject_display": snapshot.display,
        }
    )
    return context


def _raw_update(queryset: models.QuerySet, **values: object) -> int:
    return models.QuerySet.update(queryset, **values)


def _operation_already_processed(
    *, instance: WorkflowInstance, idempotency_key: str, action: str
) -> bool:
    if not idempotency_key.strip():
        raise ValidationError("کلید تکرارپذیری عملیات الزامی است.")
    previous_action = instance.processed_operations.get(idempotency_key)
    if previous_action and previous_action != action:
        raise ValidationError("کلید تکرارپذیری برای عملیات دیگری استفاده شده است.")
    return previous_action == action


def _processed_operations(
    *, instance: WorkflowInstance, idempotency_key: str, action: str
) -> dict[str, str]:
    values = dict(instance.processed_operations)
    values[idempotency_key] = action
    return values


def _history(
    *,
    work_item: WorkItem,
    action: WorkItemAssignmentAction,
    actor_membership: OrganizationMembership,
    idempotency_key: str,
    previous_state: str,
    new_state: str,
    from_membership: OrganizationMembership | None = None,
    to_membership: OrganizationMembership | None = None,
    position_assignment_id: object | None = None,
    permission_code: str = "",
    reason: str = "",
    outcome: str = "",
    metadata: dict[str, Any] | None = None,
) -> WorkItemAssignmentHistory:
    return WorkItemAssignmentHistory.objects.create(
        organization_id=work_item.organization_id,
        work_item=work_item,
        action=action,
        actor_membership=actor_membership,
        from_membership=from_membership,
        to_membership=to_membership,
        qualifying_position_assignment_id=position_assignment_id,
        permission_code=permission_code,
        reason=reason,
        previous_state=previous_state,
        new_state=new_state,
        outcome=outcome,
        metadata=metadata or {},
        idempotency_key=idempotency_key,
    )


def _matching_transition(
    *,
    step: WorkflowStepDefinition,
    outcome: str | None,
    subject_context: dict[str, Any],
) -> WorkflowTransitionDefinition:
    transitions = list(
        WorkflowTransitionDefinition.objects.filter(
            organization_id=step.organization_id,
            version_id=step.version_id,
            source_step=step,
        )
        .prefetch_related("conditions")
        .order_by("priority", "pk")
    )
    if outcome is not None:
        transitions = [item for item in transitions if item.outcome == outcome]
    matched: list[WorkflowTransitionDefinition] = []
    defaults: list[WorkflowTransitionDefinition] = []
    for candidate in transitions:
        if candidate.is_default:
            defaults.append(candidate)
            continue
        conditions = list(candidate.conditions.all())
        if all(
            evaluate_condition(item.condition_type, item.configuration, subject_context)
            != item.negate
            for item in conditions
        ):
            matched.append(candidate)
    if len(matched) == 1:
        return matched[0]
    if not matched and len(defaults) == 1:
        return defaults[0]
    if not matched:
        raise WorkflowConflict("هیچ انتقال معتبری برای نتیجه فعلی وجود ندارد.")
    raise WorkflowConflict("انتقال معتبر بیش از یک مورد است.")


def _candidate_metadata(candidate: ResolvedCandidate) -> dict[str, Any]:
    return {
        "membership_id": str(candidate.membership.pk),
        "routing_basis": candidate.routing_basis,
        "position_assignment_id": (
            str(candidate.position_assignment.pk)
            if candidate.position_assignment
            else None
        ),
    }


def _create_candidate(
    *, work_item: WorkItem, candidate: ResolvedCandidate
) -> WorkItemCandidate:
    try:
        return WorkItemCandidate.objects.create(
            organization_id=work_item.organization_id,
            work_item=work_item,
            membership=candidate.membership,
            qualifying_position_assignment=candidate.position_assignment,
            routing_basis=candidate.routing_basis,
        )
    except IntegrityError:
        return WorkItemCandidate.objects.get(
            organization_id=work_item.organization_id,
            work_item=work_item,
            membership=candidate.membership,
            is_active=True,
        )


def _make_work_item(
    *,
    instance: WorkflowInstance,
    step_instance: WorkflowStepInstance,
    action_key: str,
    candidates: list[ResolvedCandidate],
    actor: User,
    actor_membership: OrganizationMembership,
    assigned_candidate: ResolvedCandidate | None = None,
) -> WorkItem:
    configuration = step_instance.step_definition.configuration
    due_hours = configuration.get("due_hours")
    if due_hours is not None and (not isinstance(due_hours, int) or due_hours < 0):
        raise ValidationError("مهلت گام باید ساعت نامنفی باشد.")
    due_at = (
        timezone.now() + timedelta(hours=due_hours) if due_hours is not None else None
    )
    item_key = _idempotency_key(instance.pk, step_instance.pk, action_key)
    try:
        work_item = WorkItem.objects.create(
            organization_id=instance.organization_id,
            instance=instance,
            step_instance=step_instance,
            action_key=action_key,
            required_permission=step_instance.step_definition.required_permission,
            current_assignee=(
                assigned_candidate.membership if assigned_candidate else None
            ),
            assigned_via_position=(
                assigned_candidate.position_assignment if assigned_candidate else None
            ),
            due_at=due_at,
            priority=configuration.get("priority", 0),
            routing_basis=[
                basis for candidate in candidates for basis in candidate.routing_basis
            ],
            idempotency_key=item_key,
        )
    except IntegrityError:
        work_item = WorkItem.objects.get(
            organization_id=instance.organization_id,
            step_instance=step_instance,
            action_key=action_key,
        )
    for candidate in candidates:
        _create_candidate(work_item=work_item, candidate=candidate)
    if assigned_candidate and not work_item.assignment_history.exists():
        _history(
            work_item=work_item,
            action=WorkItemAssignmentAction.ASSIGN,
            actor_membership=actor_membership,
            idempotency_key=_idempotency_key(item_key, "assign"),
            previous_state=WorkItemStatus.OPEN,
            new_state=WorkItemStatus.OPEN,
            to_membership=assigned_candidate.membership,
            position_assignment_id=(
                assigned_candidate.position_assignment.pk
                if assigned_candidate.position_assignment
                else None
            ),
            permission_code=work_item.required_permission,
        )
    return work_item


def _activate_action_step(
    *,
    instance: WorkflowInstance,
    step_instance: WorkflowStepInstance,
    actor: User,
    actor_membership: OrganizationMembership,
) -> None:
    step = step_instance.step_definition
    result = resolve_step_candidates(
        instance=instance,
        step_id=step.pk,
        required_permission=step.required_permission,
    )
    _audit(
        action=(
            AuditAction.WORKFLOW_ROUTING_FALLBACK
            if result.used_fallback
            else AuditAction.WORKFLOW_ROUTING_RESOLVED
        ),
        entity_type="workflows.WorkflowStepInstance",
        entity_id=step_instance.pk,
        organization=instance.organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "candidate_ids": [str(item.membership.pk) for item in result.candidates],
            "attempted_rule_ids": list(result.attempted_rules),
            "routing_basis": [
                basis for item in result.candidates for basis in item.routing_basis
            ],
        },
    )
    if not result.candidates:
        now = timezone.now()
        WorkItem.objects.get_or_create(
            organization_id=instance.organization_id,
            step_instance=step_instance,
            action_key=step.key,
            defaults={
                "instance": instance,
                "status": WorkItemStatus.UNRESOLVED,
                "required_permission": step.required_permission,
                "routing_basis": [
                    {
                        "resolver": "unresolved",
                        "attempted_rule_ids": ",".join(result.attempted_rules),
                    }
                ],
                "unresolved_at": now,
                "unresolved_reason": "no_eligible_primary_or_fallback_candidate",
                "priority": step.configuration.get("priority", 0),
                "idempotency_key": _idempotency_key(
                    instance.pk, step_instance.pk, step.key, "unresolved"
                ),
            },
        )
        _raw_update(
            WorkflowInstance.objects.filter(pk=instance.pk),
            status=WorkflowInstanceStatus.SUSPENDED,
            suspended_at=now,
            suspension_reason="unresolvable_routing",
            updated_at=now,
        )
        instance.status = WorkflowInstanceStatus.SUSPENDED
        _audit(
            action=AuditAction.WORKFLOW_ROUTING_UNRESOLVABLE,
            entity_type="workflows.WorkflowInstance",
            entity_id=instance.pk,
            organization=instance.organization,
            actor=actor,
            actor_membership=actor_membership,
            metadata={"previous_state": "active", "new_state": "suspended"},
        )
        return
    decision_policy = step.configuration.get("decision_policy", "any")
    if decision_policy == "any":
        _make_work_item(
            instance=instance,
            step_instance=step_instance,
            action_key=step.key,
            candidates=list(result.candidates),
            actor=actor,
            actor_membership=actor_membership,
        )
    else:
        for candidate in result.candidates:
            _make_work_item(
                instance=instance,
                step_instance=step_instance,
                action_key=f"{step.key}:{candidate.membership.pk}",
                candidates=[candidate],
                assigned_candidate=candidate,
                actor=actor,
                actor_membership=actor_membership,
            )
    _audit(
        action=AuditAction.WORKFLOW_CANDIDATES_CHANGED,
        entity_type="workflows.WorkflowStepInstance",
        entity_id=step_instance.pk,
        organization=instance.organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "change": "created",
            "candidates": [_candidate_metadata(item) for item in result.candidates],
        },
    )


def _complete_instance(
    *,
    instance: WorkflowInstance,
    actor: User,
    actor_membership: OrganizationMembership,
) -> None:
    now = timezone.now()
    _raw_update(
        WorkflowInstance.objects.filter(pk=instance.pk),
        status=WorkflowInstanceStatus.COMPLETED,
        completed_at=now,
        updated_at=now,
    )
    instance.status = WorkflowInstanceStatus.COMPLETED
    _audit(
        action=AuditAction.WORKFLOW_INSTANCE_COMPLETED,
        entity_type="workflows.WorkflowInstance",
        entity_id=instance.pk,
        organization=instance.organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={"previous_state": "active", "new_state": "completed"},
    )


def _activate_step(
    *,
    instance: WorkflowInstance,
    step: WorkflowStepDefinition,
    actor: User,
    actor_membership: OrganizationMembership,
) -> WorkflowStepInstance:
    sequence = (
        instance.step_instances.aggregate(value=Max("sequence"))["value"] or 0
    ) + 1
    step_instance = WorkflowStepInstance.objects.create(
        organization_id=instance.organization_id,
        instance=instance,
        step_definition=step,
        sequence=sequence,
    )
    _audit(
        action=AuditAction.WORKFLOW_STEP_ACTIVATED,
        entity_type="workflows.WorkflowStepInstance",
        entity_id=step_instance.pk,
        organization=instance.organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={"step_key": step.key, "sequence": sequence},
    )
    if step.is_terminal:
        now = timezone.now()
        _raw_update(
            WorkflowStepInstance.objects.filter(pk=step_instance.pk),
            status=WorkflowStepInstanceStatus.COMPLETED,
            completed_at=now,
            outcome="completed",
            updated_at=now,
        )
        _complete_instance(
            instance=instance, actor=actor, actor_membership=actor_membership
        )
        return step_instance
    if step.step_type == "start":
        transition = _matching_transition(
            step=step,
            outcome=None,
            subject_context=instance.subject_context,
        )
        now = timezone.now()
        _raw_update(
            WorkflowStepInstance.objects.filter(pk=step_instance.pk),
            status=WorkflowStepInstanceStatus.COMPLETED,
            completed_at=now,
            outcome=transition.outcome,
            updated_at=now,
        )
        _audit(
            action=AuditAction.WORKFLOW_INSTANCE_ADVANCED,
            entity_type="workflows.WorkflowInstance",
            entity_id=instance.pk,
            organization=instance.organization,
            actor=actor,
            actor_membership=actor_membership,
            metadata={"from_step": step.key, "to_step": transition.target_step.key},
        )
        return _activate_step(
            instance=instance,
            step=transition.target_step,
            actor=actor,
            actor_membership=actor_membership,
        )
    _activate_action_step(
        instance=instance,
        step_instance=step_instance,
        actor=actor,
        actor_membership=actor_membership,
    )
    return step_instance


@transaction.atomic
def start_workflow(
    *,
    actor: User,
    organization: Organization,
    version_id: object,
    subject_id: str | UUID,
    idempotency_key: str,
    initial_step_key: str | None = None,
) -> WorkflowInstance:
    """Start under lock order: domain subject, instance, active step, work item."""
    actor_membership = _require_membership(actor=actor, organization=organization)
    if not idempotency_key.strip():
        raise ValidationError("کلید تکرارپذیری آغاز گردش‌کار الزامی است.")
    try:
        normalized_subject_id = UUID(str(subject_id))
        version = WorkflowVersion.objects.select_related(
            "definition__workflow_type", "organization"
        ).get(pk=version_id, organization=organization)
    except (ValueError, WorkflowVersion.DoesNotExist) as exc:
        raise PermissionDenied("نسخه یا موضوع در این سازمان یافت نشد.") from exc
    if version.status != WorkflowVersionStatus.PUBLISHED:
        raise ValidationError("فقط نسخه منتشرشده قابل اجرا است.")
    snapshot = _load_subject(
        organization=organization,
        version=version,
        subject_id=normalized_subject_id,
        actor=actor,
        for_update=True,
        check_start_permission=True,
    )
    existing = (
        WorkflowInstance.objects.select_for_update()
        .filter(organization=organization, idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        if (
            existing.version_id != version.pk
            or existing.subject_id != normalized_subject_id
        ):
            raise ValidationError("کلید تکرارپذیری برای درخواست دیگری استفاده شده است.")
        return existing
    open_instance = (
        WorkflowInstance.objects.select_for_update()
        .filter(
            organization=organization,
            definition=version.definition,
            subject_type=version.definition.workflow_type.subject_type,
            subject_id=normalized_subject_id,
            status__in=(
                WorkflowInstanceStatus.ACTIVE,
                WorkflowInstanceStatus.SUSPENDED,
            ),
        )
        .first()
    )
    if open_instance:
        return open_instance
    instance = WorkflowInstance.objects.create(
        organization=organization,
        definition=version.definition,
        version=version,
        subject_type=version.definition.workflow_type.subject_type,
        subject_id=normalized_subject_id,
        subject_context=_subject_context(snapshot=snapshot, starter=actor_membership),
        idempotency_key=idempotency_key,
        started_by=actor_membership,
    )
    _audit(
        action=AuditAction.WORKFLOW_INSTANCE_STARTED,
        entity_type="workflows.WorkflowInstance",
        entity_id=instance.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "version_id": str(version.pk),
            "subject_type": instance.subject_type,
            "subject_id": str(instance.subject_id),
            "previous_state": None,
            "new_state": "active",
        },
    )
    start_step = version.steps.filter(is_start=True).first()
    if start_step is None:
        raise ValidationError("نسخه منتشرشده گام شروع ندارد.")
    if initial_step_key is not None:
        resume_step = version.steps.filter(
            key=initial_step_key, step_type="approval", is_terminal=False
        ).first()
        if resume_step is None:
            raise ValidationError("گام آغاز بازپُرکنی معتبر نیست.")
        state = snapshot.attributes.get("status")
        commands = [
            registry.domain_commands.get(transition.domain_command)
            for transition in resume_step.outgoing_transitions.all()
        ]
        if not commands or not all(
            command is not None
            and command.workflow_type == version.definition.workflow_type.code
            and state in command.from_states
            for command in commands
        ):
            raise ValidationError("وضعیت موضوع با گام بازپُرکنی سازگار نیست.")
        start_step = resume_step
    _activate_step(
        instance=instance,
        step=start_step,
        actor=actor,
        actor_membership=actor_membership,
    )
    instance.refresh_from_db()
    return instance


def _preload_item(*, organization: Organization, work_item_id: object) -> WorkItem:
    try:
        return WorkItem.objects.select_related(
            "instance__version__definition__workflow_type",
            "step_instance__step_definition",
        ).get(pk=work_item_id, organization=organization)
    except (ValueError, WorkItem.DoesNotExist) as exc:
        raise PermissionDenied("کار در این سازمان یافت نشد.") from exc


def _lock_runtime_for_item(
    *, actor: User, organization: Organization, work_item_id: object
) -> tuple[SubjectSnapshot, WorkflowInstance, WorkflowStepInstance, WorkItem]:
    """Apply the invariant lock order: subject -> instance -> step -> item."""
    preliminary = _preload_item(organization=organization, work_item_id=work_item_id)
    snapshot = _load_subject(
        organization=organization,
        version=preliminary.instance.version,
        subject_id=preliminary.instance.subject_id,
        actor=actor,
        for_update=True,
    )
    instance = (
        WorkflowInstance.objects.select_for_update()
        .select_related("organization", "definition__workflow_type", "version")
        .get(pk=preliminary.instance_id, organization=organization)
    )
    step_instance = (
        WorkflowStepInstance.objects.select_for_update()
        .select_related("step_definition")
        .get(pk=preliminary.step_instance_id, organization=organization)
    )
    work_item = WorkItem.objects.select_for_update().get(
        pk=work_item_id,
        organization=organization,
        instance=instance,
        step_instance=step_instance,
    )
    actor_membership = get_active_membership(user=actor, organization=organization)
    _lock_membership_authority(
        organization=organization,
        membership_id=actor_membership.pk,
    )
    return snapshot, instance, step_instance, work_item


def _active_candidate(
    *, work_item: WorkItem, membership: OrganizationMembership
) -> WorkItemCandidate | None:
    return (
        WorkItemCandidate.objects.select_related("qualifying_position_assignment")
        .filter(
            organization_id=work_item.organization_id,
            work_item=work_item,
            membership=membership,
            is_active=True,
        )
        .first()
    )


def _candidate_delegation_is_current(
    *,
    candidate: WorkItemCandidate,
    item: WorkItem,
    instance: WorkflowInstance,
    membership: OrganizationMembership,
) -> bool:
    delegation_bases = [
        basis
        for basis in candidate.routing_basis
        if basis.get("resolver") == "delegation"
    ]
    if not delegation_bases:
        return True
    if any(basis.get("resolver") != "delegation" for basis in candidate.routing_basis):
        return True
    required_permission = (
        item.required_permission
        or item.step_instance.step_definition.required_permission
    )
    if not required_permission:
        return False
    now = timezone.now()
    delegation_ids = [
        basis.get("delegation_id")
        for basis in delegation_bases
        if basis.get("delegation_id")
    ]
    delegations = (
        WorkflowDelegation.objects.select_for_update(of=("self",))
        .filter(
            pk__in=delegation_ids,
            organization_id=item.organization_id,
            delegate=membership,
            permission__code=required_permission,
            starts_at__lte=now,
            ends_at__gt=now,
            revoked_at__isnull=True,
        )
        .select_related("delegator__user", "delegator__role_definition")
        .prefetch_related(
            "delegator__role_assignments__role__permissions",
            "delegator__scope_grants",
        )
    )
    from .scope import delegation_scope_is_bounded, membership_has_workflow_scope

    for delegation in delegations:
        if (
            delegation.delegator.status == MembershipStatus.ACTIVE
            and delegation.delegator.user.is_active
            and membership_has_permission(delegation.delegator, required_permission)
            and membership_has_workflow_scope(
                membership=delegation.delegator, instance=instance
            )
            and delegation_scope_is_bounded(scope=delegation.scope, instance=instance)
        ):
            return True
    return False


def list_member_work_items(
    *,
    actor: User,
    organization: Organization,
    include_terminal: bool = False,
) -> models.QuerySet[WorkItem]:
    """Return the actor's tenant-scoped workbench after explicit authorization."""

    membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORK_ITEMS_VIEW,
        allow_any_scope=True,
    )
    queryset = (
        WorkItem.objects.filter(organization=organization)
        .filter(
            models.Q(current_assignee=membership)
            | models.Q(candidates__membership=membership, candidates__is_active=True)
        )
        .select_related("instance", "step_instance", "current_assignee")
        .distinct()
    )
    queryset = scope_work_item_queryset(queryset, membership=membership)
    if not include_terminal:
        queryset = queryset.filter(
            status__in=[WorkItemStatus.OPEN, WorkItemStatus.CLAIMED]
        )
    return queryset.order_by("-priority", "due_at", "created_at")


def list_unresolved_work_items(
    *, actor: User, organization: Organization
) -> models.QuerySet[WorkItem]:
    """Return visible unresolved work only to explicit recovery authority."""

    membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.AUTHORIZATION_UNRESOLVED_RECOVER,
        allow_any_scope=True,
    )
    queryset = WorkItem.objects.filter(
        organization=organization,
        status=WorkItemStatus.UNRESOLVED,
    ).select_related("instance", "step_instance__step_definition")
    return scope_work_item_queryset(queryset, membership=membership).order_by(
        "-priority", "created_at"
    )


@transaction.atomic
def recover_unresolved_work_item(
    *,
    actor: User,
    organization: Organization,
    work_item_id: object,
    reason: str,
    idempotency_key: str,
) -> WorkItem:
    """Re-run eligible routing without privileged auto-assignment."""

    if not reason.strip():
        raise ValidationError("دلیل بازیابی کار حل‌نشده الزامی است.")
    _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.AUTHORIZATION_UNRESOLVED_RECOVER,
        allow_any_scope=True,
    )
    try:
        item = (
            WorkItem.objects.select_for_update()
            .select_related(
                "instance__version",
                "step_instance__step_definition",
            )
            .get(
                pk=work_item_id,
                organization=organization,
            )
        )
    except (ValueError, WorkItem.DoesNotExist) as exc:
        raise PermissionDenied("کار حل‌نشده در این سازمان یافت نشد.") from exc
    instance = WorkflowInstance.objects.select_for_update().get(pk=item.instance_id)
    actor_membership = get_active_membership(user=actor, organization=organization)
    _lock_membership_authority(
        organization=organization,
        membership_id=actor_membership.pk,
    )
    actor_membership = _require_instance_permission(
        actor=actor,
        organization=organization,
        instance=instance,
        permission=BusinessPermissionCode.AUTHORIZATION_UNRESOLVED_RECOVER,
    )
    if item.assignment_history.filter(idempotency_key=idempotency_key).exists():
        return item
    if item.status != WorkItemStatus.UNRESOLVED:
        raise PermissionDenied("کار حل‌نشده در این سازمان یافت نشد.")
    if (
        instance.status != WorkflowInstanceStatus.SUSPENDED
        or instance.suspension_reason != "unresolvable_routing"
    ):
        raise WorkflowConflict("اجرای گردش‌کار دیگر در وضعیت حل‌نشده نیست.")
    step = item.step_instance.step_definition
    result = resolve_step_candidates(
        instance=instance,
        step_id=step.pk,
        required_permission=step.required_permission,
    )
    if not result.candidates:
        raise ValidationError("هنوز نامزد واجد شرایطی برای این کار وجود ندارد.")
    now = timezone.now()
    decision_policy = step.configuration.get("decision_policy", "any")
    if decision_policy == "any":
        for candidate in result.candidates:
            _create_candidate(work_item=item, candidate=candidate)
        _raw_update(
            WorkItem.objects.filter(pk=item.pk),
            status=WorkItemStatus.OPEN,
            routing_basis=[
                basis
                for candidate in result.candidates
                for basis in candidate.routing_basis
            ],
            unresolved_at=None,
            unresolved_reason="",
            updated_at=now,
        )
        new_state = WorkItemStatus.OPEN
    else:
        _raw_update(
            WorkItem.objects.filter(pk=item.pk),
            status=WorkItemStatus.CANCELLED,
            cancelled_at=now,
            completion_outcome="recovered",
            updated_at=now,
        )
        for candidate in result.candidates:
            _make_work_item(
                instance=instance,
                step_instance=item.step_instance,
                action_key=f"{step.key}:{candidate.membership.pk}",
                candidates=[candidate],
                assigned_candidate=candidate,
                actor=actor,
                actor_membership=actor_membership,
            )
        new_state = WorkItemStatus.CANCELLED
    _history(
        work_item=item,
        action=WorkItemAssignmentAction.RECOVER,
        actor_membership=actor_membership,
        idempotency_key=idempotency_key,
        previous_state=WorkItemStatus.UNRESOLVED,
        new_state=new_state,
        permission_code=BusinessPermissionCode.AUTHORIZATION_UNRESOLVED_RECOVER,
        reason=reason.strip(),
        metadata={"candidate_ids": [str(c.membership.pk) for c in result.candidates]},
    )
    _raw_update(
        WorkflowInstance.objects.filter(pk=instance.pk),
        status=WorkflowInstanceStatus.ACTIVE,
        suspended_at=None,
        suspension_reason="",
        updated_at=now,
    )
    _audit(
        action=AuditAction.WORKFLOW_UNRESOLVED_RECOVERED,
        entity_type="workflows.WorkItem",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "candidate_ids": [str(c.membership.pk) for c in result.candidates],
            "reason": reason.strip(),
        },
    )
    item.refresh_from_db()
    return item


def _check_sod(
    *, instance: WorkflowInstance, step: WorkflowStepDefinition, membership_id: object
) -> None:
    checks = (
        ("exclude_creator", "creator_membership_id"),
        ("exclude_submitter", "submitter_membership_id"),
        ("exclude_starter", "starter_membership_id"),
    )
    for flag, context_key in checks:
        if step.configuration.get(flag) and str(
            instance.subject_context.get(context_key)
        ) == str(membership_id):
            raise PermissionDenied("قاعده تفکیک وظایف این اقدام را منع می‌کند.")


def _assert_live_runtime(
    *, instance: WorkflowInstance, step: WorkflowStepInstance, item: WorkItem
) -> None:
    if instance.status != WorkflowInstanceStatus.ACTIVE:
        raise WorkflowConflict("اجرای گردش‌کار فعال نیست.")
    if step.status != WorkflowStepInstanceStatus.ACTIVE:
        raise WorkflowConflict("گام گردش‌کار دیگر فعال نیست.")
    if item.status not in (WorkItemStatus.OPEN, WorkItemStatus.CLAIMED):
        raise WorkflowConflict("کار دیگر قابل اقدام نیست.")


@transaction.atomic
def claim_work_item(
    *,
    actor: User,
    organization: Organization,
    work_item_id: object,
    idempotency_key: str,
) -> WorkItem:
    actor_membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORK_ITEMS_CLAIM,
        allow_any_scope=True,
    )
    _, instance, step, item = _lock_runtime_for_item(
        actor=actor, organization=organization, work_item_id=work_item_id
    )
    actor_membership = _require_instance_permission(
        actor=actor,
        organization=organization,
        instance=instance,
        permission=BusinessPermissionCode.WORK_ITEMS_CLAIM,
    )
    previous_history = item.assignment_history.filter(
        idempotency_key=idempotency_key
    ).first()
    if previous_history:
        return item
    _assert_live_runtime(instance=instance, step=step, item=item)
    if item.status != WorkItemStatus.OPEN:
        raise WorkflowConflict("کار قبلاً اخذ شده است.")
    candidate = _active_candidate(work_item=item, membership=actor_membership)
    if candidate is None:
        raise PermissionDenied("عضویت فعلی نامزد این کار نیست.")
    required_permission = (
        item.required_permission or step.step_definition.required_permission
    )
    if required_permission and not membership_has_permission(
        actor_membership, required_permission
    ):
        raise PermissionDenied("نامزد مجوز فعلی لازم را ندارد.")
    if not _candidate_delegation_is_current(
        candidate=candidate,
        item=item,
        instance=instance,
        membership=actor_membership,
    ):
        raise PermissionDenied("واگذاری این نامزد دیگر معتبر نیست.")
    if item.current_assignee_id and item.current_assignee_id != actor_membership.pk:
        raise PermissionDenied("کار به عضویت دیگری تخصیص یافته است.")
    _check_sod(
        instance=instance,
        step=step.step_definition,
        membership_id=actor_membership.pk,
    )
    now = timezone.now()
    _raw_update(
        WorkItem.objects.filter(pk=item.pk),
        status=WorkItemStatus.CLAIMED,
        current_assignee=actor_membership,
        assigned_via_position=candidate.qualifying_position_assignment,
        claimed_at=now,
        updated_at=now,
    )
    _history(
        work_item=item,
        action=WorkItemAssignmentAction.CLAIM,
        actor_membership=actor_membership,
        idempotency_key=idempotency_key,
        previous_state=WorkItemStatus.OPEN,
        new_state=WorkItemStatus.CLAIMED,
        to_membership=actor_membership,
        position_assignment_id=candidate.qualifying_position_assignment_id,
        permission_code=BusinessPermissionCode.WORK_ITEMS_CLAIM,
    )
    _audit(
        action=AuditAction.WORK_ITEM_CLAIMED,
        entity_type="workflows.WorkItem",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "previous_state": "open",
            "new_state": "claimed",
            "qualifying_position_assignment_id": (
                str(candidate.qualifying_position_assignment_id)
                if candidate.qualifying_position_assignment_id
                else None
            ),
            "permission": str(BusinessPermissionCode.WORK_ITEMS_CLAIM),
        },
    )
    item.refresh_from_db()
    return item


@transaction.atomic
def release_work_item(
    *,
    actor: User,
    organization: Organization,
    work_item_id: object,
    idempotency_key: str,
    reason: str = "",
) -> WorkItem:
    actor_membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORK_ITEMS_CLAIM,
        allow_any_scope=True,
    )
    _, instance, step, item = _lock_runtime_for_item(
        actor=actor, organization=organization, work_item_id=work_item_id
    )
    actor_membership = _require_instance_permission(
        actor=actor,
        organization=organization,
        instance=instance,
        permission=BusinessPermissionCode.WORK_ITEMS_CLAIM,
    )
    if item.assignment_history.filter(idempotency_key=idempotency_key).exists():
        return item
    _assert_live_runtime(instance=instance, step=step, item=item)
    if (
        item.status != WorkItemStatus.CLAIMED
        or item.current_assignee_id != actor_membership.pk
    ):
        raise PermissionDenied("فقط اخذکننده فعلی می‌تواند کار را آزاد کند.")
    previous_position_id = item.assigned_via_position_id
    now = timezone.now()
    _raw_update(
        WorkItem.objects.filter(pk=item.pk),
        status=WorkItemStatus.OPEN,
        current_assignee=None,
        assigned_via_position=None,
        claimed_at=None,
        updated_at=now,
    )
    _history(
        work_item=item,
        action=WorkItemAssignmentAction.RELEASE,
        actor_membership=actor_membership,
        idempotency_key=idempotency_key,
        previous_state=WorkItemStatus.CLAIMED,
        new_state=WorkItemStatus.OPEN,
        from_membership=actor_membership,
        position_assignment_id=previous_position_id,
        permission_code=BusinessPermissionCode.WORK_ITEMS_CLAIM,
        reason=reason.strip(),
    )
    _audit(
        action=AuditAction.WORK_ITEM_RELEASED,
        entity_type="workflows.WorkItem",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "previous_state": "claimed",
            "new_state": "open",
            "reason": reason.strip(),
        },
    )
    item.refresh_from_db()
    return item


@transaction.atomic
def reassign_work_item(
    *,
    actor: User,
    organization: Organization,
    work_item_id: object,
    assignee_membership_id: object,
    reason: str,
    idempotency_key: str,
) -> WorkItem:
    actor_membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_REASSIGN,
        allow_any_scope=True,
    )
    if not reason.strip():
        raise ValidationError("دلیل تخصیص مجدد الزامی است.")
    _, instance, step, item = _lock_runtime_for_item(
        actor=actor, organization=organization, work_item_id=work_item_id
    )
    actor_membership = _require_instance_permission(
        actor=actor,
        organization=organization,
        instance=instance,
        permission=BusinessPermissionCode.WORKFLOWS_REASSIGN,
    )
    if item.assignment_history.filter(idempotency_key=idempotency_key).exists():
        return item
    _assert_live_runtime(instance=instance, step=step, item=item)
    try:
        _lock_membership_authority(
            organization=organization,
            membership_id=assignee_membership_id,
        )
        assignee = (
            OrganizationMembership.objects.select_related("user", "role_definition")
            .prefetch_related("role_assignments__role__permissions", "scope_grants")
            .get(
                pk=assignee_membership_id,
                organization=organization,
                status=MembershipStatus.ACTIVE,
                user__is_active=True,
            )
        )
    except (ValueError, OrganizationMembership.DoesNotExist) as exc:
        raise PermissionDenied("عضویت مقصد فعال و متعلق به این سازمان نیست.") from exc
    required_permission = (
        item.required_permission or step.step_definition.required_permission
    )
    if required_permission and not membership_has_permission(
        assignee, required_permission
    ):
        raise PermissionDenied("عضویت مقصد مجوز مستقل لازم را ندارد.")
    from .scope import membership_has_workflow_scope

    if not membership_has_workflow_scope(membership=assignee, instance=instance):
        raise PermissionDenied("عضویت مقصد دامنه مؤثر این کار را ندارد.")
    _check_sod(
        instance=instance,
        step=step.step_definition,
        membership_id=assignee.pk,
    )
    previous = item.current_assignee
    WorkItemCandidate.objects.get_or_create(
        organization=organization,
        work_item=item,
        membership=assignee,
        is_active=True,
        defaults={"routing_basis": [{"resolver": "explicit_reassignment"}]},
    )
    now = timezone.now()
    _raw_update(
        WorkItem.objects.filter(pk=item.pk),
        current_assignee=assignee,
        assigned_via_position=None,
        claimed_at=now if item.status == WorkItemStatus.CLAIMED else None,
        updated_at=now,
    )
    _history(
        work_item=item,
        action=WorkItemAssignmentAction.REASSIGN,
        actor_membership=actor_membership,
        idempotency_key=idempotency_key,
        previous_state=item.status,
        new_state=item.status,
        from_membership=previous,
        to_membership=assignee,
        permission_code=BusinessPermissionCode.WORKFLOWS_REASSIGN,
        reason=reason.strip(),
    )
    _audit(
        action=AuditAction.WORK_ITEM_REASSIGNED,
        entity_type="workflows.WorkItem",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "from_membership_id": str(previous.pk) if previous else None,
            "to_membership_id": str(assignee.pk),
            "previous_state": item.status,
            "new_state": item.status,
            "permission": str(BusinessPermissionCode.WORKFLOWS_REASSIGN),
            "reason": reason.strip(),
        },
    )
    item.refresh_from_db()
    return item


def _decision_threshold_reached(*, step: WorkflowStepInstance) -> bool:
    configuration = step.step_definition.configuration
    policy = configuration.get("decision_policy", "any")
    if policy == "any":
        return True
    total = step.work_items.count()
    completed = step.work_items.filter(status=WorkItemStatus.COMPLETED).count() + 1
    if policy == "all":
        return completed >= total
    if policy == "minimum_count":
        minimum = configuration.get("minimum_approvals", 1)
        return completed >= minimum
    raise ValidationError("سیاست تصمیم‌گیری ثبت نشده است.")


def _cancel_sibling_items(
    *,
    current: WorkItem,
    actor: User,
    actor_membership: OrganizationMembership,
    outcome: str,
) -> None:
    siblings = list(
        WorkItem.objects.select_for_update()
        .filter(
            organization_id=current.organization_id,
            step_instance=current.step_instance,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        )
        .exclude(pk=current.pk)
        .order_by("pk")
    )
    now = timezone.now()
    for item in siblings:
        _raw_update(
            WorkItem.objects.filter(pk=item.pk),
            status=WorkItemStatus.CANCELLED,
            cancelled_at=now,
            completion_outcome=outcome,
            updated_at=now,
        )
        _history(
            work_item=item,
            action=WorkItemAssignmentAction.CANCEL,
            actor_membership=actor_membership,
            idempotency_key=_idempotency_key(item.pk, "cancel", outcome),
            previous_state=item.status,
            new_state=WorkItemStatus.CANCELLED,
            from_membership=item.current_assignee,
            permission_code=BusinessPermissionCode.WORK_ITEMS_ACT,
            reason="decision_threshold_reached",
            outcome=outcome,
        )
        _audit(
            action=AuditAction.WORK_ITEM_CANCELLED,
            entity_type="workflows.WorkItem",
            entity_id=item.pk,
            organization=current.organization,
            actor=actor,
            actor_membership=actor_membership,
            metadata={
                "previous_state": item.status,
                "new_state": "cancelled",
                "reason": "decision_threshold_reached",
            },
        )


@transaction.atomic
def complete_work_item(
    *,
    actor: User,
    organization: Organization,
    work_item_id: object,
    outcome: str,
    idempotency_key: str,
    command_context: dict[str, Any] | None = None,
) -> WorkItem:
    actor_membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORK_ITEMS_ACT,
        allow_any_scope=True,
    )
    snapshot, instance, step, item = _lock_runtime_for_item(
        actor=actor, organization=organization, work_item_id=work_item_id
    )
    actor_membership = _require_instance_permission(
        actor=actor,
        organization=organization,
        instance=instance,
        permission=BusinessPermissionCode.WORK_ITEMS_ACT,
    )
    if item.assignment_history.filter(idempotency_key=idempotency_key).exists():
        return item
    _assert_live_runtime(instance=instance, step=step, item=item)
    if (
        item.status != WorkItemStatus.CLAIMED
        or item.current_assignee_id != actor_membership.pk
    ):
        raise PermissionDenied("کار باید توسط همین عضویت اخذ شده باشد.")
    candidate = _active_candidate(work_item=item, membership=actor_membership)
    if candidate is None:
        raise PermissionDenied("عضویت فعلی نامزد فعال این کار نیست.")
    if not _candidate_delegation_is_current(
        candidate=candidate,
        item=item,
        instance=instance,
        membership=actor_membership,
    ):
        raise PermissionDenied("واگذاری این نامزد دیگر معتبر نیست.")
    _check_sod(
        instance=instance,
        step=step.step_definition,
        membership_id=actor_membership.pk,
    )
    transition = _matching_transition(
        step=step.step_definition,
        outcome=outcome,
        subject_context=snapshot.attributes,
    )
    required_permission = (
        transition.required_permission
        or item.required_permission
        or step.step_definition.required_permission
    )
    if required_permission and not membership_has_permission(
        actor_membership, required_permission
    ):
        raise PermissionDenied("مجوز دامنه لازم برای این تصمیم را ندارید.")
    threshold_reached = _decision_threshold_reached(step=step)
    command_key = transition.domain_command or step.step_definition.domain_command
    if threshold_reached and command_key:
        command = registry.domain_commands.get(command_key)
        if command is None or command.executor is None:
            raise ValidationError("فرمان runtime این دامنه هنوز ثبت نشده است.")
        command.executor(
            subject=snapshot.subject,
            actor=actor,
            organization=organization,
            outcome=outcome,
            context=command_context or {},
            idempotency_key=idempotency_key,
            **({"work_item": item} if command.include_work_item else {}),
        )
        refreshed = _load_subject(
            organization=organization,
            version=instance.version,
            subject_id=instance.subject_id,
            actor=actor,
            for_update=False,
        )
        context = instance.subject_context | refreshed.attributes
        _raw_update(
            WorkflowInstance.objects.filter(pk=instance.pk), subject_context=context
        )
        instance.subject_context = context
    now = timezone.now()
    _raw_update(
        WorkItem.objects.filter(pk=item.pk),
        status=WorkItemStatus.COMPLETED,
        completed_at=now,
        completion_outcome=outcome,
        updated_at=now,
    )
    _history(
        work_item=item,
        action=WorkItemAssignmentAction.COMPLETE,
        actor_membership=actor_membership,
        idempotency_key=idempotency_key,
        previous_state=WorkItemStatus.CLAIMED,
        new_state=WorkItemStatus.COMPLETED,
        from_membership=actor_membership,
        to_membership=actor_membership,
        position_assignment_id=item.assigned_via_position_id,
        permission_code=required_permission or BusinessPermissionCode.WORK_ITEMS_ACT,
        outcome=outcome,
    )
    _audit(
        action=AuditAction.WORK_ITEM_COMPLETED,
        entity_type="workflows.WorkItem",
        entity_id=item.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "previous_state": "claimed",
            "new_state": "completed",
            "outcome": outcome,
            "permission": str(
                required_permission or BusinessPermissionCode.WORK_ITEMS_ACT
            ),
            "qualifying_position_assignment_id": (
                str(item.assigned_via_position_id)
                if item.assigned_via_position_id
                else None
            ),
        },
    )
    if not threshold_reached:
        item.refresh_from_db()
        return item
    _cancel_sibling_items(
        current=item,
        actor=actor,
        actor_membership=actor_membership,
        outcome=outcome,
    )
    _raw_update(
        WorkflowStepInstance.objects.filter(pk=step.pk),
        status=WorkflowStepInstanceStatus.COMPLETED,
        completed_at=now,
        outcome=outcome,
        updated_at=now,
    )
    _audit(
        action=AuditAction.WORKFLOW_INSTANCE_ADVANCED,
        entity_type="workflows.WorkflowInstance",
        entity_id=instance.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "from_step": step.step_definition.key,
            "to_step": transition.target_step.key,
            "outcome": outcome,
            "previous_state": "active",
            "new_state": "active",
        },
    )
    _activate_step(
        instance=instance,
        step=transition.target_step,
        actor=actor,
        actor_membership=actor_membership,
    )
    item.refresh_from_db()
    return item


def _lock_instance_runtime(
    *, actor: User, organization: Organization, instance_id: object
) -> tuple[SubjectSnapshot, WorkflowInstance, WorkflowStepInstance | None]:
    try:
        preliminary = WorkflowInstance.objects.select_related(
            "version__definition__workflow_type"
        ).get(pk=instance_id, organization=organization)
    except (ValueError, WorkflowInstance.DoesNotExist) as exc:
        raise PermissionDenied("اجرای گردش‌کار در این سازمان یافت نشد.") from exc
    snapshot = _load_subject(
        organization=organization,
        version=preliminary.version,
        subject_id=preliminary.subject_id,
        actor=actor,
        for_update=True,
    )
    instance = (
        WorkflowInstance.objects.select_for_update()
        .select_related("organization", "version", "definition__workflow_type")
        .get(pk=preliminary.pk, organization=organization)
    )
    step = (
        WorkflowStepInstance.objects.select_for_update()
        .select_related("step_definition")
        .filter(
            organization=organization,
            instance=instance,
            status=WorkflowStepInstanceStatus.ACTIVE,
        )
        .first()
    )
    return snapshot, instance, step


def _cancel_open_items(
    *,
    step: WorkflowStepInstance,
    actor: User,
    actor_membership: OrganizationMembership,
    reason: str,
) -> None:
    items = list(
        WorkItem.objects.select_for_update()
        .filter(
            organization_id=step.organization_id,
            step_instance=step,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        )
        .order_by("pk")
    )
    now = timezone.now()
    for item in items:
        _raw_update(
            WorkItem.objects.filter(pk=item.pk),
            status=WorkItemStatus.CANCELLED,
            cancelled_at=now,
            updated_at=now,
        )
        _history(
            work_item=item,
            action=WorkItemAssignmentAction.CANCEL,
            actor_membership=actor_membership,
            idempotency_key=_idempotency_key(item.pk, "cancel", reason),
            previous_state=item.status,
            new_state=WorkItemStatus.CANCELLED,
            from_membership=item.current_assignee,
            reason=reason,
        )


@transaction.atomic
def suspend_workflow_instance(
    *,
    actor: User,
    organization: Organization,
    instance_id: object,
    reason: str,
    idempotency_key: str,
) -> WorkflowInstance:
    if not reason.strip():
        raise ValidationError("دلیل تعلیق الزامی است.")
    _, instance, _ = _lock_instance_runtime(
        actor=actor, organization=organization, instance_id=instance_id
    )
    actor_membership = _require_instance_permission(
        actor=actor,
        organization=organization,
        instance=instance,
        permission=BusinessPermissionCode.WORKFLOWS_REASSIGN,
    )
    if _operation_already_processed(
        instance=instance, idempotency_key=idempotency_key, action="suspend"
    ):
        return instance
    if instance.status != WorkflowInstanceStatus.ACTIVE:
        raise WorkflowConflict("فقط اجرای فعال قابل تعلیق است.")
    now = timezone.now()
    _raw_update(
        WorkflowInstance.objects.filter(pk=instance.pk),
        status=WorkflowInstanceStatus.SUSPENDED,
        suspended_at=now,
        suspension_reason=reason.strip(),
        processed_operations=_processed_operations(
            instance=instance, idempotency_key=idempotency_key, action="suspend"
        ),
        updated_at=now,
    )
    _audit(
        action=AuditAction.WORKFLOW_INSTANCE_SUSPENDED,
        entity_type="workflows.WorkflowInstance",
        entity_id=instance.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "previous_state": "active",
            "new_state": "suspended",
            "reason": reason.strip(),
        },
    )
    instance.refresh_from_db()
    return instance


@transaction.atomic
def resume_workflow_instance(
    *,
    actor: User,
    organization: Organization,
    instance_id: object,
    reason: str,
    idempotency_key: str,
) -> WorkflowInstance:
    if not reason.strip():
        raise ValidationError("دلیل ادامه الزامی است.")
    _, instance, step = _lock_instance_runtime(
        actor=actor, organization=organization, instance_id=instance_id
    )
    actor_membership = _require_instance_permission(
        actor=actor,
        organization=organization,
        instance=instance,
        permission=BusinessPermissionCode.WORKFLOWS_REASSIGN,
    )
    if _operation_already_processed(
        instance=instance, idempotency_key=idempotency_key, action="resume"
    ):
        return instance
    if instance.status != WorkflowInstanceStatus.SUSPENDED or step is None:
        raise WorkflowConflict("فقط اجرای تعلیق‌شده با گام فعال قابل ادامه است.")
    if step.work_items.filter(status=WorkItemStatus.UNRESOLVED).exists():
        raise PermissionDenied(
            "کار حل‌نشده فقط از مسیر بازیابی مجاز و ممیزی‌شده قابل ادامه است."
        )
    now = timezone.now()
    _raw_update(
        WorkflowInstance.objects.filter(pk=instance.pk),
        status=WorkflowInstanceStatus.ACTIVE,
        suspended_at=None,
        suspension_reason="",
        processed_operations=_processed_operations(
            instance=instance, idempotency_key=idempotency_key, action="resume"
        ),
        updated_at=now,
    )
    instance.status = WorkflowInstanceStatus.ACTIVE
    if not step.work_items.filter(
        status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
    ).exists():
        _activate_action_step(
            instance=instance,
            step_instance=step,
            actor=actor,
            actor_membership=actor_membership,
        )
    instance.refresh_from_db()
    if instance.status == WorkflowInstanceStatus.ACTIVE:
        _audit(
            action=AuditAction.WORKFLOW_INSTANCE_RESUMED,
            entity_type="workflows.WorkflowInstance",
            entity_id=instance.pk,
            organization=organization,
            actor=actor,
            actor_membership=actor_membership,
            metadata={
                "previous_state": "suspended",
                "new_state": "active",
                "reason": reason.strip(),
            },
        )
    return instance


@transaction.atomic
def cancel_workflow_instance(
    *,
    actor: User,
    organization: Organization,
    instance_id: object,
    reason: str,
    idempotency_key: str,
) -> WorkflowInstance:
    if not reason.strip():
        raise ValidationError("دلیل لغو الزامی است.")
    _, instance, step = _lock_instance_runtime(
        actor=actor, organization=organization, instance_id=instance_id
    )
    actor_membership = _require_instance_permission(
        actor=actor,
        organization=organization,
        instance=instance,
        permission=BusinessPermissionCode.WORKFLOWS_REASSIGN,
    )
    if _operation_already_processed(
        instance=instance, idempotency_key=idempotency_key, action="cancel"
    ):
        return instance
    if instance.status not in (
        WorkflowInstanceStatus.ACTIVE,
        WorkflowInstanceStatus.SUSPENDED,
    ):
        raise WorkflowConflict("اجرای نهایی‌شده قابل لغو نیست.")
    previous_state = instance.status
    if step:
        _cancel_open_items(
            step=step,
            actor=actor,
            actor_membership=actor_membership,
            reason=reason.strip(),
        )
        now = timezone.now()
        _raw_update(
            WorkflowStepInstance.objects.filter(pk=step.pk),
            status=WorkflowStepInstanceStatus.CANCELLED,
            cancelled_at=now,
            updated_at=now,
        )
    now = timezone.now()
    _raw_update(
        WorkflowInstance.objects.filter(pk=instance.pk),
        status=WorkflowInstanceStatus.CANCELLED,
        cancelled_at=now,
        cancellation_reason=reason.strip(),
        processed_operations=_processed_operations(
            instance=instance, idempotency_key=idempotency_key, action="cancel"
        ),
        updated_at=now,
    )
    _audit(
        action=AuditAction.WORKFLOW_INSTANCE_CANCELLED,
        entity_type="workflows.WorkflowInstance",
        entity_id=instance.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "previous_state": previous_state,
            "new_state": "cancelled",
            "reason": reason.strip(),
        },
    )
    instance.refresh_from_db()
    return instance


@transaction.atomic
def cancel_workflow_for_domain(
    *,
    actor: User,
    organization: Organization,
    instance_id: object,
    command_key: str,
    reason: str,
    idempotency_key: str,
    command_context: dict[str, Any] | None = None,
) -> WorkflowInstance:
    """Cancel a subject through its registered domain service, then close runtime."""

    actor_membership = _require_membership(actor=actor, organization=organization)
    if not reason.strip():
        raise ValidationError("دلیل لغو الزامی است.")
    snapshot, instance, step = _lock_instance_runtime(
        actor=actor, organization=organization, instance_id=instance_id
    )
    actor_membership = _require_membership(actor=actor, organization=organization)
    action = f"domain_cancel:{command_key}"
    if _operation_already_processed(
        instance=instance, idempotency_key=idempotency_key, action=action
    ):
        return instance
    if instance.status not in (
        WorkflowInstanceStatus.ACTIVE,
        WorkflowInstanceStatus.SUSPENDED,
    ):
        raise WorkflowConflict("اجرای نهایی‌شده قابل لغو نیست.")
    command = registry.domain_commands.get(command_key)
    if (
        command is None
        or command.executor is None
        or command.workflow_type != instance.definition.workflow_type.code
    ):
        raise ValidationError("فرمان لغو دامنه برای این گردش‌کار ثبت نشده است.")
    subject_state = str(snapshot.attributes.get("status", ""))
    if command.from_states and subject_state not in command.from_states:
        raise WorkflowConflict("وضعیت موضوع با فرمان لغو سازگار نیست.")
    if command.include_work_item:
        raise ValidationError("این فرمان فقط در تکمیل کار تخصیص‌یافته مجاز است.")
    command.executor(
        subject=snapshot.subject,
        actor=actor,
        organization=organization,
        outcome="cancelled",
        context={"reason": reason.strip(), **(command_context or {})},
        idempotency_key=idempotency_key,
    )
    previous_state = instance.status
    if step:
        _cancel_open_items(
            step=step,
            actor=actor,
            actor_membership=actor_membership,
            reason=reason.strip(),
        )
        now = timezone.now()
        _raw_update(
            WorkflowStepInstance.objects.filter(pk=step.pk),
            status=WorkflowStepInstanceStatus.CANCELLED,
            cancelled_at=now,
            updated_at=now,
        )
    now = timezone.now()
    _raw_update(
        WorkflowInstance.objects.filter(pk=instance.pk),
        status=WorkflowInstanceStatus.CANCELLED,
        cancelled_at=now,
        cancellation_reason=reason.strip(),
        processed_operations=_processed_operations(
            instance=instance, idempotency_key=idempotency_key, action=action
        ),
        updated_at=now,
    )
    _audit(
        action=AuditAction.WORKFLOW_INSTANCE_CANCELLED,
        entity_type="workflows.WorkflowInstance",
        entity_id=instance.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "previous_state": previous_state,
            "new_state": "cancelled",
            "reason": reason.strip(),
            "domain_command": command_key,
        },
    )
    instance.refresh_from_db()
    return instance


@transaction.atomic
def migrate_workflow_instance(
    *,
    actor: User,
    organization: Organization,
    instance_id: object,
    target_version_id: object,
    reason: str,
    idempotency_key: str,
) -> WorkflowInstance:
    actor_membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_MIGRATE_INSTANCES,
        allow_any_scope=True,
    )
    if not reason.strip():
        raise ValidationError("دلیل مهاجرت نسخه الزامی است.")
    _, instance, step = _lock_instance_runtime(
        actor=actor, organization=organization, instance_id=instance_id
    )
    actor_membership = _require_instance_permission(
        actor=actor,
        organization=organization,
        instance=instance,
        permission=BusinessPermissionCode.WORKFLOWS_MIGRATE_INSTANCES,
    )
    if _operation_already_processed(
        instance=instance, idempotency_key=idempotency_key, action="migrate"
    ):
        return instance
    if (
        instance.status
        not in (
            WorkflowInstanceStatus.ACTIVE,
            WorkflowInstanceStatus.SUSPENDED,
        )
        or step is None
    ):
        raise WorkflowConflict("فقط اجرای باز قابل مهاجرت است.")
    try:
        target = WorkflowVersion.objects.select_related(
            "definition__workflow_type"
        ).get(
            pk=target_version_id,
            organization=organization,
            definition=instance.definition,
            status=WorkflowVersionStatus.PUBLISHED,
        )
    except (ValueError, WorkflowVersion.DoesNotExist) as exc:
        raise ValidationError("نسخه مقصد منتشرشده و متعلق به همین تعریف نیست.") from exc
    issues = validate_workflow_version(target)
    if issues:
        raise ValidationError([item.message for item in issues])
    target_step = target.steps.filter(key=step.step_definition.key).first()
    if target_step is None:
        raise ValidationError("گام فعال در نسخه مقصد نگاشت قطعی ندارد.")
    previous_version_id = instance.version_id
    _cancel_open_items(
        step=step,
        actor=actor,
        actor_membership=actor_membership,
        reason="version_migration",
    )
    now = timezone.now()
    _raw_update(
        WorkflowStepInstance.objects.filter(pk=step.pk),
        status=WorkflowStepInstanceStatus.CANCELLED,
        cancelled_at=now,
        updated_at=now,
    )
    _raw_update(
        WorkflowInstance.objects.filter(pk=instance.pk),
        version=target,
        status=WorkflowInstanceStatus.ACTIVE,
        suspended_at=None,
        suspension_reason="",
        processed_operations=_processed_operations(
            instance=instance, idempotency_key=idempotency_key, action="migrate"
        ),
        updated_at=now,
    )
    instance.version = target
    instance.status = WorkflowInstanceStatus.ACTIVE
    _activate_step(
        instance=instance,
        step=target_step,
        actor=actor,
        actor_membership=actor_membership,
    )
    _audit(
        action=AuditAction.WORKFLOW_INSTANCE_MIGRATED,
        entity_type="workflows.WorkflowInstance",
        entity_id=instance.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "from_version_id": str(previous_version_id),
            "to_version_id": str(target.pk),
            "mapped_step_key": target_step.key,
            "reason": reason.strip(),
        },
    )
    instance.refresh_from_db()
    return instance


@transaction.atomic
def create_workflow_delegation(
    *,
    actor: User,
    organization: Organization,
    delegator_membership_id: object,
    delegate_membership_id: object,
    starts_at: Any,
    ends_at: Any,
    reason: str,
    idempotency_key: str,
    workflow_type_code: str | None = None,
    permission_code: str | None = None,
    scope: dict[str, Any] | None = None,
) -> WorkflowDelegation:
    actor_membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_DELEGATE,
        allow_any_scope=True,
    )
    if not idempotency_key.strip():
        raise ValidationError("کلید تکرارپذیری واگذاری الزامی است.")
    if not reason.strip():
        raise ValidationError("دلیل واگذاری الزامی است.")
    if not permission_code:
        raise ValidationError("واگذاری باید به یک مجوز کسب‌وکار محدود باشد.")
    if starts_at >= ends_at:
        raise ValidationError("پایان واگذاری باید پس از شروع آن باشد.")
    if str(delegator_membership_id) == str(delegate_membership_id):
        raise PermissionDenied("واگذاری به همان عضویت مجاز نیست.")
    Organization.objects.select_for_update().get(pk=organization.pk)
    existing = WorkflowDelegation.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if str(existing.delegator_id) != str(delegator_membership_id) or str(
            existing.delegate_id
        ) != str(delegate_membership_id):
            raise ValidationError("کلید تکرارپذیری برای واگذاری دیگری استفاده شده است.")
        return existing
    authority_ids = sorted(
        {
            str(actor_membership.pk),
            str(delegator_membership_id),
            str(delegate_membership_id),
        }
    )
    for membership_id in authority_ids:
        _lock_membership_authority(
            organization=organization,
            membership_id=membership_id,
        )
    actor_membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_DELEGATE,
        allow_any_scope=True,
    )
    memberships = list(
        OrganizationMembership.objects.select_for_update(of=("self",))
        .select_related("role_definition", "user")
        .filter(
            organization=organization,
            pk__in=(delegator_membership_id, delegate_membership_id),
            status=MembershipStatus.ACTIVE,
            user__is_active=True,
        )
        .prefetch_related("role_assignments__role__permissions", "scope_grants")
        .order_by("pk")
    )
    by_id = {str(item.pk): item for item in memberships}
    try:
        delegator = by_id[str(delegator_membership_id)]
        delegate = by_id[str(delegate_membership_id)]
    except KeyError as exc:
        raise PermissionDenied("عضویت واگذارکننده یا جانشین معتبر نیست.") from exc
    workflow_type = None
    if workflow_type_code:
        try:
            workflow_type = WorkflowType.objects.get(
                code=workflow_type_code, is_active=True
            )
        except WorkflowType.DoesNotExist as exc:
            raise ValidationError("نوع گردش‌کار واگذاری ثبت نشده است.") from exc
    permission = None
    if permission_code:
        try:
            permission = BusinessPermission.objects.get(
                code=permission_code, is_active=True
            )
        except BusinessPermission.DoesNotExist as exc:
            raise ValidationError("مجوز واگذاری ثبت نشده است.") from exc
    if not membership_has_permission(
        delegator, permission_code
    ) or not membership_has_permission(delegate, permission_code):
        raise PermissionDenied(
            "واگذارکننده و جانشین باید مستقلاً مجوز کسب‌وکار لازم را داشته باشند."
        )
    normalized_scope = scope or {}
    project = None
    site = None
    project_id = normalized_scope.get("project_id")
    site_id = normalized_scope.get("site_id")
    if project_id:
        project = Project.objects.filter(
            pk=project_id, organization=organization, deleted_at__isnull=True
        ).first()
        if project is None:
            raise PermissionDenied("پروژه واگذاری در این سازمان یافت نشد.")
    if site_id:
        if project is None:
            raise ValidationError("دامنه کارگاه باید پروژه را نیز مشخص کند.")
        site = ProjectSite.objects.filter(
            pk=site_id,
            organization=organization,
            project=project,
            is_active=True,
        ).first()
        if site is None:
            raise PermissionDenied("کارگاه واگذاری در این پروژه یافت نشد.")
    for membership in (actor_membership, delegator, delegate):
        if not membership_has_scope(membership, project=project, site=site):
            raise PermissionDenied(
                "دامنه واگذاری خارج از اختیار مؤثر یکی از عوامل است."
            )
    if (
        WorkflowDelegation.objects.filter(
            organization=organization,
            delegate=delegator,
            revoked_at__isnull=True,
            starts_at__lt=ends_at,
            ends_at__gt=starts_at,
        )
        .filter(permission__code=permission_code)
        .exists()
    ):
        raise PermissionDenied("واگذاری زنجیره‌ای مجاز نیست.")
    delegation = WorkflowDelegation.objects.create(
        organization=organization,
        delegator=delegator,
        delegate=delegate,
        workflow_type=workflow_type,
        permission=permission,
        scope=normalized_scope,
        idempotency_key=idempotency_key,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason.strip(),
        created_by=actor_membership,
    )
    _audit(
        action=AuditAction.WORKFLOW_DELEGATION_CREATED,
        entity_type="workflows.WorkflowDelegation",
        entity_id=delegation.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={
            "delegator_membership_id": str(delegator.pk),
            "delegate_membership_id": str(delegate.pk),
            "permission": permission_code,
            "workflow_type": workflow_type_code,
            "reason": reason.strip(),
        },
    )
    return delegation


@transaction.atomic
def revoke_workflow_delegation(
    *,
    actor: User,
    organization: Organization,
    delegation_id: object,
    reason: str,
) -> WorkflowDelegation:
    actor_membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_DELEGATE,
        allow_any_scope=True,
    )
    if not reason.strip():
        raise ValidationError("دلیل لغو واگذاری الزامی است.")
    try:
        delegation = WorkflowDelegation.objects.select_for_update().get(
            pk=delegation_id, organization=organization
        )
    except (ValueError, WorkflowDelegation.DoesNotExist) as exc:
        raise PermissionDenied("واگذاری در این سازمان یافت نشد.") from exc
    _lock_membership_authority(
        organization=organization,
        membership_id=actor_membership.pk,
    )
    actor_membership = _require_permission(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.WORKFLOWS_DELEGATE,
        allow_any_scope=True,
    )
    project = None
    site = None
    if delegation.scope.get("project_id"):
        project = Project.objects.filter(
            pk=delegation.scope["project_id"], organization=organization
        ).first()
    if project is not None and delegation.scope.get("site_id"):
        site = ProjectSite.objects.filter(
            pk=delegation.scope["site_id"],
            organization=organization,
            project=project,
        ).first()
    if not membership_has_scope(actor_membership, project=project, site=site):
        raise PermissionDenied("دامنه این واگذاری خارج از اختیار عامل است.")
    if delegation.revoked_at:
        return delegation
    delegation.revoked_at = timezone.now()
    delegation.revoked_by = actor_membership
    delegation.revoke_reason = reason.strip()
    delegation.save(
        update_fields=["revoked_at", "revoked_by", "revoke_reason", "updated_at"]
    )
    _audit(
        action=AuditAction.WORKFLOW_DELEGATION_REVOKED,
        entity_type="workflows.WorkflowDelegation",
        entity_id=delegation.pk,
        organization=organization,
        actor=actor,
        actor_membership=actor_membership,
        metadata={"reason": reason.strip()},
    )
    return delegation
