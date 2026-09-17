"""W5.7 orchestration for actionable equipment maintenance records."""

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

from .models import MaintenanceRecord, MaintenanceStatus

SUBJECT_TYPE = "equipment.maintenance_record"
WORKFLOW_TYPE_CODE = "equipment.maintenance_record_lifecycle"
TEMPLATE_CODE = "maintenance_record_lifecycle_legacy_compatibility"
DEFINITION_CODE = "maintenance-record-lifecycle-legacy-compatibility"
TRANSITION_PERMISSION = BusinessPermissionCode.MAINTENANCE_RECORDS_TRANSITION

_COMMANDS = {
    MaintenanceStatus.IN_PROGRESS: "equipment.maintenance_record.start",
    MaintenanceStatus.COMPLETED: "equipment.maintenance_record.complete",
    MaintenanceStatus.CANCELLED: "equipment.maintenance_record.cancel",
}

COMPATIBILITY_CONFIGURATION: dict[str, Any] = {
    "steps": [
        {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
        {
            "key": "scheduled",
            "name": "شروع یا لغو سرویس",
            "step_type": "approval",
            "configuration": {"decision_policy": "any"},
            "routing": [
                {
                    "resolver_type": "business_permission",
                    "configuration": {"permission": TRANSITION_PERMISSION},
                },
                {
                    "resolver_type": "organization_owner",
                    "configuration": {},
                    "is_fallback": True,
                },
            ],
        },
        {
            "key": "in_progress",
            "name": "تکمیل یا لغو سرویس",
            "step_type": "approval",
            "configuration": {"decision_policy": "any"},
            "routing": [
                {
                    "resolver_type": "business_permission",
                    "configuration": {"permission": TRANSITION_PERMISSION},
                },
                {
                    "resolver_type": "organization_owner",
                    "configuration": {},
                    "is_fallback": True,
                },
            ],
        },
        {
            "key": "completed",
            "name": "تکمیل‌شده",
            "step_type": "end",
            "is_terminal": True,
        },
        {"key": "cancelled", "name": "لغوشده", "step_type": "end", "is_terminal": True},
    ],
    "transitions": [
        {
            "source": "start",
            "target": "scheduled",
            "outcome": "requested",
            "is_default": True,
        },
        {
            "source": "scheduled",
            "target": "in_progress",
            "outcome": MaintenanceStatus.IN_PROGRESS,
            "domain_command": _COMMANDS[MaintenanceStatus.IN_PROGRESS],
            "required_permission": TRANSITION_PERMISSION,
        },
        {
            "source": "scheduled",
            "target": "completed",
            "outcome": MaintenanceStatus.COMPLETED,
            "domain_command": _COMMANDS[MaintenanceStatus.COMPLETED],
            "required_permission": TRANSITION_PERMISSION,
        },
        {
            "source": "scheduled",
            "target": "cancelled",
            "outcome": MaintenanceStatus.CANCELLED,
            "domain_command": _COMMANDS[MaintenanceStatus.CANCELLED],
            "required_permission": TRANSITION_PERMISSION,
        },
        {
            "source": "in_progress",
            "target": "completed",
            "outcome": MaintenanceStatus.COMPLETED,
            "domain_command": _COMMANDS[MaintenanceStatus.COMPLETED],
            "required_permission": TRANSITION_PERMISSION,
        },
        {
            "source": "in_progress",
            "target": "cancelled",
            "outcome": MaintenanceStatus.CANCELLED,
            "domain_command": _COMMANDS[MaintenanceStatus.CANCELLED],
            "required_permission": TRANSITION_PERMISSION,
        },
    ],
}


def _key(*parts: object) -> str:
    return sha256(":".join(str(part) for part in parts).encode()).hexdigest()


def _active_membership_id(organization: Organization, user_id: object) -> str | None:
    if not user_id:
        return None
    membership_id = (
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
    return str(membership_id) if membership_id else None


def _due_at(record: MaintenanceRecord) -> datetime:
    return datetime.combine(
        record.scheduled_date,
        time.max,
        tzinfo=ZoneInfo(record.organization.timezone),
    )


def _sync_active_work_item_deadline(
    *, record: MaintenanceRecord, instance: WorkflowInstance
) -> None:
    WorkItem.objects.filter(
        organization=record.organization,
        instance=instance,
        status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
    ).update(due_at=_due_at(record))


def load_maintenance_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.MAINTENANCE_RECORDS_VIEW,
        message="اجازه مشاهده سوابق سرویس یا تعمیر را ندارید.",
    )
    queryset = MaintenanceRecord.objects.select_related("equipment", "project", "site")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        record = queryset.get(pk=subject_id, organization=organization)
    except MaintenanceRecord.DoesNotExist as exc:
        raise PermissionDenied("سابقه سرویس یا تعمیر در این سازمان یافت نشد.") from exc
    if (
        record.equipment.organization_id != organization.pk
        or (record.project_id and record.project.organization_id != organization.pk)
        or (record.site_id and record.site.organization_id != organization.pk)
        or (record.site_id and record.site.project_id != record.project_id)
    ):
        raise PermissionDenied("دامنه سابقه سرویس یا تعمیر نامعتبر است.")
    return SubjectSnapshot(
        subject=record,
        subject_id=str(record.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(record.project_id) if record.project_id else None,
            "site_id": str(record.site_id) if record.site_id else None,
            "maintenance_type": record.maintenance_type,
            "status": record.status,
            "scheduled_date": record.scheduled_date.isoformat(),
            "created_by_id": str(record.created_by_id)
            if record.created_by_id
            else None,
        },
        creator_membership_id=_active_membership_id(organization, record.created_by_id),
        submitter_membership_id=_active_membership_id(
            organization, record.updated_by_id
        ),
        display=f"سرویس {record.record_number} — {record.summary}",
    )


def _command(target_status: str):
    def execute(
        *,
        subject: MaintenanceRecord,
        actor: User,
        organization: Organization,
        context: dict[str, Any],
        **_: object,
    ) -> MaintenanceRecord:
        effective_date = context.get("effective_date")
        if not hasattr(effective_date, "isoformat"):
            raise ValidationError("تاریخ مؤثر اقدام سرویس یا تعمیر الزامی است.")
        from .services import _transition_maintenance_status_domain

        return _transition_maintenance_status_domain(
            organization=organization,
            actor=actor,
            record=subject,
            target_status=target_status,
            effective_date=effective_date,
            cost=context.get("cost"),
        )

    return execute


def register_maintenance_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_maintenance_subject)
    for target_status, command in _COMMANDS.items():
        registry.bind_domain_command(command, _command(target_status))


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
            name=item.get("name", item["key"]),
            step_type=item["step_type"],
            is_start=item.get("is_start", False),
            is_terminal=item.get("is_terminal", False),
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


def _ensure_maintenance_platform_catalog() -> tuple[WorkflowType, WorkflowTemplate]:
    """Restore this built-in catalog entry if a partial data migration lost it.

    Normal deployments receive these platform-owned rows from migration 0017.
    A database restored from an incomplete dump can have that migration recorded
    without its catalog rows. Recreating only missing rows leaves tenant
    definitions and published runtime history untouched.
    """
    workflow_type, _ = WorkflowType.objects.get_or_create(
        code=WORKFLOW_TYPE_CODE,
        defaults={
            "name": "چرخه سرویس و تعمیر تجهیز",
            "description": "چرخه اقدام‌پذیر سرویس، تعمیر و بازرسی تجهیزات.",
            "subject_type": SUBJECT_TYPE,
            "subject_adapter": SUBJECT_TYPE,
            "allowed_scope_fields": ["project_id", "site_id", "maintenance_type"],
            "is_active": True,
        },
    )
    if not workflow_type.is_active:
        raise ValidationError("نوع گردش‌کار نگهداری تجهیزات غیرفعال است.")
    template, _ = WorkflowTemplate.objects.get_or_create(
        workflow_type=workflow_type,
        code=TEMPLATE_CODE,
        defaults={
            "name": "سازگاری چرخه سرویس و تعمیر تجهیز",
            "description": "سازگاری با lifecycle فعلی نگهداری تجهیزات.",
            "is_active": True,
            "configuration": COMPATIBILITY_CONFIGURATION,
        },
    )
    if not template.is_active:
        raise ValidationError("قالب گردش‌کار نگهداری تجهیزات غیرفعال است.")
    return workflow_type, template


@transaction.atomic
def ensure_maintenance_compatibility_workflow(
    *, organization: Organization, actor: User
) -> WorkflowVersion:
    get_active_membership(user=actor, organization=organization)
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    workflow_type, template = _ensure_maintenance_platform_catalog()
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
            raise ValidationError("گردش‌کار پیش‌فرض نگهداری معتبر نیست.")
        return existing
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked,
        workflow_type=workflow_type,
        scope_key=scope_key,
        defaults={
            "code": DEFINITION_CODE,
            "name": "سازگاری چرخه سرویس و تعمیر تجهیز",
            "description": "چرخه مجاز نگهداری تجهیزات را با مسیر legacy سازگار می‌کند.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض نگهداری نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked,
        definition=definition,
        version_number=1,
        change_summary="W5.7 legacy compatibility",
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


def _resolve_version(
    *, organization: Organization, record: MaintenanceRecord
) -> WorkflowVersion:
    if record.organization_id != organization.pk:
        raise PermissionDenied("سابقه سرویس یا تعمیر متعلق به سازمان دیگری است.")
    context = {
        "project_id": str(record.project_id) if record.project_id else None,
        "site_id": str(record.site_id) if record.site_id else None,
        "maintenance_type": record.maintenance_type,
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
        raise ValidationError("نسخه منتشرشده گردش‌کار نگهداری یافت نشد.")
    specificity = max(score for score, _ in matches)
    selected = [version for score, version in matches if score == specificity]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار نگهداری مبهم است.")
    return selected[0]


def _eligible_membership_exists(organization: Organization) -> bool:
    return OrganizationMembership.objects.filter(
        organization=organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
        role_definition__permissions__code=TRANSITION_PERMISSION,
        role_definition__permissions__is_active=True,
    ).exists()


@transaction.atomic
def start_maintenance_workflow(
    *, organization: Organization, record: MaintenanceRecord, actor: User
) -> WorkflowInstance | None:
    if record.organization_id != organization.pk or record.status not in {
        MaintenanceStatus.SCHEDULED,
        MaintenanceStatus.IN_PROGRESS,
    }:
        raise PermissionDenied("فقط سابقه بازِ همین سازمان قابل ورود به گردش‌کار است.")
    existing = WorkflowInstance.objects.filter(
        organization=organization,
        subject_type=SUBJECT_TYPE,
        subject_id=record.pk,
        status=WorkflowInstanceStatus.ACTIVE,
    ).first()
    if existing is not None:
        _sync_active_work_item_deadline(record=record, instance=existing)
        return existing
    if not _eligible_membership_exists(organization):
        return None
    ensure_maintenance_compatibility_workflow(organization=organization, actor=actor)
    version = _resolve_version(organization=organization, record=record)
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=record.pk,
        idempotency_key=_key(WORKFLOW_TYPE_CODE, record.pk, "start"),
        initial_step_key=(
            "in_progress" if record.status == MaintenanceStatus.IN_PROGRESS else None
        ),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("سابقه نگهداری بدون کار فعال وارد گردش‌کار نمی‌شود.")
    _sync_active_work_item_deadline(record=record, instance=instance)
    return instance


def _backfill_actor(record: MaintenanceRecord) -> User | None:
    memberships = OrganizationMembership.objects.filter(
        organization=record.organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
    ).select_related("user", "role_definition")
    preferred = memberships.filter(user_id=record.updated_by_id).first()
    if preferred and membership_has_permission(preferred, TRANSITION_PERMISSION):
        return preferred.user
    owner = memberships.filter(role_definition__is_owner=True).first()
    return (
        owner.user
        if owner and membership_has_permission(owner, TRANSITION_PERMISSION)
        else None
    )


@transaction.atomic
def _reconcile_open_candidates(
    *, record: MaintenanceRecord, instance: WorkflowInstance, actor: User
) -> None:
    if instance.definition.code != DEFINITION_CODE:
        return
    instance = WorkflowInstance.objects.select_for_update().get(
        pk=instance.pk,
        organization=record.organization,
        status=WorkflowInstanceStatus.ACTIVE,
    )
    step = WorkflowStepInstance.objects.select_for_update().get(
        organization=record.organization,
        instance=instance,
        status=WorkflowStepInstanceStatus.ACTIVE,
    )
    expected_step = (
        "in_progress" if record.status == MaintenanceStatus.IN_PROGRESS else "scheduled"
    )
    if step.step_definition.key != expected_step:
        raise WorkflowConflict("گام فعال با وضعیت نگهداری سازگار نیست.")
    item = (
        WorkItem.objects.select_for_update()
        .filter(
            organization=record.organization,
            instance=instance,
            step_instance=step,
            status=WorkItemStatus.OPEN,
            current_assignee__isnull=True,
        )
        .first()
    )
    if item is None:
        return
    result = resolve_step_candidates(
        instance=instance,
        step_id=step.step_definition_id,
        required_permission=item.required_permission,
    )
    routed = {
        str(candidate.membership.pk): candidate for candidate in result.candidates
    }
    legacy = {
        str(pk)
        for pk in OrganizationMembership.objects.filter(
            organization=record.organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=TRANSITION_PERMISSION,
            role_definition__permissions__is_active=True,
        ).values_list("pk", flat=True)
    }
    if not routed or set(routed) != legacy:
        raise WorkflowConflict("مسیریابی فعلی با مجوزهای legacy نگهداری سازگار نیست.")
    current = {
        str(candidate.membership_id): candidate
        for candidate in WorkItemCandidate.objects.select_for_update().filter(
            organization=record.organization, work_item=item, is_active=True
        )
    }
    added, removed = (
        sorted(set(routed) - set(current)),
        sorted(set(current) - set(routed)),
    )
    if not added and not removed:
        return
    now = timezone.now()
    for membership_id in removed:
        WorkItemCandidate.objects.filter(pk=current[membership_id].pk).update(
            is_active=False, removed_at=now, removal_reason="w5.7_backfill_reconcile"
        )
    for membership_id in added:
        candidate = routed[membership_id]
        WorkItemCandidate.objects.create(
            organization=record.organization,
            work_item=item,
            membership=candidate.membership,
            qualifying_position_assignment=candidate.position_assignment,
            routing_basis=candidate.routing_basis,
        )
    record_audit_event(
        action=AuditAction.WORKFLOW_CANDIDATES_CHANGED,
        entity_type="workflows.WorkflowStepInstance",
        entity_id=str(step.pk),
        organization=record.organization,
        actor=actor,
        metadata={
            "change": "w5.7_backfill_reconcile",
            "work_item_id": str(item.pk),
            "added_membership_ids": added,
            "removed_membership_ids": removed,
        },
    )


@dataclass(frozen=True, slots=True)
class BackfillReport:
    scanned: int = 0
    created: int = 0
    existing: int = 0
    skipped: int = 0


def backfill_open_maintenance_workflows(
    *, organization: Organization | None = None
) -> BackfillReport:
    queryset = MaintenanceRecord.objects.filter(
        status__in=(MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS)
    )
    if organization is not None:
        queryset = queryset.filter(organization=organization)
    scanned = created = existing = skipped = 0
    for record in queryset.select_related("organization", "updated_by").iterator():
        scanned += 1
        actor = _backfill_actor(record)
        if actor is None:
            skipped += 1
            continue
        was_present = WorkflowInstance.objects.filter(
            organization=record.organization,
            subject_type=SUBJECT_TYPE,
            subject_id=record.pk,
            status=WorkflowInstanceStatus.ACTIVE,
        ).exists()
        try:
            instance = start_maintenance_workflow(
                organization=record.organization, record=record, actor=actor
            )
            if instance is None:
                skipped += 1
            elif was_present:
                _reconcile_open_candidates(
                    record=record, instance=instance, actor=actor
                )
                existing += 1
            else:
                created += 1
        except (WorkflowConflict, ValidationError, PermissionDenied):
            skipped += 1
    return BackfillReport(scanned, created, existing, skipped)


def _active_instance(*, organization: Organization, record: MaintenanceRecord) -> bool:
    return WorkflowInstance.objects.filter(
        organization=organization,
        subject_type=SUBJECT_TYPE,
        subject_id=record.pk,
        status=WorkflowInstanceStatus.ACTIVE,
    ).exists()


def _actor_item(
    *,
    organization: Organization,
    record: MaintenanceRecord,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=record.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای نگهداری وجود ندارد.")
    return item


@transaction.atomic
def perform_maintenance_transition(
    *,
    organization: Organization,
    actor: User,
    record: MaintenanceRecord,
    target_status: str,
    effective_date: Any,
    cost: Any = None,
) -> MaintenanceRecord:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=TRANSITION_PERMISSION,
        message="اجازه تغییر وضعیت سرویس یا تعمیر را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    try:
        locked = MaintenanceRecord.objects.select_for_update().get(
            pk=record.pk, organization=organization
        )
    except MaintenanceRecord.DoesNotExist as exc:
        raise PermissionDenied("سابقه سرویس یا تعمیر در این سازمان یافت نشد.") from exc
    if target_status not in _COMMANDS:
        raise ValueError("تغییر وضعیت سرویس یا تعمیر مجاز نیست.")
    if locked.status == target_status:
        completed = WorkItem.objects.filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=locked.pk,
            completion_outcome=target_status,
            status=WorkItemStatus.COMPLETED,
        )
        if completed.filter(current_assignee=membership).exists():
            # Only the winning actor may retry the same public transition.
            return locked
        if completed.exists():
            raise WorkflowConflict("این اقدام پیش‌تر توسط عضویت دیگری انجام شده است.")
    if not _active_instance(organization=organization, record=locked):
        starter = _backfill_actor(locked)
        if starter is not None:
            try:
                start_maintenance_workflow(
                    organization=organization, record=locked, actor=starter
                )
            except WorkflowConflict:
                pass
    if not _active_instance(organization=organization, record=locked):
        from .services import _transition_maintenance_status_domain

        return _transition_maintenance_status_domain(
            organization=organization,
            actor=actor,
            record=locked,
            target_status=target_status,
            effective_date=effective_date,
            cost=cost,
        )
    item = _actor_item(organization=organization, record=locked, membership=membership)
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
        outcome=target_status,
        idempotency_key=_key(item.pk, membership.pk, target_status),
        command_context={"effective_date": effective_date, "cost": cost},
    )
    locked.refresh_from_db()
    instance = WorkflowInstance.objects.get(
        organization=organization, subject_type=SUBJECT_TYPE, subject_id=locked.pk
    )
    if instance.status == WorkflowInstanceStatus.ACTIVE:
        _sync_active_work_item_deadline(record=locked, instance=instance)
    return locked


def maintenance_shadow_comparison(
    *, organization: Organization, record: MaintenanceRecord
) -> dict[str, Any]:
    if record.organization_id != organization.pk:
        raise PermissionDenied("سابقه سرویس یا تعمیر متعلق به سازمان دیگری است.")
    if record.status not in {
        MaintenanceStatus.SCHEDULED,
        MaintenanceStatus.IN_PROGRESS,
    }:
        raise ValidationError("سابقه نهایی‌شده کار باز ندارد.")
    legacy_ids = {
        str(pk)
        for pk in OrganizationMembership.objects.filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=TRANSITION_PERMISSION,
            role_definition__permissions__is_active=True,
        ).values_list("pk", flat=True)
    }
    candidates = WorkItemCandidate.objects.filter(
        organization=organization,
        work_item__instance__subject_type=SUBJECT_TYPE,
        work_item__instance__subject_id=record.pk,
        work_item__instance__status=WorkflowInstanceStatus.ACTIVE,
        work_item__status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        is_active=True,
    ).select_related("membership__role_definition")
    workflow_ids = {str(candidate.membership_id) for candidate in candidates}
    runtime_permissions = (
        BusinessPermissionCode.WORK_ITEMS_VIEW,
        BusinessPermissionCode.WORK_ITEMS_CLAIM,
        BusinessPermissionCode.WORK_ITEMS_ACT,
    )
    blocked = sorted(
        str(candidate.membership_id)
        for candidate in candidates
        if not all(
            membership_has_permission(candidate.membership, code)
            for code in runtime_permissions
        )
    )
    missing, unexpected = (
        sorted(legacy_ids - workflow_ids),
        sorted(workflow_ids - legacy_ids),
    )
    return {
        "maintenance_record_id": str(record.pk),
        "legacy_membership_ids": sorted(legacy_ids),
        "workflow_membership_ids": sorted(workflow_ids),
        "missing_membership_ids": missing,
        "unexpected_membership_ids": unexpected,
        "blocked_runtime_permission_membership_ids": blocked,
        "mismatch": bool(missing or unexpected or blocked),
    }
