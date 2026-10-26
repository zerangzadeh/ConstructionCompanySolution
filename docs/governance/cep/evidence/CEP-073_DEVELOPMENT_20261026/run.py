"""Qualify exact current Development build, then execute canonical scenarios."""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path.cwd()
OUT = Path("docs/governance/cep/evidence/CEP-073_DEVELOPMENT_20261026")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "docs/governance/cep/evidence/CEP-012_REQUALIFICATION_20261026"))
from closeout import replace_record


def freeze():
    paths = set()
    for base in ("apps", "core", "config", "templates", "tests", "scripts"):
        paths.update(p for p in Path(base).rglob("*") if p.is_file() and p.suffix in {".py", ".html", ".json", ".js", ".css"})
    paths.update(Path(".").glob("requirements*"))
    paths.update(Path(p) for p in ("manage.py", "pyproject.toml", "pytest.ini", "conftest.py"))
    files = {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    build = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"files": files, "build_sha256": build,
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()}


def main():
    text = Path("CEP_EXECUTION_REGISTRY.yaml").read_text(encoding="utf-8")
    registry = yaml.safe_load(text)
    assert registry["gates"]["GATE-06"]["status"] == "PASS"
    for key in ("CEP-006", "CEP-009", "CEP-012"):
        assert registry["ceps"][key]["execution"]["status"] == "COMPLETE"
    env = json.loads((OUT / "ENVIRONMENT.json").read_text(encoding="utf-8"))
    assert env["status"] == "PASS_PREPARATION_ONLY" and env["target_tenant_user_migration_counts"] == [0, 0, 437]
    source = freeze()
    assert source["head"] == "961e3fd942c668337012c22d42f59545c5e9fc0a" and source["branch"] == "main"
    (OUT / "SOURCE_BUILD_BEFORE.json").write_text(json.dumps(source, indent=2), encoding="utf-8")
    entry = {"status": "PASS_QUALIFIED_DEVELOPMENT_ENTRY", "at": datetime.now(timezone.utc).isoformat(),
             "gate06": "PASS", "EXT-0023": "PASS_CURRENT_TARGET_BUILD_SCENARIO_DATA_SAFETY_CAPTURE",
             "head": source["head"], "build_sha256": source["build_sha256"],
             "authority": "Current direct Human Development instruction and standing eligible non-production authority",
             "target": env["target"], "scenarios": "CEP-073_EXECUTION_MANIFEST.md",
             "conditional_migration_scenarios_selected": [], "production": False,
             "historical_P10_workload_rebound": False}
    (OUT / "ENTRY.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    cep = registry["ceps"]["CEP-073"]
    cep["dependency_status"] = "SATISFIED_REQUIRED_006_009_012_AND_DEVELOPMENT_GATE06"
    cep["eligibility_status"] = "QUALIFIED_DEVELOPMENT_CURRENT_BUILD"
    cep["execution"].update(status="IN_PROGRESS", lifecycle="STARTED_BOUNDED_DEVELOPMENT_VERIFICATION")
    cep["blockers"] = []
    cep["entry_review"] = entry
    cep["history"].extend([
        {"date": "2026-10-26", "status": "BLOCKER_RESOLVED", "reason": "CEP012 fresh PostgreSQL preservation repair/proof clears objective GATE06; EXT0023 target/build/scenario/data-safety/capture established locally without changing frozen P10 capacity profile.", "evidence": (OUT / "ENTRY.json").as_posix()},
        {"date": "2026-10-26", "status": "STARTED", "reason": "Required implementation/gate prerequisites verified; exact current SHA plus working-tree source manifest frozen; disposable synthetic Development target."},
    ])
    summary = registry["summary"]
    summary.update(in_progress=1, blocked_current=3)
    text = replace_record(text, "CEP-073", cep)
    text = replace_record(text, "summary", summary, depth=0)
    Path("CEP_EXECUTION_REGISTRY.yaml").write_text(text, encoding="utf-8", newline="")

    # A new post-entry migration run belongs to this verification package.
    from scripts.cep012_preservation_proof import run
    run(OUT / "MIGRATION")
    nodes = [
        "apps/accounting/test_imb0066.py::JournalListBoundingTests::test_pages_are_bounded_stable_disjoint_and_complete",
        "apps/accounting/test_imb0066.py::JournalListBoundingTests::test_queries_limit_journals_and_first_debit_without_line_prefetch",
        "apps/accounting/test_imb0066.py::JournalListBoundingTests::test_active_tenant_scope_and_detail_links_are_preserved",
        "apps/audit/test_imb0066.py::AuditListBoundingTests::test_pages_are_bounded_stable_disjoint_and_complete",
        "apps/audit/test_imb0066.py::AuditListBoundingTests::test_one_bounded_source_read_includes_actor_and_no_writes",
        "apps/audit/test_imb0066.py::AuditListBoundingTests::test_permission_scope_membership_tenant_and_login_fail_closed",
        "apps/inventory/test_cep009.py",
        "tests/test_cep073_runtime.py::CurrentReportingRuntimeTests::test_populated_refresh_queries_reconcile_without_source_writeback",
    ]
    args = [sys.executable, "-m", "pytest", "-q", "--reuse-db", "-p", "scripts.cep073_capture",
            "--junitxml", str(OUT / "RUNTIME.xml"), "--durations=10", *nodes]
    process_env = os.environ.copy()
    process_env.update(DB_NAME="bonira_cep073_runtime_20261026", PYTHONIOENCODING="utf-8")
    started = time.monotonic()
    result = subprocess.run(args, env=process_env, capture_output=True, text=True, encoding="utf-8")
    (OUT / "RUNTIME.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    (OUT / "COMMAND.json").write_text(json.dumps({"command": args, "exit_code": result.returncode,
                                                 "seconds": time.monotonic() - started}, indent=2), encoding="utf-8")
    after = freeze()
    (OUT / "SOURCE_BUILD_AFTER.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
    assert source == after, "Source changed during exact-build verification"
    print((result.stdout + result.stderr)[-7000:])
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
