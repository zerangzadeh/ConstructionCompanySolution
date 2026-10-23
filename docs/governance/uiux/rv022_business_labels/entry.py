"""Development-only entry snapshot for the approved PD-WD-022 delta."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(OUT.parent / "rv007_controlled_time"))
from support import guard, snapshot, REAL_NOW

guard()
assert not (OUT / "ENTRY.json").exists()
paths = set(subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines())
for parent in ("apps", "core", "config", "templates", "tests", "static", "docs/governance/uiux"):
    paths.update(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / parent).rglob("*") if p.is_file() and "__pycache__" not in p.parts and OUT not in p.parents)
data = {"at":str(REAL_NOW()), "head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"branch":subprocess.check_output(["git","branch","--show-current"],cwd=ROOT,text=True).strip(),"upstream":subprocess.check_output(["git","rev-parse","@{u}"],cwd=ROOT,text=True).strip(),"status":subprocess.check_output(["git","status","--short"],cwd=ROOT,text=True),"diff_stat":subprocess.check_output(["git","diff","--stat"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL),"index_sha256":hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest(),"hashes":{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths) if (ROOT/p).is_file()},"authority":"PRODUCT_DECISION.md: direct Human APPROVE OPTION 1; information priority only","actual_touch_set":["apps/workflows/administration_views.py","apps/workflows/administration_presentation.py","templates/workflows/administration/detail.html","apps/workflows/test_cep046_administration.py","docs/governance/uiux/rv022_business_labels/","current UIUX results/findings/impact-map and Wave D/E report pointers"],"pending_migrations":0}
(OUT / "ENTRY.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
(OUT / "DATA_BEFORE.json").write_text(json.dumps(snapshot(),indent=2),encoding="utf-8")
print("Approved presentation delta grounded; prior evidence and business fingerprints saved.")
