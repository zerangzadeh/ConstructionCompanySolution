"""Transactional P9 support coordination commands; never mutate source domains."""

from __future__ import annotations

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.models import DocumentConfidentiality, DocumentVersion
from apps.organizations.authorization import (
    has_business_permission,
    require_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    OrganizationMembership,
)
from apps.support.models import (
    Notification,
    SupportAccessRequest,
    SupportCase,
    SupportCaseEvent,
    SupportEvidence,
)


def _tenant(record, organization):
    if record.organization_id != organization.pk:
        raise PermissionDenied("Tenant scope denied.")


def _allow(organization, actor, permission):
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="مجوز لازم برای این عملیات پشتیبانی وجود ندارد.",
    )


def _audit(action, item, actor):
    record_audit_event(
        action=action,
        entity_type=item._meta.label_lower,
        entity_id=str(item.pk),
        organization=item.organization,
        actor=actor,
    )


_NOTIFICATION_SOURCES = {
    "support_case": (SupportCase, BusinessPermissionCode.SUPPORT_CASE_VIEW),
}


def _notification_source_is_available(*, organization, actor, source_type, source_id):
    try:
        model, permission = _NOTIFICATION_SOURCES[source_type]
    except KeyError:
        return False
    return (
        has_business_permission(
            user=actor,
            organization=organization,
            permission=permission,
        )
        and model.objects.filter(organization=organization, pk=source_id).exists()
    )


@transaction.atomic
def create_notification(
    *,
    organization,
    actor,
    recipient,
    source_type,
    source_id,
    source_version,
    category,
    summary,
    operation_key=None,
):
    _allow(organization, actor, BusinessPermissionCode.SUPPORT_NOTIFICATIONS_VIEW)
    if recipient is None or not summary.strip():
        raise ValidationError("Recipient and safe summary are required.")
    if not OrganizationMembership.objects.filter(
        organization=organization,
        user=recipient,
        status=MembershipStatus.ACTIVE,
    ).exists():
        raise PermissionDenied("Notification recipient must be an active member.")
    if not _notification_source_is_available(
        organization=organization,
        actor=recipient,
        source_type=source_type,
        source_id=source_id,
    ):
        raise PermissionDenied("Notification source is unavailable to the recipient.")
    key = operation_key or uuid.uuid4()
    safe_summary = summary.strip()[:240]
    operation_item = (
        Notification.objects.select_for_update()
        .filter(
            organization=organization,
            recipient=recipient,
            operation_key=key,
        )
        .first()
    )
    if operation_item is not None:
        if (
            operation_item.source_type != source_type
            or operation_item.source_id != source_id
            or operation_item.source_version != str(source_version)
            or operation_item.category != category
            or operation_item.summary != safe_summary
        ):
            raise ValidationError(
                "Operation key was already used with different notification data."
            )
        return operation_item
    item, created = Notification.objects.get_or_create(
        organization=organization,
        recipient=recipient,
        source_type=source_type,
        source_id=source_id,
        source_version=str(source_version),
        category=category,
        defaults={"summary": safe_summary, "operation_key": key},
    )
    if not created and item.summary != safe_summary:
        raise ValidationError(
            "Notification lineage already exists with different data."
        )
    if created:
        _audit(AuditAction.SUPPORT_NOTIFICATION_CREATED, item, actor)
    return item


def list_notifications(*, organization, actor):
    """Return recipient-scoped notifications with source access rechecked at read time."""
    _allow(organization, actor, BusinessPermissionCode.SUPPORT_NOTIFICATIONS_VIEW)
    items = list(
        Notification.objects.filter(
            organization=organization, recipient=actor
        ).order_by("-created_at")
    )
    for item in items:
        item.source_available = _notification_source_is_available(
            organization=organization,
            actor=actor,
            source_type=item.source_type,
            source_id=item.source_id,
        )
        item.display_summary = (
            item.summary if item.source_available else "منبع اعلان دیگر در دسترس نیست."
        )
        item.source_url = (
            reverse("support:case_detail", args=[item.source_id])
            if item.source_available and item.source_type == "support_case"
            else ""
        )
    return items


@transaction.atomic
def acknowledge_notification(*, organization, actor, notification_id):
    _allow(
        organization, actor, BusinessPermissionCode.SUPPORT_NOTIFICATIONS_ACKNOWLEDGE
    )
    item = Notification.objects.select_for_update().get(pk=notification_id)
    _tenant(item, organization)
    if item.recipient_id != actor.pk:
        raise PermissionDenied("Only recipient may acknowledge.")
    if not item.read_at:
        item.read_at = timezone.now()
        item.status = "read"
        item.save(update_fields=["read_at", "status"])
    _audit(AuditAction.SUPPORT_NOTIFICATION_ACKNOWLEDGED, item, actor)
    return item


@transaction.atomic
def create_case(
    *, organization, requester, category, summary, priority="normal", operation_key=None
):
    _allow(organization, requester, BusinessPermissionCode.SUPPORT_CASE_CREATE)
    item = SupportCase.objects.create(
        organization=organization,
        requester=requester,
        category=category,
        summary=summary[:240],
        priority=priority,
        operation_key=operation_key or uuid.uuid4(),
    )
    _audit(AuditAction.SUPPORT_CASE_CREATED, item, requester)
    return item


@transaction.atomic
def transition_case(
    *,
    organization,
    actor,
    case_id,
    expected_status,
    to_status,
    comment="",
    operation_key=None,
):
    _allow(
        organization,
        actor,
        BusinessPermissionCode.SUPPORT_CASE_REOPEN
        if to_status == "open"
        else BusinessPermissionCode.SUPPORT_CASE_RESOLVE
        if to_status in {"resolved", "closed"}
        else BusinessPermissionCode.SUPPORT_CASE_UPDATE,
    )
    case = SupportCase.objects.select_for_update().get(pk=case_id)
    _tenant(case, organization)
    key = operation_key or uuid.uuid4()
    existing_event = SupportCaseEvent.objects.filter(
        organization=organization, actor=actor, operation_key=key
    ).first()
    if existing_event is not None:
        if (
            existing_event.case_id != case.pk
            or existing_event.from_status != expected_status
            or existing_event.to_status != to_status
            or existing_event.comment != comment
        ):
            raise ValidationError("Operation key was already used for another action.")
        return case
    if case.status != expected_status:
        raise ValidationError("Stale case state.")
    allowed = {
        "open": {"triaged"},
        "triaged": {"in_progress", "closed"},
        "in_progress": {"resolved", "awaiting_requester"},
        "awaiting_requester": {"in_progress", "resolved"},
        "resolved": {"closed", "open"},
        "closed": {"open"},
    }
    if to_status not in allowed.get(case.status, set()):
        raise ValidationError("Invalid support transition.")
    before = case.status
    case.status = to_status
    if to_status == "resolved":
        case.resolution = comment
    case.save(update_fields=["status", "resolution"])
    SupportCaseEvent.objects.create(
        organization=organization,
        case=case,
        actor=actor,
        from_status=before,
        to_status=to_status,
        comment=comment,
        operation_key=key,
    )
    _audit(AuditAction.SUPPORT_CASE_TRANSITIONED, case, actor)
    return case


@transaction.atomic
def assign_case(*, organization, actor, case_id, assignee, expected_status):
    _allow(organization, actor, BusinessPermissionCode.SUPPORT_CASE_ASSIGN)
    case = SupportCase.objects.select_for_update().get(pk=case_id)
    _tenant(case, organization)
    assignee_is_active_member = OrganizationMembership.objects.filter(
        organization=organization,
        user=assignee,
        status=MembershipStatus.ACTIVE,
    ).exists()
    if (
        case.status != expected_status
        or not assignee.is_active
        or not assignee_is_active_member
    ):
        raise ValidationError("تخصیص با وضعیت فعلی سازگار نیست.")
    case.assignee = assignee
    case.save(update_fields=["assignee"])
    _audit(AuditAction.SUPPORT_CASE_ASSIGNED, case, actor)
    return case


@transaction.atomic
def request_access(
    *, organization, actor, purpose, scope, expires_at, operation_key=None
):
    _allow(organization, actor, BusinessPermissionCode.SUPPORT_ACCESS_REQUEST)
    if expires_at <= timezone.now():
        raise ValidationError("Expiry must be future.")
    item = SupportAccessRequest.objects.create(
        organization=organization,
        requested_by=actor,
        purpose=purpose,
        scope=scope,
        expires_at=expires_at,
        operation_key=operation_key or uuid.uuid4(),
    )
    _audit(AuditAction.SUPPORT_ACCESS_REQUESTED, item, actor)
    return item


@transaction.atomic
def confirm_access(*, organization, actor, request_id, platform=False):
    _allow(
        organization,
        actor,
        BusinessPermissionCode.SUPPORT_ACCESS_PLATFORM_APPROVE
        if platform
        else BusinessPermissionCode.SUPPORT_ACCESS_TENANT_CONFIRM,
    )
    item = SupportAccessRequest.objects.select_for_update().get(pk=request_id)
    _tenant(item, organization)
    if actor.pk == item.requested_by_id:
        raise PermissionDenied("Self grant denied.")
    if item.expires_at <= timezone.now():
        raise ValidationError("Support access request has expired.")
    if platform:
        if item.status != "tenant_confirmed" or not item.tenant_confirmed_by_id:
            raise ValidationError("Tenant confirmation required.")
        if actor.pk == item.tenant_confirmed_by_id:
            raise PermissionDenied("Platform approval must be independent.")
        item.platform_approved_by = actor
        item.status = "active"
    else:
        if item.status != "requested":
            raise ValidationError("Stale support access state.")
        item.tenant_confirmed_by = actor
        item.status = "tenant_confirmed"
    item.save()
    _audit(
        AuditAction.SUPPORT_ACCESS_APPROVED
        if platform
        else AuditAction.SUPPORT_ACCESS_CONFIRMED,
        item,
        actor,
    )
    return item


@transaction.atomic
def validate_access(*, organization, actor, request_id, purpose, scope):
    _allow(organization, actor, BusinessPermissionCode.SUPPORT_ACCESS_USE)
    item = SupportAccessRequest.objects.select_for_update().get(pk=request_id)
    _tenant(item, organization)
    if (
        item.requested_by_id != actor.pk
        or item.status != "active"
        or item.expires_at <= timezone.now()
        or item.purpose != purpose
        or item.scope != scope
    ):
        raise PermissionDenied("Support access is not active for this use.")
    _audit(AuditAction.SUPPORT_ACCESS_USED, item, actor)
    return item


@transaction.atomic
def revoke_access(*, organization, actor, request_id):
    _allow(organization, actor, BusinessPermissionCode.SUPPORT_ACCESS_REVOKE)
    item = SupportAccessRequest.objects.select_for_update().get(pk=request_id)
    _tenant(item, organization)
    if item.status == "revoked":
        return item
    item.status = "revoked"
    item.revoked_by = actor
    item.save(update_fields=["status", "revoked_by"])
    _audit(AuditAction.SUPPORT_ACCESS_REVOKED, item, actor)
    return item


@transaction.atomic
def link_evidence(*, organization, actor, case_id, document_version: DocumentVersion):
    _allow(organization, actor, BusinessPermissionCode.SUPPORT_EVIDENCE_LINK)
    case = SupportCase.objects.select_for_update().get(pk=case_id)
    _tenant(case, organization)
    if document_version.organization_id != organization.pk:
        raise PermissionDenied("Document tenant scope denied.")
    if document_version.document.confidentiality != DocumentConfidentiality.INTERNAL:
        _allow(
            organization,
            actor,
            BusinessPermissionCode.SUPPORT_EVIDENCE_SENSITIVE_VIEW,
        )
    item, _ = SupportEvidence.objects.get_or_create(
        organization=organization,
        case=case,
        document=document_version.document,
        document_version=document_version,
        defaults={"sha256": document_version.sha256, "created_by": actor},
    )
    _audit(AuditAction.SUPPORT_EVIDENCE_LINKED, item, actor)
    return item


def calendar_projection(*, organization, actor):
    """Read-derived entries only; SupportCase creation is the authoritative case date."""
    _allow(organization, actor, BusinessPermissionCode.SUPPORT_CALENDAR_VIEW)
    return [
        {
            "source_type": "support_case",
            "source_id": item.pk,
            "status": item.status,
            "date": item.created_at,
            "summary": item.summary,
        }
        for item in SupportCase.objects.filter(
            organization=organization, requester=actor
        ).order_by("-created_at")
    ]
