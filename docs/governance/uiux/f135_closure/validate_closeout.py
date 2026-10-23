"""Read-only final assertions and evidence manifest for the F-135 closure."""
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BASE = OUT.parent


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


entry = read("ENTRY.json")
current = read("FINAL_RECONCILIATION.json")
assert current["F-135"]["result"] == current["RV-025"]["result"] == "PASS"
assert current["wave_e"] == "WAVE_E_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT"
assert current["final_uiux_status"] == "TARGETED_RUNTIME_VALIDATION_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT"
assert current["UX_READY_FOR_UAT"] == "NOT_ISSUED"
assert current["accepted_baseline_test_failures"] == 18
assert current["unresolved_attributable_regressions"] == current["indeterminate_regressions"] == 0

key = b"f135_closure:"
for name in ("UIUX_FINDINGS_REGISTER.yaml", "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "UIUX_RUNTIME_VALIDATION_RESULTS.yaml"):
    expected = (OUT / ("entry_" + name)).read_bytes()
    if name == "UIUX_RUNTIME_VALIDATION_RESULTS.yaml":
        expected = expected.replace(b"current Wave E/final results are wave_e_targeted_closure;", b"current F-135/RV-025 and Wave E/final results are f135_closure;", 1)
    prefix, appendix = (BASE / name).read_bytes().rsplit(key, 1)
    assert prefix.rstrip() == expected.rstrip(), name
    assert json.loads(appendix.decode("utf-8").strip())["recorded_at"]
assert (BASE / "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md").read_bytes().endswith((OUT / "entry_UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md").read_bytes())

docs = {"docs/governance/uiux/" + name for name in ("UIUX_FINDINGS_REGISTER.yaml", "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md", "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md")}
product = {"apps/accounts/static/js/erp_jalali.js", "templates/base.html"}
unexpected = [p for p, h in entry["hashes"].items() if p not in docs | product and sha(ROOT / p) != h]
assert not unexpected, unexpected
assert sha(ROOT / ".git/index") == entry["index_sha256"]
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == entry["head"]
assert read("DATA_INTEGRITY.json")["all_business_and_authorization_models_unchanged"]
assert read("SOURCE_INTEGRITY.json")["head_index_registry_roadmap_unchanged"]

suite = ET.parse(OUT / "focused_affected.xml").getroot()[0]
assert len(suite.findall("testcase")) == 18
assert int(suite.get("tests")) == 21
assert int(suite.get("errors")) == int(suite.get("failures")) == 0
cases = read("KEYBOARD_TESTS.json")
assert len(cases) == 22 and all(c["result"] == "PASS" for c in cases)
for c in cases:
    if "before" in c and "after" in c:
        assert c["before"]["dates"] == c["after"]["dates"]
        assert c["before"]["url"] == c["after"]["url"]
        if c["case"].startswith("Escape"):
            assert c["after"]["openPickers"] == 0

captures = read("CAPTURES.json")
assert {(1440, 900), (390, 844)} == {tuple(c["viewport"]) for c in captures}
for c in captures:
    assert c["pageWidth"] <= c["viewport"][0]
    assert c["rtl"] == "rtl" and c["lang"] == "fa"
    assert all(d["direction"] == "ltr" for d in c["dates"])
    assert (OUT / (c["name"] + ".jpg")).read_bytes()[:2] == b"\xff\xd8"
    assert (OUT / (c["name"] + ".ax.txt")).is_file()
    if "escape" in c["name"]:
        assert c["openPickers"] == 0
assert not any(r["level"] == "error" for r in read("BROWSER_LOGS.json"))
for r in read("EVIDENCE_RECORDS.json"):
    for p in r["screenshots"]:
        assert (OUT / p).is_file(), p
for p in (OUT / "COMPLETION_REPORT.md", BASE / "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md"):
    for target in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
        assert (p.parent / target).is_file(), (p.name, target)
assert read("COVERAGE_DELTA.json")["blocked_or_unrepresented_material_cell"] is None
meta = read("BROWSER_METADATA.json")
assert meta["temporaryViewportReset"] and meta["createdTabClosed"]

checks = {}
for name, cmd in (
    ("javascript_syntax", ["node", "--check", "apps/accounts/static/js/erp_jalali.js"]),
    ("whitespace", ["git", "diff", "--check", "--", *sorted(product)]),
):
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, (name, result.stdout, result.stderr)
    checks[name] = "PASS"

result = {"status": "PASS", "F-135": "RESOLVED / PASS", "RV-025": "PASS", "current_results_reconciled": True, "historical_evidence_preserved": True, "accepted_wave_d_e_not_repeated": True, "all_other_entry_files_unchanged": True, "head_index_registry_roadmap": "UNCHANGED", "business_authorization_integrity": "PASS; no business rows added/changed/deleted", "focused_affected": "18 PASS + 3 subtests PASS", "browser_keyboard": "22 PASS", "console_errors": 0, "links_screenshots_viewports": "PASS; CSS viewport measurements authoritative; native JPEG sizes retained", "checks": checks, "yaml_validation": "Appended JSON-compatible mappings parsed; exact historical prefixes checked. Whole historical YAML parser not available; no full YAML parse claimed.", "stop": "After F-135 / RV-025 reconciliation; no CEP/Production/Sign-off/Git writes"}
(OUT / "CLOSEOUT_VALIDATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
manifest = {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "MANIFEST.json"}
(OUT / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Closeout PASS: F-135 RESOLVED; RV-025 PASS; accepted complete-with-debt statuses and history preserved. STOP.")
