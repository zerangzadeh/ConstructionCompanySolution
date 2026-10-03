"""Shared-workflow orchestration for payable certificate approval."""

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

from .models import (
    PayableCertificate,
    PayableCertificateCorrectionKind,
    PayableCertificateStatus,
)
from .workflow import _active_membership_id, _key, _write_configuration

WORKFLOW_TYPE_CODE = "billing.payable_certificate_approval"
SUBJECT_TYPE = "billing.payable_certificate"
TEMPLATE_CODE = "payable_certificate_approval_p6_s14_s20"
DEFINITION_CODE = "payable-certificate-p6-s14-s20"
APPROVE_PERMISSION = BusinessPermissionCode.PAYABLE_CERTIFICATES_APPROVE


def _starter_configuration() -> dict[str, Any]:
    permission = str(APPROVE_PERMISSION)
    return {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {
                "key": "approval",
                "name": "تأیید گواهی پرداخت",
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
                "domain_command": "billing.payable_certificate.approve",
                "required_permission": permission,
            },
            {
                "source": "approval",
                "target": "returned",
                "outcome": "returned",
                "domain_command": "billing.payable_certificate.return",
                "required_permission": permission,
            },
        ],
    }


def load_payable_certificate_subject(
    *, organization: Organization, subject_id: UUID, actor: User, for_update: bool
) -> SubjectSnapshot:
    queryset = PayableCertificate.objects.select_related("project", "contract")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        certificate = queryset.get(pk=subject_id, organization=organization)
    except PayableCertificate.DoesNotExist as exc:
        raise PermissionDenied("گواهی پرداخت در این سازمان یافت نشد.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_CERTIFICATES_VIEW,
        project=certificate.project,
        message="اجازه مشاهده گواهی پرداخت را ندارید.",
    )
    if (
        certificate.project.organization_id != organization.pk
        or certificate.contract.organization_id != organization.pk
        or certificate.contract.project_id != certificate.project_id
    ):
        raise PermissionDenied("دامنه گواهی پرداخت معتبر نیست.")
    return SubjectSnapshot(
        subject=certificate,
        subject_id=str(certificate.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(certificate.project_id),
            "contract_id": str(certificate.contract_id),
            "status": certificate.status,
            "certificate_number": certificate.certificate_number,
            "revision_number": certificate.revision_number,
            "correction_kind": certificate.correction_kind,
            "corrects_certificate_id": (
                str(certificate.corrects_id) if certificate.corrects_id else None
            ),
            "created_by_id": str(certificate.created_by_id),
            "submitted_by_id": (
                str(certificate.submitted_by_id)
                if certificate.submitted_by_id
                else None
            ),
        },
        creator_membership_id=_active_membership_id(
            organization, certificate.created_by_id
        ),
        submitter_membership_id=_active_membership_id(
            organization, certificate.submitted_by_id or certificate.created_by_id
        ),
        display=(
            f"{certificate.contract.contract_number} — گواهی پرداخت "
            f"{certificate.certificate_number} / ویرایش {certificate.revision_number}"
        ),
    )


def _approve_command(
    *,
    subject: PayableCertificate,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> PayableCertificate:
    from .payable_services import _approve_payable_certificate_domain

    reason = context.get("reason", "")
    if not isinstance(reason, str):
        raise ValidationError("دلیل تأیید گواهی پرداخت معتبر نیست.")
    return _approve_payable_certificate_domain(
        organization=organization, actor=actor, certificate=subject, reason=reason
    )


def _return_command(
    *,
    subject: PayableCertificate,
    actor: User,
    organization: Organization,
    context: dict[str, Any],
    **_: object,
) -> PayableCertificate:
    from .payable_services import _return_payable_certificate_domain

    reason = context.get("reason", "")
    if not isinstance(reason, str):
        raise ValidationError("دلیل بازگردانی گواهی پرداخت معتبر نیست.")
    return _return_payable_certificate_domain(
        organization=organization, actor=actor, certificate=subject, reason=reason
    )


def register_payable_certificate_workflow() -> None:
    registry.bind_subject_loader(SUBJECT_TYPE, load_payable_certificate_subject)
    registry.bind_domain_command(
        "billing.payable_certificate.approve", _approve_command
    )
    registry.bind_domain_command("billing.payable_certificate.return", _return_command)


@transaction.atomic
def ensure_payable_certificate_workflow(
    *, organization: Organization, actor: User
) -> WorkflowVersion:
    get_active_membership(user=actor, organization=organization)
    locked_org = Organization.objects.select_for_update(of=("self",)).get(
        pk=organization.pk
    )
    workflow_type = WorkflowType.objects.get(code=WORKFLOW_TYPE_CODE, is_active=True)
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
            "name": "تأیید گواهی پرداخت P6-S14–S20",
            "description": "مسیر پایه با جداسازی قطعی تهیه‌کننده و تأییدکننده.",
            "is_active": True,
            "configuration": _starter_configuration(),
        },
    )
    if not template.is_active:
        raise ValidationError("الگوی گردش گواهی پرداخت غیرفعال است.")
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked_org,
        workflow_type=workflow_type,
        scope_key=scope_key,
        defaults={
            "code": DEFINITION_CODE,
            "name": "تأیید گواهی پرداخت پیمان جزء",
            "description": "گردش تأیید با جداسازی تهیه‌کننده و تأییدکننده.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError("تعریف گواهی پرداخت نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked_org,
        definition=definition,
        version_number=1,
        change_summary="P6-S14-S20 payable certificate starter workflow",
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
            metadata={"workflow_type": WORKFLOW_TYPE_CODE, "starter": True},
        )
    version.refresh_from_db()
    return version


def _resolve_version(
    *, organization: Organization, certificate: PayableCertificate
) -> WorkflowVersion:
    context = {
        "project_id": str(certificate.project_id),
        "contract_id": str(certificate.contract_id),
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
        raise ValidationError("نسخه منتشرشده گردش تأیید گواهی پرداخت یافت نشد.")
    score = max(value for value, _ in matches)
    selected = [version for value, version in matches if value == score]
    if len(selected) != 1:
        raise ValidationError("انتخاب نسخه گردش گواهی پرداخت مبهم است.")
    return selected[0]


def _submission_snapshot(certificate: PayableCertificate) -> dict[str, Any]:
    return {
        "certificate": {
            "id": str(certificate.pk),
            "certificate_number": certificate.certificate_number,
            "revision_number": certificate.revision_number,
            "correction_kind": certificate.correction_kind,
            "corrects_certificate_id": (
                str(certificate.corrects_id) if certificate.corrects_id else None
            ),
            "period_start": certificate.period_start.isoformat(),
            "period_end": certificate.period_end.isoformat(),
            "measurement_cutoff": certificate.measurement_cutoff.isoformat(),
            "contract_term_version_id": str(certificate.contract_term_version_id),
            "party_identity_snapshot_id": str(certificate.party_identity_snapshot_id),
            "currency_code": certificate.currency_code,
            "gross_amount": str(certificate.gross_amount),
            "adjustment_amount": str(certificate.adjustment_amount),
            "net_amount": str(certificate.net_amount),
            "calculation": certificate.calculation_snapshot,
        },
        "items": [
            {
                "stable_line_id": str(item.stable_line_id),
                "contract_item_id": str(item.contract_item_id),
                "measurement_id": str(item.measurement_id),
                "previous_cumulative_quantity": str(item.previous_cumulative_quantity),
                "current_quantity": str(item.current_quantity),
                "new_cumulative_quantity": str(item.new_cumulative_quantity),
                "unit_rate_snapshot": str(item.unit_rate_snapshot),
                "current_amount": str(item.current_amount),
            }
            for item in certificate.items.order_by("stable_line_id")
        ],
        "adjustments": [
            {
                "type": item.adjustment_type,
                "description": item.description,
                "amount": str(item.amount),
                "rate": str(item.rate_snapshot)
                if item.rate_snapshot is not None
                else None,
                "base": (
                    str(item.base_amount_snapshot)
                    if item.base_amount_snapshot is not None
                    else None
                ),
                "evidence": item.evidence,
            }
            for item in certificate.adjustments.order_by("sequence", "created_at")
        ],
    }


@transaction.atomic
def submit_payable_certificate_with_workflow(
    *, organization: Organization, actor: User, certificate: PayableCertificate
) -> WorkflowInstance:
    try:
        locked = (
            PayableCertificate.objects.select_for_update(of=("self",))
            .select_related(
                "project",
                "contract",
                "contract_term_version",
                "party_identity_snapshot",
            )
            .get(pk=certificate.pk, organization=organization)
        )
    except PayableCertificate.DoesNotExist as exc:
        raise PermissionDenied("گواهی پرداخت متعلق به این سازمان نیست.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYABLE_CERTIFICATES_SUBMIT,
        project=locked.project,
        message="اجازه ارسال گواهی پرداخت را ندارید.",
    )
    if locked.status == PayableCertificateStatus.SUBMITTED:
        existing = WorkflowInstance.objects.filter(
            organization=organization,
            subject_type=SUBJECT_TYPE,
            subject_id=locked.pk,
            status=WorkflowInstanceStatus.ACTIVE,
        ).first()
        if existing:
            return existing
    if locked.status != PayableCertificateStatus.DRAFT:
        raise ValidationError("فقط گواهی پرداخت پیش‌نویس قابل ارسال است.")
    if locked.correction_kind != PayableCertificateCorrectionKind.CANCELLATION and (
        not locked.items.exists() or locked.net_amount <= 0
    ):
        raise ValidationError("گواهی پرداخت بدون ردیف و مبلغ مثبت قابل ارسال نیست.")
    locked.submitted_by = actor
    locked.updated_by = actor
    locked.save(update_fields=["submitted_by", "updated_by", "updated_at"])
    ensure_payable_certificate_workflow(organization=organization, actor=actor)
    version = _resolve_version(organization=organization, certificate=locked)
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=locked.pk,
        idempotency_key=_key(WORKFLOW_TYPE_CODE, locked.pk, "submit"),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict("ارسال گواهی پرداخت بدون کار فعال قابل ثبت نیست.")
    locked.submitted_at = timezone.now()
    locked.submission_snapshot = _submission_snapshot(locked)
    locked.status = PayableCertificateStatus.SUBMITTED
    locked.save(
        update_fields=[
            "status",
            "submitted_at",
            "submission_snapshot",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.PAYABLE_CERTIFICATE_SUBMITTED,
        entity_type="billing.PayableCertificate",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "certificate_number": locked.certificate_number,
            "revision_number": locked.revision_number,
        },
    )
    return instance


def _actor_item(
    *,
    organization: Organization,
    certificate: PayableCertificate,
    membership: OrganizationMembership,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=SUBJECT_TYPE,
            instance__subject_id=certificate.pk,
            instance__status=WorkflowInstanceStatus.ACTIVE,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            candidates__membership=membership,
            candidates__is_active=True,
        )
        .distinct()
        .first()
    )
    if item is None:
        raise PermissionDenied("کار فعال و نامزدی معتبر برای گواهی پرداخت وجود ندارد.")
    return item


def _complete(
    *,
    organization: Organization,
    actor: User,
    certificate: PayableCertificate,
    reason: str,
    outcome: str,
) -> PayableCertificate:
    if not reason.strip():
        raise ValidationError("دلیل تصمیم گواهی پرداخت الزامی است.")
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=APPROVE_PERMISSION,
        project=certificate.project,
        message="اجازه تصمیم‌گیری گواهی پرداخت را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    try:
        locked = PayableCertificate.objects.select_for_update(of=("self",)).get(
            pk=certificate.pk, organization=organization
        )
    except PayableCertificate.DoesNotExist as exc:
        raise PermissionDenied("گواهی پرداخت متعلق به این سازمان نیست.") from exc
    if locked.status != PayableCertificateStatus.SUBMITTED:
        raise ValidationError("فقط گواهی پرداخت ارسال‌شده قابل تصمیم‌گیری است.")
    item = _actor_item(
        organization=organization, certificate=locked, membership=membership
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
    locked.refresh_from_db()
    return locked


@transaction.atomic
def approve_payable_certificate_with_workflow(
    *,
    organization: Organization,
    actor: User,
    certificate: PayableCertificate,
    reason: str,
) -> PayableCertificate:
    return _complete(
        organization=organization,
        actor=actor,
        certificate=certificate,
        reason=reason,
        outcome="approved",
    )


@transaction.atomic
def return_payable_certificate_with_workflow(
    *,
    organization: Organization,
    actor: User,
    certificate: PayableCertificate,
    reason: str,
) -> PayableCertificate:
    return _complete(
        organization=organization,
        actor=actor,
        certificate=certificate,
        reason=reason,
        outcome="returned",
    )
