"""W5.3 compatibility workflow for the existing quality issue lifecycle."""

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

from .models import QualityIssue, QualityIssueStatus

WORKFLOW_TYPE_CODE = "quality.quality_issue_lifecycle"
SUBJECT_TYPE = "quality.quality_issue"
TEMPLATE_CODE = "quality_issue_legacy_compatibility"
DEFINITION_CODE = "quality-issue-legacy-compatibility"

STAGES = (
    (
        "review",
        "بررسی مسئله",
        "reported",
        "review",
        "under_review",
        "quality_issues.review",
    ),
    (
        "assign",
        "تعیین مسئول",
        "under_review",
        "assign",
        "assigned",
        "quality_issues.review",
    ),
    (
        "start_action",
        "آغاز اقدام اصلاحی",
        "assigned",
        "start_action",
        "action_in_progress",
        "quality_issues.manage",
    ),
    (
        "submit_for_verification",
        "ارسال برای راستی‌آزمایی",
        "action_in_progress",
        "submit_for_verification",
        "awaiting_verification",
        "quality_issues.manage",
    ),
    (
        "verify",
        "راستی‌آزمایی",
        "awaiting_verification",
        "verify",
        "verified",
        "quality_issues.verify",
    ),
    (
        "close",
        "بستن مسئله",
        "verified",
        "close",
        "closed",
        "quality_issues.close",
    ),
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
        {
            "resolver_type": "organization_owner",
            "configuration": {},
            "is_fallback": True,
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
                "domain_command": f"quality.quality_issue.{command}",
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


def _responsible_display(issue: QualityIssue) -> str:
    names: list[str] = []
    if issue.responsible_user_id:
        user = issue.responsible_user
        names.append(user.get_full_name() or user.username)
    if issue.responsible_employee_id:
        names.append(str(issue.responsible_employee))
    if issue.responsible_party_id:
        names.append(str(issue.responsible_party))
    return "، ".join(names)


def _sync_active_work_item_deadline(
    *, issue: QualityIssue, instance: WorkflowInstance
) -> None:
    if issue.due_date is None:
        return
    due_at = datetime.combine(
        issue.due_date,
        time.max,
        tzinfo=ZoneInfo(issue.organization.timezone),
    )
    WorkItem.objects.filter(
        organization=issue.organization,
        instance=instance,
        status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
    ).update(due_at=due_at)


def load_quality_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.QUALITY_ISSUES_VIEW,
        message="اجازه مشاهده مسئله کیفیت را ندارید.",
    )
    queryset = QualityIssue.objects.select_related(
        "project",
        "site",
        "responsible_user",
        "responsible_employee",
        "responsible_party",
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        issue = queryset.get(pk=subject_id, organization=organization)
    except QualityIssue.DoesNotExist as exc:
        raise PermissionDenied("مسئله کیفیت در این سازمان یافت نشد.") from exc
    if (
        issue.project.organization_id != organization.pk
        or (issue.site_id and issue.site.organization_id != organization.pk)
        or (issue.site_id and issue.site.project_id != issue.project_id)
    ):
        raise PermissionDenied("دامنه مسئله کیفیت نامعتبر است.")
    return SubjectSnapshot(
        subject=issue,
        subject_id=str(issue.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(issue.project_id),
            "site_id": str(issue.site_id) if issue.site_id else None,
            "status": issue.status,
            "created_by_id": str(issue.created_by_id),
            "responsible_display": _responsible_display(issue),
        },
        creator_membership_id=_active_membership_id(organization, issue.created_by_id),
        display=f"مسئله کیفیت {issue.issue_number}",
    )


def _command(action: str):
    def execute(
        *,
        subject: QualityIssue,
        actor: User,
        organization: Organization,
        context: dict[str, Any],
        **_: object,
    ) -> QualityIssue:
        from . import services

        required = {
            "review": (),
            "assign": ("due_date",),
            "start_action": ("corrective_action",),
            "submit_for_verification": ("corrective_action_result",),
            "verify": ("verification_summary",),
            "close": ("closure_summary",),
        }[action]
        if any(not context.get(field) for field in required):
            raise ValidationError("اطلاعات الزامی اقدام کیفیت کامل نیست.")
        operation = {
            "review": services._review_quality_issue_domain,
            "assign": services._assign_quality_issue_domain,
            "start_action": services._start_quality_corrective_action_domain,
            "submit_for_verification": (
                services._submit_quality_issue_for_verification_domain
            ),
            "verify": services._verify_quality_issue_domain,
            "close": services._close_quality_issue_domain,
        }[action]
        return operation(
            organization=organization,
            actor=actor,
            issue_id=str(subject.pk),
            **context,
        )

    return execute


def register_quality_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_quality_subject)
    for action in (
        "review",
        "assign",
        "start_action",
        "submit_for_verification",
        "verify",
        "close",
    ):
        registry.bind_domain_command(
            f"quality.quality_issue.{action}", _command(action)
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
def ensure_quality_compatibility_workflow(
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
            raise ValidationError("نسخه منتشرشده کیفیت معتبر نیست.")
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
            "name": "سازگاری چرخه مسئله کیفیت",
            "description": "رفتار مرحله‌ای فعلی کیفیت را حفظ می‌کند.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض کیفیت نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked,
        definition=definition,
        version_number=1,
        change_summary="W5.3 legacy compatibility",
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


def resolve_quality_version(
    *, organization: Organization, issue: QualityIssue
) -> WorkflowVersion:
    if issue.organization_id != organization.pk:
        raise PermissionDenied("مسئله متعلق به سازمان دیگری است.")
    context = {
        "project_id": str(issue.project_id),
        "site_id": str(issue.site_id) if issue.site_id else None,
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
        raise ValidationError("نسخه منتشرشده برای مسئله کیفیت یافت نشد.")
    specificity = max(score for score, _ in matches)
    selected = [version for score, version in matches if score == specificity]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار کیفیت مبهم است.")
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
def start_quality_workflow(
    *, organization: Organization, issue: QualityIssue, actor: User
) -> WorkflowInstance | None:
    if (
        issue.organization_id != organization.pk
        or issue.status == QualityIssueStatus.CLOSED
    ):
        raise PermissionDenied("مسئله باز متعلق به این سازمان نیست.")
    existing = WorkflowInstance.objects.filter(
        organization=organization,
        subject_type=SUBJECT_TYPE,
        subject_id=issue.pk,
    ).first()
    if existing is not None:
        if existing.status != WorkflowInstanceStatus.ACTIVE:
            raise WorkflowConflict("گردش‌کار فعلی مسئله برای اقدام فعال نیست.")
        _sync_active_work_item_deadline(issue=issue, instance=existing)
        return existing
    permission = STATUS_PERMISSION[issue.status]
    if not _eligible_membership_exists(organization, permission):
        return None
    ensure_quality_compatibility_workflow(organization=organization, actor=actor)
    version = resolve_quality_version(organization=organization, issue=issue)
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=issue.pk,
        idempotency_key=_key(WORKFLOW_TYPE_CODE, issue.pk, "start"),
        initial_step_key=STATUS_STEP[issue.status]
        if issue.status != QualityIssueStatus.REPORTED
        else None,
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("مسئله بدون کار فعال وارد گردش‌کار نمی‌شود.")
    _sync_active_work_item_deadline(issue=issue, instance=instance)
    return instance


def _backfill_actor(issue: QualityIssue) -> User | None:
    memberships = OrganizationMembership.objects.filter(
        organization=issue.organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
    ).select_related("user", "role_definition")
    preferred = memberships.filter(user_id=issue.updated_by_id).first()
    if preferred and membership_has_permission(
        preferred, BusinessPermissionCode.QUALITY_ISSUES_VIEW
    ):
        return preferred.user
    owner = memberships.filter(role_definition__is_owner=True).first()
    if owner and membership_has_permission(
        owner, BusinessPermissionCode.QUALITY_ISSUES_VIEW
    ):
        return owner.user
    return None


def _reconcile_open_candidates(
    *, issue: QualityIssue, instance: WorkflowInstance, actor: User
) -> None:
    if instance.definition.code != DEFINITION_CODE:
        return
    instance = WorkflowInstance.objects.select_for_update().get(
        pk=instance.pk,
        organization=issue.organization,
        status=WorkflowInstanceStatus.ACTIVE,
    )
    step = WorkflowStepInstance.objects.select_for_update().get(
        organization=issue.organization,
        instance=instance,
        status=WorkflowStepInstanceStatus.ACTIVE,
    )
    if step.step_definition.key != STATUS_STEP[issue.status]:
        raise WorkflowConflict("گام فعال با وضعیت مسئله کیفیت سازگار نیست.")
    items = list(
        WorkItem.objects.select_for_update().filter(
            organization=issue.organization,
            instance=instance,
            step_instance=step,
            status=WorkItemStatus.OPEN,
            current_assignee__isnull=True,
        )
    )
    if len(items) != 1:
        raise WorkflowConflict("کار بازِ قابل بازپُرکنی کیفیت یکتا نیست.")
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
            organization=issue.organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=STATUS_PERMISSION[issue.status],
            role_definition__permissions__is_active=True,
        ).values_list("pk", flat=True)
    }
    if not routed or set(routed) != legacy:
        raise WorkflowConflict("مسیریابی فعلی با مجوزهای legacy کیفیت سازگار نیست.")
    current = {
        str(candidate.membership_id): candidate
        for candidate in WorkItemCandidate.objects.select_for_update().filter(
            organization=issue.organization,
            work_item=item,
            is_active=True,
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
            is_active=False,
            removed_at=now,
            removal_reason="w5.3_backfill_reconcile",
        )
    for membership_id in added:
        candidate = routed[membership_id]
        WorkItemCandidate.objects.create(
            organization=issue.organization,
            work_item=item,
            membership=candidate.membership,
            qualifying_position_assignment=candidate.position_assignment,
            routing_basis=candidate.routing_basis,
        )
    record_audit_event(
        action=AuditAction.WORKFLOW_CANDIDATES_CHANGED,
        entity_type="workflows.WorkflowStepInstance",
        entity_id=str(step.pk),
        organization=issue.organization,
        actor=actor,
        metadata={
            "change": "w5.3_backfill_reconcile",
            "work_item_id": str(item.pk),
            "added_membership_ids": added,
            "removed_membership_ids": removed,
        },
    )


@transaction.atomic
def _backfill_one(*, issue: QualityIssue, actor: User) -> str:
    try:
        locked = QualityIssue.objects.select_for_update().get(
            pk=issue.pk, organization=issue.organization
        )
    except QualityIssue.DoesNotExist:
        return "skipped"
    if locked.status == QualityIssueStatus.CLOSED:
        return "skipped"
    was_present = WorkflowInstance.objects.filter(
        organization=locked.organization,
        subject_type=SUBJECT_TYPE,
        subject_id=locked.pk,
    ).exists()
    instance = start_quality_workflow(
        organization=locked.organization, issue=locked, actor=actor
    )
    if instance is None:
        return "skipped"
    if was_present:
        _reconcile_open_candidates(issue=locked, instance=instance, actor=actor)
    return "existing" if was_present else "created"


@dataclass(frozen=True, slots=True)
class BackfillReport:
    scanned: int = 0
    created: int = 0
    existing: int = 0
    skipped: int = 0


def backfill_open_quality_issues(
    *, organization: Organization | None = None
) -> BackfillReport:
    queryset = QualityIssue.objects.exclude(status=QualityIssueStatus.CLOSED)
    if organization is not None:
        queryset = queryset.filter(organization=organization)
    scanned = created = existing = skipped = 0
    for issue in queryset.select_related("organization", "updated_by").iterator():
        scanned += 1
        actor = _backfill_actor(issue)
        if actor is None:
            skipped += 1
            continue
        try:
            result = _backfill_one(issue=issue, actor=actor)
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
    issue: QualityIssue,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=issue.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای اقدام کیفیت وجود ندارد.")
    return item


@transaction.atomic
def perform_quality_transition(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    expected_status: str,
    outcome: str,
    context: dict[str, Any],
) -> QualityIssue:
    permission = STATUS_PERMISSION[expected_status]
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اجازه انجام این اقدام کیفیت را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    try:
        issue = QualityIssue.objects.get(pk=issue_id, organization=organization)
    except QualityIssue.DoesNotExist as exc:
        raise PermissionDenied("مسئله کیفیت در این سازمان یافت نشد.") from exc
    if issue.status != expected_status:
        raise ValueError("وضعیت مسئله برای این اقدام معتبر نیست.")
    if not WorkflowInstance.objects.filter(
        organization=organization, subject_type=SUBJECT_TYPE, subject_id=issue.pk
    ).exists():
        starter = _backfill_actor(issue)
        if starter is not None:
            try:
                _backfill_one(issue=issue, actor=starter)
            except WorkflowConflict:
                pass
    if not WorkflowInstance.objects.filter(
        organization=organization, subject_type=SUBJECT_TYPE, subject_id=issue.pk
    ).exists():
        from . import services

        operation = {
            QualityIssueStatus.UNDER_REVIEW: services._review_quality_issue_domain,
            QualityIssueStatus.ASSIGNED: services._assign_quality_issue_domain,
            QualityIssueStatus.ACTION_IN_PROGRESS: (
                services._start_quality_corrective_action_domain
            ),
            QualityIssueStatus.AWAITING_VERIFICATION: (
                services._submit_quality_issue_for_verification_domain
            ),
            QualityIssueStatus.VERIFIED: services._verify_quality_issue_domain,
            QualityIssueStatus.CLOSED: services._close_quality_issue_domain,
        }[outcome]
        return operation(
            organization=organization, actor=actor, issue_id=issue_id, **context
        )
    item = _actor_item(organization=organization, issue=issue, membership=membership)
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
    issue.refresh_from_db()
    instance = WorkflowInstance.objects.get(
        organization=organization,
        subject_type=SUBJECT_TYPE,
        subject_id=issue.pk,
    )
    _sync_active_work_item_deadline(issue=issue, instance=instance)
    return issue


def quality_shadow_comparison(
    *, organization: Organization, issue: QualityIssue
) -> dict[str, Any]:
    if issue.organization_id != organization.pk:
        raise PermissionDenied("مسئله متعلق به سازمان دیگری است.")
    permission = STATUS_PERMISSION.get(issue.status)
    if permission is None:
        raise ValidationError("مسئله بسته‌شده کار باز ندارد.")
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
        work_item__instance__subject_id=issue.pk,
        work_item__status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        is_active=True,
    ).select_related("membership__role_definition")
    workflow_ids = {str(candidate.membership_id) for candidate in candidates}
    runtime_permissions = (
        BusinessPermissionCode.WORK_ITEMS_VIEW,
        BusinessPermissionCode.WORK_ITEMS_CLAIM,
        BusinessPermissionCode.WORK_ITEMS_ACT,
    )
    blocked_ids = sorted(
        {
            str(candidate.membership_id)
            for candidate in candidates
            if not all(
                membership_has_permission(candidate.membership, code)
                for code in runtime_permissions
            )
        }
    )
    missing, unexpected = (
        sorted(legacy_ids - workflow_ids),
        sorted(workflow_ids - legacy_ids),
    )
    return {
        "issue_id": str(issue.pk),
        "legacy_membership_ids": sorted(legacy_ids),
        "workflow_membership_ids": sorted(workflow_ids),
        "missing_membership_ids": missing,
        "unexpected_membership_ids": unexpected,
        "blocked_runtime_permission_membership_ids": blocked_ids,
        "mismatch": bool(missing or unexpected or blocked_ids),
    }
