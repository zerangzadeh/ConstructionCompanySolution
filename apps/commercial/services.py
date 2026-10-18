"""Bounded Commercial pre-award lifecycle; no procurement or contract effect."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.models import DocumentVersion
from apps.documents.services import get_organization_document
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.models import Project

from .models import (
    TENDER_BID_TRANSITIONS,
    TenderBid,
    TenderBidActivation,
    TenderBidEvidence,
    TenderBidRevision,
    TenderBidStatus,
)

TRANSITIONS = TENDER_BID_TRANSITIONS


def _active_policy(organization: Organization) -> None:
    if (
        not TenderBidActivation.objects.filter(
            organization=organization, is_active=True
        )
        .exclude(policy_reference="")
        .exists()
    ):
        raise PermissionDenied("سیاست معتبر مناقصه برای این شرکت فعال نشده است.")


def _permission(
    *,
    actor: User,
    organization: Organization,
    code: BusinessPermissionCode,
    project: Project | None,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=code,
        project=project,
        message="اجازه عملیات مناقصه را ندارید.",
    )


def list_tender_bids(*, actor: User, organization: Organization) -> QuerySet[TenderBid]:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.TENDER_BIDS_VIEW,
        allow_any_scope=True,
        message="اجازه مشاهده مناقصه‌های این شرکت را ندارید.",
    )
    queryset = TenderBid.objects.filter(organization=organization).select_related(
        "project"
    )
    return scope_queryset(queryset, membership=membership, project_lookup="project_id")


def get_tender_bid(
    *, actor: User, organization: Organization, tender_id: str
) -> TenderBid:
    try:
        return list_tender_bids(actor=actor, organization=organization).get(
            pk=tender_id
        )
    except TenderBid.DoesNotExist as exc:
        raise PermissionDenied("مناقصه مجاز یافت نشد.") from exc


def _locked(*, organization: Organization, tender_id: str) -> TenderBid:
    try:
        return TenderBid.objects.select_for_update().get(
            pk=tender_id, organization=organization
        )
    except TenderBid.DoesNotExist as exc:
        raise PermissionDenied("مناقصه مجاز یافت نشد.") from exc


def _latest(tender: TenderBid) -> TenderBidRevision:
    return tender.revisions.order_by("-version").first()


def _append(
    *,
    tender: TenderBid,
    previous: TenderBidRevision | None,
    actor: User,
    status: str,
    title: str,
    description: str,
    submission_reference: str,
    result_reference: str,
    bid_bond_reference: str,
    bid_cost_reference: str,
    reason: str,
) -> TenderBidRevision:
    revision = TenderBidRevision(
        organization=tender.organization,
        tender_bid=tender,
        version=previous.version + 1 if previous else 1,
        previous_revision=previous,
        status=status,
        title=title,
        description=description,
        submission_reference=submission_reference,
        result_reference=result_reference,
        bid_bond_reference=bid_bond_reference,
        bid_cost_reference=bid_cost_reference,
        reason=reason,
        created_by=actor,
    )
    revision.save()
    record_audit_event(
        action=AuditAction.TENDER_BID_REVISED,
        entity_type="commercial_tender_bid",
        entity_id=tender.pk,
        organization=tender.organization,
        actor=actor,
        metadata={
            "version": revision.version,
            "prior_status": previous.status if previous else None,
            "status": status,
            "reason": reason,
        },
    )
    return revision


@transaction.atomic
def create_tender_bid(
    *,
    actor: User,
    organization: Organization,
    opportunity_code: str,
    title: str,
    project: Project | None = None,
    description: str = "",
    reason: str = "ثبت اولیه",
) -> TenderBid:
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.TENDER_BIDS_PREPARE,
        project=project,
    )
    _active_policy(organization)
    if project is not None and (
        project.organization_id != organization.pk or project.deleted_at
    ):
        raise PermissionDenied("پروژه مجاز یافت نشد.")
    tender = TenderBid(
        organization=organization,
        project=project,
        opportunity_code=opportunity_code,
        created_by=actor,
    )
    try:
        tender.save()
        _append(
            tender=tender,
            previous=None,
            actor=actor,
            status=TenderBidStatus.DRAFT,
            title=title,
            description=description,
            submission_reference="",
            result_reference="",
            bid_bond_reference="",
            bid_cost_reference="",
            reason=reason,
        )
    except (ValidationError, IntegrityError) as exc:
        raise ValueError("اطلاعات فرصت مناقصه معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.TENDER_BID_CREATED,
        entity_type="commercial_tender_bid",
        entity_id=tender.pk,
        organization=organization,
        actor=actor,
        metadata={"opportunity_code": tender.opportunity_code},
    )
    return tender


@transaction.atomic
def revise_tender_bid(
    *,
    actor: User,
    organization: Organization,
    tender_id: str,
    title: str,
    description: str,
    submission_reference: str,
    result_reference: str,
    bid_bond_reference: str,
    bid_cost_reference: str,
    reason: str,
) -> TenderBidRevision:
    tender = _locked(organization=organization, tender_id=tender_id)
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.TENDER_BIDS_PREPARE,
        project=tender.project,
    )
    _active_policy(organization)
    previous = _latest(tender)
    if previous.status in {
        TenderBidStatus.WON,
        TenderBidStatus.LOST,
        TenderBidStatus.WITHDRAWN,
        TenderBidStatus.CANCELLED,
    }:
        raise ValueError("وضعیت نهایی قابل بازنگری نیست.")
    if previous.status != TenderBidStatus.DRAFT and not reason.strip():
        raise ValueError("اصلاح پس از ارسال نیازمند دلیل است.")
    return _append(
        tender=tender,
        previous=previous,
        actor=actor,
        status=previous.status,
        title=title,
        description=description,
        submission_reference=submission_reference,
        result_reference=result_reference,
        bid_bond_reference=bid_bond_reference,
        bid_cost_reference=bid_cost_reference,
        reason=reason,
    )


@transaction.atomic
def transition_tender_bid(
    *,
    actor: User,
    organization: Organization,
    tender_id: str,
    target: str,
    reason: str,
    submission_reference: str = "",
    result_reference: str = "",
) -> TenderBidRevision:
    tender = _locked(organization=organization, tender_id=tender_id)
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.TENDER_BIDS_TRANSITION,
        project=tender.project,
    )
    _active_policy(organization)
    previous = _latest(tender)
    if target not in TRANSITIONS.get(previous.status, frozenset()):
        raise ValueError("تغییر وضعیت مناقصه مجاز نیست.")
    if not reason.strip():
        raise ValueError("دلیل تغییر وضعیت الزامی است.")
    submission = submission_reference.strip() or previous.submission_reference
    result = result_reference.strip() or previous.result_reference
    if target == TenderBidStatus.SUBMITTED and not submission:
        raise ValueError("ارسال پیشنهاد نیازمند مرجع ثبت‌شده است.")
    if target in {TenderBidStatus.WON, TenderBidStatus.LOST} and not result:
        raise ValueError("نتیجه مناقصه نیازمند مرجع ثبت‌شده است.")
    return _append(
        tender=tender,
        previous=previous,
        actor=actor,
        status=target,
        title=previous.title,
        description=previous.description,
        submission_reference=submission,
        result_reference=result,
        bid_bond_reference=previous.bid_bond_reference,
        bid_cost_reference=previous.bid_cost_reference,
        reason=reason,
    )


@transaction.atomic
def link_tender_evidence(
    *,
    actor: User,
    organization: Organization,
    tender_id: str,
    document_version: DocumentVersion,
    description: str = "",
) -> TenderBidEvidence:
    tender = _locked(organization=organization, tender_id=tender_id)
    _permission(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.TENDER_BIDS_PREPARE,
        project=tender.project,
    )
    _active_policy(organization)
    if document_version.organization_id != organization.pk:
        raise PermissionDenied("نسخه سند متعلق به این شرکت نیست.")
    document = get_organization_document(
        user=actor,
        organization=organization,
        document_id=str(document_version.document_id),
    )
    if document.pk != document_version.document_id or not document_version.is_available:
        raise PermissionDenied("نسخه سند مجاز و آماده نیست.")
    previous = _latest(tender)
    if previous.status in {
        TenderBidStatus.WON,
        TenderBidStatus.LOST,
        TenderBidStatus.WITHDRAWN,
        TenderBidStatus.CANCELLED,
    }:
        raise ValueError("شاهد به وضعیت نهایی افزوده نمی‌شود.")
    revision = _append(
        tender=tender,
        previous=previous,
        actor=actor,
        status=previous.status,
        title=previous.title,
        description=previous.description,
        submission_reference=previous.submission_reference,
        result_reference=previous.result_reference,
        bid_bond_reference=previous.bid_bond_reference,
        bid_cost_reference=previous.bid_cost_reference,
        reason="پیوند شاهد نسخه سند",
    )
    evidence = TenderBidEvidence(
        organization=organization,
        revision=revision,
        document_version=document_version,
        description=description.strip(),
        created_by=actor,
    )
    evidence.save()
    record_audit_event(
        action=AuditAction.TENDER_BID_EVIDENCE_LINKED,
        entity_type="commercial_tender_bid",
        entity_id=tender.pk,
        organization=organization,
        actor=actor,
        metadata={
            "revision": revision.version,
            "document_version_id": str(document_version.pk),
        },
    )
    return evidence
