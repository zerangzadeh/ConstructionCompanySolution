"""Close the supplied Product Decision; preserve CEP states and exact Gate criteria."""

import hashlib
import json
import re
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
PRODUCTION = ROOT / "docs/governance/production"
PREFIX = "docs/governance/production/evidence/20261028_legacy_decision"


def load(path):
    return json.loads(path.read_text("utf-8"))


def main():
    runtime = OUT / "runtime"
    empty = load(runtime / "empty_RESULT.json")
    populated = load(runtime / "populated_RESULT.json")
    recovery = load(runtime / "RECOVERY_RESULT.json")
    regression = load(runtime / "REGRESSION.json")
    assert all(value["result"] == "PASS" for value in (empty, populated, recovery))
    assert regression["failed"] == 0 and load(OUT / "SHUTDOWN.json")["result"] == "PASS"
    count = int(re.search(r"Ran (\d+) tests?", (runtime / "REGRESSION.txt").read_text("utf-8")).group(1))
    gate_path = PRODUCTION / "GATE11_EVALUATION.json"
    gate = load(gate_path)
    before = load(OUT / "GATE11_EVALUATION_BEFORE.json")
    assert [x["requirement"] for x in gate["clauses"]] == [x["requirement"] for x in before["clauses"]]
    gate.update({
        "at": datetime.now(UTC).isoformat(),
        "overall_readiness": "BOOTSTRAP_AND_RETIRED_POPULATION_QUALIFIED_EXTERNAL_PRODUCTION_EVIDENCE_REQUIRED",
        "requirements_satisfied": 3,
        "root_boundary": "Required EXT0018/0020/0021/0022 Production-scoped evidence remains absent. Legacy Payment population and bootstrap authority are resolved by the supplied Human decision.",
        "next_action": "Disposition the remaining Production statutory/recovery/target/operating contracts; no Legacy Payment population, zero-history, bootstrap or retention-destruction approval is needed for the implemented non-destructive migration path.",
        "remaining_safe_executable_prerequisites_before_human_policy": [],
        "legacy_payment_bootstrap": {
            "status": "RESOLVED_QUALIFIED_ANY_POPULATION",
            "authority": "docs/governance/production/LEGACY_PAYMENT_RETIRED_DECISION_20261028.md",
            "empty": PREFIX + "/runtime/empty_RESULT.json",
            "populated": PREFIX + "/runtime/populated_RESULT.json",
            "recovery": PREFIX + "/runtime/RECOVERY_RESULT.json",
            "regression": PREFIX + "/runtime/REGRESSION.json",
            "raw_retired_rows_preserved": populated["legacy_rows"],
            "physical_table_drops": 0,
            "financial_targets_created": 0,
            "applied_migrations_replayed": False,
            "production_action": False,
        },
        "safe_alternatives_exhausted": [
            "Applied direct Human retired-data decision; removed Development/loopback/twelve-condition/population gates",
            "Replaced physical table drops with state-only retirement; original rows and relationships preserved",
            "Qualified empty and populated production-settings Linux paths, unchanged prior snapshot and independent GL data",
            "Qualified native complete changed-schema backup/restore and affected active-financial regressions",
            "Retained existing statutory/recovery/deployment/operating qualification and exact approval scopes; no unsupported Production activation or owner/custody appointment",
        ],
    })
    gate.pop("specific_executable_blocker", None)
    for clause in gate["clauses"]:
        if clause["id"] == "C3":
            clause.update(status="SATISFIED_QUALIFIED_NONPRODUCTION_RUNTIME", evidence="Required bounded runtime evidence now includes complete empty/populated production-settings bootstrap and changed-schema restore. Statutory Production applicability/activation remains an external-production-contract condition C4; no actual Production action inferred.")
        elif clause["id"] == "C4":
            clause["evidence"] = "EXT0018/0020/0021/0022 Production statutory applicability, recovery objectives/custody, actual target/configuration and operating acceptance evidence remain absent. Legacy Payment migration/bootstrap semantics are resolved."
        elif clause["id"] == "C5":
            clause["evidence"] = "Required Production-scoped external evidence remains unresolved; Legacy Payment is not a blocker."
    assert sum(row["status"].startswith("SATISFIED") for row in gate["clauses"]) == 3
    gate["qualification"]["empty_production_settings_bootstrap"] = "PASS_ISOLATED_LINUX_NONPRODUCTION"
    gate["qualification"]["populated_production_settings_migration"] = "PASS_RETIRED_LEGACY_DATA_PRESERVED"
    gate["qualification"]["retirement_regression_tests"] = count
    gate["qualification"]["retirement_contract_tests_local"] = 2
    gate["qualification"]["retirement_recovery"] = PREFIX + "/runtime/RECOVERY_RESULT.json"
    gate["qualification"]["bootstrap_authority_guard_tests"] = "Prior rejection tests superseded by Human Product Decision; new production/remote preservation and no-drop contract tests PASS"
    gate_path.write_text(json.dumps(gate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report_path = PRODUCTION / "PRODUCTION_READINESS_ASSESSMENT.md"
    report = report_path.read_text("utf-8")
    report = report.replace("2/5 exact Pass Condition conjuncts satisfied", "3/5 exact Pass Condition conjuncts satisfied")
    report = report.replace("No contract, Product Decision, dependency, completed CEP or gate criterion changed.", "The supplied Human Product Decision supersedes the Legacy Payment restrictions. Canonical Gate criteria, dependency graph and completed CEP states remain unchanged.")
    report = report.replace("Current SHA/1,603 source files", "Current SHA plus bounded uncommitted decision changes/1,604 frozen source files")
    lines = report.splitlines()
    replacements = {
        "| C3 |": "| C3 | required runtime/production evidence is available | SATISFIED for approved non-production qualification | Complete production-settings empty/populated Linux bootstrap, exact retired/active-row preservation, complete native recovery and affected regressions now close the prior bootstrap gap. Retained statutory qualification remains valid in its approved scope; Production applicability belongs to C4. |",
        "| C5 |": "| C5 | no unresolved production-certification blocker remains | HUMAN_DECISION_REQUIRED, derived from C4 | Required external Production evidence remains absent. Legacy Payment population, Development guards and bootstrap are resolved; no GATE-12 sign-off or actual deployment prerequisite is invented. |",
        "| Database/migrations |": "| Database/migrations | SATISFIED non-production empty and populated production-settings qualification | Full 443-node graph, deploy/drift checks and any-population retired-data retention PASS. Four raw legacy tables survive state retirement; active GL rows and accepted DMS/audit history remain intact. No Production database or prior applied migration was mutated/replayed. |",
        "| Deploy/rollback/cutover |": "| Deploy/rollback/cutover | Bootstrap/reference qualified; real action PRODUCTION_ONLY_REQUIRED | Empty/populated production-settings bootstrap now passes without zero-history or Development-only gates. Prior compatible HTTPS rollback and procedures retained; actual Production deployment/cutover still needs separate authority. |",
        "| EXT-0021 |": "| EXT-0021 | Approved Production target/configuration and target evidence for secrets/process/static/media/TLS | The qualified reference and non-destructive bootstrap are complete. Existing topology approval is explicitly non-production; actual Production selection/evidence remains outside it. Legacy Payment is not a remaining condition. | Human Decision Authority and designated release/deployment owner; pre-deployment target/configuration selection |",
    }
    report = "\n".join(next((new for prefix, new in replacements.items() if line.startswith(prefix)), line) for line in lines) + "\n"
    start = report.index("No " + chr(96) + "DEVELOPMENT_FIX_REQUIRED")
    end = report.index("Retained fiscal qualification", start)
    report = report[:start] + (
        "The supplied [Human retired-data decision](LEGACY_PAYMENT_RETIRED_DECISION_20261028.md) "
        "resolves the former migration authority boundary. Documents 0012 and billing 0018 "
        "now have no Development/loopback, zero-population or twelve-condition gate. Billing 0018 "
        "and payments 0007 remove only model state, preserving all four original raw tables. "
        "New retained evidence is classified RETIRED_LEGACY_DATA; prior accepted snapshots remain unchanged. "
        "No Treasury/GL/AP/AR mapping, posting, opening balance or replacement payment is inferred.\n\n"
        "Empty and populated paths ran with production settings, DEBUG false, PostgreSQL TLS and "
        "the approved Linux runtime. The populated case retains original Payment/allocation/settlement/"
        "document-link rows, generic links, audit identities and unrelated draft GL data. Native "
        "complete backup/restore proves full changed-schema integrity. Existing applied migrations "
        "are not replayed; previously removed Development data is not reconstructed. "
        "Historical failed-bootstrap evidence remains retained and is superseded only for this "
        "resolved boundary.\n\n"
    ) + report[end:]
    start = report.index("For the newly proven bootstrap boundary")
    end = report.index("## Go/no-go", start)
    report = report[:start] + (
        "No additional Human decision about Legacy Payment population, empty-target eligibility "
        "or historical cash disposition is required. Physical disposal remains unauthorized; "
        "the implemented path preserves the records and needs no disposal approval.\n\n"
    ) + report[end:]
    start = report.index("## Executed current-release closeout")
    report = report[:start] + (
        "## Current retired-data decision closeout\n\n"
        f"Updated affected Linux regression: **{count}/{count} PASS**; updated local contract tests: "
        "**2/2 PASS**. Both empty and populated production-settings paths pass the full 443-node "
        f"graph. The populated case preserves **{populated['legacy_rows']} original rows across four "
        "raw retired tables**, two retained evidence records, original typed/generic links, audit "
        "identities and independent GL records, including an unchanged prior accepted snapshot. "
        f"Native restore preserves **{recovery['tables']} tables / {recovery['rows']} rows / "
        f"{recovery['constraints']} constraints / {recovery['sequences']} sequences** exactly. "
        "Failed synthetic fixture attempts are retained; only fixture construction was corrected. "
        "Prior 21 Linux boundary tests, six configuration tests and 56 HTTPS cases retain their "
        "original scope; prior Production-rejection contract tests are historical and superseded "
        "by this explicit decision. Financial runtime/authorization code is unchanged. Migration "
        "guard/retention behavior and retired-source terminology changed under the supplied decision.\n\n"
        "Detailed [new qualification](evidence/20261028_legacy_decision/COMPLETION_REPORT.md) records "
        "source hashes, commands, limitations and cleanup. All owned services/guest stopped; private "
        "synthetic data and failed attempts retained. All 79 CEP records and other gates remain "
        "unchanged. **GATE-11 NOT_PASSED, 3/5**: only required external Production-scoped evidence "
        "and its no-unresolved-blocker consequence remain. No Production action, final certification, "
        "Human Sign-off or Git write occurred.\n"
    )
    report_path.write_text(report, encoding="utf-8")

    ref_path = PRODUCTION / "PRODUCTION_REFERENCE_AND_CUTOVER.md"
    ref = ref_path.read_text("utf-8")
    (OUT / "PRODUCTION_REFERENCE_AND_CUTOVER_BEFORE.md").write_text(ref, encoding="utf-8")
    ref = re.sub(r"(?s)   Fresh bootstrap is currently blocked.*?(?=\n5\. Collect)", (
        "   Fresh bootstrap now qualifies under the supplied Legacy Payment retired decision, "
        "with empty or populated retired tables. Preserve the original rows/relationships and "
        "remove only runtime model state; no zero-population, Development or historic cash-mapping "
        "gate applies. Existing applied migrations are not replayed. Retention disposal remains "
        "separately governed.\n"
    ), ref)
    ref = re.sub(r"(?s)EXT-0021\nmust also resolve.*?populated unapproved targets\.", (
        "Legacy Payment migration/bootstrap is resolved by the "
        "[Human decision](LEGACY_PAYMENT_RETIRED_DECISION_20261028.md) and any-population "
        "non-destructive qualification. No further Legacy Payment approval is requested."
    ), ref)
    ref_path.write_text(ref, encoding="utf-8")

    registry_path = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
    original = registry_path.read_text("utf-8")
    registry = yaml.safe_load(original)
    baseline = load(ROOT / "docs/governance/production/evidence/20261028/ENTRY.json")
    assert hashlib.sha256(json.dumps(registry["ceps"], sort_keys=True, default=str).encode()).hexdigest() == baseline["ceps_before_sha256"]
    live = registry["gates"]["GATE-11"]
    live.update(
        requirements_satisfied=3, requirements_total=5,
        source="CANONICAL_GATE11_RECHECK_AFTER_HUMAN_RETIRED_DATA_DECISION",
        note="3/5 exact conjuncts satisfied. Legacy Payment no longer gates bootstrap: empty/populated production-settings Linux migration, original-row retention, native complete recovery and affected regressions PASS. No physical drops or financial reconstruction. Required EXT0018/0020/0021/0022 Production evidence still absent; CEPs/GATE08/10 retained. No actual Production or GATE12 Sign-off prerequisite invented.",
        legacy_payment_bootstrap=gate["legacy_payment_bootstrap"],
        remaining_blocker={
            "clause": "required external production evidence is available",
            "dependencies": ["EXT-0018", "EXT-0020", "EXT-0021", "EXT-0022"],
            "legacy_payment": "RESOLVED_NOT_A_BLOCKER",
            "classification": "HUMAN_PRODUCTION_SCOPE_AND_EXTERNAL_EVIDENCE_REQUIRED",
        },
    )
    live["history"].append({
        "date": "2026-10-28", "status": "NOT_PASSED",
        "reason": "Applied supplied Human Product Decision retiring Legacy Payment independent of population. Removed Development-only readiness gates and physical table drops; qualified empty/populated production-settings graph, retained rows/accepted evidence/GL and native complete recovery. Runtime evidence clause now satisfied:3/5. Remaining external Production scope/contracts not inferred; no CEP reopened or Production/Git action.",
        "evidence": PREFIX + "/COMPLETION_REPORT.md",
    })
    replacement = textwrap.indent(yaml.safe_dump({"GATE-11": live}, sort_keys=False, allow_unicode=True, width=140), "  ")
    updated, matches = re.subn(r"(?ms)^  GATE-11:\n.*?(?=^[a-zA-Z_][a-zA-Z_0-9]*:)", lambda _: replacement, original)
    assert matches == 1
    updated = updated.replace(
        "pending_checkpoint_scope: PRODUCTION_READINESS_20261028_EVIDENCE_AND_GATE_RECONCILIATION_UNCOMMITTED",
        "pending_checkpoint_scope: PRODUCTION_READINESS_AND_RETIRED_LEGACY_DATA_20261028_UNCOMMITTED",
    )
    after = yaml.safe_load(updated)
    assert after["ceps"] == registry["ceps"]
    assert all(after["gates"][key] == value for key, value in registry["gates"].items() if key != "GATE-11")
    registry_path.write_text(updated, encoding="utf-8")
    print(f"Legacy bootstrap resolved; GATE11 recomputed 3/5; {count} affected regressions PASS")


if __name__ == "__main__":
    main()
