"""P5-S06 sealed quote metadata services; commercial content is intentionally absent."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.procurement.models import (
    QuoteEnvelope,
    QuoteRevision,
    QuoteRevisionStatus,
    QuoteRevisionTransition,
    RequestForQuotation,
    RequestForQuotationInvitation,
    RequestForQuotationInvitationStatus,
    RequestForQuotationStatus,
)


def _quote_fingerprint(
    *,
    invitation: RequestForQuotationInvitation,
    integrity_fingerprint: str,
    source_channel: str,
    source_reference: str,
    supplier_submitted_at: datetime | None,
) -> str:
    payload = {
        "invitation": str(invitation.pk),
        "rfq_version": str(invitation.rfq_version_id),
        "integrity_fingerprint": integrity_fingerprint.lower(),
        "source_channel": source_channel.strip(),
        "source_reference": source_reference.strip(),
        "supplier_submitted_at": supplier_submitted_at.isoformat()
        if supplier_submitted_at
        else None,
    }
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _locked_invitation(
    *, organization: Organization, invitation: RequestForQuotationInvitation
) -> RequestForQuotationInvitation:
    try:
        locked = (
            RequestForQuotationInvitation.objects.select_for_update()
            .select_related("rfq_version__rfq__project", "supplier")
            .get(pk=invitation.pk, organization=organization)
        )
    except RequestForQuotationInvitation.DoesNotExist as exc:
        raise PermissionDenied("دعوت‌نامه استعلام در این سازمان یافت نشد.") from exc
    rfq = locked.rfq_version.rfq
    if rfq.project.organization_id != organization.pk or rfq.project.deleted_at:
        raise PermissionDenied("پروژه استعلام معتبر نیست.")
    return locked


def _require(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
    rfq: RequestForQuotation,
    message: str,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=rfq.project,
        message=message,
    )


def _capture_allowed(invitation: RequestForQuotationInvitation) -> None:
    rfq = invitation.rfq_version.rfq
    if rfq.status not in {
        RequestForQuotationStatus.ISSUED,
        RequestForQuotationStatus.CLOSED,
    }:
        raise ValueError("فقط استعلام صادرشده یا بسته‌شده می‌تواند پیشنهاد ثبت کند.")
    if invitation.rfq_version.version_number != rfq.current_version_number:
        raise ValueError("دعوت‌نامه باید متعلق به نسخه مؤثر استعلام باشد.")
    if invitation.status in {
        RequestForQuotationInvitationStatus.DECLINED,
        RequestForQuotationInvitationStatus.WITHDRAWN,
        RequestForQuotationInvitationStatus.EXPIRED,
    }:
        raise ValueError("دعوت‌نامه در وضعیت فعلی پیشنهاد نمی‌پذیرد.")


@transaction.atomic
def capture_quote_revision(
    *,
    organization: Organization,
    actor: User,
    invitation: RequestForQuotationInvitation,
    integrity_fingerprint: str,
    source_channel: str,
    idempotency_key: str,
    source_reference: str = "",
    supplier_submitted_at: datetime | None = None,
) -> QuoteRevision:
    """Capture only sealed receipt metadata, never prices, terms, files, or content."""

    locked_invitation = _locked_invitation(
        organization=organization, invitation=invitation
    )
    rfq = locked_invitation.rfq_version.rfq
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQ_QUOTES_CAPTURE,
        rfq=rfq,
        message="اجازه ثبت پیشنهاد مهروموم‌شده را ندارید.",
    )
    _capture_allowed(locked_invitation)
    if supplier_submitted_at and not timezone.is_aware(supplier_submitted_at):
        raise ValueError("زمان ارائه تأمین‌کننده باید دارای منطقه زمانی باشد.")
    key = idempotency_key.strip()
    if not key:
        raise ValueError("کلید یکتای ثبت پیشنهاد الزامی است.")
    source_channel = source_channel.strip()
    source_reference = source_reference.strip()
    integrity_fingerprint = integrity_fingerprint.strip().lower()
    payload_fingerprint = _quote_fingerprint(
        invitation=locked_invitation,
        integrity_fingerprint=integrity_fingerprint,
        source_channel=source_channel,
        source_reference=source_reference,
        supplier_submitted_at=supplier_submitted_at,
    )
    envelope, _ = QuoteEnvelope.objects.select_for_update().get_or_create(
        organization=organization,
        rfq=rfq,
        supplier=locked_invitation.supplier,
        defaults={"created_by": actor},
    )
    existing = QuoteRevision.objects.filter(
        envelope=envelope, idempotency_key=key
    ).first()
    if existing:
        if existing.payload_fingerprint != payload_fingerprint:
            raise ValueError("تلاش تکراری ثبت پیشنهاد با داده متفاوت رد شد.")
        return existing
    previous = (
        QuoteRevision.objects.select_for_update()
        .filter(envelope=envelope, status=QuoteRevisionStatus.SUBMITTED)
        .order_by("-revision_number")
        .first()
    )
    received_at = timezone.now()
    revision = QuoteRevision(
        organization=organization,
        envelope=envelope,
        invitation=locked_invitation,
        rfq_version=locked_invitation.rfq_version,
        revision_number=(QuoteRevision.objects.filter(envelope=envelope).count() + 1),
        source_channel=source_channel,
        source_reference=source_reference,
        supplier_submitted_at=supplier_submitted_at,
        received_at=received_at,
        captured_by=actor,
        integrity_fingerprint=integrity_fingerprint,
        payload_fingerprint=payload_fingerprint,
        idempotency_key=key,
        is_late=received_at > locked_invitation.rfq_version.closing_at,
        supersedes=previous,
    )
    try:
        revision.full_clean()
        revision.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("شواهد پیشنهاد مهروموم‌شده معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.RFQ_QUOTE_REVISION_CAPTURED,
        entity_type="quote_revision",
        entity_id=revision.pk,
        organization=organization,
        actor=actor,
        metadata={
            "rfq_id": str(rfq.pk),
            "rfq_version_id": str(revision.rfq_version_id),
            "supplier_id": str(locked_invitation.supplier_id),
            "revision_number": revision.revision_number,
            "is_late": revision.is_late,
        },
    )
    return revision


def _locked_revision(
    *, organization: Organization, revision: QuoteRevision
) -> QuoteRevision:
    try:
        return (
            QuoteRevision.objects.select_for_update()
            .select_related("envelope__rfq__project", "invitation", "rfq_version")
            .get(pk=revision.pk, organization=organization)
        )
    except QuoteRevision.DoesNotExist as exc:
        raise PermissionDenied("نسخه پیشنهاد در این سازمان یافت نشد.") from exc


@transaction.atomic
def submit_quote_revision(
    *,
    organization: Organization,
    actor: User,
    revision: QuoteRevision,
    idempotency_key: str,
) -> QuoteRevision:
    locked = _locked_revision(organization=organization, revision=revision)
    rfq = locked.envelope.rfq
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQ_QUOTES_SUBMIT,
        rfq=rfq,
        message="اجازه ثبت نهایی پیشنهاد مهروموم‌شده را ندارید.",
    )
    key = idempotency_key.strip()
    if not key:
        raise ValueError("کلید یکتای ثبت نهایی الزامی است.")
    existing = QuoteRevisionTransition.objects.filter(
        revision=locked, idempotency_key=key
    ).first()
    if existing:
        if existing.to_status != QuoteRevisionStatus.SUBMITTED:
            raise ValueError("کلید یکتای انتقال با عملیات متفاوت استفاده شده است.")
        locked.refresh_from_db()
        return locked
    if locked.status != QuoteRevisionStatus.CAPTURED:
        raise ValueError("فقط پیشنهاد ثبت‌شده قابل نهایی‌سازی است.")
    if (
        rfq.status != RequestForQuotationStatus.ISSUED
        or locked.rfq_version.version_number != rfq.current_version_number
        or locked.invitation.rfq_version_id != locked.rfq_version_id
    ):
        raise ValueError("ثبت نهایی فقط برای دعوت‌نامه نسخه مؤثر استعلام باز مجاز است.")
    if timezone.now() > locked.rfq_version.closing_at:
        raise ValueError("پس از مهلت، پیشنهاد جدید قابل نهایی‌سازی نیست.")
    QuoteEnvelope.objects.select_for_update().get(pk=locked.envelope_id)
    previous = (
        QuoteRevision.objects.select_for_update()
        .filter(
            envelope_id=locked.envelope_id,
            status=QuoteRevisionStatus.SUBMITTED,
        )
        .first()
    )
    if previous:
        if previous.revision_number >= locked.revision_number:
            raise ValueError("نسخه قدیمی‌تر نمی‌تواند نسخه نهایی فعال را جایگزین کند.")
        QuoteRevision.objects.filter(pk=previous.pk).update(
            status=QuoteRevisionStatus.SUPERSEDED
        )
        QuoteRevisionTransition.objects.create(
            organization=organization,
            revision=previous,
            from_status=QuoteRevisionStatus.SUBMITTED,
            to_status=QuoteRevisionStatus.SUPERSEDED,
            actor=actor,
            idempotency_key=f"superseded:{locked.pk}",
        )
    submitted_at = timezone.now()
    QuoteRevision.objects.filter(pk=locked.pk).update(
        status=QuoteRevisionStatus.SUBMITTED, submitted_at=submitted_at
    )
    QuoteRevisionTransition.objects.create(
        organization=organization,
        revision=locked,
        from_status=QuoteRevisionStatus.CAPTURED,
        to_status=QuoteRevisionStatus.SUBMITTED,
        actor=actor,
        idempotency_key=key,
    )
    locked.refresh_from_db()
    record_audit_event(
        action=AuditAction.RFQ_QUOTE_REVISION_SUBMITTED,
        entity_type="quote_revision",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"rfq_id": str(rfq.pk), "revision_number": locked.revision_number},
    )
    return locked


@transaction.atomic
def withdraw_quote_revision(
    *,
    organization: Organization,
    actor: User,
    revision: QuoteRevision,
    idempotency_key: str,
) -> QuoteRevision:
    locked = _locked_revision(organization=organization, revision=revision)
    rfq = locked.envelope.rfq
    _require(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQ_QUOTES_WITHDRAW,
        rfq=rfq,
        message="اجازه بازپس‌گیری پیشنهاد مهروموم‌شده را ندارید.",
    )
    key = idempotency_key.strip()
    if not key:
        raise ValueError("کلید یکتای بازپس‌گیری الزامی است.")
    existing = QuoteRevisionTransition.objects.filter(
        revision=locked, idempotency_key=key
    ).first()
    if existing:
        if existing.to_status != QuoteRevisionStatus.WITHDRAWN:
            raise ValueError("کلید یکتای انتقال با عملیات متفاوت استفاده شده است.")
        locked.refresh_from_db()
        return locked
    if locked.status not in {
        QuoteRevisionStatus.CAPTURED,
        QuoteRevisionStatus.SUBMITTED,
    }:
        raise ValueError("نسخه پیشنهاد در وضعیت فعلی قابل بازپس‌گیری نیست.")
    if (
        rfq.status != RequestForQuotationStatus.ISSUED
        or locked.rfq_version.version_number != rfq.current_version_number
    ):
        raise ValueError("بازپس‌گیری فقط برای نسخه مؤثر استعلام باز مجاز است.")
    if timezone.now() > locked.rfq_version.closing_at:
        raise ValueError("پس از مهلت، بازپس‌گیری عادی پیشنهاد مجاز نیست.")
    previous_status = locked.status
    withdrawn_at = timezone.now()
    QuoteRevision.objects.filter(pk=locked.pk).update(
        status=QuoteRevisionStatus.WITHDRAWN,
        withdrawn_at=withdrawn_at,
    )
    QuoteRevisionTransition.objects.create(
        organization=organization,
        revision=locked,
        from_status=previous_status,
        to_status=QuoteRevisionStatus.WITHDRAWN,
        actor=actor,
        idempotency_key=key,
    )
    locked.refresh_from_db()
    record_audit_event(
        action=AuditAction.RFQ_QUOTE_REVISION_WITHDRAWN,
        entity_type="quote_revision",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"rfq_id": str(rfq.pk), "revision_number": locked.revision_number},
    )
    return locked


def get_organization_quote_revisions(
    *, user: User, organization: Organization
) -> QuerySet[QuoteRevision]:
    """Return sealed metadata only; no commercial content model exists in this slice."""

    membership = require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.RFQ_QUOTES_VIEW_METADATA,
        allow_any_scope=True,
        message="اجازه مشاهده فراداده پیشنهادها را ندارید.",
    )
    return scope_queryset(
        QuoteRevision.objects.filter(
            organization=organization, envelope__rfq__project__deleted_at__isnull=True
        ),
        membership=membership,
        project_lookup="envelope__rfq__project_id",
    ).select_related("envelope__rfq", "invitation", "rfq_version", "captured_by")
