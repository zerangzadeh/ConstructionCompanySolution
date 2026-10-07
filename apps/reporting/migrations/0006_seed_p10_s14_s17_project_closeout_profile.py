import hashlib
import json

from django.db import migrations
from django.utils import timezone


FAMILIES = {
    "project_identity": {
        "persian_name": "هویت و دامنه پروژه",
        "authority": "Projects and Project Controls",
        "models": [["projects.Project", "self", []]],
        "permissions": ["projects.view"],
        "sensitivity": "normal",
        "empty_outcome": "unknown",
    },
    "contract_commercial": {
        "persian_name": "قراردادها و تعهدات تجاری",
        "authority": "Contracts",
        "models": [
            ["contracts.Contract", "project", ["completed", "terminated"]],
            [
                "contracts.ContractualRecord",
                "project",
                ["approved", "withdrawn", "superseded", "cancelled"],
            ],
        ],
        "permissions": ["contracts.view"],
        "sensitivity": "commercial",
        "empty_outcome": "unknown",
    },
    "billing_claims_settlement": {
        "persian_name": "صورت‌وضعیت، گواهی و تسویه",
        "authority": "Billing, AP/AR, Treasury and Accounting",
        "models": [
            [
                "billing.ProgressClaim",
                "project",
                ["approved", "superseded", "cancelled"],
            ],
            [
                "billing.PayableCertificate",
                "project",
                ["approved", "superseded", "cancelled"],
            ],
        ],
        "permissions": ["claims.view", "payable_certificates.view"],
        "sensitivity": "commercial_financial",
        "empty_outcome": "unknown",
    },
    "reconciliation_performance": {
        "persian_name": "تطبیق‌ها و عملکرد",
        "authority": "Reporting/Reconciliation and native source domains",
        "models": [
            ["reporting.MetricResult", "project", []],
            ["reporting.ReconciliationRun", "project", ["completed"]],
        ],
        "permissions": [
            "reporting.metric_result.view",
            "reporting.reconciliation_run.view",
        ],
        "sensitivity": "financial_control",
        "empty_outcome": "unknown",
    },
    "document_completeness": {
        "persian_name": "کامل‌بودن شواهد و اسناد",
        "authority": "DMS and each source domain",
        "models": [["projects.ProjectDocumentLink", "project", []]],
        "permissions": ["documents.view"],
        "sensitivity": "document_control",
        "empty_outcome": "incomplete",
    },
    "inventory_disposition": {
        "persian_name": "موجودی و تعیین تکلیف مصالح",
        "authority": "Inventory",
        "models": [
            ["inventory.StockTransaction", "project", ["posted", "reversed"]]
        ],
        "permissions": [
            "inventory_reconciliations.view",
            "inventory_valuation.view",
        ],
        "sensitivity": "inventory_control",
        "empty_outcome": "unknown",
    },
    "equipment_fixed_assets": {
        "persian_name": "تجهیزات و دارایی‌های ثابت",
        "authority": "Equipment and Fixed Assets",
        "models": [
            [
                "equipment.EquipmentAssignment",
                "project",
                ["completed", "cancelled"],
            ],
            [
                "fixed_assets.FixedAsset",
                "project",
                ["disposed", "retired", "rejected"],
            ],
        ],
        "permissions": ["equipment.view", "fixed_assets.view"],
        "sensitivity": "asset_control",
        "empty_outcome": "unknown",
    },
    "field_hse_qa": {
        "persian_name": "مسائل میدانی، HSE و QA/QC",
        "authority": "Field Operations, HSE and Quality",
        "models": [
            [
                "daily_reports.FieldObservation",
                "project",
                ["accepted", "rejected", "superseded"],
            ],
            [
                "compliance.Inspection",
                "project",
                ["passed", "failed", "cancelled", "superseded"],
            ],
            ["compliance.CapaAction", "project", ["closed", "cancelled"]],
        ],
        "permissions": ["field_observations.view", "compliance.view"],
        "sensitivity": "hse_qa",
        "empty_outcome": "unknown",
    },
    "knowledge_lessons": {
        "persian_name": "دانش و درس‌آموخته‌های بازبینی‌شده",
        "authority": "Knowledge",
        "models": [["knowledge.KnowledgeSourcePin", "source_id", []]],
        "permissions": ["knowledge.publications_view"],
        "sensitivity": "knowledge_provenance",
        "empty_outcome": "gated_unavailable",
    },
}

GOVERNANCE = "P10-C01–P10-C36=A; Product Owner authorization 2026-10-07"


def forward(apps, schema_editor):
    del schema_editor
    definition_model = apps.get_model("reporting", "ProjectCloseoutProfileDefinition")
    version_model = apps.get_model("reporting", "ProjectCloseoutProfileVersion")
    definition = definition_model.objects.create(
        code="project_closeout_v1",
        persian_name="کنترل هماهنگ اختتام پروژه",
        is_active=True,
    )
    specification = {
        "families": FAMILIES,
        "execution": "explicit_synchronous",
        "missing_input": "explicit_never_zero_or_complete",
        "correction": "immutable_successor",
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
            code: spec["authority"] for code, spec in FAMILIES.items()
        }
        | {
            "control_owner": "Reporting",
            "acceptance_owner": "Product Owner",
        },
        payload_hash=payload_hash,
        governance_reference=GOVERNANCE,
        published_at=timezone.now(),
    )


def reverse(apps, schema_editor):
    del schema_editor
    versions = apps.get_model("reporting", "ProjectCloseoutProfileVersion")
    definitions = apps.get_model("reporting", "ProjectCloseoutProfileDefinition")
    versions.objects.filter(definition__code="project_closeout_v1").delete()
    definitions.objects.filter(code="project_closeout_v1").delete()


class Migration(migrations.Migration):
    dependencies = [("reporting", "0005_projectcloseoutprofiledefinition_and_more")]
    operations = [migrations.RunPython(forward, reverse)]
