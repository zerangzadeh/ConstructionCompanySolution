import hashlib
import json

from django.db import migrations
from django.utils import timezone


PAIRS = (
    (
        "estimate_budget",
        "برآورد مصوب به بودجه پذیرفته‌شده",
        "Estimation",
        "Project Controls / Budget",
        "normal",
        "project/budget_version/currency",
        "money",
        ["estimates.view", "budgets.view"],
    ),
    (
        "commitment_projection",
        "تعهد منبع به تصویر هزینه پروژه",
        "Procurement or Contracts",
        "Project Controls",
        "normal",
        "project/source_contract/currency",
        "money",
        ["purchase_orders.view", "project_cost.view"],
    ),
    (
        "po_receipt_invoice",
        "سفارش، دریافت و صورتحساب تأمین‌کننده",
        "Procurement",
        "AP/Finance and Matching",
        "normal",
        "purchase_order_version/invoice_version/line",
        "quantity_and_money",
        ["purchase_orders.view", "supplier_invoices.view", "invoice_matches.view"],
    ),
    (
        "inventory_quantity_value",
        "مقدار و ارزش موجودی",
        "Inventory Custody",
        "Inventory Valuation",
        "normal",
        "warehouse/material/unit/currency/cutoff",
        "quantity_and_money",
        ["inventory_reconciliations.view", "inventory_valuation.view"],
    ),
    (
        "claim_settlement",
        "صورت‌وضعیت به تسویه",
        "Billing",
        "Treasury and AP/AR",
        "normal",
        "claim/currency",
        "money",
        ["claims.view", "claim_settlements.view", "treasury.view"],
    ),
    (
        "subledger_gl",
        "معین دریافتنی/پرداختنی به دفتر کل",
        "AP/AR",
        "Accounting / GL",
        "normal",
        "direction/as_of/control_account",
        "money",
        ["subledgers.view", "accounting.reports_view"],
    ),
    (
        "treasury_bank",
        "دفتر خزانه به صورت‌حساب بانک",
        "Treasury",
        "Treasury Bank Reconciliation",
        "normal",
        "bank_account/statement/as_of",
        "money",
        ["treasury.view", "treasury.bank_reconciliations_run"],
    ),
    (
        "treasury_gl",
        "خزانه به دفتر کل",
        "Treasury",
        "Accounting / GL",
        "normal",
        "cutoff/currency/source_identity",
        "money",
        ["treasury.view", "accounting.reports_view"],
    ),
    (
        "project_cost_sources",
        "منابع هزینه پروژه به تصویر هزینه",
        "Registered Source Domains",
        "Project Controls",
        "normal",
        "project/source_contract/source_event",
        "count_and_money",
        ["project_cost.view", "project_cost.reconciliations_view"],
    ),
    (
        "payroll_insurance",
        "حقوق نهایی به فهرست بیمه کارکنان",
        "Payroll",
        "Payroll Statutory",
        "restricted_personal_financial",
        "payroll_run/statutory_output/currency",
        "money",
        ["payroll_results.view", "payroll_statutory_audit.view"],
    ),
    (
        "payroll_financial_handoffs",
        "پیشنهادهای مالی حقوق به تأیید مصرف‌کننده",
        "Payroll",
        "Named Downstream Domain",
        "restricted_personal_financial",
        "proposal/family/currency",
        "money",
        [
            "payroll_handoff_reconciliation.prepare",
            "payroll_handoff_reconciliation.review",
        ],
    ),
    (
        "fixed_asset_handoffs",
        "دفتر دارایی ثابت به تأیید مصرف‌کننده",
        "Fixed Assets",
        "Accounting or Project Controls",
        "normal",
        "asset/source_envelope/consumer",
        "money",
        ["fixed_assets.view", "fixed_assets.handoff_reconcile"],
    ),
    (
        "contractor_compliance",
        "بیمه و مفاصاحساب پیمانکار به ارجاع مالی",
        "Contracts / Compliance",
        "Contract, AP or Accounting Consumer",
        "normal",
        "contract/assessment/policy_version/currency",
        "money",
        ["contractor_compliance.view", "contracts.view"],
    ),
)

GOVERNANCE = "P10-R01–P10-R36=A; Product Owner authorization 2026-10-07"
TOLERANCE_KINDS = {
    "po_receipt_invoice": "source_policy",
    "subledger_gl": "native_policy",
    "treasury_bank": "native_policy",
    "treasury_gl": "native_policy",
}
QUALITATIVE = {
    "estimate_budget": ["lineage", "mapping"],
    "commitment_projection": ["source_contract"],
    "po_receipt_invoice": ["duplicate", "version"],
    "inventory_quantity_value": ["custody", "missing_cost"],
    "claim_settlement": ["overallocated", "reversal"],
    "subledger_gl": ["posting_key", "mapping"],
    "treasury_bank": ["unmatched", "uncleared"],
    "treasury_gl": ["posting_key", "lineage"],
    "project_cost_sources": ["coverage", "lineage"],
    "payroll_insurance": ["authority", "schema", "employee"],
    "payroll_financial_handoffs": ["acknowledgement", "source_digest"],
    "fixed_asset_handoffs": ["consumer_reference", "source"],
    "contractor_compliance": ["clearance", "legal_activation"],
}


def forward(apps, schema_editor):
    del schema_editor
    definition_model = apps.get_model("reporting", "ReconciliationPairDefinition")
    version_model = apps.get_model("reporting", "ReconciliationPairVersion")
    now = timezone.now()
    for code, name, left, right, sensitivity, grain, measure, permissions in PAIRS:
        definition = definition_model.objects.create(
            code=code,
            persian_name=name,
            left_authority=left,
            right_authority=right,
            sensitivity=sensitivity,
            requires_independent_review=True,
            is_active=True,
        )
        specification = {
            "adapter": code,
            "grain": grain,
            "measure": measure,
            "source_permissions": permissions,
            "tolerance": {
                "kind": TOLERANCE_KINDS.get(code, "exact"),
                "absolute": "0",
            },
            "materiality": {
                "absolute": "0",
                "qualitative": QUALITATIVE[code],
            },
            "missing_input": "unknown_or_incomplete_never_zero",
            "rebuild": "immutable_replay_or_linked_successor",
            "downstream_effect": "none",
        }
        payload_hash = hashlib.sha256(
            json.dumps(
                specification,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        version_model.objects.create(
            definition=definition,
            version=1,
            status="published",
            specification=specification,
            source_owner_approvals={
                "left": left,
                "right": right,
                "reconciliation_owner": "Reporting/Reconciliation",
                "acceptance_owner": "Product Owner",
            },
            payload_hash=payload_hash,
            governance_reference=GOVERNANCE,
            published_at=now,
        )


def reverse(apps, schema_editor):
    del schema_editor
    codes = [item[0] for item in PAIRS]
    apps.get_model("reporting", "ReconciliationPairVersion").objects.filter(
        definition__code__in=codes
    ).delete()
    apps.get_model("reporting", "ReconciliationPairDefinition").objects.filter(
        code__in=codes
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("reporting", "0003_p10_s07_s13_reconciliation_controls")]
    operations = [migrations.RunPython(forward, reverse)]
