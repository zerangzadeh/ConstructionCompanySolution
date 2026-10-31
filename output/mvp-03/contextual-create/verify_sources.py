"""Read-only source, template and configured Development migration evidence."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.template.loader import get_template

folder = Path(__file__).parent
entry = json.loads((folder / "entry-state.json").read_text(encoding="utf-8"))
prior = json.loads(
    (folder.parent / "remediation-20261030/static-source-evidence.json").read_text(
        encoding="utf-8"
    )
)
templates = [
    "estimates/create.html", "estimates/detail.html",
    "contracts/create.html", "contracts/detail.html",
    "billing/claim_form.html", "billing/claim_detail.html",
    "components/business_create_context.html",
]
for name in templates:
    get_template(name)


def digest(value):
    return hashlib.sha256(value.replace(b"\r\n", b"\n")).hexdigest()


protected = []
for source in prior["protected_sources_unchanged"]:
    name = source["path"]
    committed = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=root)
    current = (root / name).read_bytes()
    matches = digest(current) == digest(committed)
    assert matches, name
    protected.append(dict(path=name, sha256_normalized=digest(current), matches_head=True))

changed_since_entry = []
for name, before in entry["entry_source_hashes"].items():
    current = (root / name).read_bytes()
    if before not in {digest(current), hashlib.sha256(current).hexdigest()}:
        changed_since_entry.append(name)

executor = MigrationExecutor(connection)
pending = [f"{m.app_label}.{m.name}" for m, backwards in
           executor.migration_plan(executor.loader.graph.leaf_nodes()) if not backwards]
result = {
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "template_compilation": "PASS", "templates": templates,
    "protected_sources_unchanged": protected,
    "changed_among_tracked_entry_changes": changed_since_entry,
    "newly_modified_tracked_paths": sorted(set(
        subprocess.check_output(["git", "diff", "--name-only"], cwd=root, text=True).splitlines()
    ) - set(entry["tracked_entry_changes"])),
    "configured_development_pending_migrations": pending,
    "development_migrations_applied_by_task": False,
    "git_commit_or_push_by_task": False,
}
(folder / "static-source-evidence.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"Templates: {len(templates)} PASS; protected sources: {len(protected)} unchanged; pending migrations: {pending}")
