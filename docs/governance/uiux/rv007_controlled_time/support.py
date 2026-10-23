"""Development-only evidence support; never serializes credentials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
import django
django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

REAL_NOW = timezone.now

def guard():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    assert connection.vendor == "postgresql"
    assert connection.settings_dict["NAME"] == "construction_erp"
    assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
    executor = MigrationExecutor(connection)
    assert not executor.migration_plan(executor.loader.graph.leaf_nodes())

def save(name, data):
    (OUT / name).write_text(json.dumps(data, default=str, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))

def snapshot():
    result = {}
    for model in apps.get_models():
        if model._meta.app_label == "sessions":
            continue
        columns = [f.attname for f in model._meta.concrete_fields if f.name != "last_login"]
        result[model._meta.label] = {str(row[model._meta.pk.attname]): hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest() for row in model.objects.values(*columns)}
    return result

def controlled_now():
    return datetime.fromisoformat(read("CLOCK.json")["application_now"])

def set_clock(value, phase):
    save("CLOCK.json", {"application_now": value.isoformat(), "phase": phase, "actual_wall_clock": REAL_NOW(), "test_only": True, "os_clock_modified": False})

def ground():
    guard()
    assert not (OUT / "ENTRY.json").exists()
    paths = set(subprocess.check_output(["git", "ls-files"], text=True).splitlines())
    for parent in ("apps", "core", "config", "templates", "tests"):
        paths.update(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / parent).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    paths.update({"docs/governance/uiux/UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md", "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"})
    save("ENTRY.json", {"recorded_at": REAL_NOW(), "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(), "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "upstream": subprocess.check_output(["git", "rev-parse", "@{u}"], text=True).strip(), "origin_main": subprocess.check_output(["git", "rev-parse", "origin/main"], text=True).strip(), "status": subprocess.check_output(["git", "status", "--short"], text=True), "diff_name_status": subprocess.check_output(["git", "diff", "--name-status"], text=True, stderr=subprocess.DEVNULL), "diff_stat": subprocess.check_output(["git", "diff", "--stat"], text=True, stderr=subprocess.DEVNULL), "index_sha256": hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest(), "hashes": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(paths) if (ROOT / p).is_file()}, "authority": "Human RV-007 Controlled-Time Final Closure; application-only frozen clock, canonical services, no direct date/state edits; attribution of 27 failures; no Production/Git/Wave D/CEP-078/079", "touch_set": ["rv007_controlled_time evidence", "attributable test fixture seams only", "Wave C results/report/findings reconciliation"], "database": {k: connection.settings_dict[k] for k in ("ENGINE", "HOST", "PORT", "NAME")}})
    save("DATA_BEFORE.json", snapshot())
    print("Development grounded; source/data/Git fingerprints saved.")

if __name__ == "__main__":
    ground()
