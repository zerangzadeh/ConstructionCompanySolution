"""Bounded, non-production CEP-078 re-entry closeout and evidence checks."""
import csv
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
REG = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
sys.stdout.reconfigure(encoding="utf-8")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8", stderr=subprocess.DEVNULL).strip()


def blocks(text):
    return dict(re.findall(r"^  (CEP-\d{3}):\n(.*?)(?=^  CEP-|^authority_scope:)", text, re.M | re.S))


def section(text, name):
    return re.search(r"^" + re.escape(name) + r":\n(.*?)(?=^[A-Za-z_]+:|\Z)", text, re.M | re.S).group(1)


def csv_write(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def reconcile():
    entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
    assert sha(REG) == entry["registry_before_sha256"], "Concurrent Registry mutation: stop"
    assessment = json.loads((OUT / "GATE07_CONVERGENCE.json").read_text(encoding="utf-8"))
    review = json.loads((OUT / "ENTRY_REVIEW.json").read_text(encoding="utf-8"))
    assert assessment["decision"] == "PASS_FOR_CEP078_DEVELOPMENT_IMPLEMENTED_CAPABILITY_SCOPE"
    assert review["ext0024"] == "PARTIAL_MATRIX_DEFINED; BLOCKED_SAFARI_RUNTIME_AND_EXACT_IDENTITIES"
    mapping = list(csv.DictReader((OUT.parent / "CEP-078_ACCEPTANCE_MAPPING.csv").open(encoding="utf-8")))
    for row in mapping:
        row["evidence_ids"] = "CEP-078-EV-011;CEP-078-EV-016;CEP-078-EV-019;CEP-078-EV-020"
        row["source_validity"] = "1497 accepted product hashes unchanged; original RV and prior blocked evidence retained; current gate and identity evidence is separate"
        row["current_reentry_delta"] = "19/19 scoped gate contributions supported; 42 distinct current tests PASS; Chrome/Edge/Safari matrix defined; Safari environment/exact runtime identities unavailable"
        if row["criterion"] == "AC-2":
            row["remaining_gap"] = "Safari exact OS-device-browser-engine runtime and complete observed runtime bindings; installed Chrome/Edge versions alone do not establish execution identities"
        elif row["criterion"] in ("DoD-2", "DoD-3"):
            row["remaining_gap"] = "Bind complete canonical matrix/procedure to available Safari and actual exact runtime identities; EXT0024 stays open"
        if row["criterion"].startswith("AC-"):
            assert row["result"] == "UTV"
    csv_write("CEP-078_ACCEPTANCE_MAPPING.csv", mapping)
    before = entry["registry_before"]
    text = before
    convergence = """    relevant_capability_convergence:
      CEP-078:
        status: PASS
        evaluated_at: '2026-10-23'
        source: OBJECTIVE_CURRENT_CONVERGENCE_ASSESSMENT
        evidence: docs/governance/cep/evidence/CEP-078_REENTRY_01/GATE07_CONVERGENCE.json
        scope: Development implemented shared UI and ESS frameworks plus available and conditional-unavailable states; all19 required IMB contributions mapped
        current_tests: 42_DISTINCT_PASS_WITH_ONE_EXPORT_ONLY_RETRY
        source_authority: PRESERVED
        external_activation: EXT0014_0016_0019_REQUIRED_ONLY_WHERE_AFFECTED_ACTIVATION_APPLIES_NO_NEW_ACTIVATION
        final_browser_runtime: UTV
        global_gate_pass_inferred: false
        human_signoff_or_production: NOT_EXECUTED
"""
    old_gates = section(text, "gates")
    assert "    relevant_capability_convergence:" not in old_gates.split("  GATE-07:\n")[1]
    new_gates = old_gates + convergence
    text = text.replace("gates:\n" + old_gates, "gates:\n" + new_gates, 1)
    old_cep = blocks(text)["CEP-078"]
    cep = old_cep
    scalar_updates = {
        "dependency_status": "MANDATORY_PREREQUISITES_AND_SCOPED_GATE07_SUPPORTED_EXT0024_UNSATISFIED",
        "eligibility_status": "BLOCKED_EXT0024_SAFARI_ENVIRONMENT_AND_EXACT_RUNTIME_IDENTITIES",
    }
    for key, value in scalar_updates.items():
        cep, n = re.subn(r"^    " + key + r": .*?$", "    " + key + ": " + value, cep, count=1, flags=re.M)
        assert n == 1
    cep = re.sub(r"^      source: Human request .*?$", "      source: Human request 2026-10-23 to clear CEP078 entry blockers and execute only when eligible; prior blocked history preserved", cep, count=1, flags=re.M)
    cep = re.sub(r"    blockers:\n.*?(?=    remaining_utv:)", "    blockers:\n    - CEP-078-FINDING-002 / BLOCKER-EXTERNAL / EXT-0024 full named Chrome-Edge-Safari matrix defined; available Safari OS-device-browser-engine runtime and exact execution identities absent\n", cep, count=1, flags=re.S)
    cep = re.sub(r"    remaining_utv:\n.*?(?=    completion_report:)", """    remaining_utv:
    - Safari test environment and exact OS-device-full-browser-engine identity; Chrome-Edge actual observed execution identities not replaced by installed binary metadata
    - Complete browser-accessibility-responsive matrix binding to existing safe canonical persona-route-state fixtures
    - All six canonical CEP078 browser runtime acceptance criteria unexecuted; no old RV result promoted to CEP execution
""", cep, count=1, flags=re.S)
    cep = cep.replace("path: docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md", "path: docs/governance/cep/evidence/CEP-078_REENTRY_01/CEP-078_COMPLETION_REPORT.md", 1)
    cep = cep.replace("evidence_presence: ENTRY_REVIEW_AND_REUSE_MAPPING_ONLY_NO_CEP_RUNTIME_EXECUTION", "evidence_presence: CURRENT_SCOPED_GATE_PROOF_MATRIX_AND_IDENTITY_PARTIAL_NO_CEP_BROWSER_EXECUTION", 1)
    cep = re.sub(r"    entry_review:\n.*?(?=    history:)", """    entry_review:
      evidence: docs/governance/cep/evidence/CEP-078_REENTRY_01/ENTRY_REVIEW.json
      acceptance_mapping: docs/governance/cep/evidence/CEP-078_REENTRY_01/CEP-078_ACCEPTANCE_MAPPING.csv
      prior_blocked_review: docs/governance/cep/evidence/CEP-078_ENTRY_REVIEW.json
      branch: main
      head: 43ac319c6e73e48ca9626461b73987922c498ec3
      result: BLOCKED_BEFORE_ENTRY
      canonical_report_verdict: EXECUTION FAILED
      verdict_semantics: External environment entry blocker; no browser scenario executed or failed
      gate07: PASS_FOR_CEP078_DEVELOPMENT_IMPLEMENTED_CAPABILITY_SCOPE_GLOBAL_ACTIVATION_NOT_GRANTED
      ext0024: MATRIX_DEFINED_SAFARI_ENVIRONMENT_AND_EXACT_RUNTIME_IDENTITIES_BLOCKED
      finding001: RESOLVED_FOR_SCOPED_ENTRY
      finding002: OPEN_EXACT_ENVIRONMENT_GAP
      current_gate_cases: 42_DISTINCT_PASS_WITH_ONE_EXPORT_ONLY_RETRY
      verification_execution: NOT_STARTED
""", cep, count=1, flags=re.S)
    cep += """    - date: '2026-10-23'
      status: SCOPED_GATE07_CONVERGENCE_VERIFIED
      reason: Reentry01 maps all 19 canonical contributions to actual sources and current tests. 42 distinct cases PASS; initial 41 PASS and one legacy exporter encoding failure retained, then original failed case passes with exporter destination isolated. Source and business assertions unchanged. Conditional Leave-Mission-certificate activations stay closed where absent. Canonical scoped emergence clears Finding001 for CEP078 Development entry only; global GATE07 remains NOT_READY and final browser evidence UTV.
    - date: '2026-10-23'
      status: EXT0024_MATRIX_DEFINED_ENVIRONMENT_BLOCKED
      reason: Canonical UIGAP025 explicitly names unverified Chrome-Edge-Safari behavior across critical journeys. All three browsers, 33 source scenario blocks and three CSS viewport classes retained. Exact accepted dirty application/configuration identity and installed Chrome155.0.8059.82-Edge155.0.4283.62 binary versions retained. Available provider and standard-path inventory has no Safari runtime or exact OS-device-browser-engine identity. No reduced Chromium-only matrix or runtime PASS.
    - date: '2026-10-23'
      status: ENTRY_REVIEW_BLOCKED
      reason: Both entry blockers did not clear. Finding001 resolved for scoped convergence; Finding002 remains open with exact Safari/runtime readiness gap. Runtime NOT_STARTED; all six AC UNEXECUTED; DoD NOT_MET_ENTRY_BLOCKED. New reentry completion report and manifests retained, prior blocked artifacts unchanged. No product-policy-permission-UI change, CEP079, Production, Human Sign-off or Git staging/integration command. STOP after final reconciliation.
"""
    text = text.replace("  CEP-078:\n" + old_cep, "  CEP-078:\n" + cep, 1)
    frontier = section(text, "execution_frontier")
    for key, value in {
        "current_session_continuation": "STOP_CEP078_REENTRY01_EXT0024_BLOCKED_AFTER_FINAL_RECONCILIATION",
        "next_candidate_full_entry_eligibility": "CEP078_SCOPED_GATE07_PASS_EXT0024_SAFARI_AND_EXACT_IDENTITIES_BLOCKED",
        "boundary_reason": "Current CEP078-only request assessed exact convergence; scoped GATE07 clears, EXT0024 full matrix environment incomplete; no browser execution or downstream authority",
    }.items():
        frontier, n = re.subn(r"^  " + key + r": .*?$", "  " + key + ": " + json.dumps(value), frontier, count=1, flags=re.M)
        assert n == 1
    text = text.replace("execution_frontier:\n" + section(text, "execution_frontier"), "execution_frontier:\n" + frontier, 1)
    assert len(blocks(text)) == 86
    assert all(v == blocks(text)[k] for k, v in blocks(before).items() if k != "CEP-078")
    for name in ("governance", "inventory", "summary", "authorization_batches", "human_decisions", "authority_scope", "v1_closure_triage", "repository_state"):
        assert section(text, name) == section(before, name)
    ending = "\r\n" if b"\r\n" in REG.read_bytes() else "\n"
    REG.write_bytes(text.replace("\n", ending).encode("utf-8"))
    (OUT / "REGISTRY_DELTA.diff").write_text("".join(difflib.unified_diff(before.splitlines(True), text.splitlines(True), fromfile="Registry at reentry01 start", tofile="Registry after reentry01")), encoding="utf-8")
    print("Registry reconciled: scoped GATE07 PASS, EXT0024 exact environment blocker only; CEP runtime NOT_STARTED.")


def check():
    entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
    before = entry["registry_before"]
    text = REG.read_text(encoding="utf-8")
    assert git("rev-parse", "HEAD") == entry["head"]
    assert git("diff", "--cached", "--name-only") == ""
    assert all(sha(ROOT / p) == v for p, v in entry["product_hashes"].items())
    assert all(sha(ROOT / p) == v for p, v in entry["prior_cep078_artifact_hashes"].items())
    assert sha(ROOT / "docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md") == entry["prior_report_hash"]
    assert sha(ROOT / "docs/governance/cep/manifests/CEP-078_EXECUTION_MANIFEST.md") == entry["prior_manifest_hash"]
    assert all(sha(ROOT / p) == v for p, v in entry["uiux_pointers"].items())
    trace = "docs/governance/cep/evidence/CEP-068_MISSION_LINK_TRACE.json"
    assert git("diff", "--name-only", "--", trace) == ""
    recovery = json.loads((OUT / "TEST_EXPORT_RECOVERY.json").read_text())
    assert sha(ROOT / trace) == recovery["restored_sha256"]
    prior = json.loads((OUT.parent / "CEP-078_ENTRY_REVIEW.json").read_text(encoding="utf-8"))
    checked = 0
    for folder, known in prior["accepted_evidence_integrity"].items():
        p = ROOT / "docs/governance/uiux" / folder
        assert sha(p / "MANIFEST.json") == known["manifest_sha256"]
        for path, expected in json.loads((p / "MANIFEST.json").read_text(encoding="utf-8")).items():
            assert sha(p / path) == expected, str(p / path)
            checked += 1
    assert checked == 340
    records = blocks(text)
    assert len(records) == 86
    assert all(v == records[k] for k, v in blocks(before).items() if k != "CEP-078")
    old_gates = section(before, "gates")
    new_gates = section(text, "gates")
    assert new_gates.startswith(old_gates)
    assert new_gates[len(old_gates):].startswith("    relevant_capability_convergence:\n      CEP-078:\n        status: PASS\n")
    assert "  GATE-07:\n    status: NOT_READY\n" in new_gates
    assert "  GATE-08:\n    status: NOT_PASSED\n" in new_gates
    cep = records["CEP-078"]
    assert "      status: NOT_STARTED\n      lifecycle: BLOCKED_BEFORE_ENTRY\n" in cep
    assert "      status: UNEXECUTED_ENTRY_BLOCKED\n" in cep
    assert "    dod: NOT_MET_ENTRY_BLOCKED\n" in cep
    assert "finding001: RESOLVED_FOR_SCOPED_ENTRY" in cep
    assert "    blockers:\n    - CEP-078-FINDING-002" in cep
    history_before = blocks(before)["CEP-078"].split("    history:\n")[1]
    assert cep.split("    history:\n")[1].startswith(history_before)
    counts = Counter(re.search(r"    execution:\n      status: (\S+)", v).group(1) for k, v in records.items() if int(k[-3:]) <= 79)
    assert counts == {"COMPLETE": 68, "PARTIAL": 3, "NOT_STARTED": 8}
    assert section(text, "summary") == section(before, "summary")
    assert "blocked_current: 2" in section(text, "summary")
    mapping = list(csv.DictReader((OUT / "CEP-078_ACCEPTANCE_MAPPING.csv").open(encoding="utf-8")))
    assert len(mapping) == 11 and sum(r["criterion"].startswith("AC-") for r in mapping) == 6
    assert all(r["result"] == "UTV" for r in mapping if r["criterion"].startswith("AC-"))
    planned = ["CLOSEOUT_CHECK.json", "CEP-078_EVIDENCE_MANIFEST.csv", "CEP-078_CHANGE_MANIFEST.csv"]
    paths = sorted({p.name for p in OUT.iterdir() if p.is_file()} | set(planned))
    csv_write("CEP-078_CHANGE_MANIFEST.csv", [{"path": (OUT / name).relative_to(ROOT).as_posix(), "change": "NEW", "purpose": "Isolated CEP078 reentry evidence; prior blocked evidence preserved"} for name in paths] + [{"path": "CEP_EXECUTION_REGISTRY.yaml", "change": "MODIFIED", "purpose": "CEP078/scoped GATE07/session-frontier only; all other CEP states unchanged"}])
    references = []
    for p in OUT.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
            if target in planned:
                continue
            assert (p.parent / target).resolve().is_file(), target
            references.append(target)
    result = subprocess.run(["git", "diff", "--check", "--", "CEP_EXECUTION_REGISTRY.yaml", trace], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    whitespace = [(p.name, i) for p in OUT.iterdir() if p.is_file() and p.suffix in (".py", ".md") for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if line.rstrip() != line]
    assert not whitespace, whitespace
    check_result = {
        "at": datetime.now(timezone(timedelta(hours=3, minutes=30))).isoformat(),
        "result": "PASS_CLOSEOUT_INTEGRITY_ONLY_NO_CEP_BROWSER_PASS",
        "accepted_artifacts_reverified": checked, "accepted_product_sources_preserved": len(entry["product_hashes"]),
        "prior_blocked_cep078_artifacts_preserved": len(entry["prior_cep078_artifact_hashes"]) + 2,
        "uiux_pointers_preserved": len(entry["uiux_pointers"]), "other_ceps_preserved": 85,
        "prior_history_preserved": True, "other_gate_states_preserved": True,
        "head_unchanged": True, "logical_staging_empty_and_unchanged": True,
        "index_cache_bytes_unchanged": sha(ROOT / ".git/index") == entry["index_sha256"],
        "index_note": "Index bytes changed during permitted status/stat refresh; no staged changes or Git-write command. No raw-index restoration attempted.",
        "historical_test_export": "Original path clean and restored hash matches recovery; original failed run preserved, retry isolated",
        "current_gate_cases": "42 distinct business cases PASS; original 41 plus single export-only retry", "gate_criteria_rows": 19,
        "gate07": "PASS_FOR_CEP078_SCOPED_CONVERGENCE; GLOBAL_NOT_READY_RETAINED",
        "ext0024": "MATRIX_DEFINED_ENVIRONMENT_BLOCKED_SAFARI_AND_EXACT_RUNTIME_IDENTITIES",
        "execution": "NOT_STARTED", "terminal_lifecycle": "BLOCKED_BEFORE_ENTRY", "runtime_ac": "0/6 UNEXECUTED", "scoped_dod": "NOT_MET_ENTRY_BLOCKED",
        "acceptance_mapping_rows": 11, "references_checked": references,
        "counts": {"current_governed": 79, "complete": 68, "partial": 3, "blocked_before_entry": 2, "other_not_started": 6, "post_v1": 7},
        "whitespace": "PASS for bounded Registry/restored trace/new script and document surfaces",
        "yaml_validation": "Bounded safe scalar/child-block updates; 86-record extraction, scope and untouched-section assertions; no full-parser claim",
        "production_cep079_human_signoff_git_commands": "NOT_EXECUTED", "stop": "CEP078_FINAL_RECONCILIATION_COMPLETE_BLOCKED",
    }
    save("CLOSEOUT_CHECK.json", check_result)
    primary = ["GATE07_CONVERGENCE.json", "GATE07_CONVERGENCE.csv", "GATE07_FOCUSED.json", "GATE07_FOCUSED.xml", "GATE07_RETRY.json", "EXT0024_MATRIX.json", "APPLICATION_IDENTITY.json", "BROWSER_INSTALLATIONS.json", "ENTRY_REVIEW.json", "CEP-078_ACCEPTANCE_MAPPING.csv", "CEP-078_COMPLETION_REPORT.md", "CEP-078_EXECUTION_MANIFEST.md", "TEST_EXPORT_RECOVERY.json", "CLOSEOUT_CHECK.json", "CEP-078_CHANGE_MANIFEST.csv", "ENTRY.json", "MISSION_LINK_TRACE.json"]
    evidence_paths = primary + sorted(p.name for p in OUT.iterdir() if p.is_file() and p.name not in primary + ["CEP-078_EVIDENCE_MANIFEST.csv"])
    manifest = [{"evidence_id": f"CEP-078-EV-{i:03d}", "path": (OUT / name).relative_to(ROOT).as_posix(), "sha256": sha(OUT / name), "kind": "Reentry gate/identity/mapping/preservation evidence; not CEP browser execution", "result": "HASHED_ACTUAL_ARTIFACT; see explicit scoped results and limitations"} for i, name in enumerate(evidence_paths, 11)]
    csv_write("CEP-078_EVIDENCE_MANIFEST.csv", manifest)
    for row in csv.DictReader((OUT / "CEP-078_EVIDENCE_MANIFEST.csv").open(encoding="utf-8")):
        assert sha(ROOT / row["path"]) == row["sha256"]
    print(json.dumps({"integrity": "PASS", "accepted_artifacts": 340, "product_sources": 1497, "other_ceps": 85, "gate07": "SCOPED_PASS", "ext0024": "BLOCKED_SAFARI_RUNTIME", "terminal": "BLOCKED_BEFORE_ENTRY", "runtime": "NOT_STARTED", "AC": "0/6 UNEXECUTED"}))


if __name__ == "__main__":
    {"reconcile": reconcile, "check": check}[sys.argv[1]]()
