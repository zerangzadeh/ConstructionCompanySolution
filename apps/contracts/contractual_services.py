from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import BusinessPermissionCode, Organization

from .models import (
    Contract,
    ContractStatus,
    ContractualRecord,
    ContractualRecordEvidence,
    ContractualRecordKind,
    ContractualRecordStatus,
    ContractualRevisionAction,
)


def _permission(
    *,
    actor: User,
    organization: Organization,
    code,
    project,
    allow_any_scope: bool = False,
):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=code,
        project=project,
        allow_any_scope=allow_any_scope,
        message="اجازه انجام عملیات رکورد قراردادی را ندارید.",
    )


def _decimal(value: Decimal | str | int | None) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, (bool, float)):
        raise ValidationError("مبلغ باید با Decimal وارد شود.")
    try:
        parsed = Decimal(value)
    except Exception as exc:
        raise ValidationError("مبلغ معتبر نیست.") from exc
    if (
        not parsed.is_finite()
        or parsed < 0
        or parsed != parsed.quantize(Decimal("0.0001"))
    ):
        raise ValidationError("مبلغ باید نامنفی و حداکثر دارای چهار رقم اعشار باشد.")
    return parsed


def _locked_contract(*, organization: Organization, contract: Contract) -> Contract:
    try:
        locked = (
            Contract.objects.select_for_update(of=("self",))
            .select_related("project", "party")
            .get(pk=contract.pk, organization=organization, deleted_at__isnull=True)
        )
    except Contract.DoesNotExist as exc:
        raise PermissionDenied("قرارداد متعلق به این سازمان نیست.") from exc
    if locked.status != ContractStatus.ACTIVE:
        raise ValidationError("رکورد قراردادی جدید فقط برای قرارداد فعال مجاز است.")
    if locked.party_id is None:
        raise ValidationError("قرارداد باید به طرف تجاری مرجع متصل باشد.")
    return locked


def _party_snapshot(contract: Contract):
    snapshot = contract.party.identity_snapshots.order_by("-sequence").first()
    if snapshot is None:
        raise ValidationError("طرف قرارداد تصویر هویت قابل استناد ندارد.")
    return snapshot


def get_contractual_records(
    *, actor: User, organization: Organization
) -> QuerySet[ContractualRecord]:
    membership = _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.CONTRACTUAL_RECORDS_VIEW,
        project=None,
        allow_any_scope=True,
    )
    return (
        scope_queryset(
            ContractualRecord.objects.filter(organization=organization),
            membership=membership,
            project_lookup="project_id",
        )
        .select_related(
            "project", "contract", "party_identity_snapshot__party", "supersedes"
        )
        .order_by("-created_at")
    )


@transaction.atomic
def create_contractual_record(
    *,
    organization: Organization,
    actor: User,
    contract: Contract,
    kind: str,
    record_number: str,
    title: str,
    description: str,
    idempotency_key: str,
    notice_reference: str = "",
    notice_date=None,
    requested_amount: Decimal | str | int | None = None,
    requested_eot_days: int | None = None,
    valuation_assumptions: str = "",
    cost_impact_assumptions: str = "",
    schedule_impact_assumptions: str = "",
    contract_value_impact_assumptions: str = "",
) -> ContractualRecord:
    locked_contract = _locked_contract(organization=organization, contract=contract)
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE,
        project=locked_contract.project,
    )
    if kind not in ContractualRecordKind.values:
        raise ValidationError("نوع رکورد قراردادی معتبر نیست.")
    key = idempotency_key.strip()
    if not key:
        raise ValidationError("کلید یکتای عملیات الزامی است.")
    existing = ContractualRecord.objects.filter(
        organization=organization, idempotency_key=key
    ).first()
    amount = _decimal(requested_amount)
    payload = {
        "contract_id": locked_contract.pk,
        "kind": kind,
        "record_number": record_number.strip().upper(),
        "title": title.strip(),
        "description": description.strip(),
        "requested_amount": amount,
        "requested_eot_days": requested_eot_days,
    }
    if existing:
        if any(getattr(existing, field) != value for field, value in payload.items()):
            raise ValidationError("کلید عملیات با محتوای متفاوت قبلاً استفاده شده است.")
        return existing
    record = ContractualRecord.objects.create(
        organization=organization,
        project=locked_contract.project,
        contract=locked_contract,
        party_identity_snapshot=_party_snapshot(locked_contract),
        kind=kind,
        record_number=record_number,
        title=title,
        description=description,
        notice_reference=notice_reference,
        notice_date=notice_date,
        requested_amount=amount,
        requested_eot_days=requested_eot_days,
        valuation_assumptions=valuation_assumptions,
        cost_impact_assumptions=cost_impact_assumptions,
        schedule_impact_assumptions=schedule_impact_assumptions,
        contract_value_impact_assumptions=contract_value_impact_assumptions,
        created_by=actor,
        updated_by=actor,
        idempotency_key=key,
    )
    record_audit_event(
        action=AuditAction.CONTRACTUAL_RECORD_CREATED,
        entity_type="contracts.ContractualRecord",
        entity_id=record.pk,
        organization=organization,
        actor=actor,
        metadata={"contract_id": str(record.contract_id), "kind": kind, "version": 1},
    )
    return record


@transaction.atomic
def create_contractual_revision(
    *,
    organization: Organization,
    actor: User,
    predecessor: ContractualRecord,
    revision_action: str,
    reason: str,
    idempotency_key: str,
    title: str | None = None,
    description: str | None = None,
) -> ContractualRecord:
    try:
        old = (
            ContractualRecord.objects.select_for_update(of=("self",))
            .select_related("contract__project", "party_identity_snapshot")
            .get(pk=predecessor.pk, organization=organization)
        )
    except ContractualRecord.DoesNotExist as exc:
        raise PermissionDenied("رکورد قراردادی متعلق به این سازمان نیست.") from exc
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE,
        project=old.project,
    )
    if old.status not in {
        ContractualRecordStatus.APPROVED,
        ContractualRecordStatus.RETURNED,
    }:
        raise ValidationError("فقط رکورد تأییدشده یا بازگردانده‌شده قابل بازنگری است.")
    if revision_action not in {
        ContractualRevisionAction.CORRECTION,
        ContractualRevisionAction.CANCELLATION,
    }:
        raise ValidationError("نوع بازنگری معتبر نیست.")
    if (
        revision_action == ContractualRevisionAction.CANCELLATION
        and old.status != ContractualRecordStatus.APPROVED
    ):
        raise ValidationError("ابطال فقط برای رکورد تأییدشده ثبت می‌شود.")
    if not reason.strip():
        raise ValidationError("دلیل بازنگری الزامی است.")
    existing = ContractualRecord.objects.filter(
        organization=organization, idempotency_key=idempotency_key.strip()
    ).first()
    if existing:
        if (
            existing.supersedes_id != old.pk
            or existing.revision_action != revision_action
        ):
            raise ValidationError("کلید عملیات با بازنگری دیگری استفاده شده است.")
        return existing
    record = ContractualRecord.objects.create(
        organization=organization,
        project=old.project,
        contract=old.contract,
        party_identity_snapshot=old.party_identity_snapshot,
        kind=old.kind,
        record_number=old.record_number,
        series_id=old.series_id,
        version=old.version + 1,
        revision_action=revision_action,
        supersedes=old,
        revision_reason=reason,
        title=title.strip() if title else old.title,
        description=description.strip() if description else old.description,
        notice_reference=old.notice_reference,
        notice_date=old.notice_date,
        requested_amount=Decimal(0)
        if revision_action == ContractualRevisionAction.CANCELLATION
        else old.requested_amount,
        requested_eot_days=0
        if revision_action == ContractualRevisionAction.CANCELLATION
        else old.requested_eot_days,
        valuation_assumptions=old.valuation_assumptions,
        cost_impact_assumptions=old.cost_impact_assumptions,
        schedule_impact_assumptions=old.schedule_impact_assumptions,
        contract_value_impact_assumptions=old.contract_value_impact_assumptions,
        linked_amendment=old.linked_amendment,
        created_by=actor,
        updated_by=actor,
        idempotency_key=idempotency_key.strip(),
    )
    for evidence in old.evidence_links.all():
        ContractualRecordEvidence.objects.create(
            organization=organization,
            record=record,
            label=evidence.label,
            document_version=evidence.document_version,
            project_control_item=evidence.project_control_item,
            project_change_proposal=evidence.project_change_proposal,
            schedule_revision=evidence.schedule_revision,
            progress_record=evidence.progress_record,
            payable_measurement=evidence.payable_measurement,
            linked_by=actor,
        )
    record_audit_event(
        action=AuditAction.CONTRACTUAL_RECORD_CREATED,
        entity_type="contracts.ContractualRecord",
        entity_id=record.pk,
        organization=organization,
        actor=actor,
        metadata={
            "supersedes_id": str(old.pk),
            "version": record.version,
            "action": revision_action,
        },
    )
    return record


@transaction.atomic
def add_contractual_evidence(
    *,
    organization: Organization,
    actor: User,
    record: ContractualRecord,
    label: str,
    **source: Any,
) -> ContractualRecordEvidence:
    locked = ContractualRecord.objects.select_for_update(of=("self",)).get(
        pk=record.pk, organization=organization
    )
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE,
        project=locked.project,
    )
    allowed = {
        "document_version",
        "project_control_item",
        "project_change_proposal",
        "schedule_revision",
        "progress_record",
        "payable_measurement",
    }
    link = ContractualRecordEvidence(
        organization=organization,
        record=locked,
        label=label,
        linked_by=actor,
        **{key: value for key, value in source.items() if key in allowed},
    )
    link.save()
    record_audit_event(
        action=AuditAction.CONTRACTUAL_EVIDENCE_LINKED,
        entity_type="contracts.ContractualRecordEvidence",
        entity_id=link.pk,
        organization=organization,
        actor=actor,
        metadata={"record_id": str(locked.pk), "label": link.label},
    )
    return link


def _approval_snapshot(record: ContractualRecord) -> dict[str, Any]:
    return {
        "record_id": str(record.pk),
        "series_id": str(record.series_id),
        "version": record.version,
        "kind": record.kind,
        "contract_id": str(record.contract_id),
        "project_id": str(record.project_id),
        "party_identity_snapshot_id": str(record.party_identity_snapshot_id),
        "requested_amount": str(record.requested_amount)
        if record.requested_amount is not None
        else None,
        "requested_eot_days": record.requested_eot_days,
        "evidence_ids": [
            str(value) for value in record.evidence_links.values_list("pk", flat=True)
        ],
        "effects": {
            "contract_value": "none",
            "budget": "none",
            "schedule_baseline": "none",
            "billing": "none",
            "subledger": "none",
            "accounting": "none",
            "treasury": "none",
        },
    }


@transaction.atomic
def _approve_contractual_record_domain(
    *,
    organization: Organization,
    actor: User,
    record: ContractualRecord,
    reason: str,
    entitlement_approved: bool,
    approved_amount=None,
    approved_eot_days: int | None = None,
    delay_responsibility: str = "",
) -> ContractualRecord:
    locked = ContractualRecord.objects.select_for_update(of=("self",)).get(
        pk=record.pk, organization=organization
    )
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.CONTRACTUAL_RECORDS_APPROVE,
        project=locked.project,
    )
    if locked.status != ContractualRecordStatus.SUBMITTED:
        raise ValidationError("فقط رکورد ارسال‌شده قابل تأیید است.")
    if locked.submitted_by_id == actor.pk:
        raise PermissionDenied("ارسال‌کننده نمی‌تواند رکورد خود را تأیید کند.")
    if not reason.strip() or not isinstance(entitlement_approved, bool):
        raise ValidationError("دلیل و تصمیم صریح استحقاق الزامی است.")
    amount = _decimal(approved_amount)
    locked.status = ContractualRecordStatus.APPROVED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.approval_reason = reason.strip()
    locked.entitlement_approved = entitlement_approved
    locked.approved_amount = amount
    locked.approved_eot_days = approved_eot_days
    locked.approved_delay_responsibility = delay_responsibility.strip()
    locked.updated_by = actor
    locked.save()
    if (
        locked.supersedes_id
        and locked.supersedes.status == ContractualRecordStatus.APPROVED
    ):
        predecessor = ContractualRecord.objects.select_for_update().get(
            pk=locked.supersedes_id
        )
        predecessor.status = (
            ContractualRecordStatus.CANCELLED
            if locked.revision_action == ContractualRevisionAction.CANCELLATION
            else ContractualRecordStatus.SUPERSEDED
        )
        predecessor.updated_by = actor
        predecessor.save(update_fields=["status", "updated_by", "updated_at"])
        record_audit_event(
            action=(
                AuditAction.CONTRACTUAL_RECORD_CANCELLED
                if predecessor.status == ContractualRecordStatus.CANCELLED
                else AuditAction.CONTRACTUAL_RECORD_SUPERSEDED
            ),
            entity_type="contracts.ContractualRecord",
            entity_id=predecessor.pk,
            organization=organization,
            actor=actor,
            metadata={"successor_id": str(locked.pk)},
        )
    record_audit_event(
        action=AuditAction.CONTRACTUAL_RECORD_APPROVED,
        entity_type="contracts.ContractualRecord",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "reason": locked.approval_reason,
            "entitlement_approved": entitlement_approved,
            "approved_amount": str(amount) if amount is not None else None,
            "approved_eot_days": approved_eot_days,
            "financial_effect": "none",
            "schedule_baseline_effect": "none",
            "contract_value_effect": "none",
        },
    )
    return locked


@transaction.atomic
def _return_contractual_record_domain(
    *, organization: Organization, actor: User, record: ContractualRecord, reason: str
) -> ContractualRecord:
    locked = ContractualRecord.objects.select_for_update(of=("self",)).get(
        pk=record.pk, organization=organization
    )
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.CONTRACTUAL_RECORDS_APPROVE,
        project=locked.project,
    )
    if locked.status != ContractualRecordStatus.SUBMITTED or not reason.strip():
        raise ValidationError("فقط رکورد ارسال‌شده با دلیل قابل بازگرداندن است.")
    locked.status = ContractualRecordStatus.RETURNED
    locked.returned_by = actor
    locked.returned_at = timezone.now()
    locked.return_reason = reason.strip()
    locked.updated_by = actor
    locked.save()
    record_audit_event(
        action=AuditAction.CONTRACTUAL_RECORD_RETURNED,
        entity_type="contracts.ContractualRecord",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": locked.return_reason},
    )
    return locked


@transaction.atomic
def _withdraw_contractual_record_domain(
    *, organization: Organization, actor: User, record: ContractualRecord, reason: str
) -> ContractualRecord:
    locked = ContractualRecord.objects.select_for_update(of=("self",)).get(
        pk=record.pk, organization=organization
    )
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE,
        project=locked.project,
    )
    if locked.status not in {
        ContractualRecordStatus.DRAFT,
        ContractualRecordStatus.SUBMITTED,
        ContractualRecordStatus.RETURNED,
    }:
        raise ValidationError("فقط پیش‌نویس، ارسالی یا بازگردانده‌شده قابل استرداد است.")
    if not reason.strip():
        raise ValidationError("دلیل استرداد الزامی است.")
    locked.status = ContractualRecordStatus.WITHDRAWN
    locked.withdrawn_by = actor
    locked.withdrawn_at = timezone.now()
    locked.withdrawal_reason = reason.strip()
    locked.updated_by = actor
    locked.save()
    record_audit_event(
        action=AuditAction.CONTRACTUAL_RECORD_WITHDRAWN,
        entity_type="contracts.ContractualRecord",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip()},
    )
    return locked


@transaction.atomic
def withdraw_contractual_record(
    *, organization: Organization, actor: User, record: ContractualRecord, reason: str
) -> ContractualRecord:
    try:
        locked = ContractualRecord.objects.select_for_update(of=("self",)).get(
            pk=record.pk, organization=organization
        )
    except ContractualRecord.DoesNotExist as exc:
        raise PermissionDenied("رکورد قراردادی متعلق به این سازمان نیست.") from exc
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.CONTRACTUAL_RECORDS_PREPARE,
        project=locked.project,
    )
    if locked.status == ContractualRecordStatus.SUBMITTED:
        from apps.workflows.models import WorkflowInstance, WorkflowInstanceStatus
        from apps.workflows.runtime import cancel_workflow_for_domain

        instance = (
            WorkflowInstance.objects.select_for_update()
            .filter(
                organization=organization,
                subject_type="contracts.contractual_record",
                subject_id=locked.pk,
                status=WorkflowInstanceStatus.ACTIVE,
            )
            .first()
        )
        if instance is None:
            raise ValidationError("گردش فعال رکورد ارسالی یافت نشد.")
        cancel_workflow_for_domain(
            actor=actor,
            organization=organization,
            instance_id=instance.pk,
            command_key="contracts.contractual_record.withdraw",
            reason=reason,
            idempotency_key=f"contractual-withdraw:{locked.pk}",
        )
        locked.refresh_from_db()
        return locked
    return _withdraw_contractual_record_domain(
        organization=organization, actor=actor, record=locked, reason=reason
    )


def submit_contractual_record(*, organization, actor, record):
    from .contractual_workflow import submit_contractual_record as submit

    return submit(organization=organization, actor=actor, record=record)


def decide_contractual_record(
    *, organization, actor, record, approved, reason, **facts
):
    from .contractual_workflow import decide_contractual_record as decide

    return decide(
        organization=organization,
        actor=actor,
        record=record,
        approved=approved,
        reason=reason,
        **facts,
    )
