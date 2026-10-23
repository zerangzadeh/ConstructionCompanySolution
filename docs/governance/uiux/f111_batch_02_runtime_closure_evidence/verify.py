"""Verify this read-only BATCH-02 closure attempt and preserve accepted evidence."""

import json
import re

from close_runtime import OUT, PRIOR, ROOT, file_snapshot, save, sha, snapshot

before_files = json.loads((OUT / "FILES_BEFORE.json").read_text(encoding="utf-8"))
after_files = file_snapshot()
changed = [
    name for name, expected in before_files.items() if after_files.get(name) != expected
]
register = "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
report = "docs/governance/uiux/UIUX_F111_BATCH_02_RUNTIME_CLOSURE_REPORT.md"
assert changed == [register], changed
assert set(after_files) - set(before_files) == {report}
old_register = (OUT / "REGISTER_BEFORE.txt").read_text(encoding="utf-8")
new_register = (ROOT / register).read_text(encoding="utf-8")
pattern = r"(?ms)^- finding_id: UIUX-F-122\n.*?(?=^- finding_id:|\Z)"
assert re.sub(pattern, "", old_register) == re.sub(pattern, "", new_register)
old_entry = re.search(pattern, old_register).group()
new_entry = re.search(pattern, new_register).group()
assert new_entry.startswith(old_entry)
assert "finding_status: OPEN" in new_entry
assert "runtime_status: REMEDIATION_IMPLEMENTED_PENDING_RUNTIME_RETEST" in new_entry
accepted = json.loads((PRIOR / "INDEX.json").read_text(encoding="utf-8"))
assert all(sha(ROOT / name) == expected for name, expected in accepted.items())
models_before = json.loads((OUT / "MODELS_BEFORE.json").read_text(encoding="utf-8"))
models_after = snapshot()
deltas = [
    name for name, expected in models_before.items() if models_after[name] != expected
]
assert not deltas, deltas
import yaml

yaml.safe_load(new_register)
paths = [ROOT / report, ROOT / register] + [
    p for p in OUT.iterdir() if p.suffix == ".py"
]
for path in paths:
    assert all(
        line == line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()
    ), path
save(
    "VERIFICATION.json",
    {
        "accepted_evidence_manifest_unchanged": True,
        "accepted_validation_repeated": False,
        "product_test_configuration_sources_unchanged": True,
        "f121_and_other_finding_entries_byte_preserved": True,
        "f122_old_entry_preserved_as_prefix": True,
        "changed_existing_files": changed,
        "new_report": report,
        "prior_files_preserved": len(before_files) - len(changed),
        "model_tables_compared": len(models_after),
        "model_deltas": deltas,
        "user_last_login_digest_excluded": True,
        "fixture_product_authority_writes": 0,
        "source_backed_runtime_controls": "NOT_EXECUTED_PREREQUISITE_BLOCKED",
        "fresh_server_and_browser": "NOT_STARTED_PREREQUISITE_BLOCKED",
        "batch03_through09_wave_c_production_cep078_cep079_git_writes": "NOT_EXECUTED",
    },
)
save(
    "INDEX.json",
    {
        p.relative_to(ROOT).as_posix(): sha(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "INDEX.json"
    }
    | {report: sha(ROOT / report)},
)
for link in re.findall(r"\]\(([^)]+)\)", (ROOT / report).read_text(encoding="utf-8")):
    assert (ROOT / report).parent.joinpath(link).exists(), link
print(
    "Preservation/integrity PASS: all",
    len(models_after),
    "model tables unchanged; accepted evidence unchanged",
)
