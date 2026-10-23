"""Validate final references, retained evidence and conservative result semantics."""
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BASE = OUT.parent
KEY = b"wave_e_targeted_closure:"


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


entry = read("ENTRY.json")
current = read("FINAL_RECONCILIATION.json")
assert current["wave_e"] == "WAVE_E_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT"
assert current["final_uiux_status"] == "TARGETED_RUNTIME_VALIDATION_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT"
assert current["RV-025"]["result"] == "FAIL_ACCESSIBILITY"
assert current["RV-025"]["finding_ids"] == ["UIUX-F-135"]
assert current["UX_READY_FOR_UAT"] == "NOT_ISSUED"
assert current["accepted_baseline_test_failures"] == 18
assert current["unresolved_attributable_regressions"] == current["indeterminate_regressions"] == 0
for name in ("UIUX_FINDINGS_REGISTER.yaml", "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "UIUX_RUNTIME_VALIDATION_RESULTS.yaml"):
    original = (OUT / ("entry_" + name)).read_bytes()
    expected = original
    if name == "UIUX_RUNTIME_VALIDATION_RESULTS.yaml":
        expected = expected.replace(b"  status: TARGETED_RUNTIME_VALIDATION_PARTIAL", b"  status: TARGETED_RUNTIME_VALIDATION_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT", 1)
        expected = expected.replace(b"Current D/E results are wave_de_fixture_closure; RV-020/RV-022 remain retained PASS and earlier sections are historical.", b"Accepted Wave D is wave_de_fixture_closure; current Wave E/final results are wave_e_targeted_closure; earlier sections remain historical.", 1)
    p = BASE / name
    prefix, tail = p.read_bytes().rsplit(KEY, 1)
    assert prefix.replace(b"\r\n", b"\n").rstrip() == expected.replace(b"\r\n", b"\n").rstrip(), name
    appendix = json.loads(tail.decode("utf-8").strip())
    assert appendix["recorded_at"]
    # Preserve original historical newline bytes, not just text equivalence.
    p.write_bytes(expected.rstrip() + b"\n\n" + KEY + tail)

old = json.loads((OUT / "entry_UIUX_RUNTIME_FIXTURE_REGISTRY.yaml").read_text(encoding="utf-8"))
new = json.loads((BASE / "UIUX_RUNTIME_FIXTURE_REGISTRY.yaml").read_text(encoding="utf-8"))
assert all(new[k] == v for k, v in old.items())
assert (BASE / "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md").read_bytes().endswith((OUT / "entry_UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md").read_bytes())

mutable_docs = {"docs/governance/uiux/" + p for p in ("UIUX_FINDINGS_REGISTER.yaml", "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "UIUX_RUNTIME_FIXTURE_REGISTRY.yaml", "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md", "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md")}
product = set(read("SOURCE_INTEGRITY.json")["changed_existing_product_files"])
unexpected = [p for p, h in entry["hashes"].items() if p not in mutable_docs | product and sha(ROOT / p) != h]
assert not unexpected, unexpected
assert sha(ROOT / ".git/index") == entry["index_sha256"]
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == entry["head"]

coverage = read("COVERAGE_RECONCILIATION.json")
assert coverage["unrepresented_material_cell"] is None
assert not any(v == "BLOCKED" for c in coverage["cells"] for v in c["dimension_cells"].values())
for c in coverage["cells"]:
    for path in c["screenshots"]:
        assert (OUT / path).exists(), path

sizes = set()
native_captures = []
for c in read("BROWSER_CAPTURES.json"):
    p = OUT / (c["name"] + ".jpg")
    data = p.read_bytes()
    assert data[:2] == b"\xff\xd8"
    offset = 2
    size = None
    while offset < len(data):
        assert data[offset] == 255
        marker = data[offset + 1]
        length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[offset + 5:offset + 9])
            size = (width, height)
            break
        offset += 2 + length
    css_size = (c["viewport"]["width"], c["viewport"]["height"])
    assert size and min(size) > 0
    assert css_size in {(1440, 900), (1024, 768), (390, 844)}
    assert c["pageWidth"] <= css_size[0], p.name
    sizes.add(css_size)
    native_captures.append({"file": p.name, "browser_css_viewport": css_size, "native_jpeg_dimensions": size, "exact_bitmap_match": size == css_size})
assert {(1440, 900), (1024, 768), (390, 844)} <= sizes
records = read("EVIDENCE_RECORDS.json")
assert [r["result"] for r in records] == ["PASS", "PASS", "PASS", "FAIL_ACCESSIBILITY"]
for r in records:
    for p in r["screenshots"]:
        assert (OUT / p).exists()
for p in (OUT / "COMPLETION_REPORT.md", BASE / "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md"):
    for target in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
        assert (p.parent / target).exists(), (p.name, target)
assert all(l["level"] != "error" for l in read("BROWSER_LOGS.json"))
assert read("HTTP_SUMMARY.json")["all_passed"]
assert read("DATA_INTEGRITY.json")["existing_rows_unchanged"]

notes = {"non_result_drafts": ["Initial read-only portal discovery used an incorrect relation name; corrected to portal_invitation before mutation", "Buyer/Owner permission assumptions rejected; retained invitation manager's existing permission used", "No third portal grant existed; negative HTTP harness uses an existing foreign opportunity identifier and wrong actor, not fabricated grants", "A nonexistent Quality credential alias was not used; canonical retained actor uiux.audit.project logged in normally", "Baseline probe supplies entry templates in memory only; no Git restore/write"], "browser_cache": "A plain reload initially retained old generic calendar names; versioned existing script URL loads new naming code and was then directly verified", "secrets": "Existing DPAPI secrets in memory only; failing assertion HTML redacted; no plaintext token/email/password/session/CSRF evidence", "yaml_validation": "Whole historical YAML parser unavailable; appended JSON-compatible mappings parsed and historical prefix bytes compared exactly. Fixture registry JSON parsed in full."}
(OUT / "EXECUTION_NOTES.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
result = {"status": "PASS", "historical_evidence_preserved": True, "accepted_wave_d_unchanged": True, "only_declared_product_and_reconciliation_files_changed": True, "links_and_screenshots": "PASS", "browser_css_viewports": "PASS; direct innerWidth/innerHeight measurements at the three requested sizes", "native_capture_limitation": "Native browser JPEG bitmaps are provider-sized and do not uniformly equal CSS viewport dimensions; exact dimensions recorded, no resizing or image alteration", "native_captures": native_captures, "head_index_registry_roadmap": "UNCHANGED", "supported_result_semantics": "PASS; three requested closures PASS; inherited F-135 keeps RV-025 FAIL_ACCESSIBILITY; evidence-complete statuses do not assert all-findings PASS", "no_missing_material_targeted_cell": True, "stop": "After Wave E/final reconciliation; no continuation"}
(OUT / "CLOSEOUT_VALIDATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
manifest = {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "MANIFEST.json"}
(OUT / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Closeout validation PASS; historical evidence preserved, references/dimensions verified, results conservative. STOP.")
