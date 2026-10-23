"""Capture the effective dirty-entry baseline and BATCH-09 mutation boundary."""

import hashlib
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


paths = []
for folder in (
    "apps",
    "core",
    "config",
    "templates",
    "tests",
    "docs",
    "graphify-out",
    "protected_documents",
):
    paths.extend(
        p
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and OUT not in p.parents
    )
paths.extend(
    ROOT / p for p in ("Agents.md", "CEP_EXECUTION_REGISTRY.yaml", "ROADMAP.md")
)
for app in ("equipment", "quality", "safety"):
    for name in ("forms", "views"):
        (OUT / f"{app}_{name}_entry.txt").write_bytes(
            (ROOT / f"apps/{app}/{name}.py").read_bytes()
        )
(OUT / "register_entry.txt").write_bytes(
    (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_bytes()
)
baseline = {
    "branch": git("branch", "--show-current"),
    "head": git("rev-parse", "HEAD"),
    "upstream": git("rev-parse", "--abbrev-ref", "@{upstream}"),
    "origin_main": git("rev-parse", "origin/main"),
    "ahead_behind_local_reference": git(
        "rev-list", "--left-right", "--count", "HEAD...origin/main"
    ),
    "network_fetch": False,
    "status": git("status", "--short"),
    "diff_name_status": git("diff", "--name-status"),
    "diff_stat": git("diff", "--stat"),
    "hashes": {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    },
    "authority": "Explicit attached Human BATCH-09 end-to-end request; minimum synthetic Development fixtures and existing canonical authority permitted; no Git writes",
    "actual_execution_touch_set": {
        "product": {
            "equipment": ["MaintenanceRecordForm", "maintenance_create"],
            "quality": ["QualityIssueForm", "issue_create"],
            "safety": ["SafetyIncidentForm", "incident_create"],
        },
        "files": [
            f"apps/{app}/{name}.py"
            for app in ("equipment", "quality", "safety")
            for name in ("forms", "views")
        ],
        "tests": ["tests/test_uiux_f111_pattern_operational_scope.py"],
        "governance": [
            "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml:F-115/F-126/F-127 only",
            "docs/governance/uiux/UIUX_F111_BATCH_09_REMEDIATION_REPORT.md",
            "docs/governance/uiux/f111_batch_09_evidence/*",
        ],
        "runtime": "Reuse eligible personas/Projects/masters; minimum synthetic fixtures/canonical existing authority only if preflight proves necessary; fingerprint and cleanup",
        "models_schema_migrations_services_templates_settings_shared_helpers": "NO CHANGES",
    },
}
(OUT / "ENTRY_BASELINE.json").write_text(
    json.dumps(baseline, indent=2) + "\n", encoding="utf-8"
)
print("Captured entry hashes:", len(baseline["hashes"]))
