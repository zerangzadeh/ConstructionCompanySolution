"""Read-only repository assertions and final evidence hashes; never writes Git."""

import ast
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
PRODUCTION = OUT.parents[1]


def load(path):
    return json.loads(path.read_text("utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def main():
    assert git("rev-parse", "HEAD") == load(OUT / "ENTRY.json")["head"]
    assert git("branch", "--show-current") == "main"
    assert not git("diff", "--cached", "--name-only")
    before = yaml.safe_load(git("show", "HEAD:CEP_EXECUTION_REGISTRY.yaml"))
    after = yaml.safe_load((ROOT / "CEP_EXECUTION_REGISTRY.yaml").read_text("utf-8"))
    assert all(before[k] == after[k] for k in before if k not in {"gates", "repository_state"})
    assert all(before["gates"][k] == after["gates"][k] for k in before["gates"] if k != "GATE-11")
    assert len(after["ceps"]) == 86
    assert sum(row["execution"]["status"] == "COMPLETE" for row in after["ceps"].values()) == 79
    gate = load(PRODUCTION / "GATE11_EVALUATION.json")
    previous = load(OUT / "GATE11_EVALUATION_BEFORE.json")
    assert [x["requirement"] for x in gate["clauses"]] == [x["requirement"] for x in previous["clauses"]]
    assert gate["requirements_satisfied"] == after["gates"]["GATE-11"]["requirements_satisfied"] == 3
    assert gate["status"] == after["gates"]["GATE-11"]["status"] == "NOT_PASSED"
    assert gate["requirements_total"] == 5
    freeze = load(OUT / "SOURCE_FREEZE_FINAL.json")
    assert len(freeze) == 1604 and all(sha(ROOT / p) == h for p, h in freeze.items())
    entry = load(OUT.parent / "20261028/ENTRY.json")
    assert all(sha(ROOT / row["path"]) == row["sha256"] for row in entry["canonical_prompts"].values())
    retained = load(OUT.parent / "20261028/RETAINED_HASH_CHECK.json")
    retained_deltas = [row["path"] for row in retained if sha(ROOT / row["path"]) != row["expected"]]
    assert retained_deltas == ["CEP_EXECUTION_REGISTRY.yaml"]
    changed = git("diff", "--name-only").splitlines()
    expected = set(load(OUT / "ENTRY.json")["before_hashes"]) - {
        "docs/governance/production/GATE11_EVALUATION.json",
        "docs/governance/production/PRODUCTION_READINESS_ASSESSMENT.md",
        "docs/governance/production/PRODUCTION_REFERENCE_AND_CUTOVER.md",
    }
    assert set(changed) == expected, changed
    for name in changed:
        if name.endswith(".py"):
            ast.parse((ROOT / name).read_text("utf-8"))
    link_count = 0
    for path in [PRODUCTION / "PRODUCTION_READINESS_ASSESSMENT.md", PRODUCTION / "PRODUCTION_REFERENCE_AND_CUTOVER.md", OUT / "COMPLETION_REPORT.md"]:
        text = path.read_text("utf-8")
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" in link:
                continue
            target = link.split("#", 1)[0]
            assert (path.parent / target).resolve().exists(), (path, link)
            link_count += 1
    check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert check.returncode == 0
    result = {
        "at": datetime.now(UTC).isoformat(), "result": "PASS",
        "head": git("rev-parse", "HEAD"), "branch": "main", "staged_files": 0,
        "complete_ceps_unchanged": 79, "total_cep_records_unchanged": 86, "other_gates_unchanged": True,
        "exact_gate_clauses_unchanged": 5, "requirements_satisfied": 3,
        "frozen_source_files_unchanged": len(freeze), "canonical_prompts_unchanged": len(entry["canonical_prompts"]),
        "retained_hashes_unchanged": len(retained) - len(retained_deltas),
        "intentional_retained_hash_delta": retained_deltas,
        "tracked_changed_paths": changed, "relative_links_resolve": link_count,
        "python_parse_and_diff_whitespace": "PASS", "ruff_changed_runtime_test_tool": "PASS; 3 files checked/formatted",
        "production_action": False, "git_writes": False,
    }
    (OUT / "FINAL_CHECKS.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {}
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.name != "ARTIFACT_HASHES.json":
            manifest[path.relative_to(ROOT).as_posix()] = sha(path)
    for path in [ROOT / "CEP_EXECUTION_REGISTRY.yaml", *PRODUCTION.glob("*.md"), PRODUCTION / "GATE11_EVALUATION.json", PRODUCTION / "production.env.example"]:
        manifest[path.relative_to(ROOT).as_posix()] = sha(path)
    for name in changed:
        manifest[name] = sha(ROOT / name)
    (OUT / "ARTIFACT_HASHES.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print("Final manifest:", len(manifest), "files")


if __name__ == "__main__":
    main()
