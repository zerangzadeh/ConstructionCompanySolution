"""Explicit cash planning evidence; no cash, cost or posting mutation."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal, Inexact, InvalidOperation, localcontext
from hashlib import sha256
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization
from apps.organizations.services import get_organization_settings
from apps.projects.cashflow_models import (
    ProjectCashflowSnapshot,
    ProjectCashflowSupplement,
)
from apps.projects.models import (
    BudgetAllocation,
    Project,
    ProjectCostFact,
    ProjectCostForecast,
    ProjectForecastTransition,
    ProjectScheduleItem,
)
from apps.projects.services import _require_budget_access
from apps.treasury.models import TreasuryMovement
from core.tenant_validation import validate_related_organizations

POLICY = "CEP065-CASHFLOW-v1"
DIRECTIONS = {"RECEIPT", "DISBURSEMENT"}


def digest(value: object) -> str:
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def _amount(value: object) -> Decimal:
    if not isinstance(value, (str, Decimal, int)) or isinstance(value, bool):
        raise ValidationError(
            "Cash amounts must be exact Decimal values, never floats."
        )
    try:
        amount = Decimal(value)
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ValidationError("Invalid cash amount.") from exc
    if not amount.is_finite() or amount < 0:
        raise ValidationError("Cash amounts must be finite and non-negative.")
    return amount


def _add_exact(left: Decimal, right: Decimal) -> Decimal:
    """Conserve source precision, including large cross-source control totals."""
    exponent = min(left.as_tuple().exponent, right.as_tuple().exponent, 0)
    with localcontext() as context:
        context.prec = max(left.adjusted(), right.adjusted(), 0) - exponent + 3
        context.traps[Inexact] = True
        return left + right


def _sum_exact(values: Iterable[Decimal]) -> Decimal:
    total = Decimal(0)
    for value in values:
        total = _add_exact(total, value)
    return total


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Explicit non-empty evidence references are required.")
    return value.strip()


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise ValidationError("Use an explicit ISO cash-event date.")
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError as exc:
        raise ValidationError("Use an explicit ISO cash-event date.") from exc


def _access(organization, project, actor, permission=P.PROJECT_COSTS_VIEW) -> None:
    _require_budget_access(
        organization=organization, project=project, actor=actor, permission=permission
    )


def _source(*, reference: dict, forecast: ProjectCostForecast, actor) -> dict:
    """Resolve real, scoped owner evidence; caller hashes/versions are never trusted."""
    from apps.billing.models import PayableCertificate, ProgressClaim
    from apps.contracts.models import ContractTermVersion
    from apps.subledgers.models import Obligation

    if not isinstance(reference, dict):
        raise ValidationError("An explicit source reference is required.")
    family = reference.get("family")
    configuration = {
        "budget_allocation": (BudgetAllocation, P.BUDGETS_VIEW),
        "forecast": (ProjectCostForecast, P.PROJECT_COSTS_VIEW),
        "commitment": (ProjectCostFact, P.PROJECT_COSTS_VIEW),
        "contract_terms": (ContractTermVersion, P.CONTRACTS_VIEW),
        "billing_claim": (ProgressClaim, P.CLAIMS_VIEW),
        "billing_certificate": (
            PayableCertificate,
            P.PAYABLE_CERTIFICATES_VIEW,
        ),
        "obligation": (Obligation, P.SUBLEDGERS_VIEW),
    }
    if family not in configuration:
        raise ValidationError("Unregistered cash-flow source family.")
    model, permission = configuration[family]
    _access(forecast.organization, forecast.project, actor, permission)
    try:
        obj = model.objects.select_for_update().get(
            pk=reference.get("id"), organization_id=forecast.organization_id
        )
    except (model.DoesNotExist, ValueError, ValidationError) as exc:
        raise ValidationError("Cash source is unavailable in this tenant.") from exc
    approved_at = None
    event = ""
    line = str(obj.pk)
    currency = forecast.currency
    if family == "budget_allocation":
        budget = obj.manifest_line.manifest.budget
        validate_related_organizations(
            obj,
            line=obj.manifest_line,
            manifest=obj.manifest_line.manifest,
            budget=budget,
            estimate=obj.manifest_line.manifest.estimate,
            revision=obj.manifest_line.manifest.estimate_revision,
            wbs=obj.wbs_node,
            cbs=obj.cbs_node,
            cost_center=obj.cost_center,
        )
        if obj.wbs_node and obj.wbs_node.project_id != forecast.project_id:
            raise ValidationError(
                "Budget cash evidence has another project's WBS context."
            )
        if budget.pk != forecast.budget_id or budget.status != "accepted":
            raise ValidationError(
                "Cash baseline evidence requires its accepted pinned Budget."
            )
        project_id = budget.project_id
        version = budget.version_number
        approved_at = budget.accepted_at
        evidence = {
            "amount": str(obj.amount),
            "budget_id": str(budget.pk),
            "budget_hash": budget.payload_hash,
            "manifest_line_id": str(obj.manifest_line_id),
            "estimate_revision_id": str(
                obj.manifest_line.manifest.estimate_revision_id
            ),
            "estimate_revision_number": obj.manifest_line.manifest.estimate_revision_number,
            "wbs_id": str(obj.wbs_node_id),
            "cbs_id": str(obj.cbs_node_id),
            "cost_center_id": str(obj.cost_center_id or ""),
            "basis": obj.allocation_basis_reference,
        }
        currency = budget.currency
    elif family == "forecast":
        validate_related_organizations(obj, budget=obj.budget)
        if obj.pk != forecast.pk:
            raise ValidationError(
                "Forecast planning assumptions must belong to this reviewed version."
            )
        project_id = obj.project_id
        version = obj.version_number
        # Approval of this immutable subject approves its supplement atomically.
        evidence = {
            "cutoff_date": str(obj.cutoff_date),
            "watermark": obj.source_watermark,
            "budget_id": str(obj.budget_id),
            "assumptions": obj.assumptions,
            "eac": str(obj.eac),
            "uncommitted_etc": str(obj.uncommitted_etc),
        }
        currency = obj.currency
    elif family == "commitment":
        validate_related_organizations(
            obj,
            producer=obj.contract,
            wbs=obj.wbs_node,
            cbs=obj.cbs_node,
            cost_center=obj.cost_center,
        )
        if (
            obj.kind
            not in {
                "commitment_authorized",
                "commitment_adjustment",
                "commitment_relief",
            }
            or obj.contract.status != "approved"
        ):
            raise ValidationError(
                "An approved commitment producer and classified fact are required."
            )
        project_id, version = obj.project_id, obj.source_version
        approved_at = obj.contract.approved_at
        event = obj.economic_event_id
        line = obj.source_line_id
        currency = obj.currency
        evidence = {
            "producer_id": str(obj.contract_id),
            "producer_version": obj.contract.version,
            "source_id": obj.source_id,
            "source_version": obj.source_version,
            "source_line_id": line,
            "kind": obj.kind,
            "amount": str(obj.amount),
            "payload_hash": obj.payload_hash,
            "recognition_date": str(obj.recognition_date),
            "wbs_id": str(obj.wbs_node_id or ""),
            "cbs_id": str(obj.cbs_node_id or ""),
            "cost_center_id": str(obj.cost_center_id or ""),
        }
    elif family == "contract_terms":
        validate_related_organizations(obj, contract=obj.contract)
        if obj.status != "approved":
            raise ValidationError("Approved commercial terms are required.")
        project_id, version = obj.contract.project_id, obj.version
        approved_at = obj.approved_at
        evidence = {
            "contract_id": str(obj.contract_id),
            "direction": obj.contract.direction,
            "effective_from": str(obj.effective_from),
            "payment_due_days": obj.payment_due_days,
            "approval_reason": obj.approval_reason,
        }
    elif family in {"billing_claim", "billing_certificate"}:
        validate_related_organizations(
            obj, contract=obj.contract, terms=obj.contract_term_version
        )
        if (
            obj.contract.project_id != forecast.project_id
            or obj.contract_term_version.contract_id != obj.contract_id
        ):
            raise ValidationError(
                "Billing cash evidence has inconsistent commercial context."
            )
        if obj.status != "approved":
            raise ValidationError("Approved Billing evidence is required.")
        project_id, version = obj.project_id, obj.revision_number
        approved_at = obj.approved_at
        currency = obj.currency_code
        evidence = {
            "contract_id": str(obj.contract_id),
            "terms_id": str(obj.contract_term_version_id),
            "net_amount": str(obj.net_amount),
            "due_date": str(obj.due_date or ""),
            "calculation_snapshot": obj.calculation_snapshot,
        }
    else:
        validate_related_organizations(obj, contract=obj.contract)
        if obj.contract and obj.contract.project_id != forecast.project_id:
            raise ValidationError(
                "Obligation commercial context belongs to another project."
            )
        project_id, version = obj.project_id, obj.source_version
        if obj.source_reversal_evidence is not None:
            raise ValidationError("An unreversed, source-owned obligation is required.")
        approved_at = obj.created_at
        currency = obj.currency
        line = obj.source_line_key or str(obj.pk)
        evidence = {
            "source_kind": obj.source_kind,
            "source_uuid": str(obj.source_uuid),
            "source_hash": obj.source_hash,
            "source_status": obj.source_status,
            "original_amount": str(obj.original_amount),
            "due_date": str(obj.due_date or ""),
            "contract_id": str(obj.contract_id or ""),
            "journal_id": str(obj.recognition_journal_id or ""),
        }
    if project_id != forecast.project_id or currency != forecast.currency:
        raise ValidationError(
            "Cash evidence must share project and currency; no inferred allocation or FX."
        )
    if family != "forecast" and approved_at is None:
        raise ValidationError("Source approval history is missing.")
    return {
        "family": family,
        "id": str(obj.pk),
        "version": str(version),
        "line": line,
        "project_id": str(project_id),
        "currency": currency,
        "economic_event_id": event,
        "recorded_at": obj.created_at.isoformat(),
        "approved_at": approved_at.isoformat() if approved_at else None,
        "status": getattr(obj, "status", "accepted_source"),
        "evidence": evidence,
        "hash": digest(evidence),
    }


def _rows(*, rows: list, forecast: ProjectCostForecast, actor, predecessor) -> list:
    if not isinstance(rows, list) or not rows:
        raise ValidationError("Explicit cash allocation rows are required.")
    result, identities, sources_by_event = [], set(), {}
    previous = (
        {r["key"]: r for r in predecessor.manifest["rows"]} if predecessor else {}
    )
    for supplied in rows:
        if not isinstance(supplied, dict):
            raise ValidationError("Invalid cash allocation row.")
        key, event = (
            _text(supplied.get("key")),
            _text(supplied.get("economic_event_id")),
        )
        direction = supplied.get("direction")
        if direction not in DIRECTIONS or key in identities:
            raise ValidationError(
                "Cash directions and allocation identities must be unambiguous."
            )
        identities.add(key)
        amount = _amount(supplied.get("cash_amount"))
        if not amount:
            raise ValidationError("Cash allocation amounts must be positive.")
        source = _source(
            reference=supplied.get("source", {}), forecast=forecast, actor=actor
        )
        if supplied.get("currency", source["currency"]) != source["currency"]:
            raise ValidationError(
                "Cash row currency conflicts with its authoritative source."
            )
        if source["economic_event_id"] and event != source["economic_event_id"]:
            raise ValidationError(
                "Commitment economic-event identity cannot be replaced."
            )
        group = f"{source['family']}:{source['id']}"
        if event in sources_by_event and sources_by_event[event] != group:
            raise ValidationError(
                "Overlapping source representations require one selected cash source per event."
            )
        sources_by_event[event] = group
        state = supplied.get("state", "allocated")
        if state not in {"allocated", "unallocated", "cancelled"}:
            raise ValidationError("Unknown cash allocation state.")
        expected = supplied.get("expected_cash_on")
        reason = supplied.get("exception_reason", "")
        if state == "allocated":
            expected = _date(expected).isoformat()
        elif state == "unallocated":
            if expected is not None:
                raise ValidationError("Unallocated cash must not invent timing.")
            reason = _text(reason)
        else:
            prior = previous.get(key)
            if (
                not prior
                or prior["economic_event_id"] != event
                or prior["direction"] != direction
                or _amount(prior["cash_amount"]) != amount
            ):
                raise ValidationError(
                    "Cancellation requires exact retained predecessor allocation evidence."
                )
            expected, reason = None, _text(reason)
        row = {
            "key": key,
            "economic_event_id": event,
            "direction": direction,
            "cash_amount": str(amount),
            "currency": source["currency"],
            "source_group": group,
            "source": source,
            "state": state,
            "expected_cash_on": expected,
            "cash_basis": _text(supplied.get("cash_basis")),
            "timing_basis": _text(supplied.get("timing_basis")),
            "cost_cash_difference_evidence": _text(
                supplied.get("cost_cash_difference_evidence")
            ),
            "exception_reason": reason,
            "references": [],
        }
        for reference in supplied.get("references", []):
            row["references"].append(
                _source(reference=reference, forecast=forecast, actor=actor)
            )
        if supplied.get("schedule_item_id"):
            _access(
                forecast.organization, forecast.project, actor, P.PROJECT_SCHEDULES_VIEW
            )
            try:
                item = ProjectScheduleItem.objects.select_related("schedule").get(
                    pk=supplied["schedule_item_id"],
                    organization=forecast.organization,
                    project=forecast.project,
                )
            except (
                ProjectScheduleItem.DoesNotExist,
                ValueError,
                ValidationError,
            ) as exc:
                raise ValidationError(
                    "Schedule reference is unavailable in this project."
                ) from exc
            validate_related_organizations(
                item, schedule=item.schedule, wbs=item.wbs_node
            )
            if item.schedule.project_id != forecast.project_id or (
                item.wbs_node and item.wbs_node.project_id != forecast.project_id
            ):
                raise ValidationError(
                    "The schedule revision belongs to another project."
                )
            row["schedule"] = {
                "id": str(item.pk),
                "revision_id": str(item.schedule_id),
                "hash": item.schedule.payload_hash,
                "version": item.schedule.version_number,
                "state": item.schedule.status,
                "planned_start": str(item.planned_start),
                "planned_finish": str(item.planned_finish),
                "item_hash": digest(
                    {
                        "id": str(item.pk),
                        "code": item.code,
                        "wbs_id": str(item.wbs_node_id or ""),
                        "planned_start": str(item.planned_start),
                        "planned_finish": str(item.planned_finish),
                        "source_reference": item.source_reference,
                    }
                ),
            }
        result.append(row)
    return result


def _controls(rows: list, supplied: list) -> list:
    totals = defaultdict(lambda: {"cash_amount": Decimal(0), "row_count": 0})
    for row in rows:
        key = (row["source_group"], row["direction"], row["currency"])
        totals[key]  # Even cancellation-only groups require explicit zero controls.
        if row["state"] == "cancelled":
            continue
        totals[key]["cash_amount"] = _add_exact(
            totals[key]["cash_amount"], _amount(row["cash_amount"])
        )
        totals[key]["row_count"] += 1
    controls = {}
    for control in supplied:
        key = (
            _text(control.get("source_group")),
            control.get("direction"),
            control.get("currency"),
        )
        if key in controls or key[1] not in DIRECTIONS:
            raise ValidationError("Invalid or duplicate source control.")
        controls[key] = {
            "cash_amount": _amount(control.get("cash_amount")),
            "row_count": control.get("row_count"),
        }
        if type(control.get("row_count")) is not int or control["row_count"] < 0:
            raise ValidationError("Explicit source control row counts are required.")
    if dict(totals) != controls:
        raise ValidationError(
            "Dated allocations plus explicit exceptions must reconcile exactly to approved source controls."
        )
    return [
        {
            "source_group": k[0],
            "direction": k[1],
            "currency": k[2],
            "cash_amount": str(v["cash_amount"]),
            "row_count": v["row_count"],
        }
        for k, v in sorted(controls.items())
    ]


@transaction.atomic
def prepare_cashflow_supplement(
    *,
    forecast: ProjectCostForecast,
    actor: User,
    rows: list[dict],
    controls: list[dict],
) -> ProjectCashflowSupplement:
    project = Project.objects.select_for_update().get(pk=forecast.project_id)
    forecast = (
        ProjectCostForecast.objects.select_for_update(of=("self",))
        .select_related("review", "organization", "budget")
        .get(pk=forecast.pk)
    )
    _access(forecast.organization, project, actor, P.PROJECT_FORECASTS_PREPARE)
    if forecast.review.status != "draft" or forecast.created_by_id != actor.pk:
        raise PermissionDenied(
            "Only the forecast preparer may attach cash evidence before submission."
        )
    predecessor = None
    prior_review = forecast.review.predecessor
    while prior_review is not None and predecessor is None:
        predecessor = ProjectCashflowSupplement.objects.filter(
            forecast_id=prior_review.forecast_id
        ).first()
        prior_review = prior_review.predecessor
    resolved = _rows(rows=rows, forecast=forecast, actor=actor, predecessor=predecessor)
    normalized_controls = _controls(resolved, controls)
    manifest = {
        "policy_version": POLICY,
        "forecast_id": str(forecast.pk),
        "forecast_version": forecast.version_number,
        "budget_id": str(forecast.budget_id),
        "budget_version": forecast.budget.version_number,
        "budget_hash": forecast.budget.payload_hash,
        "currency": forecast.currency,
        "cost_source_coverage_complete": forecast.coverage_complete,
        "rows": resolved,
        "controls": normalized_controls,
    }
    existing = ProjectCashflowSupplement.objects.filter(forecast=forecast).first()
    if existing:
        if existing.payload_hash != digest(manifest):
            raise ValidationError(
                "Changed cash evidence requires a new forecast version."
            )
        return existing
    return ProjectCashflowSupplement.objects.create(
        organization=forecast.organization,
        project=project,
        forecast=forecast,
        predecessor=predecessor,
        created_by=actor,
        manifest=manifest,
        payload_hash=digest(manifest),
    )


def validate_cashflow_review(*, forecast: ProjectCostForecast, actor: User) -> None:
    """Called inside existing submission/decision transactions; never grants approval."""
    supplement = ProjectCashflowSupplement.objects.filter(forecast=forecast).first()
    if supplement is None:
        return  # Legacy cost-only forecast behavior remains intact.
    if (
        digest(supplement.manifest) != supplement.payload_hash
        or supplement.policy_version != POLICY
    ):
        raise ValidationError("Cash supplement evidence integrity failed.")
    for row in supplement.manifest["rows"]:
        for source in [row["source"], *row["references"]]:
            current = _source(reference=source, forecast=forecast, actor=actor)
            if current != source:
                raise ValidationError(
                    "Cash source changed during review; create a new forecast version."
                )


def _approval(supplement, as_of: datetime, *, baseline: bool) -> dict:
    if supplement.created_at > as_of or supplement.forecast.created_at > as_of:
        raise ValidationError("Cash evidence did not exist at the knowledge cutoff.")
    transitions = list(
        ProjectForecastTransition.objects.filter(
            review__forecast=supplement.forecast, created_at__lte=as_of
        ).order_by("sequence")
    )
    approved = next(
        (t for t in reversed(transitions) if t.new_status == "approved"), None
    )
    if approved is None or (not baseline and transitions[-1].new_status != "approved"):
        raise ValidationError(
            "Select approved baseline and current approved forecast evidence as of the cutoff."
        )
    for row in supplement.manifest["rows"]:
        for source in [row["source"], *row["references"]]:
            for timestamp in (source["recorded_at"], source["approved_at"]):
                if timestamp and datetime.fromisoformat(timestamp) > as_of:
                    raise ValidationError(
                        "Source evidence postdates the knowledge cutoff."
                    )
    return {
        "transition_id": str(approved.pk),
        "actor_id": str(approved.actor_id),
        "approved_at": approved.created_at.isoformat(),
        "status_history": [
            {
                "id": str(t.pk),
                "sequence": t.sequence,
                "status": t.new_status,
                "at": t.created_at.isoformat(),
            }
            for t in transitions
        ],
    }


def _require_sources(supplement, actor) -> None:
    permissions = {
        "budget_allocation": P.BUDGETS_VIEW,
        "forecast": P.PROJECT_COSTS_VIEW,
        "commitment": P.PROJECT_COSTS_VIEW,
        "contract_terms": P.CONTRACTS_VIEW,
        "billing_claim": P.CLAIMS_VIEW,
        "billing_certificate": P.PAYABLE_CERTIFICATES_VIEW,
        "obligation": P.SUBLEDGERS_VIEW,
    }
    for row in supplement.manifest["rows"]:
        for source in [row["source"], *row["references"]]:
            _access(
                supplement.organization,
                supplement.project,
                actor,
                permissions[source["family"]],
            )
        if "schedule" in row:
            _access(
                supplement.organization,
                supplement.project,
                actor,
                P.PROJECT_SCHEDULES_VIEW,
            )


def _next_month(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def render_manifest(manifest: dict) -> dict:
    """Deterministic rebuild using retained evidence only; no current-source reads."""
    start, end = _date(manifest["horizon_start"]), _date(manifest["horizon_end"])
    buckets = {}
    cursor = start
    while cursor < end:
        buckets[cursor.isoformat()] = {
            name: {direction: Decimal(0) for direction in sorted(DIRECTIONS)}
            for name in ("baseline", "forecast", "actual")
        }
        cursor = _next_month(cursor)
    exceptions = []
    outside = {
        name: {d: Decimal(0) for d in sorted(DIRECTIONS)}
        for name in ("baseline", "forecast", "actual")
    }
    controls = {}
    for name in ("baseline", "forecast", "actual"):
        layer = manifest[name]
        controls[name] = layer["controls"]
        for row in layer["rows"]:
            if row["state"] == "cancelled":
                continue
            if row["state"] != "allocated":
                exceptions.append(
                    {
                        "layer": name,
                        "key": row["key"],
                        "amount": row["cash_amount"],
                        "reason": row["exception_reason"],
                    }
                )
                continue
            event_date = _date(row["expected_cash_on"])
            amount = _amount(row["cash_amount"])
            if row.get("sign", 1) == -1:
                amount = amount.copy_negate()
            direction = row["direction"]
            if not start <= event_date < end:
                outside[name][direction] = _add_exact(outside[name][direction], amount)
            else:
                target = buckets[event_date.replace(day=1).isoformat()][name]
                target[direction] = _add_exact(target[direction], amount)

    def strings(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, dict):
            return {k: strings(v) for k, v in value.items()}
        return value

    return {
        "buckets": strings(buckets),
        "out_of_horizon": strings(outside),
        "exceptions": exceptions,
        "complete": not exceptions,
        "coverage": {
            "cash_controls_reconciled": True,
            "cash_timing_complete": not exceptions,
            "cost_source_coverage_complete": {
                name: manifest[name]["cost_source_coverage_complete"]
                for name in ("baseline", "forecast")
            },
            "actual_scope": "Posted native Treasury movements explicitly assigned to this project at the retained cutoff",
        },
        "controls": controls,
        "policy_version": manifest["policy_version"],
    }


@transaction.atomic
def capture_cashflow_comparison(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    baseline_id: UUID | str,
    forecast_id: UUID | str,
    knowledge_as_of: datetime,
    horizon_start: date,
    horizon_end: date,
    idempotency_key: str,
) -> ProjectCashflowSnapshot:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    project = Project.objects.select_for_update().get(pk=project.pk)
    _access(organization, project, actor)
    _access(organization, project, actor, P.TREASURY_VIEW)
    captured_at = timezone.now()
    if (
        not isinstance(knowledge_as_of, datetime)
        or timezone.is_naive(knowledge_as_of)
        or knowledge_as_of > captured_at
    ):
        raise ValidationError(
            "An aware knowledge cutoff no later than capture time is required."
        )
    if (
        type(horizon_start) is not date
        or type(horizon_end) is not date
        or horizon_start.day != 1
        or horizon_end.day != 1
        or horizon_end <= horizon_start
    ):
        raise ValidationError(
            "An explicit non-empty, month-aligned horizon is required."
        )
    idempotency_key = _text(idempotency_key)
    supplements = []
    for pk in (baseline_id, forecast_id):
        try:
            s = ProjectCashflowSupplement.objects.select_related(
                "forecast", "organization", "project"
            ).get(pk=pk, organization=organization, project=project)
        except (
            ProjectCashflowSupplement.DoesNotExist,
            ValidationError,
            ValueError,
        ) as exc:
            raise ValidationError(
                "Cash supplement is unavailable in this project."
            ) from exc
        _require_sources(s, actor)
        supplements.append(s)
    existing = ProjectCashflowSnapshot.objects.filter(
        organization=organization, project=project, idempotency_key=idempotency_key
    ).first()
    if existing:
        if (
            existing.baseline_id,
            existing.forecast_id,
            existing.knowledge_as_of,
            existing.horizon_start,
            existing.horizon_end,
        ) != (
            supplements[0].pk,
            supplements[1].pk,
            knowledge_as_of,
            horizon_start,
            horizon_end,
        ):
            raise ValidationError("Cash comparison retry identity conflicts.")
        rebuild_cashflow_snapshot(snapshot=existing, actor=actor)
        return existing
    settings = get_organization_settings(organization=organization)
    if settings.updated_at > knowledge_as_of:
        raise ValidationError(
            "Tenant timezone/currency history is unavailable at this cutoff."
        )
    try:
        tenant_zone = ZoneInfo(settings.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError("Authoritative tenant timezone is required.") from exc
    manifest = {
        "policy_version": POLICY,
        "knowledge_as_of": knowledge_as_of.isoformat(),
        "captured_at": captured_at.isoformat(),
        "timezone": settings.timezone,
        "settings_id": str(settings.pk),
        "settings_recorded_at": settings.updated_at.isoformat(),
        "horizon_start": horizon_start.isoformat(),
        "horizon_end": horizon_end.isoformat(),
        "organization_id": str(organization.pk),
        "project_id": str(project.pk),
    }
    for name, s in zip(("baseline", "forecast"), supplements, strict=True):
        if (
            s.policy_version != POLICY
            or digest(s.manifest) != s.payload_hash
            or s.manifest["currency"] != settings.currency
        ):
            raise ValidationError(
                "Cash source policy, currency or manifest integrity failed."
            )
        if name == "forecast":
            validate_cashflow_review(forecast=s.forecast, actor=actor)
        approval = _approval(s, knowledge_as_of, baseline=name == "baseline")
        manifest[name] = {
            **s.manifest,
            "supplement_id": str(s.pk),
            "payload_hash": s.payload_hash,
            "recorded_at": s.created_at.isoformat(),
            "approval": approval,
            "rows": [
                {
                    **row,
                    "approval_actor_id": approval["actor_id"],
                    "approved_at": approval["approved_at"],
                }
                for row in s.manifest["rows"]
            ],
        }
    movements = (
        TreasuryMovement.objects.filter(
            organization=organization,
            project=project,
            status="posted",
            posted_at__lte=knowledge_as_of,
            created_at__lte=knowledge_as_of,
            movement_date__lte=knowledge_as_of.astimezone(tenant_zone).date(),
        )
        .select_related("reverses")
        .order_by("pk")
    )
    cash_rows = []
    for movement in movements:
        if movement.kind == "transfer":
            continue  # Internal account transfers are not project receipts/payments.
        original = movement.reverses if movement.kind == "reversal" else movement
        if original is not None and original.kind == "transfer":
            continue
        if original is None or original.kind not in {"receipt", "disbursement"}:
            raise ValidationError(
                "Treasury cash direction/reversal lineage is unavailable."
            )
        if (
            movement.currency != settings.currency
            or not movement.journal_id
            or original.organization_id != organization.pk
            or original.project_id != project.pk
        ):
            raise ValidationError(
                "Treasury evidence does not match this scoped cash comparison."
            )
        cash_rows.append(
            {
                "key": str(movement.pk),
                "state": "allocated",
                "expected_cash_on": movement.movement_date.isoformat(),
                "cash_amount": str(movement.amount),
                "direction": original.kind.upper(),
                "sign": -1 if movement.kind == "reversal" else 1,
                "version": movement.version,
                "hash": movement.payload_hash,
                "journal_id": str(movement.journal_id),
                "posted_at": movement.posted_at.isoformat(),
                "reverses_id": str(movement.reverses_id or ""),
                "currency": movement.currency,
            }
        )
    manifest["actual"] = {
        "rows": cash_rows,
        "controls": {
            "row_count": len(cash_rows),
            "source": "treasury.TreasuryMovement",
            "currency": settings.currency,
            "totals": {
                d: str(
                    _sum_exact(
                        (
                            _amount(r["cash_amount"]).copy_negate()
                            if r["sign"] == -1
                            else _amount(r["cash_amount"])
                            for r in cash_rows
                            if r["direction"] == d
                        ),
                    )
                )
                for d in sorted(DIRECTIONS)
            },
        },
    }
    result = render_manifest(manifest)
    return ProjectCashflowSnapshot.objects.create(
        organization=organization,
        project=project,
        created_by=actor,
        baseline=supplements[0],
        forecast=supplements[1],
        knowledge_as_of=knowledge_as_of,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        timezone_name=settings.timezone,
        idempotency_key=idempotency_key,
        manifest=manifest,
        result=result,
        payload_hash=digest({"manifest": manifest, "result": result}),
    )


def rebuild_cashflow_snapshot(
    *, snapshot: ProjectCashflowSnapshot, actor: User
) -> dict:
    snapshot = ProjectCashflowSnapshot.objects.select_related(
        "organization", "project", "baseline", "forecast"
    ).get(pk=snapshot.pk)
    _access(snapshot.organization, snapshot.project, actor)
    _access(snapshot.organization, snapshot.project, actor, P.TREASURY_VIEW)
    _require_sources(snapshot.baseline, actor)
    _require_sources(snapshot.forecast, actor)
    if snapshot.policy_version != POLICY or snapshot.payload_hash != digest(
        {"manifest": snapshot.manifest, "result": snapshot.result}
    ):
        raise ValidationError(
            "Retained cash comparison evidence is missing or corrupt."
        )
    rebuilt = render_manifest(snapshot.manifest)
    if rebuilt != snapshot.result:
        raise ValidationError("Retained cash comparison cannot be reproduced.")
    return rebuilt
