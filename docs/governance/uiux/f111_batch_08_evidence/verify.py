"""BATCH-08 closure gates, source boundaries and prior evidence preservation."""

import ast
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
TARGETS = {
    "procurement": ("PurchaseRequestForm", "purchase_request_create"),
    "contracts": ("ContractForm", "contract_create"),
    "inventory": ("WarehouseForm", "warehouse_create"),
    "workforce": ("TrainingRequirementForm", "workforce_training_requirement_create"),
}
FINDINGS = ("113", "116", "117", "125")


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))


def save(name, value):
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def outside(source, app, kind):
    tree = ast.parse(source)
    for node in tree.body:
        if (
            kind == "forms"
            and isinstance(node, ast.ClassDef)
            and node.name == TARGETS[app][0]
        ):
            node.body = [
                v
                for v in node.body
                if not isinstance(v, ast.FunctionDef) or v.name != "__init__"
            ]
        if (
            kind == "views"
            and isinstance(node, ast.FunctionDef)
            and node.name == TARGETS[app][1]
        ):
            assert (
                isinstance(node.body[0], ast.Assign)
                and node.body[0].targets[0].id == "form"
            )
            node.body[0] = ast.Pass()
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        remove = set()
        if (
            kind == "forms"
            and app in {"contracts", "workforce"}
            and node.module == "apps.organizations.authorization"
        ):
            remove = {"scope_queryset"}
        if (
            kind == "forms"
            and app == "contracts"
            and node.module == "apps.organizations.models"
        ):
            remove = {"OrganizationMembership"}
        if (
            kind == "views"
            and app == "contracts"
            and node.module == "apps.organizations.authorization"
        ):
            remove = {"get_active_membership"}
        node.names = [v for v in node.names if v.name not in remove]
    tree.body = [n for n in tree.body if not isinstance(n, ast.ImportFrom) or n.names]
    return ast.dump(tree, include_attributes=False)


def main():
    entry = read("ENTRY_BASELINE.json")
    allowed = {
        f"apps/{app}/{kind}.py" for app in TARGETS for kind in ("forms", "views")
    } | {"docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"}
    changed = [
        p
        for p, digest in entry["hashes"].items()
        if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != digest
    ]
    assert set(changed) == allowed, changed
    for app in TARGETS:
        for kind in ("forms", "views"):
            assert outside(
                (ROOT / f"apps/{app}/{kind}.py").read_text(encoding="utf-8"), app, kind
            ) == outside(
                (OUT / f"{app}_{kind}_entry.txt").read_text(encoding="utf-8"), app, kind
            ), (app, kind)
    original = (OUT / "register_entry.txt").read_bytes()
    current = (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_bytes()

    def strip_targets(content):
        for finding in FINDINGS:
            pattern = (
                rb"- finding_id: UIUX-F-"
                + finding.encode()
                + rb"\r?\n.*?(?=- finding_id: UIUX-F-|\Z)"
            )
            content = re.sub(pattern, b"", content, flags=re.S)
        return content

    assert strip_targets(original) == strip_targets(current)
    for finding in FINDINGS:
        block = re.search(
            rb"- finding_id: UIUX-F-"
            + finding.encode()
            + rb"\r?\n.*?(?=- finding_id: UIUX-F-|\Z)",
            current,
            re.S,
        ).group()
        for token in (
            b"finding_status: RESOLVED",
            b"status: RUNTIME_VERIFIED_RESOLVED",
            b"decision: BATCH_08_RUNTIME_VERIFIED_RESOLVED",
        ):
            assert token in block
    focused = ET.parse(OUT / "focused.xml")
    assert not focused.findall(".//failure") and not focused.findall(".//error")
    assert "86 passed, 106 subtests passed" in (OUT / "focused.txt").read_text(
        encoding="utf-8"
    )
    attribution = read("REGRESSION_ATTRIBUTION.json")
    assert (
        attribution["baseline_identical_to_current"]
        and len(attribution["failures"]) == 22
        and not attribution["new_failures"]
    )
    assert "22 failed, 83 passed, 129 subtests passed" in (
        OUT / "regression.txt"
    ).read_text(encoding="utf-8")
    for file, token in (
        ("django_check.txt", "no issues"),
        ("migration_check.txt", "No changes detected"),
        ("ruff.txt", "All checks passed"),
        ("ruff_format.txt", "1 file already formatted"),
    ):
        assert token in (OUT / file).read_text(encoding="utf-8"), file
    http = read("RUNTIME_HTTP.json")
    summary = read("HTTP_SUMMARY.json")
    assert summary["all_pass"] and len(http) == 88
    assert all(
        r["real_authentication_csrf"]
        and r["business_and_success_audit_unchanged"]
        and not r["forbidden_metadata"]
        for r in http
    )
    projects = read("BROWSER_PAYLOAD.json")["projects"]
    by_finding = {}
    for finding in FINDINGS:
        rows = [r for r in http if r["finding"] == "UIUX-F-" + finding]
        assert len(rows) == 22
        for alias, expected_keys in (
            ("uiux.persona.project-manager", "AB"),
            ("uiux.persona.tenant-admin", "ABCD"),
            ("uiux.reference.batch03.site-only", ""),
        ):
            actor_rows = [r for r in rows if r["actor"] == alias]
            assert any(r["case"] == "GET" for r in actor_rows)
            assert any(r["case"] == "required-field redisplay" for r in actor_rows)
            assert all(
                {o["value"] for o in r["options"] if o["value"]}
                == {projects[k] for k in expected_keys}
                for r in actor_rows
            )
            if expected_keys != "ABCD":
                keys = "CDX" if expected_keys else "ABCDX"
                assert all(
                    any(
                        r["case"] == "forced Project " + k and r["errors"]
                        for r in actor_rows
                    )
                    for k in keys
                )
        by_finding["UIUX-F-" + finding] = {
            "status": "RUNTIME_VERIFIED_RESOLVED",
            "http_observations": len(rows),
            "C_D_X_site_only_rejection": True,
        }
    direct = read("DIRECT_SERVICE.json")
    assert len(direct) == 32 and all(r["denied"] and not r["mutations"] for r in direct)
    browser = read("RUNTIME_BROWSER.json")
    assert len(browser) == 14
    aliases = {
        "limited": "uiux.persona.project-manager",
        "organization": "uiux.persona.tenant-admin",
        "site-only": "uiux.reference.batch03.site-only",
    }
    for row in browser:
        control = next(
            r
            for r in http
            if r["finding"] == row["finding"]
            and r["actor"] == aliases[row["actor"]]
            and r["case"] == "GET"
        )
        assert [
            {k: o[k] for k in ("value", "label")} for o in row["options"]
        ] == control["options"]
        assert row["required"] == (row["finding"] in {"UIUX-F-113", "UIUX-F-116"})
        if "server POST" in row["label"] or "service denial POST" in row["label"]:
            assert row["errors"]
        if row["actor"] != "organization":
            forbidden = "CDX" if row["actor"] == "limited" else "BCDX"
            assert all(projects[k] not in row["bodyText"] for k in forbidden)
    assert {r["finding"] for r in browser} == {"UIUX-F-" + f for f in FINDINGS}
    assert len(list(OUT.glob("browser_*.png"))) == 14
    integrity = read("RUNTIME_INTEGRITY.json")
    assert integrity["tables"] == 519 and integrity["authority_unchanged"]
    assert set(integrity["runtime_deltas"]) <= {"sessions.Session"}
    assert (
        not integrity["preexisting_business_rows_changed"]
        and not integrity["unauthorized_mutations"]
        and not integrity["runtime_success_audits"]
    )
    assert (
        integrity["training_requirements"] == 0
        and not integrity["persistent_preparation_mutations"]
    )
    fixtures = read("FIXTURES.json")
    assert not fixtures["created"] and not fixtures["authority_mutations"]
    for file in ("SERVER_IDENTITY.json", "initial_SERVER_IDENTITY.json"):
        assert all(row["predates_server"] for row in read(file)["source_files"])
    cleanup = read("SERVER_CLEANUP.json")
    assert (
        cleanup["identity_verified"]
        and cleanup["stopped"]
        and not cleanup["listener_remaining"]
    )
    report = OUT.parent / "UIUX_F111_BATCH_08_REMEDIATION_REPORT.md"
    for link in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        target = report.parent / link.split("#")[0]
        assert target.exists() or target == OUT / "VERIFICATION.json", link
    for p in (
        report,
        ROOT / "tests/test_uiux_f111_pattern_project_scope.py",
        *OUT.glob("*.py"),
    ):
        assert all(
            line == line.rstrip() for line in p.read_text(encoding="utf-8").splitlines()
        ), p
    assert (
        subprocess.run(
            ["git", "diff", "--check"], cwd=ROOT, capture_output=True
        ).returncode
        == 0
    )
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        == entry["head"]
    )
    save(
        "VERIFICATION.json",
        {
            "decision": "BATCH_08_RUNTIME_VERIFIED_RESOLVED",
            "findings": by_finding,
            "baseline_hashes_compared": len(entry["hashes"]),
            "changed_existing_files": changed,
            "non_target_source_AST_preserved": True,
            "all_other_finding_blocks_byte_preserved": True,
            "prior_batches_01_through_07_preserved": True,
            "batch_09": "UNCHANGED_NOT_EXECUTED",
            "wave_c": "NOT_STARTED",
            "focused": "86 tests +106 subtests PASS",
            "regression": "83 tests +129 subtests PASS;22 exactly reproduced baseline failures;zero new failures",
            "browser_observations": len(browser),
            "browser_real_server_POSTs": 4,
            "browser_client_only_control": 1,
            "http_observations": len(http),
            "direct_denials": len(direct),
            "integrity_tables": 519,
            "temporary_authority": "NONE",
            "migration": "NO",
            "production": "NO ACTION",
            "cep_078_079": "NOT_EXECUTED",
            "git_add_commit_push": "NOT_EXECUTED",
        },
    )
    save(
        "INDEX.json",
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name not in {"INDEX.json", "verification.txt"}
        },
    )
    print(
        "PASS: BATCH-08 closed; all four findings independently verified; prior work preserved"
    )


if __name__ == "__main__":
    main()
