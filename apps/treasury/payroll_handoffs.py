"""INT-A03 L2 requests. Treasury alone owns cash and its native reversals."""

from decimal import Decimal
from uuid import UUID, uuid4

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.payroll.financial_handoff_services import _digest, _source_snapshot
from apps.payroll.models import (
    FinancialHandoffAcknowledgement,
    FinancialHandoffLine,
    FinancialHandoffProposal,
    PayrollRun,
)

from .models import PaymentRequest, PayrollDisbursementReversal, TreasuryMovement
from .services import _lock_organization, cancel_payment_request, create_payment_request


def _source(organization, line_id, *, historical=False):
    try:
        line = FinancialHandoffLine.objects.select_related(
            "proposal__review", "run_employee__project", "employee", "project", "site"
        ).get(pk=line_id, organization=organization)
        proposal = FinancialHandoffProposal.objects.select_for_update().get(
            pk=line.proposal_id, organization=organization
        )
        run = (
            PayrollRun.objects.select_for_update()
            .select_related("period")
            .get(pk=proposal.run_id, organization=organization)
        )
        review = line.proposal.review
    except ObjectDoesNotExist as exc:
        raise ValidationError(
            "Reviewed tenant Payroll payment source required."
        ) from exc
    results = list(run.employee_results.select_for_update().select_related("employee"))
    states = {"finalized", "reversed"} if historical else {"finalized"}
    if (
        proposal.family != "payment"
        or proposal.has_exceptions
        or review.disposition != "accepted"
        or run.status not in states
        or not run.finalized_at
        or not results
        or any(r.status not in states for r in results)
        or _digest(_source_snapshot(run, results)) != proposal.source_digest
        or proposal.currency != run.currency
        or proposal.currency != "IRR"
        or proposal.monetary_policy_snapshot != run.monetary_policy_snapshot
        or line.line_kind != "payment_proposal"
        or line.run_employee.run_id != run.pk
        or line.employee_id != line.run_employee.employee_id
        or line.amount != line.run_employee.net_amount
        or line.project_id != line.run_employee.project_id
        or line.site_id != line.run_employee.site_id
        or sum(proposal.lines.values_list("amount", flat=True), Decimal(0))
        != proposal.total_amount
    ):
        raise ValidationError("Payroll source is unsupported, unreviewed or stale.")
    line.proposal = proposal
    lines = list(proposal.lines.order_by("employee", "created_at"))
    for index, item in enumerate(lines):
        expected_digest = _digest(
            {
                "proposal": str(proposal.pk),
                "index": index,
                "kind": item.line_kind,
                "amount": str(item.amount),
                "lineage": item.source_lineage,
            }
        )
        if item.content_digest != expected_digest:
            raise ValidationError("Payroll line version is inconsistent.")
    return line


@transaction.atomic
def validate_payment_source(request: PaymentRequest) -> FinancialHandoffLine:
    line = _source(request.organization, request.source_payroll_line_id)
    if (
        line.proposal.record_kind == "reversal"
        or line.amount <= 0
        or line.content_digest != request.source_payroll_version
        or line.amount != request.amount
        or line.employee_id != request.employee_id
        or line.project_id != request.project_id
        or line.site_id != request.site_id
        or request.party_id
        or request.currency != line.proposal.currency
    ):
        raise ValidationError("Request must exactly match its Payroll source version.")
    if (
        line.proposal.record_kind == "replacement"
        and not PayrollDisbursementReversal.objects.filter(
            organization=request.organization,
            request__source_payroll_line__proposal_id=line.proposal.predecessor_id,
            request__employee_id=line.employee_id,
        ).exists()
    ):
        raise ValidationError("Replacement requires retained native reversal.")
    return line


def _permission(organization, actor, code, line=None):
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=code,
        project=line.project if line else None,
        site=line.site if line else None,
        message="Explicit Treasury authority required.",
    )


@transaction.atomic
def _consume(*, organization, actor, line_id, reason, reversal_movement=None):
    organization = _lock_organization(organization)
    line = _source(organization, line_id)
    maker = _permission(organization, actor, P.TREASURY_PAYMENT_REQUESTS_CREATE, line)
    if not reason.strip():
        raise ValidationError("A handoff reason is required.")
    if line.proposal.record_kind == "reversal":
        try:
            request = PaymentRequest.objects.select_for_update().get(
                organization=organization,
                source_payroll_line__proposal_id=line.proposal.predecessor_id,
                employee=line.employee,
            )
        except PaymentRequest.DoesNotExist as exc:
            raise ValidationError("Original Treasury request required.") from exc
        existing = PayrollDisbursementReversal.objects.filter(source_line=line).first()
        if existing:
            if existing.reversal_movement_id != getattr(reversal_movement, "pk", None):
                raise ValidationError("Conflicting reversal retry.")
            return existing
        if line.amount != -request.amount:
            raise ValidationError("Exact source reversal amount required.")
        if reversal_movement:
            reversal_movement = TreasuryMovement.objects.select_for_update().get(
                pk=reversal_movement.pk, organization=organization
            )
        if not request.released_movement_id and request.status not in {
            "cancelled",
            "rejected",
        }:
            cancel_payment_request(
                organization=organization,
                actor=actor,
                request=request,
                reason=reason,
            )
            request.refresh_from_db()
        record = PayrollDisbursementReversal(
            organization=organization,
            source_line=line,
            source_version=line.content_digest,
            request=request,
            reversal_movement=reversal_movement,
            recorded_by=maker,
        )
        record.full_clean()
        record.save()
        return record
    if reversal_movement is not None:
        raise ValidationError("Cash reversal only belongs to a reversal source.")
    if line.proposal.predecessor_id:
        # Incremental adjustments remain distinct sources; replacement requires
        # the original cancellation/reversal before another full payment.
        predecessor = PaymentRequest.objects.filter(
            organization=organization,
            source_payroll_line__proposal_id=line.proposal.predecessor_id,
            employee=line.employee,
        ).first()
        if line.proposal.record_kind == "replacement" and (
            predecessor is None or not hasattr(predecessor, "payroll_reversal")
        ):
            raise ValidationError("Replacement requires retained native reversal.")
    return create_payment_request(
        organization=organization,
        actor=actor,
        kind="payroll",
        amount=line.amount,
        purpose=reason,
        idempotency_key=f"payroll:{line.pk}:{line.content_digest[:16]}",
        employee=line.employee,
        project=line.project,
        site=line.site,
        source_payroll_line=line,
    )


def consume_payment_line(
    *,
    organization: Organization,
    actor: User,
    line_id: UUID,
    reason: str,
    reversal_movement: TreasuryMovement | None = None,
) -> PaymentRequest | PayrollDisbursementReversal:
    """Savepoint rollback preserves source; sanitized failure survives outside it."""
    # Do not expose or log a foreign source, or an unauthorized attempt payload.
    _permission(organization, actor, P.TREASURY_PAYMENT_REQUESTS_CREATE)
    line = FinancialHandoffLine.objects.get(pk=line_id, organization=organization)
    try:
        return _consume(
            organization=organization,
            actor=actor,
            line_id=line_id,
            reason=reason,
            reversal_movement=reversal_movement,
        )
    except (ValidationError, DatabaseError) as exc:
        FinancialHandoffAcknowledgement.objects.create(
            organization=organization,
            proposal=line.proposal,
            downstream_reference=f"treasury:failed:{uuid4()}",
            downstream_status="failed",
            acknowledged_source_digest=line.proposal.source_digest,
            acknowledged_amount=Decimal(0),
            recorded_by=actor,
            evidence={
                "consumer": "INT-A03",
                "line": str(line.pk),
                "error_code": type(exc).__name__,
                "retry_requires_validation": True,
            },
        )
        raise


@transaction.atomic
def reconcile_payment_handoff(
    *,
    organization: Organization,
    actor: User,
    proposal_id: UUID,
) -> dict[str, object]:
    organization = _lock_organization(organization)
    _permission(organization, actor, P.TREASURY_VIEW)
    proposal = FinancialHandoffProposal.objects.get(
        pk=proposal_id, organization=organization, family="payment"
    )
    rows = []
    for line in proposal.lines.order_by("pk"):
        request = (
            PaymentRequest.objects.filter(
                organization=organization, source_payroll_line=line
            )
            .select_related("released_movement")
            .first()
        )
        reversal = (
            PayrollDisbursementReversal.objects.filter(
                organization=organization, source_line=line
            )
            .select_related("request")
            .first()
        )
        if reversal:
            request = reversal.request
        issues = []
        try:
            _source(organization, line.pk, historical=True)
        except ValidationError:
            issues.append("SOURCE_INVALID")
        if request is None:
            issues.append("TARGET_MISSING")
        elif not reversal and (
            request.source_payroll_version != line.content_digest
            or request.amount != line.amount
        ):
            issues.append("SOURCE_TARGET_MISMATCH")
        movement = (
            (
                request.released_movement
                or TreasuryMovement.objects.filter(
                    organization=organization, origin_request=request
                ).first()
            )
            if request
            else None
        )
        cash_reversal = (
            TreasuryMovement.objects.filter(reverses=movement).first()
            if movement
            else None
        )
        rows.append(
            {
                "line": str(line.pk),
                "version": line.content_digest,
                "request": str(request.pk) if request else None,
                "status": request.status if request else None,
                "amount": str(line.amount),
                "movement": str(movement.pk) if movement else None,
                "cash_reversal": str(cash_reversal.pk) if cash_reversal else None,
                "source_reversal": str(reversal.pk) if reversal else None,
                "issues": issues,
            }
        )
    return {
        "proposal": str(proposal.pk),
        "source_version": proposal.source_digest,
        "run": str(proposal.run_id),
        "run_status": proposal.run.status,
        "predecessor": str(proposal.predecessor_id)
        if proposal.predecessor_id
        else None,
        "successors": list(proposal.successors.values_list("id", flat=True)),
        "observed_at": timezone.now().isoformat(),
        "projection_only": True,
        "rows": rows,
    }
