"""Manual AP/AR write-offs and the Human-approved atomic correction contract."""

from datetime import date
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.accounting.recognition_models import SourceRecognitionDraft
from apps.accounting.recognition_services import (
    _target_matches,
    prepare_source_recognition,
)
from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    PlatformPolicyVersion,
)
from apps.organizations.policy_services import resolve_active_tenant_policy
from apps.organizations.policy_specs import (
    SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE,
    validate_policy_for_consumer,
)

from .accounting_sources import (
    _pin,
    require_source_visibility,
    validate_active_obligation,
)
from .models import (
    Obligation,
    WriteOffCorrection,
    WriteOffDecision,
    WriteOffProposal,
    WriteOffReversal,
)
from .services import (
    _amounts_as_of,
    _canonical_hash,
    _lock_membership,
    _lock_organization,
    _require_unreversed_source,
)


def _authority(
    organization: Organization, actor: User, obligation: Obligation, permission: str
) -> OrganizationMembership:
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=obligation.project,
        message="Explicit scoped AP/AR authority is required.",
    )
    require_source_visibility(organization, actor, obligation)
    return _lock_membership(organization=organization, membership=membership)


def _policy(
    organization: Organization,
    maker: OrganizationMembership,
    actor: OrganizationMembership,
    *,
    reverse: bool = False,
) -> dict:
    version = resolve_active_tenant_policy(
        organization=organization,
        policy_code=SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE,
    )
    # Tenant configuration changes share the organization lock. Pin the global
    # published version as well, so retirement cannot race an accepted action.
    PlatformPolicyVersion.objects.select_for_update().get(pk=version.pk)
    version = resolve_active_tenant_policy(
        organization=organization,
        policy_code=SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE,
    )
    validate_policy_for_consumer(
        policy_version=version,
        expected_policy_code=SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE,
        consumer="subledgers.writeoff.reverse"
        if reverse
        else "subledgers.writeoff.approve",
    )
    # Q03 A-Revised: do not silently classify write-offs as Protected or add
    # mandatory independence when the effective, explicitly selected policy allows it.
    if maker.pk == actor.pk and not version.parameters["allow_self_approval"]:
        raise PermissionDenied("The effective policy does not permit Self-Approval.")
    return {
        "policy_id": str(version.policy_id),
        "policy_version_id": str(version.pk),
        "version": version.version,
        "parameters": version.parameters,
        "self_approval_used": maker.pk == actor.pk,
        "maker_membership": str(maker.pk),
        "actor_membership": str(actor.pk),
    }


def _obligation(organization: Organization, identity: UUID) -> Obligation:
    try:
        return (
            Obligation.objects.select_for_update(of=("self",))
            .select_related("project", "party", "control_account_mapping")
            .get(pk=identity, organization=organization)
        )
    except Obligation.DoesNotExist as exc:
        raise PermissionDenied("Source is outside the active tenant.") from exc


def _capacity(obligation: Obligation, effective_date: date) -> None:
    """Prove the existing cap at every affected chronological boundary."""
    points = {effective_date}
    for allocation in obligation.settlement_allocations.select_related("reversal"):
        points.add(allocation.effective_date)
        reversal = getattr(allocation, "reversal", None)
        if reversal:
            points.add(reversal.effective_date)
    for proposal in obligation.write_off_proposals.filter(
        decision__decision="approved"
    ).select_related("decision__reversal"):
        points.add(proposal.effective_date)
        reversal = getattr(proposal.decision, "reversal", None)
        if reversal:
            points.add(reversal.effective_date)
    for cutoff in sorted(point for point in points if point >= effective_date):
        settled, written = _amounts_as_of(obligation, cutoff)
        if settled + written > obligation.original_amount or written < Decimal(0):
            raise ValidationError(
                "Write-off/settlement capacity would be exceeded at a cutoff."
            )


def max_writeoff_exposure(
    obligation: Obligation, *, on_or_after: date | None = None
) -> Decimal:
    """Reserve existing AP allocation capacity through future write-off boundaries."""
    if on_or_after is None:
        from apps.organizations.services import get_organization_settings

        configured = get_organization_settings(organization=obligation.organization)
        on_or_after = timezone.localdate(timezone=ZoneInfo(configured.timezone))
    points = {on_or_after}
    for proposal in obligation.write_off_proposals.filter(
        decision__decision="approved"
    ).select_related("decision__reversal"):
        points.add(proposal.effective_date)
        reversal = getattr(proposal.decision, "reversal", None)
        if reversal:
            points.add(reversal.effective_date)
    return max(
        (
            _amounts_as_of(obligation, cutoff)[1]
            for cutoff in points
            if cutoff >= on_or_after
        ),
        default=Decimal(0),
    )


def _audit(organization, actor, action, identity, metadata):
    record_audit_event(
        organization=organization,
        actor=actor,
        action=action,
        entity_type="subledgers.WriteOffDecision",
        entity_id=str(identity),
        metadata=metadata,
    )


def _failure(organization, actor, identity, exc):
    # Never copy exception text, amounts, reviewer data or foreign source facts.
    source = WriteOffProposal.objects.filter(
        pk=identity, organization=organization
    ).first()
    if source is None:
        source = WriteOffDecision.objects.filter(
            pk=identity, organization=organization
        ).first()
    if (
        source is not None
        and organization.memberships.filter(user=actor, status="active").exists()
    ):
        _audit(
            organization,
            actor,
            AuditAction.SUBLEDGER_WRITEOFF_FAILED,
            identity,
            {"failure_class": type(exc).__name__, "retry_requires_revalidation": True},
        )


def _effect(
    organization: Organization, decision: WriteOffDecision
) -> SourceRecognitionDraft:
    try:
        effect = (
            SourceRecognitionDraft.objects.select_for_update(of=("self",))
            .select_related("journal", "mapping")
            .get(
                organization=organization,
                source_kind="writeoff",
                source_uuid=decision.pk,
            )
        )
    except SourceRecognitionDraft.DoesNotExist as exc:
        raise ValidationError(
            "Exact original Accounting occurrence is unavailable."
        ) from exc
    if not _target_matches(effect):
        raise ValidationError(
            "Original Accounting evidence is consumed or has drifted."
        )
    return effect


def _make_decision(
    *, organization, actor, membership, proposal, approve, reason, correction=False
) -> WriteOffDecision:
    if not reason.strip():
        raise ValidationError("A decision reason is required.")
    obligation = _obligation(organization, proposal.obligation_id)
    policy = _policy(organization, proposal.proposed_by, membership)
    if proposal.corrects_id and approve and not correction:
        raise ValidationError(
            "A replacement must be approved through the atomic correction set."
        )
    _require_unreversed_source(obligation)
    validate_active_obligation(obligation)
    if proposal.effective_date < obligation.recognized_on:
        raise ValidationError("Write-off date predates source recognition.")
    decision = WriteOffDecision(
        organization=organization,
        proposal=proposal,
        decision="approved" if approve else "rejected",
        reason=reason.strip(),
        decided_by=membership,
        authority_evidence={
            "policy": policy,
            "source": _pin(obligation),
            "proposal_hash": proposal.payload_hash,
        },
    )
    decision._writeoff_service = True
    decision.save(force_insert=True)
    if approve:
        _capacity(obligation, proposal.effective_date)
        prepare_source_recognition(
            organization=organization,
            actor=actor,
            source_kind="writeoff",
            source_id=decision.pk,
            accounting_date=proposal.effective_date,
        )
    _audit(
        organization,
        actor,
        AuditAction.SUBLEDGER_WRITEOFF_DECIDED,
        decision.pk,
        {
            "proposal_id": str(proposal.pk),
            "decision": decision.decision,
            "policy": policy,
            "source_version": obligation.source_version,
        },
    )
    return decision


def decide_write_off(
    *,
    organization: Organization,
    actor: User,
    proposal: WriteOffProposal,
    approve: bool,
    reason: str,
) -> WriteOffDecision:
    try:
        with transaction.atomic():
            if type(approve) is not bool or not isinstance(reason, str):
                raise ValidationError(
                    "Explicit boolean decision and text reason are required."
                )
            organization = _lock_organization(organization)
            try:
                proposal = (
                    WriteOffProposal.objects.select_for_update(of=("self",))
                    .select_related("proposed_by", "obligation__project")
                    .get(pk=proposal.pk, organization=organization)
                )
            except WriteOffProposal.DoesNotExist as exc:
                raise PermissionDenied(
                    "Proposal is outside the active tenant."
                ) from exc
            obligation = _obligation(organization, proposal.obligation_id)
            membership = _authority(
                organization, actor, obligation, P.SUBLEDGERS_WRITEOFFS_APPROVE
            )
            _policy(organization, proposal.proposed_by, membership)
            existing = getattr(proposal, "decision", None)
            if existing:
                if (
                    existing.decision != ("approved" if approve else "rejected")
                    or existing.reason != reason.strip()
                    or existing.decided_by_id != membership.pk
                ):
                    raise ValidationError("Conflicting write-off decision replay.")
                if approve:
                    _effect(organization, existing)
                return existing
            return _make_decision(
                organization=organization,
                actor=actor,
                membership=membership,
                proposal=proposal,
                approve=approve,
                reason=reason,
            )
    except (
        ValidationError,
        PermissionDenied,
        DatabaseError,
        ObjectDoesNotExist,
    ) as exc:
        _failure(organization, actor, proposal.pk, exc)
        raise


def correct_write_off(
    *,
    organization: Organization,
    actor: User,
    original: WriteOffDecision,
    effective_date: date,
    reason: str,
    idempotency_key: str,
    replacement: WriteOffProposal | None = None,
) -> WriteOffCorrection:
    """Exact full inverse and optional approved replacement, all-or-nothing."""
    identity = original.pk
    try:
        with transaction.atomic():
            organization = _lock_organization(organization)
            try:
                original = (
                    WriteOffDecision.objects.select_for_update(of=("self",))
                    .select_related(
                        "proposal__proposed_by", "proposal__obligation__project"
                    )
                    .get(pk=identity, organization=organization)
                )
            except WriteOffDecision.DoesNotExist as exc:
                raise PermissionDenied(
                    "Original is outside the active tenant."
                ) from exc
            obligation = _obligation(organization, original.proposal.obligation_id)
            membership = _authority(
                organization, actor, obligation, P.SUBLEDGERS_WRITEOFFS_REVERSE
            )
            reversal_policy = _policy(
                organization, original.proposal.proposed_by, membership, reverse=True
            )
            if not isinstance(reason, str) or not isinstance(idempotency_key, str):
                raise ValidationError("Correction reason and identity must be text.")
            reason, idempotency_key = reason.strip(), idempotency_key.strip()
            if not reason or not idempotency_key or len(idempotency_key) > 120:
                raise ValidationError(
                    "Explicit correction reason and identity are required."
                )
            if (
                type(effective_date) is not date
                or effective_date < original.proposal.effective_date
            ):
                raise ValidationError(
                    "Correction date must preserve the original effective boundary."
                )
            payload = {
                "original": str(identity),
                "replacement": str(replacement.pk) if replacement else None,
                "date": effective_date.isoformat(),
                "reason": reason,
                "actor": str(membership.pk),
            }
            payload_hash = _canonical_hash(payload)
            existing = (
                WriteOffCorrection.objects.select_for_update()
                .filter(organization=organization, idempotency_key=idempotency_key)
                .first()
            )
            if existing:
                if existing.payload_hash != payload_hash:
                    raise ValidationError("Conflicting correction identity/payload.")
                if existing.original_id != original.pk:
                    raise ValidationError("Retained correction source does not match.")
                _pin(obligation)
                if replacement is not None:
                    _authority(
                        organization, actor, obligation, P.SUBLEDGERS_WRITEOFFS_APPROVE
                    )
                    retained_replacement = existing.replacement.proposal
                    if retained_replacement.pk != replacement.pk:
                        raise ValidationError("Retained replacement does not match.")
                    _policy(organization, retained_replacement.proposed_by, membership)
                for value in existing.accounting_evidence.values():
                    if value is not None:
                        effect = SourceRecognitionDraft.objects.select_related(
                            "journal", "mapping"
                        ).get(organization=organization, pk=value)
                        if not _target_matches(effect):
                            raise ValidationError(
                                "Retained Accounting target drift prevents replay."
                            )
                        prepare_source_recognition(
                            organization=organization,
                            actor=actor,
                            source_kind=effect.source_kind,
                            source_id=effect.source_uuid,
                            accounting_date=effect.journal.accounting_date,
                        )
                return existing
            if original.decision != "approved" or hasattr(original, "reversal"):
                raise ValidationError(
                    "Only an active approved write-off can be corrected once."
                )
            _require_unreversed_source(obligation)
            validate_active_obligation(obligation)
            original_effect = _effect(organization, original)
            # Locks/pins the original source and Accounting draft, including hash
            # and existing prepare permission validation, without a new effect.
            prepare_source_recognition(
                organization=organization,
                actor=actor,
                source_kind="writeoff",
                source_id=original.pk,
            )
            if replacement is not None:
                try:
                    replacement = (
                        WriteOffProposal.objects.select_for_update(of=("self",))
                        .select_related("proposed_by")
                        .get(pk=replacement.pk, organization=organization)
                    )
                except WriteOffProposal.DoesNotExist as exc:
                    raise PermissionDenied(
                        "Replacement is outside the active tenant."
                    ) from exc
                _authority(
                    organization, actor, obligation, P.SUBLEDGERS_WRITEOFFS_APPROVE
                )
                if (
                    replacement.corrects_id != original.pk
                    or replacement.obligation_id != obligation.pk
                    or replacement.effective_date != effective_date
                    or hasattr(replacement, "decision")
                ):
                    raise ValidationError(
                        "Replacement source/date/predecessor must match exactly."
                    )
                _policy(organization, replacement.proposed_by, membership)
            reversal = WriteOffReversal(
                organization=organization,
                decision=original,
                effective_date=effective_date,
                reason=reason,
                reversed_by=membership,
                authority_evidence={
                    "policy": reversal_policy,
                    "source": _pin(obligation),
                    "original_effect": str(original_effect.pk),
                },
            )
            reversal._writeoff_service = True
            reversal.save(force_insert=True)
            reversal_effect = prepare_source_recognition(
                organization=organization,
                actor=actor,
                source_kind="writeoff_reversal",
                source_id=reversal.pk,
                accounting_date=effective_date,
            )
            replacement_decision = None
            if replacement is not None:
                replacement_decision = _make_decision(
                    organization=organization,
                    actor=actor,
                    membership=membership,
                    proposal=replacement,
                    approve=True,
                    reason=reason,
                    correction=True,
                )
            _capacity(obligation, effective_date)
            replacement_effect = (
                _effect(organization, replacement_decision)
                if replacement_decision
                else None
            )
            result = WriteOffCorrection(
                organization=organization,
                original=original,
                reversal=reversal,
                replacement=replacement_decision,
                actor=membership,
                effective_date=effective_date,
                reason=reason,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                source_snapshot={
                    **_pin(obligation),
                    "original_decision": str(original.pk),
                    "original_amount": str(original.proposal.amount),
                    "replacement_amount": str(replacement.amount)
                    if replacement
                    else None,
                },
                policy_evidence={
                    "reversal": reversal_policy,
                    "replacement": replacement_decision.authority_evidence
                    if replacement_decision
                    else None,
                },
                accounting_evidence={
                    "original": str(original_effect.pk),
                    "reversal": str(reversal_effect.pk),
                    "replacement": str(replacement_effect.pk)
                    if replacement_effect
                    else None,
                },
            )
            result._writeoff_service = True
            result.save(force_insert=True)
            _audit(
                organization,
                actor,
                AuditAction.SUBLEDGER_WRITEOFF_CORRECTED,
                original.pk,
                {
                    "correction_id": str(result.pk),
                    "reversal_id": str(reversal.pk),
                    "replacement_id": str(replacement_decision.pk)
                    if replacement_decision
                    else None,
                    "source_version": obligation.source_version,
                    "effective_date": effective_date.isoformat(),
                    "policy": reversal_policy,
                    "accounting": result.accounting_evidence,
                },
            )
            return result
    except (
        ValidationError,
        PermissionDenied,
        DatabaseError,
        ObjectDoesNotExist,
    ) as exc:
        _failure(organization, actor, identity, exc)
        raise


@transaction.atomic
def requester_writeoff_status(
    *, organization: Organization, actor: User, proposal_id: UUID
) -> dict:
    organization = _lock_organization(organization)
    try:
        proposal = WriteOffProposal.objects.select_related("obligation__project").get(
            pk=proposal_id, organization=organization, proposed_by__user=actor
        )
    except WriteOffProposal.DoesNotExist as exc:
        raise PermissionDenied("Own proposal is unavailable.") from exc
    _authority(organization, actor, proposal.obligation, P.SUBLEDGERS_WRITEOFFS_PROPOSE)
    decision = getattr(proposal, "decision", None)
    state = decision.decision if decision else "proposed"
    if decision and hasattr(decision, "reversal"):
        state = "reversed"
    return {
        "proposal_id": str(proposal.pk),
        "status": state,
        "amount": str(proposal.amount),
        "effective_date": proposal.effective_date.isoformat(),
    }
