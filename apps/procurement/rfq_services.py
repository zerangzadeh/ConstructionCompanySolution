"""Bounded P5-S05 internal RFQ services; this module never handles quote content."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission, scope_queryset
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
)
from apps.parties.models import BusinessParty, PartyRoleType
from apps.projects.models import Project
from core.identifiers import canonicalize_upper_identifier

from .models import (
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseRequestStatus,
    QuoteEnvelope,
    QuoteRevision,
    QuoteRevisionStatus,
    RequestForQuotation,
    RequestForQuotationInvitation,
    RequestForQuotationInvitationStatus,
    RequestForQuotationLine,
    RequestForQuotationStatus,
    RequestForQuotationVersion,
    RequestForQuotationVersionLine,
    RFQCloseEntryDisposition,
    RFQCloseManifest,
    RFQCloseManifestEntry,
)


def _permission(
    *,
    organization: Organization,
    actor: User,
    permission: BusinessPermissionCode,
    project: Project,
    message: str,
) -> OrganizationMembership:
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        message=message,
    )


def _locked_rfq(
    *, organization: Organization, rfq: RequestForQuotation
) -> RequestForQuotation:
    try:
        locked = (
            RequestForQuotation.objects.select_for_update()
            .select_related("project", "purchase_request")
            .get(pk=rfq.pk, organization=organization)
        )
    except RequestForQuotation.DoesNotExist as exc:
        raise PermissionDenied("استعلام در این سازمان یافت نشد.") from exc
    if (
        locked.project.organization_id != organization.pk
        or locked.project.deleted_at is not None
    ):
        raise PermissionDenied("پروژه استعلام معتبر نیست.")
    return locked


def _supplier(*, organization: Organization, supplier: BusinessParty) -> None:
    if supplier.organization_id != organization.pk or supplier.archived_at is not None:
        raise PermissionDenied("تأمین‌کننده متعلق به این سازمان نیست.")
    if not supplier.roles.filter(
        organization=organization, role=PartyRoleType.SUPPLIER, is_active=True
    ).exists():
        raise ValueError("طرف تجاری باید نقش فعال تأمین‌کننده داشته باشد.")


def _fingerprint(
    rfq: RequestForQuotation,
    lines: list[RequestForQuotationLine],
    suppliers: list[BusinessParty],
) -> str:
    payload = {
        "rfq": str(rfq.pk),
        "terms": rfq.terms,
        "closing_at": rfq.closing_at.isoformat(),
        "earliest_opening_at": rfq.earliest_opening_at.isoformat(),
        "lines": [
            (
                str(x.purchase_request_item_id),
                str(x.quantity),
                x.description,
                x.sort_order,
            )
            for x in lines
        ],
        "suppliers": sorted(str(x.pk) for x in suppliers),
    }
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _close_fingerprint(
    *,
    rfq: RequestForQuotation,
    version: RequestForQuotationVersion,
    invitations: list[RequestForQuotationInvitation],
    envelopes: list[QuoteEnvelope],
    revisions: list[QuoteRevision],
) -> str:
    """Fingerprint only the locked metadata snapshot; never quote content."""

    payload = {
        "rfq": str(rfq.pk),
        "effective_version": str(version.pk),
        "version_number": version.version_number,
        "closing_at": version.closing_at.isoformat(),
        "invitations": [
            {
                "id": str(invitation.pk),
                "supplier": str(invitation.supplier_id),
                "status": invitation.status,
            }
            for invitation in invitations
        ],
        "envelopes": [
            {
                "id": str(envelope.pk),
                "supplier": str(envelope.supplier_id),
            }
            for envelope in envelopes
        ],
        "revisions": [
            {
                "id": str(revision.pk),
                "envelope": str(revision.envelope_id),
                "invitation": str(revision.invitation_id),
                "rfq_version": str(revision.rfq_version_id),
                "revision_number": revision.revision_number,
                "status": revision.status,
                "received_at": revision.received_at.isoformat(),
                "submitted_at": revision.submitted_at.isoformat()
                if revision.submitted_at
                else None,
                "withdrawn_at": revision.withdrawn_at.isoformat()
                if revision.withdrawn_at
                else None,
                "is_late": revision.is_late,
                "supersedes": str(revision.supersedes_id)
                if revision.supersedes_id
                else None,
            }
            for revision in revisions
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _is_effective_revision(
    *,
    revision: QuoteRevision,
    invitation: RequestForQuotationInvitation,
    version: RequestForQuotationVersion,
) -> bool:
    return (
        revision.invitation_id == invitation.pk
        and revision.rfq_version_id == version.pk
        and revision.status == QuoteRevisionStatus.SUBMITTED
        and not revision.is_late
        and revision.received_at <= version.closing_at
        and revision.submitted_at is not None
        and revision.submitted_at <= version.closing_at
        and revision.withdrawn_at is None
    )


@transaction.atomic
def create_rfq(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    purchase_request: PurchaseRequest,
    rfq_number: str,
    title: str,
    closing_at: datetime,
    earliest_opening_at: datetime,
    terms: str = "",
) -> RequestForQuotation:
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQS_CREATE,
        project=project,
        message="اجازه ایجاد استعلام را ندارید.",
    )
    if (
        project.organization_id != organization.pk
        or project.deleted_at is not None
        or purchase_request.organization_id != organization.pk
        or purchase_request.project_id != project.pk
    ):
        raise PermissionDenied("پروژه یا درخواست خرید متعلق به سازمان/پروژه نیست.")
    if purchase_request.status != PurchaseRequestStatus.APPROVED:
        raise ValueError("فقط درخواست خرید تأییدشده می‌تواند مبنای استعلام باشد.")
    if not timezone.is_aware(closing_at) or not timezone.is_aware(earliest_opening_at):
        raise ValueError("مهلت‌ها باید دارای منطقه زمانی باشند.")
    if earliest_opening_at < closing_at:
        raise ValueError("گشایش مجاز نمی‌تواند پیش از مهلت باشد.")
    rfq = RequestForQuotation(
        organization=organization,
        project=project,
        purchase_request=purchase_request,
        rfq_number=canonicalize_upper_identifier(rfq_number),
        title=title.strip(),
        terms=terms.strip(),
        closing_at=closing_at,
        earliest_opening_at=earliest_opening_at,
        created_by=actor,
        updated_by=actor,
    )
    try:
        rfq.full_clean()
        rfq.save()
    except (ValidationError, IntegrityError) as exc:
        raise ValueError("اطلاعات استعلام معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.RFQ_CREATED,
        entity_type="rfq",
        entity_id=rfq.pk,
        organization=organization,
        actor=actor,
        metadata={
            "rfq_number": rfq.rfq_number,
            "project_id": str(project.pk),
            "purchase_request_id": str(purchase_request.pk),
        },
    )
    return rfq


@transaction.atomic
def add_rfq_line(
    *,
    organization: Organization,
    actor: User,
    rfq: RequestForQuotation,
    purchase_request_item: PurchaseRequestItem,
    quantity: Decimal,
    description: str = "",
    sort_order: int = 0,
) -> RequestForQuotationLine:
    locked = _locked_rfq(organization=organization, rfq=rfq)
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQS_CHANGE,
        project=locked.project,
        message="اجازه ویرایش استعلام را ندارید.",
    )
    if locked.status != RequestForQuotationStatus.DRAFT:
        raise ValueError("فقط ردیف‌های استعلام پیش‌نویس قابل تغییر هستند.")
    if (
        purchase_request_item.organization_id != organization.pk
        or purchase_request_item.purchase_request_id != locked.purchase_request_id
    ):
        raise PermissionDenied("ردیف درخواست خرید متعلق به استعلام نیست.")
    if quantity <= 0 or quantity > purchase_request_item.quantity:
        raise ValueError("مقدار استعلام باید مثبت و حداکثر مقدار درخواست باشد.")
    line = RequestForQuotationLine(
        organization=organization,
        rfq=locked,
        purchase_request_item=purchase_request_item,
        material=purchase_request_item.material,
        unit_of_measure=purchase_request_item.unit_of_measure,
        quantity=quantity,
        description=description.strip() or purchase_request_item.description,
        sort_order=sort_order,
    )
    try:
        line.full_clean()
        line.save()
    except (ValidationError, IntegrityError) as exc:
        raise ValueError("ردیف استعلام معتبر نیست.") from exc
    record_audit_event(
        action=AuditAction.RFQ_LINE_ADDED,
        entity_type="rfq_line",
        entity_id=line.pk,
        organization=organization,
        actor=actor,
        metadata={
            "rfq_id": str(locked.pk),
            "purchase_request_item_id": str(purchase_request_item.pk),
            "quantity": str(quantity),
        },
    )
    return line


@transaction.atomic
def submit_rfq_for_issue(
    *, organization: Organization, actor: User, rfq: RequestForQuotation
) -> RequestForQuotation:
    locked = _locked_rfq(organization=organization, rfq=rfq)
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQS_SUBMIT,
        project=locked.project,
        message="اجازه ارسال استعلام برای صدور را ندارید.",
    )
    if locked.status != RequestForQuotationStatus.DRAFT:
        raise ValueError("فقط استعلام پیش‌نویس قابل ارسال است.")
    if not locked.lines.exists():
        raise ValueError("استعلام باید حداقل یک ردیف داشته باشد.")
    locked.status = RequestForQuotationStatus.SUBMITTED_FOR_ISSUE
    locked.submitted_at = timezone.now()
    locked.updated_by = actor
    locked.save(update_fields=["status", "submitted_at", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.RFQ_SUBMITTED,
        entity_type="rfq",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={},
    )
    return locked


@transaction.atomic
def issue_rfq(
    *,
    organization: Organization,
    actor: User,
    rfq: RequestForQuotation,
    suppliers: list[BusinessParty],
    idempotency_key: str,
) -> RequestForQuotationVersion:
    locked = _locked_rfq(organization=organization, rfq=rfq)
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQS_ISSUE,
        project=locked.project,
        message="اجازه صدور استعلام را ندارید.",
    )
    key = idempotency_key.strip()
    if not key:
        raise ValueError("کلید یکتای صدور الزامی است.")
    lines = list(
        locked.lines.select_for_update()
        .select_related("purchase_request_item", "material", "unit_of_measure")
        .order_by("sort_order", "created_at")
    )
    if not lines or not suppliers:
        raise ValueError("صدور استعلام به ردیف و حداقل یک تأمین‌کننده نیاز دارد.")
    if len({x.pk for x in suppliers}) != len(suppliers):
        raise ValueError("تأمین‌کننده تکراری مجاز نیست.")
    for supplier in suppliers:
        _supplier(organization=organization, supplier=supplier)
    fingerprint = _fingerprint(locked, lines, suppliers)
    existing = RequestForQuotationVersion.objects.filter(
        rfq=locked, idempotency_key=key
    ).first()
    if existing:
        if existing.payload_fingerprint != fingerprint:
            raise ValueError("تلاش تکراری صدور با داده متفاوت رد شد.")
        return existing
    if locked.status != RequestForQuotationStatus.SUBMITTED_FOR_ISSUE:
        raise ValueError("فقط استعلام ارسال‌شده برای صدور قابل صدور است.")
    now = timezone.now()
    version = RequestForQuotationVersion(
        organization=organization,
        rfq=locked,
        version_number=locked.current_version_number + 1,
        issued_at=now,
        issued_by=actor,
        terms=locked.terms,
        closing_at=locked.closing_at,
        earliest_opening_at=locked.earliest_opening_at,
        idempotency_key=key,
        payload_fingerprint=fingerprint,
    )
    try:
        version.full_clean()
        version.save()
    except IntegrityError as exc:
        raise ValueError(
            "صدور هم‌زمان استعلام رد شد؛ با همان کلید دوباره تلاش کنید."
        ) from exc
    RequestForQuotationVersionLine.objects.bulk_create(
        [
            RequestForQuotationVersionLine(
                organization=organization,
                rfq_version=version,
                purchase_request_item=x.purchase_request_item,
                material=x.material,
                unit_of_measure=x.unit_of_measure,
                description=x.description,
                quantity=x.quantity,
                sort_order=x.sort_order,
            )
            for x in lines
        ]
    )
    RequestForQuotationInvitation.objects.bulk_create(
        [
            RequestForQuotationInvitation(
                organization=organization,
                rfq_version=version,
                supplier=x,
                created_by=actor,
                updated_by=actor,
            )
            for x in suppliers
        ]
    )
    locked.status = RequestForQuotationStatus.ISSUED
    locked.current_version_number = version.version_number
    locked.issued_at = now
    locked.issued_by = actor
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "current_version_number",
            "issued_at",
            "issued_by",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.RFQ_ISSUED,
        entity_type="rfq",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "version_id": str(version.pk),
            "version_number": version.version_number,
            "invitation_count": len(suppliers),
            "idempotency_key": key,
        },
    )
    return version


@transaction.atomic
def issue_rfq_addendum(
    *,
    organization: Organization,
    actor: User,
    rfq: RequestForQuotation,
    closing_at: datetime,
    earliest_opening_at: datetime,
    terms: str,
    idempotency_key: str,
) -> RequestForQuotationVersion:
    locked = _locked_rfq(organization=organization, rfq=rfq)
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQS_ADDENDUM,
        project=locked.project,
        message="اجازه صدور الحاقیه را ندارید.",
    )
    if locked.status != RequestForQuotationStatus.ISSUED:
        raise ValueError("الحاقیه فقط برای استعلام صادرشده مجاز است.")
    if (
        earliest_opening_at < closing_at
        or closing_at < locked.closing_at
        or earliest_opening_at < locked.earliest_opening_at
    ):
        raise ValueError("الحاقیه نمی‌تواند مهلت یا مرز گشایش را زودتر کند.")
    key = idempotency_key.strip()
    lines = list(locked.lines.order_by("sort_order", "created_at"))
    suppliers = list(
        RequestForQuotationInvitation.objects.filter(
            rfq_version__rfq=locked,
            rfq_version__version_number=locked.current_version_number,
        ).values_list("supplier_id", flat=True)
    )
    changed = RequestForQuotation.objects.get(pk=locked.pk)
    changed.terms = terms.strip()
    changed.closing_at = closing_at
    changed.earliest_opening_at = earliest_opening_at
    fingerprint = _fingerprint(
        changed, lines, list(BusinessParty.objects.filter(pk__in=suppliers))
    )
    existing = RequestForQuotationVersion.objects.filter(
        rfq=locked, idempotency_key=key
    ).first()
    if existing:
        if existing.payload_fingerprint != fingerprint:
            raise ValueError("تلاش تکراری الحاقیه با داده متفاوت رد شد.")
        return existing
    now = timezone.now()
    version = RequestForQuotationVersion(
        organization=organization,
        rfq=locked,
        version_number=locked.current_version_number + 1,
        issued_at=now,
        issued_by=actor,
        terms=changed.terms,
        closing_at=closing_at,
        earliest_opening_at=earliest_opening_at,
        is_addendum=True,
        idempotency_key=key,
        payload_fingerprint=fingerprint,
    )
    version.full_clean()
    version.save()
    previous = RequestForQuotationVersion.objects.get(
        rfq=locked, version_number=locked.current_version_number
    )
    RequestForQuotationVersionLine.objects.bulk_create(
        [
            RequestForQuotationVersionLine(
                organization=organization,
                rfq_version=version,
                purchase_request_item=x.purchase_request_item,
                material=x.material,
                unit_of_measure=x.unit_of_measure,
                description=x.description,
                quantity=x.quantity,
                sort_order=x.sort_order,
            )
            for x in previous.lines.all()
        ]
    )
    RequestForQuotationInvitation.objects.bulk_create(
        [
            RequestForQuotationInvitation(
                organization=organization,
                rfq_version=version,
                supplier_id=supplier_id,
                created_by=actor,
                updated_by=actor,
            )
            for supplier_id in suppliers
        ]
    )
    locked.terms = changed.terms
    locked.closing_at = closing_at
    locked.earliest_opening_at = earliest_opening_at
    locked.current_version_number = version.version_number
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "terms",
            "closing_at",
            "earliest_opening_at",
            "current_version_number",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.RFQ_ADDENDUM_ISSUED,
        entity_type="rfq",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"version_id": str(version.pk), "idempotency_key": key},
    )
    return version


@transaction.atomic
def cancel_rfq(
    *, organization: Organization, actor: User, rfq: RequestForQuotation, reason: str
) -> RequestForQuotation:
    locked = _locked_rfq(organization=organization, rfq=rfq)
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQS_CANCEL,
        project=locked.project,
        message="اجازه لغو استعلام را ندارید.",
    )
    if locked.status not in {
        RequestForQuotationStatus.DRAFT,
        RequestForQuotationStatus.SUBMITTED_FOR_ISSUE,
        RequestForQuotationStatus.ISSUED,
    }:
        raise ValueError("استعلام در وضعیت فعلی قابل لغو نیست.")
    if not reason.strip():
        raise ValueError("دلیل لغو الزامی است.")
    locked.status = RequestForQuotationStatus.CANCELLED
    locked.cancelled_at = timezone.now()
    locked.cancellation_reason = reason.strip()
    locked.updated_by = actor
    locked.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancellation_reason",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.RFQ_CANCELLED,
        entity_type="rfq",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={"reason": reason.strip()},
    )
    return locked


@transaction.atomic
def close_rfq(
    *,
    organization: Organization,
    actor: User,
    rfq: RequestForQuotation,
    idempotency_key: str,
) -> RFQCloseManifest:
    """Freeze one metadata-only custody manifest; this never opens quote content."""

    locked = _locked_rfq(organization=organization, rfq=rfq)
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQS_CLOSE_CUSTODY,
        project=locked.project,
        message="اجازه بستن ثبتی استعلام را ندارید.",
    )
    key = idempotency_key.strip()
    if not key:
        raise ValueError("کلید یکتای بستن استعلام الزامی است.")
    existing = RFQCloseManifest.objects.filter(rfq=locked).first()
    if existing:
        if existing.idempotency_key != key:
            raise ValueError("استعلام قبلاً با کلید یکتای دیگری بسته شده است.")
        return existing
    if locked.status != RequestForQuotationStatus.ISSUED:
        raise ValueError("فقط استعلام صادرشده قابل بستن است.")
    try:
        version = RequestForQuotationVersion.objects.select_for_update().get(
            organization=organization,
            rfq=locked,
            version_number=locked.current_version_number,
        )
    except RequestForQuotationVersion.DoesNotExist as exc:
        raise ValueError("نسخه مؤثر استعلام یافت نشد.") from exc
    closed_at = timezone.now()
    if closed_at < version.closing_at:
        raise ValueError("بستن دستی نمی‌تواند پیش از مهلت معتبر انجام شود.")
    invitations = list(
        RequestForQuotationInvitation.objects.select_for_update()
        .filter(organization=organization, rfq_version=version)
        .order_by("pk")
    )
    invitation_ids = [invitation.pk for invitation in invitations]
    revisions = list(
        QuoteRevision.objects.select_for_update()
        .filter(
            organization=organization,
            invitation_id__in=invitation_ids,
        )
        .select_related("envelope")
        .order_by("invitation_id", "revision_number", "pk")
    )
    envelopes = list(
        QuoteEnvelope.objects.select_for_update()
        .filter(
            organization=organization,
            rfq=locked,
            supplier_id__in=[invitation.supplier_id for invitation in invitations],
        )
        .order_by("pk")
    )
    envelopes_by_supplier = {envelope.supplier_id: envelope for envelope in envelopes}
    fingerprint = _close_fingerprint(
        rfq=locked,
        version=version,
        invitations=invitations,
        envelopes=envelopes,
        revisions=revisions,
    )
    try:
        manifest = RFQCloseManifest.objects.create(
            organization=organization,
            rfq=locked,
            effective_version=version,
            closed_at=closed_at,
            closed_by=actor,
            idempotency_key=key,
            payload_fingerprint=fingerprint,
        )
    except IntegrityError as exc:
        raise ValueError(
            "بستن هم‌زمان استعلام رد شد؛ با همان کلید دوباره تلاش کنید."
        ) from exc
    revisions_by_invitation: dict[object, list[QuoteRevision]] = {
        invitation.pk: [] for invitation in invitations
    }
    for revision in revisions:
        revisions_by_invitation[revision.invitation_id].append(revision)
    entries = []
    for invitation in invitations:
        invitation_revisions = revisions_by_invitation[invitation.pk]
        effective = [
            revision
            for revision in invitation_revisions
            if _is_effective_revision(
                revision=revision,
                invitation=invitation,
                version=version,
            )
        ]
        if len(effective) > 1:
            raise ValueError("بیش از یک نسخه نهایی فعال برای پاکت پیشنهاد یافت شد.")
        effective_revision = effective[0] if effective else None
        envelope = envelopes_by_supplier.get(invitation.supplier_id)
        entries.append(
            RFQCloseManifestEntry(
                organization=organization,
                manifest=manifest,
                invitation=invitation,
                envelope=envelope,
                effective_revision=effective_revision,
                invitation_status=invitation.status,
                disposition=(
                    RFQCloseEntryDisposition.EFFECTIVE_SUBMITTED
                    if effective_revision
                    else RFQCloseEntryDisposition.NO_EFFECTIVE_SUBMISSION
                ),
                revision_count=len(invitation_revisions),
                captured_unsubmitted_count=sum(
                    revision.status == QuoteRevisionStatus.CAPTURED
                    for revision in invitation_revisions
                ),
                withdrawn_count=sum(
                    revision.status == QuoteRevisionStatus.WITHDRAWN
                    for revision in invitation_revisions
                ),
                superseded_count=sum(
                    revision.status == QuoteRevisionStatus.SUPERSEDED
                    for revision in invitation_revisions
                ),
                late_count=sum(revision.is_late for revision in invitation_revisions),
            )
        )
    RFQCloseManifestEntry.objects.bulk_create(entries)
    RequestForQuotation.objects.filter(pk=locked.pk).update(
        status=RequestForQuotationStatus.CLOSED,
        closed_at=closed_at,
        updated_by=actor,
        updated_at=closed_at,
    )
    record_audit_event(
        action=AuditAction.RFQ_CLOSED,
        entity_type="rfq",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "manifest_id": str(manifest.pk),
            "effective_version_id": str(version.pk),
            "authoritative_deadline": version.closing_at.isoformat(),
            "closed_at": closed_at.isoformat(),
            "invitation_count": len(invitations),
            "payload_fingerprint": fingerprint,
            "idempotency_key": key,
        },
    )
    return manifest


@transaction.atomic
def update_rfq_invitation_status(
    *,
    organization: Organization,
    actor: User,
    invitation: RequestForQuotationInvitation,
    status: RequestForQuotationInvitationStatus,
    reason: str = "",
    delivery_channel: str = "",
    delivery_reference: str = "",
) -> RequestForQuotationInvitation:
    try:
        locked = (
            RequestForQuotationInvitation.objects.select_for_update()
            .select_related("rfq_version__rfq__project")
            .get(pk=invitation.pk, organization=organization)
        )
    except RequestForQuotationInvitation.DoesNotExist as exc:
        raise PermissionDenied("دعوت‌نامه در این سازمان یافت نشد.") from exc
    rfq = locked.rfq_version.rfq
    _permission(
        organization=organization,
        actor=actor,
        permission=BusinessPermissionCode.RFQ_INVITATIONS_MANAGE,
        project=rfq.project,
        message="اجازه مدیریت دعوت‌نامه استعلام را ندارید.",
    )
    if rfq.status in {
        RequestForQuotationStatus.CANCELLED,
        RequestForQuotationStatus.CLOSED,
    }:
        raise ValueError("دعوت‌نامه استعلام بسته یا لغوشده قابل تغییر نیست.")
    normalized_reason = reason.strip()
    if (
        status
        in {
            RequestForQuotationInvitationStatus.WITHDRAWN,
            RequestForQuotationInvitationStatus.DECLINED,
        }
        and not normalized_reason
    ):
        raise ValueError("دلیل تغییر وضعیت دعوت‌نامه الزامی است.")
    locked.status = status
    locked.state_reason = normalized_reason
    if status == RequestForQuotationInvitationStatus.SENT:
        locked.delivery_channel = delivery_channel.strip()
        locked.delivery_reference = delivery_reference.strip()
        locked.sent_at = timezone.now()
    locked.updated_by = actor
    locked.save()
    record_audit_event(
        action=AuditAction.RFQ_INVITATION_UPDATED,
        entity_type="rfq_invitation",
        entity_id=locked.pk,
        organization=organization,
        actor=actor,
        metadata={
            "status": status,
            "has_delivery_proof": bool(locked.delivery_reference),
        },
    )
    return locked


def get_organization_rfqs(
    *, user: User, organization: Organization
) -> QuerySet[RequestForQuotation]:
    membership = require_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.RFQS_VIEW,
        allow_any_scope=True,
        message="اجازه مشاهده استعلام‌ها را ندارید.",
    )
    return scope_queryset(
        RequestForQuotation.objects.filter(
            organization=organization, project__deleted_at__isnull=True
        ),
        membership=membership,
        project_lookup="project_id",
    ).select_related("project", "purchase_request", "created_by", "issued_by")


def get_organization_rfq(
    *, user: User, organization: Organization, rfq_id: str
) -> RequestForQuotation:
    try:
        return (
            get_organization_rfqs(user=user, organization=organization)
            .prefetch_related("lines", "versions__lines", "versions__invitations")
            .get(pk=rfq_id)
        )
    except RequestForQuotation.DoesNotExist as exc:
        raise PermissionDenied("استعلام در این سازمان یافت نشد.") from exc
