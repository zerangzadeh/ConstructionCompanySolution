"""Separate, source-owned review of SafetyIncident records (CEP-027)."""

from collections.abc import Sequence

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.link_registry import typed_links_for_document
from apps.documents.models import DocumentRetentionClassification, DocumentVersion
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.safety.models import (
    SafetyIncident,
    SafetyReviewEvidence,
    SafetyReviewRevision,
    SafetyReviewStatus,
)
from apps.safety.services import _require_permission


def _locked(organization: Organization, incident_id: str) -> SafetyIncident:
    try:
        return (
            SafetyIncident.objects.select_for_update(of=("self",))
            .select_related("project", "site")
            .get(pk=incident_id, organization=organization)
        )
    except (SafetyIncident.DoesNotExist, ValidationError) as exc:
        raise PermissionDenied("حادثه متعلق به این سازمان نیست.") from exc


def _snapshot(incident: SafetyIncident) -> dict[str, str]:
    return {
        "organization_id": str(incident.organization_id),
        "created_by_id": str(incident.created_by_id),
        "incident_number": incident.incident_number,
        "project_id": str(incident.project_id),
        "site_id": str(incident.site_id) if incident.site_id else "",
        "phase_id": str(incident.phase_id) if incident.phase_id else "",
        "activity_id": str(incident.activity_id) if incident.activity_id else "",
        "daily_report_id": str(incident.daily_report_id)
        if incident.daily_report_id
        else "",
        "occurred_at": incident.occurred_at.isoformat(),
        "incident_type": incident.incident_type,
        "severity": incident.severity,
        "description": incident.description,
        "immediate_action": incident.immediate_action,
    }


def _valid_evidence_scope(version: DocumentVersion, incident: SafetyIncident) -> bool:
    document = version.document
    if (
        document.archived_at
        or document.retention_classification
        == DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE
        or (document.access_expires_at and document.access_expires_at <= timezone.now())
    ):
        return False
    links = typed_links_for_document(document)
    return bool(links) and all(
        (
            link.target.pk
            if link.target_type == "project"
            else getattr(link.target, "project_id", None)
        )
        == incident.project_id
        and (link.target_type != "project_site" or incident.site_id == link.target.pk)
        for link in links
    )


def _transition(
    *, incident: SafetyIncident, actor: User, prior: str, state: str, reason: str
) -> SafetyReviewRevision:
    reason = reason.strip()
    if not reason:
        raise ValueError("دلیل بررسی رکورد الزامی است.")
    previous = incident.review_revisions.order_by("-sequence").first()
    revision = SafetyReviewRevision(
        organization=incident.organization,
        incident=incident,
        sequence=previous.sequence + 1 if previous else 1,
        previous=previous,
        prior_state=prior,
        state=state,
        snapshot=_snapshot(incident),
        actor=actor,
        reason=reason,
    )
    incident.review_status = state
    incident.updated_by = actor
    incident._review_transition = True
    incident.save()
    revision.save()
    record_audit_event(
        action=AuditAction.SAFETY_INCIDENT_RECORD_REVIEWED,
        entity_type="safety_incident",
        entity_id=incident.pk,
        organization=incident.organization,
        actor=actor,
        metadata={
            "prior_state": prior,
            "state": state,
            "revision_id": str(revision.pk),
            "reason": reason,
        },
    )
    return revision


@transaction.atomic
def submit_safety_record(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    reason: str,
    document_version_ids: Sequence[str] = (),
) -> SafetyReviewRevision:
    incident = _locked(organization, incident_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_RECORD_SUBMIT,
        project=incident.project,
        site=incident.site,
    )
    if incident.review_status != SafetyReviewStatus.DRAFT:
        raise ValueError("فقط پیش‌نویس رکورد قابل ارسال است.")
    versions = list(
        DocumentVersion.objects.select_related("document").filter(
            organization=organization,
            pk__in=document_version_ids,
        )
    )
    if len(versions) != len(set(document_version_ids)) or any(
        not _valid_evidence_scope(v, incident) for v in versions
    ):
        raise PermissionDenied("نسخه سند معتبر و فعال در این سازمان یافت نشد.")
    if versions:
        _require_permission(
            organization=organization,
            user=actor,
            permission=BusinessPermissionCode.DOCUMENTS_VIEW,
            project=incident.project,
            site=incident.site,
        )
    revision = _transition(
        incident=incident,
        actor=actor,
        prior=incident.review_status,
        state=SafetyReviewStatus.SUBMITTED,
        reason=reason,
    )
    for version in versions:
        SafetyReviewEvidence.objects.create(
            organization=organization, revision=revision, document_version=version
        )
    return revision


@transaction.atomic
def decide_safety_record(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    outcome: str,
    reason: str,
) -> SafetyReviewRevision:
    incident = _locked(organization, incident_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_RECORD_DECIDE,
        project=incident.project,
        site=incident.site,
    )
    if incident.review_status != SafetyReviewStatus.SUBMITTED or outcome not in {
        SafetyReviewStatus.APPROVED,
        SafetyReviewStatus.REJECTED,
        SafetyReviewStatus.RETURNED,
    }:
        raise ValueError("تصمیم بررسی رکورد برای این وضعیت معتبر نیست.")
    return _transition(
        incident=incident,
        actor=actor,
        prior=SafetyReviewStatus.SUBMITTED,
        state=outcome,
        reason=reason,
    )


@transaction.atomic
def correct_returned_safety_record(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    description: str,
    immediate_action: str,
    reason: str,
) -> SafetyReviewRevision:
    incident = _locked(organization, incident_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_RECORD_SUBMIT,
        project=incident.project,
        site=incident.site,
    )
    if (
        incident.review_status != SafetyReviewStatus.RETURNED
        or incident.status == "closed"
    ):
        raise ValueError("فقط رکورد برگشت‌خورده قابل اصلاح است.")
    prior = incident.review_status
    incident.description = description
    incident.immediate_action = immediate_action
    incident._review_correction = True
    return _transition(
        incident=incident,
        actor=actor,
        prior=prior,
        state=SafetyReviewStatus.DRAFT,
        reason=reason,
    )
