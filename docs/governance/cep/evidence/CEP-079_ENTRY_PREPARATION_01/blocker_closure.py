"""Bounded 2026-10-24 entry closure evidence helpers; never executes UAT."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent


def write(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    assert not (OUT / "BLOCKER_CLOSURE_BASELINE.json").exists()
    commands = ["branch --show-current", "rev-parse HEAD", "rev-parse origin/main", "status --short", "diff --name-status", "diff --stat", "rev-list --left-right --count HEAD...origin/main"]
    product = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for directory in ("apps", "core", "config", "templates", "static", "tests") for p in (ROOT / directory).rglob("*") if p.is_file() and p.suffix in (".py", ".html", ".js", ".css") and "__pycache__" not in str(p)}
    write("BLOCKER_CLOSURE_BASELINE.json", {
        "date": "2026-10-24", "scope": "Tasks 1 through 5 serially; entry closure only; no UAT execution",
        "git": {c: subprocess.run(["git", *c.split()], cwd=ROOT, capture_output=True, text=True, check=True).stdout for c in commands},
        "product_hashes": product,
        "preserved_ready_cases": [r["case_id"] for r in []],
        "intended_touch_set": ["apps/workforce/static/workforce/js/organization_chart.js (only if attribution requires)", "templates/workforce/department_list.html (asset identity only if required)", "existing CEP-079_ENTRY_PREPARATION_01 evidence and matrices", "CEP_EXECUTION_REGISTRY.yaml (entry delta only)", "isolated Development fixtures only where approved canonical inputs exist"],
        "prompt_sha256": digest(ROOT / "docs/governance/cep/PROMPTS/CEP-079_EXECUTION_PROMPT.md"),
        "authority": "Direct Human request in attachment 24097c37-b1c1-481b-92fd-db64db2a01a5; minimum presentation/focus correction and governed synthetic Development inputs authorized; no schema, UAT or Git writes",
    })
    write("BLOCKER_CLOSURE_TASKS.json", {"task1": {
        "result": "BLOCKED", "blocker": "CEP079-PREP-B01", "case": "UAT-CASE-012",
        "retained_evidence": "CEP040_RECOVERY.json; unchanged HEAD 43ac319c6e73e48ca9626461b73987922c498ec3",
        "delta_check": "Direct project tests contain P4 and CEP005/047/059 scoped evidence; no original CEP040 report/acceptance retained. git log --all --grep CEP-040/IMB-0039 and exact CEP040 report/evidence paths return no records.",
        "recovery_limit": "Prior approved consolidated recovery exhausted; no repeat broad search or downstream substitution.",
        "missing_proof": json.loads((OUT / "CEP040_RECOVERY.json").read_text(encoding="utf-8"))["missing_obligations"],
        "minimum_action": "Recover original authoritative CEP040/IMB0039 source/version, duplicate/supersession, scope, no-financial-write and AC/DoD acceptance/test outputs; no reimplementation.",
    }})
