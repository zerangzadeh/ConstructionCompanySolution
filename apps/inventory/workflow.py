"""W5.6 orchestration for manual inventory posting and reversal."""

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

from .models import StockTransaction, StockTransactionStatus, StockTransactionType

SUBJECT_TYPE = "inventory.stock_transaction"
POSTING_WORKFLOW_TYPE = "inventory.stock_transaction_posting"
REVERSAL_WORKFLOW_TYPE = "inventory.stock_transaction_reversal"


@dataclass(frozen=True, slots=True)
class WorkflowAction:
    workflow_type: str
    template_code: str
    definition_code: str
    permission: str
    command: str
    outcome: str
    name: str
    description: str


POSTING = WorkflowAction(
    workflow_type=POSTING_WORKFLOW_TYPE,
    template_code="stock_transaction_posting_legacy_compatibility",
    definition_code="stock-transaction-posting-legacy-compatibility",
    permission=BusinessPermissionCode.STOCK_TRANSACTIONS_POST,
    command="inventory.stock_transaction.post",
    outcome="posted",
    name="ثبت نهایی گردش انبار",
    description="ثبت نهایی گردش انبارِ دستی با تخصیص مسئولیت.",
)
REVERSAL = WorkflowAction(
    workflow_type=REVERSAL_WORKFLOW_TYPE,
    template_code="stock_transaction_reversal_legacy_compatibility",
    definition_code="stock-transaction-reversal-legacy-compatibility",
    permission=BusinessPermissionCode.STOCK_TRANSACTIONS_REVERSE,
    command="inventory.stock_transaction.reverse",
    outcome="reversed",
    name="برگشت گردش انبار",
    description="برگشت تغییرناپذیر گردش انبارِ دستی با تخصیص مسئولیت.",
)


def _key(*parts: object) -> str:
    return sha256(":".join(str(part) for part in parts).encode()).hexdigest()


def _action(workflow_type: str) -> WorkflowAction:
    for action in (POSTING, REVERSAL):
        if action.workflow_type == workflow_type:
            return action
    raise ValidationError("نوع گردش‌کار انبار معتبر نیست.")


def _is_assignment_subject(transaction_record: StockTransaction) -> bool:
    """Goods-receipt movements retain their established direct, non-W5.6 path."""

    return (
        transaction_record.transaction_type != StockTransactionType.REVERSAL
        and transaction_record.goods_receipt_item_id is None
    )


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


def load_stock_transaction_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.STOCK_TRANSACTIONS_VIEW,
        message="اجازه مشاهده تراکنش‌های انبار را ندارید.",
    )
    queryset = StockTransaction.objects.select_related("project", "material")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        transaction_record = queryset.get(pk=subject_id, organization=organization)
    except StockTransaction.DoesNotExist as exc:
        raise PermissionDenied("تراکنش انبار در این سازمان یافت نشد.") from exc
    if not _is_assignment_subject(transaction_record):
        raise PermissionDenied("این تراکنش انبار به تخصیص گردش‌کار نیاز ندارد.")
    return SubjectSnapshot(
        subject=transaction_record,
        subject_id=str(transaction_record.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(transaction_record.project_id)
            if transaction_record.project_id
            else None,
            "transaction_type": transaction_record.transaction_type,
            "status": transaction_record.status,
            "created_by_id": str(transaction_record.created_by_id)
            if transaction_record.created_by_id
            else None,
        },
        creator_membership_id=_active_membership_id(
            organization, transaction_record.created_by_id
        ),
        submitter_membership_id=_active_membership_id(
            organization, transaction_record.updated_by_id
        ),
        display=(
            f"{transaction_record.transaction_number} — "
            f"{transaction_record.material.name}"
        ),
    )


def _post_command(
    *, subject: StockTransaction, actor: User, organization: Organization, **_: object
) -> StockTransaction:
    from .services import _post_stock_transaction_domain

    return _post_stock_transaction_domain(
        organization=organization, actor=actor, stock_transaction=subject
    )


def _reverse_command(
    *,
    subject: StockTransaction,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> StockTransaction:
    reversal_number = str(context.get("reversal_number", "")).strip()
    reason = str(context.get("reason", "")).strip()
    if not reversal_number or not reason:
        raise ValidationError("شماره و دلیل برگشت برای تکمیل کار الزامی است.")
    from .services import _reverse_stock_transaction_domain

    return _reverse_stock_transaction_domain(
        organization=organization,
        actor=actor,
        stock_transaction=subject,
        reversal_number=reversal_number,
        reason=reason,
    )


def register_stock_transaction_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_stock_transaction_subject)
    registry.bind_domain_command(POSTING.command, _post_command)
    registry.bind_domain_command(REVERSAL.command, _reverse_command)


def _configuration(action: WorkflowAction) -> dict[str, Any]:
    return {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {
                "key": "assignment",
                "name": action.name,
                "step_type": "approval",
                "configuration": {"decision_policy": "any"},
                "routing": [
                    {
                        "resolver_type": "business_permission",
                        "configuration": {"permission": action.permission},
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
        ],
        "transitions": [
            {
                "source": "start",
                "target": "assignment",
                "outcome": "requested",
                "is_default": True,
            },
            {
                "source": "assignment",
                "target": "completed",
                "outcome": action.outcome,
                "domain_command": action.command,
                "required_permission": action.permission,
            },
        ],
    }


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
def ensure_stock_transaction_compatibility_workflow(
    *, organization: Organization, actor: User, workflow_type: str
) -> WorkflowVersion:
    action = _action(workflow_type)
    get_active_membership(user=actor, organization=organization)
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    workflow_type_record = WorkflowType.objects.get(
        code=action.workflow_type, is_active=True
    )
    _, scope_key = canonical_scope({})
    existing = (
        WorkflowVersion.objects.select_related("definition")
        .filter(
            organization=locked,
            definition__workflow_type=workflow_type_record,
            definition__scope_key=scope_key,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        .first()
    )
    if existing:
        if validate_workflow_version(existing):
            raise ValidationError("گردش‌کار پیش‌فرض انبار معتبر نیست.")
        return existing
    template = WorkflowTemplate.objects.get(
        workflow_type=workflow_type_record, code=action.template_code, is_active=True
    )
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked,
        workflow_type=workflow_type_record,
        scope_key=scope_key,
        defaults={
            "code": action.definition_code,
            "name": f"سازگاری {action.name}",
            "description": action.description,
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض انبار نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked,
        definition=definition,
        version_number=1,
        change_summary="W5.6 legacy compatibility",
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
    for audit_action, entity_type, entity_id in (
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
            action=audit_action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            organization=locked,
            actor=actor,
            metadata={"workflow_type": action.workflow_type, "compatibility": True},
        )
    version.refresh_from_db()
    return version


def _resolve_version(
    *,
    organization: Organization,
    transaction_record: StockTransaction,
    action: WorkflowAction,
) -> WorkflowVersion:
    if transaction_record.organization_id != organization.pk:
        raise PermissionDenied("تراکنش انبار متعلق به سازمان دیگری است.")
    context = {
        "project_id": str(transaction_record.project_id)
        if transaction_record.project_id
        else None,
        "transaction_type": transaction_record.transaction_type,
    }
    matches = [
        (len(version.definition.scope), version)
        for version in WorkflowVersion.objects.select_related("definition").filter(
            organization=organization,
            definition__workflow_type__code=action.workflow_type,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        if all(
            context.get(key) == value for key, value in version.definition.scope.items()
        )
    ]
    if not matches:
        raise ValidationError("نسخه منتشرشده گردش‌کار انبار یافت نشد.")
    score = max(value for value, _ in matches)
    selected = [version for value, version in matches if value == score]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار انبار مبهم است.")
    return selected[0]


def _request(
    *,
    organization: Organization,
    actor: User,
    stock_transaction: StockTransaction,
    action: WorkflowAction,
) -> WorkflowInstance:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=action.permission,
        message="اجازه درخواست تخصیص گردش انبار را ندارید.",
    )
    try:
        locked = (
            StockTransaction.objects.select_for_update()
            .select_related("material")
            .get(pk=stock_transaction.pk, organization=organization)
        )
    except StockTransaction.DoesNotExist as exc:
        raise PermissionDenied("تراکنش انبار در این سازمان یافت نشد.") from exc
    if not _is_assignment_subject(locked):
        raise ValueError("این تراکنش به تخصیص گردش‌کار نیاز ندارد.")
    expected = (
        StockTransactionStatus.DRAFT
        if action == POSTING
        else StockTransactionStatus.POSTED
    )
    if locked.status != expected:
        raise ValueError("وضعیت فعلی تراکنش برای درخواست گردش‌کار معتبر نیست.")
    ensure_stock_transaction_compatibility_workflow(
        organization=organization, actor=actor, workflow_type=action.workflow_type
    )
    version = _resolve_version(
        organization=organization, transaction_record=locked, action=action
    )
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=locked.pk,
        idempotency_key=_key(action.workflow_type, locked.pk, "request"),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("درخواست انبار بدون کار فعال قابل ثبت نیست.")
    return instance


@transaction.atomic
def request_stock_transaction_posting(
    *, organization: Organization, actor: User, stock_transaction: StockTransaction
) -> WorkflowInstance:
    return _request(
        organization=organization,
        actor=actor,
        stock_transaction=stock_transaction,
        action=POSTING,
    )


@transaction.atomic
def request_stock_transaction_reversal(
    *, organization: Organization, actor: User, stock_transaction: StockTransaction
) -> WorkflowInstance:
    return _request(
        organization=organization,
        actor=actor,
        stock_transaction=stock_transaction,
        action=REVERSAL,
    )


def _active_instance(
    *,
    organization: Organization,
    stock_transaction: StockTransaction,
    action: WorkflowAction,
) -> bool:
    return WorkflowInstance.objects.filter(
        organization=organization,
        definition__workflow_type__code=action.workflow_type,
        subject_type=SUBJECT_TYPE,
        subject_id=stock_transaction.pk,
        status=WorkflowInstanceStatus.ACTIVE,
    ).exists()


def _actor_item(
    *,
    organization: Organization,
    stock_transaction: StockTransaction,
    action: WorkflowAction,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__definition__workflow_type__code=action.workflow_type,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=stock_transaction.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای تراکنش انبار وجود ندارد.")
    return item


def _complete(
    *,
    organization: Organization,
    actor: User,
    stock_transaction: StockTransaction,
    action: WorkflowAction,
    command_context: dict[str, Any] | None = None,
) -> None:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=action.permission,
        message="اجازه اقدام بر تراکنش انبار را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    item = _actor_item(
        organization=organization,
        stock_transaction=stock_transaction,
        action=action,
        membership=membership,
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
        outcome=action.outcome,
        idempotency_key=_key(item.pk, membership.pk, action.outcome),
        command_context=command_context,
    )


@transaction.atomic
def post_stock_transaction_with_workflow(
    *, organization: Organization, actor: User, stock_transaction: StockTransaction
) -> StockTransaction:
    from .services import _post_stock_transaction_domain

    try:
        locked = StockTransaction.objects.select_for_update().get(
            pk=stock_transaction.pk, organization=organization
        )
    except StockTransaction.DoesNotExist as exc:
        raise PermissionDenied("تراکنش انبار در این سازمان یافت نشد.") from exc
    if not _is_assignment_subject(locked) or not _active_instance(
        organization=organization, stock_transaction=locked, action=POSTING
    ):
        return _post_stock_transaction_domain(
            organization=organization, actor=actor, stock_transaction=locked
        )
    _complete(
        organization=organization,
        actor=actor,
        stock_transaction=locked,
        action=POSTING,
    )
    locked.refresh_from_db()
    return locked


@transaction.atomic
def reverse_stock_transaction_with_workflow(
    *,
    organization: Organization,
    actor: User,
    stock_transaction: StockTransaction,
    reversal_number: str,
    reason: str,
) -> StockTransaction:
    from .services import _reverse_stock_transaction_domain

    try:
        locked = StockTransaction.objects.select_for_update().get(
            pk=stock_transaction.pk, organization=organization
        )
    except StockTransaction.DoesNotExist as exc:
        raise PermissionDenied("تراکنش انبار در این سازمان یافت نشد.") from exc
    if not _is_assignment_subject(locked) or not _active_instance(
        organization=organization, stock_transaction=locked, action=REVERSAL
    ):
        return _reverse_stock_transaction_domain(
            organization=organization,
            actor=actor,
            stock_transaction=locked,
            reversal_number=reversal_number,
            reason=reason,
        )
    _complete(
        organization=organization,
        actor=actor,
        stock_transaction=locked,
        action=REVERSAL,
        command_context={"reversal_number": reversal_number, "reason": reason},
    )
    try:
        return StockTransaction.objects.get(
            organization=organization, reversal_of=locked
        )
    except StockTransaction.DoesNotExist as exc:
        raise WorkflowConflict("برگشت انبار پس از تکمیل کار ایجاد نشد.") from exc


def _backfill_actor(transaction_record: StockTransaction) -> User | None:
    memberships = OrganizationMembership.objects.filter(
        organization=transaction_record.organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
    ).select_related("user", "role_definition")
    preferred = memberships.filter(user_id=transaction_record.created_by_id).first()
    if preferred and membership_has_permission(
        preferred, BusinessPermissionCode.STOCK_TRANSACTIONS_VIEW
    ):
        return preferred.user
    owner = memberships.filter(role_definition__is_owner=True).first()
    return (
        owner.user
        if owner
        and membership_has_permission(
            owner, BusinessPermissionCode.STOCK_TRANSACTIONS_VIEW
        )
        else None
    )


@transaction.atomic
def _reconcile_open_candidates(
    *, transaction_record: StockTransaction, instance: WorkflowInstance, actor: User
) -> None:
    action = _action(instance.definition.workflow_type.code)
    if instance.definition.code != action.definition_code:
        return
    instance = WorkflowInstance.objects.select_for_update().get(
        pk=instance.pk,
        organization=transaction_record.organization,
        status=WorkflowInstanceStatus.ACTIVE,
    )
    step = WorkflowStepInstance.objects.select_for_update().get(
        organization=transaction_record.organization,
        instance=instance,
        status=WorkflowStepInstanceStatus.ACTIVE,
    )
    item = (
        WorkItem.objects.select_for_update()
        .filter(
            organization=transaction_record.organization,
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
            organization=transaction_record.organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=action.permission,
            role_definition__permissions__is_active=True,
        ).values_list("pk", flat=True)
    }
    if not routed or set(routed) != legacy:
        raise WorkflowConflict("مسیریابی فعلی با مجوزهای legacy انبار سازگار نیست.")
    current = {
        str(candidate.membership_id): candidate
        for candidate in WorkItemCandidate.objects.select_for_update().filter(
            organization=transaction_record.organization, work_item=item, is_active=True
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
            is_active=False, removed_at=now, removal_reason="w5.6_backfill_reconcile"
        )
    for membership_id in added:
        candidate = routed[membership_id]
        WorkItemCandidate.objects.create(
            organization=transaction_record.organization,
            work_item=item,
            membership=candidate.membership,
            qualifying_position_assignment=candidate.position_assignment,
            routing_basis=candidate.routing_basis,
        )
    record_audit_event(
        action=AuditAction.WORKFLOW_CANDIDATES_CHANGED,
        entity_type="workflows.WorkflowStepInstance",
        entity_id=str(step.pk),
        organization=transaction_record.organization,
        actor=actor,
        metadata={
            "change": "w5.6_backfill_reconcile",
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


def backfill_open_stock_transaction_workflows(
    *, organization: Organization | None = None
) -> BackfillReport:
    """Reconcile only explicit active requests; drafts and posted rows are not queues."""

    instances = WorkflowInstance.objects.filter(
        subject_type=SUBJECT_TYPE,
        status=WorkflowInstanceStatus.ACTIVE,
        definition__workflow_type__code__in=(
            POSTING.workflow_type,
            REVERSAL.workflow_type,
        ),
    )
    if organization is not None:
        instances = instances.filter(organization=organization)
    scanned = existing = skipped = 0
    for instance in instances.select_related(
        "organization", "definition__workflow_type"
    ).iterator():
        action = _action(instance.definition.workflow_type.code)
        expected = (
            StockTransactionStatus.DRAFT
            if action == POSTING
            else StockTransactionStatus.POSTED
        )
        transaction_record = (
            StockTransaction.objects.filter(
                pk=instance.subject_id,
                organization=instance.organization,
                status=expected,
            )
            .select_related("material")
            .first()
        )
        if not transaction_record or not _is_assignment_subject(transaction_record):
            skipped += 1
            continue
        actor = _backfill_actor(transaction_record)
        if actor is None:
            skipped += 1
            continue
        scanned += 1
        try:
            _reconcile_open_candidates(
                transaction_record=transaction_record, instance=instance, actor=actor
            )
        except WorkflowConflict:
            skipped += 1
        else:
            existing += 1
    return BackfillReport(scanned=scanned, existing=existing, skipped=skipped)


def stock_transaction_shadow_comparison(
    *,
    organization: Organization,
    stock_transaction: StockTransaction,
    workflow_type: str,
) -> dict[str, Any]:
    action = _action(workflow_type)
    if stock_transaction.organization_id != organization.pk:
        raise PermissionDenied("تراکنش انبار متعلق به سازمان دیگری است.")
    legacy_ids = {
        str(pk)
        for pk in OrganizationMembership.objects.filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code=action.permission,
            role_definition__permissions__is_active=True,
        ).values_list("pk", flat=True)
    }
    candidates = WorkItemCandidate.objects.filter(
        organization=organization,
        work_item__instance__definition__workflow_type__code=action.workflow_type,
        work_item__instance__subject_type=SUBJECT_TYPE,
        work_item__instance__subject_id=stock_transaction.pk,
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
        "stock_transaction_id": str(stock_transaction.pk),
        "workflow_type": action.workflow_type,
        "legacy_membership_ids": sorted(legacy_ids),
        "workflow_membership_ids": sorted(workflow_ids),
        "missing_membership_ids": missing,
        "unexpected_membership_ids": unexpected,
        "blocked_runtime_permission_membership_ids": blocked,
        "mismatch": bool(missing or unexpected or blocked),
    }
