from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Exists, OuterRef, Q, Subquery, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.documents.models import DocumentVersion
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.models import Project
from apps.reporting.models import (
    ReconciliationEvidenceLink,
    ReconciliationException,
    ReconciliationExceptionEvent,
    ReconciliationOutcome,
    ReconciliationPairVersion,
    ReconciliationRebuildCheck,
    ReconciliationRun,
    ReconciliationRunReview,
    ReconciliationRunStatus,
    ReconciliationSideSnapshot,
    ReconciliationTieOut,
    ReconciliationVersionStatus,
)

RECONCILIATION_PERMISSION_CATALOGUE = (
    BusinessPermissionCode.REPORTING_RECONCILIATION_CATALOG_VIEW,
    BusinessPermissionCode.REPORTING_RECONCILIATION_DEFINITION_PREPARE,
    BusinessPermissionCode.REPORTING_RECONCILIATION_DEFINITION_PUBLISH,
    BusinessPermissionCode.REPORTING_RECONCILIATION_RUN_EXECUTE,
    BusinessPermissionCode.REPORTING_RECONCILIATION_RUN_VIEW,
    BusinessPermissionCode.REPORTING_RECONCILIATION_RUN_REVIEW,
    BusinessPermissionCode.REPORTING_RECONCILIATION_EXCEPTION_VIEW,
    BusinessPermissionCode.REPORTING_RECONCILIATION_EXCEPTION_ASSIGN,
    BusinessPermissionCode.REPORTING_RECONCILIATION_EXCEPTION_DISPOSITION,
    BusinessPermissionCode.REPORTING_RECONCILIATION_EXCEPTION_CLOSE,
    BusinessPermissionCode.REPORTING_RECONCILIATION_EXCEPTION_REOPEN,
    BusinessPermissionCode.REPORTING_RECONCILIATION_EVIDENCE_LINK,
    BusinessPermissionCode.REPORTING_RECONCILIATION_REBUILD_EXECUTE,
    BusinessPermissionCode.REPORTING_RECONCILIATION_REBUILD_REVIEW,
    BusinessPermissionCode.REPORTING_RECONCILIATION_AUDIT_VIEW,
)


def _json_default(value: object) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _hash(payload: object) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=_json_default
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _advisory_lock(*parts: object) -> None:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    lock_id = int.from_bytes(digest[:8], byteorder="big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])


def _model(label: str):
    return apps.get_model(label)


def _decimal(value: Decimal | int | str | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _sum(queryset, field: str) -> Decimal | None:
    return _decimal(queryset.aggregate(total=Sum(field))["total"])


def _ids(queryset) -> list[str]:
    return [
        str(value) for value in queryset.order_by("pk").values_list("pk", flat=True)
    ]


def _scoped(queryset, project: Project | None, field: str = "project"):
    return queryset.filter(**{field: project}) if project is not None else queryset


def _at_cutoff(queryset, cutoff_at, field: str = "created_at"):
    return queryset.filter(**{f"{field}__lte": cutoff_at})


@dataclass(frozen=True, slots=True)
class SideData:
    authority: str
    model: str
    readiness: str
    value: dict[str, str | int | None]
    manifest: dict[str, object]


@dataclass(frozen=True, slots=True)
class PairData:
    left: SideData
    right: SideData
    comparable_key: str | None
    currency: str = ""
    unit: str = ""


def _side(
    authority: str,
    model: str,
    rows,
    *,
    amount: Decimal | None = None,
    readiness: str | None = None,
    extra: dict[str, str | int | None] | None = None,
) -> SideData:
    row_ids = _ids(rows)
    actual_readiness = readiness or ("ready" if row_ids else "unknown")
    value: dict[str, str | int | None] = {
        "amount": format(amount, "f") if amount is not None else None,
        "count": len(row_ids),
    }
    if extra:
        value.update(extra)
    return SideData(
        authority=authority,
        model=model,
        readiness=actual_readiness,
        value=value,
        manifest={"model": model, "ids": row_ids},
    )


def _estimate_budget(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    lines = _model("projects.BudgetManifestLine").objects.filter(
        organization=organization,
        manifest__budget__status="accepted",
    )
    allocations = _model("projects.BudgetAllocation").objects.filter(
        organization=organization,
        manifest_line__manifest__budget__status="accepted",
    )
    lines = _at_cutoff(lines, cutoff_at)
    allocations = _at_cutoff(allocations, cutoff_at)
    lines = _scoped(lines, project, "manifest__budget__project")
    allocations = _scoped(
        allocations, project, "manifest_line__manifest__budget__project"
    )
    return PairData(
        _side(
            "Estimation",
            "projects.BudgetManifestLine",
            lines,
            amount=_sum(lines, "source_amount"),
        ),
        _side(
            "Project Controls / Budget",
            "projects.BudgetAllocation",
            allocations,
            amount=_sum(allocations, "amount"),
        ),
        "amount",
        currency="IRR",
        unit="money",
    )


def _commitment_projection(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    """Retain source visibility without asserting an unapproved direct comparison."""
    contracts = _model("projects.ProjectCostSourceContract").objects.filter(
        organization=organization, status="approved"
    )
    po_lines = _model("procurement.PurchaseOrderVersionLine").objects.filter(
        organization=organization
    )
    contracts = _at_cutoff(contracts, cutoff_at)
    po_lines = _at_cutoff(po_lines, cutoff_at)
    po_lines = _scoped(po_lines, project, "version__purchase_order__project")
    facts = _model("projects.ProjectCostFact").objects.filter(
        organization=organization,
        kind__in=[
            "commitment_authorized",
            "commitment_adjustment",
            "commitment_relief",
        ],
    )
    facts = _at_cutoff(facts, cutoff_at)
    facts = _scoped(facts, project)
    return PairData(
        _side(
            "Procurement or Contracts",
            "procurement.PurchaseOrderVersionLine",
            po_lines,
            readiness="uncomparable",
        ),
        _side(
            "Project Controls",
            "projects.ProjectCostFact",
            facts,
            readiness="uncomparable",
        ),
        None,
        currency="IRR",
        unit="money",
    )


def _po_receipt_invoice(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    lines = _model("subledgers.SupplierInvoiceMatchLine").objects.filter(
        organization=organization
    )
    lines = _at_cutoff(lines, cutoff_at)
    lines = _scoped(lines, project, "match__invoice_version__invoice__project")
    ordered = Decimal(0)
    invoiced = Decimal(0)
    for line in lines:
        ordered += line.accepted_quantity * line.ordered_unit_price
        invoiced += line.invoiced_quantity * line.invoiced_unit_price
    left = _side(
        "Procurement",
        "subledgers.SupplierInvoiceMatchLine",
        lines,
        amount=ordered if lines.exists() else None,
        extra={
            "accepted_quantity": format(
                sum((line.accepted_quantity for line in lines), Decimal(0)), "f"
            )
            if lines.exists()
            else None
        },
    )
    right = _side(
        "AP/Finance and Matching",
        "subledgers.SupplierInvoiceMatchLine",
        lines,
        amount=invoiced if lines.exists() else None,
        extra={
            "invoiced_quantity": format(
                sum((line.invoiced_quantity for line in lines), Decimal(0)), "f"
            )
            if lines.exists()
            else None
        },
    )
    return PairData(left, right, "amount", unit="quantity_and_money")


def _inventory_quantity_value(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    transactions = _model("inventory.StockTransaction").objects.filter(
        organization=organization, status="posted"
    )
    transactions = _at_cutoff(transactions, cutoff_at, "occurred_at")
    transactions = _scoped(transactions, project)
    quantity = Decimal(0)
    for row in transactions.select_related("reversal_of"):
        if row.transaction_type in {"receipt", "adjustment_in"}:
            quantity += row.quantity
        elif row.transaction_type in {"issue", "adjustment_out"}:
            quantity -= row.quantity
        elif row.transaction_type == "reversal" and row.reversal_of_id:
            quantity += (
                -row.quantity
                if row.reversal_of.transaction_type in {"receipt", "adjustment_in"}
                else row.quantity
            )
    pools = _model("inventory.InventoryValuationPool").objects.filter(
        organization=organization
    )
    pools = _at_cutoff(pools, cutoff_at)
    currencies = list(pools.values_list("currency", flat=True).distinct())
    return PairData(
        _side(
            "Inventory Custody",
            "inventory.StockTransaction",
            transactions,
            readiness="uncomparable",
            extra={
                "quantity": format(quantity, "f") if transactions.exists() else None
            },
        ),
        _side(
            "Inventory Valuation",
            "inventory.InventoryValuationPool",
            pools,
            readiness="uncomparable",
            extra={
                "quantity": format(_sum(pools, "quantity"), "f")
                if _sum(pools, "quantity") is not None
                else None
            },
        ),
        None,
        currency=currencies[0] if len(currencies) == 1 else "",
        unit="quantity_and_money",
    )


def _claim_settlement(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    claims = _model("billing.ProgressClaim").objects.filter(
        organization=organization, status="approved"
    )
    claims = _at_cutoff(claims, cutoff_at)
    claims = _scoped(claims, project)
    from apps.billing.handoffs import PROGRESS_CLAIM_SOURCE_KIND

    # Exact source/version/context matching prevents unrelated AR or superseded
    # claim revisions from being counted. Cash is never added to allocations.
    matched_claims = claims.filter(
        pk=OuterRef("obligation__source_uuid"),
        revision_number=OuterRef("obligation__source_version"),
        project_id=OuterRef("obligation__project_id"),
        contract_id=OuterRef("obligation__contract_id"),
    )
    allocations = _model("subledgers.SettlementAllocation").objects.filter(
        Exists(matched_claims),
        organization=organization,
        obligation__organization=organization,
        obligation__source_kind=PROGRESS_CLAIM_SOURCE_KIND,
        obligation__direction="receivable",
        treasury_movement__organization=organization,
    ).filter(Q(reversal__isnull=True) | Q(reversal__created_at__gt=cutoff_at))
    allocations = _at_cutoff(allocations, cutoff_at)
    return PairData(
        _side(
            "Billing",
            "billing.ProgressClaim",
            claims,
            amount=_sum(claims, "net_amount"),
        ),
        _side(
            "Treasury and AP/AR",
            "subledgers.SettlementAllocation",
            allocations,
            amount=_sum(allocations, "amount"),
        ),
        "amount",
        unit="money",
    )


def _subledger_gl(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    del project
    slices = _model("subledgers.SubledgerReconciliationAccountSlice").objects.filter(
        organization=organization
    )
    slices = _at_cutoff(slices, cutoff_at).filter(invalidation__isnull=True)
    latest = slices.filter(
        organization_id=OuterRef("organization_id"),
        direction=OuterRef("direction"),
        as_of_date=OuterRef("as_of_date"),
        control_account_id=OuterRef("control_account_id"),
        invalidation__isnull=True,
    ).order_by("-grain_revision")
    slices = slices.filter(grain_revision=Subquery(latest.values("grain_revision")[:1]))
    left = _sum(slices, "subledger_outstanding_total")
    right = _sum(slices, "linked_gl_total")
    return PairData(
        _side(
            "AP/AR",
            "subledgers.SubledgerReconciliationAccountSlice",
            slices,
            amount=left,
        ),
        _side(
            "Accounting / GL",
            "subledgers.SubledgerReconciliationAccountSlice",
            slices,
            amount=right,
        ),
        "amount",
        unit="money",
    )


def _treasury_bank(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    del project
    runs = _model("treasury.BankReconciliationRun").objects.filter(
        organization=organization
    )
    runs = _at_cutoff(runs, cutoff_at).filter(
        grain_revision__isnull=False, invalidation__isnull=True
    )
    latest = runs.filter(
        organization_id=OuterRef("organization_id"),
        account_id=OuterRef("account_id"),
        statement_import_id=OuterRef("statement_import_id"),
        as_of_date=OuterRef("as_of_date"),
        invalidation__isnull=True,
    ).order_by("-grain_revision")
    runs = runs.filter(grain_revision=Subquery(latest.values("grain_revision")[:1]))
    book = (
        (_sum(runs, "cleared_book_in") or Decimal(0))
        - (_sum(runs, "cleared_book_out") or Decimal(0))
        if runs.exists()
        else None
    )
    statement = (
        (_sum(runs, "statement_in") or Decimal(0))
        - (_sum(runs, "statement_out") or Decimal(0))
        if runs.exists()
        else None
    )
    return PairData(
        _side("Treasury", "treasury.BankReconciliationRun", runs, amount=book),
        _side(
            "Treasury Bank Reconciliation",
            "treasury.BankReconciliationRun",
            runs,
            amount=statement,
        ),
        "amount",
        unit="money",
    )


def _treasury_gl(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    del project
    slices = _model("treasury.TreasuryGLReconciliationSlice").objects.filter(
        organization=organization
    )
    slices = _at_cutoff(slices, cutoff_at).filter(invalidation__isnull=True)
    latest = slices.filter(
        organization_id=OuterRef("organization_id"),
        cutoff_date=OuterRef("cutoff_date"),
        currency=OuterRef("currency"),
        treasury_account_id=OuterRef("treasury_account_id"),
        invalidation__isnull=True,
    ).order_by("-grain_revision")
    slices = slices.filter(grain_revision=Subquery(latest.values("grain_revision")[:1]))
    treasury = (
        (_sum(slices, "treasury_in") or Decimal(0))
        - (_sum(slices, "treasury_out") or Decimal(0))
        if slices.exists()
        else None
    )
    ledger = (
        (_sum(slices, "journal_debit") or Decimal(0))
        - (_sum(slices, "journal_credit") or Decimal(0))
        if slices.exists()
        else None
    )
    return PairData(
        _side(
            "Treasury",
            "treasury.TreasuryGLReconciliationSlice",
            slices,
            amount=treasury,
        ),
        _side(
            "Accounting / GL",
            "treasury.TreasuryGLReconciliationSlice",
            slices,
            amount=ledger,
        ),
        "amount",
        unit="money",
    )


def _project_cost_sources(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    contracts = _model("projects.ProjectCostSourceContract").objects.filter(
        organization=organization, status="approved"
    )
    facts = _model("projects.ProjectCostFact").objects.filter(organization=organization)
    contracts = _at_cutoff(contracts, cutoff_at)
    facts = _at_cutoff(facts, cutoff_at)
    facts = _scoped(facts, project)
    return PairData(
        _side(
            "Registered Source Domains",
            "projects.ProjectCostSourceContract",
            contracts,
            readiness="uncomparable",
        ),
        _side(
            "Project Controls",
            "projects.ProjectCostFact",
            facts,
            readiness="uncomparable",
        ),
        None,
        unit="count_and_money",
    )


def _payroll_insurance(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    del project
    rows = _model("payroll.StatutoryReconciliation").objects.filter(
        organization=organization, output__calculation__kind="employee_insurance"
    )
    rows = _at_cutoff(rows, cutoff_at)
    return PairData(
        _side(
            "Payroll",
            "payroll.StatutoryReconciliation",
            rows,
            amount=_sum(rows, "calculation_total"),
        ),
        _side(
            "Payroll Statutory",
            "payroll.StatutoryReconciliation",
            rows,
            amount=_sum(rows, "output_total"),
        ),
        "amount",
        unit="money",
    )


def _payroll_financial_handoffs(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    del project
    proposals = _model("payroll.FinancialHandoffProposal").objects.filter(
        organization=organization
    )
    acknowledgements = _model("payroll.FinancialHandoffAcknowledgement").objects.filter(
        organization=organization, proposal__in=proposals
    )
    proposals = _at_cutoff(proposals, cutoff_at)
    acknowledgements = _at_cutoff(acknowledgements, cutoff_at)
    readiness = None if proposals.exists() else "gated_not_activated"
    return PairData(
        _side(
            "Payroll",
            "payroll.FinancialHandoffProposal",
            proposals,
            amount=_sum(proposals, "total_amount"),
            readiness=readiness,
        ),
        _side(
            "Named Downstream Domain",
            "payroll.FinancialHandoffAcknowledgement",
            acknowledgements,
            amount=_sum(acknowledgements, "acknowledged_amount"),
            readiness=readiness,
        ),
        "amount" if readiness is None else None,
        unit="money",
    )


def _fixed_asset_handoffs(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    envelopes = _model("fixed_assets.FixedAssetSourceEnvelope").objects.filter(
        organization=organization
    )
    envelopes = _at_cutoff(envelopes, cutoff_at)
    if project is not None:
        envelopes = envelopes.filter(
            asset_transaction__asset__project=project
        ) | envelopes.filter(depreciation_line__asset__project=project)
    acknowledged = envelopes.exclude(consumer_reference="")
    readiness = None if envelopes.exists() else "gated_not_activated"
    return PairData(
        _side(
            "Fixed Assets",
            "fixed_assets.FixedAssetSourceEnvelope",
            envelopes,
            amount=_sum(envelopes, "amount"),
            readiness=readiness,
        ),
        _side(
            "Accounting or Project Controls",
            "fixed_assets.FixedAssetSourceEnvelope",
            acknowledged,
            amount=_sum(acknowledged, "amount"),
            readiness=readiness,
        ),
        "amount" if readiness is None else None,
        unit="money",
    )


def _contractor_compliance(
    organization: Organization, project: Project | None, cutoff_at
) -> PairData:
    assessments = _model("billing.ContractorComplianceAssessment").objects.filter(
        organization=organization, status="approved"
    )
    assessments = _at_cutoff(assessments, cutoff_at)
    assessments = _scoped(assessments, project)
    return PairData(
        _side(
            "Contracts / Compliance",
            "billing.ContractorComplianceAssessment",
            assessments,
            amount=_sum(assessments, "deduction_amount"),
        ),
        SideData(
            authority="Contract, AP or Accounting Consumer",
            model="gated.consumer",
            readiness="gated_not_activated",
            value={"amount": None, "count": 0},
            manifest={"model": "gated.consumer", "ids": []},
        ),
        None,
        unit="money",
    )


ADAPTERS = {
    "estimate_budget": _estimate_budget,
    "commitment_projection": _commitment_projection,
    "po_receipt_invoice": _po_receipt_invoice,
    "inventory_quantity_value": _inventory_quantity_value,
    "claim_settlement": _claim_settlement,
    "subledger_gl": _subledger_gl,
    "treasury_bank": _treasury_bank,
    "treasury_gl": _treasury_gl,
    "project_cost_sources": _project_cost_sources,
    "payroll_insurance": _payroll_insurance,
    "payroll_financial_handoffs": _payroll_financial_handoffs,
    "fixed_asset_handoffs": _fixed_asset_handoffs,
    "contractor_compliance": _contractor_compliance,
}

ORGANIZATION_ONLY_PAIRS = frozenset(
    {
        "inventory_quantity_value",
        "subledger_gl",
        "treasury_bank",
        "treasury_gl",
        "payroll_insurance",
        "payroll_financial_handoffs",
    }
)


def resolve_reconciliation_tolerance(
    data: PairData, specification: dict[str, object]
) -> dict[str, object]:
    """Resolve only governed comparison rules; never borrow a matching policy.

    No approved source-family aggregate tolerance contract is configured today.
    Native run amounts and invoice-match basis points do not supply that contract.
    Keep this boundary explicit until a source-owned resolver is approved.
    """
    rule = specification.get("tolerance")
    kind = rule.get("kind") if isinstance(rule, dict) else None
    result: dict[str, object] = {
        "kind": kind,
        "source_models": [data.left.model, data.right.model],
        "applied": False,
        "absolute": None,
        "difference_visible": True,
        "status": "unconfigured",
        "reason": "approved_source_tolerance_absent",
    }
    if kind == "exact":
        try:
            absolute = Decimal(str(rule.get("absolute")))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError("قاعده تطبیق دقیق معتبر نیست.") from exc
        if not absolute.is_finite() or absolute != 0:
            raise ValidationError("تطبیق دقیق فقط اختلاف صفر را می‌پذیرد.")
        result.update(
            absolute="0",
            status="resolved",
            reason="catalogue_exact_comparison",
        )
    return result


def _compare(
    data: PairData, specification: dict[str, object]
) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]]:
    tolerance_result = resolve_reconciliation_tolerance(data, specification)
    readiness = {data.left.readiness, data.right.readiness}
    if "gated_not_activated" in readiness:
        return (
            ReconciliationOutcome.GATED,
            {},
            tolerance_result,
            {"material": True, "reason": "gated_dependency"},
        )
    if "uncomparable" in readiness:
        return (
            ReconciliationOutcome.UNCOMPARABLE,
            {},
            tolerance_result,
            {"material": True, "reason": "unaligned_dimension"},
        )
    if "incomplete" in readiness:
        return (
            ReconciliationOutcome.INCOMPLETE,
            {},
            tolerance_result,
            {"material": True, "reason": "incomplete_coverage"},
        )
    if "unknown" in readiness or data.comparable_key is None:
        return (
            ReconciliationOutcome.UNKNOWN,
            {},
            tolerance_result,
            {"material": True, "reason": "unknown_value"},
        )
    left_value = data.left.value.get(data.comparable_key)
    right_value = data.right.value.get(data.comparable_key)
    if left_value is None and right_value is None:
        return (
            ReconciliationOutcome.UNKNOWN,
            {},
            tolerance_result,
            {"material": True, "reason": "unknown_value"},
        )
    if left_value is None:
        return (
            ReconciliationOutcome.MISSING_LEFT,
            {},
            tolerance_result,
            {"material": True, "reason": "missing_expected_side"},
        )
    if right_value is None:
        return (
            ReconciliationOutcome.MISSING_RIGHT,
            {},
            tolerance_result,
            {"material": True, "reason": "missing_expected_side"},
        )
    left_decimal = _decimal(left_value)
    right_decimal = _decimal(right_value)
    if left_decimal is None or right_decimal is None:
        return (
            ReconciliationOutcome.UNKNOWN,
            {},
            tolerance_result,
            {"material": True, "reason": "unknown_value"},
        )
    difference = left_decimal - right_decimal
    # Exact equality requires no tolerance approval. Any non-zero difference
    # remains an exception when the source-family policy is absent.
    tolerance_result["applied"] = tolerance_result["status"] == "resolved"
    outcome = (
        ReconciliationOutcome.MATCHED_EXACT
        if difference == 0
        else ReconciliationOutcome.MISMATCH
    )
    materiality_spec = dict(specification.get("materiality", {}))
    materiality = _decimal(materiality_spec.get("absolute")) or Decimal(0)
    qualitative = outcome not in {
        ReconciliationOutcome.MATCHED_EXACT,
        ReconciliationOutcome.MATCHED_WITHIN_TOLERANCE,
    }
    return (
        outcome,
        {"key": data.comparable_key, "amount": format(difference, "f")},
        tolerance_result,
        {
            "material": qualitative or abs(difference) > materiality,
            "absolute": format(materiality, "f"),
            **(
                {"reason": "approved_source_tolerance_absent"}
                if difference != 0 and tolerance_result["status"] != "resolved"
                else {}
            ),
        },
    )


def _require_pair_sources(
    *,
    actor: User,
    organization: Organization,
    project: Project | None,
    spec: dict[str, object],
) -> None:
    for permission in spec["source_permissions"]:
        require_business_permission(
            user=actor,
            organization=organization,
            permission=str(permission),
            message="مجوز دامنه منبع برای اجرای تطبیق وجود ندارد.",
            project=project,
        )


@transaction.atomic
def execute_reconciliation(
    *,
    organization: Organization,
    actor: User,
    pair_code: str,
    idempotency_key: str,
    cutoff_at=None,
    project: Project | None = None,
    replaces: ReconciliationRun | None = None,
    comparison_context: dict[str, str] | None = None,
) -> ReconciliationRun:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.REPORTING_RECONCILIATION_RUN_EXECUTE,
        message="اجازه اجرای تطبیق را ندارید.",
        project=project,
    )
    if project is not None and project.organization_id != organization.pk:
        raise PermissionDenied("پروژه متعلق به شرکت فعال نیست.")
    if project is not None and pair_code in ORGANIZATION_ONLY_PAIRS:
        raise ValidationError("این جفت فقط با دامنه کامل شرکت قابل اجرا است.")
    cutoff = cutoff_at or timezone.now()
    _advisory_lock(
        "reporting-reconciliation", organization.pk, pair_code, idempotency_key
    )
    version = (
        ReconciliationPairVersion.objects.select_for_update()
        .select_related("definition")
        .get(
            definition__code=pair_code,
            definition__is_active=True,
            status=ReconciliationVersionStatus.PUBLISHED,
        )
    )
    spec = version.specification
    _require_pair_sources(
        actor=actor, organization=organization, project=project, spec=spec
    )
    if pair_code == "attendance_timesheet":
        from apps.timekeeping.reconciliation import validate_context

        validate_context(organization, actor, project, comparison_context)
    elif comparison_context is not None:
        raise ValidationError("این جفت زمینه کارکرد نمی‌پذیرد.")
    fingerprint = _hash(
        {
            "pair_version": str(version.pk),
            "organization": str(organization.pk),
            "project": str(project.pk) if project else None,
            "cutoff": cutoff.isoformat(),
            "replaces": str(replaces.pk) if replaces else None,
            **(
                {"comparison_context": comparison_context} if comparison_context else {}
            ),
        }
    )
    existing = (
        ReconciliationRun.objects.select_for_update()
        .filter(organization=organization, idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError("کلید تکرار تطبیق با درخواست متفاوت استفاده شده است.")
        if existing.status == ReconciliationRunStatus.COMPLETED:
            _guard_context(existing, actor)
            return existing
        raise ValidationError("اجرای قبلی این کلید نهایی نشده است.")
    if replaces is not None:
        if (
            replaces.organization_id != organization.pk
            or replaces.pair_version.definition_id != version.definition_id
        ):
            raise ValidationError("اجرای جانشین باید برای همان شرکت و جفت تطبیق باشد.")
        ReconciliationRun.objects.select_for_update().get(pk=replaces.pk)
        _guard_context(replaces, actor)
    now = timezone.now()
    run = ReconciliationRun.objects.create(
        organization=organization,
        pair_version=version,
        project=project,
        status=ReconciliationRunStatus.CAPTURING,
        cutoff_at=cutoff,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        requested_by=actor,
        started_at=now,
        replaces=replaces,
    )
    if pair_code == "attendance_timesheet":
        from apps.timekeeping.reconciliation import capture

        data = capture(organization, actor, project, cutoff, comparison_context)
        if replaces:
            prior = replaces.side_snapshots.get(side="left").source_manifest
            if (
                prior["period"] != data.left.manifest["period"]
                or prior["context"]["relationship_id"]
                != comparison_context["relationship_id"]
                or replaces.project_id != run.project_id
            ):
                raise ValidationError("جانشین تطبیق باید همان هویت، دوره و دامنه باشد.")
    else:
        adapter = ADAPTERS[str(spec["adapter"])]
        data = adapter(organization, project, cutoff)
    side_payloads = []
    for side_name, side in (("left", data.left), ("right", data.right)):
        payload = {
            "authority": side.authority,
            "model": side.model,
            "readiness": side.readiness,
            "value": side.value,
            "manifest": side.manifest,
            "cutoff": cutoff.isoformat(),
        }
        side_payloads.append(payload)
        ReconciliationSideSnapshot.objects.create(
            organization=organization,
            run=run,
            side=side_name,
            authority_domain=side.authority,
            authority_model=side.model,
            readiness=side.readiness,
            value=side.value,
            source_manifest={**side.manifest, "cutoff": cutoff.isoformat()},
            source_hash=_hash(payload),
        )
    ReconciliationRun.objects.filter(pk=run.pk).update(
        status=ReconciliationRunStatus.COMPARING
    )
    if pair_code == "attendance_timesheet":
        from apps.timekeeping.reconciliation import compare

        outcome, difference, tolerance_result, materiality_result = compare(data)
    else:
        outcome, difference, tolerance_result, materiality_result = _compare(data, spec)
    tolerance_result["pair_version_id"] = str(version.pk)
    tolerance_result["specification_hash"] = _hash(spec)
    tie_payload = {
        "pair": pair_code,
        "version": version.version,
        "sides": side_payloads,
        "outcome": outcome,
        "difference": difference,
        "tolerance": tolerance_result,
        "materiality": materiality_result,
    }
    ReconciliationTieOut.objects.create(
        organization=organization,
        run=run,
        outcome=outcome,
        difference=difference,
        tolerance_result=tolerance_result,
        materiality_result=materiality_result,
        coverage={
            "left": data.left.readiness,
            "right": data.right.readiness,
            "currency": data.currency,
            "unit": data.unit,
        },
        calculation_hash=_hash(tie_payload),
    )
    if outcome not in {
        ReconciliationOutcome.MATCHED_EXACT,
        ReconciliationOutcome.MATCHED_WITHIN_TOLERANCE,
        ReconciliationOutcome.NOT_APPLICABLE,
    }:
        exception_payload = {
            "run": str(run.pk),
            "classification": materiality_result.get("reason", outcome),
            "left": data.left.manifest,
            "right": data.right.manifest,
            "difference": difference,
        }
        ReconciliationException.objects.create(
            organization=organization,
            run=run,
            exception_key=_hash(exception_payload),
            classification=str(materiality_result.get("reason", outcome)),
            materiality="material"
            if materiality_result.get("material")
            else "non_material",
            comparison_grain={
                "pair": pair_code,
                "project": str(project.pk) if project else None,
                **(
                    {
                        "context": comparison_context,
                        "period": data.left.manifest["period"],
                    }
                    if pair_code == "attendance_timesheet"
                    else {}
                ),
            },
            left_lineage=data.left.manifest,
            right_lineage=data.right.manifest,
            difference=difference,
            evidence_manifest={
                "cutoff": cutoff.isoformat(),
                "pair_version": str(version.pk),
            },
            snapshot_hash=_hash(exception_payload),
        )
    watermark = _hash(side_payloads)
    ReconciliationRun.objects.filter(pk=run.pk).update(
        status=ReconciliationRunStatus.COMPLETED,
        source_watermark=watermark,
        finished_at=timezone.now(),
    )
    run.refresh_from_db()
    record_audit_event(
        action=AuditAction.REPORTING_RECONCILIATION_RUN,
        entity_type="reporting.ReconciliationRun",
        entity_id=str(run.pk),
        organization=organization,
        actor=actor,
        metadata={
            "pair_code": pair_code,
            "outcome": outcome,
            "tolerance": tolerance_result,
        },
    )
    return run


@transaction.atomic
def review_reconciliation_run(
    *, run: ReconciliationRun, reviewer: User, decision: str, reason: str
) -> ReconciliationRunReview:
    locked = (
        ReconciliationRun.objects.select_for_update()
        .select_related("pair_version__definition")
        .get(pk=run.pk)
    )
    _guard_context(locked, reviewer, review=True)
    require_business_permission(
        user=reviewer,
        organization=locked.organization,
        permission=BusinessPermissionCode.REPORTING_RECONCILIATION_RUN_REVIEW,
        message="اجازه بررسی اجرای تطبیق را ندارید.",
        project=locked.project,
    )
    if locked.requested_by_id == reviewer.pk:
        raise PermissionDenied("اجراکننده نمی‌تواند اجرای مالی خود را بررسی کند.")
    if decision not in ReconciliationRunReview.Decision.values:
        raise ValidationError("تصمیم بررسی معتبر نیست.")
    evidence_hash = _hash(
        {
            "run": str(locked.pk),
            "tie_out": locked.tie_out.calculation_hash,
            "decision": decision,
            "reason": reason.strip(),
        }
    )
    review, created = ReconciliationRunReview.objects.get_or_create(
        organization=locked.organization,
        run=locked,
        defaults={
            "decision": decision,
            "reviewer": reviewer,
            "reason": reason.strip(),
            "evidence_hash": evidence_hash,
        },
    )
    if not created and review.evidence_hash != evidence_hash:
        raise ValidationError("اجرای تطبیق قبلاً با شاهد متفاوت بررسی شده است.")
    record_audit_event(
        action=AuditAction.REPORTING_RECONCILIATION_REVIEW,
        entity_type="reporting.ReconciliationRunReview",
        entity_id=str(review.pk),
        organization=locked.organization,
        actor=reviewer,
        metadata={"decision": decision},
    )
    return review


def _current_exception_state(
    exception: ReconciliationException,
) -> tuple[str, User | None]:
    latest = exception.events.order_by("created_at", "pk").last()
    return (latest.new_state, latest.actor) if latest else ("open", None)


@transaction.atomic
def record_exception_event(
    *,
    exception: ReconciliationException,
    actor: User,
    action: str,
    reason: str,
    operation_key: str,
    assigned_to: User | None = None,
    correction_reference: dict[str, object] | None = None,
) -> ReconciliationExceptionEvent:
    locked = (
        ReconciliationException.objects.select_for_update()
        .select_related("run", "organization")
        .get(pk=exception.pk)
    )
    _guard_context(
        locked.run, actor, review=True, correction_reference=correction_reference
    )
    if assigned_to is not None:
        _guard_context(locked.run, assigned_to, review=True)
    permission_by_action = {
        "assign": BusinessPermissionCode.REPORTING_RECONCILIATION_EXCEPTION_ASSIGN,
        "disposition": BusinessPermissionCode.REPORTING_RECONCILIATION_EXCEPTION_DISPOSITION,
        "close": BusinessPermissionCode.REPORTING_RECONCILIATION_EXCEPTION_CLOSE,
        "reopen": BusinessPermissionCode.REPORTING_RECONCILIATION_EXCEPTION_REOPEN,
    }
    if action not in permission_by_action:
        raise ValidationError("اقدام مغایرت معتبر نیست.")
    require_business_permission(
        user=actor,
        organization=locked.organization,
        permission=permission_by_action[action],
        message="اجازه اقدام روی مغایرت را ندارید.",
        project=locked.run.project,
    )
    fingerprint = _hash(
        {
            "exception": str(locked.pk),
            "action": action,
            "reason": reason.strip(),
            "assigned_to": str(assigned_to.pk) if assigned_to else None,
            "correction_reference": correction_reference or {},
        }
    )
    existing = ReconciliationExceptionEvent.objects.filter(
        organization=locked.organization, operation_key=operation_key
    ).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError(
                "کلید تکرار رویداد با درخواست متفاوت استفاده شده است."
            )
        return existing
    current, last_actor = _current_exception_state(locked)
    transitions = {
        "assign": ({"open", "assigned", "in_review"}, "assigned"),
        "disposition": ({"open", "assigned", "in_review"}, "disposition_recorded"),
        "close": ({"disposition_recorded", "close_pending"}, "closed"),
        "reopen": ({"closed"}, "reopened"),
    }
    allowed, target = transitions[action]
    if current not in allowed:
        raise ValidationError("گذار وضعیت مغایرت مجاز نیست.")
    if (
        action == "close"
        and locked.materiality == "material"
        and last_actor
        and last_actor.pk == actor.pk
    ):
        raise PermissionDenied(
            "ثبت‌کننده آخرین تصمیم نمی‌تواند مغایرت بااهمیت را به‌تنهایی ببندد."
        )
    if action == "reopen" and not reason.strip():
        raise ValidationError("بازگشایی به دلیل صریح نیاز دارد.")
    event = ReconciliationExceptionEvent.objects.create(
        organization=locked.organization,
        exception=locked,
        action=action,
        previous_state=current,
        new_state=target,
        reason=reason.strip(),
        correction_reference=correction_reference or {},
        actor=actor,
        assigned_to=assigned_to,
        operation_key=operation_key,
        request_fingerprint=fingerprint,
    )
    record_audit_event(
        action=AuditAction.REPORTING_RECONCILIATION_EXCEPTION,
        entity_type="reporting.ReconciliationExceptionEvent",
        entity_id=str(event.pk),
        organization=locked.organization,
        actor=actor,
        metadata={"action": action, "exception_id": str(locked.pk)},
    )
    return event


@transaction.atomic
def link_exception_evidence(
    *,
    exception: ReconciliationException,
    actor: User,
    document_version: DocumentVersion,
    evidence_role: str,
    sensitivity: str = "normal",
) -> ReconciliationEvidenceLink:
    _guard_context(exception.run, actor, review=True)
    require_business_permission(
        user=actor,
        organization=exception.organization,
        permission=BusinessPermissionCode.REPORTING_RECONCILIATION_EVIDENCE_LINK,
        message="اجازه پیوند شاهد تطبیق را ندارید.",
        project=exception.run.project,
    )
    require_business_permission(
        user=actor,
        organization=exception.organization,
        permission=BusinessPermissionCode.DOCUMENTS_VIEW,
        message="اجازه مشاهده نسخه سند را ندارید.",
        project=exception.run.project,
    )
    if document_version.organization_id != exception.organization_id:
        raise PermissionDenied("نسخه سند متعلق به شرکت فعال نیست.")
    return ReconciliationEvidenceLink.objects.create(
        organization=exception.organization,
        exception=exception,
        document_version=document_version,
        document_hash=document_version.sha256,
        evidence_role=evidence_role.strip(),
        sensitivity=sensitivity,
        linked_by=actor,
    )


@transaction.atomic
def replay_reconciliation(
    *,
    original_run: ReconciliationRun,
    actor: User,
    idempotency_key: str,
) -> ReconciliationRebuildCheck:
    locked = (
        ReconciliationRun.objects.select_for_update()
        .select_related("pair_version__definition", "organization")
        .get(pk=original_run.pk)
    )
    _guard_context(locked, actor)
    require_business_permission(
        user=actor,
        organization=locked.organization,
        permission=BusinessPermissionCode.REPORTING_RECONCILIATION_REBUILD_EXECUTE,
        message="اجازه بازپخش تطبیق را ندارید.",
        project=locked.project,
    )
    spec = locked.pair_version.specification
    _require_pair_sources(
        actor=actor,
        organization=locked.organization,
        project=locked.project,
        spec=spec,
    )
    fingerprint = _hash({"run": str(locked.pk), "kind": "exact_replay"})
    existing = ReconciliationRebuildCheck.objects.filter(
        organization=locked.organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise ValidationError(
                "کلید تکرار بازسازی با درخواست متفاوت استفاده شده است."
            )
        return existing
    if locked.pair_version.definition.code == "attendance_timesheet":
        from apps.timekeeping.reconciliation import capture

        current = capture(
            locked.organization,
            actor,
            locked.project,
            locked.cutoff_at,
            locked.side_snapshots.get(side="left").source_manifest["context"],
        )
    else:
        current = ADAPTERS[str(spec["adapter"])](
            locked.organization, locked.project, locked.cutoff_at
        )
    observed_sides = []
    for side in (current.left, current.right):
        observed_sides.append(
            {
                "authority": side.authority,
                "model": side.model,
                "readiness": side.readiness,
                "value": side.value,
                "manifest": side.manifest,
                "cutoff": locked.cutoff_at.isoformat(),
            }
        )
    observed_hash = _hash(observed_sides)
    retained = locked.side_snapshots.count() == 2
    outcome = (
        ReconciliationRebuildCheck.Outcome.UNVERIFIABLE
        if not retained
        else ReconciliationRebuildCheck.Outcome.MATCHED
        if observed_hash == locked.source_watermark
        else ReconciliationRebuildCheck.Outcome.MISMATCHED
    )
    check = ReconciliationRebuildCheck.objects.create(
        organization=locked.organization,
        original_run=locked,
        kind=ReconciliationRebuildCheck.Kind.EXACT_REPLAY,
        outcome=outcome,
        original_hash=locked.source_watermark,
        observed_hash=observed_hash if retained else "",
        details={
            "original_tie_out_hash": locked.tie_out.calculation_hash,
            "historical_run_unchanged": True,
        },
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        executed_by=actor,
    )
    record_audit_event(
        action=AuditAction.REPORTING_RECONCILIATION_REBUILD,
        entity_type="reporting.ReconciliationRebuildCheck",
        entity_id=str(check.pk),
        organization=locked.organization,
        actor=actor,
        metadata={"outcome": outcome, "run_id": str(locked.pk)},
    )
    return check


@transaction.atomic
def review_rebuild_check(
    *, check: ReconciliationRebuildCheck, reviewer: User, reason: str
) -> ReconciliationRebuildCheck:
    locked = (
        ReconciliationRebuildCheck.objects.select_for_update()
        .select_related("original_run__project", "organization")
        .get(pk=check.pk)
    )
    _guard_context(locked.original_run, reviewer, review=True)
    require_business_permission(
        user=reviewer,
        organization=locked.organization,
        permission=BusinessPermissionCode.REPORTING_RECONCILIATION_REBUILD_REVIEW,
        message="اجازه بررسی بازسازی را ندارید.",
        project=locked.original_run.project,
    )
    if locked.executed_by_id == reviewer.pk:
        raise PermissionDenied("اجراکننده نمی‌تواند بازسازی خود را بررسی کند.")
    if locked.reviewed_by_id:
        if (
            locked.reviewed_by_id != reviewer.pk
            or locked.review_reason != reason.strip()
        ):
            raise ValidationError("بازسازی قبلاً با شاهد متفاوت بررسی شده است.")
        return locked
    ReconciliationRebuildCheck.objects.filter(pk=locked.pk).update(
        reviewed_by=reviewer, review_reason=reason.strip()
    )
    locked.refresh_from_db()
    return locked


def _guard_context(run, actor, **kwargs):
    from apps.timekeeping.reconciliation import guard_run

    guard_run(run, actor, **kwargs)


def reconciliation_runs(*, organization: Organization, actor: User):
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.REPORTING_RECONCILIATION_RUN_VIEW,
        message="اجازه مشاهده تطبیق را ندارید.",
    )
    runs = (
        ReconciliationRun.objects.filter(organization=organization)
        .select_related("pair_version__definition", "project", "tie_out", "review")
        .prefetch_related("exceptions__events", "side_snapshots")
        .order_by("-created_at")
    )
    excluded = []
    for run in runs.filter(pair_version__definition__code="attendance_timesheet"):
        try:
            _guard_context(run, actor)
        except (PermissionDenied, ValidationError):
            excluded.append(run.pk)
    return runs.exclude(pk__in=excluded)


def reconciliation_drillthrough(
    *, organization: Organization, actor: User, run_id: str
) -> ReconciliationRun:
    run = (
        ReconciliationRun.objects.filter(organization=organization, pk=run_id)
        .select_related("pair_version__definition", "project", "tie_out")
        .prefetch_related(
            "side_snapshots", "exceptions__events", "exceptions__evidence_links"
        )
        .first()
    )
    if run is None:
        raise PermissionDenied("اجرای تطبیق در دسترس نیست.")
    _guard_context(run, actor)
    for permission in (
        BusinessPermissionCode.REPORTING_RECONCILIATION_RUN_VIEW,
        BusinessPermissionCode.REPORTING_SOURCE_DRILLTHROUGH_VIEW,
    ):
        require_business_permission(
            user=actor,
            organization=organization,
            permission=permission,
            message="اجازه مشاهده مسیر منبع تطبیق را ندارید.",
            project=run.project,
        )
    _require_pair_sources(
        actor=actor,
        organization=organization,
        project=run.project,
        spec=run.pair_version.specification,
    )
    return run
