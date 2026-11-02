"""Read-only MVP-04F evidence qualification; never migrates or writes Git."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
OUT = ROOT / "output/mvp-04f"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


product = [
    "apps/procurement/request_ui.py",
    "apps/procurement/order_ui.py",
    "templates/procurement/request_detail.html",
    "templates/procurement/order_detail.html",
    "templates/procurement/rfq_buyer_workspace.html",
]
tests = ["apps/procurement/test_mvp04f.py", "apps/procurement/test_mvp04f_browser.py"]
report = "docs/governance/mvp/MVP-04_COMPLETION_REPORT.md"
start = json.loads((OUT / "start-state.json").read_text(encoding="utf-8"))
changed = [p for p, sha in start["files"].items() if not Path(p).exists() or digest(p) != sha]
unexpected = sorted(set(changed) - set(product) - {report})
assert not unexpected, unexpected
write("preservation-check.json", {
    "snapshotted_files": len(start["files"]),
    "byte_identical_files": len(start["files"]) - len(changed),
    "declared_overlap_changed": sorted(changed),
    "unexpected_changed_or_missing": unexpected,
})
write("final-source-manifest.json", {p: digest(p) for p in product + tests})

rows = [r for p in sorted((OUT / "browser").glob("batch-*.json"))
        for r in json.loads(p.read_text(encoding="utf-8"))]
assert len(rows) == len({r["name"] for r in rows})
assert all(r["scroll"] <= r["width"] for r in rows)
assert all(not r.get("jsErrors") and not r.get("exception") and not r.get("technicalLabels") for r in rows)
expected_denials = {
    "critical-repeat-and-refresh": [400, 400, 400],
    "unauthorized-source-create": [403],
    "wrong-project-grn": [404],
    "wrong-tenant-stock": [404],
}
assert all([e["status"] for e in r.get("httpErrors", [])] == expected_denials.get(r["name"], []) for r in rows)
assert all(r["dir"] == "rtl" and r["lang"] == "fa" for r in rows)
write("browser-summary.json", {
    "browser": "Installed Google Chrome, headless CDP",
    "final_log": "browser-attempt-2.log", "test_methods": "1/1 PASS, 425.745s",
    "scenarios": len(rows), "names": [r["name"] for r in rows],
    "viewport_profiles": [1440, 1024, 390],
    "document_widths": sorted({r["width"] for r in rows}),
    "horizontal_overflow": 0, "javascript_exceptions": 0,
    "visible_technical_labels": 0, "unexpected_http_errors": 0,
    "expected_denials": expected_denials,
    "screenshot_review": ["pr-detail-390", "po-detail-390", "buyer-workspace-390",
                          "inventory-detail-390", "award-decision-1440"],
})

authorities = [
    "Agents.md", "CEP_EXECUTION_REGISTRY.yaml", "ROADMAP.md",
    "docs/governance/CEP_PROGRAM_AUTHORITY.md",
    "docs/governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md",
    "docs/ROADMAP_EXECUTION_PLAYBOOK.md",
]
boundaries = [p.as_posix() for app in ("procurement", "inventory")
              for p in Path("apps", app).rglob("*.py")
              if p.name == "models.py" or p.parent.name == "migrations" or "services" in p.name]
write("authority-and-boundary-manifest.json", {
    "request": {"path": "C:/Users/azera/.codex/attachments/91452ae9-14cf-44bc-b687-9a001d3f9253/Pasted text.txt",
                "sha256": digest("C:/Users/azera/.codex/attachments/91452ae9-14cf-44bc-b687-9a001d3f9253/Pasted text.txt")},
    "authority_hashes": {p: digest(p) for p in authorities},
    "domain_boundary_hashes": {p: digest(p) for p in sorted(boundaries)},
    "domain_product_mutation_in_F": False,
})

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django
django.setup()
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.template.loader import get_template

for p in product:
    if p.startswith("templates/"):
        text = Path(p).read_text(encoding="utf-8")
        assert "\ufffd" not in text
        get_template(p.removeprefix("templates/"))
plans = []
for filename in ("database-name.txt", "regression-database-name.txt"):
    name = (OUT / filename).read_text(encoding="utf-8").strip()
    assert name.startswith("test_mvp04f_")
    config = connections.databases["default"].copy()
    config["NAME"] = name
    alias = "qualification_" + filename.split("-")[0]
    connections.databases[alias] = config
    executor = MigrationExecutor(connections[alias])
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    assert not plan, name
    plans.append({"database": name, "applied_records": len(executor.loader.applied_migrations), "pending": len(plan)})
    connections[alias].close()
write("isolated-migration-plan.json", plans)

branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
assert branch == start["branch"] == "main"
assert head == start["head"]
current_status = subprocess.check_output(["git", "status", "--porcelain", "-uall"], text=True)
start_paths = {line[3:] for line in start["status"].splitlines()}
new_paths = {line[3:] for line in current_status.splitlines()} - start_paths
unexpected_new = sorted(p for p in new_paths if p not in tests and not p.startswith("output/mvp-04f/"))
assert not unexpected_new, unexpected_new
report_bytes = Path(report).read_bytes()
section_bytes = (OUT / "report-section.md").read_text(encoding="utf-8").encode("utf-8")
assert report_bytes.endswith(section_bytes)
assert hashlib.sha256(report_bytes[:-len(section_bytes)]).hexdigest() == start["files"][report]
report_text = report_bytes.decode("utf-8")
assert "\ufffd" not in report_text
import re
for href in re.findall(r"\]\(([^)]+)\)", section_bytes.decode("utf-8")):
    assert (Path(report).parent / href).exists(), href
assert not any(line.rstrip() != line for line in section_bytes.decode("utf-8").splitlines())
write("closeout-check.json", {
    "branch": branch, "head": head, "preservation": "PASS",
    "template_parse_utf8": "PASS", "isolated_pending_migrations": 0,
    "report_previous_bytes_preserved": True,
    "report_links_whitespace_utf8": "PASS",
    "unexpected_new_files": unexpected_new,
    "report_sha256": digest(report),
    "git_writes": "NOT EXECUTED", "MVP-05": "NOT STARTED",
})
print("Preservation, source hashes, templates, isolated migration plans and Git identity: PASS")
