"""Guarded CEP079 completion from actual retained runtime evidence; no Git writes."""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent
HEAD = "5a0a81dafbdd4d6e2142273a87efa45fc9a2c919"
PROMPT_HASH = "c02eb0bf068da7a036cf20776fd212be9d5146e994a9e6364ad4ddff9f6fb342"
now = datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


assert git("branch", "--show-current") == "main"
assert git("rev-parse", "HEAD") == git("rev-parse", "refs/remotes/origin/main") == HEAD
assert hashlib.sha256((ROOT / "docs/governance/cep/PROMPTS/CEP-079_EXECUTION_PROMPT.md").read_bytes()).hexdigest() == PROMPT_HASH
matrix_path = OUT / "44_CASE_READINESS_MATRIX.json"
matrix = read(matrix_path)
rows = matrix["rows"]
assert len(rows) == 44 and all(r["uat_execution_result"] == "PASS" for r in rows)
assert sum(len(r["upstream_imb_ids"]) for r in rows) == 48
for number in range(1, 45):
    runtime = read(OUT / f"UAT_CASE_{number:03d}_RUNTIME.json")
    assert runtime.get("scenario_result", runtime.get("result")) == "PASS", number
last = read(OUT / "UAT_CASE_044_RUNTIME.json")
assert last["finding018"]["result"] == last["finding019"]["result"] == "FIXED"
assert last["scanner_duty_at_closeout"]["effective"] is False
assert last["partner"]["status"] == "approved"
assert all(x["status"] == "closed" for x in last["focused_scoped_action_reruns"])
hse = read(OUT / "HSE_AFFECTED_VALIDATION.json")
assert hse["new_scope_tests"]["pass"] == 7
assert hse["affected_existing_tests_final_state"]["run"] == 4
assert not hse["affected_existing_tests_final_state"]["failures"]
assert not hse["affected_existing_tests_final_state"]["errors"]
assert read(OUT / "COMPLIANCE_AFFECTED_VALIDATION.json")["scoped_read_tests"]["pass"] == 2

# Keep stable identifiers and prove already-passed evidence has not changed.
evidence_path = ROOT / "docs/governance/cep/evidence/CEP-079_EVIDENCE_MANIFEST.csv"
with evidence_path.open(encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    evidence_fields, evidence_rows = reader.fieldnames, list(reader)
preserved = []
for row in evidence_rows:
    path = ROOT / row["path"]
    if path.name.startswith("UAT_CASE_") and int(path.name.split("_")[2]) <= 41:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], path
        preserved.append(row["evidence_id"])

# Exact canonical exit-gate recovery through the already-qualified source manifest.
inputs = read(OUT / "CANONICAL_INPUTS.json")
source = next(x for x in inputs["sources"] if x["member"] == "BONIRA_IMPLEMENTATION_GATE_REGISTER.csv")
archive = Path(source["archive"])
assert hashlib.sha256(archive.read_bytes()).hexdigest() == source["sha256"]
with zipfile.ZipFile(archive) as z:
    name = next(x for x in z.namelist() if x.endswith(source["member"]))
    raw = z.read(name)
assert hashlib.sha256(raw).hexdigest() == source["member_sha256"]
gate = next(x for x in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))) if x["Gate ID"] == "GATE-10")
assert gate["Human Sign-off?"] == "NO" and gate["Required IMB IDs"] == "IMB-0110"
write(OUT / "GATE10_COMPLETION_EVALUATION.json", {
    "at": now, "source": source, "canonical_contract": gate, "result": "PASS",
    "scenario_results": "44/44 actually executed PASS;48/48 mappings satisfied",
    "environment": "Isolated local Development Django/PostgreSQL; actual Chrome ordinary UI",
    "version": {"branch": "main", "head": HEAD, "local_origin_main": HEAD,
                "working_tree": "Retained and authorized uncommitted corrections; exact files hashed in evidence/change manifests"},
    "unresolved_failures": 0, "ext0025": "READY_RETAINED_RUNTIME_CORROBORATED",
    "exhaustive_claim": False, "human_signoff": "NOT_EXECUTED",
    "production_certification": "NOT_EXECUTED", "next_cep": "STOP_BY_HUMAN_SCOPE",
})

summary = matrix["uat_execution_summary"]
summary.update(updated_at=now, attempted=44, fully_executed=44, terminal_results=44,
               **{"pass": 44, "fail": 0, "blocked": 0, "not_executed": 0},
               satisfied_mappings=48, blocked_mappings=0, unexecuted_mappings=0,
               defects_discovered=19, defects_fixed=19, product_defects_discovered=13,
               product_defects_fixed=13, configuration_authority_defects_discovered=6,
               unresolved_uat_blocking_defects=0, unresolved_product_defects=0,
               environment_blockers=0, blocker=None, execution_status="COMPLETE",
               acceptance="6_OF_6_PASS", scoped_dod="MET", gate10="PASS",
               prior_environment_blocker="ENV001/ENV002/ENV003 RESOLVED; actual Browser navigation and upload/download corroborated")
write(matrix_path, matrix)

registry = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
original = registry.read_text(encoding="utf-8")


def other_ceps(text):
    return {k: v for k, v in re.findall(
        r"^  (CEP-\d{3}):\n(.*?)(?=^  CEP-\d{3}:\n|^authority_scope:)", text, re.M | re.S)
        if k != "CEP-079"}


before = other_ceps(original)
a, b = original.index("  CEP-079:\n"), original.index("  CEP-080:\n")
section = original[a:b]
section = section.replace("    execution:\n      status: PARTIAL\n", "    execution:\n      status: COMPLETE\n")
section = re.sub(r"^      lifecycle: .*", "      lifecycle: CLOSED_VERIFIED_DEVELOPMENT_REPRESENTATIVE_UAT", section, count=1, flags=re.M)
section = section.replace("      passed: 4\n      total: 6\n      status: 4_PASS_AC1_NOT_MET_AC3_PARTIAL", "      passed: 6\n      total: 6\n      status: PASS")
section = section.replace("    dod: NOT_MET", "    dod: MET")
x, y = section.index("    blockers:"), section.index("    completion_report:")
section = section[:x] + "    blockers: []\n    remaining_utv: []\n" + section[y:]
for key in ("attempted", "fully_executed", "pass", "fail", "blocked", "not_executed",
            "defects_discovered", "defects_fixed", "product_defects_discovered",
            "product_defects_fixed", "configuration_authority_defects_discovered"):
    section = re.sub(r"^      " + key + r": .*", f"      {key}: {summary[key]}", section, flags=re.M)
section = re.sub(r"^      coverage: .*", "      coverage: 48_OF_48_SATISFIED_0_BLOCKED_0_NOT_EXECUTED", section, flags=re.M)
section = re.sub(r"^      unresolved_environment_blockers: .*", "      unresolved_environment_blockers: 0", section, flags=re.M)
section = re.sub(r"^      focused_validation: .*", "      focused_validation: RETAINED26_TIMEKEEPING6_DOCUMENTS9_HSE11_COMPLIANCE2_PASS_RUFF_PASS_DJANGO0;FIVE_ATTRIBUTED_LEGACY_FIXTURE_ERRORS_NO_BROAD_PASS", section, flags=re.M)
history = (
    "    - date: '2026-10-25'\n      status: COMPLETE\n"
    "      reason: All44 representative cases actually executed PASS;48of48 mappings satisfied;19findings fixed;0unresolved blockers;AC6of6PASS;scopedDoDMET. GATE10 objective PASS from verified canonical gate contract. Human Sign-off and Production Certification NOT_EXECUTED. Entry PASS retained; no other CEP or Git writes; STOP by Human scope.\n"
    "      evidence: docs/governance/cep/evidence/CEP-079_ENTRY_PREPARATION_01/GATE10_COMPLETION_EVALUATION.json\n"
)
section = section.replace("    entry_preparation:\n", history + "    entry_preparation:\n", 1)
section += (
    "      scope_limitations:\n"
    "      - Representative44 cases only; no acceptance claim for all608 journeys.\n"
    "      - Unexecuted exhaustive performance/concurrency and browser/accessibility combinations remain UTV outside this completed scope.\n"
    "      - Production acceptance, certification and Human Sign-off NOT_EXECUTED; no downstream financial activation inferred.\n"
)
source_text = original[:a] + section + original[b:]
assert "  GATE-10:\n" not in source_text
gate_block = (
    "  GATE-10:\n    status: PASS\n    source: OBJECTIVE_CANONICAL_COMPLETION_EVALUATION\n"
    "    human_signoff_required: false\n    evaluated_at: '2026-10-25'\n"
    "    required_imb_status:\n      IMB-0110: COMPLETE_REPRESENTATIVE44_ACTUAL_RUNTIME\n"
    "    ext0025: READY\n"
    "    evidence: docs/governance/cep/evidence/CEP-079_ENTRY_PREPARATION_01/GATE10_COMPLETION_EVALUATION.json\n"
    "    note: All44 representative cases PASS with environment/version identity;48mappings satisfied;0unresolved failures. No exhaustive claim, Human Sign-off, Production Certification or next-CEP execution.\n"
)
source_text = source_text.replace("authorization_batches:\n", gate_block + "authorization_batches:\n", 1)
source_text = re.sub(r"^  execution_state_complete: .*", "  execution_state_complete: 69", source_text, flags=re.M)
source_text = re.sub(r"^  partial_current: .*", "  partial_current: 4", source_text, flags=re.M)
for key, value in {
    "current_session_continuation": "STOP_AFTER_CEP079_COMPLETE_BY_HUMAN_SCOPE",
    "next_candidate_full_entry_eligibility": "NOT_EVALUATED_OTHER_CEPS_EXCLUDED_BY_HUMAN",
    "boundary_reason": "CEP079_COMPLETE_44PASS_48MAPPINGS_AC6OF6_DODMET_GATE10PASS;STOP_BY_HUMAN_SCOPE_NO_OTHER_CEP",
    "resume_cep_after_blocker_resolution": "null",
}.items():
    source_text = re.sub(r"^  " + key + r": .*", "  " + key + ": " + value, source_text, flags=re.M)
# Remove the completed package from frontier candidate lists only.
frontier_at = source_text.index("execution_frontier:\n")
source_text = source_text[:frontier_at] + source_text[frontier_at:].replace("  - CEP-079\n", "")
assert len(before) == 85 and before == other_ceps(source_text)
assert len(re.findall(r"^    execution:\n      status: COMPLETE$", source_text, re.M)) == 69
assert len(re.findall(r"^    execution:\n      status: PARTIAL$", source_text, re.M)) == 4
registry.write_text(source_text, encoding="utf-8")

manifest = ROOT / "docs/governance/cep/manifests/CEP-079_EXECUTION_MANIFEST.md"
with manifest.open("a", encoding="utf-8") as f:
    f.write(f"""
## Final continuation and completion — {now}

Cases042..044 PASS after actual Browser continuation; all44 executed PASS/FAIL0/BLOCKED0/NOT_EXECUTED0;48of48 mappings satisfied. Findings017..019 fixed; total19corrected (13product,6configuration/authority),0unresolved. Case042 actual approved JPEG upload, retained v1/v2, project/contract links, quarantined403, actual Defender scans/audited assessments, current/v1 exact-hash ordinary downloads, foreign and sensitive denial. Five-minute existing synthetic platform-operations duty expired; history preserved; no independent scanner-approval claim. Case043 ordinary operational Equipment usage and separate non-posting Fixed Asset candidate using exact approved facts; no asset transactions/depreciation/cost allocation.

Finding018 final touch includes both subject loaders AND scoped transition entry checks in apps/safety/workflow.py and apps/quality/workflow.py; authoritative project/site checks retained. Original Project Manager create/readback and new scoped-action Safety/Quality reruns closed after separate record approval. Seven focused tests and four final affected existing tests PASS. Finding019 actual native scoped Compliance403 plus missing ordinary entry: templates/safety/list.html,templates/quality/list.html,apps/organizations/context_processors.py,apps/compliance/views.py,apps/compliance/services.py and new apps/compliance/test_cep079_scope.py. Narrow navigation availability and coarse scoped read admission precede existing object filters; no global permission-namespace expansion or organization-scope grant. Two positive/tenant/scope/inactive/permission tests PASS; actual PM Browser entry/list/detail PASS. Existing3Compliance tests fail at unchanged create_template permission setup before corrected reads; function matches HEAD; attribution retained, no broad PASS.

044 new pinned QA inspection passed; Finding/NCR/CAPA closed using independent verification and distinct configured closer. Exact published Human-approved template, safe evidence and prior prepared draft preserved; automatic Critical-rule evaluator not asserted. New Partner qualification uses existing approved requirement/profile/evidence, independent tenant-admin approval, ordinary organization-custodian workspace readback as029; primary PM project authority unchanged. Advanced partner-performance excluded. Native lifecycle facts corroborated by ordinary Browser owning-module readback; no hidden-URL navigation claim.

Validation retained26 + Timekeeping6 + Documents9 + HSE11 + Compliance2 focused checks PASS (54 across retained runs); Ruff check/format PASS, Django0issues, git diff --check PASS. Two Case024 legacy fixture failures and three Compliance setup errors attributed; Document combined-run connection errors were rerun separately PASS. No broad/full-suite certification. Previously passed001..041 case artifacts ({len(preserved)}) match retained manifest hashes. Approved035leave remains0.25day reserved; no occurrence/consumption inferred.

AC1..6PASS; scopedDoDMET. Canonical GATE10 contract recovered only from already-qualified source archive and exact member hash; objective PASS recorded with all44actual results/environment/version. Entry PASS/GATE09PASS/EXT0025READY retained without reassessment. No schema changes/Development migrations or Git writes. Other85 CEP records byte-identical; current program totals69COMPLETE/4PARTIAL/13NOT_STARTED; remote-main historical verified68 remains unchanged. STOP at CEP079 completion; no other CEP, Production acceptance/certification, Human Sign-off or exhaustive608journey claim.
""")

report_path = ROOT / "docs/governance/cep/reports/CEP-079_COMPLETION_REPORT.md"
previous = report_path.read_text(encoding="utf-8")
report_path.write_text(f"""# CEP-079 Completion Report

**COMPLETE — representative UAT; GATE-10 PASS.**

As of {now}: **44/44 executed; PASS44 / FAIL0 / BLOCKED0 / NOT_EXECUTED0. All48 Scenario→IMB mappings satisfied. AC6/6PASS; scopedDoDMET.** All19 discovered defects corrected (13product,6configuration/authority);0unresolved UAT blockers or environment blockers. Cases001..035 retained;036..044 continued in canonical order. Earlier blocked/partial observations below remain historical evidence.

Version/environment: `main` HEAD and local `origin/main` `{HEAD}`; remote freshness not queried. Canonical prompt SHA256 `{PROMPT_HASH}` verified. Local Development Django/PostgreSQL and actual Chrome ordinary UI; authorized uncommitted corrections identified in change/evidence manifests. Inherited dirty work preserved. Entry PASS/GATE09PASS/EXT0025READY retained without reassessment.

036 validates ordinary120minute Timekeeping submission, context denials and independent approval/nonfinancial allocation.037..038 validate synthetic Payroll calculation, independent finalization, equal-opposite reversal, explicit correction/replacement, immutable payslips/digests and a proposal-only handoff.039 validates registered declarative template publication/version/retirement in an isolated synthetic project.040 records actual1440/1024/390 Chrome RTL/layout/keyboard/dependent-form/Jalali/Persian-validation observations.041 records scoped/foreign/admin denials, maker approval403, unchanged protected role state and independent approval.

042 uses the same preserved Browser form after Human enabled local file access: actual synthetic upload, two retained versions, project/contract links, quarantine denial, actual Defender scans with audited clean assessments, ordinary current/v1 exact-hash downloads and foreign/sensitive access denials. Expired scanner-duty history is preserved; five-minute temporary duty is no longer effective. Actual native assignment used existing single-Superuser bootstrap; no independent scanner-approval claim.043 separates operational Equipment usage from non-posting Financial Fixed Asset candidate, using exact approved class/book/date/life/residual/basis; no capitalization, asset transaction, depreciation or cost allocation.

044 creates Safety and Quality records through ordinary PM forms and verifies closure through owning-module UI. Finding018 corrects scoped subject-loader and transition-entry checks; fresh scoped PM action reruns close with independent record approval. Finding019 provides permission-gated ordinary Compliance entry and correct scoped list/detail reads. A new source-pinned QA inspection passes; Finding/NCR/CAPA close with independent verifier and configured distinct closer. The original prepared draft and published approved template/hash remain unchanged; automatic Critical-rule evaluation is not claimed. New Partner qualification uses the existing governed source and exact evidence, independent tenant-admin approval and ordinary organization-master custodian readback. PM scope is unchanged; advanced partner-performance stays excluded.

The three corrections since035 are Document form target scoping (017), Safety/Quality scoped workflow entry (018), and Compliance navigation/scoped read (019). Earlier16 corrections remain evidenced in retained case records. Organization-level Equipment/Fixed Asset and Partner-master actions use existing authorized custodians as explicitly recorded in043/044; no scope expansion is inferred from the canonical persona label.

Focused validation: prior Billing5,Procurement5,sharedWorkflow3,Materials/Partner8,Inventory5; Timekeeping6; Documents6new+3affected; Safety/Quality7new+4affected; Compliance2new PASS (**54 checks across retained runs**). Final affected HSE4PASS10.566s; new HSE7PASS3.084s; Compliance2PASS1.311s. Ruff check/format PASS; Django0issues; diff check PASS. Two earlier unrelated Case024 fixture failures and three legacy Compliance setup errors remain attributed, with no broad/full-suite PASS claim. The latter fail in unchanged create_template permission setup before corrected reads; exact permission function matches HEAD. Initial Document combined-run connection errors were rerun separately PASS. Previously passed001..041 case artifacts ({len(preserved)}) match retained evidence hashes.

AC1: all44approved representative outcomes have actual post-remediation runtime evidence,48mappings; no exhaustive claim. AC2: exact scenario, environment, source identity and build/dirty version retained. AC3: native workflow execution plus ordinary Browser assertions recorded. AC4: timestamped measured artifacts and explicit terminal results retained. AC5: failures/blockers remain historical, each corrected/dispositioned and actually rerun; no unresolved required assertion. AC6: only executed scope is promoted; unexecuted exhaustive journeys, performance/concurrency and additional browser/accessibility combinations remain UTV outside completed scope. ScopedDoD is met by actual scenario execution and inspectable traceability/evidence, independently of focused test results.

GATE10 PASS follows its exact canonical completion contract: all44 executed, evidence/environment/version captured,0unresolved failures,no exhaustive claim; its source explicitly requires no Human Sign-off. See `GATE10_COMPLETION_EVALUATION.json`. **Human Sign-off, Production acceptance/certification and cutover: NOT_EXECUTED.** No downstream activation or acceptance of all608 journeys. No other CEP or Audits01–20 executed.

Registry, matrix JSON/CSV, acceptance/evidence/change manifests and this report synchronized. Other85 CEP records unchanged; current totals69COMPLETE/4PARTIAL/13NOT_STARTED. Historical remote-main verified count68 remains unchanged because this work is uncommitted. No schema changes/Development migrations or Git add/commit/push/reset/stash/clean. Approved035leave retains0.25day reservation; no occurrence/consumption inferred. **STOP: user-authorized CEP079 completion boundary reached.**

<!-- RETAINED_PREVIOUS_COMPLETION_BOUNDARY -->

{previous}""", encoding="utf-8")

write(OUT / "FINAL_COMPLETION_CHECK.json", {
    "at": now, "result": "PASS", "cases": 44, "pass": 44, "mappings": 48,
    "defects_corrected": 19, "unresolved": 0, "acceptance": "6/6PASS", "scoped_dod": "MET",
    "gate10": "PASS", "head": HEAD, "local_origin_main": HEAD,
    "prior_case_artifacts_hash_preserved": preserved, "other_cep_records_unchanged": 85,
    "program_counts": {"COMPLETE": 69, "PARTIAL": 4, "NOT_STARTED": 13},
    "historical_remote_verified_complete": 68, "schema_changes": False, "git_writes": False,
    "human_signoff": "NOT_EXECUTED", "production_certification": "NOT_EXECUTED",
    "continuation": "STOP_AFTER_CEP079_COMPLETE_BY_HUMAN_SCOPE",
})

known = {r["path"] for r in evidence_rows}
next_id = max(int(r["evidence_id"].split("-")[-1]) for r in evidence_rows) + 1
files = sorted(OUT.glob("UAT_CASE_*")) + [OUT / name for name in (
    "HSE_AFFECTED_VALIDATION.json", "COMPLIANCE_AFFECTED_VALIDATION.json",
    "GATE10_COMPLETION_EVALUATION.json", "FINAL_COMPLETION_CHECK.json", "final_closeout.py", "case042.py",
    "44_CASE_READINESS_MATRIX.csv", "CANONICAL_INPUTS.json")]
files += [ROOT / path for path in (
    "apps/documents/forms.py", "apps/documents/test_cep079_form_scope.py",
    "apps/safety/workflow.py", "apps/quality/workflow.py", "apps/safety/test_cep079_hse_scope.py",
    "apps/compliance/services.py", "apps/compliance/views.py", "apps/compliance/test_cep079_scope.py",
    "apps/organizations/context_processors.py", "templates/safety/list.html", "templates/quality/list.html",
    "docs/governance/cep/reports/CEP-079_COMPLETION_REPORT.md")]
for path in files:
    relative = path.relative_to(ROOT).as_posix()
    if relative not in known:
        evidence_rows.append(dict(evidence_id=f"CEP-079-EV-{next_id:03d}", path=relative,
                                  sha256="", kind="Actual continuation/completion evidence or bounded correction", result="RECORDED"))
        known.add(relative)
        next_id += 1
for row in evidence_rows:
    path = ROOT / row["path"]
    row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.name == "44_CASE_READINESS_MATRIX.json":
        row["result"] = "COMPLETE_44PASS_48MAPPINGS"
    if path.name.startswith("UAT_CASE_"):
        row["result"] = rows[int(path.name.split("_")[2]) - 1]["uat_execution_result"]
with evidence_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=evidence_fields)
    writer.writeheader()
    writer.writerows(evidence_rows)

accept = ROOT / "docs/governance/cep/evidence/CEP-079_ACCEPTANCE_MAPPING.csv"
with accept.open(encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    fields, acceptance_rows = reader.fieldnames, list(reader)
results = [
    "44/44 actual representative cases PASS;48/48 mappings satisfied;0unresolved blockers;no exhaustive claim.",
    "Canonical scenarios, Development runtime, exact build/dirty version and source identities retained.",
    "All44 actually executed;ordinary UI assertions use Browser;native owning services corroborated by Browser readback.",
    "Timestamped measured artifacts, explicit44 terminal PASS results and retained correction/blocker history.",
    "All19 findings corrected and affected assertions rerun;0open required scenario gaps;legacy fixture debt attributed separately.",
    "Only executed representative scope promoted;unexecuted exhaustive/performance/additional browser combinations remain out-of-scope UTV.",
]
assert len(acceptance_rows) == 6
for row, result in zip(acceptance_rows, results):
    row.update(status="PASS", evidence=f"CEP-079-EV-001..{next_id-1:03d}", result=result)
with accept.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(acceptance_rows)

status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True, encoding="utf-8")
with (ROOT / "docs/governance/cep/evidence/CEP-079_CHANGE_MANIFEST.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["path", "change", "purpose"])
    for line in status.splitlines():
        writer.writerow([line[3:], "MODIFIED" if line[:2] != "??" else "ADDED_OR_ADVANCED_EXISTING_UNTRACKED",
                         "Bounded CEP079 correction/validation/evidence; inherited changes preserved; no Git writes"])
print(f"COMPLETE:44PASS/48mappings/AC6of6/DoDMET/GATE10PASS;19corrected;other85CEPs unchanged;{len(evidence_rows)}hashed artifacts;STOP")
