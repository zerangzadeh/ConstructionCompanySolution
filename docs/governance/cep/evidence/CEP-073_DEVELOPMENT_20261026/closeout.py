"""Reconcile executed verification, independent external prerequisites and frontier."""

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

OUT = Path("docs/governance/cep/evidence/CEP-073_DEVELOPMENT_20261026")
sys.path.insert(0, str(Path("docs/governance/cep/evidence/CEP-012_REQUALIFICATION_20261026").resolve()))
# This module is run as __main__; import the bounded Registry text helper by path.
from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location("cep012_closeout", Path(sys.path[0]) / "closeout.py")
helper = module_from_spec(spec)
spec.loader.exec_module(helper)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def app_files(source):
    return {p: digest for p, digest in source["files"].items()
            if not p.startswith("tests/") and p != "scripts/cep073_capture.py"}


def main():
    first = read(OUT / "ATTEMPT_01/RUNTIME.json")
    retry = read(OUT / "RUNTIME.json")
    migration = read(OUT / "MIGRATION/PRESERVATION.json")
    original = read(OUT / "ATTEMPT_01/SOURCE_BUILD_BEFORE.json")
    final = read(OUT / "RETRY_SOURCE_AFTER.json")
    assert original == read(OUT / "ATTEMPT_01/SOURCE_BUILD_AFTER.json")
    assert final == read(OUT / "RETRY_SOURCE_BEFORE.json")
    assert app_files(original) == app_files(final)
    assert [p for p in final["files"] if original["files"][p] != final["files"][p]] == ["tests/test_cep073_runtime.py"]
    passed = {r["scenario"]: {**r, "artifact": "ATTEMPT_01/RUNTIME.json"}
              for r in first["tests"] if r["outcome"] == "passed" and r["phase"] == "call"}
    assert len(passed) == 9
    assert retry["exit_code"] == 0
    passed.update({r["scenario"]: {**r, "artifact": "RUNTIME.json"}
                   for r in retry["tests"] if r["outcome"] == "passed" and r["phase"] == "call"})
    assert len(passed) == 10
    assert migration["status"] == "PASS" and len(migration["checks"]) == 42
    assert migration["disposable_database_removed"]
    plans = first["plans"] + retry["plans"]
    assert {r["category"] for r in plans} == {
        "GL_BOUNDED_LIST", "AUDIT_BOUNDED_LIST", "INVENTORY_SCOPED_AGGREGATE", "REPORTING_SOURCE_AGGREGATE"
    }
    assert len([r for r in retry["plans"] if r["category"] == "REPORTING_SOURCE_AGGREGATE"]) == 2
    app_digest = hashlib.sha256(json.dumps(app_files(final), sort_keys=True).encode()).hexdigest()
    validation = {
        "status": "PASS_QUALIFIED_DEVELOPMENT", "acceptance": "12/12", "dod": "MET",
        "application_sha": final["head"], "application_source_build_sha256": app_digest,
        "final_source_manifest": "RETRY_SOURCE_AFTER.json", "distinct_runtime_passes": list(passed.values()),
        "migration_checks": 42, "migration_artifact": "MIGRATION/PRESERVATION.json",
        "query_plans": plans, "captured_plan_count": len(plans),
        "application_code_configuration_schema_unchanged_between_attempts": True,
        "fixture_repairs": [
            "Test-only reporting role assigned after native Inventory source creation, preserving source authority",
            "Explicit registered result-view permission added to the test-only reporting role",
        ],
        "failed_attempts_retained": ["ATTEMPT_01", "ATTEMPT_02"],
        "not_claimed": ["Production workload/capacity/SLA or throughput acceptance", "Historical frozen P10 workload completion", "Production/Human Sign-off"],
    }
    (OUT / "VALIDATION.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    blockers = {
        "EXT-0018": {"ceps": ["CEP-069"], "classification": "AUTHORITATIVE_EXTERNAL_INPUT",
                     "missing": "Current official statutory package with effective applicability, accepted professional/currentness review, source/version/classification/bases/caps/exemptions/shares/YTD/rounding/retroactivity/schema and explicit activation evidence",
                     "development_work": "CEP052 engine and CEP069 intake/fail-closed foundation already complete; no current values/review can be fabricated"},
        "EXT-0020": {"ceps": ["CEP-070", "CEP-074"], "classification": "HUMAN_DECISION",
                     "missing": "Approved recovery matrix: RPO/RTO, PITR requirement, backup frequency/retention, designated restore/acceptance responsibility and qualified recovery target/storage/key-recovery references",
                     "development_work": "CEP070 adapter, failure/evidence hooks and synthetic interoperability proof already complete;070 production outcome must precede074"},
        "EXT-0021": {"ceps": ["CEP-071", "CEP-075"], "classification": "HUMAN_DECISION",
                     "missing": "Approved deployment topology and target environment; process/static/media/secrets/release/recovery contracts and named activation/release responsibility",
                     "development_work": "Existing production settings guards verified; target-specific controls require selected inputs;071 required outcome precedes075"},
        "EXT-0022": {"ceps": ["CEP-072", "CEP-076"], "classification": "HUMAN_DECISION",
                     "missing": "Named release/incident/activation/escalation/support-access/access-revocation/runbook owners and approved operating signals/alert destinations/access/retention/runbook evidence contracts",
                     "development_work": "Request telemetry/failure foundation already complete; approved domain signal/alert/runbook/access scenario follows these inputs;072 required outcome precedes076"},
        "PRODUCTION_AUTHORITY": {"ceps": ["CEP-069", "CEP-070", "CEP-071", "CEP-072"], "classification": "PRODUCTION_ONLY",
                     "missing": "Separate exact-action Human authority for production activity and Human-issued final certification/sign-off",
                     "development_work": "Outside current Development authorization; no production action performed"},
    }
    resolved = [
        {"item": "Audit0016 history deletion", "classification": "DEVELOPMENT_RESOLVABLE", "result": "REPAIRED"},
        {"item": "Billing0006 policy snapshot loss", "classification": "DEVELOPMENT_RESOLVABLE", "result": "REPAIRED_BY_RAW_JSON_PRESERVING_RENAME"},
        {"item": "Billing0008 claims/allocation deletion and revision clearing", "classification": "DEVELOPMENT_RESOLVABLE", "result": "REPAIRED_WITH_EXPLICIT_FAIL_CLOSED_EXCEPTIONS"},
        {"item": "Missing CEP012 executed preservation proof", "classification": "REPRODUCIBLE_EVIDENCE", "result": "42_ACTUAL_POSTGRESQL_CHECKS_PASS"},
        {"item": "GATE06 implementation-readiness evidence", "classification": "REPRODUCIBLE_EVIDENCE", "result": "PASS_QUALIFIED_DEVELOPMENT"},
        {"item": "EXT0023 current target/build/scenario/data-safety/capture", "classification": "DEVELOPMENT_RESOLVABLE", "result": "QUALIFIED_AND_EXECUTED"},
        {"item": "Test extension/fixtures/JSON comparison and missing cached starter catalog", "classification": "DEVELOPMENT_RESOLVABLE", "result": "RESOLVED_NO_REQUIRED_FAILURE_REMAINS"},
    ]
    result = {"status": "NO DEVELOPMENT-RESOLVABLE WORK REMAINS", "work_executed": resolved,
              "remaining_blockers": blockers, "next_executable_frontier": [],
              "next_external_unlock": "EXT0020 approved recovery matrix/responsibility/target permits resuming070; its required outcome and qualified verification target then unlock074",
              "completed_ceps_not_rerun": ["CEP-077", "CEP-078", "CEP-079"],
              "git_writes": False, "production_actions": False}
    (OUT / "RESULT.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    text = Path("CEP_EXECUTION_REGISTRY.yaml").read_text(encoding="utf-8")
    registry = yaml.safe_load(text)
    excluded = read("docs/governance/cep/evidence/CEP-012_REQUALIFICATION_20261026/REGISTRY_BEFORE.json")["excluded_complete_record_hashes"]
    for key, digest in excluded.items():
        assert hashlib.sha256(json.dumps(registry["ceps"][key], sort_keys=True).encode()).hexdigest() == digest
    cep = registry["ceps"]["CEP-073"]
    cep["execution"].update(status="COMPLETE", lifecycle="CLOSED_VERIFIED_DEVELOPMENT_RUNTIME")
    cep["acceptance"] = {"passed": 12, "total": 12, "status": "PASS_QUALIFIED_DEVELOPMENT_RUNTIME"}
    cep["dod"] = "MET_FOR_DEFINED_CURRENT_BUILD_DEVELOPMENT_SCENARIOS"
    cep["blockers"] = []
    cep["remaining_utv"] = ["Production workload/capacity, frozen historical P10 profile and production deployment/certification are not validated by these bounded Development scenarios"]
    cep["completion_report"] = {"path": "docs/governance/cep/reports/CEP-073_COMPLETION_REPORT.md", "evidence_presence": "EXECUTED_POSTGRESQL_MIGRATION_QUERY_PLAN_TIMING_AND_CONCURRENCY"}
    cep["last_execution"] = {"branch": "main", "sha": final["head"], "application_build_sha256": app_digest}
    cep["git"].update(committed=False, pushed=False, merged_to_main=False, remote_main_evidence="UNCOMMITTED_CURRENT_DEVELOPMENT_VERIFICATION")
    cep["updated_at"] = "2026-10-26"
    cep["current_frontier_review"] = {"result": "COMPLETE_12_OF_12_DEVELOPMENT", "evidence": (OUT / "VALIDATION.json").as_posix(), "gate06": "PASS", "ext0023": "QUALIFIED_DEVELOPMENT_TARGET_EXECUTED"}
    cep["frontier_review"] = cep["current_frontier_review"]
    cep["history"].extend([
        {"date": "2026-10-26", "status": "VALIDATION_FIXTURE_FAILURE_RESOLVED", "reason": "Native authorization correctly rejected incomplete test-only role setup; fixture ordering and explicit registered result-view permission corrected. No product/authorization change. Nine unaffected application-source passes retained; failed scenario retried successfully.", "evidence": (OUT / "VALIDATION.json").as_posix()},
        {"date": "2026-10-26", "status": "COMPLETE", "reason": "12/12 scoped AC, DoD MET:42 post-entry PostgreSQL migration checks,10 distinct runtime cases, measured EXPLAIN ANALYZE plans and actual two-worker transfer evidence. No capacity/production/Human acceptance inferred.", "evidence": (OUT / "VALIDATION.json").as_posix()},
    ])
    gate = registry["gates"]["GATE-08"]
    gate["required_imb_status"].update({"IMB-0103": "PASS_CURRENT_DEVELOPMENT_CEP073", "IMB-0109": "PASS_CURRENT_DEVELOPMENT_CEP073"})
    gate["contributor_evidence"]["CEP-073"] = (OUT / "VALIDATION.json").as_posix()
    gate["status"] = "NOT_PASSED"
    gate["note"] = "CEP073/077/078 required scoped non-production contributions PASS. Required CEP074/075/076 outcomes remain blocked by070/071/072 and EXT0020/0021/0022. No global/Production/Human Sign-off inference."
    gate["evidence"] = (OUT / "RESULT.json").as_posix()
    gate["history"].append({"date": "2026-10-26", "status": "NOT_PASSED", "reason": "073 IMB0103/0109 executed contributions now PASS;074..076 remain unexecuted; no blanket runtime gate PASS.", "evidence": (OUT / "VALIDATION.json").as_posix()})
    counts = Counter(registry["ceps"][f"CEP-{i:03}"]["execution"]["status"] for i in range(1, 80))
    assert counts == {"COMPLETE": 72, "PARTIAL": 4, "NOT_STARTED": 3}
    summary = registry["summary"]
    summary.update(execution_state_complete=72, partial_current=4, blocked_current=3, in_progress=0,
                   eligible_under_standing_authority=0, last_updated="2026-10-26")
    frontier = registry["execution_frontier"]
    frontier.update(dependency_ready_current_governed=[f"CEP-{i:03}" for i in range(69, 73)],
                    verified_build_eligible_unblocked=[], verified_verification_eligible_unblocked=[],
                    next_autonomous_cep=None, next_executable_frontier=[], current_independent_cep=None,
                    next_entry_review_candidate=None, next_candidate_full_entry_eligibility="EXTERNAL_INPUT_REQUIRED",
                    current_session_continuation="STOP_ALL_DEVELOPMENT_RESOLVABLE_WORK_EXHAUSTED",
                    current_session_cep_range="CEP069_076_WITH_CEP012_PRESERVATION_PREREQUISITE_REPAIR",
                    independent_candidates_entry_status="069_072_PARTIAL_AUTHORITATIVE_HUMAN_INPUTS_REQUIRED;073_COMPLETE;074_076_REQUIRED_OUTCOME_AND_EXT_BLOCKED;077_079_COMPLETE_NOT_RERUN",
                    conditional_dependency_entry_review_candidates=[],
                    boundary_reason="CEP012 requalified;GATE06 PASS Development;073 verification COMPLETE.069..072 require authoritative/Human inputs;074..076 cannot bypass those required outcomes. All local/reproducible work exhausted.",
                    reconciliation_evidence=(OUT / "RESULT.json").as_posix())
    frontier["unblock_conditions"] = {
        "CEP-069": blockers["EXT-0018"]["missing"], "CEP-070": blockers["EXT-0020"]["missing"],
        "CEP-071": blockers["EXT-0021"]["missing"], "CEP-072": blockers["EXT-0022"]["missing"],
        "CEP-074": "Complete required CEP070 outcome and qualify EXT0020 restore target/objectives",
        "CEP-075": "Complete required CEP071 outcome and qualify EXT0021 deployment target",
        "CEP-076": "Complete required CEP072 outcome and qualify EXT0022 incident/runbook/owner target",
    }
    for key in ("CEP-073", "GATE-08", "summary", "execution_frontier"):
        value = cep if key == "CEP-073" else gate if key == "GATE-08" else summary if key == "summary" else frontier
        text = helper.replace_record(text, key, value, 0 if key in ("summary", "execution_frontier") else 2)
    Path("CEP_EXECUTION_REGISTRY.yaml").write_text(text, encoding="utf-8", newline="")
    prompt = Path("docs/governance/cep/PROMPTS/CEP-073_EXECUTION_PROMPT.md").read_text(encoding="utf-8")
    criteria = re.findall(r"^\d+\. `(IMB-\d+)` — (.+)$", prompt, flags=re.M)
    assert len(criteria) == 12
    helper.write_csv("docs/governance/cep/evidence/CEP-073_ACCEPTANCE_MAPPING.csv",
                     ["AC", "IMB", "Criterion", "Result", "Evidence", "Boundary"],
                     [[i, imb, criterion, "PASS_QUALIFIED_DEVELOPMENT", "CEP-073-EV-002" if imb == "IMB-0103" else "CEP-073-EV-003", "Defined synthetic current PostgreSQL scenarios; no Production capacity/SLA claim"] for i, (imb, criterion) in enumerate(criteria, 1)])
    helper.write_csv("docs/governance/cep/evidence/CEP-073_EVIDENCE_MANIFEST.csv", ["Evidence ID", "Path", "Result", "Limitation"],
                     [[f"CEP-073-EV-{i:03}", (OUT / name).as_posix(), outcome, "Qualified Development only"] for i, name, outcome in [
                         (1, "ENTRY.json", "GATE_DEPENDENCY_AND_EXT0023_ENTRY_PASS"),
                         (2, "MIGRATION/PRESERVATION.json", "42_POST_ENTRY_POSTGRESQL_CHECKS_PASS"),
                         (3, "VALIDATION.json", "10_DISTINCT_RUNTIME_CASES_AND_PLANS_PASS"),
                         (4, "RETRY_SOURCE_AFTER.json", "EXACT_FINAL_SOURCE_MANIFEST"),
                         (5, "TEST_BASELINE_REPAIR.json", "ISOLATED_TEST_CATALOG_REPAIRED"),
                         (6, "RESULT.json", "FRONTIER_AND_EXTERNAL_PREREQUISITES_RECONCILED"),
                     ]])
    helper.write_csv("docs/governance/cep/evidence/CEP-073_CHANGE_MANIFEST.csv", ["Path", "Change", "SHA256"],
                     [[p, "VERIFICATION_HARNESS_ONLY", hashlib.sha256(Path(p).read_bytes()).hexdigest()] for p in ("scripts/cep073_capture.py", "tests/test_cep073_runtime.py")])
    print("CEP073 COMPLETE12/12;GATE08 contributions advanced;72 COMPLETE/4 PARTIAL/3 BLOCKED;frontier[]")


if __name__ == "__main__":
    main()
