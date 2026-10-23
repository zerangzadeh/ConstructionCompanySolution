"""Verify BATCH-02 scope, prior evidence preservation and artifact integrity."""

import ast
import hashlib
import json
import re
from pathlib import Path

from ground import ROOT, hashes

OUT = Path(__file__).parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_parts(source):
    return {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.parse(source).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }


if __name__ == "__main__":
    entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
    current = hashes()
    changed = [
        name for name, old in entry["hashes"].items() if current.get(name) != old
    ]
    allowed = {
        "apps/billing/forms.py",
        "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml",
    }
    assert set(changed) <= allowed, changed
    new = set(current) - set(entry["hashes"])
    assert new <= {
        "tests/test_uiux_f111_pattern_clearance_scope.py",
        "docs/governance/uiux/UIUX_F111_BATCH_02_REMEDIATION_REPORT.md",
    }, new
    old_source = (OUT / "forms_entry.txt").read_text(encoding="utf-8")
    new_source = (ROOT / "apps/billing/forms.py").read_text(encoding="utf-8")
    old_parts, new_parts = source_parts(old_source), source_parts(new_source)
    changed_definitions = [key for key in old_parts if old_parts[key] != new_parts[key]]
    assert changed_definitions == ["RetentionReleaseForm"], changed_definitions
    old_register = (OUT / "register_entry.txt").read_text(encoding="utf-8")
    new_register = (
        ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
    ).read_text(encoding="utf-8")
    pattern = r"(?ms)^- finding_id: UIUX-F-122\n.*?(?=^- finding_id:|\Z)"
    assert re.sub(pattern, "", old_register) == re.sub(pattern, "", new_register)
    import yaml

    yaml.safe_load(new_register)
    files = [ROOT / name for name in new | set(changed)]
    files += [
        p
        for p in OUT.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".md"}
    ]
    for path in files:
        if path.suffix not in {".py", ".md", ".yaml"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            assert line.rstrip() == line or (
                path.suffix == ".md" and line.endswith("  ")
            ), (path, number)
    report = ROOT / "docs/governance/uiux/UIUX_F111_BATCH_02_REMEDIATION_REPORT.md"
    for link in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        target = report.parent / link.split("#")[0]
        if target.name not in {"VERIFICATION.json", "INDEX.json"}:
            assert target.exists(), link
    result = {
        "changed_existing_files": changed,
        "new_files_outside_evidence": sorted(new),
        "changed_form_definitions": changed_definitions,
        "prior_files_preserved": len(entry["hashes"]) - len(changed),
        "all_other_findings_including_f121_byte_preserved": True,
        "prior_batch01_evidence_preserved": True,
        "views_and_commercial_services_preserved": True,
        "schema_migration_settings_templates_unchanged": True,
        "batch03_through09": "NOT_EXECUTED",
        "wave_c": "NOT_STARTED",
        "production_cep078_cep079_git_writes": "NOT_EXECUTED",
        "checks": "PASS",
    }
    (OUT / "VERIFICATION.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        p.relative_to(ROOT).as_posix(): sha(p)
        for p in sorted(OUT.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and p.name != "INDEX.json"
    }
    manifest[report.relative_to(ROOT).as_posix()] = sha(report)
    manifest["apps/billing/forms.py"] = sha(ROOT / "apps/billing/forms.py")
    manifest["tests/test_uiux_f111_pattern_clearance_scope.py"] = sha(
        ROOT / "tests/test_uiux_f111_pattern_clearance_scope.py"
    )
    (OUT / "INDEX.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    for link in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        assert (report.parent / link.split("#")[0]).exists(), link
    print(
        "Boundary/preservation PASS:",
        result["prior_files_preserved"],
        "prior files unchanged",
    )
