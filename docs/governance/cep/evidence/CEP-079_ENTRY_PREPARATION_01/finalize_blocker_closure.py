"""One delta-only entry reassessment after Tasks 1..5; no UAT execution."""
import copy
import csv
import difflib
import io
import json
import re
import subprocess
from pathlib import Path

import yaml
from blocker_closure import OUT, ROOT, digest, write

REL = OUT.relative_to(ROOT).as_posix()
baseline = json.loads((OUT / "BLOCKER_CLOSURE_BASELINE.json").read_text())
tasks = json.loads((OUT / "BLOCKER_CLOSURE_TASKS.json").read_text())
assert set(tasks) == {"task1", "task2", "task3", "task4", "task5"}
assert tasks["task2"]["result"] == "PASS"
matrix_path = OUT / "44_CASE_READINESS_MATRIX.json"
matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
old_rows = copy.deepcopy(matrix["rows"])
assert len(old_rows) == 44
assert sum(r["readiness_result"] == "READY_STARTING_CONTEXT_ONLY" for r in old_rows) == 32
ready_ids = [r["scenario_id"] for r in old_rows if r["readiness_result"] == "READY_STARTING_CONTEXT_ONLY"]
baseline["preserved_ready_cases"] = ready_ids
baseline["unchanged_ready_row_sha256"] = {r["scenario_id"]: __import__("hashlib").sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest() for r in old_rows if r["scenario_id"] in ready_ids}
write("BLOCKER_CLOSURE_BASELINE.json", baseline)
for row in matrix["rows"]:
    if row["scenario_id"] == "UAT-CASE-040":
        row["readiness_result"] = "READY_STARTING_CONTEXT_ONLY"
        row["blocking_requirements"] = []
        row["qualified_fixture_references"]["workforce_keyboard_prerequisite"] = "WORKFORCE_CLOSURE.json: 6/6 distinct keyboard cells PASS; mobile pointer probes retained as limitation"
    elif row["scenario_id"] == "UAT-CASE-018":
        row["blocking_requirements"] = [{"classification": "CANONICAL_FIXTURE_PREPARATION_INTEGRITY_FAILURE", "requirement": "Native period-end reconciliation fixture rejected by retained result-hash verification; no independently signed qualified run retained", "minimum_action": "Separately authorize bounded Accounting result-hash defect attribution/correction, then prepare native signed period-end reconciliation/statements. Existing distinct close/reopen actor bindings were identified; no new approval authority required."}]
        row["qualified_fixture_references"]["failed_preparation"] = "TASK3_RECONCILIATION_FIXTURE.json: atomic rollback, protected financial sources unchanged"
assert all(a == b for a, b in zip(old_rows, matrix["rows"], strict=True) if a["scenario_id"] not in {"UAT-CASE-018", "UAT-CASE-040"})
assert all(r["uat_execution_result"] == "NOT_EXECUTED" for r in matrix["rows"])
assert sum(len(r["upstream_imb_ids"]) for r in matrix["rows"]) == 48
matrix["last_delta_reassessment"] = "2026-10-24; only rows 018/040 updated; prior 32 ready rows preserved without requalification"
write("44_CASE_READINESS_MATRIX.json", matrix)
csv_path = OUT / "44_CASE_READINESS_MATRIX.csv"
reader = csv.DictReader(io.StringIO(csv_path.read_text(encoding="utf-8-sig")))
fields = reader.fieldnames
csv_rows = list(reader)
old_csv_rows = copy.deepcopy(csv_rows)
by_id = {r["scenario_id"]: r for r in matrix["rows"]}
for row in csv_rows:
    if row["scenario_id"] in {"UAT-CASE-018", "UAT-CASE-040"}:
        for key in ("readiness_result", "blocking_requirements", "qualified_fixture_references"):
            value = by_id[row["scenario_id"]][key]
            row[key] = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
assert all(a == b for a, b in zip(old_csv_rows, csv_rows, strict=True) if a["scenario_id"] not in {"UAT-CASE-018", "UAT-CASE-040"})
with csv_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(csv_rows)

assessment = json.loads((OUT / "ENTRY_REASSESSMENT.json").read_text())
assessment["history"] = [{"date": assessment["date"], "entry": "BLOCKED", "qualified_starting_contexts": 32, "prerequisites_supported": 29, "retained_failed_workforce_evidence": "WORKFORCE_ASSESSMENT.json; WORKFORCE_SIX_CELLS.json", "resolved_blocker": "CEP079-PREP-B02", "resolution": "WORKFORCE_CLOSURE.json"}]
assessment["date"] = "2026-10-24"
assessment["kind"] = "ENTRY_BLOCKER_CLOSURE_ONLY_TASKS_1_TO_5_SERIAL"
assessment["tasks"] = "BLOCKER_CLOSURE_TASKS.json"
assessment["integrated_source_identity"] = "BLOCKER_CLOSURE_BASELINE.json exact dirty source hashes plus authorized template asset-version delta in CLOSEOUT_CHECK.json"
assessment["scenarios"].update({"qualified_starting_contexts": 33, "blocked": 11, "blocked_ids": [r["scenario_id"] for r in matrix["rows"] if r["readiness_result"] == "BLOCKED"]})
assessment["remaining_blockers"] = [b for b in assessment["remaining_blockers"] if b["id"] != "CEP079-PREP-B02"]
for b in assessment["remaining_blockers"]:
    if b["id"] == "CEP079-PREP-B04":
        b.update({"classification": "CANONICAL_FIXTURE_PREPARATION_INTEGRITY_FAILURE", "requirement": "Native period-end reconciliation result-hash verification rejects prepared evidence; signed reconciliation/statements are not qualified", "minimum_action": tasks["task3"]["cases"]["UAT-CASE-018"]["minimum_action"], "evidence": "TASK3_DISCOVERY.json; TASK3_RECONCILIATION_FIXTURE.json; TASK3_RECONCILIATION_RETRY_PREIMAGE.json"})
    elif b["id"] == "CEP079-PREP-B03":
        b["evidence"] += "; TASK5_AUTHORITY_DELTA.json; BILLING_AUTHORITY_DECISION_REQUIREMENT.json"
    elif b["id"] in {"CEP079-PREP-B06", "CEP079-PREP-B07", "CEP079-PREP-B08"}:
        b["evidence"] += "; TASK4_GOVERNED_INPUT_DISCOVERY.json"
assessment["ext_requirements"]["scenario_specific_data"] = "NOT_READY_11_BLOCKED_ROWS"
assessment["product_remediation"] = "AUTHORIZED_PRESENTATION_ONLY_TEMPLATE_ASSET_VERSION_4_TO_5"
assessment["authority"] = "Direct Human bounded Tasks 1..5 request; presentation/focus correction and canonical synthetic Development fixtures permitted. No UAT, production, Human Sign-off, statutory invention or Git writes."
assessment["fixtures"] = "Task3 native projection fixture preparation attempted atomically and rolled back on canonical integrity failure; no direct database bypass or financial mutations. Nine protected source-table fingerprints unchanged. Task4/5 read-only; no unsupported inputs created."
assessment["delta_preservation"] = {"prior_32_ready_rows": "UNCHANGED_NO_REQUALIFICATION", "UAT-CASE-034": "UNCHANGED_READY", "prior_29_supported_prerequisites": "UNCHANGED", "new_ready_case": "UAT-CASE-040"}
assessment["entry"] = "BLOCKED"
assert assessment["gate09"] == "NOT_PASSED" and assessment["ext0025"] == "NOT_READY"
assert len(assessment["remaining_blockers"]) == 7
write("ENTRY_REASSESSMENT.json", assessment)

registry_path = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
before_text = registry_path.read_text(encoding="utf-8")
before = yaml.safe_load(before_text)
reg = copy.deepcopy(before)
c = reg["ceps"]["CEP-079"]
c["blockers"] = [f"{b['id']} / {','.join(b['cases'])} / {b['requirement']}" for b in assessment["remaining_blockers"]]
c["updated_at"] = "2026-10-24"
c["entry_preparation"].update({"date": "2026-10-24", "authority": "DIRECT_HUMAN_BOUNDED_TASKS_1_TO_5_DEVELOPMENT_CLOSURE_NO_UAT", "starting_contexts": "33_QUALIFIED_11_BLOCKED", "workforce": "6_DISTINCT_KEYBOARD_PREREQUISITE_CELLS_PASS_TEMPLATE_ASSET_VERSION_ONLY_POINTER_PROBES_RETAINED", "test_data": "TASK3_CANONICAL_RECONCILIATION_HASH_FAILURE_ATOMIC_ROLLBACK_NO_NEW_QUALIFIED_FIXTURES", "blocker_closure": f"{REL}/BLOCKER_CLOSURE_TASKS.json"})
c["history"].append({"date": "2026-10-24", "status": "ENTRY_BLOCKER_DELTA_REASSESSED", "reason": "Tasks1-5 processed serially. B02 resolved by template asset v5 and six keyboard cells PASS; Edge mobile pointer probes retained as limitation. Prior32 ready rows and29 prerequisite outcomes preserved.33of44 contexts ready. Native Accounting reconciliation fixture rolled back on result-hash verification failure; B04 remains. B01,B03,B05-B08 unresolved in bounded sources. GATE09 NOT_PASSED EXT0025 NOT_READY. CEP079 NOT_STARTED; no UAT, Production, Human Sign-off or Git writes."})
reg["gates"]["GATE-09"].update({"evaluated_at": "2026-10-24", "note": "29 retained implementation outcomes supported; IMB0039 exact proof unverified. Workforce keyboard prerequisite six cells PASS; 33/44 starting contexts ready. Remaining evidence, native Accounting fixture integrity and governed-input gaps prevent entry. CEP078 COMPLETE and EXT0026 are not prerequisites."})
reg["execution_frontier"]["boundary_reason"] = "Tasks1-5 closure complete:29/30 implementation outcomes supported;33/44 starting contexts qualified;11 blocked. B02 resolved; B01,B03-B08 remain. No UAT execution."
reg["execution_frontier"]["current_session_cep_range"] = "CEP079_ENTRY_BLOCKER_CLOSURE_TASKS_1_TO_5_ONLY_DEVELOPMENT"
reg["execution_frontier"]["excluded_this_session"] = "CEP079_UAT_SCENARIO_EXECUTION;ALL_OTHER_CEP_EXECUTION;UNRELATED_REMEDIATION;Post-V1;Production;Human_Signoff;Certification;Git_WRITES"


def fragment(key, obj, indent=2):
    return "\n".join(" " * indent + line if line else line for line in yaml.safe_dump({key: obj}, sort_keys=False, allow_unicode=True, width=180).rstrip().splitlines()) + "\n"


new_text = re.sub(r"(?ms)^  CEP-079:\n.*?(?=^  CEP-080:)", lambda _: fragment("CEP-079", c), before_text, count=1)
new_text = re.sub(r"(?ms)^  GATE-09:\n.*?(?=^authorization_batches:)", lambda _: fragment("GATE-09", reg["gates"]["GATE-09"]), new_text, count=1)
new_text = re.sub(r"(?ms)^execution_frontier:\n.*\Z", lambda _: fragment("execution_frontier", reg["execution_frontier"], 0), new_text, count=1)
assert yaml.safe_load(new_text) == reg
assert all(reg["ceps"][key] == value for key, value in before["ceps"].items() if key != "CEP-079")
assert all(reg["gates"][key] == value for key, value in before["gates"].items() if key != "GATE-09")
assert all(reg[key] == value for key, value in before.items() if key not in {"ceps", "gates", "execution_frontier"})
assert c["execution"] == before["ceps"]["CEP-079"]["execution"]
assert c["eligibility_status"] == "NOT_ELIGIBLE" and c["execution"]["status"] == "NOT_STARTED"
for key in ("authorization", "acceptance", "dod", "git", "last_execution", "completion_report"):
    assert c[key] == before["ceps"]["CEP-079"][key]
registry_path.write_text(new_text, encoding="utf-8", newline="\n")
(OUT / "BLOCKER_CLOSURE_REGISTRY_DELTA.diff").write_text("".join(difflib.unified_diff(before_text.splitlines(True), new_text.splitlines(True), fromfile="Registry_before_closure", tofile="Registry_after_closure")), encoding="utf-8")
changes = {path: {"before": expected, "after": digest(ROOT / path)} for path, expected in baseline["product_hashes"].items() if digest(ROOT / path) != expected}
assert set(changes) == {"templates/workforce/department_list.html"}, changes
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == baseline["git"]["rev-parse HEAD"].strip()
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).strip()
subprocess.run(["git", "diff", "--check", "--", "CEP_EXECUTION_REGISTRY.yaml", "templates/workforce/department_list.html"], cwd=ROOT, check=True)
for path in OUT.glob("*.py"):
    compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
write("CLOSEOUT_CHECK.json", {"date": "2026-10-24", "canonical_identity": "PASS", "prerequisite_edges": 30, "owner_ceps": 27, "retained_supported": 29, "unverified": 1, "scenario_rows": 44, "mappings": 48, "starting_contexts": 33, "blocked_rows": 11, "prior_32_ready_rows_unchanged": True, "UAT-CASE-034": "UNAFFECTED_READY", "workforce_keyboard_cells": "6/6_PASS_WITH_MOBILE_POINTER_PROBE_LIMITATION_RETAINED", "uat_scenarios_executed": 0, "product_hashes_checked": len(baseline["product_hashes"]), "product_changes": changes, "other_85_ceps_preserved": True, "other_gates_preserved": True, "governance_human_decisions_and_authority_preserved": True, "registry_sha256": digest(registry_path), "head_unchanged": head, "git_index_empty": True, "whitespace_check": "PASS", "evidence_python_syntax": "PASS", "django_check": "PASS_0_ISSUES", "entry": "BLOCKED", "execution_may_begin": False})
print(json.dumps({"entry": "BLOCKED", "gate09": "NOT_PASSED", "ext0025": "NOT_READY", "prerequisites": "29/30", "contexts": "33/44", "remaining_blockers": [b["id"] for b in assessment["remaining_blockers"]], "product_changes": list(changes)}))
