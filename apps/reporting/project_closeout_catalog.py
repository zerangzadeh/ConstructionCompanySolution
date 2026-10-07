from __future__ import annotations

from typing import Final

from apps.organizations.models import BusinessPermissionCode as P

PROJECT_CLOSEOUT_GOVERNANCE_REFERENCE: Final = (
    "P10-C01–P10-C36=A; Product Owner authorization 2026-10-07"
)

# Each entry names only an authoritative read surface. No adapter calls a source
# transition service or treats absence as zero/completion.
PROJECT_CLOSEOUT_FAMILIES: Final[dict[str, dict[str, object]]] = {
    "project_identity": {
        "persian_name": "هویت و دامنه پروژه",
        "authority": "Projects and Project Controls",
        "models": (("projects.Project", "self", ()),),
        "permissions": (P.PROJECTS_VIEW.value,),
        "sensitivity": "normal",
    },
    "contract_commercial": {
        "persian_name": "قراردادها و تعهدات تجاری",
        "authority": "Contracts",
        "models": (
            ("contracts.Contract", "project", ("completed", "terminated")),
            (
                "contracts.ContractualRecord",
                "project",
                ("approved", "withdrawn", "superseded", "cancelled"),
            ),
        ),
        "permissions": (P.CONTRACTS_VIEW.value,),
        "sensitivity": "commercial",
    },
    "billing_claims_settlement": {
        "persian_name": "صورت‌وضعیت، گواهی و تسویه",
        "authority": "Billing, AP/AR, Treasury and Accounting",
        "models": (
            (
                "billing.ProgressClaim",
                "project",
                ("approved", "superseded", "cancelled"),
            ),
            (
                "billing.PayableCertificate",
                "project",
                ("approved", "superseded", "cancelled"),
            ),
        ),
        "permissions": (
            P.CLAIMS_VIEW.value,
            P.PAYABLE_CERTIFICATES_VIEW.value,
        ),
        "sensitivity": "commercial_financial",
    },
    "reconciliation_performance": {
        "persian_name": "تطبیق‌ها و عملکرد",
        "authority": "Reporting/Reconciliation and native source domains",
        "models": (
            ("reporting.MetricResult", "project", ()),
            ("reporting.ReconciliationRun", "project", ("completed",)),
        ),
        "permissions": (
            P.REPORTING_METRIC_RESULT_VIEW.value,
            P.REPORTING_RECONCILIATION_RUN_VIEW.value,
        ),
        "sensitivity": "financial_control",
    },
    "document_completeness": {
        "persian_name": "کامل‌بودن شواهد و اسناد",
        "authority": "DMS and each source domain",
        "models": (("projects.ProjectDocumentLink", "project", ()),),
        "permissions": (P.DOCUMENTS_VIEW.value,),
        "sensitivity": "document_control",
        "empty_outcome": "incomplete",
    },
    "inventory_disposition": {
        "persian_name": "موجودی و تعیین تکلیف مصالح",
        "authority": "Inventory",
        "models": (
            ("inventory.StockTransaction", "project", ("posted", "reversed")),
        ),
        "permissions": (
            P.INVENTORY_RECONCILIATIONS_VIEW.value,
            P.INVENTORY_VALUATION_VIEW.value,
        ),
        "sensitivity": "inventory_control",
    },
    "equipment_fixed_assets": {
        "persian_name": "تجهیزات و دارایی‌های ثابت",
        "authority": "Equipment and Fixed Assets",
        "models": (
            (
                "equipment.EquipmentAssignment",
                "project",
                ("completed", "cancelled"),
            ),
            (
                "fixed_assets.FixedAsset",
                "project",
                ("disposed", "retired", "rejected"),
            ),
        ),
        "permissions": (P.EQUIPMENT_VIEW.value, P.FIXED_ASSETS_VIEW.value),
        "sensitivity": "asset_control",
    },
    "field_hse_qa": {
        "persian_name": "مسائل میدانی، HSE و QA/QC",
        "authority": "Field Operations, HSE and Quality",
        "models": (
            (
                "daily_reports.FieldObservation",
                "project",
                ("accepted", "rejected", "superseded"),
            ),
            (
                "compliance.Inspection",
                "project",
                ("passed", "failed", "cancelled", "superseded"),
            ),
            ("compliance.CapaAction", "project", ("closed", "cancelled")),
        ),
        "permissions": (
            P.FIELD_OBSERVATIONS_VIEW.value,
            P.COMPLIANCE_VIEW.value,
        ),
        "sensitivity": "hse_qa",
    },
    "knowledge_lessons": {
        "persian_name": "دانش و درس‌آموخته‌های بازبینی‌شده",
        "authority": "Knowledge",
        "models": (
            (
                "knowledge.KnowledgeSourcePin",
                "source_id",
                (),
            ),
        ),
        "permissions": (P.KNOWLEDGE_PUBLICATIONS_VIEW.value,),
        "sensitivity": "knowledge_provenance",
        "empty_outcome": "gated_unavailable",
    },
}

PROJECT_CLOSEOUT_PROFILE_CODE: Final = "project_closeout_v1"
