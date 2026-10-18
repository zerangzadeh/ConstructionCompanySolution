"""Closed PD-030 source families; AP/AR supplies facts, Accounting owns L2 drafts."""

from dataclasses import asdict
from uuid import UUID

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError

from apps.accounting.recognition_models import SourceRecognitionDraft
from apps.accounting.recognition_sources import SourceEvidence, _row, digest
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P

from .models import (
    Obligation,
    SupplierInvoiceAPReversal,
    WriteOffDecision,
    WriteOffReversal,
)
from .services import _SOURCE_RESOLVERS, _canonical_hash

OBLIGATION_KINDS = {
    "ar_claim": (
        "billing.progress_claim.v1",
        "billing.ProgressClaim",
        "receivable_recognized",
    ),
    "ap_certificate": (
        "billing.payable_certificate.v1",
        "billing.PayableCertificate",
        "payable_recognized",
    ),
    "ap_invoice": (
        "procurement.supplier_invoice_match.v1",
        "subledgers.SupplierInvoiceMatch",
        "payable_recognized",
    ),
}


def _pin(obligation: Obligation) -> dict:
    if (
        obligation.source_hash != _canonical_hash(obligation.source_snapshot)
        or not obligation.control_account_id
        or not obligation.control_account_mapping_id
        or obligation.control_account_mapping.organization_id
        != obligation.organization_id
        or obligation.control_account_mapping.control_account_id
        != obligation.control_account_id
        or obligation.control_account_mapping.source_kind != obligation.source_kind
        or obligation.control_account_mapping.direction != obligation.direction
    ):
        raise ValidationError(
            "Retained source/control-account evidence does not match."
        )
    return {
        "obligation_id": str(obligation.pk),
        "source_kind": obligation.source_kind,
        "source_uuid": str(obligation.source_uuid),
        "source_version": obligation.source_version,
        "source_line_key": obligation.source_line_key,
        "source_hash": obligation.source_hash,
        "source_snapshot": obligation.source_snapshot,
        "control_account_id": str(obligation.control_account_id),
        "control_mapping_id": str(obligation.control_account_mapping_id),
        "direction": obligation.direction,
        "original_amount": str(obligation.original_amount),
        "currency": obligation.currency,
        "recognized_on": obligation.recognized_on.isoformat(),
        "project_id": str(obligation.project_id) if obligation.project_id else None,
        "party_id": str(obligation.party_id) if obligation.party_id else None,
        "payload_hash": obligation.payload_hash,
    }


def validate_active_obligation(obligation: Obligation) -> None:
    resolver = _SOURCE_RESOLVERS.get(obligation.source_kind)
    if resolver is None:
        raise ValidationError("Approved native source contract is unavailable.")
    current = resolver(
        obligation.organization,
        obligation.source_uuid,
        obligation.source_version,
        obligation.source_line_key,
    )
    retained = {
        "amount": obligation.original_amount,
        "direction": obligation.direction,
        "currency": obligation.currency,
        "recognized_on": obligation.recognized_on,
        "due_date": obligation.due_date,
        "party_id": obligation.party_id,
        "project_id": obligation.project_id,
        "contract_id": obligation.contract_id,
        "source_status": obligation.source_status,
        "source_snapshot": obligation.source_snapshot,
    }
    if _canonical_hash(asdict(current)) != obligation.payload_hash or any(
        getattr(current, name) != value for name, value in retained.items()
    ):
        raise ValidationError("Native source/version drifted from the AP/AR pin.")


def require_source_visibility(organization, actor, obligation):
    if obligation.source_kind == "payroll.liability.v1":
        for code in (P.PAYROLL_RESULTS_VIEW, P.SUBLEDGERS_PAYROLL_VIEW):
            require_business_permission(
                user=actor,
                organization=organization,
                permission=code,
                project=obligation.project,
                message="Sensitive Payroll AP source authority is required.",
            )


def _scope(organization, actor, obligation, permission):
    for code in (P.SUBLEDGERS_VIEW, permission):
        require_business_permission(
            user=actor,
            organization=organization,
            permission=code,
            project=obligation.project,
            message="AP/AR source object scope is required.",
        )
    require_source_visibility(organization, actor, obligation)


def read_subledger_source(
    *,
    organization,
    actor,
    kind: str,
    identity: UUID,
    permission: str,
    historical_event: str | None = None,
) -> SourceEvidence:
    try:
        if kind in OBLIGATION_KINDS:
            source_kind, label, event = OBLIGATION_KINDS[kind]
            obligation = (
                Obligation.objects.select_for_update(of=("self",))
                .select_related("project", "party", "control_account_mapping")
                .get(
                    organization=organization,
                    source_kind=source_kind,
                    source_uuid=identity,
                    source_line_key="",
                )
            )
            _scope(organization, actor, obligation, permission)
            native = (
                apps.get_model(label)
                .objects.select_for_update()
                .get(organization=organization, pk=identity)
            )
            pin = _pin(obligation)
            reversal = obligation.source_reversal_evidence
            previous = None
            if reversal is not None and historical_event != event:
                # Only an AP-owned finalized native source reversal qualifies;
                # an unapproved Billing cancellation/request is never substituted.
                event, occurred, previous = (
                    "reversed",
                    reversal.effective_date,
                    identity,
                )
                pin["source_reversal"] = {
                    "id": str(reversal.pk),
                    "date": occurred.isoformat(),
                    "reason": reversal.reason,
                    "actor": str(reversal.reversed_by_id),
                }
            else:
                if reversal is None:
                    validate_active_obligation(obligation)
                # For reversed history, the immutable AP pin and retained native
                # reversal preserve the original occurrence without reactivation.
                occurred = obligation.recognized_on
                if kind == "ap_invoice":
                    prior = (
                        SupplierInvoiceAPReversal.objects.filter(
                            organization=organization, replacement_match=native
                        )
                        .select_related("obligation")
                        .first()
                    )
                    if (
                        prior
                        and SourceRecognitionDraft.objects.filter(
                            organization=organization,
                            source_kind=kind,
                            source_uuid=prior.obligation.source_uuid,
                            is_reversal=False,
                        ).exists()
                    ):
                        previous = prior.obligation.source_uuid
            row = _row(
                obligation,
                "amount",
                obligation.original_amount,
                project=obligation.project,
                party=obligation.party,
            )
            return SourceEvidence(
                kind,
                identity,
                event,
                f"{obligation.source_version}:{obligation.source_hash}",
                occurred,
                obligation.currency,
                (row,),
                pin,
                previous_id=previous,
                reversal=event == "reversed",
            )

        model = WriteOffReversal if kind == "writeoff_reversal" else WriteOffDecision
        source = model.objects.select_for_update(of=("self",)).get(
            organization=organization, pk=identity
        )
        decision = source.decision if kind == "writeoff_reversal" else source
        proposal = decision.proposal
        obligation = (
            Obligation.objects.select_for_update(of=("self",))
            .select_related("project", "party", "control_account_mapping")
            .get(organization=organization, pk=proposal.obligation_id)
        )
        _scope(organization, actor, obligation, permission)
        if decision.decision != "approved" or not decision.authority_evidence:
            raise ValidationError(
                "An approved write-off with retained authority is required."
            )
        pin = _pin(obligation)
        pin.update(
            {
                "proposal_id": str(proposal.pk),
                "decision_id": str(decision.pk),
                "writeoff_version": 1,
                "amount": str(proposal.amount),
                "reason": proposal.reason,
                "decision_reason": decision.reason,
                "decision_actor": str(decision.decided_by_id),
                "authority": decision.authority_evidence,
            }
        )
        previous = None
        if proposal.corrects_id:
            previous = proposal.corrects_id
        reversal = kind == "writeoff_reversal"
        if reversal:
            event, occurred, previous = "reversed", source.effective_date, decision.pk
            pin["reversal"] = {
                "id": str(source.pk),
                "date": occurred.isoformat(),
                "reason": source.reason,
                "actor": str(source.reversed_by_id),
                "authority": source.authority_evidence,
            }
        else:
            event = f"{obligation.direction}_written_off"
            occurred = proposal.effective_date
            if (
                hasattr(decision, "reversal")
                and not SourceRecognitionDraft.objects.filter(
                    organization=organization,
                    source_kind="writeoff",
                    source_uuid=decision.pk,
                ).exists()
            ):
                raise ValidationError(
                    "A reversed occurrence cannot acquire a new original effect."
                )
        row = _row(
            proposal,
            "amount",
            proposal.amount,
            project=obligation.project,
            party=obligation.party,
        )
        return SourceEvidence(
            kind,
            identity,
            event,
            "1:" + digest(pin),
            occurred,
            obligation.currency,
            (row,),
            pin,
            previous_id=previous,
            reversal=reversal,
        )
    except ObjectDoesNotExist as exc:
        raise PermissionDenied(
            "Source does not exist in the authorized tenant."
        ) from exc


def validate_control_rows(source: SourceEvidence, rows: list[dict]) -> None:
    control = source.metadata["control_account_id"]
    direction = source.metadata["direction"]
    writeoff = source.kind in {"writeoff", "writeoff_reversal"}
    debit = (direction == "receivable") != writeoff
    if source.reversal:
        debit = not debit
    matches = [row for row in rows if row["account_id"] == control]
    side, other = ("debit", "credit") if debit else ("credit", "debit")
    from decimal import Decimal

    if (
        len(matches) != 1
        or Decimal(matches[0][side]) <= 0
        or Decimal(matches[0][other]) != 0
    ):
        raise ValidationError(
            "Configured rows must use the exact retained directional control account."
        )
