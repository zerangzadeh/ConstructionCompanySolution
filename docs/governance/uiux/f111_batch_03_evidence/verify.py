"""Verify BATCH-03 boundaries, independent evidence, and baseline attribution."""

import ast
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
REPORT = "docs/governance/uiux/UIUX_F111_BATCH_03_REMEDIATION_REPORT.md"
REGISTER = "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"


def save(name, value):
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_declarations(source, names):
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    removed = set()
    for node in tree.body:
        if getattr(node, "name", None) in names:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            removed.update(range(start - 1, node.end_lineno))
    return b"".join(line for index, line in enumerate(lines) if index not in removed)


def failures(name):
    return {
        case.attrib["classname"] + "." + case.attrib["name"]: (
            case.find("failure").attrib,
            case.find("failure").text,
        )
        for case in ET.parse(OUT / name).iter("testcase")
        if case.find("failure") is not None
    }


if __name__ == "__main__":
    baseline, actual = failures("baseline.xml"), failures("regression.xml")
    assert len(baseline) == len(actual) == 11
    assert baseline == actual
    assert all(
        "apps\\projects\\services.py:169" in trace for _, trace in actual.values()
    )
    save(
        "REGRESSION_ATTRIBUTION.json",
        {
            "classification": "BASELINE TEST DEBT",
            "entry_replay": "Captured dirty-entry apps.billing.forms loaded in memory; no checkout replacement",
            "failures": sorted(actual),
            "identical_failure_attributes_and_tracebacks": 11,
            "boundary": "Project creation in legacy fixture setup, before payable forms/views",
            "attributable_regressions": 0,
            "legacy_downstream_behavior": "UNVERIFIED_BY_BLOCKED_LEGACY_TESTS",
        },
    )
    entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT
        )
        .decode()
        .splitlines()
    )
    current = {
        name: sha(ROOT / name)
        for name in names
        if (ROOT / name).is_file()
        and not name.startswith("docs/governance/uiux/f111_batch_03_evidence/")
    }
    changed = [
        name for name, value in entry["hashes"].items() if current.get(name) != value
    ]
    assert set(changed) == {
        "apps/billing/forms.py",
        "apps/billing/views.py",
        REGISTER,
    }, changed
    new = set(current) - set(entry["hashes"])
    assert new == {REPORT, "tests/test_uiux_f111_pattern_payable_scope.py"}, new
    declarations = {
        "forms": {"PayableMeasurementForm", "PayableCertificateForm"},
        "views": {"payable_measurement_create", "payable_certificate_create"},
    }
    for module, allowed in declarations.items():
        old = (OUT / f"{module}_entry.txt").read_bytes()
        updated = (ROOT / f"apps/billing/{module}.py").read_bytes()
        assert strip_declarations(old, allowed) == strip_declarations(
            updated, allowed
        ), module
    old_register = (OUT / "register_entry.txt").read_text(encoding="utf-8")
    register = (ROOT / REGISTER).read_text(encoding="utf-8")
    pattern = r"(?ms)^- finding_id: UIUX-F-12[34]\n.*?(?=^- finding_id:|\Z)"
    assert re.sub(pattern, "", old_register) == re.sub(pattern, "", register)
    parsed = yaml.safe_load(register)
    assert parsed is not None
    for finding in ("123", "124"):
        old = re.search(
            rf"(?ms)^- finding_id: UIUX-F-{finding}\n.*?(?=^- finding_id:|\Z)",
            old_register,
        ).group()
        updated = re.search(
            rf"(?ms)^- finding_id: UIUX-F-{finding}\n.*?(?=^- finding_id:|\Z)", register
        ).group()
        assert "finding_status: OPEN" in updated
        assert "status: REMEDIATION_IMPLEMENTED_PENDING_RUNTIME_RETEST" in updated
        assert "original_static_status: STATIC_CONFIRMED" in updated
        # Historical problem/source trace/recommendation content retained verbatim.
        for start, end in (("  problem:", "  original_static_status:"),):
            assert (
                old[old.index(start) :].rstrip()
                == updated[updated.index(start) : updated.index(end)].rstrip()
            )
    http = json.loads((OUT / "RUNTIME_HTTP.json").read_text(encoding="utf-8"))
    assert len(http) == 12
    browser = json.loads((OUT / "BROWSER.json").read_text(encoding="utf-8"))
    assert browser["visibleAccountSummaryIdentityVerified"]
    for surface, field in (
        ("measurement", "contract_item"),
        ("certificate", "contract"),
    ):
        observations = [r for r in http if r["surface"] == surface]
        assert len(observations) == 6
        assert all(
            r["status"] == 200
            and not r["model_deltas"]
            and not r["forbidden_metadata_matches"]
            for r in observations
        )
        limited = [
            r for r in observations if r["actor"] == "uiux.persona.project-manager"
        ]
        assert len(limited) == 5
        assert {r["label"] for r in limited} == {
            "authorized GET",
            "missing required field redisplay",
        } | {f"forced {k} source; otherwise valid form" for k in "CDX"}
        assert browser[surface]["options"] == limited[0]["options"]
        assert browser[surface]["expandedPopupInspected"]
    preflight = json.loads((OUT / "RUNTIME_BEFORE.json").read_text(encoding="utf-8"))
    assert preflight["site_only_membership_candidates_all_tenants"] == []
    assert preflight["site_only_runtime"] == "PENDING_NO_EXISTING_QUALIFYING_ACTOR"
    integrity = json.loads((OUT / "RUNTIME_INTEGRITY.json").read_text(encoding="utf-8"))
    assert (
        integrity["models_compared"] == 519
        and integrity["business_audit_authority_unchanged"]
    )
    files = [ROOT / name for name in new | set(changed)] + [p for p in OUT.glob("*.py")]
    for path in files:
        for number, line in enumerate(
            path.read_text(encoding="utf-8-sig").splitlines(), 1
        ):
            assert line.rstrip() == line or (
                path.suffix == ".md" and line.endswith("  ")
            ), (path, number)
    report = ROOT / REPORT
    for link in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        target = report.parent / link.split("#")[0]
        if target.name not in {"VERIFICATION.json", "INDEX.json"}:
            assert target.exists(), link
    save(
        "VERIFICATION.json",
        {
            "changed_existing_files": changed,
            "new_files_outside_evidence": sorted(new),
            "prior_files_byte_preserved": len(entry["hashes"]) - len(changed),
            "allowed_product_declarations": {
                key: sorted(value) for key, value in declarations.items()
            },
            "all_other_product_source_bytes_preserved": True,
            "all_other_finding_entries_byte_preserved": True,
            "batch01_and_batch02_code_and_evidence_preserved": True,
            "plan_registry_roadmap_services_models_settings_templates_preserved": True,
            "entry_capture_correction": "ENTRY.json intended report path retained copied BATCH_02 filename; actual new report is BATCH_03 only. No BATCH_02 report was modified.",
            "independent_runtime_available_controls": {
                "UIUX-F-123": "PASS_6_HTTP_AND_MEASUREMENT_BROWSER",
                "UIUX-F-124": "PASS_6_HTTP_AND_CERTIFICATE_BROWSER",
            },
            "both_findings_required_site_only_runtime": "PENDING_NO_EXISTING_QUALIFYING_ACTOR",
            "finding_closure": "NONE_BOTH_REMAIN_OPEN",
            "batch04_through09": "NOT_EXECUTED",
            "wave_c": "NOT_STARTED",
            "production_cep078_cep079_git_writes": "NOT_EXECUTED",
            "boundary_evidence_checks": "PASS",
            "decision": "BATCH_03_IMPLEMENTED_RUNTIME_RETEST_PENDING",
        },
    )
    manifest = {
        p.relative_to(ROOT).as_posix(): sha(p)
        for p in sorted(OUT.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and p.name != "INDEX.json"
    }
    for name in new | set(changed):
        manifest[name] = sha(ROOT / name)
    save("INDEX.json", manifest)
    print(
        "Boundary/preservation, baseline attribution, independent available runtime evidence: PASS; required site-only runtime PENDING"
    )
