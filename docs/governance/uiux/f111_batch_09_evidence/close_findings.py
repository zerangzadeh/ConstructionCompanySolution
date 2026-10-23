"""Advance only the three BATCH-09 entries after every evidence gate passes."""

import json
import re
from pathlib import Path

import yaml

from verify import evidence_gates, source_boundary

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
source_boundary()
gates = evidence_gates()
register = ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
content = register.read_bytes()
assert content == (OUT / "register_entry.txt").read_bytes()
newline = "\r\n" if b"\r\n" in content else "\n"
seams = {
    "115": "MaintenanceRecordForm/maintenance_create",
    "126": "QualityIssueForm/issue_create",
    "127": "SafetyIncidentForm/incident_create",
}
for finding, seam in seams.items():
    original = re.search(rb"- finding_id: UIUX-F-" + finding.encode() + rb"\r?\n.*?(?=- finding_id: UIUX-F-|\Z)", content, re.S).group()
    block = original.decode("utf-8")
    block = block.replace("finding_status: OPEN", "finding_status: RESOLVED", 1).replace("status: STATIC_CONFIRMED", "status: RUNTIME_VERIFIED_RESOLVED", 1).replace("runtime_status: NOT_EXECUTED", "runtime_status: RUNTIME_VERIFIED_RESOLVED", 1).replace("runtime_classification: NOT_TESTED", "runtime_classification: PASS_REQUIRED_CONTROLS", 1)
    own = gates["http_by_finding"]["UIUX-F-" + finding]
    lines = [
        "  batch_09_remediation:",
        "    date: 2026-10-22",
        "    report: UIUX_F111_BATCH_09_REMEDIATION_REPORT.md",
        "    evidence: f111_batch_09_evidence/",
        "    historical_status: STATIC_CONFIRMED",
        "    implementation_status: REMEDIATION_IMPLEMENTED",
        "    source_boundary: " + seam + "; existing site-aware helpers and exact canonical local lookups",
        "    focused_validation: Independent Maintenance, Quality and Safety matrices PASS; see focused.xml and focused.txt",
        "    regression: Exact dirty-entry replay and current outcomes match; see REGRESSION_ATTRIBUTION.json",
        "    checks: Django, Ruff, migration currency/drift, source boundary, YAML, links and whitespace PASS",
        "    migration: NO",
        f"    runtime_http: {own} own authenticated real-CSRF observations PASS; eight own direct-service denials PASS",
        "    runtime_browser: " + ("Maintenance limited/site-only GET and mixed Project/Site server POST rejection" if finding == "115" else "Quality limited/site-only five-field GET and mixed Site/Phase server POST rejection" if finding == "126" else "Independent Safety limited/site-only five-field browser GET; complete own HTTP five-field and mixed-child negatives"),
        "    runtime_project_scope: PASS_A_B_AND_THEIR_CHILDREN_ONLY_ORGANIZATION_A_THROUGH_D",
        "    runtime_site_scope: PASS_PARENT_A_CONTEXT_EXACT_GRANTED_SITE_CHILDREN_NO_SIBLINGS_OR_PROJECT_ONLY_ACTIVITY",
        "    runtime_same_tenant_cross_tenant_exclusion: PASS_C_D_X_EACH_PROTECTED_FIELD",
        "    runtime_manipulated_mixed_post: PASS_FORCED_PROJECT_SITE_CHILD_IDS_AND_INCONSISTENT_AUTHORIZED_COMBINATIONS",
        "    runtime_invalid_redisplay: PASS_SCOPED_OPTIONS_AND_NO_FORBIDDEN_METADATA",
        "    runtime_preparation: Four minimum synthetic sibling objects through canonical services; existing actors, grants and other fixtures reused; audit retained",
        "    runtime_authority: UNCHANGED; temporary grants NONE; no revocation required",
        "    runtime_integrity: PASS_519_TABLES_SESSIONS_ONLY_ZERO_BUSINESS_OR_SUCCESS_AUDIT_RUNTIME_DELTA",
        "    preserved_domain_behavior: Existing optional fields, lifecycle predicates, domain relationships, permission gates and workflow semantics retained",
        "    disposition: Finding RESOLVED; historical evidence and BATCH-01..08 preserved; Wave C and SP-031 untouched",
        "    decision: BATCH_09_RUNTIME_VERIFIED_RESOLVED",
    ]
    block += newline.join(lines) + newline
    content = content.replace(original, block.encode("utf-8"), 1)
parsed = yaml.safe_load(content)
assert parsed
register.write_bytes(content)
(OUT / "YAML_VALIDATION.json").write_text(json.dumps({"passed": True, "parser": "PyYAML", "version": yaml.__version__, "scope": "Only F-115/F-126/F-127 entries; all other finding bytes and historical evidence retained"}, indent=2) + "\n", encoding="utf-8")
print("Three BATCH-09 findings closed; YAML parse PASS")
