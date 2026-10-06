"""Transactional P9-S06–S11 application services."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Model, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.compliance.models import (
    CapaAction,
    CapaStatus,
    ComplianceDownstreamProposal,
    ComplianceEvidenceLink,
    ComplianceLifecycleEvent,
    ControlProfile,
    FindingStatus,
    Inspection,
    InspectionFinding,
    InspectionStatus,
    InspectionTemplate,
    InspectionTemplateVersion,
    NcrStatus,
    Nonconformance,
    Permit,
    PermitStatus,
    QualityTest,
    TemplateStatus,
    TestResult,
    TestStatus,
)
from apps.documents.models import DocumentVersion
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.models import Project, ProjectSite

INSPECTION_TRANSITIONS = {
    InspectionStatus.DRAFT: {
        InspectionStatus.SCHEDULED,
        InspectionStatus.IN_PROGRESS,
        InspectionStatus.CANCELLED,
    },
    InspectionStatus.SCHEDULED: {
        InspectionStatus.IN_PROGRESS,
        InspectionStatus.CANCELLED,
    },
    InspectionStatus.IN_PROGRESS: {
        InspectionStatus.SUBMITTED,
        InspectionStatus.CANCELLED,
    },
    InspectionStatus.SUBMITTED: {InspectionStatus.UNDER_REVIEW},
    InspectionStatus.UNDER_REVIEW: {
        InspectionStatus.PASSED,
        InspectionStatus.CONDITIONAL,
        InspectionStatus.FAILED,
    },
    InspectionStatus.PASSED: {InspectionStatus.SUPERSEDED},
    InspectionStatus.CONDITIONAL: {InspectionStatus.SUPERSEDED},
    InspectionStatus.FAILED: {InspectionStatus.SUPERSEDED},
}
PERMIT_TRANSITIONS = {
    PermitStatus.DRAFT: {PermitStatus.SUBMITTED, PermitStatus.CANCELLED},
    PermitStatus.SUBMITTED: {PermitStatus.UNDER_REVIEW, PermitStatus.CANCELLED},
    PermitStatus.UNDER_REVIEW: {PermitStatus.ISSUED, PermitStatus.CANCELLED},
    PermitStatus.ISSUED: {
        PermitStatus.SUSPENDED,
        PermitStatus.EXPIRED,
        PermitStatus.REVOKED,
        PermitStatus.SUPERSEDED,
    },
    PermitStatus.SUSPENDED: {
        PermitStatus.ISSUED,
        PermitStatus.EXPIRED,
        PermitStatus.REVOKED,
        PermitStatus.SUPERSEDED,
    },
}
TEST_TRANSITIONS = {
    TestStatus.DRAFT: {TestStatus.REQUESTED, TestStatus.CANCELLED},
    TestStatus.REQUESTED: {
        TestStatus.SCHEDULED,
        TestStatus.IN_EXECUTION,
        TestStatus.CANCELLED,
    },
    TestStatus.SCHEDULED: {TestStatus.IN_EXECUTION, TestStatus.CANCELLED},
    TestStatus.IN_EXECUTION: {TestStatus.RESULT_ENTERED},
    TestStatus.RESULT_ENTERED: {TestStatus.UNDER_REVIEW},
    TestStatus.UNDER_REVIEW: {
        TestStatus.ACCEPTED,
        TestStatus.REJECTED,
        TestStatus.INVALIDATED,
    },
    TestStatus.ACCEPTED: {TestStatus.INVALIDATED, TestStatus.SUPERSEDED},
    TestStatus.REJECTED: {TestStatus.INVALIDATED, TestStatus.SUPERSEDED},
}
FINDING_TRANSITIONS = {
    FindingStatus.RECORDED: {FindingStatus.TRIAGED, FindingStatus.DISMISSED},
    FindingStatus.TRIAGED: {FindingStatus.ASSIGNED, FindingStatus.DISMISSED},
    FindingStatus.ASSIGNED: {FindingStatus.CORRECTION_IN_PROGRESS},
    FindingStatus.CORRECTION_IN_PROGRESS: {FindingStatus.PENDING_VERIFICATION},
    FindingStatus.PENDING_VERIFICATION: {
        FindingStatus.VERIFIED,
        FindingStatus.CORRECTION_IN_PROGRESS,
    },
    FindingStatus.VERIFIED: {FindingStatus.CLOSED, FindingStatus.ASSIGNED},
    FindingStatus.CLOSED: {FindingStatus.ASSIGNED},
}
NCR_TRANSITIONS = {
    NcrStatus.DRAFT: {NcrStatus.ISSUED, NcrStatus.VOIDED},
    NcrStatus.ISSUED: {NcrStatus.DISPOSITION_PENDING, NcrStatus.VOIDED},
    NcrStatus.DISPOSITION_PENDING: {NcrStatus.ACTION_IN_PROGRESS},
    NcrStatus.ACTION_IN_PROGRESS: {NcrStatus.PENDING_VERIFICATION},
    NcrStatus.PENDING_VERIFICATION: {NcrStatus.VERIFIED, NcrStatus.ACTION_IN_PROGRESS},
    NcrStatus.VERIFIED: {NcrStatus.CLOSED, NcrStatus.ACTION_IN_PROGRESS},
    NcrStatus.CLOSED: {NcrStatus.ACTION_IN_PROGRESS},
}
CAPA_TRANSITIONS = {
    CapaStatus.PROPOSED: {CapaStatus.APPROVED, CapaStatus.REJECTED},
    CapaStatus.APPROVED: {CapaStatus.ASSIGNED, CapaStatus.CANCELLED},
    CapaStatus.ASSIGNED: {CapaStatus.IN_PROGRESS, CapaStatus.CANCELLED},
    CapaStatus.IN_PROGRESS: {CapaStatus.PENDING_VERIFICATION},
    CapaStatus.PENDING_VERIFICATION: {CapaStatus.VERIFIED, CapaStatus.IN_PROGRESS},
    CapaStatus.VERIFIED: {CapaStatus.EFFECTIVENESS_PENDING},
    CapaStatus.EFFECTIVENESS_PENDING: {CapaStatus.EFFECTIVE, CapaStatus.INEFFECTIVE},
    CapaStatus.EFFECTIVE: {CapaStatus.CLOSED},
    CapaStatus.INEFFECTIVE: {CapaStatus.IN_PROGRESS},
    CapaStatus.CLOSED: {CapaStatus.IN_PROGRESS},
}


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _permission(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
    project: Project | None = None,
    site: ProjectSite | None = None,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        site=site,
        allow_site_parent=True,
        message="اجازه انجام این عملیات HSE/QA را ندارید.",
    )


def _audit_created(record: Model, actor: User) -> None:
    record_audit_event(
        action=AuditAction.COMPLIANCE_RECORD_CREATED,
        entity_type=record._meta.label_lower,
        entity_id=str(record.pk),
        organization=record.organization,
        actor=actor,
        metadata={"profile": getattr(record, "profile", "")},
    )


@transaction.atomic
def create_template(
    *, organization: Organization, actor: User, profile: str, code: str, title: str
) -> InspectionTemplate:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_TEMPLATES_MANAGE,
    )
    template = InspectionTemplate(
        organization=organization,
        profile=profile,
        code=code,
        title=title,
        created_by=actor,
    )
    template.full_clean()
    template.save()
    _audit_created(template, actor)
    return template


@transaction.atomic
def publish_template_version(
    *,
    organization: Organization,
    actor: User,
    template_id: str,
    checklist: list[dict[str, Any]],
    required_evidence: list[dict[str, Any]],
    outcome_rules: dict[str, Any],
    source_references: list[dict[str, Any]],
) -> InspectionTemplateVersion:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_TEMPLATES_PUBLISH,
    )
    template = InspectionTemplate.objects.select_for_update().get(
        pk=template_id, organization=organization
    )
    payload = {
        "checklist": checklist,
        "required_evidence": required_evidence,
        "outcome_rules": outcome_rules,
        "source_references": source_references,
    }
    version = InspectionTemplateVersion(
        organization=organization,
        template=template,
        version_number=(
            template.versions.order_by("-version_number")
            .values_list("version_number", flat=True)
            .first()
            or 0
        )
        + 1,
        canonical_hash=_hash(payload),
        published_by=actor,
        **payload,
    )
    version.full_clean()
    version.save()
    template.current_version = version
    template.status = TemplateStatus.PUBLISHED
    template.full_clean()
    template.save(update_fields=["current_version", "status", "updated_at"])
    record_audit_event(
        action=AuditAction.COMPLIANCE_TEMPLATE_PUBLISHED,
        entity_type="compliance.inspectiontemplate",
        entity_id=str(template.pk),
        organization=organization,
        actor=actor,
        metadata={"version": version.version_number, "hash": version.canonical_hash},
    )
    return version


@transaction.atomic
def create_inspection(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    site: ProjectSite | None,
    profile: str,
    number: str,
    template_version: InspectionTemplateVersion,
    title: str,
    inspector: User,
    scheduled_for: datetime | None = None,
    operation_key: uuid.UUID | None = None,
    replaces: Inspection | None = None,
) -> Inspection:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_INSPECTIONS_CREATE,
        project=project,
        site=site,
    )
    key = operation_key or uuid.uuid4()
    existing = Inspection.objects.filter(
        organization=organization, created_by=actor, operation_key=key
    ).first()
    if existing:
        return existing
    inspection = Inspection(
        organization=organization,
        project=project,
        site=site,
        profile=profile,
        number=number,
        template_version=template_version,
        template_snapshot_hash=template_version.canonical_hash,
        title=title,
        inspector=inspector,
        scheduled_for=scheduled_for,
        created_by=actor,
        operation_key=key,
        replaces=replaces,
    )
    inspection.full_clean()
    inspection.save()
    _audit_created(inspection, actor)
    return inspection


def scoped_inspections(
    *, organization: Organization, actor: User, profile: str | None = None
) -> QuerySet[Inspection]:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.COMPLIANCE_VIEW,
        message="اجازه مشاهده کارگاه HSE/QA را ندارید.",
    )
    queryset = Inspection.objects.filter(organization=organization).select_related(
        "project", "site", "template_version__template", "inspector"
    )
    if profile:
        queryset = queryset.filter(profile=profile)
    return scope_queryset(
        queryset,
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )


def compliance_export_rows(
    *, organization: Organization, actor: User
) -> list[dict[str, Any]]:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.COMPLIANCE_EXPORT,
        message="اجازه خروجی HSE/QA را ندارید.",
    )
    rows: list[dict[str, Any]] = []
    for model in (
        Inspection,
        Permit,
        QualityTest,
        InspectionFinding,
        Nonconformance,
        CapaAction,
    ):
        queryset = scope_queryset(
            model.objects.filter(organization=organization),
            membership=membership,
            project_lookup="project_id",
            site_lookup="site_id",
        )
        rows.extend(
            {
                "record_type": record._meta.label_lower,
                "id": str(record.pk),
                "number": getattr(record, "number", ""),
                "profile": record.profile,
                "status": record.status,
                "project_id": str(record.project_id),
                "site_id": str(record.site_id or ""),
                "updated_at": record.updated_at.isoformat(),
            }
            for record in queryset.order_by("created_at", "pk")
        )
    record_audit_event(
        action=AuditAction.COMPLIANCE_EXPORTED,
        entity_type="compliance.export",
        entity_id=str(organization.pk),
        organization=organization,
        actor=actor,
        metadata={"row_count": len(rows)},
    )
    return rows


def reconcile_compliance(
    *, organization: Organization, actor: User
) -> dict[str, Any]:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.COMPLIANCE_AUDIT_RECONCILE,
        message="اجازه تطبیق HSE/QA را ندارید.",
    )
    exceptions: list[dict[str, str]] = []
    checked = 0
    initial_statuses = {
        Inspection: InspectionStatus.DRAFT,
        Permit: PermitStatus.DRAFT,
        QualityTest: TestStatus.DRAFT,
        InspectionFinding: FindingStatus.RECORDED,
        Nonconformance: NcrStatus.DRAFT,
        CapaAction: CapaStatus.PROPOSED,
    }
    accessible_ids: set[uuid.UUID] = set()
    for model, initial_status in initial_statuses.items():
        queryset = scope_queryset(
            model.objects.filter(organization=organization),
            membership=membership,
            project_lookup="project_id",
            site_lookup="site_id",
        )
        for record in queryset.iterator():
            checked += 1
            accessible_ids.add(record.pk)
            latest = (
                ComplianceLifecycleEvent.objects.filter(
                    organization=organization,
                    entity_type=record._meta.label_lower,
                    entity_id=record.pk,
                )
                .order_by("-created_at", "-pk")
                .first()
            )
            if latest and latest.to_status != record.status:
                exceptions.append(
                    {
                        "record": f"{record._meta.label_lower}:{record.pk}",
                        "issue": "latest_event_status_mismatch",
                    }
                )
            elif latest is None and record.status != initial_status:
                exceptions.append(
                    {
                        "record": f"{record._meta.label_lower}:{record.pk}",
                        "issue": "missing_lifecycle_event",
                    }
                )
    evidence = ComplianceEvidenceLink.objects.filter(organization=organization)
    for link in evidence.select_related("document", "document_version"):
        if link.target.pk not in accessible_ids:
            continue
        checked += 1
        if (
            link.document_version.document_id != link.document_id
            or link.sha256 != link.document_version.sha256
        ):
            exceptions.append(
                {
                    "record": f"compliance.evidence:{link.pk}",
                    "issue": "document_version_integrity_mismatch",
                }
            )
    result = {"checked": checked, "exceptions": exceptions}
    record_audit_event(
        action=AuditAction.COMPLIANCE_RECONCILED,
        entity_type="compliance.reconciliation",
        entity_id=str(organization.pk),
        organization=organization,
        actor=actor,
        metadata={"checked": checked, "exception_count": len(exceptions)},
    )
    return result


def _transition_permission(record: Model, to_status: str) -> BusinessPermissionCode:
    if isinstance(record, Inspection):
        if to_status in {
            InspectionStatus.SCHEDULED,
            InspectionStatus.IN_PROGRESS,
            InspectionStatus.CANCELLED,
        }:
            return BusinessPermissionCode.COMPLIANCE_INSPECTIONS_EXECUTE
        if to_status == InspectionStatus.SUBMITTED:
            return BusinessPermissionCode.COMPLIANCE_INSPECTIONS_SUBMIT
        return BusinessPermissionCode.COMPLIANCE_INSPECTIONS_REVIEW
    if isinstance(record, Permit):
        if to_status in {PermitStatus.SUBMITTED, PermitStatus.CANCELLED}:
            return BusinessPermissionCode.COMPLIANCE_PERMITS_PREPARE
        if to_status in {PermitStatus.UNDER_REVIEW, PermitStatus.ISSUED}:
            return BusinessPermissionCode.COMPLIANCE_PERMITS_ISSUE
        return BusinessPermissionCode.COMPLIANCE_PERMITS_CONTROL
    if isinstance(record, QualityTest):
        if to_status in {TestStatus.REQUESTED, TestStatus.CANCELLED}:
            return BusinessPermissionCode.COMPLIANCE_TESTS_REQUEST
        if to_status in {
            TestStatus.SCHEDULED,
            TestStatus.IN_EXECUTION,
            TestStatus.RESULT_ENTERED,
        }:
            return BusinessPermissionCode.COMPLIANCE_TESTS_EXECUTE
        return BusinessPermissionCode.COMPLIANCE_TESTS_REVIEW
    if isinstance(record, InspectionFinding):
        if to_status == FindingStatus.TRIAGED:
            return BusinessPermissionCode.COMPLIANCE_FINDINGS_CLASSIFY
        if to_status == FindingStatus.VERIFIED:
            return BusinessPermissionCode.COMPLIANCE_VERIFY
        if to_status == FindingStatus.CLOSED:
            return BusinessPermissionCode.COMPLIANCE_CLOSE
        if (
            record.status in {FindingStatus.VERIFIED, FindingStatus.CLOSED}
            and to_status == FindingStatus.ASSIGNED
        ):
            return BusinessPermissionCode.COMPLIANCE_REOPEN
        return BusinessPermissionCode.COMPLIANCE_FINDINGS_MANAGE
    if isinstance(record, Nonconformance):
        if to_status == NcrStatus.VERIFIED:
            return BusinessPermissionCode.COMPLIANCE_VERIFY
        if to_status == NcrStatus.CLOSED:
            return BusinessPermissionCode.COMPLIANCE_CLOSE
        if (
            record.status in {NcrStatus.VERIFIED, NcrStatus.CLOSED}
            and to_status == NcrStatus.ACTION_IN_PROGRESS
        ):
            return BusinessPermissionCode.COMPLIANCE_REOPEN
        return BusinessPermissionCode.COMPLIANCE_NCR_MANAGE
    if isinstance(record, CapaAction):
        if to_status in {CapaStatus.APPROVED, CapaStatus.ASSIGNED, CapaStatus.REJECTED}:
            return BusinessPermissionCode.COMPLIANCE_CAPA_ASSIGN
        if to_status in {
            CapaStatus.IN_PROGRESS,
            CapaStatus.PENDING_VERIFICATION,
            CapaStatus.CANCELLED,
        } and record.status not in {CapaStatus.INEFFECTIVE, CapaStatus.CLOSED}:
            return BusinessPermissionCode.COMPLIANCE_CAPA_EXECUTE
        if to_status == CapaStatus.VERIFIED:
            return BusinessPermissionCode.COMPLIANCE_VERIFY
        if to_status in {
            CapaStatus.EFFECTIVENESS_PENDING,
            CapaStatus.EFFECTIVE,
            CapaStatus.INEFFECTIVE,
        }:
            return BusinessPermissionCode.COMPLIANCE_EFFECTIVENESS_REVIEW
        if to_status == CapaStatus.CLOSED:
            return BusinessPermissionCode.COMPLIANCE_CLOSE
        return BusinessPermissionCode.COMPLIANCE_REOPEN
    raise ValueError("نوع رکورد پشتیبانی نمی‌شود.")


def _transition_map(record: Model) -> dict[str, set[str]]:
    if isinstance(record, Inspection):
        return INSPECTION_TRANSITIONS
    if isinstance(record, Permit):
        return PERMIT_TRANSITIONS
    if isinstance(record, QualityTest):
        return TEST_TRANSITIONS
    if isinstance(record, InspectionFinding):
        return FINDING_TRANSITIONS
    if isinstance(record, Nonconformance):
        return NCR_TRANSITIONS
    if isinstance(record, CapaAction):
        return CAPA_TRANSITIONS
    raise ValueError("نوع رکورد پشتیبانی نمی‌شود.")


def _allowed_update_fields(record: Model, to_status: str) -> set[str]:
    if isinstance(record, Inspection):
        return {"responses"} if to_status == InspectionStatus.IN_PROGRESS else set()
    if isinstance(record, Permit):
        if to_status == PermitStatus.ISSUED:
            return {
                "rule_source",
                "rule_version",
                "issuer_name",
                "valid_from",
                "valid_until",
                "conditions",
            }
        return set()
    if isinstance(record, QualityTest):
        return {"performer_name"} if to_status == TestStatus.IN_EXECUTION else set()
    if isinstance(record, InspectionFinding):
        if to_status == FindingStatus.TRIAGED:
            return {"classification", "severity", "disposition"}
        if to_status == FindingStatus.ASSIGNED:
            return {"responsible_user_id", "due_date"}
        if to_status == FindingStatus.PENDING_VERIFICATION:
            return {"correction"}
        return set()
    if isinstance(record, Nonconformance):
        return {"disposition"} if to_status == NcrStatus.ACTION_IN_PROGRESS else set()
    if isinstance(record, CapaAction):
        if to_status == CapaStatus.ASSIGNED:
            return {"responsible_user_id", "target_date"}
        return set()
    return set()


@transaction.atomic
def transition_record(
    *,
    organization: Organization,
    actor: User,
    model: type[Model],
    record_id: str,
    to_status: str,
    reason: str,
    operation_key: uuid.UUID,
    expected_status: str,
    updates: dict[str, Any] | None = None,
) -> Model:
    payload_hash = _hash(
        {"to_status": to_status, "reason": reason, "updates": updates or {}}
    )
    entity_type = model._meta.label_lower
    previous_event = ComplianceLifecycleEvent.objects.filter(
        organization=organization,
        actor=actor,
        entity_type=entity_type,
        operation_key=operation_key,
    ).first()
    if previous_event:
        if previous_event.payload_hash != payload_hash:
            raise ValueError("کلید عملیات با محتوای متفاوت دوباره استفاده شده است.")
        return model.objects.get(pk=record_id, organization=organization)
    record = model.objects.select_for_update().get(
        pk=record_id, organization=organization
    )
    if record.status != expected_status:
        raise ValueError("وضعیت رکورد از زمان نمایش تغییر کرده است.")
    allowed = _transition_map(record).get(record.status, set())
    if to_status not in allowed:
        raise ValueError("گذار وضعیت در چرخه عمر پذیرفته‌شده مجاز نیست.")
    permission = _transition_permission(record, to_status)
    _permission(
        organization=organization,
        actor=actor,
        permission=permission,
        project=record.project,
        site=record.site,
    )
    if (
        to_status in {FindingStatus.VERIFIED, NcrStatus.VERIFIED, CapaStatus.VERIFIED}
        and getattr(record, "implemented_by_id", None) == actor.pk
    ):
        raise PermissionDenied("اجراکننده نمی‌تواند اقدام خود را راستی‌آزمایی کند.")
    if (
        isinstance(record, CapaAction)
        and to_status == CapaStatus.CLOSED
        and record.distinct_closer_required
        and record.verified_by_id == actor.pk
    ):
        raise PermissionDenied(
            "سیاست پین‌شده این اقدام، بستن توسط فردی غیر از راستی‌آزما را الزامی می‌کند."
        )
    unexpected_updates = set((updates or {}).keys()) - _allowed_update_fields(
        record, to_status
    )
    if unexpected_updates:
        raise ValueError("جزئیات ارسالی برای این گذار مجاز نیست.")
    previous_status = record.status
    for field, value in (updates or {}).items():
        setattr(record, field, value)
    now = timezone.now()
    if isinstance(record, Inspection):
        if to_status == InspectionStatus.SUBMITTED:
            record.submitted_by, record.submitted_at = actor, now
            record.canonical_hash = _hash(
                {
                    "template": record.template_snapshot_hash,
                    "responses": record.responses,
                    "scope": [str(record.project_id), str(record.site_id or "")],
                }
            )
        if to_status in {
            InspectionStatus.PASSED,
            InspectionStatus.CONDITIONAL,
            InspectionStatus.FAILED,
        }:
            record.reviewed_by, record.reviewed_at, record.review_reason = (
                actor,
                now,
                reason,
            )
    if isinstance(record, Permit) and to_status == PermitStatus.ISSUED:
        record.issued_by = actor
    if isinstance(record, QualityTest) and to_status in {
        TestStatus.ACCEPTED,
        TestStatus.REJECTED,
        TestStatus.INVALIDATED,
    }:
        result = record.results.select_for_update().order_by("-sequence").first()
        if result is None:
            raise ValueError("بررسی آزمون بدون نتیجه ثبت‌شده مجاز نیست.")
        result.reviewed_by = actor
        result.review_decision = to_status
        result.review_reason = reason
        if to_status == TestStatus.INVALIDATED:
            result.invalidated_at = now
            result.invalidation_reason = reason
        result.save()
    if isinstance(record, InspectionFinding):
        if to_status == FindingStatus.PENDING_VERIFICATION:
            record.implemented_by = actor
        elif to_status == FindingStatus.VERIFIED:
            record.verified_by = actor
        elif to_status == FindingStatus.CLOSED:
            record.closed_by = actor
    if isinstance(record, Nonconformance):
        if to_status == NcrStatus.ISSUED:
            record.issued_by = actor
        elif to_status == NcrStatus.PENDING_VERIFICATION:
            record.implemented_by = actor
        elif to_status == NcrStatus.VERIFIED:
            record.verified_by = actor
        elif to_status == NcrStatus.CLOSED:
            record.closed_by = actor
    if isinstance(record, CapaAction):
        if to_status == CapaStatus.APPROVED:
            record.approved_by = actor
        elif to_status == CapaStatus.PENDING_VERIFICATION:
            record.implemented_by = actor
        elif to_status == CapaStatus.VERIFIED:
            record.verified_by = actor
        elif to_status in {CapaStatus.EFFECTIVE, CapaStatus.INEFFECTIVE}:
            record.effectiveness_reviewed_by = actor
        elif to_status == CapaStatus.CLOSED:
            record.closed_by = actor
    record.status = to_status
    record._service_transition = True
    try:
        record.full_clean()
        record.save()
    finally:
        del record._service_transition
    ComplianceLifecycleEvent.objects.create(
        organization=organization,
        entity_type=entity_type,
        entity_id=record.pk,
        profile=record.profile,
        from_status=previous_status,
        to_status=to_status,
        reason=reason,
        actor=actor,
        operation_key=operation_key,
        payload_hash=payload_hash,
    )
    record_audit_event(
        action=AuditAction.COMPLIANCE_TRANSITIONED,
        entity_type=entity_type,
        entity_id=str(record.pk),
        organization=organization,
        actor=actor,
        changes={"status": {"from": previous_status, "to": to_status}},
        metadata={"reason": reason, "operation_key": str(operation_key)},
    )
    return record


@transaction.atomic
def create_finding(
    *,
    organization: Organization,
    actor: User,
    inspection: Inspection | None,
    source_test: QualityTest | None,
    number: str,
    title: str,
    description: str,
) -> InspectionFinding:
    source = inspection or source_test
    if source is None:
        raise ValueError("منبع یافته الزامی است.")
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_FINDINGS_CREATE,
        project=source.project,
        site=source.site,
    )
    finding = InspectionFinding(
        organization=organization,
        project=source.project,
        site=source.site,
        profile=source.profile,
        inspection=inspection,
        source_test=source_test,
        number=number,
        title=title,
        description=description,
        created_by=actor,
    )
    finding.full_clean()
    finding.save()
    _audit_created(finding, actor)
    return finding


@transaction.atomic
def promote_finding_to_ncr(
    *,
    organization: Organization,
    actor: User,
    finding_id: str,
    number: str,
    description: str,
) -> Nonconformance:
    finding = InspectionFinding.objects.select_for_update().get(
        pk=finding_id, organization=organization
    )
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_NCR_MANAGE,
        project=finding.project,
        site=finding.site,
    )
    if finding.profile != ControlProfile.QA_QC or finding.status not in {
        FindingStatus.TRIAGED,
        FindingStatus.ASSIGNED,
    }:
        raise ValueError("فقط یافته طبقه‌بندی‌شده QA/QC به NCR تبدیل می‌شود.")
    ncr = Nonconformance(
        organization=organization,
        project=finding.project,
        site=finding.site,
        profile=ControlProfile.QA_QC,
        number=number,
        finding=finding,
        description=description,
    )
    ncr.full_clean()
    ncr.save()
    _audit_created(ncr, actor)
    return ncr


@transaction.atomic
def create_permit(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    site: ProjectSite | None,
    number: str,
    permit_type: str,
    rule_source: str,
    rule_version: str,
    issuer_name: str,
    scope_description: str,
    valid_from: datetime | None,
    valid_until: datetime | None,
) -> Permit:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_PERMITS_PREPARE,
        project=project,
        site=site,
    )
    permit = Permit(
        organization=organization,
        project=project,
        site=site,
        profile=ControlProfile.HSE,
        number=number,
        permit_type=permit_type,
        rule_source=rule_source,
        rule_version=rule_version,
        issuer_name=issuer_name,
        scope_description=scope_description,
        valid_from=valid_from,
        valid_until=valid_until,
        created_by=actor,
    )
    permit.full_clean()
    permit.save()
    _audit_created(permit, actor)
    return permit


@transaction.atomic
def create_test(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    site: ProjectSite | None,
    number: str,
    title: str,
    method_reference: str,
    method_version: str,
    acceptance_criteria: dict[str, Any],
    specimen_id: str = "",
    replaces: QualityTest | None = None,
) -> QualityTest:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_TESTS_REQUEST,
        project=project,
        site=site,
    )
    test = QualityTest(
        organization=organization,
        project=project,
        site=site,
        profile=ControlProfile.QA_QC,
        number=number,
        title=title,
        method_reference=method_reference,
        method_version=method_version,
        acceptance_criteria=acceptance_criteria,
        specimen_id=specimen_id,
        requested_by=actor,
        replaces=replaces,
    )
    test.full_clean()
    test.save()
    _audit_created(test, actor)
    return test


@transaction.atomic
def enter_test_result(
    *,
    organization: Organization,
    actor: User,
    test_id: str,
    values: dict[str, Any],
    units: dict[str, Any],
    operation_key: uuid.UUID | None = None,
) -> TestResult:
    test = QualityTest.objects.select_for_update().get(
        pk=test_id, organization=organization
    )
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_TESTS_EXECUTE,
        project=test.project,
        site=test.site,
    )
    if test.status != TestStatus.IN_EXECUTION:
        raise ValueError("نتیجه فقط برای آزمون در حال اجرا ثبت می‌شود.")
    result = TestResult(
        organization=organization,
        test=test,
        sequence=(
            test.results.order_by("-sequence")
            .values_list("sequence", flat=True)
            .first()
            or 0
        )
        + 1,
        values=values,
        units=units,
        criteria_snapshot=test.acceptance_criteria,
        result_hash=_hash(
            {"values": values, "units": units, "criteria": test.acceptance_criteria}
        ),
        entered_by=actor,
    )
    result.full_clean()
    result.save()
    previous_status = test.status
    test.status = TestStatus.RESULT_ENTERED
    test._service_transition = True
    try:
        test.save(update_fields=["status", "updated_at"])
    finally:
        del test._service_transition
    transition_key = operation_key or uuid.uuid4()
    ComplianceLifecycleEvent.objects.create(
        organization=organization,
        entity_type=test._meta.label_lower,
        entity_id=test.pk,
        profile=test.profile,
        from_status=previous_status,
        to_status=TestStatus.RESULT_ENTERED,
        reason="نتیجه آزمون ثبت شد.",
        actor=actor,
        operation_key=transition_key,
        payload_hash=result.result_hash,
    )
    record_audit_event(
        action=AuditAction.COMPLIANCE_TRANSITIONED,
        entity_type=test._meta.label_lower,
        entity_id=str(test.pk),
        organization=organization,
        actor=actor,
        changes={"status": {"from": previous_status, "to": TestStatus.RESULT_ENTERED}},
        metadata={"result_id": str(result.pk), "operation_key": str(transition_key)},
    )
    _audit_created(result, actor)
    return result


@transaction.atomic
def create_capa(
    *,
    organization: Organization,
    actor: User,
    source: InspectionFinding | Nonconformance,
    number: str,
    action_type: str,
    problem_or_risk: str,
    cause_or_rationale: str,
    implementation_plan: str,
    verification_criteria: str,
    effectiveness_criteria: str,
    target_date: Any,
    distinct_closer_required: bool = False,
) -> CapaAction:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_CAPA_ASSIGN,
        project=source.project,
        site=source.site,
    )
    capa = CapaAction(
        organization=organization,
        project=source.project,
        site=source.site,
        profile=source.profile,
        number=number,
        action_type=action_type,
        finding=source if isinstance(source, InspectionFinding) else None,
        nonconformance=source if isinstance(source, Nonconformance) else None,
        problem_or_risk=problem_or_risk,
        cause_or_rationale=cause_or_rationale,
        implementation_plan=implementation_plan,
        verification_criteria=verification_criteria,
        effectiveness_criteria=effectiveness_criteria,
        target_date=target_date,
        distinct_closer_required=distinct_closer_required,
    )
    capa.full_clean()
    capa.save()
    _audit_created(capa, actor)
    return capa


@transaction.atomic
def link_evidence(
    *,
    organization: Organization,
    actor: User,
    document_version: DocumentVersion,
    purpose: str,
    operation_key: uuid.UUID,
    **subject: Model,
) -> ComplianceEvidenceLink:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_EVIDENCE_LINK,
    )
    existing = ComplianceEvidenceLink.objects.filter(
        organization=organization, created_by=actor, operation_key=operation_key
    ).first()
    if existing:
        if existing.document_version_id != document_version.pk:
            raise ValueError("کلید پیوند شواهد با نسخه متفاوت استفاده شده است.")
        return existing
    link = ComplianceEvidenceLink(
        organization=organization,
        document=document_version.document,
        document_version=document_version,
        sha256=document_version.sha256,
        purpose=purpose,
        created_by=actor,
        operation_key=operation_key,
        **subject,
    )
    link.full_clean()
    link.save()
    record_audit_event(
        action=AuditAction.COMPLIANCE_EVIDENCE_LINKED,
        entity_type="compliance.evidence",
        entity_id=str(link.pk),
        organization=organization,
        actor=actor,
        metadata={"document_version": str(document_version.pk), "purpose": purpose},
    )
    return link


@transaction.atomic
def create_downstream_proposal(
    *,
    organization: Organization,
    actor: User,
    source: Model,
    target_domain: str,
    proposal_payload: dict[str, Any],
    operation_key: uuid.UUID,
) -> ComplianceDownstreamProposal:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.COMPLIANCE_AUDIT_RECONCILE,
        project=source.project,
        site=source.site,
    )
    if target_domain not in {
        "projects",
        "project_cost",
        "inventory",
        "equipment",
        "contracts",
        "procurement",
    }:
        raise ValueError("دامنه مقصد پیشنهاد ثبت‌شده نیست.")
    proposal = ComplianceDownstreamProposal(
        organization=organization,
        project=source.project,
        site=source.site,
        profile=source.profile,
        source_type=source._meta.label_lower,
        source_id=source.pk,
        source_hash=_hash({"source": str(source.pk), "status": source.status}),
        target_domain=target_domain,
        proposal_payload=proposal_payload,
        created_by=actor,
        operation_key=operation_key,
    )
    proposal.full_clean()
    try:
        proposal.save()
    except IntegrityError:
        return ComplianceDownstreamProposal.objects.get(
            organization=organization, created_by=actor, operation_key=operation_key
        )
    record_audit_event(
        action=AuditAction.COMPLIANCE_PROPOSAL_CREATED,
        entity_type="compliance.downstream_proposal",
        entity_id=str(proposal.pk),
        organization=organization,
        actor=actor,
        metadata={"target_domain": target_domain, "source_type": proposal.source_type},
    )
    return proposal
