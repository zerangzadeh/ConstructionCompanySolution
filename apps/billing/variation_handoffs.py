"""INT-C02: approved source availability, with no financial decision authority."""

from __future__ import annotations

import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.contracts.models import ContractualRecord
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization

from .variation_models import VariationBillingEligibility

APPROVED_HISTORY = ("approved", "superseded", "cancelled")
POLICY = "HUMAN-CEP037-ELIGIBILITY-20261018"


def source_digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def eligibility_for_source(source: ContractualRecord) -> bool:
    """Approved source amount is deliberately absent from this predicate."""
    return (
        source.revision_action in ("original", "correction")
        and source.entitlement_approved is True
    )


def _permission(
    organization: Organization, actor: User, source: ContractualRecord, permission: str
):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=source.project,
        message="اختیار و دامنه منبع اهلیت لازم است.",
    )


def _latest_source(organization: Organization, series_id) -> ContractualRecord | None:
    # Domain version/chain authority, not created_at or a later unapproved draft.
    return (
        ContractualRecord.objects.filter(
            organization=organization,
            series_id=series_id,
            kind="variation",
            status__in=APPROVED_HISTORY,
            approved_at__isnull=False,
            approved_by__isnull=False,
        )
        .order_by("-version")
        .first()
    )


def _source_snapshot(source: ContractualRecord) -> dict:
    chain = []
    current = source
    while current is not None:
        if (
            current.organization_id != source.organization_id
            or current.series_id != source.series_id
            or current.contract_id != source.contract_id
            or current.kind != "variation"
        ):
            raise ValidationError("زنجیره منبع تأییدشده معتبر نیست.")
        if current.supersedes_id:
            previous = current.supersedes
            if (
                previous.version + 1 != current.version
                or current.revision_action not in ("correction", "cancellation")
            ):
                raise ValidationError("پیوند نسخه منبع معتبر نیست.")
        else:
            previous = None
            if current.version != 1 or current.revision_action != "original":
                raise ValidationError("ریشه منبع معتبر نیست.")
        chain.append(
            {
                "source_id": str(current.pk),
                "version": current.version,
                "action": current.revision_action,
                "approved_at": current.approved_at.isoformat()
                if current.approved_at
                else None,
                "approved_by_id": str(current.approved_by_id),
                "entitlement_approved": current.entitlement_approved,
            }
        )
        current = previous
    return {
        "policy": POLICY,
        "source_id": str(source.pk),
        "series_id": str(source.series_id),
        "source_version": source.version,
        "project_id": str(source.project_id),
        "contract_id": str(source.contract_id),
        "revision_action": source.revision_action,
        "entitlement_approved": source.entitlement_approved,
        "approved_amount_evidence_only": str(source.approved_amount)
        if source.approved_amount is not None
        else None,
        "approval_reason": source.approval_reason,
        "source_chain": chain,
    }


@transaction.atomic
def _accept(
    *,
    organization: Organization,
    actor: User,
    source: ContractualRecord,
    idempotency_key: str,
    source_event: bool,
) -> VariationBillingEligibility:
    try:
        source = ContractualRecord.objects.select_for_update(of=("self",)).get(
            pk=source.pk, organization=organization
        )
    except ContractualRecord.DoesNotExist as exc:
        raise PermissionDenied("منبع متعلق به این سازمان نیست.") from exc
    membership = _permission(
        organization,
        actor,
        source,
        P.CONTRACTUAL_RECORDS_APPROVE
        if source_event
        else P.BILLING_VARIATION_ELIGIBILITY_RETRY,
    )
    if source_event and source.approved_by_id != actor.pk:
        raise PermissionDenied("رخداد تأیید باید متعلق به تأییدکننده ثبت‌شده باشد.")
    latest = _latest_source(organization, source.series_id)
    if (
        source.kind != "variation"
        or source.status != "approved"
        or latest is None
        or latest.pk != source.pk
        or not isinstance(source.entitlement_approved, bool)
        or source.project.deleted_at is not None
        or source.contract.deleted_at is not None
    ):
        raise ValidationError("آخرین حالت مؤثر و تأییدشده تغییر لازم است.")
    snapshot = _source_snapshot(source)
    digest = source_digest(snapshot)
    key = idempotency_key.strip()
    if not key or len(key) > 120:
        raise ValidationError("کلید رخداد معتبر لازم است.")
    by_key = VariationBillingEligibility.objects.filter(
        organization=organization, idempotency_key=key
    ).first()
    prior = VariationBillingEligibility.objects.filter(
        organization=organization, source=source
    ).first()
    if by_key and by_key.source_id != source.pk:
        raise ValidationError("کلید عملیات به منبع دیگری تعلق دارد.")
    if prior:
        if prior.source_sha256 != digest:
            raise ValidationError("شواهد منبع با پذیرش قبلی هم‌خوان نیست.")
        return prior
    predecessor = (
        VariationBillingEligibility.objects.select_for_update()
        .filter(
            organization=organization,
            series_id=source.series_id,
            source_version__lt=source.version,
        )
        .order_by("-source_version")
        .first()
    )
    target = VariationBillingEligibility.objects.create(
        organization=organization,
        project=source.project,
        contract=source.contract,
        source=source,
        series_id=source.series_id,
        source_version=source.version,
        source_snapshot=snapshot,
        source_sha256=digest,
        active_at_occurrence=eligibility_for_source(source),
        predecessor=predecessor,
        idempotency_key=key,
        created_by=membership,
    )
    record_audit_event(
        organization=organization,
        actor=actor,
        action=AuditAction.VARIATION_BILLING_ACCEPTED,
        entity_type="billing.VariationBillingEligibility",
        entity_id=target.pk,
        metadata={
            "source_id": str(source.pk),
            "series_id": str(source.series_id),
            "source_version": source.version,
            "active": target.active_at_occurrence,
            "predecessor_id": str(predecessor.pk) if predecessor else None,
            "source_sha256": digest,
            "policy": POLICY,
        },
    )
    return target


def _failure(
    *,
    organization: Organization,
    actor: User,
    source: ContractualRecord,
    error: Exception,
    permission: str,
) -> None:
    actual = ContractualRecord.objects.filter(
        pk=source.pk, organization=organization, kind="variation"
    ).first()
    if actual is None:
        return
    _permission(organization, actor, actual, permission)
    record_audit_event(
        organization=organization,
        actor=actor,
        action=AuditAction.VARIATION_BILLING_FAILED,
        entity_type="contracts.ContractualRecord",
        entity_id=actual.pk,
        metadata={
            "source_version": actual.version,
            "error_type": type(error).__name__,
            "policy": POLICY,
            "target_effect": "rolled_back",
        },
    )


def accept_approved_variation_event(
    *, organization: Organization, actor: User, source: ContractualRecord
) -> None:
    """Registered L2 consequence inside source approval, not Billing approval.

    A failed target savepoint leaves the approved source and explicit retry audit
    intact. Current availability then fails closed until a successful retry.
    """
    if source.kind != "variation":
        return
    try:
        _accept(
            organization=organization,
            actor=actor,
            source=source,
            idempotency_key=f"int-c02:{source.pk}:{source.version}",
            source_event=True,
        )
    except (ValidationError, PermissionDenied, DatabaseError) as exc:
        _failure(
            organization=organization,
            actor=actor,
            source=source,
            error=exc,
            permission=P.CONTRACTUAL_RECORDS_APPROVE,
        )


def retry_variation_billing_handoff(
    *,
    organization: Organization,
    actor: User,
    source: ContractualRecord,
    idempotency_key: str,
) -> VariationBillingEligibility:
    try:
        return _accept(
            organization=organization,
            actor=actor,
            source=source,
            idempotency_key=idempotency_key,
            source_event=False,
        )
    except (ValidationError, PermissionDenied, DatabaseError) as exc:
        # Never retain failure evidence to a tenant or object the actor cannot access.
        try:
            _failure(
                organization=organization,
                actor=actor,
                source=source,
                error=exc,
                permission=P.BILLING_VARIATION_ELIGIBILITY_RETRY,
            )
        except PermissionDenied:
            raise exc
        raise


@transaction.atomic
def reconcile_variation_billing(
    *, organization: Organization, actor: User, source: ContractualRecord
) -> dict:
    try:
        source = ContractualRecord.objects.select_for_update(of=("self",)).get(
            pk=source.pk, organization=organization, kind="variation"
        )
    except ContractualRecord.DoesNotExist as exc:
        raise PermissionDenied("منبع متعلق به این سازمان نیست.") from exc
    _permission(organization, actor, source, P.BILLING_VARIATION_ELIGIBILITY_VIEW)
    latest = _latest_source(organization, source.series_id)
    targets = list(
        VariationBillingEligibility.objects.filter(
            organization=organization, series_id=source.series_id
        ).order_by("source_version")
    )
    current = next((t for t in targets if latest and t.source_id == latest.pk), None)
    current_valid = bool(
        current
        and latest
        and latest.status == "approved"
        and current.source_sha256 == source_digest(_source_snapshot(latest))
        and current.active_at_occurrence == eligibility_for_source(latest)
    )
    result = {
        "series_id": str(source.series_id),
        "policy": POLICY,
        "latest_approved_source_id": str(latest.pk) if latest else None,
        "latest_approved_version": latest.version if latest else None,
        "active_eligibility_id": str(current.pk)
        if current_valid and current.active_at_occurrence
        else None,
        "handoff_pending": bool(latest and not current_valid),
        "targets": [
            {
                "target_id": str(t.pk),
                "source_id": str(t.source_id),
                "source_version": t.source_version,
                "active_at_occurrence": t.active_at_occurrence,
                "is_current_source": bool(latest and t.source_id == latest.pk),
                "predecessor_id": str(t.predecessor_id) if t.predecessor_id else None,
                "source_snapshot": t.source_snapshot,
                "source_sha256": t.source_sha256,
            }
            for t in targets
        ],
    }
    result["evidence_hash"] = source_digest(result)
    return result
