"""Bounded evidence/Registry closeout only. Never executes Django or UAT."""
import csv
import difflib
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[5]
E = Path(__file__).resolve().parent
REL = E.relative_to(ROOT).as_posix()


def read(name):
    return json.loads((E / name).read_text(encoding="utf-8"))


def write(name, value):
    (E / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_write(name, rows):
    with (E / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


entry = read("ENTRY.json")
inputs = read("CANONICAL_INPUTS.json")
matrix = read("44_CASE_READINESS_MATRIX.json")
rows = matrix["rows"]
assert len(rows) == 44 and len({r["scenario_id"] for r in rows}) == 44
assert all(r["uat_execution_result"] == "NOT_EXECUTED" for r in rows)
assert sum(len(r["upstream_imb_ids"]) for r in rows) == 48
assert all(not r["positive_authority_state"]["missing_permissions"] for r in rows)
blocked_rows = [r for r in rows if r["readiness_result"] == "BLOCKED"]
assert len(blocked_rows) == 12
assert not read("FINAL_DATA_AUDIT.json")["unexpected_existing_captured_changes"]
source_changes = [p for p, digest in entry["source_hashes"].items() if sha(ROOT / p) != digest]
assert not source_changes, source_changes

registry_path = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
before_text = (E / "REGISTRY_BEFORE.yaml").read_text(encoding="utf-8")
before = yaml.safe_load(before_text)
assert hashlib.sha256((E / "REGISTRY_BEFORE.yaml").read_bytes()).hexdigest() == entry["registry_sha256"]
manifest = yaml.safe_load((ROOT / "docs/governance/cep/CEP_PROMPT_MANIFEST.yaml").read_text(encoding="utf-8"))["prompts"]
prompt = ROOT / manifest["CEP-079"]["path"]
assert sha(prompt) == manifest["CEP-079"]["sha256"] == entry["prompt_sha256"]
owners = {}
for cep, edges in re.findall(r"- `(CEP-\d+)` — source `([^`]+)`", prompt.read_text(encoding="utf-8")):
    for imb in re.findall(r"(IMB-\d+)→IMB-0110", edges):
        owners[imb] = cep
assert len(owners) == 30 and len(set(owners.values())) == 27
prereqs = []
for edge in inputs["prerequisite_edges"]:
    imb = edge["Prerequisite IMB ID"]
    cep = owners[imb]
    ident = manifest[cep]
    assert sha(ROOT / ident["path"]) == ident["sha256"]
    rec = before["ceps"][cep]
    assert rec["execution"]["status"] == "COMPLETE"
    report = ROOT / (rec["completion_report"]["path"] or f"docs/governance/cep/reports/{cep}_COMPLETION_REPORT.md")
    cases = sorted(set(re.findall(r"UAT-CASE-\d+", edge["Dependency Condition"])))
    assert cases and set(cases) <= {r["scenario_id"] for r in rows}
    exists = report.is_file()
    assert exists == (cep != "CEP-040")
    acceptance = ROOT / f"docs/governance/cep/evidence/{cep}_ACCEPTANCE_MAPPING.csv"
    prereqs.append({
        "edge_id": edge["Edge ID"], "imb": imb, "owner_cep": cep,
        "condition": edge["Dependency Condition"], "applies": True,
        "cases": ";".join(cases), "registry_execution": rec["execution"]["status"],
        "prompt_sha256": ident["sha256"],
        "outcome_evidence": report.relative_to(ROOT).as_posix() if exists else "CEP040_RECOVERY.json",
        "outcome_evidence_sha256": sha(report) if exists else sha(E / "CEP040_RECOVERY.json"),
        "acceptance_mapping": acceptance.relative_to(ROOT).as_posix() if acceptance.is_file() else "See retained report; not inferred from downstream references",
        "acceptance_mapping_sha256": sha(acceptance) if acceptance.is_file() else "",
        "implementation_outcome": "SUPPORTED_RETAINED_SCOPED_EVIDENCE" if exists else "UNVERIFIED_EXACT_OUTCOME_EVIDENCE_MISSING",
        "readiness_limit": "Implementation evidence reused, not a new runtime PASS; current applicable verification/data failures remain separately blocking",
    })
assert sum(r["implementation_outcome"].startswith("SUPPORTED") for r in prereqs) == 29
csv_write("30_PREREQUISITE_ASSESSMENT.csv", prereqs)

six = read("WORKFORCE_INITIAL_SIX_CELLS.json")
assert len(six) == 6 and all(c["result"] == "FAIL" for c in six)
write("WORKFORCE_ASSESSMENT.json", {
    "scope": "Only six formerly UTV Workforce prerequisite cells; not CEP079 scenario execution",
    "cells": [{"browser": c["family"], "viewport": c["viewport"], "result": c["result"], "checks": c["checks"], "capture": c["capture"]} for c in six],
    "distinct_cells": 6, "fail": 6, "pass": 0, "utv": 0,
    "raw_observations": 7, "repeat": "One Chrome 390 hard-refresh attribution probe also FAIL; not counted as a seventh cell",
    "failure": "Close does not restore trigger focus; Escape retains the open drawer and close-button focus",
    "source_drift": {"path": "templates/workforce/department_list.html", "classification": "PRE_EXISTING_PRESENTATION_SURFACE_DRIFT_FROM_PRIOR_R5_EVIDENCE", "current": sha(ROOT / "templates/workforce/department_list.html"), "prior_R5": "238f648fb22aa80d0f086b545faab388dc709d2c5322af551622f344ce909937", "detail": "Current entry/HEAD template requests JS v4; prior final R5 evidence expected v5. Current JS bytes match prior final R5. Causal attribution to asset caching/source delivery is NOT proved; hard refresh still failed."},
    "attributable_regression_introduced_by_preparation": False,
    "functional_current_result": "Actual FAIL retained, irrespective of presentation-only file classification",
    "applicability": {"UAT-CASE-040": "BLOCKING current cross-cutting keyboard/RTL/form prerequisite", "UAT-CASE-034": "NOT CURRENTLY BLOCKING: ordinary Person/employee route selected; conditional blocker if department-tree traversal is required later"},
    "prior_sufficient_coverage_rerun": False,
    "minimum_action": "Attribute and repair this bounded defect under separate implementation authority, then recheck exactly six cells; do not require blanket CEP078 completion",
})

blockers = [
    {"id": "CEP079-PREP-B01", "cases": ["UAT-CASE-012"], "classification": "MISSING_EVIDENCE", "requirement": "CEP040 / IMB0039 exact completion, AC/DoD and tests proving source reconciliation, version/as-of, duplicates/supersession, tenant/project aggregation and no financial writes", "minimum_action": "Recover original authoritative execution/acceptance/test evidence. Search is exhausted in the approved local, retained Git and recovery sources; downstream completion claims are insufficient. No reimplementation to manufacture proof.", "evidence": "CEP040_RECOVERY.json"},
    {"id": "CEP079-PREP-B02", "cases": ["UAT-CASE-040"], "classification": "REQUIRED_RUNTIME_VERIFICATION_FAIL", "requirement": "Six browser/viewport cells fail Close and Escape focus", "minimum_action": "Separately authorize bounded defect attribution/correction and revalidate only six cells. Case034 ordinary route is unaffected; no blanket CEP078 completion condition.", "evidence": "WORKFORCE_ASSESSMENT.json"},
    {"id": "CEP079-PREP-B03", "cases": ["UAT-CASE-009", "UAT-CASE-016 (AR branch)", "UAT-CASE-023"], "classification": "PRODUCT_REGULATORY_OR_HUMAN_SOURCE_REQUIRED", "requirement": "Approved effective tax_rate, tax_basis, insurance_rate, insurance_basis; effective source provenance; real ACCEPTED professional review; applicable ContractTermVersion and TenantBillingConfiguration", "minimum_action": "Supply existing approved commercial/regulatory values and bases, effective authority/source/version and accepted professional review, plus approved contract terms/configuration. If unavailable, the responsible Human/Product-Regulatory authority must determine them. Then prepare only disposable claim/AR/settlement inputs through owning lifecycles.", "evidence": "BILLING_SOURCE_RECOVERY.json; BILLING_BROAD_RECOVERY_INDEX.json; SOURCE_PRODUCER_REGISTRY.json"},
    {"id": "CEP079-PREP-B04", "cases": ["UAT-CASE-018"], "classification": "MISSING_QUALIFIED_FIXTURE_AND_EVIDENCE", "requirement": "Signed independent native period-end reconciliation with verified statement/control coverage for the isolated fiscal period; distinct close/reopen requester and approver bindings", "minimum_action": "Provide/qualify native period-end reconciliation and its statement/control inputs and bind authorized independent actors. Empty period or unknown source coverage cannot substitute for verified zero. Close/reopen remains unexecuted.", "evidence": "44_CASE_READINESS_MATRIX.json; REMAINING_STARTING_STATES.json"},
    {"id": "CEP079-PREP-B05", "cases": ["UAT-CASE-019", "UAT-CASE-020", "UAT-CASE-022"], "classification": "MISSING_QUALIFIED_CONFIGURATION_AND_FIXTURE", "requirement": "ACTIVE BANK Treasury account with approved effective bank/GL mapping; disposable statement and cleared cheque sources", "minimum_action": "Locate approved bank/accounting mapping inputs, then activate an isolated Development bank account and prepare statement/cheque starting states canonically. Obtain source-owner approval only if an applicable mapping does not already exist; do not invent the account mapping.", "evidence": "TREASURY_PREPARATION_RESULT.json; QUALIFIED_STARTING_DATA.json"},
    {"id": "CEP079-PREP-B06", "cases": ["UAT-CASE-029", "UAT-CASE-044"], "classification": "MISSING_GOVERNED_BUSINESS_SOURCE_AND_FIXTURE", "requirement": "Qualified PartnerProfile, sourced QualificationRequirement and associated qualified partner context", "minimum_action": "Attach an existing approved requirement/source/version and partner facts, then prepare an isolated profile/context through the canonical lifecycle. If no approved requirement exists, obtain domain-owner criteria; do not treat illustrative test criteria as approved business policy.", "evidence": "QUALIFIED_STARTING_DATA.json; 44_CASE_READINESS_MATRIX.json"},
    {"id": "CEP079-PREP-B07", "cases": ["UAT-CASE-043"], "classification": "MISSING_GOVERNED_FINANCIAL_SOURCE_AND_FIXTURE", "requirement": "Qualified FixedAssetClassVersion, AssetBookPolicyVersion and positive asset candidate with sourced capitalization/monetary facts", "minimum_action": "Attach applicable approved class/book/capitalization sources and asset facts; prepare a non-posting isolated candidate. Source-owner decision is needed only where existing approved inputs cannot be located; no invented depreciation or posting policy.", "evidence": "QUALIFIED_STARTING_DATA.json; 44_CASE_READINESS_MATRIX.json"},
    {"id": "CEP079-PREP-B08", "cases": ["UAT-CASE-044"], "classification": "MISSING_GOVERNED_BUSINESS_SOURCE_AND_FIXTURE", "requirement": "Published Compliance InspectionTemplateVersion with approved checklist/outcome rules/source references", "minimum_action": "Attach an approved existing-semantic inspection template and prepare isolated inspection inputs. Obtain domain-owner content if absent; no invented checklist/risk rules.", "evidence": "QUALIFIED_STARTING_DATA.json; 44_CASE_READINESS_MATRIX.json"},
]
assessment = {
    "date": "2026-10-23", "cep": "CEP-079", "kind": "ENTRY_PREPARATION_ONLY",
    "entry": "BLOCKED", "gate09": "NOT_PASSED", "ext0025": "NOT_READY",
    "canonical_prompt_sha256": sha(prompt), "head": entry["head"],
    "integrated_source_identity": "ENTRY.json source_hashes: 1497 exact current dirty-worktree product files; HEAD alone is not the integrated source identity",
    "canonical_requirements": {"GATE-09": inputs["gate09"], "EXT-0025": inputs["ext0025"]},
    "prerequisites": {"conditional_edges": 30, "applies": 30, "owner_ceps": 27, "supported_implementation_outcomes": 29, "unverified": ["CEP-040/IMB-0039"], "verification_failures_separate": "WORKFORCE_ASSESSMENT.json", "evidence": "30_PREREQUISITE_ASSESSMENT.csv"},
    "scenarios": {"approved": 44, "scenario_imb_mappings": 48, "qualified_starting_contexts": 32, "blocked": 12, "not_executed": 44, "blocked_ids": [r["scenario_id"] for r in blocked_rows], "evidence": "44_CASE_READINESS_MATRIX.csv"},
    "ext_requirements": {"integrated_build_source_identity": "IDENTIFIED_CURRENT_HEAD_PLUS_DIRTY_SOURCE_HASHES", "authoritative_catalogue_mapping": "RECOVERED_APPROVED_SOURCE", "safe_disposable_context": "ISOLATED_SYNTHETIC_TARGETS_PREPARED_EXISTING_ACCEPTED_BUSINESS_ROWS_UNCHANGED", "actors_scopes_permissions": "QUALIFIED_EXPLICIT_EXISTING_CANONICAL_ASSIGNMENTS_NO_ROLE_DEFINITION_CHANGES", "scenario_specific_data": "NOT_READY_12_BLOCKED_ROWS", "browser_runtime": "AVAILABLE_CHROME_AND_EDGE", "database_django_runtime": "AVAILABLE_DEVELOPMENT_POSTGRESQL_DJANGO_MIGRATIONS_CURRENT", "capture": "AVAILABLE_JSON_CSV_SCREENSHOTS_SOURCES_HASHES_NO_UAT_RESULTS"},
    "remaining_blockers": blockers,
    "authority": "Direct Human request permits bounded preparation and synthetic Development fixtures. Objective Gate evaluation is allowed by current governance; unmet requirements prohibit PASS. No Human Sign-off/EXT0026 required or performed.",
    "cep078": "PARTIAL preserved; not a canonical dependency. Only material scenario intersections assessed; no blanket COMPLETE requirement.",
    "fixtures": "Canonical services only; no role/permission definitions changed. Source-preservation and business-row limitations in FINAL_DATA_AUDIT.json. Raw retry metadata status indexing error is corrected by current DB witness, not a mutation rerun.",
    "uat_execution": "NOT_STARTED_ALL_44_NOT_EXECUTED", "may_begin_next_step": False,
    "product_remediation": "NONE", "git_writes": "NONE", "production": "NONE", "human_signoff": "NOT_EXECUTED",
}
write("ENTRY_REASSESSMENT.json", assessment)
report = """# CEP-079 entry preparation — 2026-10-23

**ENTRY BLOCKED. GATE-09 NOT_PASSED. EXT-0025 NOT_READY.** CEP-079 remains NOT_ELIGIBLE / NOT_STARTED. No UAT scenario was executed or scored.

44 approved cases / 48 Scenario→IMB mappings recovered under the canonical prompt recovery rule; all 30 conditional edges apply across 27 CEPs. 29 retained scoped implementation outcomes are supported. CEP040/IMB0039 exact execution proof remains unverified. The Registry's historical COMPLETE state is preserved. Report/acceptance references and hashes are in `30_PREREQUISITE_ASSESSMENT.csv`; report evidence is not promoted to fresh runtime PASS.

`44_CASE_READINESS_MATRIX.csv` and JSON contain all 44 original semantic rows, actual actors, explicit canonical role/permission/scope state, negative comparators, independent checkers, required disposable state, data availability, fixture references and blockers. 32 have qualified starting contexts only; 12 are blocked. Every UAT result is NOT_EXECUTED. Qualification promises no later scenario PASS; services must recheck current authorization and source state transactionally.

## Remaining blockers

| Cases | Classification / exact missing requirement | Minimum next action |
|---|---|---|
"""
for b in blockers:
    report += f"| {', '.join(b['cases'])} | {b['classification']}: {b['requirement']} | {b['minimum_action']} |\n"
report += """
## Evidence and preparation boundaries

`CEP040_RECOVERY.json` records the ordered repository, retained Git/output and approved archive searches; downstream references were rejected as proof. `BILLING_SOURCE_RECOVERY.json` plus the broad archive index cover all 15 approved recovery archives. Policy schemas define allowable structure, not approved rates/bases. No effective regulatory version, accepted professional review, ContractTermVersion or TenantBillingConfiguration exists in the qualified context. The only registered AR producer is Billing progress claim; case016's AR branch therefore shares this gap. No rates, zero substitutions, terms, provenance or professional acceptance were invented.

`WORKFORCE_ASSESSMENT.json` retains six actual FAIL results, with seven raw observations including one hard-refresh probe. Close focus restoration and Escape fail in Chrome and Edge at 1440×900, 1024×768 and 390×844. Current template/asset version drift predates preparation; caching causality is unproved. No attributable regression was introduced here. Prior sufficient coverage was not rerun. Case040 is affected; case034 uses the ordinary Person/employee route and is not currently blocked by the tree. CEP078 completion remains unnecessary.

Development context is the configured local PostgreSQL database, not Production. Browser, Django/PostgreSQL, migrations and JSON/CSV/image capture are available. `ENTRY.json` pins branch, HEAD, local upstream and all 1497 product source hashes, including pre-existing dirty changes; `SOURCE_PRESERVATION.json` and closeout checks prove no product mutation during preparation. No remote-ref freshness claim is made.

Only clearly isolated `CEP079-PREP-01` synthetic business targets were created through canonical services/lifecycles. Existing accepted financial, Payroll, stock and other business sources are read-only. Actors use registered canonical roles and explicit scope assignments through governed dual-control/Platform Initial Grant services; no role definition, permission set, legacy role hierarchy or authorization semantics was changed. The new assignments are test-membership fixtures, not default grants. 14 existing credentials were verified read-only without disclosure or password changes. New Payroll/cash/stock/AP preparatory lifecycles establish disposable starting states; they are not CEP079 UAT results.

`FINAL_DATA_AUDIT.json` witnesses current fixture states and no unexpected changes among captured pre-existing rows. Expected synthetic membership timestamps and one associated authorization-quarantine resolution are recorded. The initial snapshot omitted natural-key Session and JournalNumberSequence rows; later full-primary-key snapshots cover all 519 models and retain canonical counter changes. This limitation prevents a claim of a complete initial natural-key preimage. Raw Payroll retry metadata mistakenly assigned finalized status to the last input record; current DB witness correctly identifies the finalized PayrollRun and input status. The helper is corrected without repeating mutations. Failed preparation groups and rollbacks are retained as evidence, not PASS.

No broad implementation suite, prior sufficient CEP078 runtime coverage, CEP079 scenario, unrelated remediation, Git write, Production action or Human Sign-off was performed. Registry changes record only this preparation, Gate09 non-passage and the stopped frontier. Entry reassessment must be repeated after the exact blockers clear; UAT may not begin in the next step.
"""
(E / "REPORT.md").write_text(report, encoding="utf-8")

reg = yaml.safe_load(before_text)
c = reg["ceps"]["CEP-079"]
c["title"] = "Representative UAT execution"
c["dependency_status"] = "30_CONDITIONS_APPLY_29_IMPLEMENTATION_OUTCOMES_SUPPORTED_CEP040_IMB0039_EVIDENCE_UNVERIFIED"
c["execution"]["lifecycle"] = "NOT_ELIGIBLE_ENTRY_PREPARATION_BLOCKED"
c["blockers"] = [f"{b['id']} / {','.join(b['cases'])} / {b['requirement']}" for b in blockers]
c["entry_preparation"] = {
    "date": "2026-10-23", "authority": "DIRECT_HUMAN_BOUNDED_DEVELOPMENT_ENTRY_PREPARATION_REQUEST_NO_UAT_EXECUTION",
    "result": "BLOCKED", "gate09": "NOT_PASSED", "ext0025": "NOT_READY",
    "assessment": f"{REL}/ENTRY_REASSESSMENT.json", "report": f"{REL}/REPORT.md",
    "readiness_matrix": f"{REL}/44_CASE_READINESS_MATRIX.csv",
    "prerequisites": "30_APPLY_29_SUPPORTED_1_UNVERIFIED", "starting_contexts": "32_QUALIFIED_12_BLOCKED",
    "workforce": "6_DISTINCT_REQUIRED_CELLS_FAIL_CLOSE_ESCAPE_FOCUS_NO_PRODUCT_CHANGE",
    "personas": "EXPLICIT_EXISTING_CANONICAL_ROLES_AND_SCOPES_QUALIFIED_NO_ROLE_DEFINITION_CHANGES",
    "test_data": "MINIMAL_ISOLATED_SYNTHETIC_DEVELOPMENT_FIXTURES_VIA_CANONICAL_SERVICES",
    "uat_scenarios_executed": 0, "cep078_complete_required": False,
}
c["updated_at"] = "2026-10-23"
c["history"].append({"date": "2026-10-23", "status": "ENTRY_PREPARATION_BLOCKED", "reason": "Bounded Human-requested preparation only; exact remaining blockers in entry_preparation assessment. No scenario execution, Product remediation, Git writes, Production action or Human Sign-off."})
gate = {"status": "NOT_PASSED", "source": "OBJECTIVE_ENTRY_READINESS_REASSESSMENT", "human_signoff_required": False, "evaluated_at": "2026-10-23", "evidence": f"{REL}/ENTRY_REASSESSMENT.json", "required_imb_status": {r["imb"]: r["implementation_outcome"] for r in prereqs}, "ext0025": "NOT_READY", "note": "29 retained implementation outcomes supported; IMB0039 unverified; applicable Workforce runtime FAIL and scenario-specific data/authority gaps prevent entry. CEP078 COMPLETE and EXT0026 are not prerequisites."}
reg["gates"]["GATE-09"] = gate
front = reg["execution_frontier"]
front.update({"current_session_continuation": "STOP_CEP079_ENTRY_BLOCKED_NO_UAT_EXECUTION", "current_session_cep_range": "CEP079_ENTRY_PREPARATION_ONLY_DEVELOPMENT", "boundary_reason": "Current bounded entry preparation: 29/30 implementation outcomes supported, 32/44 starting contexts qualified, 12 blocked; exact source/fixture/evidence/runtime blockers retained. No CEP079 UAT execution authorized by this preparation.", "next_candidate_full_entry_eligibility": "CEP079_ENTRY_BLOCKED_REQUIRES_EXACT_REMAINING_BLOCKERS_CLEARED_AND_REASSESSMENT", "resume_cep_after_blocker_resolution": "CEP079_ENTRY_REASSESSMENT_ONLY_BEFORE_ANY_UAT_EXECUTION", "independent_candidates_entry_status": "NOT_EXECUTED_OUTSIDE_CURRENT_ENTRY_PREPARATION_SCOPE", "excluded_this_session": "CEP079_UAT_SCENARIO_EXECUTION;ALL_OTHER_CEP_EXECUTION;Product_REMEDIATION;Post-V1;Production;Human_Signoff;Certification;Git_WRITES"})
assert reg["summary"]["blocked_current"] == 1 and reg["summary"]["not_started_other_current_governed"] == 6
reg["summary"]["blocked_current"] = 2
reg["summary"]["not_started_other_current_governed"] = 5

# Bounded textual replacement preserves all unrelated Registry content and comments.
def fragment(key, obj, indent=2):
    return "\n".join(" " * indent + line if line else line for line in yaml.safe_dump({key: obj}, sort_keys=False, allow_unicode=True, width=180).rstrip().splitlines()) + "\n"

new_text = re.sub(r"(?ms)^  CEP-079:\n.*?(?=^  CEP-080:)", lambda _: fragment("CEP-079", c), before_text, count=1)
new_text = new_text.replace("authorization_batches:\n", fragment("GATE-09", gate) + "authorization_batches:\n", 1)
new_text = re.sub(r"(?ms)^execution_frontier:\n.*\Z", lambda _: fragment("execution_frontier", front, 0), new_text, count=1)
new_text = new_text.replace("  blocked_current: 1\n", "  blocked_current: 2\n", 1).replace("  not_started_other_current_governed: 6\n", "  not_started_other_current_governed: 5\n", 1)
assert yaml.safe_load(new_text) == reg
current = registry_path.read_text(encoding="utf-8")
assert current in (before_text, new_text), "Registry changed independently; do not overwrite"
registry_path.write_text(new_text, encoding="utf-8", newline="\n")
(E / "REGISTRY_DELTA.diff").write_text("".join(difflib.unified_diff(before_text.splitlines(True), new_text.splitlines(True), fromfile="Registry_before", tofile="Registry_after")), encoding="utf-8")
assert all(reg["ceps"][k] == v for k, v in before["ceps"].items() if k != "CEP-079")
assert all(reg["gates"][k] == v for k, v in before["gates"].items())
assert all(reg[k] == before[k] for k in before if k not in {"ceps", "gates", "execution_frontier", "summary"})
assert c["eligibility_status"] == "NOT_ELIGIBLE" and c["execution"]["status"] == "NOT_STARTED"
assert c["acceptance"] == before["ceps"]["CEP-079"]["acceptance"] and c["last_execution"] == before["ceps"]["CEP-079"]["last_execution"]
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == entry["head"]
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).strip()
subprocess.run(["git", "diff", "--check", "--", "CEP_EXECUTION_REGISTRY.yaml"], cwd=ROOT, check=True)
for p in E.glob("*.py"):
    compile(p.read_text(encoding="utf-8-sig"), str(p), "exec")
write("CLOSEOUT_CHECK.json", {"canonical_identity": "PASS", "prerequisite_edges": 30, "owner_ceps": 27, "retained_supported": 29, "unverified": 1, "scenario_rows": 44, "mappings": 48, "starting_contexts": 32, "blocked_rows": 12, "uat_scenarios_executed": 0, "product_hashes_checked": len(entry["source_hashes"]), "product_changes": source_changes, "unexpected_captured_existing_data_changes": {}, "other_85_ceps_preserved": True, "prior_gates_preserved": True, "governance_human_decisions_and_authority_preserved": True, "summary_reconciled": {"blocked_current": 2, "not_started_other_current_governed": 5}, "registry_sha256": sha(registry_path), "head_unchanged": head, "git_index_empty": True, "registry_whitespace_check": "PASS", "evidence_python_syntax": "PASS", "entry": "BLOCKED", "execution_may_begin": False})
files = [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(E.rglob("*")) if p.is_file() and p.name != "EVIDENCE_MANIFEST.csv"]
csv_write("EVIDENCE_MANIFEST.csv", files)
print(json.dumps({"entry": "BLOCKED", "gate09": "NOT_PASSED", "ext0025": "NOT_READY", "prerequisites": "29/30", "starting_contexts": "32/44", "blocked": 12, "evidence_files": len(files), "no_uat": True}))
