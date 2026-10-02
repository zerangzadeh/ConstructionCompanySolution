"""P5-S10 revision-specific commercial admissibility lifecycle."""

from __future__ import annotations

import hashlib
import json
import re

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import membership_has_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from apps.organizations.policy_services import resolve_active_tenant_policy
from apps.organizations.policy_specs import (
    RFQ_ADMISSIBILITY_SELF_APPROVAL_POLICY_CODE,
    validate_policy_for_consumer,
)
from apps.procurement.models import (
    QuoteAdmissibilityDecision,
    QuoteAdmissibilityPreparation,
    QuoteAdmissibilityReasonCode,
    QuoteAdmissibilityWithdrawal,
    QuoteConfidentialAccessGrant,
    QuoteConfidentialAccessRevocation,
    QuoteEligibilityState,
    QuoteOpeningEvent,
    QuoteRevision,
)
from apps.procurement.opening_services import _lock_target

ADMISSIBILITY_APPROVAL_CONSUMER = "procurement.quote_admissibility.approve"
ADMISSIBILITY_PERMISSIONS = (
    BusinessPermissionCode.RFQ_QUOTES_PREPARE_ADMISSIBILITY,
    BusinessPermissionCode.RFQ_QUOTES_APPROVE_ADMISSIBILITY,
)

_REASONS_BY_STATE = {
    QuoteEligibilityState.ADMISSIBLE: {
        QuoteAdmissibilityReasonCode.REQUIREMENTS_MET,
    },
    QuoteEligibilityState.INADMISSIBLE: {
        QuoteAdmissibilityReasonCode.LATE_SUBMISSION,
        QuoteAdmissibilityReasonCode.REQUIRED_EVIDENCE_MISSING,
        QuoteAdmissibilityReasonCode.COMMERCIAL_NONCONFORMANCE,
    },
    QuoteEligibilityState.REVIEW_REQUIRED: {
        QuoteAdmissibilityReasonCode.REQUIRED_EVIDENCE_MISSING,
        QuoteAdmissibilityReasonCode.EXCEPTION_REVIEW_REQUIRED,
    },
}


def _key(value: str) -> str:
    normalized = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", normalized):
        raise ValueError("کلید یکتای عملیات پذیرش معتبر نیست.")
    return normalized


def _rationale(value: str) -> str:
    normalized = str(value).strip()
    if not normalized or len(normalized) > 500:
        raise ValueError("توضیح محرمانه پذیرش معتبر الزامی است.")
    return normalized


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _audit_actor(organization: Organization, actor: User) -> User | None:
    return (
        actor
        if organization.memberships.filter(
            user=actor, status=MembershipStatus.ACTIVE
        ).exists()
        else None
    )


def _record_denial(
    *, organization: Organization, actor: User, revision_id: object, failure: Exception
) -> None:
    record_audit_event(
        action=AuditAction.RFQ_ADMISSIBILITY_REJECTED,
        entity_type="quote_revision",
        entity_id=str(revision_id),
        organization=organization,
        actor=_audit_actor(organization, actor),
        metadata={
            "quote_revision_id": str(revision_id),
            "attempted_actor_id": str(actor.pk),
            "failure_code": type(failure).__name__,
            "content_recorded": False,
        },
    )


def _validate_outcome(*, state: str, reason_code: str) -> tuple[str, str]:
    if state not in {
        QuoteEligibilityState.ADMISSIBLE,
        QuoteEligibilityState.INADMISSIBLE,
        QuoteEligibilityState.REVIEW_REQUIRED,
    }:
        raise ValueError("وضعیت پذیرش تجاری معتبر نیست.")
    if reason_code not in QuoteAdmissibilityReasonCode.values:
        raise ValueError("کد دلیل پذیرش تجاری در کاتالوگ v1 نیست.")
    if reason_code not in _REASONS_BY_STATE[state]:
        raise ValueError("کد دلیل با وضعیت پذیرش تجاری سازگار نیست.")
    return state, reason_code


def _require_confidential_access(
    *, organization: Organization, actor: User, revision: QuoteRevision
) -> OrganizationMembership:
    membership = OrganizationMembership.objects.select_for_update().get(
        organization=organization,
        user=actor,
        status=MembershipStatus.ACTIVE,
        user__is_active=True,
    )
    if not membership_has_permission(
        membership, BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL
    ):
        raise PermissionDenied("مجوز مشاهده محرمانه برای نسخه لازم است.")
    grants = list(
        QuoteConfidentialAccessGrant.objects.select_for_update()
        .filter(
            organization=organization,
            quote_revision=revision,
            membership=membership,
        )
        .only("pk")
    )
    if not grants or all(
        QuoteConfidentialAccessRevocation.objects.filter(grant=grant).exists()
        for grant in grants
    ):
        raise PermissionDenied("دسترسی محرمانه فعال و اختصاصی برای نسخه لازم است.")
    return membership


def _revalidate_opened_revision(
    *, organization: Organization, actor: User, revision: QuoteRevision, permission
):
    revision, manifest = _lock_target(
        organization=organization,
        actor=actor,
        revision=revision,
        permission=permission,
    )
    opening = QuoteOpeningEvent.objects.select_for_update().get(
        organization=organization, quote_revision=revision
    )
    _require_confidential_access(
        organization=organization, actor=actor, revision=revision
    )
    return revision, manifest, opening


def prepare_quote_admissibility(
    *,
    organization: Organization,
    actor: User,
    quote_revision: QuoteRevision,
    state: str,
    reason_code: str,
    rationale: str,
    idempotency_key: str,
) -> QuoteAdmissibilityPreparation:
    """Record an immutable, confidential proposal for one already-opened revision."""

    revision_id = quote_revision.pk
    try:
        state, reason_code = _validate_outcome(state=state, reason_code=reason_code)
        rationale = _rationale(rationale)
        key = _key(idempotency_key)
        with transaction.atomic():
            revision, manifest, opening = _revalidate_opened_revision(
                organization=organization,
                actor=actor,
                revision=quote_revision,
                permission=BusinessPermissionCode.RFQ_QUOTES_PREPARE_ADMISSIBILITY,
            )
            payload_fingerprint = _fingerprint(
                {
                    "revision": str(revision.pk),
                    "opening": str(opening.pk),
                    "package_fingerprint": opening.package_fingerprint,
                    "state": state,
                    "reason_code": reason_code,
                    "rationale": rationale,
                }
            )
            existing = (
                QuoteAdmissibilityPreparation.objects.select_for_update()
                .filter(quote_revision=revision, idempotency_key=key)
                .first()
            )
            if existing:
                if existing.payload_fingerprint != payload_fingerprint:
                    raise ValueError("کلید یکتا با آماده‌سازی متفاوت استفاده شده است.")
                return existing
            preparation = QuoteAdmissibilityPreparation.objects.create(
                organization=organization,
                quote_revision=revision,
                opening_event=opening,
                prepared_by=actor,
                prepared_at=timezone.now(),
                proposed_state=state,
                reason_code=reason_code,
                rationale=rationale,
                close_manifest=manifest,
                package_fingerprint=opening.package_fingerprint,
                idempotency_key=key,
                payload_fingerprint=payload_fingerprint,
            )
            record_audit_event(
                action=AuditAction.RFQ_ADMISSIBILITY_PREPARED,
                entity_type="quote_admissibility_preparation",
                entity_id=preparation.pk,
                organization=organization,
                actor=actor,
                metadata={
                    "quote_revision_id": str(revision.pk),
                    "opening_event_id": str(opening.pk),
                    "state": state,
                    "reason_code": reason_code,
                    "content_recorded": False,
                },
            )
            return preparation
    except Exception as exc:
        _record_denial(
            organization=organization, actor=actor, revision_id=revision_id, failure=exc
        )
        raise


def withdraw_quote_admissibility_preparation(
    *,
    organization: Organization,
    actor: User,
    preparation: QuoteAdmissibilityPreparation,
    reason: str,
) -> QuoteAdmissibilityWithdrawal:
    """Withdraw a pending proposal; approval/correction history is never erased."""

    revision_id = preparation.quote_revision_id
    try:
        reason = _rationale(reason)
        with transaction.atomic():
            locked = (
                QuoteAdmissibilityPreparation.objects.select_for_update()
                .select_related("quote_revision")
                .get(pk=preparation.pk, organization=organization)
            )
            _revalidate_opened_revision(
                organization=organization,
                actor=actor,
                revision=locked.quote_revision,
                permission=BusinessPermissionCode.RFQ_QUOTES_PREPARE_ADMISSIBILITY,
            )
            if QuoteAdmissibilityDecision.objects.filter(preparation=locked).exists():
                raise ValueError("آماده‌سازی تأییدشده قابل پس‌گیری نیست.")
            existing = (
                QuoteAdmissibilityWithdrawal.objects.select_for_update()
                .filter(preparation=locked)
                .first()
            )
            if existing:
                return existing
            withdrawal = QuoteAdmissibilityWithdrawal.objects.create(
                organization=organization,
                preparation=locked,
                withdrawn_by=actor,
                withdrawn_at=timezone.now(),
                reason=reason,
            )
            record_audit_event(
                action=AuditAction.RFQ_ADMISSIBILITY_WITHDRAWN,
                entity_type="quote_admissibility_withdrawal",
                entity_id=withdrawal.pk,
                organization=organization,
                actor=actor,
                metadata={
                    "quote_revision_id": str(locked.quote_revision_id),
                    "preparation_id": str(locked.pk),
                    "content_recorded": False,
                },
            )
            return withdrawal
    except Exception as exc:
        _record_denial(
            organization=organization, actor=actor, revision_id=revision_id, failure=exc
        )
        raise


def approve_quote_admissibility(
    *,
    organization: Organization,
    actor: User,
    preparation: QuoteAdmissibilityPreparation,
    supersedes: QuoteAdmissibilityDecision | None = None,
) -> QuoteAdmissibilityDecision:
    """Approve one pending preparation, or append an explicit correction decision."""

    revision_id = preparation.quote_revision_id
    try:
        with transaction.atomic():
            locked = (
                QuoteAdmissibilityPreparation.objects.select_for_update()
                .select_related("quote_revision", "opening_event", "close_manifest")
                .get(pk=preparation.pk, organization=organization)
            )
            revision, manifest, opening = _revalidate_opened_revision(
                organization=organization,
                actor=actor,
                revision=locked.quote_revision,
                permission=BusinessPermissionCode.RFQ_QUOTES_APPROVE_ADMISSIBILITY,
            )
            if QuoteAdmissibilityWithdrawal.objects.filter(preparation=locked).exists():
                raise ValueError("آماده‌سازی پس‌گرفته‌شده قابل تأیید نیست.")
            existing = (
                QuoteAdmissibilityDecision.objects.select_for_update()
                .filter(preparation=locked)
                .first()
            )
            if existing:
                return existing
            policy = resolve_active_tenant_policy(
                organization=organization,
                policy_code=RFQ_ADMISSIBILITY_SELF_APPROVAL_POLICY_CODE,
            )
            validate_policy_for_consumer(
                policy_version=policy,
                consumer=ADMISSIBILITY_APPROVAL_CONSUMER,
                expected_policy_code=RFQ_ADMISSIBILITY_SELF_APPROVAL_POLICY_CODE,
            )
            if (
                actor.pk == locked.prepared_by_id
                and not policy.parameters["allow_self_approval"]
            ):
                raise PermissionDenied("سیاست مؤثر خودتأییدی پذیرش را مجاز نمی‌داند.")
            prior = list(
                QuoteAdmissibilityDecision.objects.select_for_update()
                .filter(quote_revision=revision)
                .order_by("created_at", "pk")
            )
            if not prior and supersedes is not None:
                raise ValueError("تصحیح بدون تصمیم پیشین معتبر نیست.")
            if prior:
                latest = next(
                    (
                        item
                        for item in reversed(prior)
                        if not item.superseded_by.exists()
                    ),
                    None,
                )
                if latest is None or supersedes is None or supersedes.pk != latest.pk:
                    raise ValueError("تصمیم پیشین فقط با جانشینی صریح قابل تصحیح است.")
                if supersedes.organization_id != organization.pk:
                    raise PermissionDenied("تصمیم جانشین متعلق به این Tenant نیست.")
            if (
                locked.opening_event_id != opening.pk
                or locked.close_manifest_id != manifest.pk
                or locked.package_fingerprint != opening.package_fingerprint
            ):
                raise ValueError("شواهد آماده‌سازی دیگر با پیش‌نیازهای فعلی یکسان نیست.")
            decision = QuoteAdmissibilityDecision.objects.create(
                organization=organization,
                quote_revision=revision,
                preparation=locked,
                opening_event=opening,
                approved_by=actor,
                approved_at=timezone.now(),
                state=locked.proposed_state,
                reason_code=locked.reason_code,
                rationale=locked.rationale,
                close_manifest=manifest,
                package_fingerprint=opening.package_fingerprint,
                approval_policy_version=policy,
                supersedes=supersedes,
            )
            record_audit_event(
                action=AuditAction.RFQ_ADMISSIBILITY_APPROVED,
                entity_type="quote_admissibility_decision",
                entity_id=decision.pk,
                organization=organization,
                actor=actor,
                metadata={
                    "quote_revision_id": str(revision.pk),
                    "preparation_id": str(locked.pk),
                    "supersedes_id": str(supersedes.pk) if supersedes else None,
                    "state": decision.state,
                    "reason_code": decision.reason_code,
                    "policy_version_id": str(policy.pk),
                    "self_approved": actor.pk == locked.prepared_by_id,
                    "content_recorded": False,
                },
            )
            return decision
    except Exception as exc:
        _record_denial(
            organization=organization, actor=actor, revision_id=revision_id, failure=exc
        )
        raise
