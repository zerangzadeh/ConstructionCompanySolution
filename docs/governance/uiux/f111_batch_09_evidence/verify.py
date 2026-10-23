"""Evidence gates, exact source boundaries and preservation for BATCH-09."""

import ast
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
TARGETS = {
    "equipment": ("MaintenanceRecordForm", "maintenance_create"),
    "quality": ("QualityIssueForm", "issue_create"),
    "safety": ("SafetyIncidentForm", "incident_create"),
}
FINDINGS = ("115", "126", "127")


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def imports(source):
    return {(n.module, a.name) for n in ast.parse(source).body if isinstance(n, ast.ImportFrom) for a in n.names}


def outside(source, app, kind):
    tree = ast.parse(source)
    for node in tree.body:
        if kind == "forms" and isinstance(node, ast.ClassDef) and node.name == TARGETS[app][0]:
            node.body = [n for n in node.body if not isinstance(n, ast.FunctionDef) or n.name != "__init__"]
        if kind == "views" and isinstance(node, ast.FunctionDef) and node.name == TARGETS[app][1]:
            assert isinstance(node.body[0], ast.Assign) and node.body[0].targets[0].id == "form"
            node.body[0] = ast.Pass()
    tree.body = [n for n in tree.body if not isinstance(n, (ast.ImportFrom, ast.Import))]
    return ast.dump(tree, include_attributes=False)


def source_boundary(closed=False):
    entry = read("ENTRY_BASELINE.json")
    product = {f"apps/{app}/{kind}.py" for app in TARGETS for kind in ("forms", "views")}
    register = "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
    changed = [p for p, digest in entry["hashes"].items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != digest]
    assert set(changed) == product | ({register} if closed else set()), changed
    changes = {}
    for app in TARGETS:
        for kind in ("forms", "views"):
            current = (ROOT / f"apps/{app}/{kind}.py").read_text(encoding="utf-8")
            initial = (OUT / f"{app}_{kind}_entry.txt").read_text(encoding="utf-8")
            assert outside(current, app, kind) == outside(initial, app, kind), (app, kind)
            added, removed = imports(current) - imports(initial), imports(initial) - imports(current)
            expected_added, expected_removed = set(), set()
            if app in {"quality", "safety"}:
                if kind == "forms":
                    expected_added = {("apps.organizations.authorization", "scope_queryset"), ("apps.organizations.form_scoping", "scoped_projects_for_form"), ("apps.organizations.models", "OrganizationMembership")}
                    expected_removed = {("apps.projects.models", "Project")}
                else:
                    expected_added = {("apps.organizations.authorization", "get_active_membership")}
            assert added == expected_added and removed == expected_removed, (app, kind, added, removed)
            changes[app + "." + kind] = {"added": sorted(added), "removed": sorted(removed)}
    original = (OUT / "register_entry.txt").read_bytes()
    current = (ROOT / register).read_bytes()
    def strip_targets(content):
        for finding in FINDINGS:
            content = re.sub(rb"- finding_id: UIUX-F-" + finding.encode() + rb"\r?\n.*?(?=- finding_id: UIUX-F-|\Z)", b"", content, flags=re.S)
        return content
    assert strip_targets(original) == strip_targets(current)
    if not closed:
        assert original == current
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == entry["head"]
    assert subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True).returncode == 0
    return {"baseline_hashes_compared": len(entry["hashes"]), "changed_existing_files": changed, "non_target_source_AST_preserved": True, "import_changes": changes, "all_other_finding_blocks_byte_preserved": True, "prior_batches_01_through_08_preserved": True, "graph_registry_roadmap_protected_documents_unchanged": True}


def evidence_gates():
    focused = ET.parse(OUT / "focused.xml")
    assert not focused.findall(".//failure") and not focused.findall(".//error")
    cases = focused.findall(".//testcase")
    assert len(cases) == 48
    assert all(any(name in c.get("classname", "") for c in cases) for name in ("MaintenanceOperationalScopeTests", "QualityOperationalScopeTests", "SafetyOperationalScopeTests"))
    assert all(sum(name in c.get("classname", "") for c in cases) == 16 for name in ("MaintenanceOperationalScopeTests", "QualityOperationalScopeTests", "SafetyOperationalScopeTests"))
    attribution = read("REGRESSION_ATTRIBUTION.json")
    assert not attribution["new_failures"]
    assert attribution["baseline_identical_to_current"]
    for file, token in (("django_check.txt", "no issues"), ("migration_check.txt", "No changes detected"), ("ruff.txt", "All checks passed"), ("ruff_format.txt", "1 file already formatted")):
        assert token in (OUT / file).read_text(encoding="utf-8"), file
    http, summary = read("RUNTIME_HTTP.json"), read("HTTP_SUMMARY.json")
    assert summary["all_pass"] and len(http) == summary["observations"]
    assert all(r["real_authentication_csrf"] and r["business_and_success_audit_unchanged"] and not r.get("forbidden_metadata", []) for r in http)
    payload = read("BROWSER_PAYLOAD.json")
    for finding in FINDINGS:
        protected = ("project", "site") if finding == "115" else ("project", "site", "phase", "activity", "daily_report")
        rows = [r for r in http if r["finding"] == "UIUX-F-" + finding]
        assert len(rows) >= 30
        for actor, allowed in (("uiux.persona.project-manager", "AB"), ("uiux.persona.tenant-admin", "ABCD"), ("uiux.reference.batch03.site-only", "A")):
            own = [r for r in rows if r["actor"] == actor]
            get = next(r for r in own if r["case"] == "GET")
            assert any(r["case"] == "required-field redisplay" and r["errors"] for r in own)
            assert {o["value"] for o in get["options"]["project"] if o["value"]} == {payload["sources"][k]["project"] for k in allowed}
            if allowed == "ABCD":
                continue
            for field in protected:
                for key in ("BCDX" if allowed == "A" else "CDX"):
                    assert any(r["case"] == "forced " + key + " " + field and r["errors"] for r in own), (finding, actor, field, key)
                if field != "project":
                    label = "ungranted sibling " if allowed == "A" else "mixed authorized parent/child "
                    assert any(r["case"] == label + field and r["errors"] for r in own)
            if finding != "115" and allowed == "A":
                assert any(r["case"] == "site grant cannot enumerate project-only Activity" and r["errors"] for r in own)
    direct = read("DIRECT_SERVICE.json")
    assert len(direct) == 24 and all(r["denied"] and not r["mutations"] for r in direct)
    browser = read("RUNTIME_BROWSER.json")
    assert len(browser) == 9
    localization = read("BROWSER_LABEL_NORMALIZATION.json")
    digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    for row in browser:
        control = next(r for r in http if r["finding"] == row["finding"] and r["actor"] == row["actor"] and r["case"] == "GET")
        for field, options in control["options"].items():
            actual = row["options"][field]
            assert len(actual) == len(options)
            for observed, expected in zip(actual, options, strict=True):
                label = localization["daily_report_labels"][expected["label"]] if field == "daily_report" else expected["label"]
                assert observed["value"] == expected["value"]
                assert observed["label"].translate(digits) == label.translate(digits), (row["finding"], row["label"], field)
        assert (OUT / row["screenshot"]).exists()
        if "real server POST" in row["label"]:
            assert row["errors"]
    assert sum("real server POST" in r["label"] for r in browser) == 2
    integrity = read("RUNTIME_INTEGRITY.json")
    assert integrity["tables"] == 519 and integrity["authority_unchanged"]
    assert not integrity["preexisting_business_rows_changed"] and not integrity["unauthorized_mutations"] and not integrity["runtime_success_audits"]
    assert set(integrity["runtime_deltas"]) <= {"sessions.Session"}
    fixtures = read("FIXTURES.json")
    assert len(fixtures["created"]) == 4 and not fixtures["authority_mutations"]
    assert all(r["predates_server"] for r in read("SERVER_IDENTITY.json")["source_files"])
    cleanup = read("SERVER_CLEANUP.json")
    assert cleanup["identity_verified"] and cleanup["stopped"] and not cleanup["listener_remaining"]
    return {"focused_tests": len(cases), "regression": attribution, "http_observations": len(http), "http_by_finding": summary["by_finding"], "direct_denials": len(direct), "browser_observations": len(browser), "browser_real_server_POSTs": 2, "browser_date_normalization_only": 1, "integrity_tables": 519, "fixture_preparation": "Four canonical synthetic sibling objects; audit retained", "temporary_authority": "NONE"}


def main():
    if "--source-only" in sys.argv:
        save("SOURCE_BOUNDARY.json", source_boundary())
        print("Source boundary PASS; prior work preserved")
        return
    result = source_boundary(closed=True) | evidence_gates()
    register = (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_text(encoding="utf-8")
    for finding in FINDINGS:
        block = re.search(r"- finding_id: UIUX-F-" + finding + r"\n.*?(?=- finding_id: UIUX-F-|\Z)", register, re.S).group()
        assert "finding_status: RESOLVED" in block and "decision: BATCH_09_RUNTIME_VERIFIED_RESOLVED" in block
    report = OUT.parent / "UIUX_F111_BATCH_09_REMEDIATION_REPORT.md"
    for link in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        target = report.parent / link.split("#")[0]
        assert target.exists() or target == OUT / "VERIFICATION.json", link
    for p in (report, ROOT / "tests/test_uiux_f111_pattern_operational_scope.py", *OUT.glob("*.py")):
        assert all(line == line.rstrip() for line in p.read_text(encoding="utf-8").splitlines()), p
    save("VERIFICATION.json", result | {"decision": "BATCH_09_RUNTIME_VERIFIED_RESOLVED", "findings": {"UIUX-F-" + f: "RUNTIME_VERIFIED_RESOLVED" for f in FINDINGS}, "migration": "NO", "wave_c": "NOT_STARTED", "SP031": "NOT_EXECUTED_UNCHANGED", "production": "NO ACTION", "cep_078_079": "NOT_EXECUTED", "git_add_commit_push": "NOT_EXECUTED"})
    save("INDEX.json", {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in {"INDEX.json", "verification.txt"}})
    print("PASS: all three findings independently closed; exact source boundary and prior evidence preserved")


if __name__ == "__main__":
    main()
