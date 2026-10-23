"""Close actual partial CEP-078 runtime execution; preserve source and history."""
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


def csv_write(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def section(text, name):
    return re.search(r"^" + name + r":\n(.*?)(?=^[A-Za-z_]+:|\Z)", text, re.M | re.S).group(1)


def blocks(text):
    return dict(re.findall(r"^  (CEP-\d{3}):\n(.*?)(?=^  CEP-|^authority_scope:)", text, re.M | re.S))


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8", stderr=subprocess.DEVNULL).strip()


def reconcile():
    result = json.loads((OUT / "RUNTIME_RESULTS.json").read_text(encoding="utf-8"))
    assert result["result"] == "PARTIAL" and result["Edge"]["corrected_assertions"] == {"PASS": 24, "FAIL": 3}
    entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
    raw = REG.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    initial = text
    current = blocks(text)["CEP-078"]
    assert "      status: IN_PROGRESS\n" in current
    cep = current.replace("      status: IN_PROGRESS\n      lifecycle: EXECUTION_STARTED", "      status: PARTIAL\n      lifecycle: BLOCKED_AFTER_PARTIAL_VERIFICATION", 1)
    cep = re.sub(r"^    eligibility_status: .*?$", "    eligibility_status: BLOCKED_REQUIRED_IN_SCOPE_ACCESSIBILITY_FAILURE_AFTER_VALID_ENTRY", cep, count=1, flags=re.M)
    cep = cep.replace("      passed: null\n      total: 6\n      status: IN_PROGRESS_NO_RUNTIME_PASS_INFERRED", "      passed: 4\n      total: 6\n      status: PARTIAL_AC1_FAIL_AC3_PARTIAL_AC2_4_5_6_PASS", 1)
    cep = cep.replace("    dod: IN_PROGRESS", "    dod: NOT_MET_REQUIRED_ACCESSIBILITY_FAILURE_AND_REMAINING_UTV", 1)
    cep = cep.replace("    blockers: []", "    blockers:\n    - CEP-078-FINDING-006 / BLOCKER-TEST / Existing UIUX-F-107 login page has two nested main landmarks; required actual Edge check FAIL at desktop-tablet-mobile; separate remediation authority needed", 1)
    cep = re.sub(r"    remaining_utv:\n.*?(?=    completion_report:)", """    remaining_utv:
    - Chrome anonymous login coverage; current authenticated session redirected Login to Home and was preserved without identity change
    - Other 32 approved journey inputs for both Chrome and Edge remain unexecuted after required failed shared-login accessibility test
    - Remaining keyboard-semantic-table-modal-Jalali-role-workspace states and full cross-browser runtime coverage remain UTV; scope not deleted or promoted
""", cep, count=1, flags=re.S)
    cep = re.sub(r"      evidence_presence: .*?$", "      evidence_presence: ACTUAL_PARTIAL_RUNTIME_ARTIFACTS_WITH_OPEN_REQUIRED_ACCESSIBILITY_FINDING", cep, count=1, flags=re.M)
    cep = cep.replace("    history:\n", """    verification_review:
      evidence: docs/governance/cep/evidence/CEP-078_REENTRY_02/RUNTIME_RESULTS.json
      acceptance_mapping: docs/governance/cep/evidence/CEP-078_REENTRY_02/CEP-078_ACCEPTANCE_MAPPING.csv
      canonical_verdict: EXECUTION PARTIAL
      entry_result: PASS_RETAINED
      ext0024: APPROVED_CHROME_EDGE_READINESS_PASS_RETAINED
      finding006: OPEN_EXISTING_UIUX_F107_REQUIRED_TEST_FAILURE
      corrected_edge_assertions: 24_PASS_3_FAIL_ACROSS_THREE_VIEWPORTS
      chrome_anonymous_login: UTV_AUTHENTICATED_REDIRECT_PRECONDITION_NOT_MET
      source_changes: NONE
      business_data: 518_MODEL_AGGREGATES_UNCHANGED
      safari_requirement: EXCLUDED_BY_HUMAN_DECISION
    history:
""", 1)
    cep += """    - date: '2026-10-23'
      status: PARTIAL
      reason: Actual Edge Login at 1440x900-1024x768-390x844 reproduces existing UIUX-F107 two nested main landmarks. Corrected assertions24 PASS-3 required FAIL; initial Tab expectation skipped visible forgot-password link and was corrected in evidence only. Chrome existing authenticated session redirects to Home; anonymous login UTV, no session change. AC1 FAIL, AC3 PARTIAL, AC2-4-5-6 PASS; scoped DoD not met. Finding006 OPEN; affected verification stopped under required-test fix-or-block rule, no silent product remediation. Full remaining matrix UTV; accepted RV evidence and baseline debt unchanged. Human Chrome-Edge decision and valid entry retained; no Safari requirement, CEP079, Production, Human Sign-off or Git writes. STOP after partial reconciliation.
"""
    text = text.replace("  CEP-078:\n" + current, "  CEP-078:\n" + cep, 1)
    record_map = blocks(text)
    states = {k: re.search(r"    execution:\n      status: (\S+)", v).group(1) for k, v in record_map.items() if int(k[-3:]) <= 79}
    counts = Counter(states.values())
    blocked = sum(s == "NOT_STARTED" and "lifecycle: BLOCKED" in record_map[k] for k, s in states.items())
    values = {"execution_state_complete": counts["COMPLETE"], "in_progress": counts["IN_PROGRESS"], "blocked_current": blocked, "partial_current": counts["PARTIAL"], "failed_current": counts["FAILED"], "not_started_other_current_governed": counts["NOT_STARTED"] - blocked}
    summary = section(text, "summary")
    for key, value in values.items():
        summary, n = re.subn(r"^  " + key + r": .*?$", f"  {key}: {value}", summary, count=1, flags=re.M)
        assert n == 1
    text = text.replace("summary:\n" + section(text, "summary"), "summary:\n" + summary, 1)
    frontier = section(text, "execution_frontier")
    for key, value in {"current_session_continuation": "STOP_CEP078_PARTIAL_REQUIRED_ACCESSIBILITY_FINDING006_AFTER_RECONCILIATION", "next_candidate_full_entry_eligibility": "CEP078_PARTIAL_NEEDS_SEPARATELY_AUTHORIZED_REMEDIATION_AND_AFFECTED_RUNTIME_REVALIDATION", "boundary_reason": "Human Chrome-Edge scope applied and entry passed; actual required Login semantic check fails. No product-remediation or downstream-Production authority."}.items():
        frontier, n = re.subn(r"^  " + key + r": .*?$", "  " + key + ": " + json.dumps(value), frontier, count=1, flags=re.M)
        assert n == 1
    text = text.replace("execution_frontier:\n" + section(text, "execution_frontier"), "execution_frontier:\n" + frontier, 1)
    assert all(v == blocks(text)[k] for k, v in blocks(entry["registry_before"]).items() if k != "CEP-078")
    ending = "\r\n" if b"\r\n" in raw else "\n"
    REG.write_bytes(text.replace("\n", ending).encode("utf-8"))
    (OUT / "REGISTRY_DELTA.diff").write_text("".join(difflib.unified_diff(entry["registry_before"].splitlines(True), text.splitlines(True), fromfile="Registry before Human scope reentry02", tofile="Registry after actual partial runtime")), encoding="utf-8")

    old_rows = list(csv.DictReader((OUT / "CEP-078_ACCEPTANCE_MAPPING.csv").open(encoding="utf-8")))
    statuses = {"AC-1": "FAIL", "AC-2": "PASS", "AC-3": "PARTIAL", "AC-4": "PASS", "AC-5": "PASS", "AC-6": "PASS", "DoD-1": "FAIL", "DoD-2": "PASS", "DoD-3": "PASS", "DoD-4": "PASS", "DoD-5": "PARTIAL"}
    gaps = {"AC-1": "Existing UIUX-F107 required Login landmark check FAIL; separate remediation and full missing runtime needed", "AC-2": "No identity/definition gap in executed scope; provider-to-version binding inference retained explicitly", "AC-3": "Actual bounded Edge runtime executed; Chrome anonymous precondition and remaining32 journey inputs UTV", "AC-4": "No artifact-format gap for executed scope; no artifacts fabricated for unexecuted states", "AC-5": "Open Finding006 remains; no completion/waiver or silent remediation", "AC-6": "Full remaining Chrome-Edge matrix UTV retained; Safari excluded", "DoD-1": "Required semantic outcome FAIL", "DoD-2": "Definition/identity supported; no physical-device conformance claim", "DoD-3": "Procedure prepared and required-failure stop applied", "DoD-4": "Explicit measured pass-fail-partial-UTV records retained", "DoD-5": "Actual required evidence incomplete; failed result and unexecuted coverage prevent DoD"}
    for row in old_rows:
        row["result"] = statuses[row["criterion"]]
        row["remaining_gap"] = gaps[row["criterion"]]
        row["current_reentry_delta"] = "Human scope applied; actual Chrome-Edge control and uniform running builds verified; actual Edge Login semantic failure, Chrome anonymous UTV; no product changes"
        row["evidence_ids"] = "Resolved by current evidence manifest: READINESS_RESUMED/RUNNING_BROWSER_IDENTITIES/RUNTIME_RESULTS/RUNTIME_OBSERVATIONS/KEYBOARD_CORRECTION"
        row["existing_evidence"] += "; current READINESS_RESUMED.json + RUNTIME_RESULTS.json; original RV IDs never relabeled"
    csv_write("CEP-078_ACCEPTANCE_MAPPING.csv", old_rows)
    (OUT / "RUNTIME_TEST_OUTPUT.txt").write_text("CEP-078 actual runtime assertion output\nEdge / CEP-078-SC-001 / 1440x900: FAIL nested main landmarks\nEdge / CEP-078-SC-001 / 1024x768: FAIL nested main landmarks\nEdge / CEP-078-SC-001 / 390x844: FAIL nested main landmarks\nCorrected Edge assertions:24 PASS,3 FAIL.\nInitial direct-password Tab expectation corrected to include visible forgot-password link; original evidence retained.\nChrome anonymous Login:UTV at all3 observed sizes due authenticated redirect; session preserved.\nObserved page console errors:0. Business form submissions:0.\nOther32 approved journey inputs:UTV after required failure stop. No full browser, WCAG or regression PASS.\n", encoding="utf-8")
    print(json.dumps({"execution": "PARTIAL", "lifecycle": "BLOCKED_AFTER_PARTIAL_VERIFICATION", "AC": "4 PASS / 1 FAIL / 1 PARTIAL", "DoD": "NOT_MET", "summary": values}))


def check():
    entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
    before = entry["registry_before"]
    text = REG.read_text(encoding="utf-8")
    assert git("rev-parse", "HEAD") == entry["head"]
    assert git("diff", "--cached", "--name-only") == ""
    assert all(sha(ROOT / p) == v for p, v in entry["product_hashes"].items())
    assert all(sha(ROOT / p) == v for p, v in entry["previous_reentry_hashes"].items())
    assert all(sha(ROOT / p) == v for p, v in entry["prior_cep078_artifact_hashes"].items())
    assert all(sha(ROOT / p) == v for p, v in entry["uiux_pointers"].items())
    assert sha(ROOT / entry["human_decision_path"]) == entry["human_decision_sha256"]
    prior = json.loads((OUT.parent / "CEP-078_ENTRY_REVIEW.json").read_text(encoding="utf-8"))
    total = 0
    for folder, metadata in prior["accepted_evidence_integrity"].items():
        base = ROOT / "docs/governance/uiux" / folder
        assert sha(base / "MANIFEST.json") == metadata["manifest_sha256"]
        for name, value in json.loads((base / "MANIFEST.json").read_text(encoding="utf-8")).items():
            assert sha(base / name) == value, name
            total += 1
    assert total == 340
    old_records, records = blocks(before), blocks(text)
    assert len(records) == 86
    assert all(v == records[k] for k, v in old_records.items() if k != "CEP-078")
    for name in ("governance", "inventory", "gates", "authorization_batches", "authority_scope", "v1_closure_triage", "repository_state"):
        assert section(text, name) == section(before, name)
    assert section(text, "human_decisions").startswith(section(before, "human_decisions"))
    assert "    supported_browsers: [Google Chrome, Microsoft Edge]" in section(text, "human_decisions")
    cep = records["CEP-078"]
    assert "      status: PARTIAL\n      lifecycle: BLOCKED_AFTER_PARTIAL_VERIFICATION" in cep
    assert "      passed: 4\n      total: 6" in cep
    assert "entry_result: PASS_RETAINED" in cep
    assert "    - CEP-078-FINDING-006 / BLOCKER-TEST" in cep
    assert cep.split("    history:\n")[1].startswith(old_records["CEP-078"].split("    history:\n")[1])
    states = Counter(re.search(r"    execution:\n      status: (\S+)", v).group(1) for k, v in records.items() if int(k[-3:]) <= 79)
    assert states == {"COMPLETE": 68, "PARTIAL": 4, "NOT_STARTED": 7}, states
    assert "  blocked_current: 1\n" in section(text, "summary") and "  partial_current: 4\n" in section(text, "summary")
    mapping = list(csv.DictReader((OUT / "CEP-078_ACCEPTANCE_MAPPING.csv").open(encoding="utf-8")))
    assert len(mapping) == 11
    ac = Counter(r["result"] for r in mapping if r["criterion"].startswith("AC-"))
    assert ac == {"PASS": 4, "FAIL": 1, "PARTIAL": 1}
    data = json.loads((OUT / "DATA_INTEGRITY.json").read_text())
    assert data["result"] == "PASS" and not data["changes"] and data["models_compared"] == 518
    cleanup = json.loads((OUT / "BROWSER_CLEANUP.json").read_text())
    assert cleanup["edgeCreatedTab"] == cleanup["chromeCreatedTab"] == "CLOSED"
    assert cleanup["edgeViewport"] == cleanup["chromeViewport"] == "RESET"
    import struct
    def native_size(path):
        raw = path.read_bytes()
        assert raw[:2] == b"\xff\xd8", "Expected unmodified native JPEG capture"
        offset = 2
        while offset < len(raw):
            assert raw[offset] == 0xFF
            while raw[offset] == 0xFF:
                offset += 1
            marker = raw[offset]
            offset += 1
            length = struct.unpack(">H", raw[offset:offset + 2])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack(">HH", raw[offset + 3:offset + 7])
                return width, height
            assert marker not in (0xD9, 0xDA), "JPEG dimensions missing before image data"
            offset += length
        raise AssertionError("JPEG dimensions missing")
    image_sizes = {}
    for width, height in ((1440, 900), (1024, 768), (390, 844)):
        path = OUT / f"edge_login_focus_{width}.jpg"
        size = native_size(path)
        # Native mobile capture is one pixel shorter than the independently
        # measured 390x844 CSS viewport. Preserve the returned image verbatim.
        expected_pixels = (390, 843) if width == 390 else (width, height)
        assert size == expected_pixels
        image_sizes[path.name] = list(size)
    expected = {"CLOSEOUT_CHECK.json", "CEP-078_EVIDENCE_MANIFEST.csv", "CEP-078_CHANGE_MANIFEST.csv"}
    files = sorted({p.name for p in OUT.iterdir() if p.is_file()} | expected)
    csv_write("CEP-078_CHANGE_MANIFEST.csv", [{"path": (OUT / name).relative_to(ROOT).as_posix(), "change": "NEW", "purpose": "Isolated Human-scope/entry/actual-partial-runtime evidence"} for name in files] + [{"path": entry["human_decision_path"], "change": "NEW", "purpose": "Direct Human V1-CEP078 Chrome+Edge scope decision"}, {"path": "CEP_EXECUTION_REGISTRY.yaml", "change": "MODIFIED", "purpose": "Human decision and CEP078 entry/start/partial/summary/frontier reconciliation only"}])
    references = []
    for path in OUT.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if target in expected:
                continue
            assert (path.parent / target).resolve().is_file(), target
            references.append(target)
    diff_check = subprocess.run(["git", "diff", "--check", "--", "CEP_EXECUTION_REGISTRY.yaml"], cwd=ROOT, capture_output=True, text=True)
    assert diff_check.returncode == 0, diff_check.stdout
    whitespace = [(p.name, n) for p in OUT.iterdir() if p.is_file() and p.suffix in (".md", ".py") for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if line.rstrip() != line]
    assert not whitespace
    check_result = {"at": datetime.now(timezone(timedelta(hours=3, minutes=30))).isoformat(), "result": "PASS_CLOSEOUT_INTEGRITY_NOT_RUNTIME_ACCEPTANCE", "execution": "PARTIAL", "lifecycle": "BLOCKED_AFTER_PARTIAL_VERIFICATION", "entry": "PASS_RETAINED", "human_browser_scope": "Chrome+Edge; Safari excluded", "runtime_builds": {"Chrome": "155.0.8059.82", "Edge": "155.0.4283.62"}, "AC": {"PASS": 4, "FAIL": 1, "PARTIAL": 1}, "DoD": "NOT_MET_REQUIRED_ACCESSIBILITY_FAILURE_AND_REMAINING_UTV", "required_finding": "CEP-078-FINDING-006 / existing UIUX-F-107", "runtime_assertions": "24 PASS / 3 required FAIL; Chrome anonymous Login UTV", "accepted_artifacts_preserved": 340, "product_sources_preserved": 1497, "prior_reentry_files_preserved": len(entry["previous_reentry_hashes"]), "other_ceps_preserved": 85, "gates_and_prior_history_preserved": True, "business_model_aggregates": "518 unchanged; normal sessions/last_login excluded", "head_unchanged": True, "staging_empty": True, "index_bytes_unchanged": sha(ROOT / ".git/index") == entry["index_sha256"], "capture_pixel_sizes": image_sizes, "capture_privacy": "Native empty-control images; no stored secrets or image edits", "browser_cleanup": "Viewports reset; created tabs closed; existing session/user tabs retained", "references_checked": references, "counts": {"current_governed": 79, "complete": 68, "partial": 4, "blocked_not_started": 1, "other_not_started": 6, "post_v1": 7}, "whitespace": "PASS scoped Registry/new documents/scripts", "yaml_check": "Bounded safe block/scalar edits;86 records and untouched-section/history assertions; no full-parser claim", "product_migrations_permissions": "UNCHANGED", "cep079_production_human_signoff_git_writes": "NOT_EXECUTED", "stop": "CEP078_PARTIAL_FINAL_RECONCILIATION_COMPLETE"}
    save("CLOSEOUT_CHECK.json", check_result)
    prior_manifests = [OUT.parent / "CEP-078_EVIDENCE_MANIFEST.csv", OUT.parent / "CEP-078_REENTRY_01/CEP-078_EVIDENCE_MANIFEST.csv"]
    next_id = max(int(r["evidence_id"].split("-")[-1]) for manifest in prior_manifests for r in csv.DictReader(manifest.open(encoding="utf-8"))) + 1
    priority = ["RUNTIME_RESULTS.json", "RUNTIME_OBSERVATIONS.json", "KEYBOARD_CORRECTION.json", "READINESS_RESUMED.json", "RUNNING_BROWSER_IDENTITIES.json", "EXT0024_MATRIX.json", "ENTRY_REVIEW.json", "CEP-078_ACCEPTANCE_MAPPING.csv", "CEP-078_COMPLETION_REPORT.md", "CEP-078_EXECUTION_MANIFEST.md", "CLOSEOUT_CHECK.json"]
    ordered = priority + sorted(p.name for p in OUT.iterdir() if p.is_file() and p.name not in priority + ["CEP-078_EVIDENCE_MANIFEST.csv"])
    ids = {name: f"CEP-078-EV-{n:03d}" for n, name in enumerate(ordered, next_id)}
    for row in mapping:
        row["evidence_ids"] = ";".join(ids[name] for name in ("RUNTIME_RESULTS.json", "RUNTIME_OBSERVATIONS.json", "READINESS_RESUMED.json", "CEP-078_ACCEPTANCE_MAPPING.csv"))
    csv_write("CEP-078_ACCEPTANCE_MAPPING.csv", mapping)
    evidence = [{"evidence_id": ids[name], "path": (OUT / name).relative_to(ROOT).as_posix(), "sha256": sha(OUT / name), "kind": "Actual bounded runtime/readiness/scope/preservation evidence; see explicit PASS-FAIL-PARTIAL-UTV scope", "result": "RETAINED_ACTUAL_ARTIFACT_NOT_BLANKET_PASS"} for name in ordered]
    evidence.append({"evidence_id": f"CEP-078-EV-{next_id+len(ordered):03d}", "path": entry["human_decision_path"], "sha256": sha(ROOT / entry["human_decision_path"]), "kind": "Explicit Human Product-Governance browser scope decision", "result": "APPROVED_BY_HUMAN_FOR_V1_CEP078_ONLY"})
    csv_write("CEP-078_EVIDENCE_MANIFEST.csv", evidence)
    assert all(sha(ROOT / row["path"]) == row["sha256"] for row in csv.DictReader((OUT / "CEP-078_EVIDENCE_MANIFEST.csv").open(encoding="utf-8")))
    print(json.dumps({"integrity": "PASS", "execution": "PARTIAL", "AC": "4 PASS / 1 FAIL / 1 PARTIAL", "DoD": "NOT_MET", "accepted_artifacts": 340, "product_sources": 1497, "business_aggregates_unchanged": 518, "other_ceps_preserved": 85, "current_blocker": "Existing UIUX-F107 required landmark failure"}))


if __name__ == "__main__":
    {"reconcile": reconcile, "check": check}[sys.argv[1]]()
