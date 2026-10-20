"""SPEC-023 financial gates. Captures evidence; never performs a source action."""

import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.accounting.recognition_models import SourceRecognitionDraft
from apps.accounting.recognition_services import _journal_rows
from apps.accounting.recognition_sources import digest, read_source
from apps.accounts.models import User
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization, OrganizationSettings
from apps.projects.models import Project
from apps.projects.services import get_project_cost_reconciliation
from apps.subledgers.closeout_projection import settlement_reconciliation
from apps.treasury.models import TreasuryGLReconciliationSlice, TreasuryMovement

from .models import ReconciliationException

GATE_FAMILIES = (
    "accounting_period_controls",
    "treasury_gl",
    "subledger_settlement_control",
    "inventory_gl",
    "payroll_financial",
    "fixed_assets_gl",
    "project_cost_sources",
    "linked_blocking_exceptions",
)
SOURCE_PERMISSIONS = (
    P.ACCOUNTING_VIEW,
    P.ACCOUNTING_RECOGNITION_VIEW,
    P.TREASURY_VIEW,
    P.SUBLEDGERS_VIEW,
    P.INVENTORY_VALUATION_VIEW,
    P.PAYROLL_RESULTS_VIEW,
    P.FIXED_ASSETS_VIEW,
    P.PROJECT_COST_RECONCILIATIONS_VIEW,
)


def _result(
    outcome: str, *, evidence: list | None = None, issues: tuple | list = ()
) -> dict:
    return {"outcome": outcome, "evidence": evidence or [], "issues": list(issues)}


def require_financial_sources(
    organization: Organization, project: Project, actor: User
) -> None:
    for code in SOURCE_PERMISSIONS:
        require_business_permission(
            user=actor,
            organization=organization,
            project=project,
            permission=code,
            message="Financial source access required.",
        )


def _accounting(organization: Organization, project: Project, cutoff: datetime) -> dict:
    journals = (
        JournalEntry.objects.filter(
            organization=organization,
            lines__project=project,
            document_date__lte=cutoff.date(),
            created_at__lte=cutoff,
        )
        .select_related("period")
        .distinct()
    )
    evidence, issues = [], []
    for journal in journals:
        event = (
            journal.period.control_events.filter(created_at__lte=cutoff)
            .order_by("-sequence")
            .first()
        )
        evidence.append(
            {
                "journal": str(journal.pk),
                "version": journal.source_version,
                "status": journal.status,
                "period": str(journal.period_id),
                "control_event": str(event.pk) if event else None,
                "control_hash": event.evidence_hash if event else None,
            }
        )
        if (
            journal.status != "posted"
            or journal.period.status != "closed"
            or event is None
            or event.action != "close"
        ):
            issues.append("ACCOUNTING_PERIOD_CONTROL_UNRESOLVED")
    return _result(
        "blocked" if issues else "satisfied" if evidence else "not_applicable",
        evidence=evidence,
        issues=issues,
    )


def _treasury(organization: Organization, project: Project, cutoff: datetime) -> dict:
    evidence, issues = [], []
    for movement in TreasuryMovement.objects.filter(
        organization=organization,
        project=project,
        status="posted",
        movement_date__lte=cutoff.date(),
        created_at__lte=cutoff,
    ).select_related("journal"):
        legs = list(movement.legs.all())
        if not legs:
            issues.append("POSTED_CASH_LEGS_MISSING")
        for leg in legs:
            current = (
                TreasuryGLReconciliationSlice.objects.filter(
                    organization=organization,
                    treasury_account_id=leg.account_id,
                    cutoff_date=cutoff.date(),
                    currency=movement.currency,
                    invalidation__isnull=True,
                )
                .order_by("-grain_revision")
                .first()
            )
            captured = (
                current.leg_evidence.filter(organization=organization, leg=leg).first()
                if current
                else None
            )
            lines = (
                list(
                    current.journal_line_evidence.filter(
                        organization=organization, movement=movement
                    ).select_related("journal")
                )
                if current
                else []
            )
            valid = bool(captured and lines and movement.journal_id)
            if valid:
                valid = (
                    captured.movement_version == movement.version
                    and captured.occurrence_id == movement.occurrence_id
                    and captured.amount == leg.amount
                    and captured.direction == leg.direction
                    and all(
                        x.journal.status == "posted"
                        and x.journal.source_uuid == x.journal_source_uuid
                        and x.journal.source_version == x.journal_source_version
                        for x in lines
                    )
                )
                signed_cash = leg.amount if leg.direction == "in" else -leg.amount
                valid = (
                    valid
                    and sum((x.debit - x.credit for x in lines), Decimal(0))
                    == signed_cash
                )
            evidence.append(
                {
                    "movement": str(movement.pk),
                    "version": movement.version,
                    "leg": str(leg.pk),
                    "native_slice": str(current.pk) if current else None,
                    "native_revision": current.grain_revision if current else None,
                    "journal_lines": [str(x.journal_line_id) for x in lines],
                    "matched": valid,
                }
            )
            if not valid:
                issues.append("CURRENT_TREASURY_GL_EVIDENCE_UNVERIFIED")
    return _result(
        "blocked" if issues else "satisfied" if evidence else "not_applicable",
        evidence=evidence,
        issues=issues,
    )


def _recognition(
    organization: Organization,
    project: Project,
    actor: User,
    cutoff: datetime,
    sources: list[tuple[str, UUID]],
) -> dict:
    evidence, issues = [], []
    for kind, identity in sources:
        effects = (
            SourceRecognitionDraft.objects.filter(
                organization=organization,
                source_kind=kind,
                source_uuid=identity,
                created_at__lte=cutoff,
            )
            .select_related("journal")
            .order_by("created_at")
        )
        if not effects.exists():
            issues.append("ACCOUNTING_SOURCE_TARGET_MISSING")
        for effect in effects:
            valid = False
            try:
                source = read_source(
                    organization=organization,
                    actor=actor,
                    kind=kind,
                    identity=identity,
                    permission=P.ACCOUNTING_RECOGNITION_VIEW,
                    historical_event=effect.source_event,
                )
                expected = effect.target_snapshot
                actual = _journal_rows(effect.journal)
                keys = (
                    "source_line_uuid",
                    "account_id",
                    "project_id",
                    "site_id",
                    "wbs_node_id",
                    "party_id",
                )
                valid = (
                    source.occurred_on <= cutoff.date()
                    and digest(source.snapshot()) == effect.source_sha256
                    and effect.journal.status == "posted"
                    and effect.journal.accounting_date <= cutoff.date()
                    and effect.journal.source_uuid == identity
                    and effect.journal.reconciliation_reference == effect.source_sha256
                    and len(actual) == len(expected)
                    and bool(expected)
                    and all(
                        all(a[k] == b[k] for k in keys)
                        and Decimal(a["debit"]) == Decimal(b["debit"])
                        and Decimal(a["credit"]) == Decimal(b["credit"])
                        for a, b in zip(actual, expected, strict=True)
                    )
                )
            except (ValidationError, ObjectDoesNotExist):
                pass
            # Only the scoped source identity and its immutable reference are exposed.
            evidence.append(
                {
                    "kind": kind,
                    "source": str(identity),
                    "effect": str(effect.pk),
                    "source_version": effect.source_version_reference,
                    "source_hash": effect.source_sha256,
                    "journal": str(effect.journal_id),
                    "journal_status": effect.journal.status,
                    "matched": valid,
                }
            )
            if not valid:
                issues.append("POSTED_SOURCE_OWNER_RECOGNITION_UNVERIFIED")
    return _result(
        "unverifiable" if issues else "satisfied" if evidence else "not_applicable",
        evidence=evidence,
        issues=issues,
    )


@transaction.atomic
def financial_gate_snapshot(
    *,
    organization: Organization,
    project: Project,
    actor: User,
    cutoff: datetime,
    case=None,
) -> dict:
    """All eight explicit families, native policy only, stable economic watermark."""
    if project.organization_id != organization.pk:
        raise PermissionDenied("Project is outside the tenant.")
    require_financial_sources(organization, project, actor)
    Organization.objects.select_for_update().get(pk=organization.pk)
    try:
        cutoff = timezone.localtime(
            cutoff,
            ZoneInfo(
                OrganizationSettings.objects.get(organization=organization).timezone
            ),
        )
    except ObjectDoesNotExist:
        gates = {
            name: _result("unverifiable", issues=["ORGANIZATION_SETTINGS_MISSING"])
            for name in GATE_FAMILIES
        }
        return {
            "families": gates,
            "source_watermark": digest(gates),
            "projection_only": True,
            "outcome": "blocked",
        }
    subledger = settlement_reconciliation(
        organization=organization,
        actor=actor,
        project=project,
        as_of_date=cutoff.date(),
    )
    events = (
        list(case.events.filter(created_at__lte=cutoff).order_by("created_at", "pk"))
        if case
        else []
    )
    accepted = {}
    for event in events:
        if event.action == "coordinate":
            accepted.update(event.details.get("accepted_open_obligations", {}))
    sub_issues = [issue for row in subledger["rows"] for issue in row["issues"]]
    for row in subledger["rows"]:
        if (
            Decimal(row["outstanding"]) > 0
            and accepted.get(row["obligation"]) != row["economic_hash"]
        ):
            sub_issues.append("OPEN_OBLIGATION_REQUIRES_EXPLICIT_ACCEPTANCE")
    gates = {
        "accounting_period_controls": _accounting(organization, project, cutoff),
        "treasury_gl": _treasury(organization, project, cutoff),
        "subledger_settlement_control": _result(
            "blocked"
            if sub_issues
            else "satisfied"
            if subledger["rows"]
            else "not_applicable",
            evidence=subledger["rows"],
            issues=sub_issues,
        ),
    }
    stocks = apps.get_model("inventory.StockTransaction").objects.filter(
        organization=organization,
        project=project,
        status__in=("posted", "reversed"),
        occurred_at__lte=cutoff,
    )
    inventory = apps.get_model("inventory.InventoryValuationEvent").objects.filter(
        stock_transaction__in=stocks
    )
    gates["inventory_gl"] = _recognition(
        organization, project, actor, cutoff, [("inventory", x.pk) for x in inventory]
    )
    if stocks.exclude(valuation_event__isnull=False).exists():
        gates["inventory_gl"]["outcome"] = "unverifiable"
        gates["inventory_gl"]["issues"].append("VALUATION_SOURCE_MISSING")
    asset_sources = apps.get_model("fixed_assets.AssetTransaction").objects.filter(
        organization=organization,
        source_project=project,
        source_dimensions_captured=True,
        status__in=("finalized", "reversed"),
        occurred_on__lte=cutoff.date(),
    )
    depreciation_ids = set(
        apps.get_model("fixed_assets.DepreciationRun")
        .objects.filter(
            organization=organization,
            lines__asset__project=project,
            status__in=("finalized", "reversed"),
            fiscal_period__ends_on__lte=cutoff.date(),
            created_at__lte=cutoff,
        )
        .values_list("pk", flat=True)
    )
    depreciation_ids.update(
        SourceRecognitionDraft.objects.filter(
            organization=organization,
            source_kind="depreciation",
            source_snapshot__rows__contains=[{"project_id": str(project.pk)}],
            created_at__lte=cutoff,
        ).values_list("source_uuid", flat=True)
    )
    gates["fixed_assets_gl"] = _recognition(
        organization,
        project,
        actor,
        cutoff,
        [("asset", x.pk) for x in asset_sources]
        + [("depreciation", x) for x in depreciation_ids],
    )
    if (
        apps.get_model("fixed_assets.AssetTransaction")
        .objects.filter(
            organization=organization,
            asset__project=project,
            source_dimensions_captured=False,
            status__in=("finalized", "reversed"),
            occurred_on__lte=cutoff.date(),
        )
        .exists()
    ):
        gates["fixed_assets_gl"]["outcome"] = "unverifiable"
        gates["fixed_assets_gl"]["issues"].append(
            "HISTORICAL_ASSET_DIMENSIONS_UNVERIFIED"
        )
    # Payroll is conditional on actual activated downstream contracts, never labels.
    requests = apps.get_model("treasury.PaymentRequest").objects.filter(
        organization=organization,
        project=project,
        kind="payroll",
        created_at__lte=cutoff,
    )
    payroll_ids = (
        SourceRecognitionDraft.objects.filter(
            organization=organization,
            source_kind="payroll",
            source_snapshot__rows__contains=[{"project_id": str(project.pk)}],
            created_at__lte=cutoff,
        )
        .values_list("source_uuid", flat=True)
        .distinct()
    )
    payroll = _recognition(
        organization, project, actor, cutoff, [("payroll", x) for x in payroll_ids]
    )
    for request in requests.select_related("released_movement"):
        valid = request.status in {"cancelled", "rejected"} or (
            request.status == "released"
            and request.released_movement
            and request.released_movement.status == "posted"
        )
        payroll["evidence"].append(
            {
                "request": str(request.pk),
                "source_line": str(request.source_payroll_line_id),
                "source_version": request.source_payroll_version,
                "status": request.status,
            }
        )
        if not valid:
            payroll["issues"].append("PAYROLL_CASH_HANDOFF_UNRESOLVED")
    payroll["outcome"] = (
        "blocked"
        if payroll["issues"]
        else "satisfied"
        if payroll["evidence"]
        else "not_applicable"
    )
    gates["payroll_financial"] = payroll
    cost = get_project_cost_reconciliation(
        organization=organization, project=project, actor=actor
    )
    cost_evidence = json.loads(json.dumps(asdict(cost), default=str)) if cost else None
    cost_ready = bool(
        cost
        and cost.coverage_complete
        and cost.source_equivalence_established
        and cost.unresolved_total_difference == 0
    )
    gates["project_cost_sources"] = _result(
        "satisfied" if cost_ready else "unverifiable",
        evidence=[cost_evidence] if cost_evidence else [],
        issues=[] if cost_ready else ["PROJECT_COST_COVERAGE_UNVERIFIED"],
    )
    linked = {
        str(identity)
        for event in events
        for identity in event.details.get("blocking_exception_ids", [])
    }
    exceptions = ReconciliationException.objects.filter(
        organization=organization, run__project=project, pk__in=linked
    ).prefetch_related("events")
    exception_rows = []
    exception_issues = (
        ["LINKED_EXCEPTION_SCOPE_INVALID"] if exceptions.count() != len(linked) else []
    )
    for exception in exceptions:
        last = (
            exception.events.filter(created_at__lte=cutoff)
            .order_by("created_at", "pk")
            .last()
        )
        state = last.new_state if last else "open"
        exception_rows.append(
            {
                "exception": str(exception.pk),
                "state": state,
                "version": exception.snapshot_hash,
                "event": str(last.pk) if last else None,
            }
        )
        if state != "closed":
            exception_issues.append("LINKED_BLOCKING_EXCEPTION_UNRESOLVED")
    gates["linked_blocking_exceptions"] = _result(
        "blocked" if exception_issues else "satisfied",
        evidence=exception_rows,
        issues=exception_issues,
    )
    assert set(gates) == set(GATE_FAMILIES)
    return {
        "families": gates,
        "source_watermark": digest(gates),
        "as_of_date": cutoff.date().isoformat(),
        "projection_only": True,
        "outcome": "satisfied"
        if all(x["outcome"] in {"satisfied", "not_applicable"} for x in gates.values())
        else "blocked",
    }
