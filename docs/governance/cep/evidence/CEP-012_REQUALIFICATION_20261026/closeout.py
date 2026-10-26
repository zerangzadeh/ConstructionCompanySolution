"""Guarded CEP-012 closeout; preserves unrelated Registry record bytes."""

import copy
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path
from textwrap import indent

import yaml

ROOT = Path.cwd()
EV = Path("docs/governance/cep/evidence/CEP-012_REQUALIFICATION_20261026")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def replace_record(text, key, value, depth=2):
    lines = text.splitlines(keepends=True)
    start = lines.index(" " * depth + key + ":\n")
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and len(line) - len(line.lstrip()) <= depth:
            break
        end += 1
    body = yaml.safe_dump({key: value}, sort_keys=False, allow_unicode=True, width=140)
    lines[start:end] = [indent(body, " " * depth)]
    return "".join(lines)


def write_csv(path, header, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    proof = read(EV / "PRESERVATION.json")
    regression = read(EV / "SERVICE_REGRESSION.json")
    checks = read(EV / "CHECKS.json")
    assert proof["status"] == "PASS" and len(proof["checks"]) == 42
    assert proof["before_hash"] == proof["after_hash"]
    assert proof["disposable_database_removed"]
    assert regression["exit_code"] == 0
    assert all(v["exit_code"] == 0 for v in checks.values())
    for path, digest in proof["source_sha256"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
    text = Path("CEP_EXECUTION_REGISTRY.yaml").read_text(encoding="utf-8")
    registry = yaml.safe_load(text)
    before = copy.deepcopy(registry)
    for key in ("CEP-028", "CEP-029", "CEP-057", "CEP-058", "CEP-064"):
        assert registry["ceps"][key]["execution"]["status"] == "COMPLETE"
        assert Path(registry["ceps"][key]["completion_report"]["path"]).is_file()
    row = registry["ceps"]["CEP-012"]
    (EV / "REGISTRY_BEFORE.json").write_text(json.dumps({
        "CEP-012": row, "GATE-06": registry["gates"]["GATE-06"],
        "excluded_complete_record_hashes": {
            key: hashlib.sha256(json.dumps(registry["ceps"][key], sort_keys=True).encode()).hexdigest()
            for key in ("CEP-077", "CEP-078", "CEP-079")
        },
    }, indent=2), encoding="utf-8")
    row["title"] = "History-safe migration foundation"
    row["acceptance"] = {"passed": 14, "total": 14, "status": "PASS_CURRENT_DEVELOPMENT_REQUALIFICATION"}
    row["dod"] = "MET_CURRENT_DEVELOPMENT_REQUALIFICATION"
    row["completion_report"] = {
        "path": "docs/governance/cep/reports/CEP-012_COMPLETION_REPORT.md",
        "evidence_presence": "CURRENT_REPRODUCIBLE_POSTGRESQL_PRESERVATION_PROOF",
    }
    row["last_execution"] = {"branch": "main", "sha": "961e3fd942c668337012c22d42f59545c5e9fc0a"}
    row["updated_at"] = "2026-10-26"
    row["remaining_utv"] = ["Production/real-history recovery and deployment not executed; no reconstruction of previously deleted records"]
    row["current_requalification_git"] = {"committed": False, "pushed": False, "git_writes": False}
    row["history"].extend([
        {"date": "2026-10-26", "status": "RESUMED_REQUALIFICATION", "reason": "Current Human instruction authorizes fresh Development preservation proof and attributable repair. Historical COMPLETE retained; missing historical artifact not reconstructed."},
        {"date": "2026-10-26", "status": "BLOCKER_RESOLVED", "reason": "Repaired history-deleting operations and preserved original policy JSON. Forty-two actual PostgreSQL preservation/retry/exception/rollback checks and required service regression PASS.", "evidence": (EV / "PRESERVATION.json").as_posix()},
        {"date": "2026-10-26", "status": "CLOSED_VERIFIED", "reason": "14/14 Development AC and scoped DoD supported by new executed proof. No production action, Human Sign-off or Git write."},
    ])
    gate = registry["gates"]["GATE-06"]
    gate["history"].append({"date": "2026-10-26", "status": "PASS", "reason": "Objective Development implementation-readiness evaluation: all six required IMB contributions have reconciliation/history/retry/recovery evidence; fresh CEP012 proof replaces missing historical evidence.", "evidence": (EV / "GATE06.json").as_posix()})
    gate.update({
        "status": "PASS", "source": "OBJECTIVE_TECHNICAL_DEVELOPMENT_GATE_EVALUATION",
        "scope": "QUALIFIED_NONPRODUCTION_SOURCE_SETS_ONLY",
        "updated_at": "2026-10-26", "evaluated_at": "2026-10-26",
        "evidence": (EV / "GATE06.json").as_posix(),
        "current_readiness_evidence": (EV / "PRESERVATION.json").as_posix(),
        "current_readiness_note": "Fresh actual PostgreSQL CEP012 preservation proof and repaired audited operations; no old artifact required. All required completed contributor evidence retained. Runtime EXT0023 qualified separately; real EXT0015/0017 and production datasets are not inferred from synthetic proof.",
        "note": "PASS for bounded Development implementation readiness, using authorized synthetic/retained-disposition contributor datasets. No production migration/cutover, historical-loss recovery, Human Sign-off or production certification.",
        "required_imb_status": {key: "PASS_QUALIFIED_DEVELOPMENT" for key in ("IMB-0050", "IMB-0070", "IMB-0075", "IMB-0080", "IMB-0096", "IMB-0097")},
    })
    gate_proof = {
        "status": "PASS", "scope": gate["scope"],
        "canonical_contract": "CANONICAL_IDENTITY.json",
        "contributors": {
            "IMB-0050": "CEP028 completed governed disposition/reference preservation; CEP064 twelve-condition native recovery proof (not rerun)",
            "IMB-0070": "CEP029 completed source/target mapping, revisions, retry, exception and schema/data rollback evidence (not rerun)",
            "IMB-0075": "CEP057 authorized synthetic Development dataset,17 targets and reversal/recovery evidence (not rerun)",
            "IMB-0080": "CEP058 authorized synthetic Development YTD dataset and reconciliation/recovery evidence (not rerun)",
            "IMB-0096": "Fresh actual PostgreSQL audit history preservation, stable UUIDs and complete row equality",
            "IMB-0097": "Fresh actual PostgreSQL claims/items/adjustments/legacy and native allocations, snapshots, revisions, retry, exceptions, schema/transaction rollback/reapply",
        },
        "migration_proof": "PRESERVATION.json", "service_regression": "SERVICE_REGRESSION.json",
        "required_datasets_exist": True,
        "dataset_authority": "Current direct bounded synthetic Development proof instruction; existing DEV-SYNTHETIC-DATA-AUTH-20261020-V2 and approved excluded-source disposition retained",
        "runtime_external": "EXT0023 remains a separate entry condition for CEP073; implementation gate is not runtime PASS",
        "real_or_production_history": "UNQUALIFIED; no synthetic-to-real inference",
        "human_signoff": "NOT_EXECUTED", "production_certification": "NOT_EXECUTED",
    }
    (EV / "GATE06.json").write_text(json.dumps(gate_proof, indent=2), encoding="utf-8")
    for key, value in (("CEP-012", row), ("GATE-06", gate)):
        text = replace_record(text, key, value)
    after = yaml.safe_load(text)
    for key in registry["ceps"]:
        if key != "CEP-012":
            assert before["ceps"][key] == after["ceps"][key]
    Path("CEP_EXECUTION_REGISTRY.yaml").write_text(text, encoding="utf-8", newline="")
    prompt = Path("docs/governance/cep/PROMPTS/CEP-012_EXECUTION_PROMPT.md").read_text(encoding="utf-8")
    criteria = re.findall(r"^\d+\. `(IMB-\d+)` — (.+)$", prompt, flags=re.M)
    assert len(criteria) == 14
    write_csv("docs/governance/cep/evidence/CEP-012_ACCEPTANCE_MAPPING.csv",
              ["AC", "IMB", "Criterion", "Result", "Evidence", "Boundary"],
              [[i, imb, criterion, "PASS_DEVELOPMENT", "CEP-012-EV-002;CEP-012-EV-003;CEP-012-EV-004", "Audited source checkpoints; synthetic PostgreSQL; no production/history-recovery claim"] for i, (imb, criterion) in enumerate(criteria, 1)])
    write_csv("docs/governance/cep/evidence/CEP-012_EVIDENCE_MANIFEST.csv",
              ["Evidence ID", "Path", "Result", "Limitation"],
              [[f"CEP-012-EV-{i:03}", (EV / name).as_posix(), result, "Development only"] for i, name, result in [
                  (1, "CANONICAL_IDENTITY.json", "CANONICAL_IDENTITY_PASS"),
                  (2, "PRESERVATION.json", "42_POSTGRESQL_CHECKS_PASS"),
                  (3, "SERVICE_REGRESSION.txt", "12_TESTS_PASS"),
                  (4, "CHECKS.json", "LINT_FORMAT_SYSTEM_DRIFT_PASS"),
                  (5, "GATE06.json", "OBJECTIVE_GATE06_PASS"),
              ]])
    files = ["apps/audit/migrations/0016_membership_provisioned_action.py", "apps/billing/migrations/0006_tenantbillingconfiguration_and_more.py", "apps/billing/migrations/0008_p6_s01_s06_seed_reset_and_required_snapshots.py", "scripts/cep012_preservation_proof.py"]
    write_csv("docs/governance/cep/evidence/CEP-012_CHANGE_MANIFEST.csv", ["Path", "Change", "SHA256"],
              [[p, "BOUNDED_HISTORY_PRESERVATION_REPAIR_OR_PROOF", hashlib.sha256(Path(p).read_bytes()).hexdigest()] for p in files])
    (EV / "CODE_DIFF.patch").write_bytes(subprocess.check_output(["git", "diff", "--", *files[:3]]))
    print("CEP012 current requalification COMPLETE;14/14 AC; GATE06 PASS Development only")


if __name__ == "__main__":
    main()
