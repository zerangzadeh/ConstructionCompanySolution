"""W5.4 approval orchestration for immutable contract amendments."""

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

from .models import ContractAmendment, ContractAmendmentStatus, ContractStatus

WORKFLOW_TYPE_CODE = "contracts.contract_amendment_approval"
SUBJECT_TYPE = "contracts.contract_amendment"
TEMPLATE_CODE = "contract_amendment_legacy_compatibility"
DEFINITION_CODE = "contract-amendment-legacy-compatibility"
APPROVE_PERMISSION = BusinessPermissionCode.CONTRACT_AMENDMENTS_APPROVE

COMPATIBILITY_CONFIGURATION: dict[str, Any] = {
    "steps": [
        {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
        {
            "key": "approval",
            "name": "تأیید الحاقیه",
            "step_type": "approval",
            "configuration": {"decision_policy": "any"},
            "routing": [
                {
                    "resolver_type": "business_permission",
                    "configuration": {"permission": "contract_amendments.approve"},
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
            "domain_command": "contracts.contract_amendment.approve",
            "required_permission": "contract_amendments.approve",
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


def load_contract_amendment_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTS_VIEW,
        message="اجازه مشاهده الحاقیه قرارداد را ندارید.",
    )
    queryset = ContractAmendment.objects.select_related("contract", "contract__project")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        amendment = queryset.get(pk=subject_id, organization=organization)
    except ContractAmendment.DoesNotExist as exc:
        raise PermissionDenied("الحاقیه در این سازمان یافت نشد.") from exc
    if (
        amendment.contract.organization_id != organization.pk
        or amendment.contract.deleted_at
    ):
        raise PermissionDenied("دامنه الحاقیه معتبر نیست.")
    return SubjectSnapshot(
        subject=amendment,
        subject_id=str(amendment.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(amendment.contract.project_id),
            "contract_id": str(amendment.contract_id),
            "status": amendment.status,
            "created_by_id": str(amendment.created_by_id)
            if amendment.created_by_id
            else None,
        },
        creator_membership_id=_active_membership_id(
            organization, amendment.created_by_id
        ),
        submitter_membership_id=_active_membership_id(
            organization, amendment.created_by_id
        ),
        display=f"{amendment.contract.contract_number} — الحاقیه {amendment.amendment_number}",
    )


def _approve_command(
    *, subject: ContractAmendment, actor: User, organization: Organization, **_: object
) -> ContractAmendment:
    from .services import _approve_contract_amendment_domain

    return _approve_contract_amendment_domain(
        organization=organization, actor=actor, amendment=subject
    )


def register_contract_amendment_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_contract_amendment_subject)
    registry.bind_domain_command(
        "contracts.contract_amendment.approve", _approve_command
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
def ensure_contract_amendment_compatibility_workflow(
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
            raise ValidationError("گردش‌کار پیش‌فرض الحاقیه معتبر نیست.")
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
            "name": "سازگاری تأیید الحاقیه قرارداد",
            "description": "تأیید تک‌مرحله‌ای الحاقیه را حفظ می‌کند.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض الحاقیه نسخه منتشرشده ندارد.")
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


def resolve_contract_amendment_version(
    *, organization: Organization, amendment: ContractAmendment
) -> WorkflowVersion:
    if amendment.organization_id != organization.pk:
        raise PermissionDenied("الحاقیه متعلق به سازمان دیگری است.")
    context = {
        "project_id": str(amendment.contract.project_id),
        "contract_id": str(amendment.contract_id),
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
        raise ValidationError("نسخه منتشرشده برای الحاقیه یافت نشد.")
    score = max(value for value, _ in matches)
    selected = [version for value, version in matches if value == score]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار الحاقیه مبهم است.")
    return selected[0]


@transaction.atomic
def request_contract_amendment_approval(
    *, organization: Organization, actor: User, amendment: ContractAmendment
) -> WorkflowInstance:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTS_CHANGE,
        message="اجازه درخواست تأیید الحاقیه را ندارید.",
    )
    locked = (
        ContractAmendment.objects.select_for_update()
        .select_related("contract", "contract__project")
        .get(pk=amendment.pk)
    )
    if locked.organization_id != organization.pk:
        raise PermissionDenied("الحاقیه متعلق به این سازمان نیست.")
    if locked.status != ContractAmendmentStatus.DRAFT or locked.contract.status not in {
        ContractStatus.ACTIVE,
        ContractStatus.COMPLETED,
    }:
        raise ValueError(
            "فقط الحاقیه پیش‌نویسِ قرارداد نهایی‌شده قابل ارسال برای تأیید است."
        )
    ensure_contract_amendment_compatibility_workflow(
        organization=organization, actor=actor
    )
    version = resolve_contract_amendment_version(
        organization=organization, amendment=locked
    )
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=locked.pk,
        idempotency_key=_key(WORKFLOW_TYPE_CODE, locked.pk, "request"),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("درخواست تأیید الحاقیه بدون کار فعال قابل ثبت نیست.")
    return instance


def _actor_item(
    *,
    organization: Organization,
    amendment: ContractAmendment,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=amendment.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای تأیید الحاقیه وجود ندارد.")
    return item


@transaction.atomic
def approve_contract_amendment_with_workflow(
    *, organization: Organization, actor: User, amendment: ContractAmendment
) -> ContractAmendment:
    active = WorkflowInstance.objects.filter(
        organization=organization,
        subject_type=SUBJECT_TYPE,
        subject_id=amendment.pk,
        status=WorkflowInstanceStatus.ACTIVE,
    ).exists()
    if not active:
        from .services import _approve_contract_amendment_domain

        return _approve_contract_amendment_domain(
            organization=organization, actor=actor, amendment=amendment
        )
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=APPROVE_PERMISSION,
        message="اجازه تأیید الحاقیه‌های این سازمان را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    locked = (
        ContractAmendment.objects.select_for_update()
        .select_related("contract")
        .get(pk=amendment.pk, organization=organization)
    )
    if locked.status != ContractAmendmentStatus.DRAFT:
        raise ValueError("فقط الحاقیه‌های پیش‌نویس قابل تأیید هستند.")
    item = _actor_item(
        organization=organization, amendment=locked, membership=membership
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


def _backfill_actor(amendment: ContractAmendment) -> User | None:
    memberships = OrganizationMembership.objects.filter(
        organization=amendment.organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
    ).select_related("user", "role_definition")
    preferred = memberships.filter(user_id=amendment.created_by_id).first()
    if preferred and membership_has_permission(
        preferred, BusinessPermissionCode.CONTRACTS_VIEW
    ):
        return preferred.user
    owner = memberships.filter(role_definition__is_owner=True).first()
    return (
        owner.user
        if owner
        and membership_has_permission(owner, BusinessPermissionCode.CONTRACTS_VIEW)
        else None
    )


@transaction.atomic
def _reconcile_open_candidates(
    *, amendment: ContractAmendment, instance: WorkflowInstance, actor: User
) -> None:
    """Refresh only an unclaimed compatibility item; finalized history is untouched."""
    if instance.definition.code != DEFINITION_CODE:
        return
    instance = WorkflowInstance.objects.select_for_update().get(
        pk=instance.pk,
        organization=amendment.organization,
        status=WorkflowInstanceStatus.ACTIVE,
    )
    step = WorkflowStepInstance.objects.select_for_update().get(
        organization=amendment.organization,
        instance=instance,
        status=WorkflowStepInstanceStatus.ACTIVE,
    )
    item = (
        WorkItem.objects.select_for_update()
        .filter(
            organization=amendment.organization,
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
            organization=amendment.organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=APPROVE_PERMISSION,
            role_definition__permissions__is_active=True,
        ).values_list("pk", flat=True)
    }
    if not routed or set(routed) != legacy:
        raise WorkflowConflict("مسیریابی فعلی با مجوزهای legacy الحاقیه سازگار نیست.")
    current = {
        str(candidate.membership_id): candidate
        for candidate in WorkItemCandidate.objects.select_for_update().filter(
            organization=amendment.organization, work_item=item, is_active=True
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
            organization=amendment.organization,
            work_item=item,
            membership=candidate.membership,
            qualifying_position_assignment=candidate.position_assignment,
            routing_basis=candidate.routing_basis,
        )
    record_audit_event(
        action=AuditAction.WORKFLOW_CANDIDATES_CHANGED,
        entity_type="workflows.WorkflowStepInstance",
        entity_id=str(step.pk),
        organization=amendment.organization,
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


def backfill_open_contract_amendment_approvals(
    *, organization: Organization | None = None
) -> BackfillReport:
    """Only explicitly pending runtime subjects are reconciled; draft is not a queue state."""
    instances = WorkflowInstance.objects.filter(
        subject_type=SUBJECT_TYPE, status=WorkflowInstanceStatus.ACTIVE
    )
    if organization is not None:
        instances = instances.filter(organization=organization)
    scanned = existing = skipped = 0
    for instance in instances.select_related("organization").iterator():
        amendment = ContractAmendment.objects.filter(
            pk=instance.subject_id,
            organization=instance.organization,
            status=ContractAmendmentStatus.DRAFT,
        ).first()
        if not amendment:
            skipped += 1
            continue
        actor = _backfill_actor(amendment)
        if actor is None:
            skipped += 1
            continue
        scanned += 1
        try:
            _reconcile_open_candidates(
                amendment=amendment, instance=instance, actor=actor
            )
        except WorkflowConflict:
            skipped += 1
        else:
            existing += 1
    return BackfillReport(scanned=scanned, existing=existing, skipped=skipped)


def contract_amendment_shadow_comparison(
    *, organization: Organization, amendment: ContractAmendment
) -> dict[str, Any]:
    if amendment.organization_id != organization.pk:
        raise PermissionDenied("الحاقیه متعلق به سازمان دیگری است.")
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
        work_item__instance__subject_id=amendment.pk,
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
        "amendment_id": str(amendment.pk),
        "legacy_membership_ids": sorted(legacy_ids),
        "workflow_membership_ids": sorted(workflow_ids),
        "missing_membership_ids": missing,
        "unexpected_membership_ids": unexpected,
        "blocked_runtime_permission_membership_ids": blocked,
        "mismatch": bool(missing or unexpected or blocked),
    }
