from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
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
from apps.workflows.runtime import (
    WorkflowConflict,
    cancel_workflow_for_domain,
    claim_work_item,
    complete_work_item,
    start_workflow,
)
from apps.workflows.validators import validate_workflow_version

from .models import PurchaseRequest, PurchaseRequestStatus

WORKFLOW_TYPE_CODE = "procurement.purchase_request_approval"
SUBJECT_TYPE = "procurement.purchase_request"
COMPATIBILITY_TEMPLATE_CODE = "purchase_request_legacy_compatibility"
COMPATIBILITY_DEFINITION_CODE = "purchase-request-legacy-compatibility"

COMPATIBILITY_CONFIGURATION: dict[str, Any] = {
    "steps": [
        {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
        {
            "key": "legacy_decision",
            "name": "تصمیم سازگار با خرید",
            "step_type": "approval",
            "configuration": {"decision_policy": "any"},
            "routing": [
                {
                    "resolver_type": "business_permission",
                    "configuration": {
                        "permission": str(
                            BusinessPermissionCode.PURCHASE_REQUESTS_APPROVE
                        )
                    },
                },
                {
                    "resolver_type": "business_permission",
                    "configuration": {
                        "permission": str(
                            BusinessPermissionCode.PURCHASE_REQUESTS_REJECT
                        )
                    },
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
        {
            "key": "rejected",
            "name": "ردشده",
            "step_type": "end",
            "is_terminal": True,
        },
    ],
    "transitions": [
        {
            "source": "start",
            "target": "legacy_decision",
            "outcome": "submitted",
            "is_default": True,
        },
        {
            "source": "legacy_decision",
            "target": "approved",
            "outcome": "approved",
            "domain_command": "procurement.purchase_request.approve",
            "required_permission": str(
                BusinessPermissionCode.PURCHASE_REQUESTS_APPROVE
            ),
        },
        {
            "source": "legacy_decision",
            "target": "rejected",
            "outcome": "rejected",
            "domain_command": "procurement.purchase_request.reject",
            "required_permission": str(BusinessPermissionCode.PURCHASE_REQUESTS_REJECT),
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


def load_purchase_request_subject(
    *,
    organization: Organization,
    subject_id: UUID,
    actor: User,
    for_update: bool,
) -> SubjectSnapshot:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PURCHASE_REQUESTS_VIEW,
        message="اجازه مشاهده این درخواست خرید را ندارید.",
    )
    queryset = PurchaseRequest.objects.select_related(
        "project", "created_by", "updated_by"
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        purchase_request = queryset.get(pk=subject_id, organization=organization)
    except PurchaseRequest.DoesNotExist as exc:
        raise PermissionDenied("درخواست خرید در این سازمان یافت نشد.") from exc
    if purchase_request.project.organization_id != organization.pk:
        raise PermissionDenied("پروژه درخواست خرید متعلق به این سازمان نیست.")
    return SubjectSnapshot(
        subject=purchase_request,
        subject_id=str(purchase_request.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(purchase_request.project_id),
            "status": purchase_request.status,
            "created_by_id": str(purchase_request.created_by_id),
        },
        creator_membership_id=_active_membership_id(
            organization, purchase_request.created_by_id
        ),
        submitter_membership_id=_active_membership_id(
            organization, purchase_request.updated_by_id
        ),
        display=f"{purchase_request.request_number} — {purchase_request.title}",
    )


def _submit_command(
    *, subject: PurchaseRequest, actor: User, organization: Organization, **_: object
) -> PurchaseRequest:
    from .services import _submit_purchase_request_domain

    return _submit_purchase_request_domain(
        organization=organization, actor=actor, purchase_request=subject
    )


def _approve_command(
    *,
    subject: PurchaseRequest,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> PurchaseRequest:
    from .services import _decide_purchase_request_domain

    return _decide_purchase_request_domain(
        organization=organization,
        actor=actor,
        purchase_request=subject,
        approve=True,
        reason=str(context.get("reason", "")),
    )


def _reject_command(
    *,
    subject: PurchaseRequest,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> PurchaseRequest:
    from .services import _decide_purchase_request_domain

    return _decide_purchase_request_domain(
        organization=organization,
        actor=actor,
        purchase_request=subject,
        approve=False,
        reason=str(context.get("reason", "")),
    )


def _cancel_command(
    *,
    subject: PurchaseRequest,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> PurchaseRequest:
    from .services import _cancel_purchase_request_domain

    return _cancel_purchase_request_domain(
        organization=organization,
        actor=actor,
        purchase_request=subject,
        reason=str(context.get("reason", "")),
    )


def register_purchase_request_workflow() -> None:
    registry.bind_subject_loader(
        "procurement.purchase_request", load_purchase_request_subject
    )
    registry.bind_domain_command("procurement.purchase_request.submit", _submit_command)
    registry.bind_domain_command(
        "procurement.purchase_request.approve", _approve_command
    )
    registry.bind_domain_command("procurement.purchase_request.reject", _reject_command)
    registry.bind_domain_command("procurement.purchase_request.cancel", _cancel_command)


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
            required_permission=item.get("required_permission", ""),
            domain_command=item.get("domain_command", ""),
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
                order=route.get("order", order),
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
            priority=item.get("priority", 0),
            is_default=item.get("is_default", False),
        )


@transaction.atomic
def ensure_purchase_request_compatibility_workflow(
    *, organization: Organization, actor: User
) -> WorkflowVersion:
    """Materialize the code-owned legacy policy once for a tenant."""

    get_active_membership(user=actor, organization=organization)
    locked_organization = Organization.objects.select_for_update().get(
        pk=organization.pk
    )
    workflow_type = WorkflowType.objects.get(code=WORKFLOW_TYPE_CODE, is_active=True)
    _, default_scope_key = canonical_scope({})
    existing = (
        WorkflowVersion.objects.select_related("definition")
        .filter(
            organization=locked_organization,
            definition__workflow_type=workflow_type,
            definition__scope_key=default_scope_key,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        .first()
    )
    if existing:
        if validate_workflow_version(existing):
            raise ValidationError("گردش‌کار پیش‌فرض منتشرشده معتبر نیست.")
        return existing
    template = WorkflowTemplate.objects.get(
        workflow_type=workflow_type,
        code=COMPATIBILITY_TEMPLATE_CODE,
        is_active=True,
    )
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked_organization,
        workflow_type=workflow_type,
        scope_key=default_scope_key,
        defaults={
            "code": COMPATIBILITY_DEFINITION_CODE,
            "name": "سازگاری تأیید درخواست خرید",
            "description": "رفتار تک‌تصمیمی پیش از W3 را بدون تفکیک وظایف حفظ می‌کند.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف پیش‌فرض گردش‌کار نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked_organization,
        definition=definition,
        version_number=1,
        change_summary="W3 legacy compatibility",
    )
    _write_configuration(
        organization=locked_organization,
        version=version,
        configuration=template.configuration,
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
    record_audit_event(
        action=AuditAction.WORKFLOW_DEFINITION_CREATED,
        entity_type="workflows.WorkflowDefinition",
        entity_id=str(definition.pk),
        organization=locked_organization,
        actor=actor,
        metadata={"workflow_type": WORKFLOW_TYPE_CODE, "compatibility": True},
    )
    record_audit_event(
        action=AuditAction.WORKFLOW_VERSION_PUBLISHED,
        entity_type="workflows.WorkflowVersion",
        entity_id=str(version.pk),
        organization=locked_organization,
        actor=actor,
        metadata={"version": 1, "compatibility": True},
    )
    version.refresh_from_db()
    return version


def _subject_context(purchase_request: PurchaseRequest) -> dict[str, str]:
    return {
        "project_id": str(purchase_request.project_id),
        "status": purchase_request.status,
        "created_by_id": str(purchase_request.created_by_id),
    }


def resolve_purchase_request_workflow_version(
    *, organization: Organization, purchase_request: PurchaseRequest
) -> WorkflowVersion:
    if purchase_request.organization_id != organization.pk:
        raise PermissionDenied("درخواست خرید متعلق به سازمان دیگری است.")
    context = _subject_context(purchase_request)
    candidates: list[tuple[int, WorkflowVersion]] = []
    versions = WorkflowVersion.objects.select_related("definition").filter(
        organization=organization,
        definition__workflow_type__code=WORKFLOW_TYPE_CODE,
        status=WorkflowVersionStatus.PUBLISHED,
    )
    for version in versions:
        if all(
            context.get(key) == value for key, value in version.definition.scope.items()
        ):
            candidates.append((len(version.definition.scope), version))
    if not candidates:
        raise ValidationError("نسخه منتشرشده سازگار برای درخواست خرید یافت نشد.")
    specificity = max(score for score, _ in candidates)
    selected = [version for score, version in candidates if score == specificity]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش‌کار درخواست خرید مبهم است.")
    return selected[0]


def _command(key: str):
    command = registry.domain_commands.get(key)
    if command is None or command.executor is None:
        raise ValidationError("فرمان دامنه درخواست خرید ثبت نشده است.")
    return command


def _authorize_owned_request_action(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    permission: BusinessPermissionCode,
) -> OrganizationMembership:
    if purchase_request.organization_id != organization.pk:
        raise PermissionDenied("درخواست خرید متعلق به سازمان دیگری است.")
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اجازه انجام این عملیات درخواست خرید را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    if (
        not actor.is_superuser
        and not membership_has_permission(
            membership, BusinessPermissionCode.PURCHASE_REQUESTS_APPROVE
        )
        and purchase_request.created_by_id != actor.pk
    ):
        raise PermissionDenied("اجازه انجام این عملیات روی درخواست خرید را ندارید.")
    return membership


def submit_purchase_request_with_workflow(
    *, organization: Organization, actor: User, purchase_request: PurchaseRequest
) -> PurchaseRequest:
    _authorize_owned_request_action(
        organization=organization,
        actor=actor,
        purchase_request=purchase_request,
        permission=BusinessPermissionCode.PURCHASE_REQUESTS_SUBMIT,
    )
    ensure_purchase_request_compatibility_workflow(
        organization=organization, actor=actor
    )
    current_status = (
        PurchaseRequest.objects.filter(
            pk=purchase_request.pk, organization=organization
        )
        .values_list("status", flat=True)
        .first()
    )
    if current_status == PurchaseRequestStatus.SUBMITTED:
        version = resolve_purchase_request_workflow_version(
            organization=organization, purchase_request=purchase_request
        )
        instance = start_workflow(
            actor=actor,
            organization=organization,
            version_id=version.pk,
            subject_id=purchase_request.pk,
            idempotency_key=_key(WORKFLOW_TYPE_CODE, purchase_request.pk, "start"),
        )
        if (
            instance.status != WorkflowInstanceStatus.ACTIVE
            or not instance.work_items.filter(
                status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
            ).exists()
        ):
            raise WorkflowConflict("ارسال درخواست بدون کار فعال قابل ثبت نیست.")
        purchase_request.refresh_from_db()
        return purchase_request
    return _submit_purchase_request_atomic(
        organization=organization, actor=actor, purchase_request=purchase_request
    )


@transaction.atomic
def _submit_purchase_request_atomic(
    *, organization: Organization, actor: User, purchase_request: PurchaseRequest
) -> PurchaseRequest:
    version = resolve_purchase_request_workflow_version(
        organization=organization, purchase_request=purchase_request
    )
    _command("procurement.purchase_request.submit").executor(
        subject=purchase_request,
        actor=actor,
        organization=organization,
        outcome="submitted",
        context={},
        idempotency_key=_key(purchase_request.pk, "submit"),
    )
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=purchase_request.pk,
        idempotency_key=_key(WORKFLOW_TYPE_CODE, purchase_request.pk, "start"),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("ارسال درخواست بدون کار فعال قابل ثبت نیست.")
    purchase_request.refresh_from_db()
    return purchase_request


def _actor_item(
    *,
    organization: Organization,
    purchase_request: PurchaseRequest,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=purchase_request.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و candidacy معتبر برای این تصمیم وجود ندارد.")
    return item


@transaction.atomic
def decide_purchase_request_with_workflow(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    outcome: str,
    reason: str = "",
) -> PurchaseRequest:
    if outcome not in {"approved", "rejected"}:
        raise ValidationError("نتیجه تصمیم درخواست خرید ثبت نشده است.")
    permission = (
        BusinessPermissionCode.PURCHASE_REQUESTS_APPROVE
        if outcome == "approved"
        else BusinessPermissionCode.PURCHASE_REQUESTS_REJECT
    )
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اجازه تعیین تکلیف این درخواست خرید را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    if purchase_request.organization_id != organization.pk:
        raise PermissionDenied("درخواست خرید متعلق به سازمان دیگری است.")
    current_status = (
        PurchaseRequest.objects.filter(
            pk=purchase_request.pk, organization=organization
        )
        .values_list("status", flat=True)
        .first()
    )
    expected_status = (
        PurchaseRequestStatus.APPROVED
        if outcome == "approved"
        else PurchaseRequestStatus.REJECTED
    )
    if (
        current_status == expected_status
        and WorkItem.objects.filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=purchase_request.pk,
            completion_outcome=outcome,
            assignment_history__actor_membership=membership,
            assignment_history__action="complete",
        ).exists()
    ):
        purchase_request.refresh_from_db()
        return purchase_request
    if current_status != PurchaseRequestStatus.SUBMITTED:
        raise ValueError("فقط درخواست‌های خرید ارسال‌شده قابل تعیین تکلیف هستند.")
    item = _actor_item(
        organization=organization,
        purchase_request=purchase_request,
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
        outcome=outcome,
        idempotency_key=_key(item.pk, membership.pk, outcome),
        command_context={"reason": reason.strip()},
    )
    purchase_request.refresh_from_db()
    return purchase_request


@transaction.atomic
def cancel_purchase_request_with_workflow(
    *,
    organization: Organization,
    actor: User,
    purchase_request: PurchaseRequest,
    reason: str,
) -> PurchaseRequest:
    _authorize_owned_request_action(
        organization=organization,
        actor=actor,
        purchase_request=purchase_request,
        permission=BusinessPermissionCode.PURCHASE_REQUESTS_CANCEL,
    )
    current_status = (
        PurchaseRequest.objects.filter(
            pk=purchase_request.pk, organization=organization
        )
        .values_list("status", flat=True)
        .first()
    )
    if (
        current_status == PurchaseRequestStatus.CANCELLED
        and AuditEvent.objects.filter(
            organization=organization,
            entity_id=str(purchase_request.pk),
            action=AuditAction.PURCHASE_REQUEST_CANCELLED,
            actor=actor,
        ).exists()
    ):
        purchase_request.refresh_from_db()
        return purchase_request
    if current_status not in (
        PurchaseRequestStatus.DRAFT,
        PurchaseRequestStatus.SUBMITTED,
    ):
        raise ValueError("فقط درخواست‌های خرید پیش‌نویس یا ارسال‌شده قابل لغو هستند.")
    if current_status == PurchaseRequestStatus.DRAFT:
        _command("procurement.purchase_request.cancel").executor(
            subject=purchase_request,
            actor=actor,
            organization=organization,
            outcome="cancelled",
            context={"reason": reason.strip()},
            idempotency_key=_key(purchase_request.pk, "cancel"),
        )
    else:
        instance = WorkflowInstance.objects.filter(
            organization=organization,
            subject_type=SUBJECT_TYPE,
            subject_id=purchase_request.pk,
            status__in=(
                WorkflowInstanceStatus.ACTIVE,
                WorkflowInstanceStatus.SUSPENDED,
            ),
        ).first()
        if instance is None:
            raise WorkflowConflict("اجرای فعال گردش‌کار برای لغو درخواست یافت نشد.")
        cancel_workflow_for_domain(
            actor=actor,
            organization=organization,
            instance_id=instance.pk,
            command_key="procurement.purchase_request.cancel",
            reason=reason,
            idempotency_key=_key(purchase_request.pk, "cancel"),
        )
    purchase_request.refresh_from_db()
    return purchase_request


@dataclass(frozen=True, slots=True)
class BackfillReport:
    scanned: int = 0
    created: int = 0
    existing: int = 0
    skipped: int = 0


def _backfill_actor(purchase_request: PurchaseRequest) -> User | None:
    memberships = OrganizationMembership.objects.filter(
        organization=purchase_request.organization,
        status=MembershipStatus.ACTIVE,
        role_definition__is_active=True,
        user__is_active=True,
    ).select_related("user", "role_definition")
    preferred = memberships.filter(user_id=purchase_request.updated_by_id).first()
    if preferred and membership_has_permission(
        preferred, BusinessPermissionCode.PURCHASE_REQUESTS_SUBMIT
    ):
        return preferred.user
    owner = memberships.filter(role_definition__is_owner=True).first()
    return owner.user if owner else None


def backfill_submitted_purchase_requests(
    *, organization: Organization | None = None
) -> BackfillReport:
    queryset = PurchaseRequest.objects.filter(status=PurchaseRequestStatus.SUBMITTED)
    if organization is not None:
        queryset = queryset.filter(organization=organization)
    scanned = created = existing = skipped = 0
    for purchase_request in queryset.select_related(
        "organization", "updated_by"
    ).iterator():
        scanned += 1
        actor = _backfill_actor(purchase_request)
        if actor is None:
            skipped += 1
            continue
        ensure_purchase_request_compatibility_workflow(
            organization=purchase_request.organization, actor=actor
        )
        was_present = WorkflowInstance.objects.filter(
            organization=purchase_request.organization,
            subject_type=SUBJECT_TYPE,
            subject_id=purchase_request.pk,
        ).exists()
        version = resolve_purchase_request_workflow_version(
            organization=purchase_request.organization,
            purchase_request=purchase_request,
        )
        start_workflow(
            actor=actor,
            organization=purchase_request.organization,
            version_id=version.pk,
            subject_id=purchase_request.pk,
            idempotency_key=_key(WORKFLOW_TYPE_CODE, purchase_request.pk, "start"),
        )
        if was_present:
            existing += 1
        else:
            created += 1
    return BackfillReport(
        scanned=scanned, created=created, existing=existing, skipped=skipped
    )


def purchase_request_shadow_comparison(
    *, organization: Organization, purchase_request: PurchaseRequest
) -> dict[str, Any]:
    if purchase_request.organization_id != organization.pk:
        raise PermissionDenied("درخواست خرید متعلق به سازمان دیگری است.")
    legacy_ids = {
        str(value)
        for value in OrganizationMembership.objects.filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
            role_definition__is_active=True,
            user__is_active=True,
            role_definition__permissions__code__in=(
                str(BusinessPermissionCode.PURCHASE_REQUESTS_APPROVE),
                str(BusinessPermissionCode.PURCHASE_REQUESTS_REJECT),
            ),
            role_definition__permissions__is_active=True,
        )
        .distinct()
        .values_list("pk", flat=True)
    }
    workflow_ids = {
        str(value)
        for value in WorkItemCandidate.objects.filter(
            organization=organization,
            work_item__instance__subject_type=SUBJECT_TYPE,
            work_item__instance__subject_id=purchase_request.pk,
            work_item__status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            is_active=True,
        ).values_list("membership_id", flat=True)
    }
    missing = sorted(legacy_ids - workflow_ids)
    unexpected = sorted(workflow_ids - legacy_ids)
    return {
        "purchase_request_id": str(purchase_request.pk),
        "legacy_membership_ids": sorted(legacy_ids),
        "workflow_membership_ids": sorted(workflow_ids),
        "missing_membership_ids": missing,
        "unexpected_membership_ids": unexpected,
        "mismatch": bool(missing or unexpected),
    }
