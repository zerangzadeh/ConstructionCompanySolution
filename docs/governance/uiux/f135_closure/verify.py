"""Prove the bounded code/data delta and record validation without replaying debt."""
import difflib
import json
import subprocess
import xml.etree.ElementTree as ET

from entry import ROOT, OUT, guard, snapshot, sha, git, save

guard()
entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
before = json.loads((OUT / "DATA_BEFORE.json").read_text(encoding="utf-8"))
after = snapshot()
assert before == after, "Existing business/authorization data changed or new records added"
save("DATA_INTEGRITY.json", {"all_business_and_authorization_models_unchanged": True, "existing_rows_changed": 0, "rows_added": 0, "rows_deleted": 0, "exclusions": ["sessions", "User.last_login"], "permissions_roles_memberships_scopes_workflows_financial_data": "UNCHANGED", "portal_fixture_and_expiry": "UNCHANGED; accepted evidence retained; no portal renewal or replay", "guard": "config.settings.development; DEBUG true; loopback PostgreSQL construction_erp; no pending migrations"})
allowed = {"apps/accounts/static/js/erp_jalali.js", "templates/base.html"}
changed = [p for p, h in entry["hashes"].items() if not p.startswith("docs/governance/uiux/") and sha(ROOT / p) != h]
assert set(changed) == allowed, changed
script = (ROOT / "apps/accounts/static/js/erp_jalali.js").read_text(encoding="utf-8")
old = (OUT / "entry_erp_jalali.js").read_text(encoding="utf-8")
start = script.index('    document.addEventListener("keydown", (event) => {')
end = script.index('    document.addEventListener("click", (event) => {', start)
assert script[:start] + script[end:] == old
assert (ROOT / "templates/base.html").read_text(encoding="utf-8") == (OUT / "entry_base.html").read_text(encoding="utf-8").replace("?v=20261023-labels", "?v=20261023-escape", 1)
save("SOURCE_INTEGRITY.json", {"changed_product_paths": changed, "only_new_script_behavior": "One guarded Escape listener: hide open picker; return focus from hidden calendar content to its existing trigger. No changes outside this block to existing JS.", "cache_reference_only": True, "all_other_entry_product_sources_unchanged": True, "existing_F110_labels_preserved": True, "head_index_registry_roadmap_unchanged": git("rev-parse", "HEAD").strip() == entry["head"] and sha(ROOT / ".git/index") == entry["index_sha256"] and all(sha(ROOT / p) == entry["hashes"][p] for p in ("CEP_EXECUTION_REGISTRY.yaml", "ROADMAP.md")), "changes": {p: {"entry": entry["hashes"][p], "current": sha(ROOT / p)} for p in changed}})
(OUT / "SOURCE_DELTA.diff").write_text("".join(difflib.unified_diff(old.splitlines(keepends=True), script.splitlines(keepends=True), fromfile="session-entry/erp_jalali.js", tofile="current/erp_jalali.js")), encoding="utf-8")
suite = ET.parse(OUT / "focused_affected.xml").getroot()[0]
assert len(suite.findall("testcase")) == 18 and int(suite.get("tests")) == 21 and int(suite.get("failures")) == 0 and int(suite.get("errors")) == 0
browser = json.loads((OUT / "KEYBOARD_TESTS.json").read_text(encoding="utf-8"))
assert len(browser) == 22 and all(c["result"] == "PASS" for c in browser)
save("REGRESSION_ATTRIBUTION.json", {"selection": ["tests/test_jalali_forms.py", "apps/accounts/test_jalali.py", "tests/test_list_filters.py", "tests/test_uiux_wave_e_targeted.py"], "focused": "7 Jalali form/format cases PASS", "affected_regression": "11 existing table-filter/name/localization cases PASS; 3 date-field subtests PASS", "total": "18 PASS; zero failures/errors", "original_18_baseline_failures": "ACCEPTED_UNCHANGED; prior rv007_controlled_time/REGRESSION_ATTRIBUTION.json retained", "inherited_statutory_copy_assertion": "RETAINED separately; wave_de_fixture_closure/REGRESSION_ATTRIBUTION.json", "inherited_projects_navigation_assertion": "RETAINED separately; wave_e_targeted_closure/BASELINE_PROBE.json; not rerun or repaired", "F135": "ATTRIBUTABLE_ACCESSIBILITY_REPAIR_VERIFIED; prior inherited defect now resolved", "unresolved_attributable_regressions": 0, "indeterminate_regressions": 0, "full_suite_claim": "NONE; unrelated baseline cases not repeated"})
save("VALIDATION.json", {"focused_and_affected_tests": "18/18 PASS; 3 subtests PASS", "browser_keyboard_tests": "22/22 PASS", "javascript_syntax": "node --check apps/accounts/static/js/erp_jalali.js: PASS", "django_system_check": "PASS; no issues", "browser_errors": 0, "development_tailwind_warnings": "Retained in BROWSER_LOGS.json", "date_parsing_filter_semantics": "UNCHANGED; exact entry-source equality outside new keydown block, focused form/parsing/filter regression and unchanged live date values/query URLs", "schema_migration": "NONE", "data_integrity": "PASS; no business/auth row changes or additions"})
print("Integrity PASS: only Escape handler/cache reference changed; business/auth data unchanged; 18 tests + 22 browser cases PASS.")
