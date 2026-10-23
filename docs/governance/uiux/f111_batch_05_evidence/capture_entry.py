"""Capture the effective dirty baseline before BATCH-05 product mutation."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


paths = []
for folder in ("apps", "core", "config", "templates", "tests", "docs", "graphify-out"):
    paths.extend(
        p
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and OUT not in p.parents
    )
paths.extend(
    ROOT / p for p in ("Agents.md", "CEP_EXECUTION_REGISTRY.yaml", "ROADMAP.md")
)
hashes = {
    p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in paths
}
for name in ("forms", "views"):
    (OUT / f"{name}_entry.txt").write_bytes(
        (ROOT / f"apps/inventory/{name}.py").read_bytes()
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
    "hashes": hashes,
    "authority": "Explicit attached Human BATCH-05 request, including minimum synthetic Development fixture preparation; no Git writes",
    "actual_execution_touch_set": {
        "product": [
            "apps/inventory/forms.py:StockTransactionForm.__init__",
            "apps/inventory/views.py:transaction_create",
        ],
        "tests": ["tests/test_uiux_f111_pattern_stock_scope.py"],
        "governance": [
            "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml:UIUX-F-118",
            "docs/governance/uiux/UIUX_F111_BATCH_05_REMEDIATION_REPORT.md",
            "docs/governance/uiux/f111_batch_05_evidence/*",
        ],
        "runtime": "Existing demo Procurement personas/sources first; if absent, canonical receipt/warehouse workflow and temporary existing-role/scope assignment only, documented and revoked",
        "models_schema_migrations_services_templates_settings_shared_helpers": "NO CHANGES",
    },
}
(OUT / "ENTRY_BASELINE.json").write_text(
    json.dumps(baseline, indent=2) + "\n", encoding="utf-8"
)
print("Dirty baseline and exact touch set captured:", len(hashes), "files")
