from __future__ import annotations

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
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
)
from apps.workflows.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowTemplate,
    WorkflowType,
    WorkflowVersion,
    WorkflowVersionStatus,
    WorkItem,
    WorkItemStatus,
    canonical_scope,
)
from apps.workflows.registry import SubjectSnapshot, registry
from apps.workflows.runtime import (
    WorkflowConflict,
    claim_work_item,
    complete_work_item,
    start_workflow,
)
from apps.workflows.validators import validate_workflow_version

from .models import ContractualRecord, ContractualRecordStatus
from .workflow import _active_membership_id, _key, _write_configuration

WORKFLOW_TYPE = "contracts.contractual_record_approval"
SUBJECT_TYPE = "contracts.contractual_record"
TEMPLATE_CODE = "contractual_record_approval_p6_s33_s38"
DEFINITION_CODE = "contractual-record-approval-p6-s33-s38"


def _configuration() -> dict[str, Any]:
    permission = str(BusinessPermissionCode.CONTRACTUAL_RECORDS_APPROVE)
    return {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {
                "key": "approval",
                "name": "تصمیم رکورد قراردادی",
                "step_type": "approval",
                "configuration": {
                    "decision_policy": "any",
                    "exclude_submitter": True,
                    "allow_submitter_if_no_other_candidate": False,
                },
                "routing": [
                    {
                        "resolver_type": "submitter_primary_position_manager",
                        "configuration": {"permission": permission},
                    },
                    {
                        "resolver_type": "business_permission",
                        "configuration": {
                            "permission": permission,
                            "exclude_submitter_unless_no_other": False,
                        },
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
                "key": "returned",
                "name": "بازگردانده‌شده",
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
                "domain_command": "contracts.contractual_record.approve",
                "required_permission": permission,
            },
            {
                "source": "approval",
                "target": "returned",
                "outcome": "returned",
                "domain_command": "contracts.contractual_record.return",
                "required_permission": permission,
            },
        ],
    }


def load_contractual_record_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    queryset = ContractualRecord.objects.select_related("project", "contract")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        record = queryset.get(pk=subject_id, organization=organization)
    except ContractualRecord.DoesNotExist as exc:
        raise PermissionDenied("رکورد قراردادی در این سازمان یافت نشد.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTUAL_RECORDS_VIEW,
        project=record.project,
        message="اجازه مشاهده رکورد قراردادی را ندارید.",
    )
    if record.contract.project_id != record.project_id:
        raise PermissionDenied("دامنه رکورد قراردادی معتبر نیست.")
    return SubjectSnapshot(
        subject=record,
        subject_id=str(record.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(record.project_id),
            "contract_id": str(record.contract_id),
            "status": record.status,
            "kind": record.kind,
            "created_by_id": str(record.created_by_id),
            "submitted_by_id": str(record.submitted_by_id)
            if record.submitted_by_id
            else None,
        },
        creator_membership_id=_active_membership_id(organization, record.created_by_id),
        submitter_membership_id=_active_membership_id(
            organization, record.submitted_by_id or record.created_by_id
        ),
        display=f"{record.contract.contract_number} — {record.get_kind_display()}",
    )


def _approve_command(*, subject, actor, organization, context, **_):
    from .contractual_services import _approve_contractual_record_domain

    entitlement = context.get("entitlement_approved")
    if not isinstance(entitlement, bool):
        raise ValidationError("تصمیم صریح استحقاق الزامی است.")
    return _approve_contractual_record_domain(
        organization=organization,
        actor=actor,
        record=subject,
        reason=str(context.get("reason", "")),
        entitlement_approved=entitlement,
        approved_amount=context.get("approved_amount"),
        approved_eot_days=context.get("approved_eot_days"),
        delay_responsibility=str(context.get("delay_responsibility", "")),
    )


def _return_command(*, subject, actor, organization, context, **_):
    from .contractual_services import _return_contractual_record_domain

    return _return_contractual_record_domain(
        organization=organization,
        actor=actor,
        record=subject,
        reason=str(context.get("reason", "")),
    )


def _withdraw_command(*, subject, actor, organization, context, **_):
    from .contractual_services import _withdraw_contractual_record_domain

    return _withdraw_contractual_record_domain(
        organization=organization,
        actor=actor,
        record=subject,
        reason=str(context.get("reason", "")),
    )


def register_contractual_record_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_contractual_record_subject)
    registry.bind_domain_command(
        "contracts.contractual_record.approve", _approve_command
    )
    registry.bind_domain_command("contracts.contractual_record.return", _return_command)
    registry.bind_domain_command(
        "contracts.contractual_record.withdraw", _withdraw_command
    )


@transaction.atomic
def _ensure_workflow(*, organization: Organization, actor: User) -> WorkflowVersion:
    get_active_membership(user=actor, organization=organization)
    locked_org = Organization.objects.select_for_update(of=("self",)).get(
        pk=organization.pk
    )
    workflow_type = WorkflowType.objects.get(code=WORKFLOW_TYPE, is_active=True)
    _, scope_key = canonical_scope({})
    existing = (
        WorkflowVersion.objects.select_related("definition")
        .filter(
            organization=locked_org,
            definition__workflow_type=workflow_type,
            definition__scope_key=scope_key,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        .first()
    )
    if existing:
        issues = validate_workflow_version(existing)
        if issues:
            raise ValidationError([issue.message for issue in issues])
        return existing
    template, _ = WorkflowTemplate.objects.get_or_create(
        workflow_type=workflow_type,
        code=TEMPLATE_CODE,
        defaults={
            "name": "تأیید رکورد قراردادی P6-S33–S38",
            "description": "مسیر پایه با جداسازی قطعی ارسال‌کننده و تأییدکننده.",
            "is_active": True,
            "configuration": _configuration(),
        },
    )
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked_org,
        workflow_type=workflow_type,
        scope_key=scope_key,
        defaults={
            "code": DEFINITION_CODE,
            "name": "تأیید رکورد قراردادی",
            "description": "تصمیم صریح استحقاق و آثار قراردادی بدون اثر خودکار.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف رکورد قراردادی نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked_org,
        definition=definition,
        version_number=1,
        change_summary="P6-S33-S38 contractual record starter workflow",
    )
    _write_configuration(
        organization=locked_org, version=version, configuration=template.configuration
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
            entity_id=entity_id,
            organization=locked_org,
            actor=actor,
            metadata={"workflow_type": WORKFLOW_TYPE, "starter": True},
        )
    version.refresh_from_db()
    return version


def _resolve_version(
    *, organization: Organization, record: ContractualRecord
) -> WorkflowVersion:
    context = {
        "project_id": str(record.project_id),
        "contract_id": str(record.contract_id),
    }
    matches = [
        (len(version.definition.scope), version)
        for version in WorkflowVersion.objects.select_related("definition").filter(
            organization=organization,
            definition__workflow_type__code=WORKFLOW_TYPE,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        if all(
            context.get(key) == value for key, value in version.definition.scope.items()
        )
    ]
    if not matches:
        raise ValidationError("نسخه منتشرشده گردش رکورد قراردادی یافت نشد.")
    score = max(value for value, _ in matches)
    selected = [version for value, version in matches if value == score]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش رکورد قراردادی مبهم است.")
    return selected[0]


@transaction.atomic
def submit_contractual_record(
    *, organization: Organization, actor: User, record: ContractualRecord
) -> WorkflowInstance:
    locked = (
        ContractualRecord.objects.select_for_update(of=("self",))
        .select_related("project", "contract", "party_identity_snapshot")
        .get(pk=record.pk, organization=organization)
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTUAL_RECORDS_SUBMIT,
        project=locked.project,
        message="اجازه ارسال رکورد قراردادی را ندارید.",
    )
    if locked.status == ContractualRecordStatus.SUBMITTED:
        existing = WorkflowInstance.objects.filter(
            organization=organization,
            subject_type=SUBJECT_TYPE,
            subject_id=locked.pk,
            status=WorkflowInstanceStatus.ACTIVE,
        ).first()
        if existing:
            return existing
    if locked.status != ContractualRecordStatus.DRAFT:
        raise ValidationError("فقط نسخه پیش‌نویس قابل ارسال است.")
    locked.submitted_by = actor
    locked.updated_by = actor
    locked.save(update_fields=["submitted_by", "updated_by", "updated_at"])
    _ensure_workflow(organization=organization, actor=actor)
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=_resolve_version(organization=organization, record=locked).pk,
        subject_id=locked.pk,
        idempotency_key=_key(WORKFLOW_TYPE, locked.pk, "submit"),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("ارسال بدون کار فعال قابل ثبت نیست.")
    from .contractual_services import _approval_snapshot

    locked.status = ContractualRecordStatus.SUBMITTED
    locked.submitted_at = timezone.now()
    locked.submission_snapshot = _approval_snapshot(locked)
    locked.save(
        update_fields=["status", "submitted_at", "submission_snapshot", "updated_at"]
    )
    record_audit_event(
        action=AuditAction.CONTRACTUAL_RECORD_SUBMITTED,
        entity_type="contracts.ContractualRecord",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"workflow_instance_id": str(instance.pk)},
    )
    return instance


def _actor_item(
    *,
    organization: Organization,
    record: ContractualRecord,
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
        raise PermissionDenied("کار فعال و نامزدی معتبر برای این رکورد وجود ندارد.")
    return item


@transaction.atomic
def decide_contractual_record(
    *,
    organization: Organization,
    actor: User,
    record: ContractualRecord,
    approved: bool,
    reason: str,
    entitlement_approved: bool | None = None,
    approved_amount=None,
    approved_eot_days: int | None = None,
    delay_responsibility: str = "",
) -> ContractualRecord:
    if not reason.strip():
        raise ValidationError("دلیل تصمیم الزامی است.")
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACTUAL_RECORDS_APPROVE,
        project=record.project,
        message="اجازه تصمیم‌گیری رکورد قراردادی را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    locked = ContractualRecord.objects.select_for_update(of=("self",)).get(
        pk=record.pk, organization=organization
    )
    if locked.status != ContractualRecordStatus.SUBMITTED:
        raise ValidationError("فقط رکورد ارسال‌شده قابل تصمیم‌گیری است.")
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
    context = {"reason": reason.strip()}
    if approved:
        context.update(
            entitlement_approved=entitlement_approved,
            approved_amount=approved_amount,
            approved_eot_days=approved_eot_days,
            delay_responsibility=delay_responsibility,
        )
    complete_work_item(
        actor=actor,
        organization=organization,
        work_item_id=item.pk,
        outcome="approved" if approved else "returned",
        idempotency_key=_key(
            item.pk, membership.pk, "approved" if approved else "returned"
        ),
        command_context=context,
    )
    locked.refresh_from_db()
    return locked
