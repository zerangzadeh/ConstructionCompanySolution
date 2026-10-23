"""Record bounded Task 4 conclusions, then check unchanged Task 5 authority."""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from blocker_closure import OUT, digest, write

task4 = json.loads((OUT / "TASK4_GOVERNED_INPUT_DISCOVERY.json").read_text())
local_sources = [
    "docs/architecture/P9_S12_S15_PARTNER_QUALIFICATION_AND_PERFORMANCE_DECISION_PACKET.md",
    "docs/architecture/P8_S24_S27_EQUIPMENT_COST_AND_FIXED_ASSETS_DECISION_PACKET.md",
    "docs/architecture/P9_S06_S11_HSE_QA_CAPA_DECISION_PACKET.md",
]
task4["local_authority"] = {p: digest(ROOT / p) for p in local_sources}
task4["recovery"] = {
    "package": "BONIRA_REQUIRED_SPECIFICATION_COMPLETION_CONSOLIDATED_LATEST.zip",
    "member": "BONIRA_HSE_QA_V1_SCOPE_SPECIFICATION.md",
    "member_sha256": "37d5232351ff13b2d29a5c1dd87fdf9a7790511e3285e2d44f7bf80f544330f4",
    "conclusion": "Approved capability/lifecycle scope explicitly does not supply checklist content, regulatory form, risk/severity, acceptance thresholds or taxonomy. Missing policy must not be invented.",
}
task4["other_tenant_template"] = {"organization": "demo-construction-04", "template": "P10-S20-CAL", "source": "P10-S20 calibration v1", "conclusion": "Calibration-only template in another tenant is not approved domain-owner inspection content for this tenant; neither copied nor promoted to business authority."}
task4["conclusion"] = "BLOCKED: accepted architecture defines source-backed mechanics; no approved applicable qualification criteria/partner facts, asset class/book/capitalization facts, or inspection checklist/outcome rules recovered. Illustrative tests are not policy. No domain fixtures created."
task4["minimum_actions"] = {
    "CEP079-PREP-B06": {"cases": ["UAT-CASE-029", "UAT-CASE-044"], "owner": "Partner Qualification domain owner", "required": "Approved versioned qualification/category applicability requirement, source_reference/source_version and partner evidence/facts for the applicable BusinessParty; then canonical isolated profile/qualification fixture."},
    "CEP079-PREP-B07": {"cases": ["UAT-CASE-043"], "owner": "Fixed Assets/Accounting policy owner", "required": "Approved effective asset class, book/monetary policy, capitalization source/reference and required candidate facts; non-posting candidate only. No invented threshold, useful life, treatment or recognition."},
    "CEP079-PREP-B08": {"cases": ["UAT-CASE-044"], "owner": "Compliance HSE/QA domain owner", "required": "Approved applicable inspection template/checklist, outcome rules, required evidence and source/version references; then isolated native inspection inputs."},
}
write("TASK4_GOVERNED_INPUT_DISCOVERY.json", task4)
tasks = json.loads((OUT / "BLOCKER_CLOSURE_TASKS.json").read_text())
tasks["task4"] = {"result": "BLOCKED", "evidence": "TASK4_GOVERNED_INPUT_DISCOVERY.json", "minimum_actions": task4["minimum_actions"], "fixtures_created": 0}
write("BLOCKER_CLOSURE_TASKS.json", tasks)

# Task 5 starts only after the Task 4 result is retained.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.db import connection, transaction
from apps.organizations.models import Organization, PlatformPolicyVersion
from apps.contracts.models import ContractTermVersion
from apps.billing.models import TenantBillingConfiguration, ProgressClaim

previous = json.loads((OUT / "BILLING_SOURCE_RECOVERY.json").read_text())
archive_checks = []
for source in previous["approved_recovery_archives"]:
    archive = Path(source["archive"])
    archive_checks.append({"archive": archive.name, "sha256": digest(archive), "matches_retained": digest(archive) == source["sha256"]})
assert all(item["matches_retained"] for item in archive_checks)
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
    org = Organization.objects.get(slug="demo-construction-01", status="active")
    db = {"regulatory_policy_versions_all_statuses_all_tenants": PlatformPolicyVersion.objects.filter(policy__code="receivable-claim-regulatory").count(),
          "contract_term_versions_all_tenants": ContractTermVersion.objects.count(),
          "target_contract_term_versions": ContractTermVersion.objects.filter(organization=org).count(),
          "target_billing_configurations": TenantBillingConfiguration.objects.filter(organization=org).count(),
          "target_progress_claims": ProgressClaim.objects.filter(organization=org).count()}
requirements = []
for item in previous["missing_obligations"]:
    requirements.append({"missing_parameter_or_source": item["field"], "required_authority_provenance": item["authority"],
                         "affected_uat_cases": ["UAT-CASE-009", "UAT-CASE-016 (AR branch)", "UAT-CASE-023"],
                         "minimum_decision_evidence": item["missing"]})
write("BILLING_AUTHORITY_DECISION_REQUIREMENT.json", requirements)
write("TASK5_AUTHORITY_DELTA.json", {"date": "2026-10-24", "result": "BLOCKED_NO_APPROVED_EFFECTIVE_INPUTS_RECOVERED", "retained_sources": ["BILLING_SOURCE_RECOVERY.json", "BILLING_BROAD_RECOVERY_INDEX.json", "SOURCE_PRODUCER_REGISTRY.json"], "approved_recovery_archive_hash_checks": archive_checks, "database": db, "stop_search": "Prior bounded recovery of all 15 approved archives retained; byte identities unchanged. No repeated absence search or new statutory/legal interpretation.", "decision_requirement": "BILLING_AUTHORITY_DECISION_REQUIREMENT.json", "mutations": "NONE"})
tasks["task5"] = {"result": "BLOCKED", "blocker": "CEP079-PREP-B03", "cases": ["UAT-CASE-009", "UAT-CASE-016 (AR branch)", "UAT-CASE-023"], "evidence": ["TASK5_AUTHORITY_DELTA.json", "BILLING_AUTHORITY_DECISION_REQUIREMENT.json"], "minimum_action": "Human/Product-Regulatory authority supplies approved effective four parameters/bases with external provenance and accepted professional review, applicable approved contract terms and Billing configuration; canonical disposable claim/AR/settlement fixture preparation follows."}
write("BLOCKER_CLOSURE_TASKS.json", tasks)
print(json.dumps({"task4": "BLOCKED_B06_B07_B08", "task5": "BLOCKED_B03", "unchanged_recovery_archives": len(archive_checks), "billing_database": db}))
