"""Compute the unchanged five-clause Gate and update only supported live metadata."""

import hashlib
import json
import re
import textwrap
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text("utf-8"))


def main():
    entry = load(OUT / "ENTRY.json")
    runtime = OUT / "runtime"
    current = load(runtime / "CURRENT_RELEASE.json")
    tests = load(runtime / "CURRENT_BOUNDARY_TESTS.json")
    shutdown = load(OUT / "SHUTDOWN.json")
    assert current["result"] == "PASS" and tests["failed"] == 0
    assert shutdown["result"] == "PASS"
    log = (runtime / "CURRENT_BOUNDARY_TESTS.txt").read_text("utf-8")
    test_count = int(re.search(r"Ran (\d+) tests?", log).group(1))
    assert "\nOK" in log
    registry_path = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
    original = registry_path.read_text("utf-8")
    registry = yaml.safe_load(original)
    assert (
        hashlib.sha256(
            json.dumps(registry["ceps"], sort_keys=True, default=str).encode()
        ).hexdigest()
        == entry["ceps_before_sha256"]
    )
    contributors = {
        "IMB-0083": "CEP-069",
        "IMB-0098": "CEP-070",
        "IMB-0099": "CEP-071",
        "IMB-0100": "CEP-072",
        "IMB-0101": "CEP-072",
        "IMB-0104": "CEP-074",
        "IMB-0105": "CEP-075",
        "IMB-0106": "CEP-076",
        "IMB-0107": "CEP-077",
    }
    assert all(
        registry["ceps"][cep]["execution"]["status"] == "COMPLETE"
        for cep in contributors.values()
    )
    assert registry["gates"]["GATE-10"]["status"] == "PASS"
    assert registry["gates"]["GATE-08"]["status"] == "PASS"
    clauses = [
        {
            "id": "C1",
            "requirement": "GATE-10 Representative UAT Completion has PASSED",
            "status": "SATISFIED",
            "evidence": "Retained canonical GATE10 PASS; 44/44 cases, 48 mappings; no reassessment",
        },
        {
            "id": "C2",
            "requirement": "all required Production Certification IMB items are complete",
            "status": "SATISFIED_RECORDED_APPROVED_EXECUTION_SCOPE",
            "evidence": "All nine required IMBs have completed scoped contributors; no actual Production certification inferred",
        },
        {
            "id": "C3",
            "requirement": "required runtime/production evidence is available",
            "status": "PARTIAL_HUMAN_DECISION_REQUIRED",
            "evidence": "Retained qualifications and current Linux upgrade/runtime/rollback PASS; empty production-settings bootstrap blocked by explicit historical Development-only disposition. Production statutory activation scope also absent; no guard bypass",
        },
        {
            "id": "C4",
            "requirement": "required external production evidence is available",
            "status": "HUMAN_DECISION_REQUIRED",
            "evidence": "EXT0018/0020/0021/0022 approvals explicitly non-production; actual Production applicability/migration/recovery/target/operating evidence absent",
        },
        {
            "id": "C5",
            "requirement": "no unresolved production-certification blocker remains",
            "status": "HUMAN_DECISION_REQUIRED",
            "evidence": "Unresolved Production contract/authority and resulting bootstrap/activation evidence boundary; actual deployment and GATE12 Sign-off not invented prerequisites",
        },
    ]
    satisfied = sum(row["status"].startswith("SATISFIED") for row in clauses)
    assert satisfied == 2
    external = load(OUT / "EXTERNAL_PHASE_ROWS.json")
    external = [
        row
        for row in external
        if row["CEP ID"] in {"CEP-069", "CEP-070", "CEP-071", "CEP-072"}
    ]
    assert len(external) == 4 and all(
        row["Blocks Production?"] == "YES" and row["Required Gate"] == "GATE-11"
        for row in external
    )
    report = ROOT / "docs/governance/production/PRODUCTION_READINESS_ASSESSMENT.md"
    result = {
        "at": datetime.now(UTC).isoformat(),
        "client_date": "2026-10-28",
        "candidate_head": entry["head"],
        "branch": "main",
        "overall_readiness": "NONPRODUCTION_RELEASE_QUALIFIED_PRODUCTION_CONTRACT_AND_BOOTSTRAP_AUTHORITY_REQUIRED",
        "gate": "GATE-11",
        "status": "NOT_PASSED",
        "canonical_source": "evidence/20261028/SOURCE_CONTRACT.json; exact GATE11 row, archive/member SHA identities verified",
        "requirements_satisfied": satisfied,
        "requirements_total": len(clauses),
        "requirement_count_semantics": "Five exact conjuncts of canonical Pass Condition; scoped IMB completion is distinct from actual Production certification",
        "clauses": clauses,
        "required_imb_contributors": contributors,
        "completed_required_imb_execution_contributions": 9,
        "external_production_phase_rows": external,
        "root_boundary": "Production-scoped release/migration/statutory/recovery/operating authority and evidence are absent; non-production-only approvals cannot be broadened by Codex",
        "specific_executable_blocker": load(OUT / "BOOTSTRAP_BOUNDARY.json"),
        "qualification": {
            "current_linux_tests": test_count,
            "failed": 0,
            "configuration_guard_tests": 6,
            "bootstrap_authority_guard_tests": 2,
            "https_cases": sum(step["http_cases"] for step in current["web"]),
            "new_migrations": 6,
            "schema_and_deploy": "PASS_UPGRADE_ON_ISOLATED_CLONE",
            "empty_production_settings_bootstrap": "BLOCKED_NOT_PASS",
            "preservation": "runtime/MIGRATION_PRESERVATION.json and CATALOG_DELTA.json",
            "source_build_template_reuse": "evidence/20261028/REUSE_AND_BUILD_CHECKS.json",
            "limits": "Changed-boundary tests use a fresh migrated/flush fixture; statutory test-only Development override is retained; no capacity, global full-suite, actual Production install or cold image rebuild claim",
        },
        "remaining_safe_executable_prerequisites_before_human_policy": [],
        "safe_alternatives_exhausted": [
            "Reused and resumed approved isolated Linux runtime; six-migration upgrade/preservation and current release runtime/HTTPS rollback executed",
            "Actually attempted empty production-settings bootstrap; retained explicit authority failure, inspected downstream local-Development guard and existing guard tests",
            "Completed unaffected qualification using clean migrated synthetic fixture; this is expressly not Production bootstrap proof",
            "Reused adopted statutory/recovery/deployment/operating decisions and measured evidence within exact scopes; prepared consolidated Production extension and narrow empty-target-only policy recommendation",
            "Did not change DEBUG, fake migration history, reinterpret demo-data authorization or invent Production custody/owners to force acceptance",
        ],
        "next_action": "Human Decision Authority dispositions the four Production-phase extensions, including explicit empty-target retirement/bootstrap semantics; then implement/qualify only the authorized bootstrap/statutory envelope in isolated non-production and recompute this exact Gate",
        "production_only_later": [
            "Selected actual private credentials/certificates/network/storage bindings",
            "Separately authorized deployment/migration/activation/cutover",
            "Actual operational delivery/restore/continuing-operation evidence where selected",
            "Later final Production Certification/Human Business Sign-off under applicable authority",
        ],
        "production_action": False,
        "human_signoff": "NOT_EXECUTED",
        "final_production_certification": "NOT_EXECUTED",
        "git_writes": False,
        "report": report.relative_to(ROOT).as_posix(),
    }
    gate_path = ROOT / "docs/governance/production/GATE11_EVALUATION.json"
    gate_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    gate = registry["gates"]["GATE-11"]
    gate.update(
        {
            "status": "NOT_PASSED",
            "source": "CANONICAL_FIVE_CLAUSE_PRODUCTION_READINESS_EVALUATION",
            "evaluated_at": "2026-10-28",
            "evidence": gate_path.relative_to(ROOT).as_posix(),
            "requirements_satisfied": satisfied,
            "requirements_total": 5,
            "current_release_qualification": "docs/governance/production/evidence/20261028/runtime/CURRENT_RELEASE.json",
            "readiness_report": report.relative_to(ROOT).as_posix(),
            "note": "2/5 exact conjuncts satisfied; nine scoped IMB outcomes and GATE08/10 retained. Current Linux upgrade/runtime/rollback qualified. Empty production-settings bootstrap actually rejects Development-only Legacy Payment disposition; statutory production envelope also unauthorized. Required EXT0018/0020/0021/0022 Production evidence not supplied by non-production-only approvals. No actual deployment or GATE12 Human Sign-off invented as a pre-Gate requirement.",
            "remaining_blocker": {
                "clause": "required external production evidence is available; unresolved bootstrap/activation evidence also affects runtime/no-blocker clauses",
                "classification": "HUMAN_PRODUCTION_SCOPE_AND_MIGRATION_POLICY_REQUIRED",
                "evidence": "docs/governance/production/evidence/20261028/BOOTSTRAP_BOUNDARY.json",
            },
        }
    )
    gate.setdefault("history", []).append(
        {
            "date": "2026-10-28",
            "status": "NOT_PASSED",
            "reason": "Exact canonical recheck 2/5: reused qualified evidence, completed current Linux release/schema delta and concrete reference/template/cutover contracts. Proven empty production-settings bootstrap hits explicit Development-only retirement guard; required external Production scope/policy/owner evidence remains absent. Completed CEPs and other gates unchanged; no Production/Git action.",
            "evidence": gate_path.relative_to(ROOT).as_posix(),
        }
    )
    replacement = textwrap.indent(
        yaml.safe_dump(
            {"GATE-11": gate}, sort_keys=False, allow_unicode=True, width=140
        ),
        "  ",
    )
    updated, count = re.subn(
        r"(?ms)^  GATE-11:\n.*?(?=^[a-zA-Z_][a-zA-Z_0-9]*:)",
        lambda _: replacement,
        original,
    )
    assert count == 1
    # Ordinary current-HEAD reconciliation, without rewriting CEP Git histories.
    start = updated.index("repository_state:\n")
    end = updated.index("execution_frontier:\n", start)
    state = registry["repository_state"]
    state.update(
        {
            "branch": "main",
            "last_reconciled_head": entry["head"],
            "origin_main": entry["origin_main"],
            "integration_checkpoint": entry["head"],
            "last_reconciled_at": "2026-10-28",
            "pending_checkpoint_scope": "PRODUCTION_READINESS_20261028_EVIDENCE_AND_GATE_RECONCILIATION_UNCOMMITTED",
            "metadata_boundary": "Session began clean at c9fe1d7, matching cached and live remote main; current readiness files and Gate/repository metadata remain uncommitted. Observed Git state only; no add/commit/push/merge or per-CEP Git-history rewrite.",
        }
    )
    state_text = yaml.safe_dump(
        {"repository_state": state}, sort_keys=False, allow_unicode=True, width=140
    )
    updated = updated[:start] + state_text + updated[end:]
    after = yaml.safe_load(updated)
    assert after["ceps"] == registry["ceps"]
    assert after["execution_frontier"] == registry["execution_frontier"]
    assert all(
        after["gates"][key] == value
        for key, value in registry["gates"].items()
        if key != "GATE-11"
    )
    registry_path.write_text(updated, encoding="utf-8")
    outcomes = Counter(
        item["execution"]["status"]
        for key, item in after["ceps"].items()
        if int(key.split("-")[1]) <= 79
    )
    assert outcomes == {"COMPLETE": 79}, outcomes
    text = report.read_text("utf-8")
    text += f"\n## Executed current-release closeout\n\nCurrent Linux changed-boundary tests: **{test_count}/{test_count} PASS**; secure configuration tests: **6/6 PASS**. Actual HTTPS transition/security cases: **{sum(step['http_cases'] for step in current['web'])}/56 PASS** across previous/current/rollback/return. Six new migrations, upgrade deploy/drift checks, exact business-row preservation and explained catalog deltas PASS. Fresh production-settings bootstrap remains **BLOCKED**, explicitly distinct from the successful upgrade and migrated test fixture. All owned services/guest stopped; private synthetic resources retained. No product/schema/permission policy changed; no CEP reopened; 79/79 COMPLETE and GATE08/10 PASS retained. GATE11 is **NOT_PASSED, 2/5**; C3/C4/C5 require the exact Production contract/authority disposition above.\n"
    report.write_text(text, encoding="utf-8")
    print(
        f"Recorded GATE11 NOT_PASSED: {satisfied}/5; {test_count} Linux tests; all CEPs preserved"
    )


if __name__ == "__main__":
    main()
