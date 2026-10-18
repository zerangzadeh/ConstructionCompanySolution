"""Separate, source-owned review of QualityIssue records (CEP-027)."""

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
from apps.quality.models import (
    QualityIssue,
    QualityReviewEvidence,
    QualityReviewRevision,
    QualityReviewStatus,
)
from apps.quality.services import _require_permission


def _locked(organization: Organization, issue_id: str) -> QualityIssue:
    try:
        return (
            QualityIssue.objects.select_for_update(of=("self",))
            .select_related("project", "site")
            .get(pk=issue_id, organization=organization)
        )
    except (QualityIssue.DoesNotExist, ValidationError) as exc:
        raise PermissionDenied("مسئله متعلق به این سازمان نیست.") from exc


def _snapshot(issue: QualityIssue) -> dict[str, str]:
    return {
        "organization_id": str(issue.organization_id),
        "created_by_id": str(issue.created_by_id),
        "issue_number": issue.issue_number,
        "project_id": str(issue.project_id),
        "site_id": str(issue.site_id) if issue.site_id else "",
        "phase_id": str(issue.phase_id) if issue.phase_id else "",
        "activity_id": str(issue.activity_id) if issue.activity_id else "",
        "daily_report_id": str(issue.daily_report_id) if issue.daily_report_id else "",
        "identified_at": issue.identified_at.isoformat(),
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "description": issue.description,
        "specification_reference": issue.specification_reference,
    }


def _valid_evidence_scope(version: DocumentVersion, issue: QualityIssue) -> bool:
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
        == issue.project_id
        and (link.target_type != "project_site" or issue.site_id == link.target.pk)
        for link in links
    )


def _transition(
    *, issue: QualityIssue, actor: User, prior: str, state: str, reason: str
) -> QualityReviewRevision:
    reason = reason.strip()
    if not reason:
        raise ValueError("دلیل بررسی رکورد الزامی است.")
    previous = issue.review_revisions.order_by("-sequence").first()
    revision = QualityReviewRevision(
        organization=issue.organization,
        issue=issue,
        sequence=previous.sequence + 1 if previous else 1,
        previous=previous,
        prior_state=prior,
        state=state,
        snapshot=_snapshot(issue),
        actor=actor,
        reason=reason,
    )
    issue.review_status = state
    issue.updated_by = actor
    issue._review_transition = True
    issue.save()
    revision.save()
    record_audit_event(
        action=AuditAction.QUALITY_ISSUE_RECORD_REVIEWED,
        entity_type="quality_issue",
        entity_id=issue.pk,
        organization=issue.organization,
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
def submit_quality_record(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    reason: str,
    document_version_ids: Sequence[str] = (),
) -> QualityReviewRevision:
    issue = _locked(organization, issue_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.QUALITY_ISSUES_RECORD_SUBMIT,
        project=issue.project,
        site=issue.site,
    )
    if issue.review_status != QualityReviewStatus.DRAFT:
        raise ValueError("فقط پیش‌نویس رکورد قابل ارسال است.")
    versions = list(
        DocumentVersion.objects.select_related("document").filter(
            organization=organization,
            pk__in=document_version_ids,
        )
    )
    if len(versions) != len(set(document_version_ids)) or any(
        not _valid_evidence_scope(v, issue) for v in versions
    ):
        raise PermissionDenied("نسخه سند معتبر و فعال در این سازمان یافت نشد.")
    if versions:
        _require_permission(
            organization=organization,
            user=actor,
            permission=BusinessPermissionCode.DOCUMENTS_VIEW,
            project=issue.project,
            site=issue.site,
        )
    revision = _transition(
        issue=issue,
        actor=actor,
        prior=issue.review_status,
        state=QualityReviewStatus.SUBMITTED,
        reason=reason,
    )
    for version in versions:
        QualityReviewEvidence.objects.create(
            organization=organization, revision=revision, document_version=version
        )
    return revision


@transaction.atomic
def decide_quality_record(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    outcome: str,
    reason: str,
) -> QualityReviewRevision:
    issue = _locked(organization, issue_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.QUALITY_ISSUES_RECORD_DECIDE,
        project=issue.project,
        site=issue.site,
    )
    if issue.review_status != QualityReviewStatus.SUBMITTED or outcome not in {
        QualityReviewStatus.APPROVED,
        QualityReviewStatus.REJECTED,
        QualityReviewStatus.RETURNED,
    }:
        raise ValueError("تصمیم بررسی رکورد برای این وضعیت معتبر نیست.")
    return _transition(
        issue=issue,
        actor=actor,
        prior=QualityReviewStatus.SUBMITTED,
        state=outcome,
        reason=reason,
    )


@transaction.atomic
def correct_returned_quality_record(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    description: str,
    specification_reference: str,
    reason: str,
) -> QualityReviewRevision:
    issue = _locked(organization, issue_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.QUALITY_ISSUES_RECORD_SUBMIT,
        project=issue.project,
        site=issue.site,
    )
    if issue.review_status != QualityReviewStatus.RETURNED or issue.status == "closed":
        raise ValueError("فقط رکورد برگشت‌خورده قابل اصلاح است.")
    prior = issue.review_status
    issue.description = description
    issue.specification_reference = specification_reference
    issue._review_correction = True
    return _transition(
        issue=issue,
        actor=actor,
        prior=prior,
        state=QualityReviewStatus.DRAFT,
        reason=reason,
    )
