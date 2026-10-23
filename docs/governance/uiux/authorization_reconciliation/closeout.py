"""Append the bounded authorization revalidation without rewriting prior history."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BASE = OUT.parent
sys.path.insert(0, str(Path(os.environ["TEMP"]) / "bonira-wave-c-tools"))
import yaml


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_cases(name):
    return {(c.attrib["classname"], c.attrib["name"]):
            c.find("failure") is None and c.find("error") is None
            for c in ET.parse(OUT / name).iter("testcase")}


assert all(test_cases("initial_grant_final.xml").values())
assert all(test_cases("opening_retest.xml").values())
merged = test_cases("final.xml")
merged.update(test_cases("initial_grant_final.xml"))
merged.update(test_cases("opening_retest.xml"))
remaining = ["::".join(key) for key, passed in merged.items() if not passed]
assert len(remaining) == 4 and all("registry" in key.lower() for key in remaining)
validation = {
    "initial_grant_and_matrix": "18/18 PASS on final service source",
    "protected_opening_retest": "9/9 PASS, including concurrency",
    "affected_selection": "114 tests: 105 initially PASS, 5 fixture failures corrected/retested PASS, 4 baseline registry failures; 68 subtests PASS",
    "remaining_failures": remaining,
    "baseline_attribution": "REGISTRY_BASELINE_DEBT.json",
    "http": read("HTTP_SUMMARY.json"),
    "concurrency": read("CONCURRENCY.json"),
    "integrity": read("INTEGRITY.json"),
    "django_check": "PASS", "migration_drift": "PASS_NO_CHANGES",
    "ruff_lint": "PASS", "new_module_format": "PASS",
    "full_repository_regression": "NOT_RUN",
}
entry = read("ENTRY.json")
allowed_existing_changes = {
    "apps/payroll/test_p7_s13_s22_core_payroll.py",
    "apps/workforce/test_cep022.py", "apps/procurement/views.py",
    "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_RESULTS.yaml",
    "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml",
    "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md",
}
unexpected = [name for name, digest in entry["preexisting_hashes"].items()
              if name not in allowed_existing_changes
              and (not (ROOT / name).is_file()
                   or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest)]
assert not unexpected, unexpected
assert hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest() == entry["index_sha256"]
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == entry["head"]
validation["unrelated_entry_files_byte_preserved"] = True
validation["git_index_and_head_unchanged"] = True
(OUT / "FINAL_VERIFICATION.json").write_text(json.dumps(validation, indent=2)+"\n", encoding="utf-8")

for name in ("UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "UIUX_FINDINGS_REGISTER.yaml",
             "UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md"):
    snapshot = OUT / "entry_reports" / name
    snapshot.parent.mkdir(exist_ok=True)
    assert not snapshot.exists(), "Do not overwrite closeout entry history"
    snapshot.write_bytes((BASE / name).read_bytes())

status = {
    "decision": "WAVE_C_BLOCKED",
    "recorded_on": "2026-10-22",
    "authority": "authorization_reconciliation/PRODUCT_DECISION.md",
    "scope": "Role reconciliation and affected authorization boundaries only",
    "matrix": "147 of 148 prior gaps mapped; one catalog-only reserved code explicitly unassigned",
    "owner_admin_permissions": "UNCHANGED_FROM_HEAD",
    "initial_grant": "SIX_SCENARIO_GRANTS_PLUS_ONE_CONCURRENCY_FIXTURE_AUDITED",
    "affected": {
        "RV-007": "First-grant blocker resolved; opening form/duties authorized. Issued RFQ closes 2026-10-24; no early close/opening or source/scan bypass.",
        "RV-029": "Employment manager and explicitly linked own-history actor authorized; HTTP 200 and denial/invalid/CSRF boundaries verified. No new employment history/source document manufactured; full populated scenario not rerun.",
        "RV-032": "Project-scoped invitation manager authorized; real CSRF POST creates one synthetic invitation, with no external tenant membership. External original-payload custody/hash contract remains unresolved.",
    },
    "unaffected_gates": ["RV-011 accounting effective monetary policies",
                         "RV-013 eligible source/Treasury approval and mapping policy",
                         "RV-018 statutory source/schema and payload selection contract",
                         "RV-030 approved Tender policy reference/activation"],
    "new_finding": "UIUX-F-132_RUNTIME_VERIFIED_RESOLVED",
    "validation": "authorization_reconciliation/FINAL_VERIFICATION.json",
    "full_wave_c_completion": False, "wave_closed": False,
    "prior_closed_findings_preserved": True,
    "production": "UNTOUCHED", "human_signoff": "NOT_EXECUTED",
    "cep_078_079": "NOT_EXECUTED", "git_writes": "NOT_EXECUTED",
    "report": "authorization_reconciliation/COMPLETION_REPORT.md",
}
results_path = BASE / "UIUX_RUNTIME_VALIDATION_RESULTS.yaml"
text = results_path.read_text(encoding="utf-8")
assert text.count("latest_wave_c_execution: wave_c_targeted_reentry") == 1
text = text.replace("latest_wave_c_execution: wave_c_targeted_reentry",
                    "latest_wave_c_execution: wave_c_role_reconciliation")
text += "\n" + yaml.safe_dump({"wave_c_role_reconciliation": status}, allow_unicode=True, sort_keys=False, width=110)
results_path.write_text(text, encoding="utf-8")

finding = {
    "finding_id": "UIUX-F-132", "module": "Procurement",
    "surface_id": "RV-032-SUPPLIER-PORTAL-INVITATION",
    "route": "/procurement/rfq-invitations/<uuid:invitation_id>/portal/",
    "category": "FUNCTIONAL_ACCESS", "severity": "HIGH",
    "status": "RUNTIME_VERIFIED_RESOLVED", "runtime_status": "RUNTIME_VERIFIED_RESOLVED",
    "problem": "Existing object permission call omits mandatory message, causing HTTP 500 for an authorized portal manager.",
    "evidence": {"diagnostic": "authorization_reconciliation/HTTP_DIAGNOSTIC.json",
                 "runtime": "authorization_reconciliation/HTTP.json",
                 "regression": "authorization_reconciliation/final.xml"},
    "remediation": "Localized denial message supplied. Tenant/project permission check unchanged; authorized GET/POST, unauthorized actor, other-project and CSRF denials verified.",
}
findings_path = BASE / "UIUX_FINDINGS_REGISTER.yaml"
text = findings_path.read_text(encoding="utf-8")
assert "finding_id: UIUX-F-132" not in text
text = text.replace("  finding_count: 131", "  finding_count: 132", 1)
text = text.replace("    HIGH: 82", "    HIGH: 83", 1)
assert text.count("\nruntime_wave_a:") == 1
text = text.replace("\nruntime_wave_a:", "\n" + yaml.safe_dump([finding], allow_unicode=True, sort_keys=False, width=110) + "\nruntime_wave_a:")
text = text.replace("latest_wave_c_execution: wave_c_targeted_reentry",
                    "latest_wave_c_execution: wave_c_role_reconciliation")
text += "\n" + yaml.safe_dump({"wave_c_role_reconciliation": status}, allow_unicode=True, sort_keys=False, width=110)
findings_path.write_text(text, encoding="utf-8")
assert len(yaml.safe_load(text)["findings"]) == 132

report = BASE / "UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md"
report.write_text(report.read_text(encoding="utf-8") + """

## Authorization reconciliation addendum — 2026-10-22

The Human Product Decision authorizes the bounded Platform Initial Grant and
Role-Permission Matrix correction. The former first-grant authority gaps for
RV-007, RV-029 and RV-032 are resolved through six audited scenario grants using
existing role/scope/audit records. Owner/Admin default permissions match HEAD
exactly. No new bootstrap subsystem, second Platform approver or tenant-business
bypass was introduced.

18 final Initial Grant/matrix tests and 9 protected-opening retests PASS. The
affected selection has 110 passing main tests after fixture retests and 68 passing
subtests, with four HEAD-attributed registry failures retained. Real runtime:
18 expected HTTP observations, including six POSTs; one concurrent grant and one
duplicate denial. All pre-existing rows remain; financial/Payroll/Inventory model
fingerprints are unchanged. No schema migration or domain reset occurred.

The newly reachable Portal management page exposed an existing missing required
permission-message argument. UIUX-F-132 is runtime-verified resolved by the bounded
call correction and regression. One real synthetic external invitation was
created; its plaintext token was not persisted and no external membership was
created. Existing own-history identity/source-document checks remain authoritative.

RFQ opening still requires the scheduled October 24 close and valid source/scan
evidence. Populated own Employment history was not rerun. Accounting, statutory,
Tender and external payload-custody gates remain as previously recorded. This
authorization revalidation does not close Wave C or CEP-078/079.

[Completion report](authorization_reconciliation/COMPLETION_REPORT.md),
[current matrix](authorization_reconciliation/ROLE_PERMISSION_MATRIX.csv),
[verification](authorization_reconciliation/FINAL_VERIFICATION.json).

**WAVE_C_BLOCKED. Production, Human Sign-off and Git writes: NOT_EXECUTED.**
""", encoding="utf-8")
print("Canonical affected Wave C results/findings updated; prior history retained")
