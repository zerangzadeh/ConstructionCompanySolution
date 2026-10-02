"""P5-S18–S22 invite-scoped external portal foundation (no UI or uploads)."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.procurement.models import (
    QuoteEnvelope,
    QuoteRevision,
    QuoteRevisionStatus,
    QuoteRevisionTransition,
    QuoteSourceChannel,
    RequestForQuotationInvitation,
    RequestForQuotationInvitationStatus,
    RequestForQuotationStatus,
    SupplierPortalCapability,
    SupplierPortalGrant,
    SupplierPortalGrantRevocation,
    SupplierPortalInvitation,
    SupplierPortalInvitationStatus,
    SupplierPortalPrincipal,
    SupplierPortalSubmissionReceipt,
)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _require_manage_permission(
    *,
    organization: Organization,
    actor: User,
    rfq_invitation: RequestForQuotationInvitation,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUPPLIER_PORTAL_INVITATIONS_MANAGE,
        project=rfq_invitation.rfq_version.rfq.project,
        message="اجازه مدیریت دعوت‌نامه درگاه تأمین‌کننده را ندارید.",
    )


def _validate_open_rfq_invitation(invitation: RequestForQuotationInvitation) -> None:
    rfq = invitation.rfq_version.rfq
    if (
        rfq.status != RequestForQuotationStatus.ISSUED
        or invitation.rfq_version.version_number != rfq.current_version_number
        or invitation.status
        in {
            RequestForQuotationInvitationStatus.DECLINED,
            RequestForQuotationInvitationStatus.WITHDRAWN,
            RequestForQuotationInvitationStatus.EXPIRED,
            RequestForQuotationInvitationStatus.CLOSED,
        }
    ):
        raise ValueError("فقط دعوت‌نامه فعال نسخه مؤثر استعلام باز قابل استفاده است.")


@transaction.atomic
def create_supplier_portal_invitation(
    *,
    organization: Organization,
    actor: User,
    rfq_invitation: RequestForQuotationInvitation,
    invited_email: str,
    expires_at: datetime,
) -> tuple[SupplierPortalInvitation, str]:
    """Create an exact-scope invitation and return its one-time plaintext token."""

    try:
        locked = (
            RequestForQuotationInvitation.objects.select_for_update()
            .select_related("rfq_version__rfq__project", "supplier")
            .get(pk=rfq_invitation.pk, organization=organization)
        )
    except RequestForQuotationInvitation.DoesNotExist as exc:
        raise PermissionDenied("دعوت‌نامه استعلام در این سازمان یافت نشد.") from exc
    _require_manage_permission(
        organization=organization, actor=actor, rfq_invitation=locked
    )
    _validate_open_rfq_invitation(locked)
    now = timezone.now()
    email = invited_email.strip().lower()
    if not email:
        raise ValueError("ایمیل مخاطب دعوت‌نامه الزامی است.")
    if timezone.is_naive(expires_at):
        raise ValueError("زمان انقضا باید دارای منطقه زمانی باشد.")
    if expires_at <= now or expires_at > locked.rfq_version.closing_at:
        raise ValueError("انقضای دعوت‌نامه باید بین اکنون و مهلت استعلام باشد.")
    if SupplierPortalInvitation.objects.filter(
        rfq_invitation=locked, status=SupplierPortalInvitationStatus.PENDING
    ).exists():
        raise ValueError("برای این دعوت استعلام یک دعوت‌نامه خارجی باز وجود دارد.")
    token = secrets.token_urlsafe(32)
    invitation = SupplierPortalInvitation(
        organization=organization,
        rfq_invitation=locked,
        invited_email=email,
        token_hash=_hash_token(token),
        token_prefix=token[:12],
        expires_at=expires_at,
        created_by=actor,
    )
    invitation.save()
    record_audit_event(
        action=AuditAction.SUPPLIER_PORTAL_INVITATION_CREATED,
        entity_type="supplier_portal_invitation",
        entity_id=invitation.pk,
        organization=organization,
        actor=actor,
        metadata={
            "rfq_id": str(locked.rfq_version.rfq_id),
            "rfq_invitation_id": str(locked.pk),
            "supplier_id": str(locked.supplier_id),
            "expires_at": expires_at.isoformat(),
        },
    )
    return invitation, token


@transaction.atomic
def accept_supplier_portal_invitation(
    *, actor: User, token: str
) -> SupplierPortalGrant:
    """Bind an authenticated existing user; this never creates Tenant membership."""

    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("حساب کاربری فعال الزامی است.")
    token_hash = _hash_token(token.strip())
    try:
        invitation = (
            SupplierPortalInvitation.objects.select_for_update(of=("self",))
            .select_related(
                "organization",
                "rfq_invitation__supplier",
                "rfq_invitation__rfq_version__rfq__project",
                "accepted_principal",
            )
            .get(token_hash=token_hash)
        )
    except SupplierPortalInvitation.DoesNotExist as exc:
        raise PermissionDenied("دعوت‌نامه معتبر نیست.") from exc
    if invitation.status == SupplierPortalInvitationStatus.ACCEPTED:
        if invitation.accepted_principal.user_id != actor.pk:
            raise PermissionDenied("دعوت‌نامه قبلاً به هویت دیگری متصل شده است.")
        return invitation.grants.get(
            capability=SupplierPortalCapability.RFQ_QUOTE_SUBMIT
        )
    if invitation.status != SupplierPortalInvitationStatus.PENDING:
        raise PermissionDenied("دعوت‌نامه لغو شده است.")
    now = timezone.now()
    if (
        not invitation.organization.is_active
        or now >= invitation.expires_at
        or actor.email.strip().lower() != invitation.invited_email
    ):
        raise PermissionDenied("هویت یا زمان دعوت‌نامه معتبر نیست.")
    _validate_open_rfq_invitation(invitation.rfq_invitation)
    principal, _ = SupplierPortalPrincipal.objects.get_or_create(
        organization=invitation.organization,
        supplier=invitation.rfq_invitation.supplier,
        user=actor,
    )
    updated = SupplierPortalInvitation.objects.filter(
        pk=invitation.pk, status=SupplierPortalInvitationStatus.PENDING
    ).update(
        status=SupplierPortalInvitationStatus.ACCEPTED,
        accepted_principal=principal,
        accepted_at=now,
    )
    if updated != 1:
        raise PermissionDenied("دعوت‌نامه دیگر قابل پذیرش نیست.")
    invitation.refresh_from_db()
    grant = SupplierPortalGrant(
        organization=invitation.organization,
        principal=principal,
        portal_invitation=invitation,
        rfq_invitation=invitation.rfq_invitation,
        capability=SupplierPortalCapability.RFQ_QUOTE_SUBMIT,
    )
    grant.save()
    record_audit_event(
        action=AuditAction.SUPPLIER_PORTAL_INVITATION_ACCEPTED,
        entity_type="supplier_portal_grant",
        entity_id=grant.pk,
        organization=invitation.organization,
        actor=None,
        metadata={
            "principal_id": str(principal.pk),
            "external_user_id": str(actor.pk),
            "rfq_invitation_id": str(invitation.rfq_invitation_id),
        },
    )
    return grant


def _locked_active_grant(
    *, actor: User, grant: SupplierPortalGrant
) -> SupplierPortalGrant:
    try:
        locked = (
            SupplierPortalGrant.objects.select_for_update()
            .select_related(
                "organization",
                "principal__user",
                "portal_invitation",
                "rfq_invitation__supplier",
                "rfq_invitation__rfq_version__rfq__project",
            )
            .get(pk=grant.pk)
        )
    except SupplierPortalGrant.DoesNotExist as exc:
        raise PermissionDenied("مجوز درگاه معتبر نیست.") from exc
    if (
        not actor.is_authenticated
        or not actor.is_active
        or locked.principal.user_id != actor.pk
        or not locked.organization.is_active
        or locked.capability != SupplierPortalCapability.RFQ_QUOTE_SUBMIT
        or locked.portal_invitation.status != SupplierPortalInvitationStatus.ACCEPTED
        or timezone.now() >= locked.portal_invitation.expires_at
        or SupplierPortalGrantRevocation.objects.filter(grant=locked).exists()
    ):
        raise PermissionDenied("مجوز درگاه فعال نیست.")
    _validate_open_rfq_invitation(locked.rfq_invitation)
    return locked


@transaction.atomic
def revoke_supplier_portal_grant(
    *, organization: Organization, actor: User, grant: SupplierPortalGrant, reason: str
) -> SupplierPortalGrantRevocation:
    try:
        locked = (
            SupplierPortalGrant.objects.select_for_update()
            .select_related(
                "rfq_invitation__rfq_version__rfq__project", "portal_invitation"
            )
            .get(pk=grant.pk, organization=organization)
        )
    except SupplierPortalGrant.DoesNotExist as exc:
        raise PermissionDenied("مجوز درگاه در این سازمان یافت نشد.") from exc
    _require_manage_permission(
        organization=organization, actor=actor, rfq_invitation=locked.rfq_invitation
    )
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError("دلیل لغو الزامی است.")
    existing = SupplierPortalGrantRevocation.objects.filter(grant=locked).first()
    if existing:
        return existing
    revocation = SupplierPortalGrantRevocation(
        organization=organization,
        grant=locked,
        revoked_by=actor,
        reason=normalized_reason,
    )
    revocation.save()
    SupplierPortalInvitation.objects.filter(pk=locked.portal_invitation_id).update(
        status=SupplierPortalInvitationStatus.REVOKED
    )
    record_audit_event(
        action=AuditAction.SUPPLIER_PORTAL_GRANT_REVOKED,
        entity_type="supplier_portal_grant_revocation",
        entity_id=revocation.pk,
        organization=organization,
        actor=actor,
        metadata={"grant_id": str(locked.pk), "reason": normalized_reason},
    )
    return revocation


@transaction.atomic
def get_supplier_portal_rfq_context(
    *, actor: User, grant: SupplierPortalGrant
) -> dict[str, Any]:
    """Return only invitation-visible issued RFQ facts, never internal notes or peers."""

    locked = _locked_active_grant(actor=actor, grant=grant)
    version = locked.rfq_invitation.rfq_version
    rfq = version.rfq
    lines = version.lines.select_related("unit_of_measure").order_by("sort_order", "pk")
    return {
        "organization_name": locked.organization.name,
        "supplier_name": locked.rfq_invitation.supplier.display_name,
        "project_code": rfq.project.code,
        "project_name": rfq.project.name,
        "rfq_number": rfq.rfq_number,
        "title": rfq.title,
        "terms": version.terms,
        "closing_at": version.closing_at,
        "lines": [
            {
                "line_id": str(line.pk),
                "description": line.description,
                "quantity": str(line.quantity),
                "unit": line.unit_of_measure.symbol,
            }
            for line in lines
        ],
    }


def _submission_payload_fingerprint(
    *,
    grant: SupplierPortalGrant,
    integrity_fingerprint: str,
    source_reference: str,
    supplier_submitted_at: datetime | None,
) -> str:
    payload = {
        "grant": str(grant.pk),
        "rfq_invitation": str(grant.rfq_invitation_id),
        "integrity_fingerprint": integrity_fingerprint,
        "source_reference": source_reference,
        "supplier_submitted_at": supplier_submitted_at.isoformat()
        if supplier_submitted_at
        else None,
    }
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


@transaction.atomic
def submit_supplier_portal_quote(
    *,
    actor: User,
    grant: SupplierPortalGrant,
    integrity_fingerprint: str,
    idempotency_key: str,
    source_reference: str = "",
    supplier_submitted_at: datetime | None = None,
) -> SupplierPortalSubmissionReceipt:
    """Atomically reuse the existing sealed QuoteRevision lifecycle and return a receipt."""

    locked_grant = _locked_active_grant(actor=actor, grant=grant)
    invitation = locked_grant.rfq_invitation
    rfq = invitation.rfq_version.rfq
    now = timezone.now()
    if now > invitation.rfq_version.closing_at:
        raise ValueError("پس از مهلت، پیشنهاد جدید پذیرفته نمی‌شود.")
    key = idempotency_key.strip()
    fingerprint = integrity_fingerprint.strip().lower()
    reference = source_reference.strip()
    if not key:
        raise ValueError("کلید یکتای ارسال الزامی است.")
    if supplier_submitted_at and not timezone.is_aware(supplier_submitted_at):
        raise ValueError("زمان ارسال باید دارای منطقه زمانی باشد.")
    payload_fingerprint = _submission_payload_fingerprint(
        grant=locked_grant,
        integrity_fingerprint=fingerprint,
        source_reference=reference,
        supplier_submitted_at=supplier_submitted_at,
    )
    existing = (
        SupplierPortalSubmissionReceipt.objects.filter(
            grant=locked_grant, idempotency_key=key
        )
        .select_related("quote_revision")
        .first()
    )
    if existing:
        if existing.payload_fingerprint != payload_fingerprint:
            raise ValueError("کلید یکتای ارسال با داده متفاوت استفاده شده است.")
        return existing
    envelope, _ = QuoteEnvelope.objects.select_for_update().get_or_create(
        organization=locked_grant.organization,
        rfq=rfq,
        supplier=invitation.supplier,
        defaults={"created_by": actor},
    )
    previous = (
        QuoteRevision.objects.select_for_update()
        .filter(envelope=envelope, status=QuoteRevisionStatus.SUBMITTED)
        .first()
    )
    revision = QuoteRevision(
        organization=locked_grant.organization,
        envelope=envelope,
        invitation=invitation,
        rfq_version=invitation.rfq_version,
        revision_number=QuoteRevision.objects.filter(envelope=envelope).count() + 1,
        status=QuoteRevisionStatus.CAPTURED,
        source_channel=QuoteSourceChannel.EXTERNAL_PORTAL,
        source_reference=reference,
        supplier_submitted_at=supplier_submitted_at,
        received_at=now,
        captured_by=actor,
        integrity_fingerprint=fingerprint,
        payload_fingerprint=payload_fingerprint,
        idempotency_key=f"portal:{locked_grant.pk}:{key}",
        is_late=False,
        supersedes=previous,
    )
    try:
        revision.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError("شواهد پیشنهاد خارجی معتبر نیست.") from exc
    if previous:
        QuoteRevision.objects.filter(pk=previous.pk).update(
            status=QuoteRevisionStatus.SUPERSEDED
        )
        QuoteRevisionTransition.objects.create(
            organization=locked_grant.organization,
            revision=previous,
            from_status=QuoteRevisionStatus.SUBMITTED,
            to_status=QuoteRevisionStatus.SUPERSEDED,
            actor=actor,
            idempotency_key=f"portal-superseded:{revision.pk}",
        )
    QuoteRevision.objects.filter(pk=revision.pk).update(
        status=QuoteRevisionStatus.SUBMITTED, submitted_at=now
    )
    QuoteRevisionTransition.objects.create(
        organization=locked_grant.organization,
        revision=revision,
        from_status=QuoteRevisionStatus.CAPTURED,
        to_status=QuoteRevisionStatus.SUBMITTED,
        actor=actor,
        idempotency_key=f"portal-submit:{key}",
    )
    revision.refresh_from_db()
    receipt = SupplierPortalSubmissionReceipt(
        organization=locked_grant.organization,
        grant=locked_grant,
        quote_revision=revision,
        idempotency_key=key,
        payload_fingerprint=payload_fingerprint,
    )
    receipt.save()
    record_audit_event(
        action=AuditAction.SUPPLIER_PORTAL_QUOTE_SUBMITTED,
        entity_type="supplier_portal_submission_receipt",
        entity_id=receipt.pk,
        organization=locked_grant.organization,
        actor=None,
        metadata={
            "principal_id": str(locked_grant.principal_id),
            "external_user_id": str(actor.pk),
            "rfq_id": str(rfq.pk),
            "rfq_invitation_id": str(invitation.pk),
            "quote_revision_id": str(revision.pk),
            "revision_number": revision.revision_number,
        },
    )
    return receipt
