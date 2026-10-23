"""Append only evidence-gated BATCH-08 closure to the four finding blocks."""

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))


assert read("HTTP_SUMMARY.json")["all_pass"]
assert len(read("RUNTIME_HTTP.json")) == 88
assert len(read("RUNTIME_BROWSER.json")) == 14
assert read("RUNTIME_INTEGRITY.json")["authority_unchanged"]
assert not read("RUNTIME_INTEGRITY.json")["preexisting_business_rows_changed"]
assert not read("REGRESSION_ATTRIBUTION.json")["new_failures"]
assert read("SERVER_CLEANUP.json")["stopped"]
register = ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
content = register.read_bytes()
assert content == (OUT / "register_entry.txt").read_bytes()
newline = "\r\n" if b"\r\n" in content else "\n"
seams = {"113": "PurchaseRequestForm/purchase_request_create", "116": "ContractForm/contract_create", "117": "WarehouseForm/warehouse_create", "125": "TrainingRequirementForm/workforce_training_requirement_create"}
browser = {"113": "Required Project GET, forced C query, duplicate server POST, organization and site-only GET; additional client-only date rejection", "116": "Independent limited Contract GET; complete own HTTP matrix", "117": "Optional Project GET, duplicate and blank-central denial server POSTs, organization and site-only GET", "125": "Independent Training Requirement GET and authorized B stricter-service denial POST"}
for finding, seam in seams.items():
    pattern = rb"- finding_id: UIUX-F-" + finding.encode() + rb"\r?\n.*?(?=- finding_id: UIUX-F-|\Z)"
    original = re.search(pattern, content, re.S).group()
    block = original.decode("utf-8")
    block = block.replace("finding_status: OPEN", "finding_status: RESOLVED", 1).replace("status: STATIC_CONFIRMED", "status: RUNTIME_VERIFIED_RESOLVED", 1).replace("runtime_status: NOT_EXECUTED", "runtime_status: RUNTIME_VERIFIED_RESOLVED", 1).replace("runtime_classification: NOT_TESTED", "runtime_classification: PASS_REQUIRED_CONTROLS", 1)
    lines = [
        "  batch_08_remediation:",
        "    date: 2026-10-22",
        "    report: UIUX_F111_BATCH_08_REMEDIATION_REPORT.md",
        "    evidence: f111_batch_08_evidence/",
        "    historical_status: STATIC_CONFIRMED",
        "    implementation_status: REMEDIATION_IMPLEMENTED",
        "    source_boundary: " + seam + "; existing scope_queryset, project_lookup pk, include_site_parent false",
        "    focused_validation: 86 tests and 106 subtests PASS across all four independent matrices",
        "    regression: 83 tests and 129 subtests PASS; 22 exact dirty-entry failures; zero new failures",
        "    checks: Django, Ruff, migration currency/drift, source boundary, YAML, links and whitespace PASS",
        "    migration: NO",
        "    runtime_http: 22 own authenticated real-CSRF observations PASS; eight own direct-service denials PASS",
        "    runtime_browser: " + browser[finding],
        "    runtime_authorized_sources: PASS_PROJECT_A_B_AND_ORGANIZATION_A_THROUGH_D",
        "    runtime_same_tenant_cross_tenant_exclusion: PASS_C_D_X_PROJECT_UUIDS_AND_DISTINGUISHABLE_LABELS",
        "    runtime_site_only_negative: PASS_EMPTY_PROJECT_OPTIONS_NO_PARENT_PROMOTION",
        "    runtime_manipulated_post: PASS_FORCED_C_D_X_AND_SITE_ONLY_A_B_C_D_X_SAFE_REJECTION",
        "    runtime_invalid_redisplay: PASS_SCOPED_CHOICES_RETAINED_NO_FORBIDDEN_METADATA",
        "    runtime_preparation: Existing qualifying actors, Projects and masters reused; no persistent fixture or authority mutation",
        "    runtime_authority: UNCHANGED; temporary grants NONE; no revocation required",
        "    runtime_integrity: PASS_519_TABLES_ZERO_BUSINESS_OR_SUCCESS_AUDIT_DELTA_TRAINING_REQUIREMENTS_ZERO",
        "    disposition: Finding RESOLVED; historical evidence, other findings and BATCH-01..07 preserved; BATCH-09 unchanged",
        "    decision: BATCH_08_RUNTIME_VERIFIED_RESOLVED",
    ]
    if finding == "117":
        lines.insert(-2, "    domain_control: Optional blank central warehouse retained; limited service denial and organization success preserved")
    if finding == "125":
        lines.insert(-2, "    domain_control: Existing organization-level training service gate and downstream tenant validation retained; SP-031 unchanged")
    block += newline.join(lines) + newline
    content = content.replace(original, block.encode("utf-8"), 1)
import yaml

parsed = yaml.safe_load(content)
assert parsed
register.write_bytes(content)
(OUT / "YAML_VALIDATION.json").write_text(json.dumps({"passed": True, "parser": "PyYAML", "version": yaml.__version__, "scope": "Four BATCH-08 blocks only; historical evidence and all other bytes retained"}, indent=2) + "\n", encoding="utf-8")
print("Four BATCH-08 findings closed; YAML parse PASS")
