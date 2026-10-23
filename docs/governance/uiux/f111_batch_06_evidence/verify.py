"""Verify BATCH-06 boundaries, preserved history and required closeout evidence."""
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
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def outside_boundary(source, name):
    tree = ast.parse(source)
    if name == "forms":
        tree.body = [n for n in tree.body if not isinstance(n, ast.ClassDef) or n.name != "ExpenseAllocationForm"]
        extras = {"scope_queryset", "normalized_uuid", "OrganizationMembership", "ProjectBudgetControl"}
        for n in tree.body:
            if isinstance(n, ast.ImportFrom):
                n.names = [a for a in n.names if a.name not in extras]
        tree.body = [n for n in tree.body if not isinstance(n, ast.ImportFrom) or n.names]
    else:
        tree.body = [n for n in tree.body if not isinstance(n, ast.FunctionDef) or n.name not in {"expense_detail", "expense_allocate"}]
    return ast.dump(tree, include_attributes=False)


def main():
    entry = read("ENTRY_BASELINE.json")
    changed = [n for n, h in entry["hashes"].items() if hashlib.sha256((ROOT / n).read_bytes()).hexdigest() != h]
    assert set(changed) == {"apps/expenses/forms.py", "apps/expenses/views.py", "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"}, changed
    for name in ("forms", "views"):
        current = (ROOT / f"apps/expenses/{name}.py").read_text(encoding="utf-8")
        baseline = (OUT / f"{name}_entry.txt").read_text(encoding="utf-8")
        assert outside_boundary(current, name) == outside_boundary(baseline, name)
    register = (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_text(encoding="utf-8")
    original = (OUT / "register_entry.txt").read_text(encoding="utf-8")
    pattern = r"- finding_id: UIUX-F-119\n.*?(?=- finding_id: UIUX-F-120\n)"
    assert re.sub(pattern, "", register, flags=re.S) == re.sub(pattern, "", original, flags=re.S)
    assert yaml.safe_load(register)
    finding = re.search(pattern, register, re.S).group()
    for token in ("finding_status: RESOLVED", "status: RUNTIME_VERIFIED_RESOLVED", "decision: BATCH_06_RUNTIME_VERIFIED_RESOLVED"):
        assert token in finding
    focused = ET.parse(OUT / "focused.xml").getroot()
    assert not focused.findall(".//failure") and not focused.findall(".//error")
    assert "12 passed, 42 subtests passed" in (OUT / "focused.txt").read_text(encoding="utf-8")
    def results(name):
        rows = []
        for c in ET.parse(OUT / name).getroot().findall(".//testcase"):
            failure = c.find("failure")
            assert c.find("error") is None
            rows.append((c.get("classname"), c.get("name"), None if failure is None else failure.get("message")))
        return rows
    assert results("baseline_regression.xml") == results("regression.xml")
    attribution = read("REGRESSION_ATTRIBUTION.json")
    assert attribution["baseline_identical_to_current"] and len(attribution["failures"]) == 15 and not attribution["new_failures"]
    assert "15 failed, 47 passed, 64 subtests passed" in (OUT / "regression.txt").read_text(encoding="utf-8")
    for file, token in (("django_check.txt", "no issues"), ("migration_check.txt", "No changes detected"), ("ruff.txt", "All checks passed"), ("ruff_format.txt", "3 files already formatted")):
        assert token in (OUT / file).read_text(encoding="utf-8"), file
    http = read("RUNTIME_HTTP.json")
    assert len(http) == 25
    negatives = [r for r in http if r.get("bare_response")]
    assert len(negatives) == 17 and all(r["status"] == 400 and r["refreshed_get"] == 200 and r["business_and_audit_unchanged"] and not r["forbidden_metadata"] for r in negatives)
    assert len([r for r in http if r["status"] == 404]) == 6
    assert all(r["denied"] and r["mutations"] == 0 for r in read("DIRECT_SERVICE.json"))
    browser = read("RUNTIME_BROWSER.json")
    assert len(browser) == 7
    fixtures = read("FIXTURES.json")["coding"]
    comparisons = []
    for record in browser:
        if "GET" not in record["label"]:
            continue
        actor = "uiux.persona.tenant-admin" if record["label"] == "organization GET" else "uiux.persona.project-manager"
        control = next(r for r in http if r["case"] == "detail GET" and r["actor"] == actor)
        for field, options in record["options"].items():
            assert [{k: o[k] for k in ("value", "label")} for o in options] == control["options"][field]
        forbidden = "X" if actor.endswith("tenant-admin") else "CDX"
        for fixture in fixtures:
            if fixture["key"] in forbidden:
                for field in ("project", "wbs_node", "activity"):
                    assert fixture["ids"][field] not in record["bodyText"]
                    assert fixture["labels"][field] not in record["bodyText"]
        comparisons.append(record["label"])
    assert len(comparisons) == 4
    assert "HTTP ERROR 400" in browser[1]["bodyText"]
    assert "404" in browser[-1]["bodyText"] and all(not v for v in browser[-1]["options"].values())
    for name in ("browser_limited_get.png", "browser_mixed_wbs_400.png", "browser_mixed_activity_400.png", "browser_refreshed_get.png", "browser_activity_refreshed.png", "browser_organization.png", "browser_site_only.png"):
        assert (OUT / name).stat().st_size > 1000
    integrity = read("RUNTIME_INTEGRITY.json")
    assert integrity["tables"] == 519 and not integrity["preexisting_rows_changed"] and not integrity["unauthorized_mutations"]
    assert integrity["authority_unchanged"] and integrity["authority_fingerprint_before"] == integrity["authority_fingerprint_after"]
    assert integrity["runtime_success_audits"] == 1 and not read("RUNTIME_POSITIVE.json")["approved_or_posted"]
    expected_prep = {"projects."+name: 5 for name in ("WBSNode", "Activity", "CostStructureVersion", "CBSNode", "CostCenter", "BudgetVersion", "ProjectBudgetControl", "BudgetSourceManifest", "BudgetManifestLine", "BudgetAllocation")}
    expected_prep.update({"estimates."+name: 5 for name in ("Estimate", "EstimateRevision", "EstimateItem")})
    expected_prep.update({"expenses.Expense": 1, "audit.AuditEvent": 46})
    assert integrity["preparation_additions"] == expected_prep
    assert all(row["predates_server"] for row in read("SERVER_IDENTITY.json")["source_files"])
    assert read("SERVER_CLEANUP.json")["listener_remaining"] is False
    check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
    (OUT / "whitespace.txt").write_text(check.stdout + check.stderr, encoding="utf-8")
    assert check.returncode == 0
    report = OUT.parent / "UIUX_F111_BATCH_06_REMEDIATION_REPORT.md"
    for link in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        target = report.parent / link.split("#")[0]
        assert target.exists() or target in {OUT / "VERIFICATION.json", OUT / "INDEX.json"}, link
    for path in (report, ROOT / "tests/test_uiux_f111_pattern_allocation_scope.py", *OUT.glob("*.py")):
        assert all(line == line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()), path
    save("VERIFICATION.json", {
        "decision": "BATCH_06_RUNTIME_VERIFIED_RESOLVED", "finding": "UIUX-F-119", "status": "RUNTIME_VERIFIED_RESOLVED",
        "baseline_files_compared": len(entry["hashes"]), "changed_existing_files": changed,
        "product_ast_boundaries_only": True, "prior_batches_other_findings_registry_roadmap_graph_preserved": True,
        "focused": "12 tests + 42 subtests PASS", "regression": "47 tests + 64 subtests PASS; 15 exact-baseline setup failures; zero new regressions",
        "http_observations": len(http), "browser_observations": len(browser), "browser_exact_http_comparisons": comparisons,
        "direct_service_denials": 8, "authorized_runtime_allocations": 1, "integrity": integrity,
        "migration": "NO", "batch07_09": "NOT_EXECUTED", "wave_c": "NOT_STARTED",
        "production_cep078_079_git_writes": "NOT_EXECUTED",
        "final_source_sha256": {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in ("apps/expenses/forms.py", "apps/expenses/views.py", "tests/test_uiux_f111_pattern_allocation_scope.py", "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml")},
    })
    save("INDEX.json", {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name != "INDEX.json"})
    print("BATCH-06 final boundary/evidence verification PASS")


if __name__ == "__main__":
    main()
