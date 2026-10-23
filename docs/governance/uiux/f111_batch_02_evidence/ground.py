"""Bounded BATCH-02 source preservation; no application or database mutation."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8")


def hashes():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in git(
            "ls-files", "--cached", "--others", "--exclude-standard"
        ).splitlines()
        if (ROOT / name).is_file()
        and not name.startswith("docs/governance/uiux/f111_batch_02_evidence/")
    }


if __name__ == "__main__":
    entry = {
        "branch": git("branch", "--show-current").strip(),
        "head": git("rev-parse", "HEAD").strip(),
        "upstream": git("rev-parse", "@{u}").strip(),
        "divergence": git("rev-list", "--left-right", "--count", "HEAD...@{u}").strip(),
        "status": git("status", "--short"),
        "diff_names": git("diff", "--name-status"),
        "diff_stat": git("diff", "--stat"),
        "hashes": hashes(),
        "actual_execution_touch_set": [
            "apps/billing/forms.py:RetentionReleaseForm clearance choices + reader import",
            "tests/test_uiux_f111_pattern_clearance_scope.py",
            "docs/governance/uiux/UIUX_F111_BATCH_02_REMEDIATION_REPORT.md",
            "docs/governance/uiux/f111_batch_02_evidence/",
            "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml:UIUX-F-122 only",
        ],
        "views": "Existing BATCH-01 trusted actor/membership wiring is sufficient; no edit",
        "migration": "NO",
        "authority": "Human BATCH-02-only execution request and canonical plan",
    }
    assert entry["branch"] == "main"
    (OUT / "ENTRY.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    (OUT / "forms_entry.txt").write_bytes((ROOT / "apps/billing/forms.py").read_bytes())
    register = (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_bytes()
    (OUT / "register_entry.txt").write_bytes(register)
    print("Entry preserved:", len(entry["hashes"]), "files; bounded touch set recorded")
