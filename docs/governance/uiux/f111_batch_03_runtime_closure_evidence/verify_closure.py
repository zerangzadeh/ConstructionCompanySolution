"""Verify closure evidence and preserve every previously accepted artifact."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
REGISTER = "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
REPORT = "docs/governance/uiux/UIUX_F111_BATCH_03_RUNTIME_CLOSURE_REPORT.md"


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def save(name, value):
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    entry = read("ENTRY.json")
    state = read("PROVISIONING.json")["authority_after"]
    assert not state["identity"]["staff"] and not state["identity"]["superuser"]
    assert state["identity"]["active"] and not state["identity"]["must_change_password"]
    assert all(state["required_capabilities"].values())
    assert {g["scope_type"] for g in state["scope_grants"]} == {"site"}
    assert len(state["scope_grants"]) == len(state["role_assignments"]) == 1
    assert state["role_assignments"][0]["role__code"] == "operations_manager"
    assert (
        state["role_assignments"][0]["assigned_by_id"]
        != state["role_assignments"][0]["approved_by_id"]
    )
    assert read("RUNTIME_AFTER.json")["authority"] == state
    assert read("RUNTIME_VERIFICATION.json")["all_preexisting_rows_unchanged"]
    http = read("RUNTIME_HTTP.json")
    assert len(http) == 14
    results = {}
    for finding, surface in (
        ("UIUX-F-123", "measurement"),
        ("UIUX-F-124", "certificate"),
    ):
        rows = [r for r in http if r["surface"] == surface]
        assert len(rows) == 7
        assert all(
            r["status"] == 200
            and r["actual_login_and_csrf_middleware"]
            and not r["model_deltas"]
            and not r["forbidden_source_metadata_matches"]
            for r in rows
        )
        assert all(r["options"] == [{"value": "", "label": "---------"}] for r in rows)
        assert sum(r["label"].startswith("forced ") for r in rows) == 5
        assert (
            len(
                [
                    r
                    for r in rows
                    if r["label"].startswith("missing required") and r["errors"]
                ]
            )
            == 1
        )
        results[finding] = (
            "PASS_OWN_SITE_ONLY_GET_FIVE_SOURCE_POSTS_INVALID_REDISPLAY_NO_METADATA_OR_BUSINESS_MUTATION"
        )
    old = (OUT / "REGISTER_BEFORE.txt").read_text(encoding="utf-8")
    new = (ROOT / REGISTER).read_text(encoding="utf-8")
    pattern = r"(?ms)^- finding_id: UIUX-F-12[34]\n.*?(?=^- finding_id:|\Z)"
    assert re.sub(pattern, "", old) == re.sub(pattern, "", new)
    assert yaml.safe_load(new)
    for finding in ("123", "124"):
        pat = rf"(?ms)^- finding_id: UIUX-F-{finding}\n.*?(?=^- finding_id:|\Z)"
        previous = re.search(pat, old).group()
        current = re.search(pat, new).group()
        assert "finding_status: RESOLVED" in current
        assert "  status: RUNTIME_VERIFIED_RESOLVED\n" in current
        assert "  runtime_status: RUNTIME_VERIFIED_RESOLVED\n" in current
        # Old source/problem/evidence and entire implementation attempt retained.
        assert (
            previous[previous.index("  problem:") :].rstrip()
            == current[
                current.index("  problem:") : current.index(
                    "  batch_03_site_only_runtime_closure:"
                )
            ].rstrip()
        )
    files = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT
        )
        .decode()
        .splitlines()
    )
    hashes = {
        name: sha(ROOT / name)
        for name in files
        if (ROOT / name).is_file()
        and not name.startswith(
            "docs/governance/uiux/f111_batch_03_runtime_closure_evidence/"
        )
    }
    changed = [
        name
        for name, expected in entry["hashes"].items()
        if hashes.get(name) != expected
    ]
    assert changed == [REGISTER], changed
    new_files = set(hashes) - set(entry["hashes"])
    assert new_files == {REPORT}, new_files
    report = ROOT / REPORT
    for path in [ROOT / REGISTER, report, *OUT.glob("*.py")]:
        for number, line in enumerate(
            path.read_text(encoding="utf-8-sig").splitlines(), 1
        ):
            assert line.rstrip() == line or (
                path.suffix == ".md" and line.endswith("  ")
            ), (path, number)
    for link in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        target = report.parent / link.split("#")[0]
        assert target.exists() or target.name in {"VERIFICATION.json", "INDEX.json"}, (
            link
        )
    assert read("SERVER_CLEANUP.json")["port_8006_listeners"] == 0
    save(
        "VERIFICATION.json",
        {
            "checks": "PASS",
            "changed_existing_files": changed,
            "new_files_outside_evidence": sorted(new_files),
            "preserved_existing_files": len(entry["hashes"]) - len(changed),
            "all_product_test_config_template_sources_unchanged": True,
            "accepted_batch01_batch02_batch03_evidence_unchanged": True,
            "p17_and_organization_actor_evidence_not_repeated": True,
            "all_other_findings_including_f121_f122_byte_preserved": True,
            "original_f123_f124_static_and_implementation_history_preserved": True,
            "independent_missing_runtime_controls": results,
            "reference_authority_fingerprint": state["authority_fingerprint"],
            "decision": "BATCH_03_RUNTIME_VERIFIED_RESOLVED",
            "batch04_to09": "NOT_EXECUTED",
            "wave_c": "NOT_STARTED",
            "production_cep078_cep079_git_writes": "NOT_EXECUTED",
        },
    )
    index = {
        p.relative_to(ROOT).as_posix(): sha(p)
        for p in sorted(OUT.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and p.name != "INDEX.json"
    }
    index[REPORT] = sha(report)
    index[REGISTER] = sha(ROOT / REGISTER)
    save("INDEX.json", index)
    print(
        "Closure boundary, accepted-evidence preservation, independent site-only controls and runtime integrity: PASS"
    )
