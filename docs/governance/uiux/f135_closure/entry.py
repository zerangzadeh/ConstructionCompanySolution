"""Development-only F-135 evidence; no business fixture mutation."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(OUT.parent / "rv007_controlled_time"))
from support import guard, snapshot, REAL_NOW


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


guard()
if __name__ == "__main__":
    assert not (OUT / "ENTRY.json").exists()
    files = [p for parent in ("apps", "core", "config", "templates", "tests", "static", "docs/governance/uiux") for p in (ROOT / parent).rglob("*") if p.is_file() and "__pycache__" not in p.parts and OUT not in p.parents]
    files += [ROOT / p for p in ("CEP_EXECUTION_REGISTRY.yaml", "ROADMAP.md")]
    save("ENTRY.json", {"recorded_at": REAL_NOW(), "branch": git("branch", "--show-current").strip(), "head": git("rev-parse", "HEAD").strip(), "upstream": git("rev-parse", "@{u}").strip(), "origin_main": git("rev-parse", "origin/main").strip(), "status": git("status", "--short"), "diff_name_status": git("diff", "--name-status"), "diff_stat": git("diff", "--stat"), "index_sha256": sha(ROOT / ".git/index"), "hashes": {p.relative_to(ROOT).as_posix(): sha(p) for p in files}, "authority": "Direct Human F-135 only: minimal Escape dismissal/focus; focused/affected/authenticated desktop-mobile keyboard checks; findings/results/evidence reconciliation; STOP. No CEP-078/079/Production/Human Sign-off/Git writes.", "touch_set": ["apps/accounts/static/js/erp_jalali.js", "existing script cache-version reference in templates/base.html", "F-135 evidence and current findings/results/impact/Wave E/completion pointers only"], "preexisting_debt": "Accepted 18 baseline failures plus separately evidenced statutory/Projects assertions retained without rerun/reclassification; F-135 only is authorized for remediation"})
    save("DATA_BEFORE.json", snapshot())
    (OUT / "entry_erp_jalali.js").write_bytes((ROOT / "apps/accounts/static/js/erp_jalali.js").read_bytes())
    (OUT / "entry_base.html").write_bytes((ROOT / "templates/base.html").read_bytes())
    print("Development/migration guard PASS; HEAD/index/source/business-data entry evidence saved.")
