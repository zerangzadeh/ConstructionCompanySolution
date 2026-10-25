"""W5.2 compatibility workflow for the existing safety incident lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from hashlib import sha256
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import (
    get_active_membership,
    membership_has_permission,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.workflows.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowRoutingRule,
    WorkflowStepDefinition,
    WorkflowStepInstance,
    WorkflowStepInstanceStatus,
    WorkflowTemplate,
    WorkflowTransitionDefinition,
    WorkflowType,
    WorkflowVersion,
    WorkflowVersionStatus,
    WorkItem,
    WorkItemCandidate,
    WorkItemStatus,
    canonical_scope,
)
from apps.workflows.registry import SubjectSnapshot, registry
from apps.workflows.routing import resolve_step_candidates
from apps.workflows.runtime import (
    WorkflowConflict,
    claim_work_item,
    complete_work_item,
    start_workflow,
)
from apps.workflows.validators import validate_workflow_version

from .models import SafetyIncident, SafetyIncidentStatus

WORKFLOW_TYPE_CODE = "safety.safety_incident_lifecycle"
SUBJECT_TYPE = "safety.safety_incident"
TEMPLATE_CODE = "safety_incident_legacy_compatibility"
DEFINITION_CODE = "safety-incident-legacy-compatibility"

STAGES = (
    (
        "review",
        "بررسی حادثه",
        "reported",
        "review",
        "under_review",
        "safety_incidents.review",
    ),
    (
        "assign",
        "تعیین مسئول",
        "under_review",
        "assign",
        "assigned",
        "safety_incidents.review",
    ),
    (
        "start_action",
        "آغاز اقدام",
        "assigned",
        "start_action",
        "action_in_progress",
        "safety_incidents.manage",
    ),
    (
        "resolve",
        "ثبت رفع",
        "action_in_progress",
        "resolve",
        "resolved",
        "safety_incidents.manage",
    ),
    ("close", "بستن حادثه", "resolved", "close", "closed", "safety_incidents.close"),
)
STATUS_STEP = {stage[2]: stage[0] for stage in STAGES}
STATUS_PERMISSION = {stage[2]: stage[5] for stage in STAGES}


def _routes(step_key: str, permission: str) -> list[dict[str, Any]]:
    del step_key
    return [
        {
            "resolver_type": "business_permission",
            "configuration": {"permission": permission},
        },
    ]


COMPATIBILITY_CONFIGURATION: dict[str, Any] = {
    "steps": [
        {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
        *[
            {
                "key": key,
                "name": title,
                "step_type": "approval",
                "required_permission": permission,
                "configuration": {"decision_policy": "any"},
                "routing": _routes(key, permission),
            }
            for key, title, _, _, _, permission in STAGES
        ],
        {"key": "closed", "name": "بسته‌شده", "step_type": "end", "is_terminal": True},
    ],
    "transitions": [
        {
            "source": "start",
            "target": "review",
            "outcome": "reported",
            "is_default": True,
        },
        *[
            {
                "source": key,
                "target": STAGES[index + 1][0] if index + 1 < len(STAGES) else "closed",
                "outcome": outcome,
                "domain_command": f"safety.safety_incident.{command}",
                "required_permission": permission,
            }
            for index, (key, _, _, command, outcome, permission) in enumerate(STAGES)
        ],
    ],
}


def _key(*parts: object) -> str:
    return sha256(":".join(str(part) for part in parts).encode()).hexdigest()


def _active_membership_id(organization: Organization, user_id: object) -> str | None:
    if not user_id:
        return None
    value = (
        OrganizationMembership.objects.filter(
            organization=organization,
            user_id=user_id,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
        )
        .values_list("pk", flat=True)
        .first()
    )
    return str(value) if value else None


def _responsible_display(incident: SafetyIncident) -> str:
    names: list[str] = []
    if incident.responsible_user_id:
        user = incident.responsible_user
        names.append(user.get_full_name() or user.username)
    if incident.responsible_employee_id:
        names.append(str(incident.responsible_employee))
    if incident.responsible_party_id:
        names.append(str(incident.responsible_party))
    return "، ".join(names)


def _sync_active_work_item_deadline(
    *, incident: SafetyIncident, instance: WorkflowInstance
) -> None:
    if incident.due_date is None:
        return
    due_at = datetime.combine(
        incident.due_date,
        time.max,
        tzinfo=ZoneInfo(incident.organization.settings.timezone),
    )
    WorkItem.objects.filter(
        organization=incident.organization,
        instance=instance,
        status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
    ).update(due_at=due_at)


def load_safety_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_VIEW,
        allow_any_scope=True,
        message="اجازه مشاهده حادثه ایمنی را ندارید.",
    )
    queryset = SafetyIncident.objects.select_related(
        "organization__settings",
        "project",
        "site",
        "responsible_user",
        "responsible_employee",
        "responsible_party",
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        incident = queryset.get(pk=subject_id, organization=organization)
    except SafetyIncident.DoesNotExist as exc:
        raise PermissionDenied("حادثه در این سازمان یافت نشد.") from exc
    if (
        incident.project.organization_id != organization.pk
        or (incident.site_id and incident.site.organization_id != organization.pk)
        or (incident.site_id and incident.site.project_id != incident.project_id)
    ):
        raise PermissionDenied("دامنه حادثه ایمنی نامعتبر است.")
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_VIEW,
        project=incident.project,
        site=incident.site,
        allow_site_parent=True,
        message="اجازه مشاهده حادثه ایمنی را ندارید.",
    )
    return SubjectSnapshot(
        subject=incident,
        subject_id=str(incident.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(incident.project_id),
            "site_id": str(incident.site_id) if incident.site_id else None,
            "status": incident.status,
            "created_by_id": str(incident.created_by_id)
            if incident.created_by_id
            else None,
            "responsible_display": _responsible_display(incident),
        },
        creator_membership_id=_active_membership_id(
            organization, incident.created_by_id
        ),
        display=f"حادثه {incident.incident_number}",
    )


def _command(action: str):
    def execute(
        *,
        subject: SafetyIncident,
        actor: User,
        organization: Organization,
        context: dict[str, Any],
        **_: object,
    ) -> SafetyIncident:
        from . import services

        required = {
            "review": (),
            "assign": ("due_date",),
            "start_action": ("corrective_action",),
            "resolve": ("resolution_summary",),
            "close": ("closure_summary",),
        }[action]
        if any(not context.get(field) for field in required):
            raise ValidationError("اطلاعات الزامی اقدام ایمنی کامل نیست.")
        operation = {
            "review": services._review_safety_incident_domain,
            "assign": services._assign_safety_incident_domain,
            "start_action": services._start_corrective_action_domain,
            "resolve": services._resolve_safety_incident_domain,
            "close": services._close_safety_incident_domain,
        }[action]
        return operation(
            organization=organization,
            actor=actor,
            incident_id=str(subject.pk),
            **context,
        )

    return execute


def register_safety_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_safety_subject)
    for action in ("review", "assign", "start_action", "resolve", "close"):
        registry.bind_domain_command(
            f"safety.safety_incident.{action}", _command(action)
        )


def _write_configuration(
    *,
    organization: Organization,
    version: WorkflowVersion,
    configuration: dict[str, Any],
) -> None:
    steps: dict[str, WorkflowStepDefinition] = {}
    for item in configuration["steps"]:
        step = WorkflowStepDefinition.objects.create(
            organization=organization,
            version=version,
            key=item["key"],
            name=item["name"],
            step_type=item["step_type"],
            is_start=item.get("is_start", False),
            is_terminal=item.get("is_terminal", False),
            required_permission=item.get("required_permission", ""),
            configuration=item.get("configuration", {}),
        )
        steps[step.key] = step
        for order, route in enumerate(item.get("routing", [])):
            WorkflowRoutingRule.objects.create(
                organization=organization,
                version=version,
                step=step,
                resolver_type=route["resolver_type"],
                configuration=route.get("configuration", {}),
                order=order,
                is_fallback=route.get("is_fallback", False),
            )
    for item in configuration["transitions"]:
        WorkflowTransitionDefinition.objects.create(
            organization=organization,
            version=version,
            source_step=steps[item["source"]],
            target_step=steps[item["target"]],
            outcome=item["outcome"],
            domain_command=item.get("domain_command", ""),
            required_permission=item.get("required_permission", ""),
            is_default=item.get("is_default", False),
        )


@transaction.atomic
def ensure_safety_compatibility_workflow(
    *, organization: Organization, actor: User
) -> WorkflowVersion:
    get_active_membership(user=actor, organization=organization)
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    workflow_type = WorkflowType.objects.get(code=WORKFLOW_TYPE_CODE, is_active=True)
    _, scope_key = canonical_scope({})
    existing = (
        WorkflowVersion.objects.select_related("definition")
        .filter(
            organization=locked,
            definition__workflow_type=workflow_type,
            definition__scope_key=scope_key,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        .first()
    )
    if existing:
        if validate_workflow_version(existing):
            raise ValidationError("نسخه منتشرشده ایمنی معتبر نیست.")
        return existing
    template = WorkflowTemplate.objects.get(
        workflow_type=workflow_type, code=TEMPLATE_CODE, is_active=True
    )
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked,
        workflow_type=workflow_type,
        scope_key=scope_key,
        defaults={
            "code": DEFINITION_CODE,
            "name": "سازگاری چرخه حادثه ایمنی",
            "description": "رفتار مرحله‌ای فعلی ایمنی را حفظ می‌کند.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض ایمنی نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked,
        definition=definition,
        version_number=1,
        change_summary="W5.2 legacy compatibility",
    )
    _write_configuration(
        organization=locked, version=version, configuration=template.configuration
    )
    issues = validate_workflow_version(version)
    if issues:
        raise ValidationError([issue.message for issue in issues])
    now = timezone.now()
    models.QuerySet.update(
        WorkflowVersion.objects.filter(pk=version.pk),
        status=WorkflowVersionStatus.PUBLISHED,
        validation_report=[],
        validated_at=now,
        validated_by=actor,
        published_at=now,
        published_by=actor,
        updated_at=now,
    )
    for action, entity_type, entity_id in (
        (
            AuditAction.WORKFLOW_DEFINITION_CREATED,
            "workflows.WorkflowDefinition",
            definition.pk,
        ),
        (
            AuditAction.WORKFLOW_VERSION_PUBLISHED,
            "workflows.WorkflowVersion",
            version.pk,
        ),
    ):
        record_audit_event(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            organization=locked,
            actor=actor,
            metadata={"workflow_type": WORKFLOW_TYPE_CODE, "compatibility": True},
        )
    version.refresh_from_db()
    return version


def resolve_safety_version(
    *, organization: Organization, incident: SafetyIncident
) -> WorkflowVersion:
    if incident.organization_id != organization.pk:
        raise PermissionDenied("حادثه متعلق به سازمان دیگری است.")
    context = {
        "project_id": str(incident.project_id),
        "site_id": str(incident.site_id) if incident.site_id else None,
    }
    matches = [
        (len(version.definition.scope), version)
        for version in WorkflowVersion.objects.select_related("definition").filter(
            organization=organization,
            definition__workflow_type__code=WORKFLOW_TYPE_CODE,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        if all(
            context.get(key) == value for key, value in version.definition.scope.items()
        )
    ]
    if not matches:
        raise ValidationError("نسخه منتشرشده برای حادثه ایمنی یافت نشد.")
    specificity = max(score for score, _ in matches)
    selected = [version for score, version in matches if score == specificity]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار ایمنی مبهم است.")
    return selected[0]


def _eligible_membership_exists(organization: Organization, permission: str) -> bool:
    return OrganizationMembership.objects.filter(
        organization=organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
        role_definition__permissions__code=permission,
        role_definition__permissions__is_active=True,
    ).exists()


@transaction.atomic
def start_safety_workflow(
    *, organization: Organization, incident: SafetyIncident, actor: User
) -> WorkflowInstance | None:
    if (
        incident.organization_id != organization.pk
        or incident.status == SafetyIncidentStatus.CLOSED
    ):
        raise PermissionDenied("حادثه باز متعلق به این سازمان نیست.")
    existing = WorkflowInstance.objects.filter(
        organization=organization,
        subject_type=SUBJECT_TYPE,
        subject_id=incident.pk,
    ).first()
    if existing is not None:
        if existing.status != WorkflowInstanceStatus.ACTIVE:
            raise WorkflowConflict("گردش‌کار فعلی حادثه برای اقدام فعال نیست.")
        _sync_active_work_item_deadline(incident=incident, instance=existing)
        return existing
    permission = STATUS_PERMISSION[incident.status]
    if not _eligible_membership_exists(organization, permission):
        return None
    ensure_safety_compatibility_workflow(organization=organization, actor=actor)
    version = resolve_safety_version(organization=organization, incident=incident)
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=incident.pk,
        idempotency_key=_key(WORKFLOW_TYPE_CODE, incident.pk, "start"),
        initial_step_key=(
            STATUS_STEP[incident.status]
            if incident.status != SafetyIncidentStatus.REPORTED
            else None
        ),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("حادثه بدون کار فعال وارد گردش‌کار نمی‌شود.")
    _sync_active_work_item_deadline(incident=incident, instance=instance)
    return instance


def _backfill_actor(incident: SafetyIncident) -> User | None:
    memberships = OrganizationMembership.objects.filter(
        organization=incident.organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
    ).select_related("user", "role_definition")
    preferred = memberships.filter(user_id=incident.updated_by_id).first()
    if preferred and membership_has_permission(
        preferred, BusinessPermissionCode.SAFETY_INCIDENTS_VIEW
    ):
        return preferred.user
    for membership in memberships.filter(role_definition__is_owner=True):
        if membership_has_permission(
            membership, BusinessPermissionCode.SAFETY_INCIDENTS_VIEW
        ):
            return membership.user
    return None


def _reconcile_open_candidates(
    *, incident: SafetyIncident, instance: WorkflowInstance, actor: User
) -> None:
    if instance.definition.code != DEFINITION_CODE:
        return
    instance = WorkflowInstance.objects.select_for_update().get(
        pk=instance.pk,
        organization=incident.organization,
        status=WorkflowInstanceStatus.ACTIVE,
    )
    step = WorkflowStepInstance.objects.select_for_update().get(
        organization=incident.organization,
        instance=instance,
        status=WorkflowStepInstanceStatus.ACTIVE,
    )
    if step.step_definition.key != STATUS_STEP[incident.status]:
        raise WorkflowConflict("گام فعال با وضعیت حادثه ایمنی سازگار نیست.")
    items = list(
        WorkItem.objects.select_for_update().filter(
            organization=incident.organization,
            instance=instance,
            step_instance=step,
            status=WorkItemStatus.OPEN,
            current_assignee__isnull=True,
        )
    )
    if len(items) != 1:
        raise WorkflowConflict("کار بازِ قابل بازپُرکنی ایمنی یکتا نیست.")
    item = items[0]
    result = resolve_step_candidates(
        instance=instance,
        step_id=step.step_definition_id,
        required_permission=item.required_permission,
    )
    routed = {
        str(candidate.membership.pk): candidate for candidate in result.candidates
    }
    legacy = {
        str(membership_id)
        for membership_id in OrganizationMembership.objects.filter(
            organization=incident.organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=STATUS_PERMISSION[incident.status],
            role_definition__permissions__is_active=True,
        ).values_list("pk", flat=True)
    }
    if not routed or set(routed) != legacy:
        raise WorkflowConflict("مسیریابی فعلی با مجوزهای legacy ایمنی سازگار نیست.")
    current = {
        str(candidate.membership_id): candidate
        for candidate in WorkItemCandidate.objects.select_for_update().filter(
            organization=incident.organization,
            work_item=item,
            is_active=True,
        )
    }
    added = sorted(set(routed) - set(current))
    removed = sorted(set(current) - set(routed))
    if not added and not removed:
        return
    now = timezone.now()
    for membership_id in removed:
        WorkItemCandidate.objects.filter(pk=current[membership_id].pk).update(
            is_active=False,
            removed_at=now,
            removal_reason="w5.2_backfill_reconcile",
        )
    for membership_id in added:
        candidate = routed[membership_id]
        WorkItemCandidate.objects.create(
            organization=incident.organization,
            work_item=item,
            membership=candidate.membership,
            qualifying_position_assignment=candidate.position_assignment,
            routing_basis=candidate.routing_basis,
        )
    record_audit_event(
        action=AuditAction.WORKFLOW_CANDIDATES_CHANGED,
        entity_type="workflows.WorkflowStepInstance",
        entity_id=str(step.pk),
        organization=incident.organization,
        actor=actor,
        metadata={
            "change": "w5.2_backfill_reconcile",
            "work_item_id": str(item.pk),
            "added_membership_ids": added,
            "removed_membership_ids": removed,
        },
    )


@transaction.atomic
def _backfill_one(*, incident: SafetyIncident, actor: User) -> str:
    try:
        locked = SafetyIncident.objects.select_for_update().get(
            pk=incident.pk, organization=incident.organization
        )
    except SafetyIncident.DoesNotExist:
        return "skipped"
    if locked.status == SafetyIncidentStatus.CLOSED:
        return "skipped"
    was_present = WorkflowInstance.objects.filter(
        organization=locked.organization,
        subject_type=SUBJECT_TYPE,
        subject_id=locked.pk,
    ).exists()
    instance = start_safety_workflow(
        organization=locked.organization, incident=locked, actor=actor
    )
    if instance is None:
        return "skipped"
    if was_present:
        _reconcile_open_candidates(incident=locked, instance=instance, actor=actor)
    return "existing" if was_present else "created"


@dataclass(frozen=True, slots=True)
class BackfillReport:
    scanned: int = 0
    created: int = 0
    existing: int = 0
    skipped: int = 0


def backfill_open_safety_incidents(
    *, organization: Organization | None = None
) -> BackfillReport:
    queryset = SafetyIncident.objects.exclude(
        status=SafetyIncidentStatus.CLOSED
    ).select_related("organization__settings")
    if organization is not None:
        queryset = queryset.filter(organization=organization)
    scanned = created = existing = skipped = 0
    for incident in queryset.select_related("organization", "updated_by").iterator():
        scanned += 1
        actor = _backfill_actor(incident)
        if actor is None:
            skipped += 1
            continue
        try:
            result = _backfill_one(incident=incident, actor=actor)
        except (WorkflowConflict, ValidationError):
            skipped += 1
            continue
        if result == "created":
            created += 1
        elif result == "existing":
            existing += 1
        else:
            skipped += 1
    return BackfillReport(scanned, created, existing, skipped)


def _actor_item(
    *,
    organization: Organization,
    incident: SafetyIncident,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=incident.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای اقدام ایمنی وجود ندارد.")
    return item


@transaction.atomic
def perform_safety_transition(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    expected_status: str,
    outcome: str,
    context: dict[str, Any],
) -> SafetyIncident:
    permission = STATUS_PERMISSION[expected_status]
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        allow_any_scope=True,
        message="اجازه انجام این اقدام ایمنی را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    try:
        incident = SafetyIncident.objects.get(pk=incident_id, organization=organization)
    except SafetyIncident.DoesNotExist as exc:
        raise PermissionDenied("حادثه در این سازمان یافت نشد.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=incident.project,
        site=incident.site,
        allow_site_parent=True,
        message="اجازه انجام این اقدام ایمنی را ندارید.",
    )
    if incident.status != expected_status:
        raise ValueError("وضعیت حادثه برای این اقدام معتبر نیست.")
    if not WorkflowInstance.objects.filter(
        organization=organization, subject_type=SUBJECT_TYPE, subject_id=incident.pk
    ).exists():
        starter = _backfill_actor(incident)
        if starter is not None:
            try:
                with transaction.atomic():
                    _backfill_one(incident=incident, actor=starter)
            except WorkflowConflict:
                pass
    if not WorkflowInstance.objects.filter(
        organization=organization, subject_type=SUBJECT_TYPE, subject_id=incident.pk
    ).exists():
        # Legacy records without an actionable route remain on their domain path.
        from . import services

        operation = {
            "under_review": services._review_safety_incident_domain,
            "assigned": services._assign_safety_incident_domain,
            "action_in_progress": services._start_corrective_action_domain,
            "resolved": services._resolve_safety_incident_domain,
            "closed": services._close_safety_incident_domain,
        }[outcome]
        return operation(
            organization=organization, actor=actor, incident_id=incident_id, **context
        )
    item = _actor_item(
        organization=organization, incident=incident, membership=membership
    )
    if item.status == WorkItemStatus.OPEN:
        item = claim_work_item(
            actor=actor,
            organization=organization,
            work_item_id=item.pk,
            idempotency_key=_key(item.pk, membership.pk, "claim"),
        )
    elif item.current_assignee_id != membership.pk:
        raise PermissionDenied("کار به عضویت دیگری تخصیص یافته است.")
    complete_work_item(
        actor=actor,
        organization=organization,
        work_item_id=item.pk,
        outcome=outcome,
        idempotency_key=_key(item.pk, membership.pk, outcome),
        command_context=context,
    )
    incident.refresh_from_db()
    instance = WorkflowInstance.objects.get(
        organization=organization,
        subject_type=SUBJECT_TYPE,
        subject_id=incident.pk,
    )
    _sync_active_work_item_deadline(incident=incident, instance=instance)
    return incident


def safety_shadow_comparison(
    *, organization: Organization, incident: SafetyIncident
) -> dict[str, Any]:
    if incident.organization_id != organization.pk:
        raise PermissionDenied("حادثه متعلق به سازمان دیگری است.")
    permission = STATUS_PERMISSION.get(incident.status)
    if permission is None:
        raise ValidationError("حادثه بسته‌شده کار باز ندارد.")
    legacy_ids = {
        str(membership.pk)
        for membership in OrganizationMembership.objects.filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=permission,
            role_definition__permissions__is_active=True,
        )
    }
    candidates = WorkItemCandidate.objects.filter(
        organization=organization,
        work_item__instance__subject_type=SUBJECT_TYPE,
        work_item__instance__subject_id=incident.pk,
        work_item__status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        is_active=True,
    ).select_related("membership__role_definition")
    workflow_ids = {str(item.membership_id) for item in candidates}
    required_runtime = (
        BusinessPermissionCode.WORK_ITEMS_VIEW,
        BusinessPermissionCode.WORK_ITEMS_CLAIM,
        BusinessPermissionCode.WORK_ITEMS_ACT,
    )
    blocked_ids = sorted(
        {
            str(item.membership_id)
            for item in candidates
            if not all(
                membership_has_permission(item.membership, code)
                for code in required_runtime
            )
        }
    )
    missing = sorted(legacy_ids - workflow_ids)
    unexpected = sorted(workflow_ids - legacy_ids)
    return {
        "incident_id": str(incident.pk),
        "legacy_membership_ids": sorted(legacy_ids),
        "workflow_membership_ids": sorted(workflow_ids),
        "missing_membership_ids": missing,
        "unexpected_membership_ids": unexpected,
        "blocked_runtime_permission_membership_ids": blocked_ids,
        "mismatch": bool(missing or unexpected or blocked_ids),
    }
