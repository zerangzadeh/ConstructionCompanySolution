"""Resume after the Human connects Edge; no product changes or browser-policy bypass."""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
sys.stdout.reconfigure(encoding="utf-8")
entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
identities = json.loads((OUT / "RUNNING_BROWSER_IDENTITIES.json").read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def section(text, name):
    return re.search(r"^" + name + r":\n(.*?)(?=^[A-Za-z_]+:|\Z)", text, re.M | re.S).group(1)


def blocks(text):
    return dict(re.findall(r"^  (CEP-\d{3}):\n(.*?)(?=^  CEP-|^authority_scope:)", text, re.M | re.S))


assert all(sha(ROOT / p) == v for p, v in entry["product_hashes"].items())
runtime = {}
for family, label, provider in (("chrome", "Chrome", "3"), ("msedge", "Edge", "4")):
    candidates = [r for r in identities["process_candidates"] if r["family"] == family]
    exe = {r.get("executable_product_version") for r in candidates}
    loaded = {m["product_version"] for r in candidates for m in r.get("loaded_runtime_modules", [])}
    assert len(exe) == 1 and None not in exe and loaded == exe
    runtime[label] = {"provider": provider, "full_browser_version": next(iter(exe)), "loaded_runtime_version": next(iter(loaded)), "observed_at_utc": identities["observed_at_utc"], "OS": identities["operating_system"], "architecture": identities["host_architecture"], "candidate_processes": len(candidates), "identity_method": "Read-only OS executable/loaded-module identity; every visible local candidate in this browser family has the same full build. Provider has no PID, so family-to-version binding is an explicit inference from uniform current process evidence and local-provider identity.", "internal_version_page_access": "NOT_USED; earlier rejection retained and not bypassed"}
now = datetime.now(timezone(timedelta(hours=3, minutes=30))).isoformat()
ready = {"at": now, "user_update": "Check now. i installed Edge Extention", "observed_providers": {"Chrome": "3", "Edge": "4"}, "edge_controllable_blank_tab": "1452708121", "chrome_controllable_blank_tab": "1823780339", "runtime_identities": runtime, "viewport_preflight": [{"width": w, "height": h, "Chrome": "MEASURED_EXACT_CLIENT_SIZE", "Edge": "MEASURED_EXACT_CLIENT_SIZE"} for w, h in ((1440, 900), (1024, 768), (390, 844))], "finding004": "RESOLVED_BY_HUMAN_CONNECTED_EDGE_EXTENSION_AND_ACTUAL_BLANK_TAB_CONTROL", "finding005": "RESOLVED_BY_PERMITTED_READ_ONLY_OS_RUNTIME_MODULE_EVIDENCE; earlier blocked internal URL remains blocked", "safari": "EXCLUDED_BY_HUMAN_DECISION; no runtime or version requirement", "EXT0024": "PASS_READINESS_APPROVED_CHROME_EDGE_MATRIX_AND_OBSERVED_IDENTITIES", "GATE07": "SCOPED_PASS_REUSED_SOURCE_VALID", "prior_attempts": "RUNTIME_READINESS.json preserved unchanged", "scope": "Existing canonical viewport/accessibility and 33 journey inputs retained; no product remediation or scope reduction", "application_identity": "../CEP-078_REENTRY_01/APPLICATION_IDENTITY.json unchanged and source-verified", "entry_result": "PASS", "runtime_results": "No application scenario result inferred from readiness"}
save("READINESS_RESUMED.json", ready)
matrix = json.loads((OUT / "EXT0024_MATRIX.json").read_text(encoding="utf-8"))
matrix["status"] = "APPROVED_CHROME_EDGE_MATRIX_ENVIRONMENT_READY"
matrix["runtime_identity_evidence"] = "READINESS_RESUMED.json + RUNNING_BROWSER_IDENTITIES.json"
for browser in matrix["browsers"]:
    browser["observed_runtime_version"] = runtime[browser["name"]]["full_browser_version"]
    browser["readiness"] = "PASS_CONNECTED_CONTROL_RUNTIME_IDENTITY_AND_VIEWPORT_PREFLIGHT"
matrix["exact_remaining_blocker"] = None
matrix["next_safe_action"] = "Execute only missing approved runtime verification; record failures without product remediation."
matrix["entry"] = "PASS_AFTER_HUMAN_EDGE_CONNECTION_AND_ALLOWED_RUNTIME_IDENTITY_EVIDENCE"
save("EXT0024_MATRIX.json", matrix)
save("ENTRY_REVIEW.json", {"at": now, "human_decision_applied": True, "safari_requirement": "EXCLUDED_FOR_V1_CEP078", "prerequisites": "CEP003/017 available and unchanged", "gate07": "PASS_SCOPED_CEP078_REUSED", "ext0024": "PASS_CHROME_EDGE_READINESS", "evidence": "READINESS_RESUMED.json", "eligibility": "ELIGIBLE", "entry": "PASS", "execution": "STARTED", "runtime_acceptance": "No PASS inferred before actual scenarios", "human_signoff_production_cep079_git_writes": "NOT_EXECUTED"})

# Hash-only non-production business baseline; sessions/last_login excluded, as in
# the accepted evidence helper. No source records or sensitive values serialized.
sys.path.insert(0, str(ROOT / "docs/governance/uiux/rv007_controlled_time"))
from support import guard, snapshot

guard()
baseline = snapshot()
save("DATA_BEFORE.json", {label: {"count": len(rows), "aggregate_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()} for label, rows in baseline.items()})

reg = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
raw = reg.read_bytes()
assert sha(reg) == entry["registry_before_sha256"]
text = entry["registry_before"]
humans = section(text, "human_decisions")
decision = """  CEP078_V1_BROWSER_SCOPE_20261023:
    source: docs/governance/cep/supporting/CEP-078_V1_BROWSER_SCOPE_HUMAN_DECISION_20261023.md
    authority: DIRECT_HUMAN_PRODUCT_GOVERNANCE_DECISION
    status: APPROVED_BY_HUMAN
    scope: BONIRA_V1_AND_CEP078_ONLY
    supported_browsers: [Google Chrome, Microsoft Edge]
    safari_required_for_entry_acceptance_dod: false
    historical_evidence_preserved: true
    safari_compatibility_certification_future_support: NOT_CLAIMED
"""
assert "CEP078_V1_BROWSER_SCOPE_20261023:" not in humans
text = text.replace("human_decisions:\n" + humans, "human_decisions:\n" + humans + decision, 1)
old = blocks(text)["CEP-078"]
cep = old
cep = re.sub(r"^    dependency_status: .*?$", "    dependency_status: MANDATORY_CEP003_CEP017_SCOPED_GATE07_AND_CHROME_EDGE_EXT0024_SATISFIED", cep, count=1, flags=re.M)
cep = re.sub(r"^    eligibility_status: .*?$", "    eligibility_status: ELIGIBLE_CHROME_EDGE_NON_PRODUCTION", cep, count=1, flags=re.M)
cep = cep.replace("      status: NOT_STARTED\n      lifecycle: BLOCKED_BEFORE_ENTRY", "      status: IN_PROGRESS\n      lifecycle: EXECUTION_STARTED", 1)
cep = cep.replace("      status: UNEXECUTED_ENTRY_BLOCKED", "      status: IN_PROGRESS_NO_RUNTIME_PASS_INFERRED", 1)
cep = cep.replace("    dod: NOT_MET_ENTRY_BLOCKED", "    dod: IN_PROGRESS", 1)
cep = re.sub(r"    blockers:\n.*?(?=    remaining_utv:)", "    blockers: []\n", cep, count=1, flags=re.S)
cep = re.sub(r"    remaining_utv:\n.*?(?=    completion_report:)", "    remaining_utv:\n    - Missing approved Chrome-Edge browser-responsive-accessibility execution evidence remains UTV until actual scenario execution\n", cep, count=1, flags=re.S)
cep = cep.replace("CEP-078_REENTRY_01/CEP-078_COMPLETION_REPORT.md", "CEP-078_REENTRY_02/CEP-078_COMPLETION_REPORT.md", 1)
cep = re.sub(r"      evidence_presence: .*?$", "      evidence_presence: CURRENT_ENTRY_PASS_RUNTIME_EXECUTION_IN_PROGRESS", cep, count=1, flags=re.M)
cep = re.sub(r"    last_execution:\n      branch: null\n      sha: null", "    last_execution:\n      branch: main\n      sha: 43ac319c6e73e48ca9626461b73987922c498ec3", cep, count=1)
cep = re.sub(r"    entry_review:\n.*?(?=    history:)", """    entry_review:
      evidence: docs/governance/cep/evidence/CEP-078_REENTRY_02/ENTRY_REVIEW.json
      readiness: docs/governance/cep/evidence/CEP-078_REENTRY_02/READINESS_RESUMED.json
      human_decision: CEP078_V1_BROWSER_SCOPE_20261023
      result: PASS
      gate07: PASS_FOR_CEP078_SCOPED_CONVERGENCE_REUSED
      ext0024: PASS_APPROVED_CHROME_EDGE_CONTROL_RUNTIME_IDENTITY_VIEWPORT_READINESS
      safari_requirement: EXCLUDED_BY_HUMAN_FOR_V1_CEP078
      execution: STARTED_NO_ACCEPTANCE_PASS_INFERRED
""", cep, count=1, flags=re.S)
cep += """    - date: '2026-10-23'
      status: HUMAN_BROWSER_SCOPE_APPLIED
      reason: Explicit Human decision sets Chrome and Edge as V1-CEP078 supported browsers; Safari excluded from entry-AC-DoD without compatibility-certification-future-support inference. Historical source and blocked evidence unchanged.
    - date: '2026-10-23'
      status: ENTRY_PASS_AND_STARTED
      reason: Human connected Edge extension; actual Chrome3 and Edge4 blank tabs controllable at all three canonical CSS viewports. Read-only OS process and loaded-module metadata proves uniform running Chrome155.0.8059.82 and Edge155.0.4283.62 across all visible family candidates, binding limitation explicit. No blocked internal-page workaround. Source-valid scoped GATE07 proof reused; Development guard passes. EXT0024 readiness and entry PASS; runtime scenarios begin, no AC-DoD PASS inferred.
"""
text = text.replace("  CEP-078:\n" + old, "  CEP-078:\n" + cep, 1)
summary = section(text, "summary").replace("  in_progress: 0\n", "  in_progress: 1\n", 1).replace("  blocked_current: 2\n", "  blocked_current: 1\n", 1)
text = text.replace("summary:\n" + section(text, "summary"), "summary:\n" + summary, 1)
frontier = section(text, "execution_frontier")
frontier = re.sub(r"^  current_session_continuation: .*?$", '  current_session_continuation: "CEP078_RUNTIME_IN_PROGRESS_AFTER_APPROVED_CHROME_EDGE_ENTRY"', frontier, flags=re.M)
frontier = re.sub(r"^  next_candidate_full_entry_eligibility: .*?$", '  next_candidate_full_entry_eligibility: "CEP078_ENTRY_PASS_EXECUTION_STARTED"', frontier, flags=re.M)
frontier = re.sub(r"^  boundary_reason: .*?$", '  boundary_reason: "Human Chrome-Edge scope applied; actual runtime readiness established; CEP078 only, no downstream or Production authority"', frontier, flags=re.M)
text = text.replace("execution_frontier:\n" + section(text, "execution_frontier"), "execution_frontier:\n" + frontier, 1)
assert all(v == blocks(text)[k] for k, v in blocks(entry["registry_before"]).items() if k != "CEP-078")
reg.write_bytes(text.replace("\n", "\r\n" if b"\r\n" in raw else "\n").encode("utf-8"))
(OUT / "CEP-078_COMPLETION_REPORT.md").write_text("# CEP-078 re-entry 02 — execution in progress\n\nHuman Chrome + Edge decision applied. Scoped GATE-07 proof reused. EXT-0024 and formal entry PASS. Actual runtime acceptance/DoD remain pending. Earlier readiness failures remain in RUNTIME_READINESS.json; resumed proof is READINESS_RESUMED.json. No Safari requirement, product remediation, downstream execution, Production, Human Sign-off or Git writes. Final reconciliation will replace this provisional report.\n", encoding="utf-8")
print("Formal CEP078 entry PASS; Registry IN_PROGRESS; source identity and Development baseline retained; no acceptance PASS inferred.")
