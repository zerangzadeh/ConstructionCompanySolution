from __future__ import annotations

from dataclasses import dataclass
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
    require_business_permission,
)
from apps.organizations.models import (
    SUPPORTED_BASE_CURRENCY,
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
    OrganizationSettings,
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
    ComplianceEvidenceStatus,
    ContractComplianceEvidence,
    ContractGuarantee,
    ContractorComplianceAssessment,
    EvidenceExpiryKind,
    GuaranteeStatus,
    RetentionRelease,
    RetentionReleaseStatus,
    StatutoryRecordStatus,
    TaxpayerInvoice,
)
from .workflow import _active_membership_id, _key, _write_configuration


@dataclass(frozen=True, slots=True)
class CommercialWorkflowSpec:
    model: type
    workflow_type: str
    subject_type: str
    template_code: str
    definition_code: str
    label: str
    view_permission: BusinessPermissionCode
    submit_permission: BusinessPermissionCode
    approve_permission: BusinessPermissionCode
    draft_status: str
    submitted_status: str
    submitted_action: AuditAction
    entity_type: str


GUARANTEE_SPEC = CommercialWorkflowSpec(
    model=ContractGuarantee,
    workflow_type="billing.guarantee_approval",
    subject_type="billing.contract_guarantee",
    template_code="guarantee_approval_p6_s21_s25",
    definition_code="guarantee-approval-p6-s21-s25",
    label="ضمانت‌نامه",
    view_permission=BusinessPermissionCode.GUARANTEES_VIEW,
    submit_permission=BusinessPermissionCode.GUARANTEES_SUBMIT,
    approve_permission=BusinessPermissionCode.GUARANTEES_APPROVE,
    draft_status=GuaranteeStatus.DRAFT,
    submitted_status=GuaranteeStatus.SUBMITTED,
    submitted_action=AuditAction.GUARANTEE_SUBMITTED,
    entity_type="billing.ContractGuarantee",
)
COMPLIANCE_SPEC = CommercialWorkflowSpec(
    model=ContractComplianceEvidence,
    workflow_type="billing.compliance_evidence_approval",
    subject_type="billing.contract_compliance_evidence",
    template_code="compliance_evidence_approval_p6_s21_s25",
    definition_code="compliance-evidence-approval-p6-s21-s25",
    label="شاهد بیمه/مفاصاحساب",
    view_permission=BusinessPermissionCode.COMPLIANCE_EVIDENCE_VIEW,
    submit_permission=BusinessPermissionCode.COMPLIANCE_EVIDENCE_SUBMIT,
    approve_permission=BusinessPermissionCode.COMPLIANCE_EVIDENCE_APPROVE,
    draft_status=ComplianceEvidenceStatus.DRAFT,
    submitted_status=ComplianceEvidenceStatus.SUBMITTED,
    submitted_action=AuditAction.COMPLIANCE_EVIDENCE_SUBMITTED,
    entity_type="billing.ContractComplianceEvidence",
)
RELEASE_SPEC = CommercialWorkflowSpec(
    model=RetentionRelease,
    workflow_type="billing.retention_release_approval",
    subject_type="billing.retention_release",
    template_code="retention_release_approval_p6_s21_s25",
    definition_code="retention-release-approval-p6-s21-s25",
    label="آزادسازی کسور تضمین",
    view_permission=BusinessPermissionCode.RETENTION_RELEASES_VIEW,
    submit_permission=BusinessPermissionCode.RETENTION_RELEASES_SUBMIT,
    approve_permission=BusinessPermissionCode.RETENTION_RELEASES_APPROVE,
    draft_status=RetentionReleaseStatus.DRAFT,
    submitted_status=RetentionReleaseStatus.SUBMITTED,
    submitted_action=AuditAction.RETENTION_RELEASE_SUBMITTED,
    entity_type="billing.RetentionRelease",
)
TAXPAYER_INVOICE_SPEC = CommercialWorkflowSpec(
    model=TaxpayerInvoice,
    workflow_type="billing.taxpayer_invoice_approval",
    subject_type="billing.taxpayer_invoice",
    template_code="taxpayer_invoice_approval_p6_s26_s32",
    definition_code="taxpayer-invoice-approval-p6-s26-s32",
    label="صورتحساب مؤدیان",
    view_permission=BusinessPermissionCode.TAXPAYER_INVOICES_VIEW,
    submit_permission=BusinessPermissionCode.TAXPAYER_INVOICES_SUBMIT,
    approve_permission=BusinessPermissionCode.TAXPAYER_INVOICES_APPROVE,
    draft_status=StatutoryRecordStatus.DRAFT,
    submitted_status=StatutoryRecordStatus.SUBMITTED,
    submitted_action=AuditAction.TAXPAYER_INVOICE_SUBMITTED,
    entity_type="billing.TaxpayerInvoice",
)
CONTRACTOR_COMPLIANCE_SPEC = CommercialWorkflowSpec(
    model=ContractorComplianceAssessment,
    workflow_type="billing.contractor_compliance_approval",
    subject_type="billing.contractor_compliance_assessment",
    template_code="contractor_compliance_approval_p6_s26_s32",
    definition_code="contractor-compliance-approval-p6-s26-s32",
    label="ارزیابی انطباق بیمه پیمانکار",
    view_permission=BusinessPermissionCode.CONTRACTOR_COMPLIANCE_VIEW,
    submit_permission=BusinessPermissionCode.CONTRACTOR_COMPLIANCE_SUBMIT,
    approve_permission=BusinessPermissionCode.CONTRACTOR_COMPLIANCE_APPROVE,
    draft_status=StatutoryRecordStatus.DRAFT,
    submitted_status=StatutoryRecordStatus.SUBMITTED,
    submitted_action=AuditAction.CONTRACTOR_COMPLIANCE_SUBMITTED,
    entity_type="billing.ContractorComplianceAssessment",
)
SPECS = (
    GUARANTEE_SPEC,
    COMPLIANCE_SPEC,
    RELEASE_SPEC,
    TAXPAYER_INVOICE_SPEC,
    CONTRACTOR_COMPLIANCE_SPEC,
)


def _spec_for(record: object) -> CommercialWorkflowSpec:
    for spec in SPECS:
        if isinstance(record, spec.model):
            return spec
    raise TypeError("نوع رکورد کنترل قراردادی پشتیبانی نمی‌شود.")


def _configuration(spec: CommercialWorkflowSpec) -> dict[str, Any]:
    permission = str(spec.approve_permission)
    return {
        "steps": [
            {"key": "start", "name": "شروع", "step_type": "start", "is_start": True},
            {
                "key": "approval",
                "name": f"تأیید {spec.label}",
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
                "domain_command": f"{spec.subject_type}.approve",
                "required_permission": permission,
            },
            {
                "source": "approval",
                "target": "returned",
                "outcome": "returned",
                "domain_command": f"{spec.subject_type}.return",
                "required_permission": permission,
            },
        ],
    }


def _load_subject(
    *,
    spec: CommercialWorkflowSpec,
    organization: Organization,
    subject_id: UUID,
    actor: User,
    for_update: bool,
) -> SubjectSnapshot:
    queryset = spec.model.objects.select_related("project", "contract")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        record = queryset.get(pk=subject_id, organization=organization)
    except spec.model.DoesNotExist as exc:
        raise PermissionDenied(f"{spec.label} در این سازمان یافت نشد.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=spec.view_permission,
        project=record.project,
        message=f"اجازه مشاهده {spec.label} را ندارید.",
    )
    if (
        record.project.organization_id != organization.pk
        or record.contract.organization_id != organization.pk
        or record.contract.project_id != record.project_id
    ):
        raise PermissionDenied("دامنه رکورد کنترل قراردادی معتبر نیست.")
    return SubjectSnapshot(
        subject=record,
        subject_id=str(record.pk),
        organization_id=str(organization.pk),
        attributes={
            "project_id": str(record.project_id),
            "contract_id": str(record.contract_id),
            "status": record.status,
            "created_by_id": str(record.created_by_id),
            "submitted_by_id": str(record.submitted_by_id)
            if record.submitted_by_id
            else None,
        },
        creator_membership_id=_active_membership_id(organization, record.created_by_id),
        submitter_membership_id=_active_membership_id(
            organization, record.submitted_by_id or record.created_by_id
        ),
        display=f"{record.contract.contract_number} — {spec.label}",
    )


def load_guarantee_subject(**kwargs) -> SubjectSnapshot:
    return _load_subject(spec=GUARANTEE_SPEC, **kwargs)


def load_compliance_subject(**kwargs) -> SubjectSnapshot:
    return _load_subject(spec=COMPLIANCE_SPEC, **kwargs)


def load_release_subject(**kwargs) -> SubjectSnapshot:
    return _load_subject(spec=RELEASE_SPEC, **kwargs)


def load_taxpayer_invoice_subject(**kwargs) -> SubjectSnapshot:
    return _load_subject(spec=TAXPAYER_INVOICE_SPEC, **kwargs)


def load_contractor_compliance_subject(**kwargs) -> SubjectSnapshot:
    return _load_subject(spec=CONTRACTOR_COMPLIANCE_SPEC, **kwargs)


def _command(
    *,
    spec: CommercialWorkflowSpec,
    approved: bool,
    subject,
    actor,
    organization,
    context,
    **_,
):
    from .commercial_services import (
        _approve_compliance_domain,
        _approve_guarantee_domain,
        _approve_retention_release_domain,
        _return_compliance_domain,
        _return_guarantee_domain,
        _return_retention_release_domain,
    )
    from .statutory_services import (
        _approve_contractor_domain,
        _approve_taxpayer_invoice_domain,
        _return_contractor_domain,
        _return_taxpayer_invoice_domain,
    )

    reason = context.get("reason", "")
    if not isinstance(reason, str):
        raise ValidationError("دلیل تصمیم معتبر نیست.")
    handlers = {
        (GUARANTEE_SPEC.subject_type, True): _approve_guarantee_domain,
        (GUARANTEE_SPEC.subject_type, False): _return_guarantee_domain,
        (COMPLIANCE_SPEC.subject_type, True): _approve_compliance_domain,
        (COMPLIANCE_SPEC.subject_type, False): _return_compliance_domain,
        (RELEASE_SPEC.subject_type, True): _approve_retention_release_domain,
        (RELEASE_SPEC.subject_type, False): _return_retention_release_domain,
        (TAXPAYER_INVOICE_SPEC.subject_type, True): _approve_taxpayer_invoice_domain,
        (TAXPAYER_INVOICE_SPEC.subject_type, False): _return_taxpayer_invoice_domain,
        (CONTRACTOR_COMPLIANCE_SPEC.subject_type, True): _approve_contractor_domain,
        (CONTRACTOR_COMPLIANCE_SPEC.subject_type, False): _return_contractor_domain,
    }
    keyword = {
        GUARANTEE_SPEC.subject_type: "guarantee",
        COMPLIANCE_SPEC.subject_type: "evidence",
        RELEASE_SPEC.subject_type: "release",
        TAXPAYER_INVOICE_SPEC.subject_type: "invoice",
        CONTRACTOR_COMPLIANCE_SPEC.subject_type: "assessment",
    }[spec.subject_type]
    return handlers[(spec.subject_type, approved)](
        organization=organization,
        actor=actor,
        reason=reason,
        **{keyword: subject},
    )


def register_commercial_control_workflows() -> None:
    loaders = {
        GUARANTEE_SPEC.subject_type: load_guarantee_subject,
        COMPLIANCE_SPEC.subject_type: load_compliance_subject,
        RELEASE_SPEC.subject_type: load_release_subject,
        TAXPAYER_INVOICE_SPEC.subject_type: load_taxpayer_invoice_subject,
        CONTRACTOR_COMPLIANCE_SPEC.subject_type: load_contractor_compliance_subject,
    }
    for spec in SPECS:
        registry.bind_subject_loader(spec.subject_type, loaders[spec.subject_type])
        registry.bind_domain_command(
            f"{spec.subject_type}.approve",
            lambda spec=spec, **kwargs: _command(spec=spec, approved=True, **kwargs),
        )
        registry.bind_domain_command(
            f"{spec.subject_type}.return",
            lambda spec=spec, **kwargs: _command(spec=spec, approved=False, **kwargs),
        )


@transaction.atomic
def _ensure_workflow(
    *, organization: Organization, actor: User, spec: CommercialWorkflowSpec
) -> WorkflowVersion:
    get_active_membership(user=actor, organization=organization)
    locked_org = Organization.objects.select_for_update(of=("self",)).get(
        pk=organization.pk
    )
    workflow_type = WorkflowType.objects.get(code=spec.workflow_type, is_active=True)
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
        code=spec.template_code,
        defaults={
            "name": f"تأیید {spec.label} P6-S21–S25",
            "description": "مسیر پایه با جداسازی قطعی تهیه‌کننده و تأییدکننده.",
            "is_active": True,
            "configuration": _configuration(spec),
        },
    )
    if not template.is_active:
        raise ValidationError(f"الگوی گردش {spec.label} غیرفعال است.")
    definition, created = WorkflowDefinition.objects.get_or_create(
        organization=locked_org,
        workflow_type=workflow_type,
        scope_key=scope_key,
        defaults={
            "code": spec.definition_code,
            "name": f"تأیید {spec.label}",
            "description": "گردش تأیید با جداسازی تهیه‌کننده و تأییدکننده.",
            "scope": {},
            "created_by": actor,
            "updated_by": actor,
        },
    )
    if not created:
        raise ValidationError(f"تعریف {spec.label} نسخه منتشرشده ندارد.")
    version = WorkflowVersion.objects.create(
        organization=locked_org,
        definition=definition,
        version_number=1,
        change_summary=f"P6-S21-S25 {spec.subject_type} starter workflow",
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
            metadata={"workflow_type": spec.workflow_type, "starter": True},
        )
    version.refresh_from_db()
    return version


def _resolve_version(
    *, organization: Organization, record: object, spec: CommercialWorkflowSpec
) -> WorkflowVersion:
    context = {
        "project_id": str(record.project_id),
        "contract_id": str(record.contract_id),
    }
    matches = [
        (len(version.definition.scope), version)
        for version in WorkflowVersion.objects.select_related("definition").filter(
            organization=organization,
            definition__workflow_type__code=spec.workflow_type,
            status=WorkflowVersionStatus.PUBLISHED,
        )
        if all(
            context.get(key) == value for key, value in version.definition.scope.items()
        )
    ]
    if not matches:
        raise ValidationError(f"نسخه منتشرشده گردش {spec.label} یافت نشد.")
    score = max(value for value, _ in matches)
    selected = [version for value, version in matches if value == score]
    if len(selected) != 1:
        raise ValidationError(f"انتخاب نسخه گردش {spec.label} مبهم است.")
    return selected[0]


def _snapshot(record: object, spec: CommercialWorkflowSpec) -> dict[str, Any]:
    values = {
        "id": str(record.pk),
        "project_id": str(record.project_id),
        "contract_id": str(record.contract_id),
        "party_identity_snapshot_id": str(record.party_identity_snapshot_id),
        "status": record.status,
    }
    if isinstance(record, ContractGuarantee):
        values.update(
            series_id=str(record.series_id),
            version=record.version,
            revision_action=record.revision_action,
            guarantee_type=record.guarantee_type,
            exposure_side=record.exposure_side,
            instrument_reference=record.instrument_reference,
            amount=str(record.amount),
            currency_code=record.currency_code,
            effective_from=record.effective_from.isoformat(),
            expires_on=record.expires_on.isoformat() if record.expires_on else None,
            evidence_document_version_id=str(record.evidence_document_version_id),
        )
    elif isinstance(record, ContractComplianceEvidence):
        values.update(
            series_id=str(record.series_id),
            version=record.version,
            revision_action=record.revision_action,
            evidence_kind=record.evidence_kind,
            reference=record.reference,
            effective_from=record.effective_from.isoformat(),
            expires_on=record.expires_on.isoformat() if record.expires_on else None,
            document_version_id=str(record.document_version_id),
        )
    elif isinstance(record, RetentionRelease):
        values.update(
            release_number=record.release_number,
            revision_number=record.revision_number,
            correction_kind=record.correction_kind,
            amount=str(record.amount),
            currency_code=record.currency_code,
            release_date=record.release_date.isoformat(),
            contract_term_version_id=str(record.contract_term_version_id),
            evidence_document_version_id=str(record.evidence_document_version_id),
            clearance_evidence_id=(
                str(record.clearance_evidence_id)
                if record.clearance_evidence_id
                else None
            ),
            calculation=record.calculation_snapshot,
        )
    elif isinstance(record, TaxpayerInvoice):
        values.update(
            series_id=str(record.series_id),
            version=record.version,
            record_kind=record.record_kind,
            source_claim_id=str(record.source_claim_id),
            policy_version_id=str(record.policy_version_id),
            schema_identifier=record.schema_identifier,
            tax_code=record.tax_code,
            payload=record.payload_snapshot,
            preflight=record.preflight_snapshot,
        )
    else:
        values.update(
            source_certificate_id=str(record.source_certificate_id),
            policy_version_id=str(record.policy_version_id),
            period_start=record.period_start.isoformat(),
            period_end=record.period_end.isoformat(),
            deduction_amount=str(record.deduction_amount),
            clearance_evidence_id=(
                str(record.clearance_evidence_id)
                if record.clearance_evidence_id
                else None
            ),
            calculation=record.calculation_snapshot,
        )
    return {spec.subject_type: values}


@transaction.atomic
def submit_commercial_record(
    *, organization: Organization, actor: User, record: object
) -> WorkflowInstance:
    spec = _spec_for(record)
    try:
        locked = (
            spec.model.objects.select_for_update(of=("self",))
            .select_related("project", "contract")
            .get(pk=record.pk, organization=organization)
        )
    except spec.model.DoesNotExist as exc:
        raise PermissionDenied(f"{spec.label} متعلق به این سازمان نیست.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=spec.submit_permission,
        project=locked.project,
        message=f"اجازه ارسال {spec.label} را ندارید.",
    )
    if locked.status == spec.submitted_status:
        existing = WorkflowInstance.objects.filter(
            organization=organization,
            subject_type=spec.subject_type,
            subject_id=locked.pk,
            status=WorkflowInstanceStatus.ACTIVE,
        ).first()
        if existing:
            return existing
    if locked.status != spec.draft_status:
        raise ValidationError(f"فقط {spec.label} پیش‌نویس قابل ارسال است.")
    if (
        hasattr(locked, "expiry_kind")
        and locked.expiry_kind == EvidenceExpiryKind.DATED
    ):
        settings, _ = OrganizationSettings.objects.get_or_create(
            organization=organization, defaults={"currency": SUPPORTED_BASE_CURRENCY}
        )
        if locked.expires_on < timezone.localdate(timezone=ZoneInfo(settings.timezone)):
            raise ValidationError(f"{spec.label} منقضی قابل ارسال نیست.")
    locked.submitted_by = actor
    locked.updated_by = actor
    locked.save(update_fields=["submitted_by", "updated_by", "updated_at"])
    _ensure_workflow(organization=organization, actor=actor, spec=spec)
    version = _resolve_version(organization=organization, record=locked, spec=spec)
    instance = start_workflow(
        actor=actor,
        organization=organization,
        version_id=version.pk,
        subject_id=locked.pk,
        idempotency_key=_key(spec.workflow_type, locked.pk, "submit"),
    )
    if (
        instance.status != WorkflowInstanceStatus.ACTIVE
        or not instance.work_items.filter(
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED)
        ).exists()
    ):
        raise WorkflowConflict(f"ارسال {spec.label} بدون کار فعال قابل ثبت نیست.")
    locked.submitted_at = timezone.now()
    locked.submission_snapshot = _snapshot(locked, spec)
    locked.status = spec.submitted_status
    locked.save(
        update_fields=["status", "submitted_at", "submission_snapshot", "updated_at"]
    )
    record_audit_event(
        action=spec.submitted_action,
        entity_type=spec.entity_type,
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"workflow_instance_id": str(instance.pk)},
    )
    return instance


def _actor_item(
    *,
    organization: Organization,
    record: object,
    membership: OrganizationMembership,
    spec: CommercialWorkflowSpec,
) -> WorkItem:
    item = (
        WorkItem.objects.select_related("instance", "current_assignee")
        .filter(
            organization=organization,
            instance__subject_type=spec.subject_type,
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
        raise PermissionDenied(f"کار فعال و نامزدی معتبر برای {spec.label} وجود ندارد.")
    return item


@transaction.atomic
def decide_commercial_record(
    *,
    organization: Organization,
    actor: User,
    record: object,
    approved: bool,
    reason: str,
):
    spec = _spec_for(record)
    if not reason.strip():
        raise ValidationError(f"دلیل تصمیم {spec.label} الزامی است.")
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=spec.approve_permission,
        project=record.project,
        message=f"اجازه تصمیم‌گیری {spec.label} را ندارید.",
    ) or get_active_membership(user=actor, organization=organization)
    try:
        locked = spec.model.objects.select_for_update(of=("self",)).get(
            pk=record.pk, organization=organization
        )
    except spec.model.DoesNotExist as exc:
        raise PermissionDenied(f"{spec.label} متعلق به این سازمان نیست.") from exc
    if locked.status != spec.submitted_status:
        raise ValidationError(f"فقط {spec.label} ارسالی قابل تصمیم‌گیری است.")
    item = _actor_item(
        organization=organization, record=locked, membership=membership, spec=spec
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
        outcome="approved" if approved else "returned",
        idempotency_key=_key(
            item.pk, membership.pk, "approved" if approved else "returned"
        ),
        command_context={"reason": reason.strip()},
    )
    locked.refresh_from_db()
    return locked
