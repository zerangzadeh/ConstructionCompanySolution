"""Bounded CEP-078 entry evidence and Registry reconciliation; no application imports."""
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
UI = ROOT / "docs/governance/uiux"
REG = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
ARCHIVES = Path(r"E:\ERP_Construction_Documents\New Version\BONIRA_TRUE_LATEST_STATE_RECONSTRUCTION_20261013\Consolidated_Packages")
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
sys.stdout.reconfigure(encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def save(name, data):
    (OUT / ("CEP-078_" + name)).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def blocks(text):
    return dict(re.findall(r"^  (CEP-\d{3}):\n(.*?)(?=^  CEP-|^authority_scope:)", text, re.M | re.S))


def section(text, name):
    return re.search(r"^" + re.escape(name) + r":\n(.*?)(?=^[A-Za-z_]+:|\Z)", text, re.M | re.S).group(1)


def dump_csv(name, columns, rows):
    with (OUT / ("CEP-078_" + name)).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def entry():
    assert not (OUT / "CEP-078_ENTRY_REVIEW.json").exists(), "Preserve prior entry evidence"
    before = REG.read_bytes()
    text = before.decode("utf-8").replace("\r\n", "\n")
    records = blocks(text)
    assert len(records) == 86
    head = git("rev-parse", "HEAD")
    assert git("branch", "--show-current") == "main"
    assert head == "43ac319c6e73e48ca9626461b73987922c498ec3"
    assert git("rev-parse", "origin/main") == head
    prompt = ROOT / "docs/governance/cep/PROMPTS/CEP-078_EXECUTION_PROMPT.md"
    identity = sha(prompt)
    expected = re.search(r"  CEP-078:\n.*?sha256: ([a-f0-9]+)", (ROOT / "docs/governance/cep/CEP_PROMPT_MANIFEST.yaml").read_text(), re.S).group(1)
    assert identity == expected == "313eb92ea69db33fe2ccaa6d881a6346949286aa8d9c688ac87dd820b0e92030"
    for cep in ("CEP-003", "CEP-017"):
        assert "      status: COMPLETE\n" in records[cep]
    assert "  GATE-07:\n    status: NOT_READY\n" in text
    accepted = {}
    for name in ("wave_de_fixture_closure", "wave_e_targeted_closure", "f135_closure"):
        folder = UI / name
        manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
        bad = [k for k, v in manifest.items() if not (folder / k).is_file() or sha(folder / k) != v]
        assert not bad, (name, bad)
        accepted[name] = {"manifest_sha256": sha(folder / "MANIFEST.json"), "checked_artifacts": len(manifest), "mismatches": bad}
    previous = json.loads((UI / "f135_closure/ENTRY.json").read_text(encoding="utf-8"))
    sources = {k: v for k, v in previous["hashes"].items() if k.split("/")[0] in ("apps", "core", "config", "templates", "tests", "static")}
    final_changes = json.loads((UI / "f135_closure/SOURCE_INTEGRITY.json").read_text())["changes"]
    sources.update({k: v["current"] for k, v in final_changes.items()})
    mismatches = [k for k, v in sources.items() if not (ROOT / k).is_file() or sha(ROOT / k) != v]
    assert not mismatches, mismatches
    paths = git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    product = {p: sha(ROOT / p) for p in paths if p.split("/")[0] in ("apps", "core", "config", "templates", "tests", "static") and (ROOT / p).is_file()}
    ui_pointers = {p.relative_to(ROOT).as_posix(): sha(p) for p in UI.iterdir() if p.is_file()}
    recovered = {}
    recovery_files = {
        "BONIRA_CODEX_EXECUTION_PACKAGE_DESIGN_CONSOLIDATED_LATEST.zip": ["packages/CEP-078.md", "BONIRA_CEP_DEPENDENCY_REGISTER.csv", "BONIRA_CEP_EXTERNAL_DEPENDENCY_REGISTER.csv"],
        "BONIRA_IMPLEMENTATION_DEPENDENCY_GRAPH_CONSOLIDATED_LATEST.zip": ["BONIRA_EXTERNAL_IMPLEMENTATION_DEPENDENCY_REGISTER.csv", "BONIRA_IMPLEMENTATION_DEPENDENCY_EDGE_REGISTER.csv"],
        "BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG_CONSOLIDATED_LATEST.zip": ["BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG.csv"],
        "BONIRA_IMPLEMENTATION_ROADMAP_CONSOLIDATED_LATEST.zip": ["BONIRA_IMPLEMENTATION_GATE_REGISTER.csv"],
        "BONIRA_UI_WORKSPACE_ARCHITECTURE_CONSOLIDATED_LATEST.zip": ["BONIRA_UI_ARCHITECTURE_REGISTER.csv"],
        "BONIRA_REQUIRED_SPECIFICATION_COMPLETION_CONSOLIDATED_LATEST.zip": ["BONIRA_CONFIGURATION_PROFILE_MATRIX.csv"],
    }
    for name, members in recovery_files.items():
        archive = ARCHIVES / name
        data = {"path": str(archive), "sha256": sha(archive), "members": {}}
        with zipfile.ZipFile(archive) as z:
            for member in members:
                content = z.read(member)
                record = {"sha256": hashlib.sha256(content).hexdigest()}
                if member.endswith(".csv"):
                    rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
                    record["relevant_rows"] = [r for r in rows if any(t in str(r) for t in ("CEP-078", "EXT-0024", "IMB-0108")) or ("GATE_REGISTER" in member and r.get("Gate ID") in ("GATE-02", "GATE-07", "GATE-08")) or ("UI_ARCHITECTURE_REGISTER" in member and r.get("UI Architecture ID") in ("UIA-010", "UIA-011"))]
                    if "CONFIGURATION_PROFILE" in member:
                        record["applicability"] = "Three profile suggestions; package configuration impact N/A; no browser support policy or activation inferred"
                else:
                    record["content"] = content.decode("utf-8-sig")
                data["members"][member] = record
        recovered[name] = data
    final = json.loads((UI / "f135_closure/FINAL_RECONCILIATION.json").read_text())
    save("ENTRY_REVIEW.json", {
        "recorded_at": datetime.now(timezone(timedelta(hours=3, minutes=30))).isoformat(),
        "environment": "Development / Non-Production; entry review only; no application connection or browser execution",
        "authorization": "Current Human request + conditional standing non-production authority; no waiver of entry conditions",
        "repository": {"branch": "main", "head": head, "origin_main": git("rev-parse", "origin/main"), "upstream": git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"), "ahead_behind": git("rev-list", "--left-right", "--count", "HEAD...@{upstream}"), "remote_freshness": "NOT_QUERIED", "status": git("status", "--short"), "diff_name_status": git("diff", "--name-status"), "diff_stat": git("diff", "--stat"), "index_sha256": sha(ROOT / ".git/index"), "commits_since_registry_baseline": git("log", "--oneline", "582e4183bb83e05bcb72860f0e2e546940b245d2..HEAD")},
        "canonical_prompt": {"path": prompt.relative_to(ROOT).as_posix(), "sha256": identity, "manifest_match": True},
        "local_authority_hashes": {p: sha(ROOT / p) for p in ("Agents.md", "ROADMAP.md", "docs/governance/CEP_PROGRAM_AUTHORITY.md", "docs/governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md", "docs/ROADMAP_EXECUTION_PLAYBOOK.md", "docs/governance/cep/CEP_PROMPT_MANIFEST.yaml")},
        "registry_before": {"sha256": hashlib.sha256(before).hexdigest(), "cep078": records["CEP-078"], "sections": {n: section(text, n) for n in ("summary", "execution_frontier", "repository_state")}, "other_cep_hashes": {k: digest(v) for k, v in records.items() if k != "CEP-078"}, "untouched_section_hashes": {n: digest(section(text, n)) for n in ("governance", "inventory", "gates", "authorization_batches", "human_decisions", "authority_scope", "v1_closure_triage")}},
        "approved_recovery": {"reason": "Required upstream canonical records not present repository-locally; approved consolidated location established by CEP-034_SOURCE_IDENTITY.json and CEP-017 manifest; available local prompt never substituted", "archives": recovered},
        "prerequisites": {"CEP-003": "COMPLETE; 11 focused tests historically PASS, actual shared form/RTL/Jalali sources present; historical Registry AC unrecorded is not rewritten", "CEP-017": "COMPLETE; 12/12 AC and 16 final combined tests historically PASS; current shared drawer/navigation source present"},
        "gates": {"GATE-02": "PASS_RETAINED", "GATE-07": "NOT_READY_RETAINED; no current full or capability-scoped convergence PASS established", "GATE-08": "NOT_PASSED_RETAINED; EXIT, not an added entry prerequisite"},
        "external": {"EXT-0024": "NOT_ESTABLISHED: approved cross-browser/device/viewport/accessibility matrix and exact browser/build version missing from evidence reviewed; accepted latest audit explicitly lacks full exact browser build", "search_scope": "Current Registry, local canonical prompt, certification/, UIUX playbook/matrices/metadata/reports, recovered package/external/dependency/gate/UI/profile sources; not an assertion of absence outside inspected approved sources"},
        "accepted_evidence_integrity": accepted,
        "accepted_source_state": {"compared_files": len(sources), "mismatches": mismatches, "basis": "f135_closure ENTRY source hashes with final SOURCE_INTEGRITY current hashes for its two authorized changed paths", "same_head": previous["head"] == head},
        "product_hashes": product,
        "uiux_pointer_hashes": ui_pointers,
        "accepted_current_state": final,
        "reuse_decision": "Original RV evidence retained for provenance/gap mapping, not relabeled CEP runtime PASS. Canonical DoD requires actual CEP verification evidence; audit playbook section 2 forbids retrospective promotion.",
        "findings": [
            {"id": "CEP-078-FINDING-001", "class": "BLOCKER-DEPENDENCY", "result": "BLOCKED", "evidence": "Registry GATE-07 NOT_READY and recovered gate failure consequence explicitly blocks IMB-0108; all 19 contributor owners now COMPLETE is insufficient for convergence/activation evidence", "resolution": "Establish evidence-supported GATE-07 global or explicitly capability-scoped convergence, including applicable EXT0014/0016/0019 activation evidence; no blanket activation inferred"},
            {"id": "CEP-078-FINDING-002", "class": "BLOCKER-EXTERNAL", "result": "UTV", "evidence": "EXT-0024 approved supported browser/device/viewport/accessibility matrix plus exact build/version not established; f135_closure/BROWSER_METADATA fullBrowserBuildAvailable=false; latest evidence single provider", "resolution": "Establish the approved CEP scenario/environment matrix and exact application source/configuration and browser versions, then repeat entry; ordinary safe engineering readiness can be proved under standing authority"},
            {"id": "CEP-078-FINDING-003", "class": "EVIDENCE_REUSE_LIMIT", "result": "PARTIAL", "evidence": "340 accepted artifact hashes and 1497 accepted source hashes match, but provenance/scope/version and DoD prevent promotion to CEP execution; F-135 supersedes RV-EV-064 only", "resolution": "Retain accepted evidence; execute only gaps permitted by the approved CEP matrix after entry clears; do not duplicate sufficient evidence or infer full conformance"},
        ],
        "disposition": "BLOCKED_BEFORE_ENTRY", "runtime_execution": "NOT_STARTED", "acceptance": "UNEXECUTED; 0/6 proved by CEP runtime evidence", "dod": "NOT_MET_ENTRY_BLOCKED", "report_verdict": "EXECUTION FAILED (entry prerequisites prevent execution; not a runtime test failure)",
        "new_product_changes": 0, "new_runtime_checks": 0, "new_application_tests": 0, "migrations_and_business_data_changes": "NONE", "cep079_production_human_signoff_git_writes": "NOT_EXECUTED",
    })
    print("Entry evidence saved; 340 accepted artifacts and 1497 accepted product source hashes PASS; entry BLOCKED.")


def mappings():
    common = "Source validity PASS: 1497 final accepted product hashes and 340 manifest artifact hashes; original RV IDs retained; no CEP runtime promotion"
    rows = []
    data = [
        ("AC-1", "Audit19 static fixes followed by runtime cross-browser/accessibility evidence", "RV-EV-058/059; RV-EV-060 completed cells; RV-EV-061/062/063/065", "Own ESS/Knowledge; representative responsive cells; Projects/Quality/platform/positive portal; F-135 desktop/mobile keyboard", "Eligible approved cross-browser/accessibility target outcome with exact runtime identities", "UTV", "PARTIAL"),
        ("AC-2", "Exact scenario environment and version defined", "Wave D/E EVIDENCE_RECORDS; BROWSER_METADATA; F-135 ENTRY and SOURCE_INTEGRITY", "1440x900 / 1024x768 / 390x844 audit CSS viewports; existing canonical persona shapes/routes; F-135 desktop/mobile only", "CEP-approved supported matrix and full exact browser versions; current source hash already valid", "UTV", "PARTIAL"),
        ("AC-3", "Scenario actually executed not inferred", "RV-EV-058..065 original executed audit records", "Authenticated browser captures and controls; F-135 22 keyboard assertions; no CEP execution", "Actual permitted CEP execution after entry gates clear", "UTV", "PARTIAL"),
        ("AC-4", "Measured artifacts timestamps explicit pass/fail retained", "Three accepted MANIFEST.json files; original EVIDENCE_RECORDS and keyboard/capture artifacts", "340/340 hashes PASS; original explicit PASS/FAIL and timestamps retained", "Actual CEP runtime measurement artifacts; entry hash checks cannot replace them", "UTV", "PARTIAL"),
        ("AC-5", "Failed scenario stays open evidence gap", "F-135 FINAL_RECONCILIATION; historical RV-EV-064; baseline regression attribution", "Prior F-135 failure superseded only by RV-EV-065; other findings/debt preserved", "Scenario acceptance remains unexecuted at gate stop; recordkeeping control PASS", "UTV", "PASS"),
        ("AC-6", "UTV stays until execution evidence exists", "Original browser metadata limitations; current CEP entry decision", "No cross-browser exact-build or CEP runtime PASS; UTV explicit", "Required runtime UTV unchanged; recordkeeping control PASS", "UTV", "PASS"),
        ("DoD-1", "Target outcome exactly in approved scope", "Existing remediated sources and accepted audit observations", "Product source unchanged since accepted final state", "Eligible CEP target outcome execution", "UTV", "PARTIAL"),
        ("DoD-2", "Target environment/scenario documented", "UIUX matrix; evidence records; current entry evidence", "Existing representative personas/routes/viewports, Development/source identity", "Complete CEP-supported cross-browser/device/accessibility matrix and exact runtime versions", "PARTIAL", "PARTIAL"),
        ("DoD-3", "Execution procedure prepared", "Canonical CEP prompt; UIUX playbook; execution manifest", "Entry stop, output format and resume sequence documented", "Bind procedure to EXT-0024 approved matrix and eligible scope", "PARTIAL", "PARTIAL"),
        ("DoD-4", "Evidence/pass-fail record format defined", "Original RV record format; CEP-078 mappings/manifests/report", "Explicit result, source, timestamp and limitation fields", "No format gap; format is not runtime evidence", "PASS", "PASS"),
        ("DoD-5", "Actual verification execution evidence produced by CEP", "None; no retrospective promotion", "Runtime NOT_STARTED", "Actual CEP verification evidence after entry clears", "UTV", "UTV"),
    ]
    for criterion, requirement, existing, scope, gap, result, control in data:
        rows.append({"criterion": criterion, "requirement": requirement, "existing_evidence": existing, "existing_scope": scope, "source_validity": common, "reuse_disposition": "REFERENCE_AND_GAP_ANALYSIS_ONLY; no relabeling or duplicate rerun", "remaining_gap": gap, "result": result, "supporting_control_result": control, "evidence_ids": "CEP-078-EV-001;CEP-078-EV-002"})
    dump_csv("ACCEPTANCE_MAPPING.csv", list(rows[0]), rows)


def reconcile():
    saved = json.loads((OUT / "CEP-078_ENTRY_REVIEW.json").read_text(encoding="utf-8"))
    original = REG.read_bytes()
    assert hashlib.sha256(original).hexdigest() == saved["registry_before"]["sha256"], "Concurrent Registry change: stop"
    text = original.decode("utf-8").replace("\r\n", "\n")
    records = blocks(text)
    mappings()
    replacement = """    title: Browser, accessibility and responsive runtime verification
    phase: VERIFICATION_UAT
    dependency_status: MANDATORY_CEP003_CEP017_COMPLETE_ENTRY_GATE_AND_EXT0024_UNSATISFIED
    eligibility_status: BLOCKED_GATE07_AND_UNVERIFIED_EXT0024
    authorization:
      status: AUTHORIZED_FOR_ENTRY_AND_CONDITIONAL_NON_PRODUCTION_VERIFICATION
      authorization_id: null
      source: Human request 2026-10-23 to continue through CEP078 supported terminal reconciliation; canonical entry conditions not waived
    execution:
      status: NOT_STARTED
      lifecycle: BLOCKED_BEFORE_ENTRY
      advisor_review: NOT_REQUIRED_CURRENT_GOVERNANCE
    acceptance:
      passed: null
      total: 6
      status: UNEXECUTED_ENTRY_BLOCKED
    dod: NOT_MET_ENTRY_BLOCKED
    blockers:
    - CEP-078-FINDING-001 / BLOCKER-DEPENDENCY / GATE-07 NOT_READY; current full or capability-scoped convergence clearance not established
    - CEP-078-FINDING-002 / BLOCKER-EXTERNAL / EXT-0024 approved supported browser-device-viewport-accessibility matrix and exact runtime build-version not established
    remaining_utv:
    - Canonical CEP078 cross-browser-responsive-accessibility runtime outcome and six scenario acceptance criteria remain unexecuted
    - Exact full browser versions and approved CEP matrix; original audit version and representative-equivalence limitations retained
    - Any approved tablet keyboard or semantic-state coverage not directly evidenced; no full WCAG-screen-reader-all-route claim
    completion_report:
      path: docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md
      evidence_presence: ENTRY_REVIEW_AND_REUSE_MAPPING_ONLY_NO_CEP_RUNTIME_EXECUTION
    git:
      committed: false
      commit_sha: null
      pushed: false
      merged_to_main: false
      remote_main_evidence: UNCOMMITTED_ENTRY_REVIEW_ONLY
    last_execution:
      branch: null
      sha: null
    updated_at: '2026-10-23'
    entry_review:
      evidence: docs/governance/cep/evidence/CEP-078_ENTRY_REVIEW.json
      acceptance_mapping: docs/governance/cep/evidence/CEP-078_ACCEPTANCE_MAPPING.csv
      branch: main
      head: 43ac319c6e73e48ca9626461b73987922c498ec3
      result: BLOCKED_BEFORE_ENTRY
      canonical_report_verdict: EXECUTION FAILED
      verdict_semantics: Entry requirements prevent execution; not a runtime scenario test failure
      implementation_prerequisites: CEP003_AND_CEP017_AVAILABLE
      gate07: NOT_READY_RETAINED_NO_GLOBAL_OR_SCOPED_PASS_INFERRED
      ext0024: NOT_ESTABLISHED
      accepted_artifact_hashes: 340_PASS_0_MISMATCH
      accepted_product_source_hashes: 1497_PASS_0_MISMATCH
      verification_execution: NOT_STARTED
    history:
    - date: '2026-10-23'
      status: ENTRY_REVIEW_BLOCKED
      reason: Current Human CEP078-only non-production request reviewed at main43ac319 with accepted dirty UIUX work. Prompt identity, prerequisite implementation and340 accepted artifacts plus1497 final source hashes verified. GATE07 remains NOT_READY; EXT0024 matrix-exact-version readiness unproved. Accepted Waves and RV025 PASS retained under original RV IDs; no retrospective CEP runtime promotion. AC unexecuted, DoD not met; final report uses EXECUTION FAILED for blocked entry, not a runtime failure. No product-data-migration-browser-Git writes, CEP079, Production or Human Sign-off.
"""
    text = text.replace("  CEP-078:\n" + records["CEP-078"], "  CEP-078:\n" + replacement, 1)
    new_records = blocks(text)
    current = {k: v for k, v in new_records.items() if int(k[-3:]) <= 79}
    execution = {k: re.search(r"    execution:\n      status: (\S+)", v).group(1) for k, v in current.items()}
    counts = Counter(execution.values())
    blocked = sum(s == "NOT_STARTED" and bool(re.search(r"    eligibility_status: BLOCKED|      lifecycle: BLOCKED", current[k])) for k, s in execution.items())
    values = {"execution_state_complete": counts["COMPLETE"], "in_progress": counts["IN_PROGRESS"], "blocked_current": blocked, "partial_current": counts["PARTIAL"], "failed_current": counts["FAILED"], "not_started_other_current_governed": counts["NOT_STARTED"] - blocked}
    summary = section(text, "summary")
    for key, value in values.items():
        summary, n = re.subn(r"^  " + key + r": .*?$", f"  {key}: {value}", summary, count=1, flags=re.M)
        assert n == 1
    summary = re.sub(r"^  last_updated: .*?$", "  last_updated: '2026-10-23'", summary, count=1, flags=re.M)
    text = text.replace("summary:\n" + section(text, "summary"), "summary:\n" + summary, 1)
    frontier = section(text, "execution_frontier")
    updates = {
        "current_session_continuation": "STOP_CEP078_BLOCKED_AFTER_FINAL_RECONCILIATION",
        "next_candidate_full_entry_eligibility": "CEP078_ENTRY_REVIEW_COMPLETE_BLOCKED_GATE07_EXT0024",
        "boundary_reason": "Current Human scope is CEP078 only through supported terminal state; entry blocked, no CEP079 or Production authority",
        "resume_cep_after_blocker_resolution": "CEP-078",
        "independent_candidates_entry_status": "NOT_EXECUTED_OUTSIDE_CURRENT_CEP078_ONLY_SCOPE",
        "current_session_cep_range": "CEP078_ONLY_DEVELOPMENT_NON_PRODUCTION",
        "excluded_this_session": "CEP079;ALL_OTHER_CEP_EXECUTION;Post-V1;Production;Human_Signoff;Certification;Git_WRITES",
    }
    for key, value in updates.items():
        frontier, n = re.subn(r"^  " + key + r": .*?$", "  " + key + ": " + json.dumps(value), frontier, count=1, flags=re.M)
        assert n == 1
    text = text.replace("execution_frontier:\n" + section(text, "execution_frontier"), "execution_frontier:\n" + frontier, 1)
    repository = section(text, "repository_state")
    for key, value in {"last_reconciled_head": saved["repository"]["head"], "origin_main": saved["repository"]["origin_main"], "last_reconciled_at": "2026-10-23", "metadata_boundary": "Current branch-HEAD-local-origin grounding for CEP078 entry review only;582e418 integration checkpoint remains historical. No new CEP execution or Git integration claimed; local origin ref freshness not remotely queried."}.items():
        repository, n = re.subn(r"^  " + key + r": .*?$", "  " + key + ": " + json.dumps(value), repository, count=1, flags=re.M)
        assert n == 1
    text = text.replace("repository_state:\n" + section(text, "repository_state"), "repository_state:\n" + repository, 1)
    for key, value in saved["registry_before"]["other_cep_hashes"].items():
        assert digest(blocks(text)[key]) == value
    for key, value in saved["registry_before"]["untouched_section_hashes"].items():
        assert digest(section(text, key)) == value
    ending = "\r\n" if b"\r\n" in original else "\n"
    REG.write_bytes(text.replace("\n", ending).encode("utf-8"))
    changed = ["CEP_EXECUTION_REGISTRY.yaml", "docs/governance/cep/manifests/CEP-078_EXECUTION_MANIFEST.md", "docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md"] + ["docs/governance/cep/evidence/CEP-078_" + n for n in ("RECONCILE.py", "ENTRY_REVIEW.json", "ACCEPTANCE_MAPPING.csv", "EVIDENCE_MANIFEST.csv", "CHANGE_MANIFEST.csv", "CLOSEOUT_CHECK.json")]
    dump_csv("CHANGE_MANIFEST.csv", ["path", "change_type", "purpose"], [{"path": p, "change_type": "MODIFIED" if p == "CEP_EXECUTION_REGISTRY.yaml" else "NEW", "purpose": "Bounded blocked-entry reconciliation and evidence only; no product or historical evidence change"} for p in changed])
    print(json.dumps({"registry_reconciled": True, "execution_status": "NOT_STARTED", "lifecycle": "BLOCKED_BEFORE_ENTRY", "summary": values, "AC": "6 UNEXECUTED", "DoD": "NOT_MET_ENTRY_BLOCKED"}))


def check():
    saved = json.loads((OUT / "CEP-078_ENTRY_REVIEW.json").read_text(encoding="utf-8"))
    text = REG.read_text(encoding="utf-8")
    records = blocks(text)
    assert len(records) == 86
    assert all(digest(records[k]) == v for k, v in saved["registry_before"]["other_cep_hashes"].items())
    assert all(digest(section(text, k)) == v for k, v in saved["registry_before"]["untouched_section_hashes"].items())
    assert git("rev-parse", "HEAD") == saved["repository"]["head"]
    assert sha(ROOT / ".git/index") == saved["repository"]["index_sha256"]
    assert all((ROOT / k).is_file() and sha(ROOT / k) == v for k, v in saved["product_hashes"].items())
    assert all(sha(ROOT / k) == v for k, v in saved["uiux_pointer_hashes"].items())
    assert all(sha(ROOT / k) == v for k, v in saved["local_authority_hashes"].items())
    for folder, data in saved["accepted_evidence_integrity"].items():
        assert sha(UI / folder / "MANIFEST.json") == data["manifest_sha256"]
    mapping = list(csv.DictReader((OUT / "CEP-078_ACCEPTANCE_MAPPING.csv").open(encoding="utf-8")))
    assert len(mapping) == 11
    assert {r["criterion"] for r in mapping} == {"AC-" + str(i) for i in range(1, 7)} | {"DoD-" + str(i) for i in range(1, 6)}
    assert all(r["result"] == "UTV" for r in mapping if r["criterion"].startswith("AC-"))
    assert "      status: NOT_STARTED\n      lifecycle: BLOCKED_BEFORE_ENTRY\n" in records["CEP-078"]
    assert "      status: UNEXECUTED_ENTRY_BLOCKED\n" in records["CEP-078"]
    assert "    dod: NOT_MET_ENTRY_BLOCKED\n" in records["CEP-078"]
    states = Counter(re.search(r"    execution:\n      status: (\S+)", v).group(1) for k, v in records.items() if int(k[-3:]) <= 79)
    assert states == {"COMPLETE": 68, "PARTIAL": 3, "NOT_STARTED": 8}, states
    assert "  blocked_current: 2\n" in section(text, "summary")
    assert "  not_started_other_current_governed: 6\n" in section(text, "summary")
    assert 'STOP_CEP078_BLOCKED_AFTER_FINAL_RECONCILIATION' in section(text, "execution_frontier")
    allowed = {r["path"] for r in csv.DictReader((OUT / "CEP-078_CHANGE_MANIFEST.csv").open(encoding="utf-8"))}
    # Directory-collapsed original status is not used as an invented per-file diff.
    assert all(p.startswith("docs/governance/cep/") or p == "CEP_EXECUTION_REGISTRY.yaml" for p in allowed)
    reference_sources = [
        ("001", "docs/governance/cep/evidence/CEP-078_ENTRY_REVIEW.json", "Measured entry review, source recovery and accepted-evidence integrity; not CEP browser execution"),
        ("002", "docs/governance/cep/evidence/CEP-078_ACCEPTANCE_MAPPING.csv", "All 6 AC and 5 scoped DoD evidence-to-gap rows"),
        ("003", "docs/governance/cep/evidence/CEP-078_CLOSEOUT_CHECK.json", "Bounded documentation and preservation checks; not runtime PASS"),
        ("004", "docs/governance/cep/manifests/CEP-078_EXECUTION_MANIFEST.md", "Entry and actual authorized touch set"),
        ("005", "docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md", "Blocked final result and remaining UTV"),
        ("006", "docs/governance/uiux/wave_de_fixture_closure/MANIFEST.json", "Original RV provenance retained; 211 artifacts checked at entry"),
        ("007", "docs/governance/uiux/wave_e_targeted_closure/MANIFEST.json", "Original RV provenance retained; 80 artifacts checked at entry"),
        ("008", "docs/governance/uiux/f135_closure/MANIFEST.json", "Original RV provenance retained; 49 artifacts checked at entry"),
        ("009", "docs/governance/cep/evidence/CEP-078_RECONCILE.py", "Standard-library-only reproducible entry/reconciliation/check procedure"),
        ("010", "docs/governance/cep/evidence/CEP-078_CHANGE_MANIFEST.csv", "Bounded new files and Registry mutation inventory"),
    ]
    # Verify Markdown links in the two new documents; all targets must be real files.
    refs = []
    for relative in (reference_sources[3][1], reference_sources[4][1]):
        p = ROOT / relative
        for target in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
            destination = (p.parent / target.split("#")[0]).resolve()
            if destination.name in ("CEP-078_CLOSEOUT_CHECK.json", "CEP-078_EVIDENCE_MANIFEST.csv"):
                continue  # Produced immediately below.
            assert destination.is_file(), str(destination)
            refs.append(str(destination.relative_to(ROOT)))
    whitespace = subprocess.run(["git", "diff", "--check", "--", "CEP_EXECUTION_REGISTRY.yaml"], cwd=ROOT, capture_output=True, text=True)
    assert whitespace.returncode == 0, whitespace.stdout + whitespace.stderr
    new_files = [ROOT / p for p in allowed if p != "CEP_EXECUTION_REGISTRY.yaml" and (ROOT / p).is_file()]
    bad_space = [(p.relative_to(ROOT).as_posix(), i) for p in new_files if p.suffix in (".md", ".py") for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if line.rstrip() != line]
    assert not bad_space, bad_space
    result = {
        "recorded_at": datetime.now(timezone(timedelta(hours=3, minutes=30))).isoformat(),
        "result": "PASS_DOCUMENTATION_EVIDENCE_INTEGRITY_ONLY",
        "application_and_browser_runtime": "NOT_EXECUTED_ENTRY_BLOCKED",
        "accepted_entry_artifact_checks": {k: v["checked_artifacts"] for k, v in saved["accepted_evidence_integrity"].items()},
        "accepted_product_source_hashes_at_entry": saved["accepted_source_state"],
        "product_files_preserved_since_entry": len(saved["product_hashes"]),
        "uiux_pointer_files_preserved": len(saved["uiux_pointer_hashes"]),
        "other_cep_records_unchanged": 85, "gates_and_historical_sections_unchanged": True,
        "head_and_index_unchanged": True, "canonical_sources_and_roadmap_unchanged": True,
        "acceptance_mapping_rows": 11, "canonical_runtime_ac_proved": 0,
        "registry_summary": {"current_governed": 79, "complete": 68, "partial": 3, "blocked_before_entry": 2, "other_not_started": 6, "post_v1_deferred": 7},
        "registry_state": "NOT_STARTED / BLOCKED_BEFORE_ENTRY; acceptance UNEXECUTED; DoD NOT_MET_ENTRY_BLOCKED",
        "report_verdict": "EXECUTION FAILED; entry failure, no runtime scenario failure claim",
        "gate07": "NOT_READY", "gate08": "NOT_PASSED", "cep079": "UNCHANGED_NOT_STARTED",
        "references_checked": refs, "registry_diff_whitespace": "PASS", "new_document_source_whitespace": "PASS",
        "yaml_check_method": "Bounded scalar/block edits; 86 record extraction and untouched-section hashes; no full YAML parser/conformance claim",
        "new_evidence_manifest": "SHA256 for all listed actual files; excludes its own hash to avoid circularity",
        "production_human_signoff_git_writes": "NOT_EXECUTED", "stop": "CEP078_FINAL_RECONCILIATION_COMPLETE_BLOCKED",
    }
    save("CLOSEOUT_CHECK.json", result)
    manifest = [{"evidence_id": "CEP-078-EV-" + number, "path": path, "sha256": sha(ROOT / path), "evidence_kind": description, "result": "RETAINED_OR_REVIEWED_NO_CEP_RUNTIME_PASS"} for number, path, description in reference_sources]
    dump_csv("EVIDENCE_MANIFEST.csv", list(manifest[0]), manifest)
    for row in csv.DictReader((OUT / "CEP-078_EVIDENCE_MANIFEST.csv").open(encoding="utf-8")):
        assert sha(ROOT / row["path"]) == row["sha256"]
    print(json.dumps({"closeout": result["result"], "records": 86, "other_ceps_preserved": 85, "accepted_artifacts": 340, "accepted_sources": 1497, "runtime_ac_proved": 0, "state": "BLOCKED_BEFORE_ENTRY", "git_writes": "NOT_EXECUTED"}))


if __name__ == "__main__":
    {"entry": entry, "reconcile": reconcile, "check": check}[sys.argv[1]]()
