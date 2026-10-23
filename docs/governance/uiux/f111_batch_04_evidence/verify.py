"""Verify BATCH-04 boundaries, evidence, and preservation of the dirty baseline."""

import ast
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def save(name, value):
    (OUT / name).write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def suite(name):
    root = ET.parse(OUT / f"{name}.xml").getroot()
    cases = root.findall(".//testcase")
    failures = {}
    for case in cases:
        for tag in ("failure", "error"):
            failure = case.find(tag)
            if failure is not None:
                failures[case.attrib["classname"] + "." + case.attrib["name"]] = {
                    "attributes": failure.attrib,
                    "text": failure.text,
                }
    return {
        "cases": len(cases),
        "passed": len(cases) - len(failures),
        "failures": failures,
    }


def canonical_ast(source, name):
    tree = ast.parse(source)
    if name == "forms":
        cls = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "GoodsReceiptForm"
        )
        cls.body = [
            node
            for node in cls.body
            if not isinstance(node, ast.FunctionDef) or node.name != "__init__"
        ]
    else:
        tree.body = [
            node
            for node in tree.body
            if not isinstance(node, ast.FunctionDef)
            or node.name != "goods_receipt_create"
        ]
    return ast.dump(tree, include_attributes=False)


def main():
    baseline = read("ENTRY_BASELINE.json")
    allowed = {
        "apps/procurement/forms.py",
        "apps/procurement/views.py",
        "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml",
    }
    changed = [
        name
        for name, digest in baseline["hashes"].items()
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest
    ]
    assert set(changed) == allowed, changed
    for name in ("forms", "views"):
        assert canonical_ast(
            (ROOT / f"apps/procurement/{name}.py").read_text(encoding="utf-8"), name
        ) == canonical_ast(
            (OUT / f"{name}_entry.txt").read_text(encoding="utf-8"), name
        )
    register = ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
    old = (OUT / "register_entry.txt").read_text(encoding="utf-8")
    current = register.read_text(encoding="utf-8")
    pattern = r"- finding_id: UIUX-F-114\n.*?(?=- finding_id: UIUX-F-115\n)"
    assert re.sub(pattern, "", old, flags=re.DOTALL) == re.sub(
        pattern, "", current, flags=re.DOTALL
    )
    data = yaml.safe_load(current)
    assert data
    finding = re.search(pattern, current, flags=re.DOTALL).group(0)
    assert "finding_status: RESOLVED" in finding
    assert "status: RUNTIME_VERIFIED_RESOLVED" in finding
    assert "decision: BATCH_04_RUNTIME_VERIFIED_RESOLVED" in finding
    assert all(line == line.rstrip() for line in finding.splitlines())
    assert "System check identified no issues" in (OUT / "django_check.txt").read_text(
        encoding="utf-8"
    )
    assert "No changes detected" in (OUT / "migration_check.txt").read_text(
        encoding="utf-8"
    )
    assert "All checks passed!" in (OUT / "ruff.txt").read_text(encoding="utf-8")
    assert "files already formatted" in (OUT / "ruff_format.txt").read_text(
        encoding="utf-8"
    )
    assert read("RUNTIME_ENTRY.json")["pending_migrations"] == 0
    assert not read("SERVER_CLEANUP.json")["listener_remaining"]
    focused = suite("focused")
    regression = suite("regression")
    assert not focused["failures"]
    attribution = {"attributable_regressions": 0}
    if regression["failures"]:
        entry = suite("baseline_regression")
        assert regression["failures"] == entry["failures"], (
            "Regression differs from exact dirty-entry replay"
        )
        attribution |= {
            "classification": "BASELINE TEST DEBT",
            "identical_failures": len(entry["failures"]),
            "failures": list(entry["failures"]),
            "boundary": "Legacy Purchase Request authorization/setup or panel entry before changed GoodsReceiptForm/view; exact entry forms+views replay",
        }
    save("REGRESSION_ATTRIBUTION.json", attribution)
    http = read("RUNTIME_HTTP.json")
    assert len(http) == 13 and all(
        r["status"] == 200
        and not r["forbidden_metadata"]
        and set(r["model_deltas"]) <= {"sessions.Session"}
        for r in http
    )
    assert all(r["errors"] for r in http if r["method"] == "POST")
    browser = read("RUNTIME_BROWSER.json")
    assert len(browser) == 4
    assert [len(r["options"]) for r in browser] == [3, 3, 1, 5]
    assert browser[1]["errorVisible"]
    integrity = read("RUNTIME_INTEGRITY.json")
    assert (
        not integrity["preexisting_rows_changed"] and integrity["authority_unchanged"]
    )
    for command, filename in ((["git", "diff", "--check"], "whitespace.txt"),):
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, check=False
        )
        (OUT / filename).write_text(result.stdout + result.stderr, encoding="utf-8")
        assert result.returncode == 0
    fresh = [
        ROOT / "tests/test_uiux_f111_pattern_receipt_scope.py",
        ROOT / "docs/governance/uiux/UIUX_F111_BATCH_04_REMEDIATION_REPORT.md",
        *OUT.glob("*.py"),
    ]
    for path in fresh:
        assert all(
            line == line.rstrip()
            for line in path.read_text(encoding="utf-8").splitlines()
        ), path
    report = fresh[1].read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", report):
        resolved = fresh[1].parent / target.split("#")[0]
        assert resolved.exists() or resolved in {
            OUT / "VERIFICATION.json",
            OUT / "INDEX.json",
        }, target
    summary = {
        "decision": "BATCH_04_RUNTIME_VERIFIED_RESOLVED",
        "finding": "UIUX-F-114",
        "status": "RUNTIME_VERIFIED_RESOLVED",
        "baseline_files_compared": len(baseline["hashes"]),
        "changed_existing_files": changed,
        "two_product_ast_boundaries_only": True,
        "all_other_findings_and_prior_evidence_preserved": True,
        "focused": {k: v for k, v in focused.items() if k != "failures"},
        "regression": {k: v for k, v in regression.items() if k != "failures"},
        "attribution": attribution,
        "runtime_http": len(http),
        "runtime_browser": len(browser),
        "integrity": integrity,
        "migration": "NO",
        "batch05_to09": "NOT_EXECUTED",
        "wave_c": "NOT_STARTED",
        "production_cep078_079_git_writes": "NOT_EXECUTED",
    }
    save("VERIFICATION.json", summary)
    save(
        "INDEX.json",
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in OUT.iterdir()
            if p.is_file() and p.name not in {"INDEX.json", "verification.txt"}
        },
    )
    print("BATCH-04 validation, runtime, preservation and boundary checks PASS")


if __name__ == "__main__":
    main()
