"""Read-only Development grounding and preservation for F-121 browser closure."""

import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
PRIOR = ROOT / "docs/governance/uiux/f111_batch_01_runtime_closure_evidence"
ctx = runpy.run_path(
    str(ROOT / "docs/governance/uiux/f111_batch_01_evidence/runtime_retest.py"),
    run_name="browser_ground_helpers",
)
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.documents.models import Document
from apps.documents.services import typed_links_for_document


def save(name, value):
    (OUT / name).write_text(
        json.dumps(value, default=str, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


if sys.argv[1] == "before":
    old = json.loads((PRIOR / "ENTRY.json").read_text(encoding="utf-8"))
    source = {name: sha(ROOT / name) for name in old["source_hashes"]}
    assert source == old["source_hashes"]
    assert git("rev-parse", "HEAD") == old["head"]
    user, org, member, authority, objects = ctx["ground"]()
    assert json.loads(json.dumps(authority, default=str)) == old["authority"]
    expected_fixture = json.loads((PRIOR / "FIXTURE.json").read_text(encoding="utf-8"))
    doc = Document.objects.get(pk=expected_fixture["document_id"], organization=org)
    assert str(doc.current_version_id) == expected_fixture["version_id"]
    assert doc.title == doc.reference == "BATCH_01_RUNTIME_CLOSURE_FIXTURE"
    assert str(doc.pk) in objects["mixed_context_documents"]
    fixture_file = json.loads((PRIOR / "FIXTURE_FILE.json").read_text(encoding="utf-8"))
    assert sha(ROOT / fixture_file["path"]) == fixture_file["sha256"]
    executor = MigrationExecutor(connection)
    assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
    models = ctx["snapshot"]()
    prior_models = json.loads(
        (PRIOR / "POST_FIXTURE_BASELINE.json").read_text(encoding="utf-8")
    )["models"]
    deltas = [key for key in models if models[key] != prior_models[key]]
    assert set(deltas) <= {"sessions.Session"}, deltas
    register = ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
    raw = register.read_text(encoding="utf-8")
    entry = raw.split("- finding_id: UIUX-F-121\n", 1)[1].split(
        "- finding_id: UIUX-F-122\n", 1
    )[0]
    assert "finding_status: OPEN" in entry
    (OUT / "F121_BEFORE.yaml").write_text(
        "- finding_id: UIUX-F-121\n" + entry, encoding="utf-8"
    )
    paths = set()
    for directory in (
        "apps",
        "core",
        "config",
        "templates",
        "tests",
        "docs/governance/uiux",
    ):
        paths.update(
            p
            for p in (ROOT / directory).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and OUT not in p.parents
        )
    save(
        "PRESERVATION_BEFORE.json",
        {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)},
    )
    save("MODELS_BEFORE.json", models)
    save(
        "ENTRY.json",
        {
            "branch": git("branch", "--show-current"),
            "head": git("rev-parse", "HEAD"),
            "upstream": git(
                "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
            ),
            "upstream_head": git("rev-parse", "@{upstream}"),
            "dirty_state": git("status", "--short"),
            "source_hashes": source,
            "authority": authority,
            "authority_matches_accepted": True,
            "objects": objects,
            "fixture": {
                "document_id": doc.pk,
                "version_id": doc.current_version_id,
                "label": doc.title,
                "file_sha256": fixture_file["sha256"],
                "links": [
                    {"target_type": link.target_type, "target_id": str(link.target.pk)}
                    for link in typed_links_for_document(doc)
                ],
            },
            "model_deltas_since_accepted_fixture_baseline": deltas,
            "pending_migrations": 0,
            "settings": "config.settings.development",
            "database": connection.settings_dict["NAME"],
            "read_only_grounding": True,
        },
    )
    print(
        "Grounding PASS: unchanged HEAD/Billing/authority; retained mixed fixture; business/audit baseline unchanged"
    )
elif sys.argv[1] == "after":
    before = json.loads((OUT / "MODELS_BEFORE.json").read_text(encoding="utf-8"))
    after = ctx["snapshot"]()
    deltas = [key for key in after if after[key] != before[key]]
    assert set(deltas) <= {"sessions.Session"}, deltas
    save(
        "RUNTIME_INTEGRITY.json",
        {
            "model_tables_compared": len(after),
            "model_deltas": deltas,
            "business_audit_and_authority_unchanged": True,
            "user_last_login_excluded": True,
        },
    )
    print("Browser runtime integrity PASS: business, audit and authority unchanged")
