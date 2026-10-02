"""P5-S11 immutable commercial comparison and sourcing-only award services."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
)
from apps.organizations.policy_services import resolve_active_tenant_policy
from apps.organizations.policy_specs import (
    RFQ_COMPARISON_SELF_FINALIZATION_POLICY_CODE,
    RFQ_EXCEPTION_SELF_APPROVAL_POLICY_CODE,
    RFQ_SOURCING_AWARD_SELF_FINALIZATION_POLICY_CODE,
    validate_policy_for_consumer,
)
from apps.procurement.admissibility_services import _require_confidential_access
from apps.procurement.models import (
    CommercialComparison,
    CommercialComparisonInput,
    CommercialComparisonStatus,
    CommercialEvaluation,
    CommercialException,
    CommercialExceptionCode,
    CommercialExceptionStatus,
    EvaluatorAppointment,
    EvaluatorConflictDeclaration,
    QuoteAdmissibilityDecision,
    QuoteCommercialAssertion,
    QuoteEligibilityState,
    QuoteOpeningEvent,
    QuoteRevision,
    RFQCommercialScope,
    SourcingAward,
    SourcingAwardAllocation,
    SourcingAwardOutcome,
    SourcingAwardPreparation,
    SourcingAwardPreparationAllocation,
)
from apps.procurement.opening_services import _lock_target

NORMALIZATION_POLICY_CODE = "commercial-normalization-v1"
NORMALIZATION_POLICY_VERSION = 1
COMPARISON_FINALIZATION_CONSUMER = "procurement.comparison.finalize"
AWARD_FINALIZATION_CONSUMER = "procurement.sourcing_award.finalize"
EXCEPTION_APPROVAL_CONSUMER = "procurement.commercial_exception.approve"


def _text(value: str, label: str) -> str:
    normalized = str(value).strip()
    if not normalized or len(normalized) > 500:
        raise ValueError(f"{label} معتبر و الزامی است.")
    return normalized


def _key(value: str) -> str:
    normalized = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", normalized):
        raise ValueError("کلید یکتای عملیات معتبر نیست.")
    return normalized


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _membership(
    *, organization: Organization, actor: User, permission, scope: RFQCommercialScope
):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=scope.rfq_version.rfq.project,
        message="مجوز و دامنه تجاری RFQ لازم است.",
    )


def _current_admissibility(
    *, organization: Organization, revision: QuoteRevision
) -> QuoteAdmissibilityDecision:
    decision = (
        QuoteAdmissibilityDecision.objects.select_for_update()
        .filter(
            organization=organization,
            quote_revision=revision,
            state=QuoteEligibilityState.ADMISSIBLE,
        )
        .order_by("-created_at")
        .first()
    )
    if decision is None or decision.superseded_by.exists():
        raise PermissionDenied("فقط نسخه بازشده با پذیرش تجاری مؤثر قابل مقایسه است.")
    return decision


def _revalidate_revision(
    *, organization: Organization, actor: User, revision: QuoteRevision, permission
):
    revision, manifest = _lock_target(
        organization=organization, actor=actor, revision=revision, permission=permission
    )
    opening = (
        QuoteOpeningEvent.objects.select_for_update()
        .filter(organization=organization, quote_revision=revision)
        .first()
    )
    if opening is None:
        raise PermissionDenied("گشایش حفاظت‌شده نسخه لازم است.")
    _require_confidential_access(
        organization=organization, actor=actor, revision=revision
    )
    return (
        revision,
        manifest,
        opening,
        _current_admissibility(organization=organization, revision=revision),
    )


def _normalize(
    *, scope: RFQCommercialScope, item: dict[str, Any]
) -> tuple[Decimal, dict[str, str]]:
    offered_quantity = Decimal(str(item["offered_quantity"]))
    unit_price = (
        Decimal(str(item["unit_price"])) if item.get("unit_price") is not None else None
    )
    line_amount = (
        Decimal(str(item["line_amount"]))
        if item.get("line_amount") is not None
        else None
    )
    discount = Decimal(str(item.get("explicit_discount", "0")))
    currency = str(item["currency"]).strip().upper()
    if offered_quantity <= 0 or discount < 0 or not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("کمیت، تخفیف یا ارز ادعاشده قابل مقایسه نیست.")
    if unit_price is None and line_amount is None:
        raise ValueError("قیمت واحد یا مبلغ ردیف ادعاشده لازم است.")
    # v1 does no conversion: a line amount is usable only for the governing quantity.
    if line_amount is not None and offered_quantity != scope.required_quantity:
        raise ValueError("مبلغ ردیف با مقدار حاکم RFQ قابل نرمال‌سازی نیست.")
    if unit_price is not None:
        derived = scope.required_quantity * unit_price - discount
        if line_amount is not None and line_amount - discount != derived:
            raise ValueError("قیمت واحد و مبلغ ردیف ادعاشده با هم سازگار نیستند.")
    else:
        derived = line_amount - discount  # type: ignore[operator]
    if derived < 0:
        raise ValueError("مبلغ نرمال‌شده منفی مجاز نیست.")
    return derived, {
        "policy": f"{NORMALIZATION_POLICY_CODE}:{NORMALIZATION_POLICY_VERSION}",
        "governing_quantity": str(scope.required_quantity),
        "offered_quantity": str(offered_quantity),
        "unit_price": "" if unit_price is None else str(unit_price),
        "line_amount": "" if line_amount is None else str(line_amount),
        "explicit_discount": str(discount),
        "currency": currency,
        "transforms": "none: no FX/tax/escalation/inferred_discount/unit_conversion",
        "result": str(derived),
    }


def prepare_comparison(
    *,
    organization: Organization,
    actor: User,
    scope: RFQCommercialScope,
    assertions: list[dict[str, Any]],
    idempotency_key: str,
    supersedes: CommercialComparison | None = None,
) -> CommercialComparison:
    """Create the full immutable asserted-input and reproducible v1 comparison set."""
    key = _key(idempotency_key)
    if not assertions:
        raise ValueError("حداقل یک ورودی تجاری لازم است.")
    with transaction.atomic():
        scope = (
            RFQCommercialScope.objects.select_for_update()
            .select_related("rfq_version__rfq__project")
            .get(pk=scope.pk, organization=organization)
        )
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_PREPARE_COMPARISON,
            scope=scope,
        )
        normalized: list[tuple[dict[str, Any], QuoteRevision, Any, Any, Any]] = []
        currencies: set[str] = set()
        revision_ids: set[object] = set()
        for item in assertions:
            revision = QuoteRevision.objects.get(
                pk=item["quote_revision_id"], organization=organization
            )
            if revision.pk in revision_ids:
                raise ValueError("هر نسخه فقط یک ورودی برای یک مقایسه دارد.")
            revision_ids.add(revision.pk)
            revision, _manifest, opening, admissibility = _revalidate_revision(
                organization=organization,
                actor=actor,
                revision=revision,
                permission=BusinessPermissionCode.RFQ_QUOTES_PREPARE_COMPARISON,
            )
            amount, lineage = _normalize(scope=scope, item=item)
            currencies.add(lineage["currency"])
            normalized.append(
                (item, revision, opening, admissibility, (amount, lineage))
            )
        if len(currencies) != 1:
            raise ValueError("چندارزی بدون سیاست FX قابل مقایسه نیست.")
        payload = {
            "scope": str(scope.pk),
            "assertions": [
                {k: str(v) for k, v in item.items()} for item, *_ in normalized
            ],
            "supersedes": str(supersedes.pk) if supersedes else None,
        }
        fingerprint = _fingerprint(payload)
        existing = (
            CommercialComparison.objects.select_for_update()
            .filter(commercial_scope=scope, idempotency_key=key)
            .first()
        )
        if existing:
            if existing.payload_fingerprint != fingerprint:
                raise ValueError("کلید یکتا با مقایسه متفاوت استفاده شده است.")
            return existing
        if supersedes is not None and (
            supersedes.organization_id != organization.pk
            or supersedes.commercial_scope_id != scope.pk
            or not supersedes.finalized_at
        ):
            raise ValueError("جانشینی فقط برای مقایسه نهایی همان دامنه مجاز است.")
        comparison = CommercialComparison.objects.create(
            organization=organization,
            commercial_scope=scope,
            prepared_by=actor,
            prepared_at=timezone.now(),
            normalization_policy_code=NORMALIZATION_POLICY_CODE,
            normalization_policy_version=NORMALIZATION_POLICY_VERSION,
            supersedes=supersedes,
            idempotency_key=key,
            payload_fingerprint=fingerprint,
        )
        for sequence, (
            item,
            revision,
            opening,
            admissibility,
            calculation,
        ) in enumerate(normalized, start=1):
            amount, lineage = calculation
            assertion_payload = {
                "comparison": str(comparison.pk),
                "sequence": sequence,
                "revision": str(revision.pk),
                **{k: str(v) for k, v in item.items()},
            }
            assertion = QuoteCommercialAssertion.objects.create(
                organization=organization,
                quote_revision=revision,
                commercial_scope=scope,
                offered_quantity=Decimal(str(item["offered_quantity"])),
                unit_price=Decimal(str(item["unit_price"]))
                if item.get("unit_price") is not None
                else None,
                line_amount=Decimal(str(item["line_amount"]))
                if item.get("line_amount") is not None
                else None,
                currency=lineage["currency"],
                explicit_discount=Decimal(str(item.get("explicit_discount", "0"))),
                is_alternate=bool(item.get("is_alternate", False)),
                alternate_basis=str(item.get("alternate_basis", "")),
                source_locator=_text(item.get("source_locator", ""), "مرجع منبع"),
                asserted_by=actor,
                idempotency_key=f"{key}-{sequence}",
                payload_fingerprint=_fingerprint(assertion_payload),
            )
            CommercialComparisonInput.objects.create(
                organization=organization,
                comparison=comparison,
                assertion=assertion,
                quote_revision=revision,
                admissibility_decision=admissibility,
                opening_event=opening,
                normalized_amount=amount,
                calculation_lineage=lineage,
            )
        record_audit_event(
            action=AuditAction.RFQ_COMPARISON_PREPARED,
            entity_type="commercial_comparison",
            entity_id=comparison.pk,
            organization=organization,
            actor=actor,
            metadata={
                "scope_id": str(scope.pk),
                "input_count": len(normalized),
                "normalization_policy": "v1",
                "content_recorded": False,
            },
        )
        return comparison


def appoint_evaluator(
    *,
    organization: Organization,
    actor: User,
    comparison: CommercialComparison,
    membership: OrganizationMembership,
    quote_revision: QuoteRevision | None = None,
) -> EvaluatorAppointment:
    with transaction.atomic():
        comparison = (
            CommercialComparison.objects.select_for_update()
            .select_related("commercial_scope__rfq_version__rfq__project")
            .get(pk=comparison.pk, organization=organization)
        )
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_PREPARE_COMPARISON,
            scope=comparison.commercial_scope,
        )
        if membership.organization_id != organization.pk or (
            quote_revision
            and not comparison.inputs.filter(quote_revision=quote_revision).exists()
        ):
            raise PermissionDenied("ارزیاب یا نسخه خارج از دامنه مقایسه است.")
        return EvaluatorAppointment.objects.get_or_create(
            organization=organization,
            comparison=comparison,
            membership=membership,
            quote_revision=quote_revision,
            defaults={"appointed_by": actor, "appointed_at": timezone.now()},
        )[0]


def declare_evaluator_conflict(
    *,
    organization: Organization,
    actor: User,
    appointment: EvaluatorAppointment,
    evidence: str,
) -> EvaluatorConflictDeclaration:
    with transaction.atomic():
        appointment = (
            EvaluatorAppointment.objects.select_for_update()
            .select_related(
                "comparison__commercial_scope__rfq_version__rfq__project",
                "membership__user",
            )
            .get(pk=appointment.pk, organization=organization)
        )
        if appointment.membership.user_id != actor.pk:
            raise PermissionDenied("فقط ارزیاب منصوب می‌تواند تعارض خود را اعلام کند.")
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_EVALUATE_COMPARISON,
            scope=appointment.comparison.commercial_scope,
        )
        result = EvaluatorConflictDeclaration.objects.create(
            organization=organization,
            appointment=appointment,
            declared_by=actor,
            declared_at=timezone.now(),
            evidence=_text(evidence, "شاهد تعارض"),
        )
        record_audit_event(
            action=AuditAction.RFQ_EVALUATOR_CONFLICT_DECLARED,
            entity_type="evaluator_conflict",
            entity_id=result.pk,
            organization=organization,
            actor=actor,
            metadata={
                "comparison_id": str(appointment.comparison_id),
                "content_recorded": False,
            },
        )
        return result


def dispose_evaluator_conflict(
    *,
    organization: Organization,
    actor: User,
    conflict: EvaluatorConflictDeclaration,
    approved: bool,
    reason: str,
) -> EvaluatorConflictDeclaration:
    with transaction.atomic():
        conflict = (
            EvaluatorConflictDeclaration.objects.select_for_update()
            .select_related(
                "appointment__comparison__commercial_scope__rfq_version__rfq__project"
            )
            .get(pk=conflict.pk, organization=organization)
        )
        scope = conflict.appointment.comparison.commercial_scope
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_DISPOSE_CONFLICT,
            scope=scope,
        )
        if actor.pk == conflict.declared_by_id:
            raise PermissionDenied("خودتعیین‌تکلیفی تعارض ممنوع است.")
        if conflict.disposition != CommercialExceptionStatus.PROPOSED:
            return conflict
        existing = conflict.superseded_by.select_for_update().first()
        if existing is not None:
            return existing
        # Keep declaration immutable: disposition is an append-only successor record.
        result = EvaluatorConflictDeclaration.objects.create(
            organization=organization,
            appointment=conflict.appointment,
            declared_by=conflict.declared_by,
            declared_at=conflict.declared_at,
            evidence=conflict.evidence,
            disposition=CommercialExceptionStatus.APPROVED
            if approved
            else CommercialExceptionStatus.REJECTED,
            disposed_by=actor,
            disposed_at=timezone.now(),
            disposition_reason=_text(reason, "دلیل تعیین تکلیف"),
            supersedes=conflict,
        )
        record_audit_event(
            action=AuditAction.RFQ_EVALUATOR_CONFLICT_DISPOSED,
            entity_type="evaluator_conflict",
            entity_id=result.pk,
            organization=organization,
            actor=actor,
            metadata={
                "predecessor_id": str(conflict.pk),
                "approved": approved,
                "content_recorded": False,
            },
        )
        return result


def evaluate_comparison(
    *,
    organization: Organization,
    actor: User,
    appointment: EvaluatorAppointment,
    input: CommercialComparisonInput,
    recommendation: str,
    evidence: str,
) -> CommercialEvaluation:
    with transaction.atomic():
        appointment = (
            EvaluatorAppointment.objects.select_for_update()
            .select_related(
                "comparison__commercial_scope__rfq_version__rfq__project",
                "membership__user",
            )
            .get(pk=appointment.pk, organization=organization)
        )
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_EVALUATE_COMPARISON,
            scope=appointment.comparison.commercial_scope,
        )
        if (
            appointment.membership.user_id != actor.pk
            or appointment.revoked_at
            or input.organization_id != organization.pk
            or input.comparison_id != appointment.comparison_id
        ):
            raise PermissionDenied("انتصاب فعال و دقیق ارزیاب لازم است.")
        if EvaluatorConflictDeclaration.objects.filter(
            appointment=appointment,
            disposition=CommercialExceptionStatus.PROPOSED,
            superseded_by__isnull=True,
        ).exists():
            raise PermissionDenied("ارزیاب دارای تعارض حل‌نشده نمی‌تواند ارزیابی کند.")
        result, _ = CommercialEvaluation.objects.get_or_create(
            organization=organization,
            comparison=appointment.comparison,
            evaluator_appointment=appointment,
            input=input,
            defaults={
                "recommendation": _text(recommendation, "توصیه"),
                "evaluated_by": actor,
                "evaluated_at": timezone.now(),
                "evidence": _text(evidence, "شاهد ارزیابی"),
            },
        )
        record_audit_event(
            action=AuditAction.RFQ_COMPARISON_EVALUATED,
            entity_type="commercial_evaluation",
            entity_id=result.pk,
            organization=organization,
            actor=actor,
            metadata={
                "comparison_id": str(appointment.comparison_id),
                "input_id": str(input.pk),
                "content_recorded": False,
            },
        )
        return result


def finalize_comparison(
    *,
    organization: Organization,
    actor: User,
    comparison: CommercialComparison,
    reason: str,
) -> CommercialComparison:
    with transaction.atomic():
        comparison = (
            CommercialComparison.objects.select_for_update()
            .select_related(
                "commercial_scope__rfq_version__rfq__project", "prepared_by"
            )
            .get(pk=comparison.pk, organization=organization)
        )
        scope = comparison.commercial_scope
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_FINALIZE_COMPARISON,
            scope=scope,
        )
        if comparison.finalized_at:
            return comparison
        # Finalization is append-only: once the locked prepared record has a
        # finalized successor, all retries (including a transaction that waited
        # on this row) must resolve to that governing successor.
        existing_finalization = comparison.superseded_by.select_for_update().filter(
            finalized_at__isnull=False
        ).first()
        if existing_finalization is not None:
            return existing_finalization
        if EvaluatorConflictDeclaration.objects.filter(
            appointment__comparison=comparison,
            disposition=CommercialExceptionStatus.PROPOSED,
            superseded_by__isnull=True,
        ).exists():
            raise PermissionDenied("تعارض ارزیاب حل‌نشده مانع نهایی‌سازی است.")
        if (
            not comparison.evaluations.exists()
            or comparison.inputs.exclude(evaluations__isnull=False).exists()
        ):
            raise PermissionDenied(
                "تمام ورودی‌های مقایسه باید ارزیابی مستند داشته باشند."
            )
        policy = resolve_active_tenant_policy(
            organization=organization,
            policy_code=RFQ_COMPARISON_SELF_FINALIZATION_POLICY_CODE,
        )
        validate_policy_for_consumer(
            policy_version=policy,
            consumer=COMPARISON_FINALIZATION_CONSUMER,
            expected_policy_code=RFQ_COMPARISON_SELF_FINALIZATION_POLICY_CODE,
        )
        if (
            actor.pk == comparison.prepared_by_id
            and not policy.parameters["allow_self_approval"]
        ):
            raise PermissionDenied("سیاست Tenant خودنهایی‌سازی مقایسه را مجاز نمی‌داند.")
        amounts = list(comparison.inputs.values_list("normalized_amount", flat=True))
        low = min(amounts)
        status = (
            CommercialComparisonStatus.TIE_REVIEW_REQUIRED
            if amounts.count(low) > 1
            else CommercialComparisonStatus.FINALIZED
        )
        # The finalized immutable successor carries the decision and predecessor lineage.
        finalized = CommercialComparison.objects.create(
            organization=organization,
            commercial_scope=scope,
            prepared_by=comparison.prepared_by,
            prepared_at=comparison.prepared_at,
            normalization_policy_code=comparison.normalization_policy_code,
            normalization_policy_version=1,
            status=status,
            finalized_by=actor,
            finalized_at=timezone.now(),
            finalization_policy_version=policy,
            finalization_reason=_text(reason, "دلیل نهایی‌سازی"),
            supersedes=comparison,
            idempotency_key=f"final-{comparison.pk}",
            payload_fingerprint=_fingerprint(
                {"finalizes": str(comparison.pk), "reason": reason, "status": status}
            ),
        )
        for source in comparison.inputs.all():
            CommercialComparisonInput.objects.create(
                organization=organization,
                comparison=finalized,
                assertion=source.assertion,
                quote_revision=source.quote_revision,
                admissibility_decision=source.admissibility_decision,
                opening_event=source.opening_event,
                normalized_amount=source.normalized_amount,
                calculation_lineage=source.calculation_lineage,
            )
        record_audit_event(
            action=AuditAction.RFQ_COMPARISON_FINALIZED,
            entity_type="commercial_comparison",
            entity_id=finalized.pk,
            organization=organization,
            actor=actor,
            metadata={
                "predecessor_id": str(comparison.pk),
                "status": status,
                "policy_version_id": str(policy.pk),
                "self_finalized": actor.pk == comparison.prepared_by_id,
                "content_recorded": False,
            },
        )
        return finalized


def propose_commercial_exception(
    *,
    organization: Organization,
    actor: User,
    revision: QuoteRevision,
    scope: RFQCommercialScope,
    code: str,
    evidence: str,
) -> CommercialException:
    with transaction.atomic():
        scope = (
            RFQCommercialScope.objects.select_for_update()
            .select_related("rfq_version__rfq__project")
            .get(pk=scope.pk, organization=organization)
        )
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_PREPARE_COMPARISON,
            scope=scope,
        )
        _revalidate_revision(
            organization=organization,
            actor=actor,
            revision=revision,
            permission=BusinessPermissionCode.RFQ_QUOTES_PREPARE_COMPARISON,
        )
        if code not in CommercialExceptionCode.values:
            raise ValueError("استثنا خارج از کاتالوگ بسته v1 است.")
        return CommercialException.objects.create(
            organization=organization,
            quote_revision=revision,
            commercial_scope=scope,
            code=code,
            evidence=_text(evidence, "شاهد استثنا"),
            proposed_by=actor,
            proposed_at=timezone.now(),
        )


def decide_commercial_exception(
    *,
    organization: Organization,
    actor: User,
    exception: CommercialException,
    approved: bool,
    reason: str,
) -> CommercialException:
    with transaction.atomic():
        exception = (
            CommercialException.objects.select_for_update()
            .select_related("commercial_scope__rfq_version__rfq__project")
            .get(pk=exception.pk, organization=organization)
        )
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_APPROVE_EXCEPTION,
            scope=exception.commercial_scope,
        )
        if exception.status != CommercialExceptionStatus.PROPOSED:
            return exception
        policy = resolve_active_tenant_policy(
            organization=organization,
            policy_code=RFQ_EXCEPTION_SELF_APPROVAL_POLICY_CODE,
        )
        validate_policy_for_consumer(
            policy_version=policy,
            consumer=EXCEPTION_APPROVAL_CONSUMER,
            expected_policy_code=RFQ_EXCEPTION_SELF_APPROVAL_POLICY_CODE,
        )
        if (
            actor.pk == exception.proposed_by_id
            and not policy.parameters["allow_self_approval"]
        ):
            raise PermissionDenied("سیاست Tenant خودتأییدی استثنا را مجاز نمی‌داند.")
        result = CommercialException.objects.create(
            organization=organization,
            quote_revision=exception.quote_revision,
            commercial_scope=exception.commercial_scope,
            catalogue_version=1,
            code=exception.code,
            evidence=exception.evidence,
            proposed_by=exception.proposed_by,
            proposed_at=exception.proposed_at,
            status=CommercialExceptionStatus.APPROVED
            if approved
            else CommercialExceptionStatus.REJECTED,
            decided_by=actor,
            decided_at=timezone.now(),
            decision_reason=_text(reason, "دلیل تصمیم"),
            approval_policy_version=policy,
            supersedes=exception,
        )
        record_audit_event(
            action=AuditAction.RFQ_COMMERCIAL_EXCEPTION_DECIDED,
            entity_type="commercial_exception",
            entity_id=result.pk,
            organization=organization,
            actor=actor,
            metadata={
                "predecessor_id": str(exception.pk),
                "approved": approved,
                "policy_version_id": str(policy.pk),
                "content_recorded": False,
            },
        )
        return result


def withdraw_commercial_exception(
    *,
    organization: Organization,
    actor: User,
    exception: CommercialException,
    reason: str,
) -> CommercialException:
    """Append a withdrawal; a proposal is never edited or deleted."""
    with transaction.atomic():
        exception = (
            CommercialException.objects.select_for_update()
            .select_related("commercial_scope__rfq_version__rfq__project")
            .get(pk=exception.pk, organization=organization)
        )
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_PREPARE_COMPARISON,
            scope=exception.commercial_scope,
        )
        if exception.status != CommercialExceptionStatus.PROPOSED:
            raise ValueError("فقط استثنای پیشنهادی قابل پس‌گیری است.")
        existing = exception.superseded_by.select_for_update().first()
        if existing is not None:
            return existing
        return CommercialException.objects.create(
            organization=organization,
            quote_revision=exception.quote_revision,
            commercial_scope=exception.commercial_scope,
            catalogue_version=1,
            code=exception.code,
            evidence=exception.evidence,
            proposed_by=exception.proposed_by,
            proposed_at=exception.proposed_at,
            status=CommercialExceptionStatus.WITHDRAWN,
            decided_by=actor,
            decided_at=timezone.now(),
            decision_reason=_text(reason, "دلیل پس‌گیری"),
            supersedes=exception,
        )


def prepare_sourcing_award(
    *,
    organization: Organization,
    actor: User,
    comparison: CommercialComparison,
    outcome: str,
    allocations: list[dict[str, Any]],
    reason: str,
    evidence: str,
    idempotency_key: str,
    tie_resolution: bool = False,
) -> SourcingAwardPreparation:
    key = _key(idempotency_key)
    with transaction.atomic():
        comparison = (
            CommercialComparison.objects.select_for_update()
            .select_related("commercial_scope__rfq_version__rfq__project")
            .get(pk=comparison.pk, organization=organization)
        )
        scope = comparison.commercial_scope
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_PREPARE_SOURCING_AWARD,
            scope=scope,
        )
        if not comparison.finalized_at:
            raise PermissionDenied("انتخاب فقط پس از مقایسه نهایی مجاز است.")
        if outcome not in SourcingAwardOutcome.values:
            raise ValueError("نتیجه انتخاب معتبر نیست.")
        if (
            comparison.status == CommercialComparisonStatus.TIE_REVIEW_REQUIRED
            and outcome == SourcingAwardOutcome.AWARDED
            and not tie_resolution
        ):
            raise PermissionDenied("تساوی فقط با تصمیم صریح و مستند قابل انتخاب است.")
        if outcome == SourcingAwardOutcome.NO_AWARD and allocations:
            raise ValueError("بدون انتخاب نمی‌تواند تخصیص داشته باشد.")
        payload = {
            "comparison": str(comparison.pk),
            "outcome": outcome,
            "allocations": allocations,
            "reason": reason,
            "evidence": evidence,
            "tie_resolution": tie_resolution,
        }
        fingerprint = _fingerprint(payload)
        existing = (
            SourcingAwardPreparation.objects.select_for_update()
            .filter(comparison=comparison, idempotency_key=key)
            .first()
        )
        if existing:
            if existing.payload_fingerprint != fingerprint:
                raise ValueError(
                    "کلید یکتا با آماده‌سازی انتخاب متفاوت استفاده شده است."
                )
            return existing
        allocation_rows: list[tuple[CommercialComparisonInput, Decimal]] = []
        seen: set[object] = set()
        total = Decimal(0)
        for row in allocations:
            item = CommercialComparisonInput.objects.get(
                pk=row["comparison_input_id"],
                comparison=comparison,
                organization=organization,
            )
            if item.pk in seen:
                raise ValueError("ورودی انتخاب نباید تکرار شود.")
            seen.add(item.pk)
            quantity = Decimal(str(row["quantity"]))
            if quantity <= 0:
                raise ValueError("تخصیص باید مثبت باشد.")
            total += quantity
            allocation_rows.append((item, quantity))
        if total > scope.required_quantity:
            raise ValueError("تخصیص از مقدار RFQ بیشتر است.")
        if outcome == SourcingAwardOutcome.AWARDED and not allocation_rows:
            raise ValueError("انتخاب نیازمند تخصیص است.")
        if len(allocation_rows) > 1 and not scope.allows_split_award:
            raise PermissionDenied("RFQ انتخاب چندگانه را مجاز نمی‌داند.")
        if scope.scope_type == "lot" and total != scope.required_quantity:
            raise PermissionDenied("بسته غیرقابل‌تقسیم باید کامل انتخاب شود.")
        prep = SourcingAwardPreparation.objects.create(
            organization=organization,
            comparison=comparison,
            outcome=outcome,
            prepared_by=actor,
            prepared_at=timezone.now(),
            reason=_text(reason, "دلیل انتخاب"),
            evidence=_text(evidence, "شاهد انتخاب"),
            tie_resolution=tie_resolution,
            idempotency_key=key,
            payload_fingerprint=fingerprint,
        )
        for item, quantity in allocation_rows:
            SourcingAwardPreparationAllocation.objects.create(
                organization=organization,
                preparation=prep,
                comparison_input=item,
                quantity=quantity,
            )
        record_audit_event(
            action=AuditAction.RFQ_SOURCING_AWARD_PREPARED,
            entity_type="sourcing_award_preparation",
            entity_id=prep.pk,
            organization=organization,
            actor=actor,
            metadata={
                "comparison_id": str(comparison.pk),
                "outcome": outcome,
                "allocation_count": len(allocation_rows),
                "content_recorded": False,
            },
        )
        return prep


def finalize_sourcing_award(
    *,
    organization: Organization,
    actor: User,
    preparation: SourcingAwardPreparation,
    supersedes: SourcingAward | None = None,
) -> SourcingAward:
    with transaction.atomic():
        prep = (
            SourcingAwardPreparation.objects.select_for_update()
            .select_related(
                "comparison__commercial_scope__rfq_version__rfq__project", "prepared_by"
            )
            .get(pk=preparation.pk, organization=organization)
        )
        scope = prep.comparison.commercial_scope
        _membership(
            organization=organization,
            actor=actor,
            permission=BusinessPermissionCode.RFQ_QUOTES_FINALIZE_SOURCING_AWARD,
            scope=scope,
        )
        existing = (
            SourcingAward.objects.select_for_update().filter(preparation=prep).first()
        )
        if existing:
            return existing
        # Lock the comparison as the governing award scope.  A preparation row
        # lock alone serializes retries of that one preparation but leaves two
        # different preparations able to over-allocate the same RFQ scope.
        governing_comparison = CommercialComparison.objects.select_for_update().get(
            pk=prep.comparison_id, organization=organization
        )
        governing_award = (
            SourcingAward.objects.filter(
                comparison=governing_comparison, superseded_by__isnull=True
            )
            .first()
        )
        if governing_award is not None:
            if supersedes is None:
                raise ValueError("برای دامنه انتخاب، رکورد نهایی حاکم از پیش وجود دارد.")
            if governing_award.pk != supersedes.pk:
                raise ValueError("اصلاح انتخاب باید رکورد نهایی حاکم را جانشین کند.")
        policy = resolve_active_tenant_policy(
            organization=organization,
            policy_code=RFQ_SOURCING_AWARD_SELF_FINALIZATION_POLICY_CODE,
        )
        validate_policy_for_consumer(
            policy_version=policy,
            consumer=AWARD_FINALIZATION_CONSUMER,
            expected_policy_code=RFQ_SOURCING_AWARD_SELF_FINALIZATION_POLICY_CODE,
        )
        if (
            actor.pk == prep.prepared_by_id
            and not policy.parameters["allow_self_approval"]
        ):
            raise PermissionDenied("سیاست Tenant خودنهایی‌سازی انتخاب را مجاز نمی‌داند.")
        if EvaluatorConflictDeclaration.objects.filter(
            appointment__comparison=prep.comparison,
            appointment__membership__user=actor,
            disposition=CommercialExceptionStatus.PROPOSED,
            superseded_by__isnull=True,
        ).exists():
            raise PermissionDenied(
                "عامل دارای تعارض حل‌نشده نمی‌تواند انتخاب را نهایی کند."
            )
        if supersedes is not None and (
            supersedes.organization_id != organization.pk
            or supersedes.comparison.commercial_scope_id != scope.pk
        ):
            raise PermissionDenied("جانشین انتخاب خارج از دامنه است.")
        total = prep.allocations.aggregate(value=Sum("quantity"))["value"] or Decimal(0)
        unawarded = (
            scope.required_quantity
            if prep.outcome == SourcingAwardOutcome.NO_AWARD
            else scope.required_quantity - total
        )
        award = SourcingAward.objects.create(
            organization=organization,
            preparation=prep,
            comparison=prep.comparison,
            outcome=prep.outcome,
            finalized_by=actor,
            finalized_at=timezone.now(),
            finalization_policy_version=policy,
            reason=prep.reason,
            evidence=prep.evidence,
            unawarded_quantity=unawarded,
            supersedes=supersedes,
        )
        for allocation in prep.allocations.select_related("comparison_input"):
            SourcingAwardAllocation.objects.create(
                organization=organization,
                award=award,
                comparison_input=allocation.comparison_input,
                quote_revision=allocation.comparison_input.quote_revision,
                quantity=allocation.quantity,
            )
        record_audit_event(
            action=AuditAction.RFQ_SOURCING_AWARD_FINALIZED,
            entity_type="sourcing_award",
            entity_id=award.pk,
            organization=organization,
            actor=actor,
            metadata={
                "comparison_id": str(prep.comparison_id),
                "outcome": award.outcome,
                "policy_version_id": str(policy.pk),
                "self_finalized": actor.pk == prep.prepared_by_id,
                "downstream_objects_created": False,
                "content_recorded": False,
            },
        )
        return award
