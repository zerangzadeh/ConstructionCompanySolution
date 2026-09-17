"""W5.4 approval orchestration for versioned estimates."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID

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

from .models import Estimate, EstimateRevisionStatus, EstimateStatus

WORKFLOW_TYPE_CODE = "estimates.estimate_approval"
SUBJECT_TYPE = "estimates.estimate"
TEMPLATE_CODE = "estimate_legacy_compatibility"
DEFINITION_CODE = "estimate-legacy-compatibility"
APPROVE_PERMISSION = BusinessPermissionCode.ESTIMATES_APPROVE

COMPATIBILITY_CONFIGURATION: dict[str, Any] = {
    "steps": [
        {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
        {
            "key": "approval",
            "name": "تأیید برآورد",
            "step_type": "approval",
            "configuration": {"decision_policy": "any"},
            "routing": [
                {
                    "resolver_type": "business_permission",
                    "configuration": {"permission": "estimates.approve"},
                },
                {
                    "resolver_type": "organization_owner",
                    "configuration": {},
                    "is_fallback": True,
                },
            ],
        },
        {
            "key": "approved",
            "name": "تأییدشده",
            "step_type": "end",
            "is_terminal": True,
        },
    ],
    "transitions": [
        {
            "source": "start",
            "target": "approval",
            "outcome": "requested",
            "is_default": True,
        },
        {
            "source": "approval",
            "target": "approved",
            "outcome": "approved",
            "domain_command": "estimates.estimate.approve",
            "required_permission": "estimates.approve",
        },
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


def load_estimate_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.ESTIMATES_VIEW,
        message="اجازه مشاهده برآورد را ندارید.",
    )
    queryset = Estimate.objects.select_related(
        "project", "phase", "contract", "current_revision"
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        estimate = queryset.get(pk=subject_id, organization=organization)
    except Estimate.DoesNotExist as exc:
        raise PermissionDenied("برآورد در این سازمان یافت نشد.") from exc
    if estimate.project.organization_id != organization.pk or estimate.deleted_at:
        raise PermissionDenied("دامنه برآورد معتبر نیست.")
    return SubjectSnapshot(
        subject=estimate,
        subject_id=str(estimate.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(estimate.project_id),
            "phase_id": str(estimate.phase_id) if estimate.phase_id else None,
            "contract_id": str(estimate.contract_id) if estimate.contract_id else None,
            "status": estimate.status,
            "current_revision_id": str(estimate.current_revision_id)
            if estimate.current_revision_id
            else None,
            "created_by_id": str(estimate.created_by_id)
            if estimate.created_by_id
            else None,
        },
        creator_membership_id=_active_membership_id(
            organization, estimate.created_by_id
        ),
        submitter_membership_id=_active_membership_id(
            organization, estimate.updated_by_id
        ),
        display=f"{estimate.estimate_number} — {estimate.title}",
    )


def _approve_command(*, subject: Estimate, actor: User, **_: object) -> Estimate:
    from .services import _approve_estimate_domain

    return _approve_estimate_domain(estimate=subject, actor=actor)


def register_estimate_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_estimate_subject)
    registry.bind_domain_command("estimates.estimate.approve", _approve_command)


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


@transaction.atomic
def ensure_estimate_compatibility_workflow(
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
            raise ValidationError("گردش‌کار پیش‌فرض برآورد معتبر نیست.")
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
            "name": "سازگاری تأیید برآورد",
            "description": "تأیید تک‌مرحله‌ای برآورد و بازنگری جاری را حفظ می‌کند.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض برآورد نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked,
        definition=definition,
        version_number=1,
        change_summary="W5.4 legacy compatibility",
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


def resolve_estimate_version(
    *, organization: Organization, estimate: Estimate
) -> WorkflowVersion:
    if estimate.organization_id != organization.pk:
        raise PermissionDenied("برآورد متعلق به سازمان دیگری است.")
    context = {
        "project_id": str(estimate.project_id),
        "phase_id": str(estimate.phase_id) if estimate.phase_id else None,
        "contract_id": str(estimate.contract_id) if estimate.contract_id else None,
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
        raise ValidationError("نسخه منتشرشده برای برآورد یافت نشد.")
    score = max(value for value, _ in matches)
    selected = [version for value, version in matches if value == score]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار برآورد مبهم است.")
    return selected[0]


def _is_draft_revision(estimate: Estimate) -> bool:
    return bool(
        estimate.current_revision_id
        and estimate.current_revision.status == EstimateRevisionStatus.DRAFT
    )


@transaction.atomic
def request_estimate_approval(*, estimate: Estimate, actor: User) -> WorkflowInstance:
    locked = (
        Estimate.objects.select_for_update(of=("self",))
        .select_related("current_revision")
        .get(pk=estimate.pk)
    )
    require_business_permission(
        user=actor,
        organization=locked.organization,
        permission=BusinessPermissionCode.ESTIMATES_REVISE,
        message="اجازه درخواست تأیید برآورد را ندارید.",
    )
    if (
        locked.deleted_at
        or locked.status != EstimateStatus.DRAFT
        or not _is_draft_revision(locked)
    ):
        raise ValueError(
            "فقط برآورد با بازنگری جاری پیش‌نویس قابل ارسال برای تأیید است."
        )
    version = ensure_estimate_compatibility_workflow(
        organization=locked.organization, actor=actor
    )
    version = resolve_estimate_version(
        organization=locked.organization, estimate=locked
    )
    instance = start_workflow(
        actor=actor,
        organization=locked.organization,
        version_id=version.pk,
        subject_id=locked.pk,
        idempotency_key=_key(
            WORKFLOW_TYPE_CODE, locked.pk, locked.current_revision_id, "request"
        ),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("درخواست تأیید برآورد بدون کار فعال قابل ثبت نیست.")
    return instance


def _actor_item(
    *,
    organization: Organization,
    estimate: Estimate,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=estimate.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای تأیید برآورد وجود ندارد.")
    return item


@transaction.atomic
def approve_estimate_with_workflow(*, estimate: Estimate, actor: User) -> Estimate:
    """Use the shared runtime once explicitly requested; otherwise preserve legacy approval."""
    organization = estimate.organization
    active = WorkflowInstance.objects.filter(
        organization=organization,
        subject_type=SUBJECT_TYPE,
        subject_id=estimate.pk,
        status=WorkflowInstanceStatus.ACTIVE,
    ).exists()
    if not active:
        from .services import _approve_estimate_domain

        return _approve_estimate_domain(estimate=estimate, actor=actor)
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=APPROVE_PERMISSION,
        message="اجازه تأیید برآوردهای این سازمان را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    locked = (
        Estimate.objects.select_for_update(of=("self",))
        .select_related("current_revision")
        .get(pk=estimate.pk, organization=organization)
    )
    if locked.status != EstimateStatus.DRAFT or not _is_draft_revision(locked):
        raise ValueError("فقط برآوردهای پیش‌نویس قابل تأیید هستند.")
    item = _actor_item(
        organization=organization, estimate=locked, membership=membership
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
        outcome="approved",
        idempotency_key=_key(item.pk, membership.pk, "approved"),
    )
    locked.refresh_from_db()
    return locked


def _backfill_actor(estimate: Estimate) -> User | None:
    memberships = OrganizationMembership.objects.filter(
        organization=estimate.organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
    ).select_related("user", "role_definition")
    preferred = memberships.filter(user_id=estimate.updated_by_id).first()
    if preferred and membership_has_permission(
        preferred, BusinessPermissionCode.ESTIMATES_VIEW
    ):
        return preferred.user
    owner = memberships.filter(role_definition__is_owner=True).first()
    return (
        owner.user
        if owner
        and membership_has_permission(owner, BusinessPermissionCode.ESTIMATES_VIEW)
        else None
    )


@transaction.atomic
def _reconcile_open_candidates(
    *, estimate: Estimate, instance: WorkflowInstance, actor: User
) -> None:
    """Idempotently refresh an unclaimed compatibility work item only."""
    if instance.definition.code != DEFINITION_CODE:
        return
    instance = WorkflowInstance.objects.select_for_update().get(
        pk=instance.pk,
        organization=estimate.organization,
        status=WorkflowInstanceStatus.ACTIVE,
    )
    step = WorkflowStepInstance.objects.select_for_update().get(
        organization=estimate.organization,
        instance=instance,
        status=WorkflowStepInstanceStatus.ACTIVE,
    )
    item = (
        WorkItem.objects.select_for_update()
        .filter(
            organization=estimate.organization,
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
            organization=estimate.organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=APPROVE_PERMISSION,
            role_definition__permissions__is_active=True,
        ).values_list("pk", flat=True)
    }
    if not routed or set(routed) != legacy:
        raise WorkflowConflict("مسیریابی فعلی با مجوزهای legacy برآورد سازگار نیست.")
    current = {
        str(candidate.membership_id): candidate
        for candidate in WorkItemCandidate.objects.select_for_update().filter(
            organization=estimate.organization, work_item=item, is_active=True
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
            is_active=False, removed_at=now, removal_reason="w5.4_backfill_reconcile"
        )
    for membership_id in added:
        candidate = routed[membership_id]
        WorkItemCandidate.objects.create(
            organization=estimate.organization,
            work_item=item,
            membership=candidate.membership,
            qualifying_position_assignment=candidate.position_assignment,
            routing_basis=candidate.routing_basis,
        )
    record_audit_event(
        action=AuditAction.WORKFLOW_CANDIDATES_CHANGED,
        entity_type="workflows.WorkflowStepInstance",
        entity_id=str(step.pk),
        organization=estimate.organization,
        actor=actor,
        metadata={
            "change": "w5.4_backfill_reconcile",
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


def backfill_open_estimate_approvals(
    *, organization: Organization | None = None
) -> BackfillReport:
    """Reconcile only already-pending runtime subjects; drafts are not inferred actionable."""
    instances = WorkflowInstance.objects.filter(
        subject_type=SUBJECT_TYPE, status=WorkflowInstanceStatus.ACTIVE
    )
    if organization is not None:
        instances = instances.filter(organization=organization)
    scanned = existing = skipped = 0
    for instance in instances.select_related("organization").iterator():
        estimate = (
            Estimate.objects.filter(
                pk=instance.subject_id,
                organization=instance.organization,
                status=EstimateStatus.DRAFT,
            )
            .select_related("current_revision")
            .first()
        )
        if not estimate or not _is_draft_revision(estimate):
            skipped += 1
            continue
        actor = _backfill_actor(estimate)
        if actor is None:
            skipped += 1
            continue
        scanned += 1
        try:
            _reconcile_open_candidates(
                estimate=estimate, instance=instance, actor=actor
            )
        except WorkflowConflict:
            skipped += 1
        else:
            existing += 1
    return BackfillReport(scanned=scanned, existing=existing, skipped=skipped)


def estimate_shadow_comparison(
    *, organization: Organization, estimate: Estimate
) -> dict[str, Any]:
    if estimate.organization_id != organization.pk:
        raise PermissionDenied("برآورد متعلق به سازمان دیگری است.")
    legacy_ids = {
        str(pk)
        for pk in OrganizationMembership.objects.filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=APPROVE_PERMISSION,
            role_definition__permissions__is_active=True,
        ).values_list("pk", flat=True)
    }
    candidates = WorkItemCandidate.objects.filter(
        organization=organization,
        work_item__instance__subject_type=SUBJECT_TYPE,
        work_item__instance__subject_id=estimate.pk,
        work_item__status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
        is_active=True,
    ).select_related("membership__role_definition")
    workflow_ids = {str(candidate.membership_id) for candidate in candidates}
    blocked = sorted(
        str(candidate.membership_id)
        for candidate in candidates
        if not all(
            membership_has_permission(candidate.membership, code)
            for code in (
                BusinessPermissionCode.WORK_ITEMS_VIEW,
                BusinessPermissionCode.WORK_ITEMS_CLAIM,
                BusinessPermissionCode.WORK_ITEMS_ACT,
            )
        )
    )
    missing, unexpected = (
        sorted(legacy_ids - workflow_ids),
        sorted(workflow_ids - legacy_ids),
    )
    return {
        "estimate_id": str(estimate.pk),
        "legacy_membership_ids": sorted(legacy_ids),
        "workflow_membership_ids": sorted(workflow_ids),
        "missing_membership_ids": missing,
        "unexpected_membership_ids": unexpected,
        "blocked_runtime_permission_membership_ids": blocked,
        "mismatch": bool(missing or unexpected or blocked),
    }
