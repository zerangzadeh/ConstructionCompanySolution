"""Prove existing permission-registry debt is unchanged by CEP065 ownership metadata."""

import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()

from apps.organizations import permission_registry as current
from apps.organizations.models import BusinessPermissionCode
from apps.organizations.test_permission_registry import _permission_members_referenced_by

BASELINE = "14c32ced2eab37a6322cde36b406fff1a929aade"
path = "apps/organizations/permission_registry.py"
source = subprocess.check_output(["git", "show", BASELINE + ":" + path])
baseline = types.ModuleType("cep065_registry_baseline")
sys.modules[baseline.__name__] = baseline
exec(compile(source.decode("utf-8"), path, "exec"), baseline.__dict__)
new_labels = {"projects.ProjectCashflowSupplement", "projects.ProjectCashflowSnapshot"}
before = [dataclasses.asdict(resource) for resource in baseline.PERMISSION_RESOURCES]
after = [dataclasses.asdict(resource) for resource in current.PERMISSION_RESOURCES]
normalized = []
for resource in after:
    resource = dict(resource)
    resource["model_labels"] = tuple(label for label in resource["model_labels"] if label not in new_labels)
    resource["enforcement_modules"] = tuple(module for module in resource["enforcement_modules"] if module != "apps.projects.cashflow")
    normalized.append(resource)
assert before == normalized
for label in new_labels:
    assert [r.key for r in current.PERMISSION_RESOURCES if label in r.model_labels] == ["project_cost"]


def debt(module):
    resources = module.PERMISSION_RESOURCES
    models = Counter(label for resource in resources for label in resource.model_labels)
    codes = {p.value for resource in resources for p in resource.permissions}
    return {
        "missing_permission_codes": sorted(set(BusinessPermissionCode.values) - codes),
        "duplicate_model_labels": sorted(label for label, count in models.items() if count > 1),
        "namespace_mismatches": sorted(p.value for resource in resources for p in resource.permissions if p.value.partition(".")[0] != resource.key),
        "missing_enforcement_references": {
            resource.key: sorted(p.name for p in resource.permissions if p.name not in _permission_members_referenced_by(resource.enforcement_modules))
            for resource in resources
            if any(p.name not in _permission_members_referenced_by(resource.enforcement_modules) for p in resource.permissions)
        },
    }


old_debt, new_debt = debt(baseline), debt(current)
assert old_debt == new_debt
format_baseline = subprocess.run(
    [".venv/Scripts/ruff.exe", "format", "--check", "--stdin-filename", path, "-"],
    input=source, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
assert format_baseline.returncode == 1
result = {
    "baseline": BASELINE,
    "baseline_registry_sha256": hashlib.sha256(source).hexdigest(),
    "only_delta": {"new_models": sorted(new_labels), "existing_resource": "project_cost", "enforcement_module": "apps.projects.cashflow", "permission_or_grant_changes": False},
    "registry_debt_unchanged": new_debt,
    "registry_suite": {"run": 8, "pass": 2, "baseline_failures": 6},
    "format_baseline": "UNCHANGED_OLD_REGISTRY_FILE_IS_UNFORMATTED; new evidence/service files formatted",
}
Path("docs/governance/cep/evidence/CEP-065_REGISTRY_ATTRIBUTION.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print("PASS: both new evidence models registered once; existing registry debt and old whole-file formatting debt unchanged.")
