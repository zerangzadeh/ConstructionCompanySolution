"""INT-B01: explicit AP acceptance of retained invoice/match occurrences.

Procurement matching never creates an obligation. This AP-owned adapter creates no
Accounting journal. Source correction reverses an unconsumed AP target and accepts
the exact superseding match in one transaction, retaining both histories.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationSettings,
)
from apps.organizations.services import get_organization_settings

from .models import (
    InvoiceMatchStatus,
    Obligation,
    ObligationDirection,
    SupplierInvoice,
    SupplierInvoiceAPReversal,
    SupplierInvoiceMatch,
    SupplierInvoiceStatus,
    SupplierInvoiceVersion,
)
from .services import (
    ObligationSourceSnapshot,
    _active_settlement_amount,
    _approved_writeoff_amount,
    _canonical_hash,
    _lock_membership,
    _lock_organization,
    _required_text,
    recognize_obligation,
    register_source_resolver,
    registered_source_kinds,
)

INVOICE_MATCH_SOURCE_KIND = "procurement.supplier_invoice_match.v1"
RECOGNITION_EVENT = "approved_supplier_invoice_match"
ELIGIBLE_MATCH_STATUSES = (
    InvoiceMatchStatus.MATCHED,
    InvoiceMatchStatus.WITHIN_TOLERANCE,
)


def _source(organization: Organization, source_uuid: UUID) -> SupplierInvoiceMatch:
    try:
        match = SupplierInvoiceMatch.objects.select_related(
            "invoice_version__invoice__supplier",
            "invoice_version__invoice__project",
            "tolerance_policy",
        ).get(pk=source_uuid, organization=organization)
    except SupplierInvoiceMatch.DoesNotExist as exc:
        raise PermissionDenied("منبع تطبیق متعلق به این Tenant نیست.") from exc
    # Same lock order as invoice preparation; matching also locks this version.
    SupplierInvoice.objects.select_for_update().get(
        pk=match.invoice_version.invoice_id, organization=organization
    )
    SupplierInvoiceVersion.objects.select_for_update().get(
        pk=match.invoice_version_id, organization=organization
    )
    match.refresh_from_db()
    return match


def _validate_source(match: SupplierInvoiceMatch) -> dict[str, object]:
    version = match.invoice_version
    version.refresh_from_db()
    if (
        version.status != SupplierInvoiceStatus.APPROVED
        or not version.approved_at
        or not version.approved_by_id
        or match.status not in ELIGIBLE_MATCH_STATUSES
        or version.currency != "IRR"
        or version.organization_id != match.organization_id
        or version.invoice.organization_id != match.organization_id
        or match.tolerance_policy.organization_id != match.organization_id
        or not match.tolerance_policy.is_approved
        or not match.tolerance_policy.approved_at
    ):
        raise ValidationError(
            "صورتحساب تأییدشده و تطبیق مجاز با سیاست مصوب الزامی است."
        )
    if (
        SupplierInvoiceVersion.objects.filter(
            invoice=version.invoice,
            status=SupplierInvoiceStatus.APPROVED,
            version_number__gt=version.version_number,
        ).exists()
        or version.matches.filter(version_number__gt=match.version_number).exists()
    ):
        raise ValidationError("نسخه منبع جانشین شده است؛ آخرین نسخه معتبر لازم است.")
    lines = list(version.lines.order_by("line_number"))
    evidence = list(
        match.lines.select_related("invoice_line").order_by("invoice_line__line_number")
    )
    if (
        not lines
        or {line.pk for line in lines} != {item.invoice_line_id for item in evidence}
        or len(lines) != len(evidence)
        or any(
            item.organization_id != match.organization_id
            or item.invoice_line.organization_id != match.organization_id
            or item.status not in ELIGIBLE_MATCH_STATUSES
            or item.invoiced_quantity != item.invoice_line.quantity
            or item.invoiced_unit_price != item.invoice_line.unit_price
            for item in evidence
        )
        or match.lines.filter(discrepancies__blocking=True).exists()
    ):
        raise ValidationError("شواهد کامل و مجاز تطبیق برای تمام ردیف‌ها الزامی است.")
    expected = _canonical_hash(
        {
            "invoice_hash": version.source_hash,
            "policy_hash": match.tolerance_policy.payload_hash,
            "lines": [str(line.pk) for line in version.lines.all()],
        }
    )
    if match.source_fingerprint != expected:
        raise ValidationError("اثر انگشت منبع تطبیق هم‌خوان نیست.")
    return {
        "invoice_id": str(version.invoice_id),
        "invoice_version_id": str(version.pk),
        "invoice_version": version.version_number,
        "invoice_hash": version.source_hash,
        "match_id": str(match.pk),
        "match_version": match.version_number,
        "match_fingerprint": match.source_fingerprint,
        "recognition_event": RECOGNITION_EVENT,
        "tolerance_policy_id": str(match.tolerance_policy_id),
        "tolerance_policy_hash": match.tolerance_policy.payload_hash,
        "approved_by_id": str(version.approved_by_id),
        "approved_at": version.approved_at.isoformat(),
        "matched_by_id": str(match.matched_by_id),
        "matched_at": match.matched_at.isoformat(),
        "lines": [
            {"invoice_line_id": str(line.pk), "gross_amount": str(line.gross_amount)}
            for line in lines
        ],
        "match_line_ids": [str(item.pk) for item in evidence],
    }


def resolve_invoice_match_source(
    organization: Organization,
    source_uuid: UUID,
    source_version: int,
    source_line_key: str,
) -> ObligationSourceSnapshot:
    """Called inside the locked AP recognition transaction, including retries."""
    match = _source(organization, source_uuid)
    if source_line_key or match.version_number != source_version:
        raise ValidationError("هویت یا نسخه منبع تطبیق AP نامعتبر است.")
    snapshot = _validate_source(match)
    targets = Obligation.objects.filter(
        organization=organization,
        source_kind=INVOICE_MATCH_SOURCE_KIND,
        source_snapshot__invoice_id=snapshot["invoice_id"],
    )
    if targets.filter(source_uuid=match.pk, source_reversals__isnull=False).exists():
        raise ValidationError("همان رخداد برگشت‌شده دوباره فعال نمی‌شود.")
    if (
        targets.filter(source_reversals__isnull=True)
        .exclude(source_uuid=match.pk)
        .exists()
    ):
        raise ValidationError("تعهد قبلی فعال است؛ اصلاح کنترل‌شده AP الزامی است.")
    version = match.invoice_version
    invoice = version.invoice
    try:
        settings = get_organization_settings(organization=organization)
    except OrganizationSettings.DoesNotExist as exc:
        raise ValidationError(
            "تنظیمات مصوب Tenant برای پذیرش منبع AP الزامی است."
        ) from exc
    if settings.currency != version.currency:
        raise ValidationError("ارز منبع با تنظیمات مصوب Tenant هم‌خوان نیست.")
    snapshot["recognition_timezone"] = settings.timezone
    return ObligationSourceSnapshot(
        source_kind=INVOICE_MATCH_SOURCE_KIND,
        source_uuid=match.pk,
        source_version=match.version_number,
        source_line_key="",
        source_status=match.status,
        direction=ObligationDirection.PAYABLE,
        amount=sum((line.gross_amount for line in version.lines.all()), Decimal(0)),
        currency=version.currency,
        recognized_on=timezone.localdate(
            version.approved_at, timezone=ZoneInfo(settings.timezone)
        ),
        due_date=version.due_date,
        party_id=invoice.supplier_id,
        party_name=invoice.supplier.legal_name or invoice.supplier.display_name,
        party_tax_identifier=invoice.supplier.tax_identifier,
        project_id=invoice.project_id,
        contract_id=None,
        source_snapshot=snapshot,
    )


def register_supplier_invoice_handoff() -> None:
    if INVOICE_MATCH_SOURCE_KIND not in registered_source_kinds():
        register_source_resolver(
            INVOICE_MATCH_SOURCE_KIND, resolve_invoice_match_source
        )


def _reverse(
    *,
    organization: Organization,
    actor,
    obligation: Obligation,
    effective_date: date,
    reason: str,
    idempotency_key: str,
    replacement_match: SupplierInvoiceMatch | None,
) -> SupplierInvoiceAPReversal:
    try:
        obligation = Obligation.objects.select_for_update().get(
            pk=obligation.pk, organization=organization
        )
    except Obligation.DoesNotExist as exc:
        raise PermissionDenied("تعهد متعلق به این Tenant نیست.") from exc
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_SOURCES_REVERSE,
        project=obligation.project,
        message="اختیار برگشت منبع AP را ندارید.",
    )
    membership = _lock_membership(organization=organization, membership=membership)
    reason = _required_text(reason, message="دلیل برگشت منبع AP الزامی است.")
    idempotency_key = _required_text(
        idempotency_key, message="کلید برگشت منبع الزامی است."
    )
    payload_hash = _canonical_hash(
        {
            "obligation": obligation.pk,
            "replacement_match": replacement_match.pk if replacement_match else None,
            "effective_date": effective_date,
            "reason": reason,
        }
    )
    prior = SupplierInvoiceAPReversal.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if prior:
        if prior.payload_hash != payload_hash:
            raise ValidationError("کلید برگشت با محتوای متفاوت استفاده شده است.")
        return prior
    if not SupplierInvoiceMatch.objects.filter(
        organization=organization,
        pk=obligation.source_uuid,
        version_number=obligation.source_version,
        invoice_version_id=obligation.source_snapshot.get("invoice_version_id"),
        invoice_version__invoice_id=obligation.source_snapshot.get("invoice_id"),
    ).exists():
        raise ValidationError("هویت منبع اصلی تعهد AP قابل احراز نیست.")
    if (
        obligation.source_reversals.exists()
        or obligation.recognition_journal_id
        or _active_settlement_amount(obligation=obligation)
        or _approved_writeoff_amount(obligation=obligation)
    ):
        raise ValidationError(
            "تعهد مصرف‌شده یا برگشت‌شده نیازمند رفع اثر در مرجع مستقل خود است."
        )
    if obligation.settlement_allocations.filter(
        reversal__effective_date__gt=effective_date
    ).exists():
        raise ValidationError("برگشت منبع نمی‌تواند پیش از رفع اثر تسویه ثبت شود.")
    if obligation.write_off_proposals.filter(
        decision__reversal__effective_date__gt=effective_date
    ).exists():
        raise ValidationError("برگشت منبع نمی‌تواند پیش از رفع اثر سوخت ثبت شود.")
    reversal = SupplierInvoiceAPReversal.objects.create(
        organization=organization,
        obligation=obligation,
        replacement_match=replacement_match,
        effective_date=effective_date,
        reason=reason,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        reversed_by=membership,
    )
    record_audit_event(
        action=AuditAction.SUPPLIER_INVOICE_AP_REVERSED,
        entity_type="subledgers.SupplierInvoiceAPReversal",
        entity_id=reversal.pk,
        organization=organization,
        actor=actor,
        metadata={
            "obligation": str(obligation.pk),
            "replacement_match": str(replacement_match.pk)
            if replacement_match
            else None,
        },
    )
    return reversal


def handoff_supplier_invoice_match(
    *,
    organization: Organization,
    actor,
    match: SupplierInvoiceMatch,
    idempotency_key: str,
    corrects: Obligation | None = None,
    effective_date: date | None = None,
    reason: str = "",
) -> Obligation:
    """Explicit AP-owned L2 acceptance; failed target writes roll back together."""
    # Authorize before opening source details or retaining tenant failure evidence.
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_OBLIGATIONS_RECOGNIZE,
        allow_any_scope=True,
        message="اختیار پذیرش منبع AP را ندارید.",
    )
    failure_phase = "source_validation"
    try:
        with transaction.atomic():
            organization = _lock_organization(organization)
            source = _source(organization, match.pk)
            require_business_permission(
                user=actor,
                organization=organization,
                permission=BusinessPermissionCode.SUBLEDGERS_OBLIGATIONS_RECOGNIZE,
                project=source.invoice_version.invoice.project,
                message="دامنه پروژه AP مجاز نیست.",
            )
            _validate_source(source)
            if corrects is not None:
                failure_phase = "source_reversal"
                if effective_date is None:
                    raise ValidationError("تاریخ اثر اصلاح AP الزامی است.")
                _reverse(
                    organization=organization,
                    actor=actor,
                    obligation=corrects,
                    effective_date=effective_date,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    replacement_match=source,
                )
            failure_phase = "target_acceptance"
            target = recognize_obligation(
                organization=organization,
                actor=actor,
                source_kind=INVOICE_MATCH_SOURCE_KIND,
                source_uuid=source.pk,
                source_version=source.version_number,
                idempotency_key=idempotency_key,
            )
            if corrects is not None and effective_date > target.recognized_on:
                # No period with two active payables: callers must align correction
                # with the replacement's retained recognition occurrence.
                raise ValidationError(
                    "تاریخ برگشت نباید پس از شناسایی منبع جانشین باشد."
                )
            return target
    except (ValidationError, PermissionDenied, DatabaseError) as exc:
        # No attempted target/reversal survives; approved source evidence is intact.
        # Audit only a source actually belonging to the authorized tenant/project.
        source = SupplierInvoiceMatch.objects.filter(
            pk=match.pk, organization=organization
        ).first()
        if source is not None:
            try:
                require_business_permission(
                    user=actor,
                    organization=organization,
                    permission=BusinessPermissionCode.SUBLEDGERS_OBLIGATIONS_RECOGNIZE,
                    project=source.invoice_version.invoice.project,
                    message="دامنه مجاز نیست.",
                )
            except PermissionDenied:
                raise exc
            record_audit_event(
                action=AuditAction.SUPPLIER_INVOICE_AP_FAILED,
                entity_type="subledgers.SupplierInvoiceMatch",
                entity_id=source.pk,
                organization=organization,
                actor=actor,
                metadata={
                    "request_hash": _canonical_hash(idempotency_key),
                    "error_type": type(exc).__name__,
                    "failure_phase": failure_phase,
                    "match_version": source.version_number,
                },
            )
        raise


@transaction.atomic
def reverse_supplier_invoice_obligation(
    *,
    organization: Organization,
    actor,
    obligation: Obligation,
    effective_date: date,
    reason: str,
    idempotency_key: str,
) -> SupplierInvoiceAPReversal:
    organization = _lock_organization(organization)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_SOURCES_REVERSE,
        allow_any_scope=True,
        message="اختیار برگشت منبع AP را ندارید.",
    )
    return _reverse(
        organization=organization,
        actor=actor,
        obligation=obligation,
        effective_date=effective_date,
        reason=reason,
        idempotency_key=idempotency_key,
        replacement_match=None,
    )


@transaction.atomic
def reconcile_supplier_invoice_ap(
    *,
    organization: Organization,
    actor,
    invoice: SupplierInvoice,
) -> dict[str, object]:
    """Tenant/project-scoped source-to-target projection, never posting authority."""
    organization = _lock_organization(organization)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_VIEW,
        allow_any_scope=True,
        message="اختیار مشاهده تطبیق AP را ندارید.",
    )
    try:
        invoice = SupplierInvoice.objects.select_for_update().get(
            pk=invoice.pk, organization=organization
        )
    except SupplierInvoice.DoesNotExist as exc:
        raise PermissionDenied("صورتحساب متعلق به این Tenant نیست.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.SUBLEDGERS_VIEW,
        project=invoice.project,
        message="اختیار مشاهده تطبیق AP را ندارید.",
    )
    version = (
        invoice.versions.filter(status=SupplierInvoiceStatus.APPROVED)
        .order_by("-version_number")
        .first()
    )
    match = version.matches.order_by("-version_number").first() if version else None
    targets = list(
        Obligation.objects.filter(
            organization=organization,
            source_kind=INVOICE_MATCH_SOURCE_KIND,
            source_snapshot__invoice_id=str(invoice.pk),
        ).order_by("created_at", "pk")
    )
    rows = []
    for target in targets:
        reversal = target.source_reversals.first()
        replacement = next(
            (
                item
                for item in targets
                if reversal and item.source_uuid == reversal.replacement_match_id
            ),
            None,
        )
        rows.append(
            {
                "obligation_id": str(target.pk),
                "source": target.source_snapshot,
                "original_amount": str(target.original_amount),
                "outstanding_amount": str(target.outstanding_amount),
                "reversal_id": str(reversal.pk) if reversal else None,
                "reversal_effective_date": reversal.effective_date.isoformat()
                if reversal
                else None,
                "replacement_obligation_id": str(replacement.pk)
                if replacement
                else None,
                "current_source": bool(
                    match and target.source_uuid == match.pk and not reversal
                ),
                "recognition_journal_id": str(target.recognition_journal_id)
                if target.recognition_journal_id
                else None,
            }
        )
    result = {
        "invoice_id": str(invoice.pk),
        "active_invoice_version": version.version_number if version else None,
        "active_match_id": str(match.pk) if match else None,
        "active_match_version": match.version_number if match else None,
        "active_match_status": match.status if match else None,
        "targets": rows,
    }
    result["evidence_hash"] = _canonical_hash(result)
    return result
