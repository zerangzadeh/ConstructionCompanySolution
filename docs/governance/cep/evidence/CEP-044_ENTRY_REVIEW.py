"""Read-only canonical/repository/Development catalog inspection for CEP-044."""

import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
EVIDENCE = ROOT / "docs/governance/cep/evidence"
SOURCES = Path(
    "E:/ERP_Construction_Documents/New Version/"
    "BONIRA_TRUE_LATEST_STATE_RECONSTRUCTION_20261013/Consolidated_Packages"
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def records(text):
    section = text.split("\nceps:\n", 1)[1]
    return dict(
        re.findall(
            r"^  (CEP-\d{3}):\n(.*?)(?=^  CEP-\d{3}:|^\S|\Z)",
            section,
            re.MULTILINE | re.DOTALL,
        )
    )


manifest = (ROOT / "docs/governance/cep/CEP_PROMPT_MANIFEST.yaml").read_text("utf-8")
identities = {}
for cep, path, expected in re.findall(
    r"^  (CEP-\d{3}):\n    path: (.*?)\n    canonical: true\n    immutable: true\n    sha256: (\w+)",
    manifest,
    re.MULTILINE,
):
    actual = sha((ROOT / path).read_bytes())
    assert actual == expected, (cep, actual, expected)
    identities[cep] = actual
assert len(identities) == 79

registry = (ROOT / "CEP_EXECUTION_REGISTRY.yaml").read_text("utf-8")
ceps = records(registry)
states = {
    cep: re.search(r"    execution:\n      status: (\S+)", block)[1]
    for cep, block in ceps.items()
}
entry = {
    "date": "2026-10-19",
    "branch": git("branch", "--show-current"),
    "head": git("rev-parse", "HEAD"),
    "origin_main": git("rev-parse", "origin/main"),
    "remote_main": git("ls-remote", "origin", "refs/heads/main").split()[0],
    "initial_working_tree": "CLEAN (verified before this evidence script was created)",
    "initial_diff_name_status": "EMPTY",
    "initial_diff_stat": "EMPTY",
    "checkpoint_parent": git("rev-parse", "HEAD^"),
    "checkpoint_changed_paths": git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"
    ).splitlines(),
    "checkpoint_message": git("log", "-1", "--format=%s"),
    "checkpoint_reconciliation": "Commit message cep-044 contains CEP043 implementation/evidence, not CEP044 implementation. CEP043 execution baseline retained separately.",
    "all_79_prompt_hashes": identities,
    "source_resolution": "Local canonical prompt; named upstream sources unavailable locally (rg --files); approved consolidated recovery used only for missing sources.",
    "sources": {},
    "extracts": {},
}
assert entry["branch"] == "main"
assert entry["head"] == entry["origin_main"] == entry["remote_main"]
assert entry["checkpoint_parent"] == "da01c850b6fbacf41c793548426cb53e9bbc6813"

requests = {
    "CODEX_EXECUTION_PACKAGE_DESIGN": [
        "packages/CEP-044.md",
        "BONIRA_CEP_DEPENDENCY_REGISTER.csv",
    ],
    "FINAL_IMPLEMENTATION_MASTER_BACKLOG": [
        "BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG.csv"
    ],
    "REQUIRED_SPECIFICATION_COMPLETION": [
        "BONIRA_ACCOUNTING_RECOGNITION_OWNER_MATRIX.csv",
        "BONIRA_CONFIGURATION_PROFILE_MATRIX.csv",
        "BONIRA_WRITE_OFF_POLICY_SPECIFICATION.md",
        "BONIRA_REQUIRED_SPECIFICATION_COMPLETION_REGISTER.csv",
    ],
    "PRODUCT_DECISION_FREEZE": ["BONIRA_FINAL_PRODUCT_DECISION_REGISTER.md"],
    "IMPLEMENTATION_ROADMAP": ["BONIRA_IMPLEMENTATION_GATE_REGISTER.csv"],
}
approved_recovery = json.loads((EVIDENCE / "CEP-043_ENTRY.json").read_text("utf-8"))[
    "sources"
]
dependencies = []
for suffix, names in requests.items():
    path = SOURCES / f"BONIRA_{suffix}_CONSOLIDATED_LATEST.zip"
    source = {"path": str(path), "sha256": sha(path.read_bytes()), "members": {}}
    assert source["sha256"] == approved_recovery[path.name]["sha256"]
    with zipfile.ZipFile(path) as archive:
        for name in names:
            data = archive.read(name)
            source["members"][name] = sha(data)
            value = data.decode("utf-8-sig")
            if "DEPENDENCY_REGISTER" in name:
                dependencies = list(csv.DictReader(io.StringIO(value)))
                entry["extracts"][name] = [
                    r for r in dependencies if r["Dependent CEP"] == "CEP-044"
                ]
            elif "MASTER_BACKLOG.csv" in name:
                entry["extracts"][name] = [
                    r
                    for r in csv.DictReader(io.StringIO(value))
                    if r["Backlog ID"] in {"IMB-0062", "IMB-0063"}
                ]
            elif "OWNER_MATRIX.csv" in name:
                entry["extracts"][name] = [
                    r
                    for r in csv.DictReader(io.StringIO(value))
                    if r["Source Family"]
                    in {
                        "Billing Progress Claim",
                        "Billing Payable Certificate",
                        "Procurement Supplier Invoice Match",
                        "AP/AR Write-off",
                    }
                ]
            elif "SPECIFICATION_COMPLETION_REGISTER.csv" in name:
                entry["extracts"][name] = [
                    r
                    for r in csv.DictReader(io.StringIO(value))
                    if r["Specification ID"] in {"SPEC-002", "SPEC-024"}
                ]
            elif "GATE_REGISTER.csv" in name:
                entry["extracts"][name] = [
                    r
                    for r in csv.DictReader(io.StringIO(value))
                    if r["Gate ID"] == "GATE-05"
                ]
            elif "FINAL_PRODUCT_DECISION" in name:
                entry["extracts"][name] = {}
                for pd in ("PD-015", "PD-030"):
                    match = re.search(
                        r"^### `" + pd + r"`.*?(?=^### |\Z)",
                        value,
                        re.MULTILINE | re.DOTALL,
                    )
                    assert match
                    entry["extracts"][name][pd] = match[0]
            elif "WRITE_OFF" in name:
                entry["extracts"][name] = value
    entry["sources"][path.name] = source

ready, conditional = [], []
for cep in ceps:
    if int(cep[-3:]) > 79 or states[cep] == "COMPLETE":
        continue
    deps = [r for r in dependencies if r["Dependent CEP"] == cep]
    if any(
        states[r["Prerequisite CEP"]] != "COMPLETE" and r["Condition"] == "ALWAYS"
        for r in deps
    ):
        continue
    unmet = [r for r in deps if states[r["Prerequisite CEP"]] != "COMPLETE"]
    if unmet:
        conditional.append({"cep": cep, "requires_condition_review": unmet})
    else:
        ready.append(cep)

# Independently compare every prompt prerequisite set to the canonical register.
for cep in identities:
    prompt = (
        ROOT / f"docs/governance/cep/PROMPTS/{cep}_EXECUTION_PROMPT.md"
    ).read_text("utf-8")
    section = prompt.split("## 8. Prerequisite CEPs", 1)[1].split("## 9.", 1)[0]
    actual = set(re.findall(r"^- `(CEP-\d{3})`", section, re.MULTILINE))
    expected = {
        r["Prerequisite CEP"] for r in dependencies if r["Dependent CEP"] == cep
    }
    assert actual == expected, (cep, actual, expected)
entry["all_prerequisite_sets_match_canonical_dependency_register"] = True
entry["frontier"] = {
    "dependency_ready": ready,
    "conditional_entry_review": conditional,
    "readiness_is_not_eligibility": True,
}
entry["entry_conditions"] = {
    "CEP-008": states["CEP-008"],
    "external_dependencies": "NONE",
    "GATE-05": "NOT_PASSED; exit-only, not a build-entry prerequisite",
    "migration_impact": "NONE; stop before any required schema/data migration",
    "standing_authority": "CURRENT_GOVERNED_NON_PRODUCTION_ONLY; conditional on package boundaries",
}

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.conf import settings
from django.db import connection

from apps.workflows.models import WorkflowType
from apps.workflows.registry import registry as workflow_registry

cfg = settings.DATABASES["default"]
assert settings.SETTINGS_MODULE == "config.settings.development"
assert cfg["ENGINE"] == "django.db.backends.postgresql"
assert cfg["HOST"] in ("localhost", "127.0.0.1", "::1")
assert connection.Database.__name__ == "psycopg"
assert connection.Database.__version__.startswith("3.")
with connection.cursor() as cursor:
    cursor.execute(
        "SELECT app,name FROM django_migrations WHERE app IN ('workflows','accounting','subledgers','organizations') ORDER BY app,name"
    )
    applied = cursor.fetchall()
entry["environment"] = {
    "settings": "config.settings.development",
    "database": "Django PostgreSQL backend / Psycopg 3 / verified loopback; no credentials retained",
    "driver_version": connection.Database.__version__,
    "migration_tips": {
        app: [name for a, name in applied if a == app][-1]
        for app in ("workflows", "accounting", "subledgers", "organizations")
    },
    "workflow_types_code": list(workflow_registry.workflow_types),
    "workflow_types_database": list(
        WorkflowType.objects.values_list("code", flat=True)
    ),
    "workflow_catalog_no_migration_alternative": "apps/workflows/admin.py SystemCatalogAdmin allows superuser add/change; catalog absence alone is NOT proof of unavoidable migration.",
    "business_data_written": False,
}
path = EVIDENCE / "CEP-044_ENTRY.json"
path.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", "utf-8")
print(
    json.dumps(
        {
            "entry": str(path.relative_to(ROOT)),
            "prompt_hashes": len(identities),
            "dependencies": "ALL MATCH",
            "ready": ready,
            "head": entry["head"],
        }
    )
)
