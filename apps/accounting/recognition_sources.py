"""Typed, non-executable source vocabulary for SPEC-002 L2 drafts only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P

FAMILIES = {
    "inventory": (
        "Inventory",
        "Eligible posted inventory financial-effect event",
        "Inventory asset/COGS/consumption recognition",
        "Inventory",
        P.INVENTORY_VALUATION_VIEW,
    ),
    "payroll": (
        "Payroll",
        "Finalized payroll expense/liability occurrence",
        "Payroll expense/liability recognition",
        "Payroll",
        P.PAYROLL_RESULTS_VIEW,
    ),
    "asset": (
        "Fixed Assets",
        "Capitalization / depreciation / disposal occurrence",
        "Fixed asset/depreciation recognition",
        "Fixed Assets",
        P.FIXED_ASSETS_VIEW,
    ),
    "depreciation": (
        "Fixed Assets",
        "Capitalization / depreciation / disposal occurrence",
        "Fixed asset/depreciation recognition",
        "Fixed Assets",
        P.FIXED_ASSETS_VIEW,
    ),
    "expense": (
        "Direct Expense",
        "Approved explicitly classified direct-expense occurrence",
        "Direct expense recognition",
        "Expenses",
        P.EXPENSES_VIEW,
    ),
}
SOURCE_MODELS = {
    "inventory": "inventory.InventoryValuationEvent",
    "payroll": "payroll.PayrollRun",
    "asset": "fixed_assets.AssetTransaction",
    "depreciation": "fixed_assets.DepreciationRun",
    "expense": "expenses.Expense",
}
MAPPING_EVENTS = {
    "Inventory": {
        "receipt",
        "issue",
        "return",
        "transfer",
        "count_adjustment:adjustment_in",
        "count_adjustment:adjustment_out",
    },
    "Payroll": {"finalized"},
    "Fixed Assets": {"capitalization", "disposal", "depreciation"},
    "Direct Expense": {"approved"},
}
DRAFT_SOURCE_KINDS = frozenset(f"recognition.{kind}" for kind in SOURCE_MODELS)
DRAFT_EVENT = "recognition_draft"
DRAFT_REVERSAL_EVENT = "recognition_reversal_draft"


def digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def validate_mapping_assignments(mapping) -> None:
    """Validate supplied accounts; never select accounts or infer treatment."""
    if mapping.source_event not in MAPPING_EVENTS.get(mapping.source_family, set()):
        raise ValidationError("رخداد نگاشت خارج از ماتریس مصوب است.")
    assignments = mapping.account_assignments
    if not isinstance(assignments, dict) or not assignments:
        raise ValidationError("نگاشت صریح حساب‌ها الزامی است.")
    ids = set()
    for key, pair in assignments.items():
        if (
            not isinstance(key, str)
            or not isinstance(pair, dict)
            or set(pair) != {"debit", "credit"}
        ):
            raise ValidationError("فقط کلید منبع و زوج حساب صریح مجاز است.")
        prefix = "component:" if mapping.source_family == "Payroll" else "class:"
        if mapping.source_family == "Payroll" or mapping.source_event == "depreciation":
            try:
                UUID(key.removeprefix(prefix))
            except (ValueError, AttributeError) as exc:
                raise ValidationError("کلید جزء منبع معتبر نیست.") from exc
            if not key.startswith(prefix):
                raise ValidationError("کلید جزء منبع معتبر نیست.")
        elif key != "amount":
            raise ValidationError("کلید مبلغ منبع معتبر نیست.")
        if pair["debit"] == pair["credit"]:
            raise ValidationError("حساب‌های زوج نگاشت باید متمایز باشند.")
        try:
            ids.update(UUID(value) for value in pair.values())
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationError("شناسه حساب معتبر نیست.") from exc
    accounts = apps.get_model("accounting.Account").objects.filter(
        pk__in=ids,
        organization_id=mapping.organization_id,
        is_posting=True,
        archived_at__isnull=True,
    )
    if accounts.count() != len(ids):
        raise ValidationError("همه حساب‌ها باید برگ فعال همان Tenant باشند.")
    mapping.account_assignments = {
        key: {side: str(UUID(value)) for side, value in pair.items()}
        for key, pair in assignments.items()
    }
    # Component/class IDs must themselves belong to this tenant.
    if mapping.source_family == "Payroll" or mapping.source_event == "depreciation":
        label = (
            "payroll.PayrollComponent"
            if mapping.source_family == "Payroll"
            else "fixed_assets.FixedAssetClassVersion"
        )
        source_ids = [UUID(key.split(":", 1)[1]) for key in assignments]
        if apps.get_model(label).objects.filter(
            organization_id=mapping.organization_id, pk__in=source_ids
        ).count() != len(source_ids):
            raise ValidationError("جزء نگاشت متعلق به Tenant نیست.")


@dataclass(frozen=True)
class SourceEvidence:
    kind: str
    identity: UUID
    event: str
    version: str
    occurred_on: date
    currency: str
    rows: tuple[dict, ...]
    metadata: dict
    previous_id: UUID | None = None
    reversal: bool = False

    def snapshot(self) -> dict:
        return json.loads(json.dumps(self.__dict__, default=str))


def _row(
    source,
    key,
    amount,
    *,
    project=None,
    site=None,
    wbs_node=None,
    party=None,
    **context,
):
    return {
        "source_line_uuid": str(source.pk),
        "key": key,
        "amount": str(amount),
        "project_id": str(project.pk) if project else None,
        "site_id": str(site.pk) if site else None,
        "wbs_node_id": str(wbs_node.pk) if wbs_node else None,
        "party_id": str(party.pk) if party else None,
        "context": context,
    }


def read_source(
    *,
    organization,
    actor,
    kind: str,
    identity: UUID,
    permission: str,
    historical_event: str | None = None,
) -> SourceEvidence:
    if kind not in SOURCE_MODELS:
        raise ValidationError("خانواده منبع شناسایی مصوب نیست.")
    model = apps.get_model(SOURCE_MODELS[kind])
    try:
        source = model.objects.select_for_update(of=("self",)).get(
            pk=identity, organization=organization
        )
    except model.DoesNotExist as exc:
        raise PermissionDenied("منبع در محدوده مجاز وجود ندارد.") from exc

    def scope(project=None, site=None):
        for code in (FAMILIES[kind][4], permission):
            require_business_permission(
                user=actor,
                organization=organization,
                permission=code,
                project=project,
                site=site,
                message="اختیار و محدوده منبع شناسایی لازم است.",
            )

    rows = []
    previous = None
    reversal = False
    if kind == "inventory":
        stock = source.stock_transaction
        scope(stock.project)
        if (
            source.status not in {"finalized", "reversed"}
            or stock.status not in {"posted", "reversed"}
            or not source.finalized_at
            or not source.source_version
        ):
            raise ValidationError("ارزش‌گذاری نهایی و نسخه‌دار لازم است.")
        event, version, occurred_on, currency = (
            source.event_type,
            source.source_version,
            timezone.localtime(
                stock.occurred_at, ZoneInfo(organization.settings.timezone)
            ).date(),
            source.currency,
        )
        if event == "count_adjustment":
            event = f"count_adjustment:{stock.transaction_type}"
        previous, reversal = source.reversal_of_id, bool(source.reversal_of_id)
        rows.append(_row(source, "amount", source.value_amount, project=stock.project))
        metadata = {
            "stock_id": str(stock.pk),
            "stock_type": stock.transaction_type,
            "valuation_id": str(source.pk),
            "precision_version_id": str(source.monetary_precision_version_id),
            "rounding_version_id": str(source.rounding_policy_version_id),
            "source_reference": source.source_reference,
            "finalized_at": source.finalized_at.isoformat(),
            "quantity": str(source.quantity),
            "unit_cost": str(source.unit_cost),
        }
    elif kind == "payroll":
        scope()
        if (
            source.status not in {"finalized", "reversed"}
            or not source.finalized_at
            or not source.calculation_digest
        ):
            raise ValidationError("حقوق قطعی با نسخه محاسبه لازم است.")
        event, version, occurred_on, currency = (
            "finalized",
            source.calculation_digest,
            source.period.ends_on,
            source.currency,
        )
        previous = source.reversal_of_id or source.replaces_id or source.predecessor_id
        reversal = bool(source.reversal_of_id)
        results = list(
            source.employee_results.select_for_update(of=("self",))
            .select_related("project", "site")
            .order_by("pk")
        )
        if not results or any(
            result.status not in {"finalized", "reversed"} for result in results
        ):
            raise ValidationError("نتایج قطعی حقوق لازم است.")
        for result in results:
            scope(result.project, result.site)
            component_totals = {
                key: Decimal(0)
                for key in (
                    "earning",
                    "allowance",
                    "deduction",
                    "reimbursement",
                    "employer",
                    "informational",
                )
            }
            for line in (
                result.lines.select_for_update(of=("self",))
                .select_related("component")
                .order_by("pk")
            ):
                if line.component_kind not in component_totals:
                    raise ValidationError("نوع جزء حقوق خارج از قرارداد منبع است.")
                component_totals[line.component_kind] += line.amount
                if line.component_kind == "informational":
                    continue
                rows.append(
                    _row(
                        line,
                        f"component:{line.component_id}",
                        line.amount,
                        project=result.project,
                        site=result.site,
                        component_id=str(line.component_id),
                        employee_id=str(result.employee_id),
                        result_id=str(result.pk),
                        rule_version=str(line.rule_version),
                    )
                )
            expected_totals = (
                result.gross_amount,
                result.deduction_amount,
                result.reimbursement_amount,
                result.employer_amount,
                result.informational_amount,
            )
            actual_totals = (
                component_totals["earning"] + component_totals["allowance"],
                component_totals["deduction"],
                component_totals["reimbursement"],
                component_totals["employer"],
                component_totals["informational"],
            )
            if actual_totals != expected_totals:
                raise ValidationError("جمع اجزای حقوق با شواهد قطعی منبع سازگار نیست.")
        metadata = {
            "run_kind": source.kind,
            "run_id": str(source.pk),
            "calculation_digest": source.calculation_digest,
            "period_id": str(source.period_id),
            "precision_version_id": str(source.precision_policy_version_id),
            "rounding_version_id": str(source.rounding_policy_version_id),
            "monetary_policy_snapshot": source.monetary_policy_snapshot,
            "finalized_at": source.finalized_at.isoformat(),
            "totals": [
                {
                    "result_id": str(r.pk),
                    "gross": str(r.gross_amount),
                    "deduction": str(r.deduction_amount),
                    "employer": str(r.employer_amount),
                    "net": str(r.net_amount),
                }
                for r in results
            ],
        }
    elif kind == "asset":
        asset = source.asset
        project = (
            source.source_project
            if source.source_dimensions_captured
            else asset.project
        )
        site = source.source_site if source.source_dimensions_captured else asset.site
        scope(project, site)
        if source.status not in {"finalized", "reversed"} or not source.finalized_at:
            raise ValidationError("تراکنش نهایی دفتر دارایی لازم است.")
        previous, reversal = source.reversal_of_id, bool(source.reversal_of_id)
        event = source.transaction_type
        version = f"class:{asset.asset_class.version};book:{asset.book_policy.version};source:{source.source.source_version if source.source_id else source.occurrence_key}"
        occurred_on, currency = source.occurred_on, source.currency_code
        rows.append(
            _row(
                source,
                "amount",
                source.amount,
                project=project,
                site=site,
                cost_center_id=str(
                    source.source_cost_center_id
                    if source.source_dimensions_captured
                    else asset.cost_center_id
                ),
            )
        )
        metadata = {
            "asset_id": str(asset.pk),
            "class_id": str(asset.asset_class_id),
            "class_version": asset.asset_class.version,
            "book_id": str(asset.book_policy_id),
            "book_version": asset.book_policy.version,
            "occurrence_key": source.occurrence_key,
            "finalized_at": source.finalized_at.isoformat(),
        }
    elif kind == "depreciation":
        scope()
        if source.status not in {"finalized", "reversed"} or not source.finalized_at:
            raise ValidationError("استهلاک نهایی دفتر دارایی لازم است.")
        previous, reversal = source.reversal_of_id, bool(source.reversal_of_id)
        event, version, occurred_on, currency = (
            "depreciation",
            f"book:{source.book_policy.version};watermark:{source.source_watermark.isoformat()}",
            source.fiscal_period.ends_on,
            "IRR",
        )
        for line in (
            source.lines.select_for_update(of=("self",))
            .select_related("asset__asset_class", "asset__project", "asset__site")
            .order_by("pk")
        ):
            scope(line.asset.project, line.asset.site)
            rows.append(
                _row(
                    line,
                    f"class:{line.asset.asset_class_id}",
                    line.depreciation_amount,
                    project=line.asset.project,
                    site=line.asset.site,
                    asset_id=str(line.asset_id),
                    class_version=line.asset.asset_class.version,
                    basis=str(line.basis_snapshot),
                    residual=str(line.residual_snapshot),
                    cost_center_id=str(line.asset.cost_center_id),
                )
            )
        metadata = {
            "run_id": str(source.pk),
            "book_id": str(source.book_policy_id),
            "book_version": source.book_policy.version,
            "period_id": str(source.fiscal_period_id),
            "source_watermark": source.source_watermark.isoformat(),
            "finalized_at": source.finalized_at.isoformat(),
        }
    else:
        scope(source.project)
        if (
            source.status not in {"approved", "void"}
            or not source.approved_at
            or not source.approved_by_id
            or source.classification != "direct"
        ):
            raise ValidationError("هزینه مستقیم مصوب و طبقه‌بندی‌شده لازم است.")
        event, version, occurred_on, currency = (
            "approved",
            str(source.source_version),
            source.incurred_on,
            organization.settings.currency,
        )
        previous, reversal = (
            source.replaces_id,
            source.status == "void" and historical_event != "approved",
        )
        if reversal:
            previous, event = source.pk, "void"
        allocation_objects = list(
            source.allocations.select_for_update(of=("self",))
            .select_related("project", "wbs_node")
            .order_by("pk")
        )
        allocations = [
            {
                "id": str(a.pk),
                "amount": a.amount,
                "wbs_node_id": str(a.wbs_node_id),
                "cbs_node_id": str(a.cbs_node_id),
                "cost_center_id": str(a.cost_center_id),
                "budget_id": str(a.governing_budget_id),
                "basis": a.allocation_basis_reference,
            }
            for a in allocation_objects
        ]
        if (
            not allocations
            or sum((r["amount"] for r in allocations), Decimal(0)) != source.amount
        ):
            raise ValidationError("تخصیص محفوظ و متوازن هزینه لازم است.")
        for allocation in allocation_objects:
            scope(allocation.project)
            rows.append(
                _row(
                    allocation,
                    "amount",
                    allocation.amount,
                    project=allocation.project,
                    wbs_node=allocation.wbs_node,
                    party=source.party,
                    cost_center_id=str(allocation.cost_center_id),
                    cbs_node_id=str(allocation.cbs_node_id),
                    budget_id=str(allocation.governing_budget_id),
                )
            )
        metadata = {
            "expense_id": str(source.pk),
            "fingerprint": source.source_fingerprint,
            "approved_at": source.approved_at.isoformat(),
            "approved_by_id": str(source.approved_by_id),
            "allocations": json.loads(json.dumps(allocations, default=str)),
            "reimbursement_employee_id": str(source.reimbursement_employee_id),
            "replaces_id": str(source.replaces_id),
        }
    if not rows or any(not Decimal(row["amount"]).is_finite() for row in rows):
        raise ValidationError("شواهد مبلغ منبع معتبر نیست.")
    return SourceEvidence(
        kind,
        source.pk,
        event,
        version,
        occurred_on,
        currency,
        tuple(rows),
        metadata,
        previous,
        reversal,
    )
