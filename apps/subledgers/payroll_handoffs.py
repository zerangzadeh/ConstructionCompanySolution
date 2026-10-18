"""INT-B07 AP-owned L2 drafts; explicit enrollment and retained corrections.

No Payroll write, GL writer, cash effect, implicit mapping or aggregation.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.parties.models import BusinessParty
from apps.payroll.financial_handoff_services import _digest, _source_snapshot
from apps.payroll.models import (
    FinancialHandoffLine,
    FinancialHandoffProposal,
    PayrollReversal,
)

from .models import Obligation, ObligationDirection
from .payroll_models import (
    PayrollAPDraft,
    PayrollAPEnrollment,
    PayrollAPEnrollmentEvent,
    PayrollAPOperation,
    PayrollAPReversal,
)
from .services import (
    ObligationSourceSnapshot,
    _active_settlement_amount,
    _approved_writeoff_amount,
    _canonical_hash,
    _lock_membership,
    _lock_organization,
    recognize_obligation,
    register_source_resolver,
    registered_source_kinds,
)

SOURCE_KIND = "payroll.liability.v1"
CATEGORIES = frozenset(
    {"employee_payable", "statutory_employee_payable", "statutory_employer_payable"}
)


def _require(organization, actor, permission):
    membership = require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="Explicit authorized AP/Payroll access required.",
    )
    return _lock_membership(organization=organization, membership=membership)


def _create(model, **values):
    obj = model(**values)
    obj._ap_service = True
    obj.save()
    return obj


def _audit(organization, actor, action, identity, metadata):
    entity_type = {
        AuditAction.PAYROLL_AP_ENROLLMENT_PREPARED: "subledgers.PayrollAPEnrollment",
        AuditAction.PAYROLL_AP_ENROLLMENT_CHANGED: "subledgers.PayrollAPEnrollmentEvent",
        AuditAction.PAYROLL_AP_FAILED: "payroll.FinancialHandoffProposal",
        AuditAction.PAYROLL_AP_RECONCILED: "payroll.FinancialHandoffProposal",
    }.get(action, "subledgers.PayrollAPOperation")
    record_audit_event(
        organization=organization,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=identity,
        metadata=metadata,
    )


def _read(organization, proposal_id, *, historical=False):
    try:
        proposal = (
            FinancialHandoffProposal.objects.select_for_update(of=("self",))
            .select_related("run__period", "review")
            .get(pk=proposal_id, organization=organization)
        )
        run = (
            type(proposal.run)
            .objects.select_for_update()
            .get(pk=proposal.run_id, organization=organization)
        )
        review = proposal.review
    except ObjectDoesNotExist as exc:
        raise ValidationError(
            "Approved tenant Payroll liability source required."
        ) from exc
    proposal.run = run
    states = {"finalized", "reversed"} if historical else {"finalized"}
    results = list(run.employee_results.select_for_update().select_related("employee"))
    if (
        proposal.family != "liability"
        or proposal.has_exceptions
        or review.disposition != "accepted"
        or run.status not in states
        or not run.finalized_at
        or not results
        or proposal.currency != run.currency
        or proposal.monetary_policy_snapshot != run.monetary_policy_snapshot
        or any(r.status not in states for r in results)
        or _digest(_source_snapshot(run, results)) != proposal.source_digest
    ):
        raise ValidationError(
            "Finalized reviewed Payroll evidence is missing or stale."
        )
    lines = list(
        proposal.lines.select_for_update(of=("self",))
        .select_related("run_employee__project", "statutory_result__calculation")
        .order_by("pk")
    )
    if not lines or sum((x.amount for x in lines), Decimal(0)) != proposal.total_amount:
        raise ValidationError("Payroll proposal totals do not reconcile.")
    rows = []
    for line in lines:
        if (
            line.organization_id != organization.pk
            or line.run_employee.run_id != run.pk
            or line.employee_id != line.run_employee.employee_id
            or line.line_kind not in CATEGORIES
        ):
            raise ValidationError("Unsupported Payroll liability occurrence.")
        if line.line_kind == "employee_payable":
            expected = line.run_employee.net_amount
        else:
            statutory = line.statutory_result
            if (
                statutory is None
                or statutory.calculation.run_id != run.pk
                or statutory.calculation.review.disposition != "accepted"
            ):
                raise ValidationError("Accepted statutory source evidence required.")
            expected = (
                statutory.employee_amount
                if line.line_kind == "statutory_employee_payable"
                else statutory.employer_amount + statutory.other_amount
            )
        if line.amount != expected:
            raise ValidationError(
                "Liability amount disagrees with authoritative Payroll result."
            )
        rows.append(
            {
                "id": str(line.pk),
                "employee": str(line.employee_id),
                "kind": line.line_kind,
                "amount": str(line.amount),
                "digest": line.content_digest,
                "lineage": line.source_lineage,
                "component": line.component_reference,
                "site": str(line.run_employee.site_id)
                if line.run_employee.site_id
                else None,
                "project": str(line.run_employee.project_id)
                if line.run_employee.project_id
                else None,
            }
        )
    payload = {
        "proposal": str(proposal.pk),
        "run": str(run.pk),
        "run_version": run.calculation_digest,
        "proposal_version": proposal.source_digest,
        "currency": proposal.currency,
        "review": str(review.pk),
        "predecessor": str(proposal.predecessor_id)
        if proposal.predecessor_id
        else None,
        "kind": proposal.record_kind,
        "lines": rows,
    }
    return proposal, lines, payload, _canonical_hash(payload)


def _cached_source(cache, organization, proposal_id, *, historical=False):
    key = (organization.pk, proposal_id, historical)
    if key not in cache:
        cache[key] = _read(organization, proposal_id, historical=historical)
    return cache[key]


def validate_assignments(enrollment):
    cache = {}
    if (
        enrollment.category not in CATEGORIES
        or not isinstance(enrollment.assignments, dict)
        or not enrollment.assignments
    ):
        raise ValidationError(
            "Explicit supported liability classification and occurrence mappings required."
        )
    for line_id, terms in enrollment.assignments.items():
        try:
            line = FinancialHandoffLine.objects.get(
                pk=UUID(line_id), organization_id=enrollment.organization_id
            )
            party = BusinessParty.objects.get(
                pk=UUID(terms["party_id"]), organization_id=enrollment.organization_id
            )
            date.fromisoformat(terms["recognized_on"])
            date.fromisoformat(terms["due_date"])
        except (
            ObjectDoesNotExist,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as exc:
            raise ValidationError(
                "Explicit same-tenant source/payee/date terms required."
            ) from exc
        if (
            line.line_kind != enrollment.category
            or not (party.legal_name or party.display_name).strip()
            or set(terms)
            != {
                "party_id",
                "recognized_on",
                "due_date",
                "grouping_reference",
                "source_hash",
            }
            or not isinstance(terms["grouping_reference"], str)
            or not 0 < len(terms["grouping_reference"].strip()) <= 120
        ):
            raise ValidationError("Enrollment classification/terms are invalid.")
        _, _, _, source_hash = _cached_source(
            cache, enrollment.organization, line.proposal_id
        )
        if source_hash != terms["source_hash"]:
            raise ValidationError("Enrollment source version is stale.")


@transaction.atomic
def prepare_enrollment(
    *,
    organization: Organization,
    actor: User,
    category: str,
    assignments: dict,
    evidence_reference: str,
) -> PayrollAPEnrollment:
    organization = _lock_organization(organization)
    membership = _require(organization, actor, P.SUBLEDGERS_PAYROLL_ENROLLMENTS_MANAGE)
    _require(organization, actor, P.PAYROLL_RESULTS_VIEW)
    values, cache = {}, {}
    for line_id, supplied in assignments.items():
        try:
            line = FinancialHandoffLine.objects.get(
                pk=line_id, organization=organization
            )
        except ObjectDoesNotExist as exc:
            raise ValidationError("Tenant liability source required.") from exc
        _, _, _, h = _cached_source(cache, organization, line.proposal_id)
        if set(supplied) != {
            "party_id",
            "recognized_on",
            "due_date",
            "grouping_reference",
        }:
            raise ValidationError("Explicit AP occurrence terms required; no defaults.")
        values[str(line.pk)] = {
            **supplied,
            "party_id": str(UUID(supplied["party_id"])),
            "source_hash": h,
        }
    version = (
        PayrollAPEnrollment.objects.filter(organization=organization, category=category)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    result = _create(
        PayrollAPEnrollment,
        organization=organization,
        actor=membership,
        category=category,
        version=version,
        assignments=values,
        evidence_reference=evidence_reference.strip(),
    )
    _audit(
        organization,
        actor,
        AuditAction.PAYROLL_AP_ENROLLMENT_PREPARED,
        result.pk,
        {"version": version, "category": category},
    )
    return result


@transaction.atomic
def change_enrollment(
    *,
    organization: Organization,
    actor: User,
    enrollment: PayrollAPEnrollment,
    kind: str,
    effective_at: datetime,
    reason: str,
) -> PayrollAPEnrollmentEvent:
    organization = _lock_organization(organization)
    membership = _require(organization, actor, P.SUBLEDGERS_PAYROLL_ENROLLMENTS_APPROVE)
    enrollment = PayrollAPEnrollment.objects.get(
        pk=enrollment.pk, organization=organization
    )
    prior = enrollment.events.filter(kind=kind).first()
    if prior:
        if (
            prior.effective_at == effective_at
            and prior.reason == reason.strip()
            and prior.actor_id == membership.pk
        ):
            return prior
        raise ValidationError("Enrollment event identity has conflicting payload.")
    if (
        timezone.is_naive(effective_at)
        or effective_at < timezone.now()
        or kind not in {"activate", "withdraw"}
    ):
        raise ValidationError("Enrollment changes must be explicit and prospective.")
    active = enrollment.events.filter(kind="activate").first()
    if kind == "activate":
        _require(organization, actor, P.PAYROLL_RESULTS_VIEW)
        validate_assignments(enrollment)
        previous = PayrollAPEnrollmentEvent.objects.filter(
            organization=organization,
            enrollment__category=enrollment.category,
            kind="activate",
        )
        if (
            previous.filter(enrollment__version__gte=enrollment.version).exists()
            or previous.filter(effective_at__gte=effective_at).exists()
        ):
            raise ValidationError(
                "Activated versions/effective times must advance prospectively."
            )
    elif active is None or effective_at < active.effective_at:
        raise ValidationError(
            "Withdrawal requires retained activation and a valid effective time."
        )
    result = _create(
        PayrollAPEnrollmentEvent,
        organization=organization,
        actor=membership,
        enrollment=enrollment,
        kind=kind,
        effective_at=effective_at,
        reason=reason.strip(),
    )
    _audit(
        organization,
        actor,
        AuditAction.PAYROLL_AP_ENROLLMENT_CHANGED,
        result.pk,
        {
            "enrollment": str(enrollment.pk),
            "kind": kind,
            "effective_at": effective_at.isoformat(),
        },
    )
    return result


def _active(organization, category, *, at=None):
    at = at or timezone.now()
    event = (
        PayrollAPEnrollmentEvent.objects.filter(
            organization=organization,
            kind="activate",
            enrollment__category=category,
            effective_at__lte=at,
        )
        .select_related("enrollment")
        .order_by("-enrollment__version")
        .first()
    )
    if (
        event is None
        or event.enrollment.events.filter(
            kind="withdraw", effective_at__lte=at
        ).exists()
    ):
        return None
    return event.enrollment


def _drafts(
    organization,
    actor,
    membership,
    proposal,
    lines,
    payload,
    source_hash,
    predecessors=None,
    exclusions=None,
):
    drafts = []
    exclusions = exclusions if exclusions is not None else []
    consumed_at = timezone.now()
    active = {
        category: _active(organization, category, at=consumed_at)
        for category in {line.line_kind for line in lines}
    }
    for line in lines:
        if line.amount <= 0:
            exclusions.append({"line": str(line.pk), "reason": "NON_POSITIVE_PAYABLE"})
            continue
        enrollment = active[line.line_kind]
        if enrollment is None or str(line.pk) not in enrollment.assignments:
            exclusions.append(
                {
                    "line": str(line.pk),
                    "reason": "NO_ACTIVE_ENROLLMENT"
                    if enrollment is None
                    else "OCCURRENCE_NOT_ENROLLED",
                    "enrollment": str(enrollment.pk) if enrollment else None,
                }
            )
            continue
        terms = enrollment.assignments[str(line.pk)]
        if terms["source_hash"] != source_hash:
            raise ValidationError("Enrollment pins another Payroll source version.")
        party = BusinessParty.objects.get(
            pk=terms["party_id"], organization=organization
        )
        snapshot = {
            "source": payload,
            "source_hash": source_hash,
            "enrollment": str(enrollment.pk),
            "enrollment_version": enrollment.version,
            "terms": terms,
            "line": str(line.pk),
            "party_name": party.legal_name or party.display_name,
            "party_tax_identifier": party.tax_identifier,
            "policy_evidence": enrollment.evidence_reference,
            "consumed_at": consumed_at.isoformat(),
            "predecessor": str((predecessors or {})[_key(line)].pk)
            if _key(line) in (predecessors or {})
            else None,
        }
        drafts.append(
            _create(
                PayrollAPDraft,
                organization=organization,
                actor=membership,
                source_line=line,
                enrollment=enrollment,
                source_version=proposal.source_digest,
                predecessor=(predecessors or {}).get(_key(line)),
                snapshot=snapshot,
                payload_hash=_canonical_hash(snapshot),
                amount=line.amount,
                currency=proposal.currency,
                party=party,
                project=line.run_employee.project,
                recognized_on=date.fromisoformat(terms["recognized_on"]),
                due_date=date.fromisoformat(terms["due_date"]),
                grouping_reference=terms["grouping_reference"],
            )
        )
    return drafts


def _key(line):
    return (
        line.employee_id,
        line.line_kind,
        line.statutory_result.calculation.kind if line.statutory_result_id else "",
    )


def _target(draft):
    return Obligation.objects.filter(
        organization_id=draft.organization_id,
        source_kind=SOURCE_KIND,
        source_uuid=draft.pk,
        source_version=1,
    ).first()


def _validate_draft(draft, *, cache=None):
    proposal, _, _, current = _cached_source(
        cache if cache is not None else {},
        draft.organization,
        draft.source_line.proposal_id,
        historical=True,
    )
    consumed_at = datetime.fromisoformat(draft.snapshot["consumed_at"])
    enrollment_at_consumption = _active(
        draft.organization, draft.enrollment.category, at=consumed_at
    )
    if (
        enrollment_at_consumption is None
        or enrollment_at_consumption.pk != draft.enrollment_id
    ):
        raise ValidationError(
            "Draft does not pin an enrollment active at source consumption."
        )
    if (
        current != draft.snapshot["source_hash"]
        or proposal.source_digest != draft.source_version
        or _canonical_hash(draft.snapshot) != draft.payload_hash
        or draft.amount != draft.source_line.amount
        or draft.currency != proposal.currency
        or draft.enrollment_id != UUID(draft.snapshot["enrollment"])
        or draft.snapshot["terms"]
        != draft.enrollment.assignments[str(draft.source_line_id)]
        or str(draft.party_id) != draft.snapshot["terms"]["party_id"]
        or draft.recognized_on.isoformat() != draft.snapshot["terms"]["recognized_on"]
        or draft.due_date.isoformat() != draft.snapshot["terms"]["due_date"]
        or draft.grouping_reference != draft.snapshot["terms"]["grouping_reference"]
        or draft.project_id != draft.source_line.run_employee.project_id
        or draft.snapshot["line"] != str(draft.source_line_id)
        or draft.snapshot["enrollment_version"] != draft.enrollment.version
        or draft.snapshot["predecessor"]
        != (str(draft.predecessor_id) if draft.predecessor_id else None)
    ):
        raise ValidationError("Payroll AP draft/source/mapping drift detected.")


def _snapshot(draft):
    return ObligationSourceSnapshot(
        SOURCE_KIND,
        draft.pk,
        1,
        "",
        "approved_ap_draft",
        ObligationDirection.PAYABLE,
        draft.amount,
        draft.currency,
        draft.recognized_on,
        draft.due_date,
        draft.party_id,
        draft.snapshot["party_name"],
        draft.snapshot["party_tax_identifier"],
        draft.project_id,
        None,
        {
            "draft": str(draft.pk),
            "source_version": draft.source_version,
            **draft.snapshot,
        },
    )


def _validate_target(draft, target):
    expected = _snapshot(draft)
    if (
        target.payload_hash != _canonical_hash(asdict(expected))
        or target.source_snapshot != expected.source_snapshot
        or target.source_hash != _canonical_hash(expected.source_snapshot)
        or target.original_amount != draft.amount
        or target.currency != draft.currency
        or target.party_id != draft.party_id
        or target.project_id != draft.project_id
        or target.recognized_on != draft.recognized_on
        or target.due_date != draft.due_date
        or target.direction != ObligationDirection.PAYABLE
        or target.source_version != 1
        or target.source_line_key
        or target.contract_id
        or target.party_name_snapshot != expected.party_name
        or target.party_tax_identifier_snapshot != expected.party_tax_identifier
    ):
        raise ValidationError("AP target/source payload drift detected.")


def _operation(
    *,
    organization,
    actor,
    proposal,
    idempotency_key,
    reversal=None,
    effective_date=None,
    reason="",
):
    idempotency_key = idempotency_key.strip()
    membership = _require(organization, actor, P.SUBLEDGERS_PAYROLL_PREPARE)
    _require(organization, actor, P.PAYROLL_RESULTS_VIEW)
    proposal, lines, payload, h = _read(organization, proposal.pk, historical=True)
    inverse_hash = _read(organization, reversal.pk)[3] if reversal else None
    request = {
        "source": str(proposal.pk),
        "hash": h,
        "reversal": str(reversal.pk) if reversal else None,
        "reversal_hash": inverse_hash,
        "effective_date": str(effective_date) if effective_date else None,
        "reason": reason.strip(),
    }
    request_hash = _canonical_hash(request)
    if not idempotency_key.strip() or not reason.strip():
        raise ValidationError("Explicit request identity and reason required.")
    prior = PayrollAPOperation.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    source_prior = PayrollAPOperation.objects.filter(
        organization=organization, source_proposal=proposal
    ).first()
    if prior or source_prior:
        prior = prior or source_prior
        if (
            prior.source_proposal_id != proposal.pk
            or prior.payload_hash != request_hash
        ):
            raise ValidationError(
                "Payroll occurrence/request identity has conflicting payload."
            )
        source_cache = {}
        for pk in prior.result["drafts"]:
            draft = PayrollAPDraft.objects.get(pk=pk, organization=organization)
            if draft.source_line.proposal_id != prior.source_proposal_id:
                raise ValidationError(
                    "Operation/draft occurrence linkage drift detected."
                )
            _validate_draft(draft, cache=source_cache)
            target = _target(draft)
            if target:
                _validate_target(draft, target)
        for pk in prior.result["reversals"]:
            effect = PayrollAPReversal.objects.select_related("draft").get(
                pk=pk, organization=organization
            )
            if effect.source_proposal_id != prior.reversal_proposal_id:
                raise ValidationError("Operation/reversal lineage drift detected.")
            _validate_draft(effect.draft, cache=source_cache)
            target = _target(effect.draft)
            if (target.pk if target else None) != effect.obligation_id:
                raise ValidationError("Reversal/AP target linkage drift detected.")
            if target:
                _validate_target(effect.draft, target)
        return prior
    _read(organization, proposal.pk)
    reversals, predecessors, exclusions, source_cache = [], {}, [], {}
    if reversal is not None:
        _require(organization, actor, P.SUBLEDGERS_SOURCES_REVERSE)
        reversal, inverse_lines, _, inverse_hash = _read(organization, reversal.pk)
        if not effective_date:
            raise ValidationError("Explicit AP correction effective date required.")
        try:
            chain = PayrollReversal.objects.get(
                organization=organization, reversal_run_id=reversal.run_id
            )
            original = FinancialHandoffProposal.objects.get(
                organization=organization,
                run_id=chain.original_run_id,
                family="liability",
            )
        except ObjectDoesNotExist as exc:
            raise ValidationError(
                "Retained Payroll reversal/predecessor required."
            ) from exc
        if reversal.record_kind != "reversal" or reversal.predecessor_id != original.pk:
            raise ValidationError("Reversal source lineage does not match.")
        if proposal.pk != reversal.pk and (
            proposal.record_kind != "replacement"
            or proposal.run_id != chain.replacement_run_id
            or proposal.predecessor_id != original.pk
        ):
            raise ValidationError(
                "Replacement must follow the retained Payroll replacement chain."
            )
        _, old_lines, _, _ = _read(organization, original.pk, historical=True)
        old_map, inverse_map = (
            {_key(x): x for x in old_lines},
            {_key(x): x for x in inverse_lines},
        )
        if (
            len(old_map) != len(old_lines)
            or len(inverse_map) != len(inverse_lines)
            or set(old_map) != set(inverse_map)
            or original.currency != reversal.currency
            or any(old_map[k].amount != -inverse_map[k].amount for k in old_map)
        ):
            raise ValidationError(
                "Payroll reversal must be an exact inverse occurrence set."
            )
        old_drafts = list(
            PayrollAPDraft.objects.select_for_update(of=("self",))
            .filter(organization=organization, source_line__proposal=original)
            .select_related("source_line__statutory_result__calculation")
        )
        if not old_drafts:
            raise ValidationError("No retained original AP effect exists to correct.")
        for draft in old_drafts:
            _validate_draft(draft, cache=source_cache)
            target = _target(draft)
            if target:
                target = Obligation.objects.select_for_update().get(
                    pk=target.pk, organization=organization
                )
                _validate_target(draft, target)
            rh = _canonical_hash(
                {
                    "draft": str(draft.pk),
                    "reversal": str(reversal.pk),
                    "source_hash": inverse_hash,
                    "effective_date": str(effective_date),
                    "reason": reason.strip(),
                }
            )
            existing = PayrollAPReversal.objects.filter(draft=draft).first()
            if existing:
                if existing.payload_hash != rh:
                    raise ValidationError(
                        "Existing Payroll AP reversal has conflicting payload."
                    )
                reversals.append(existing)
            else:
                if target and (
                    target.recognition_journal_id
                    or _active_settlement_amount(obligation=target)
                    or _approved_writeoff_amount(obligation=target)
                    or target.settlement_allocations.filter(
                        reversal__effective_date__gt=effective_date
                    ).exists()
                    or target.write_off_proposals.filter(
                        decision__reversal__effective_date__gt=effective_date
                    ).exists()
                ):
                    raise ValidationError(
                        "Consumed AP target requires independent downstream unwind first."
                    )
                reversals.append(
                    _create(
                        PayrollAPReversal,
                        organization=organization,
                        actor=membership,
                        draft=draft,
                        obligation=target,
                        source_proposal=reversal,
                        effective_date=effective_date,
                        reason=reason.strip(),
                        payload_hash=rh,
                    )
                )
            predecessors[_key(draft.source_line)] = draft
        drafts = (
            []
            if proposal.pk == reversal.pk
            else _drafts(
                organization,
                actor,
                membership,
                proposal,
                lines,
                payload,
                h,
                predecessors,
                exclusions=exclusions,
            )
        )
        if any(effective_date > d.recognized_on for d in drafts):
            raise ValidationError(
                "Reversal cannot follow replacement recognition date."
            )
    else:
        if proposal.record_kind != "original":
            raise ValidationError(
                "Corrections require explicit retained reversal lineage."
            )
        drafts = _drafts(
            organization,
            actor,
            membership,
            proposal,
            lines,
            payload,
            h,
            exclusions=exclusions,
        )
        if not drafts:
            raise ValidationError(
                "No active approved occurrence enrollment; AP consumption denied."
            )
    result = _create(
        PayrollAPOperation,
        organization=organization,
        actor=membership,
        source_proposal=proposal,
        reversal_proposal=reversal,
        source_hash=h,
        payload_hash=request_hash,
        idempotency_key=idempotency_key.strip(),
        result={
            "drafts": [str(x.pk) for x in drafts],
            "reversals": [str(x.pk) for x in reversals],
            "exclusions": exclusions,
        },
    )
    _audit(
        organization, actor, AuditAction.PAYROLL_AP_OPERATION, result.pk, result.result
    )
    return result


def prepare_payroll_ap(
    *,
    organization: Organization,
    actor: User,
    proposal: FinancialHandoffProposal,
    idempotency_key: str,
    reason: str,
    reversal=None,
    effective_date: date | None = None,
) -> PayrollAPOperation:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=P.SUBLEDGERS_PAYROLL_PREPARE,
        message="Explicit authorized AP/Payroll access required.",
    )
    try:
        with transaction.atomic():
            organization = _lock_organization(organization)
            return _operation(
                organization=organization,
                actor=actor,
                proposal=proposal,
                idempotency_key=idempotency_key,
                reason=reason,
                reversal=reversal,
                effective_date=effective_date,
            )
    except (
        ValidationError,
        PermissionDenied,
        DatabaseError,
        ObjectDoesNotExist,
    ) as exc:
        if FinancialHandoffProposal.objects.filter(
            organization=organization, pk=proposal.pk
        ).exists():
            require_business_permission(
                user=actor,
                organization=organization,
                permission=P.PAYROLL_RESULTS_VIEW,
                message="Explicit authorized AP/Payroll access required.",
            )
            _audit(
                organization,
                actor,
                AuditAction.PAYROLL_AP_FAILED,
                proposal.pk,
                {
                    "request_hash": _canonical_hash(idempotency_key),
                    "error_type": type(exc).__name__,
                },
            )
        if isinstance(exc, ObjectDoesNotExist):
            raise ValidationError(
                "Pinned AP source/mapping evidence is unavailable."
            ) from exc
        raise


def resolve_payroll_source(organization, source_uuid, source_version, source_line_key):
    try:
        draft = (
            PayrollAPDraft.objects.select_for_update()
            .select_related("enrollment", "source_line__proposal")
            .get(pk=source_uuid, organization=organization)
        )
    except ObjectDoesNotExist as exc:
        raise ValidationError("Tenant AP-owned Payroll draft required.") from exc
    _validate_draft(draft)
    if (
        source_version != 1
        or source_line_key
        or PayrollAPReversal.objects.filter(draft=draft).exists()
    ):
        raise ValidationError("Source version or active AP draft is invalid.")
    if _target(draft) is None:
        _read(organization, draft.source_line.proposal_id)
    target = _target(draft)
    if target:
        _validate_target(draft, target)
    return _snapshot(draft)


def accept_payroll_ap_draft(
    *,
    organization: Organization,
    actor: User,
    draft: PayrollAPDraft,
    idempotency_key: str,
) -> Obligation:
    for permission in (P.SUBLEDGERS_OBLIGATIONS_RECOGNIZE, P.PAYROLL_RESULTS_VIEW):
        require_business_permission(
            user=actor,
            organization=organization,
            permission=permission,
            message="Explicit AP and sensitive Payroll authority required.",
        )
    try:
        with transaction.atomic():
            organization = _lock_organization(organization)
            _require(organization, actor, P.SUBLEDGERS_OBLIGATIONS_RECOGNIZE)
            _require(organization, actor, P.PAYROLL_RESULTS_VIEW)
            return recognize_obligation(
                organization=organization,
                actor=actor,
                source_kind=SOURCE_KIND,
                source_uuid=draft.pk,
                source_version=1,
                idempotency_key=idempotency_key,
            )
    except (ValidationError, DatabaseError) as exc:
        retained = PayrollAPDraft.objects.filter(
            pk=draft.pk, organization=organization
        ).first()
        if retained is not None:
            _audit(
                organization,
                actor,
                AuditAction.PAYROLL_AP_FAILED,
                retained.source_line.proposal_id,
                {
                    "draft": str(retained.pk),
                    "request_hash": _canonical_hash(idempotency_key),
                    "error_type": type(exc).__name__,
                },
            )
        raise


def _native_lineage(organization, source):
    from apps.payroll.models import PayrollRun

    current, seen, lineage = source.run, set(), []
    while current.status == "reversed":
        if current.pk in seen:
            raise ValidationError("Native Payroll correction lineage cycle.")
        seen.add(current.pk)
        chain = (
            PayrollReversal.objects.filter(
                organization=organization, original_run=current
            )
            .select_related("reversal_run")
            .first()
        )
        if chain is None:
            raise ValidationError(
                "Reversed Payroll source lacks authoritative reversal lineage."
            )
        lineage.append(
            {
                "original_run": str(current.pk),
                "original_version": current.calculation_digest,
                "reversal_run": str(chain.reversal_run_id),
                "reversal_version": chain.reversal_run.calculation_digest,
                "replacement_run": str(chain.replacement_run_id)
                if chain.replacement_run_id
                else None,
            }
        )
        if chain.replacement_run_id is None:
            return None, lineage
        current = PayrollRun.objects.select_for_update().get(
            pk=chain.replacement_run_id, organization=organization
        )
    return (
        {"run": str(current.pk), "version": current.calculation_digest}
        if current.status == "finalized"
        else None
    ), lineage


@transaction.atomic
def reconcile_payroll_ap(
    *, organization: Organization, actor: User, proposal: FinancialHandoffProposal
) -> dict:
    organization = _lock_organization(organization)
    membership = _require(organization, actor, P.SUBLEDGERS_PAYROLL_VIEW)
    _require(organization, actor, P.PAYROLL_RESULTS_VIEW)
    source, _, _, source_hash = _read(organization, proposal.pk, historical=True)
    active_source, native_lineage = _native_lineage(organization, source)
    pending = list(
        PayrollAPDraft.objects.filter(
            organization=organization, source_line__proposal=source
        )
    )
    rows, visited, cache = [], set(), {}
    for draft in pending:
        if draft.pk in visited:
            raise ValidationError("AP replacement lineage cycle/duplicate.")
        visited.add(draft.pk)
        _validate_draft(draft, cache=cache)
        target = _target(draft)
        rev = (
            PayrollAPReversal.objects.filter(draft=draft, organization=organization)
            .select_related("source_proposal")
            .first()
        )
        if target:
            _validate_target(draft, target)
        children = list(draft.replacements.filter(organization=organization))
        pending.extend(children)
        source_state = draft.source_line.proposal.run.status
        rows.append(
            {
                "source_line": str(draft.source_line_id),
                "source_version": draft.source_version,
                "enrollment": str(draft.enrollment_id),
                "enrollment_version": draft.enrollment.version,
                "consumed_at": draft.snapshot["consumed_at"],
                "draft": str(draft.pk),
                "predecessor": str(draft.predecessor_id)
                if draft.predecessor_id
                else None,
                "amount": str(draft.amount),
                "obligation": str(target.pk) if target else None,
                "reversal": str(rev.pk) if rev else None,
                "reversal_source": str(rev.source_proposal_id) if rev else None,
                "reversal_source_version": rev.source_proposal.source_digest
                if rev
                else None,
                "replacements": [str(x.pk) for x in children],
                "issues": ["PENDING_AP_CORRECTION"]
                if source_state == "reversed" and rev is None
                else [],
            }
        )
    operations = PayrollAPOperation.objects.filter(
        organization=organization,
        source_proposal__run_id__in=[item["original_run"] for item in native_lineage]
        + ([active_source["run"]] if active_source else [str(source.run_id)]),
    )
    result = {
        "organization": str(organization.pk),
        "observed_at": timezone.now().isoformat(),
        "source": str(source.pk),
        "source_hash": source_hash,
        "active_native_source": active_source,
        "native_lineage": native_lineage,
        "rows": rows,
        "projection_only": True,
        "recorded_exclusions": [
            {
                "operation": str(op.pk),
                "source": str(op.source_proposal_id),
                "exclusions": op.result.get("exclusions", []),
            }
            for op in operations
        ],
    }
    _audit(
        organization,
        actor,
        AuditAction.PAYROLL_AP_RECONCILED,
        source.pk,
        {"prepared_by": str(membership.pk), "result": result},
    )
    return result


def register_payroll_handoff():
    if SOURCE_KIND not in registered_source_kinds():
        register_source_resolver(SOURCE_KIND, resolve_payroll_source)
