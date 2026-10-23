"""Read-only Batch-01 source and preservation checks; write scoped evidence."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tree(source):
    return ast.parse(source)


def canonical(node):
    return ast.dump(node, include_attributes=False)


def verify_source():
    results = {}
    for kind in ("forms", "views"):
        relative = f"apps/billing/{kind}.py"
        original = subprocess.check_output(
            ["git", "show", f"HEAD:{relative}"], cwd=ROOT
        ).decode("utf-8")
        current = (ROOT / relative).read_text(encoding="utf-8")
        old = tree(original)
        new = tree(current)
        old_nodes = {
            n.name: n for n in old.body if isinstance(n, ast.FunctionDef | ast.ClassDef)
        }
        new_nodes = {
            n.name: n for n in new.body if isinstance(n, ast.FunctionDef | ast.ClassDef)
        }
        assert old_nodes.keys() == new_nodes.keys()
        if kind == "views":
            allowed = {
                "guarantee_create",
                "compliance_evidence_create",
                "retention_release_create",
            }
            unchanged = [k for k in old_nodes if k not in allowed]
            assert all(
                canonical(old_nodes[k]) == canonical(new_nodes[k]) for k in unchanged
            )
        else:
            allowed = {
                "_CommercialEvidenceForm": {"_configure_create"},
                "GuaranteeForm": {"__init__"},
                "ComplianceEvidenceForm": {"__init__"},
                "RetentionReleaseForm": {"__init__"},
            }
            unchanged = [k for k in old_nodes if k not in allowed]
            assert all(
                canonical(old_nodes[k]) == canonical(new_nodes[k]) for k in unchanged
            )
            for name, methods in allowed.items():

                def retained(node, excluded=methods):
                    return [
                        canonical(n)
                        for n in node.body
                        if not isinstance(n, ast.FunctionDef) or n.name not in excluded
                    ]

                assert retained(old_nodes[name]) == retained(new_nodes[name]), name
        results[relative] = {
            "entry_HEAD_source_sha256": sha(original.encode()),
            "current_sha256": sha((ROOT / relative).read_bytes()),
            "out_of_scope_declarations_unchanged": True,
            "unchanged_declarations": unchanged,
        }
    return results


if __name__ == "__main__":
    entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
    allowed = {
        "apps/billing/forms.py",
        "apps/billing/views.py",
        "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml",
    }
    checked, unexpected = 0, []
    for relative, expected in entry["hashes"].items():
        if relative in allowed:
            continue
        checked += 1
        path = ROOT / relative
        if not path.is_file() or sha(path.read_bytes()) != expected:
            unexpected.append(relative)
    assert not unexpected, unexpected
    register = (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_bytes()
    start = register.index(b"- finding_id: UIUX-F-121")
    end = register.index(b"- finding_id: UIUX-F-122")
    register_entry = json.loads((OUT / "REGISTER_ENTRY.json").read_text())
    assert (
        sha(register[:start] + register[end:]) == register_entry["other_entries_sha256"]
    )
    output = {
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "entry_capture_note": "ENTRY.json is the execution capture containing initial Batch-01 Billing edits; original Billing source is replayed from unchanged HEAD. Eight prior F-111 product files are preserved by content hash.",
        "existing_files_preserved": checked,
        "unexpected_changes": unexpected,
        "other_finding_entries_byte_preserved": True,
        "source_boundary": verify_source(),
        "git_status": subprocess.check_output(
            ["git", "status", "--short"], cwd=ROOT, text=True
        ),
    }
    (OUT / "VERIFICATION.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    print(
        f"Boundary PASS: {checked} existing files and all other findings preserved; only authorized Billing declarations differ"
    )
