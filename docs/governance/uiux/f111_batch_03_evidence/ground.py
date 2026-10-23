"""Bounded BATCH-03 source preservation; no application or database mutation."""

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
        and not name.startswith("docs/governance/uiux/f111_batch_03_evidence/")
    }


if __name__ == "__main__":
    if (OUT / "ENTRY.json").exists():
        raise SystemExit("Entry already captured; refusing to overwrite baseline")
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
            "apps/billing/forms.py:PayableMeasurementForm, PayableCertificateForm",
            "tests/test_uiux_f111_pattern_payable_scope.py",
            "docs/governance/uiux/UIUX_F111_BATCH_03_REMEDIATION_REPORT.md",
            "docs/governance/uiux/f111_batch_03_evidence/",
            "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml:UIUX-F-123 and UIUX-F-124 only",
        ],
        "views": "apps/billing/views.py:payable_measurement_create, payable_certificate_create",
        "migration": "NO",
        "authority": "Human BATCH-03-only execution request and canonical plan",
    }
    assert entry["branch"] == "main"
    (OUT / "ENTRY.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    (OUT / "forms_entry.txt").write_bytes((ROOT / "apps/billing/forms.py").read_bytes())
    register = (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_bytes()
    (OUT / "register_entry.txt").write_bytes(register)
    print("Entry preserved:", len(entry["hashes"]), "files; bounded touch set recorded")
