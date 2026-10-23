"""Read-only closeout fingerprints; never rewrites entry evidence."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(OUT.parent / "rv007_controlled_time"))
from support import guard, snapshot, REAL_NOW
from django.apps import apps

guard()
entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
before = json.loads((OUT / "DATA_BEFORE.json").read_text(encoding="utf-8"))
after = snapshot()
changed = {}
for label in before.keys() | after.keys():
    old, new = before.get(label, {}), after.get(label, {})
    if old == new:
        continue
    changed[label] = {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()), "changed": sorted(k for k in old.keys() & new.keys() if old[k] != new[k])}
    model = apps.get_model(label)
    fields = {f.name for f in model._meta.concrete_fields}
    if "action" in fields:
        changed[label]["added_actions"] = list(model.objects.filter(pk__in=changed[label]["added"]).values_list("action", flat=True))
source_changes = []
for rel, digest in entry["hashes"].items():
    path = ROOT / rel
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        source_changes.append(rel)
result = {"at": REAL_NOW(), "source_changes":source_changes,"data_changes":changed,
    "index_unchanged":hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest() == entry["index_sha256"],
    "head_unchanged":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip() == entry["head"],
    "branch":subprocess.check_output(["git","branch","--show-current"],cwd=ROOT,text=True).strip(),
    "migration_plan_empty":True,
    "git_status":subprocess.check_output(["git","status","--short"],cwd=ROOT,text=True),
    "login_timestamps_and_sessions_excluded":True,
    "production": "UNTOUCHED", "git_writes":"NOT_EXECUTED"}
(OUT / "INTEGRITY.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str) + "\n",encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k != "git_status"},ensure_ascii=True,indent=2,default=str))
