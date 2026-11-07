"""Bounded source/evidence checks; no application or Git mutations."""
from pathlib import Path
import hashlib
import difflib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
adopters = [
    "templates/home.html",
    "templates/projects/detail.html",
    "templates/projects/control_comparison.html",
    "templates/projects/control_exceptions.html",
    "templates/reporting/dashboard.html",
    "apps/reporting/templates/reporting/_read_model_card.html",
    "templates/inventory/valuation_workbench.html",
    "apps/billing/templates/billing/commercial_control_dashboard.html",
    "apps/billing/templates/billing/statutory_operations_dashboard.html",
]
new = [
    "apps/accounts/static/css/erp_dashboard_reporting.css",
    "templates/components/dashboard_reporting_assets.html",
    "templates/components/dashboard_metric.html",
    "tests/test_dashboard_reporting.py",
    "scripts/verification/dashboard_reporting_validate.py",
]
changed = [*adopters, "apps/inventory/p8_views.py", "docs/ui-guidelines.md", *new]
checks = {}
for relative in adopters:
    source = (ROOT / relative).read_text(encoding="utf-8")
    assert not any(marker in source for marker in ("\ufffd", "????", "Ø", "Ù", "Û", "Ã")), relative
    assert '<style' not in source and 'style="' not in source, relative
    baseline = (OUT / "baseline" / relative).read_text(encoding="utf-8")
    before_forms = re.findall(r'<form\b.*?</form>', baseline, re.S)
    after_forms = re.findall(r'<form\b.*?</form>', source, re.S)
    def contracts(forms):
        return [{"method": re.findall(r'method="([^"]*)"', f), "action": re.findall(r'action="([^"]*)"', f), "names": re.findall(r'name="([^"]*)"', f), "csrf": "csrf_token" in f} for f in forms]
    assert contracts(before_forms) == contracts(after_forms), relative
    checks[relative] = {"forms_unchanged": True, "utf8": True, "sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}
before = (OUT / "baseline/docs/ui-guidelines.md").read_text(encoding="utf-8")
after = (ROOT / "docs/ui-guidelines.md").read_text(encoding="utf-8")
prefix = after.partition("## 53. Dashboard Pattern")[0]
external = ("| Confirmations and focused dialogs |", "| Toasts, confirmations and interactive alerts |")
def prior_lines(text):
    return [line for line in text.rstrip().splitlines() if not line.startswith(external)]
assert prior_lines(prefix) == prior_lines(before), "Prior UI guidance changed outside the independently edited Stage 6 table row"
(OUT / "concurrent-guideline.diff").write_text("".join(difflib.unified_diff(before.splitlines(True), prefix.splitlines(True))), encoding="utf-8")
checks["prior_ui_guidelines_preserved_except_independent_stage6_row"] = True
checks["view_diff"] = subprocess.check_output(["git", "diff", "--", "apps/inventory/p8_views.py"], text=True)
checks["files"] = changed
(OUT / "source-checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "files-changed.md").write_text("# Files changed by this task\n\n" + "\n".join(f"- `{p}`" for p in changed) + "\n\nEvidence, baseline copies and one-shot local verification helpers are under `output/dashboard-reporting/`.\n", encoding="utf-8")
print("Form contracts, UTF-8, scoped files and prior UI guidelines: PASS")
