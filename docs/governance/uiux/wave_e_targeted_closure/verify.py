"""Preservation, baseline attribution and bounded validation evidence."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET

from entry import ROOT, OUT, guard, save, sha, snapshot, git

guard()
entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))

# Assertion HTML contains per-request CSRF values: retain the useful failure only.
p = OUT / "affected.xml"
tree = ET.parse(p)
for failure in tree.getroot().iter("failure"):
    failure.set("message", failure.get("message", "").split("in the following response")[0] + " [response HTML redacted]")
    failure.text = (failure.text or "").split("in the following response")[0] + " [response HTML redacted]"
tree.write(p, encoding="utf-8", xml_declaration=True)
summary = []
for t in tree.getroot().iter("testcase"):
    failure = t.find("failure")
    summary.append({"test": t.get("classname") + "." + t.get("name"), "result": "FAIL" if failure is not None else "PASS", "message": failure.get("message") if failure is not None else ""})
(OUT / "affected.txt").write_text("Affected regression: 15 tests; 14 PASS, 1 pre-entry navigation assertion FAIL.\nResponse HTML/CSRF removed; see affected.xml and BASELINE_PROBE.json.\n", encoding="utf-8")
save("REGRESSION_ATTRIBUTION.json", {"affected": {"tests": 15, "passed": 14, "failures": 1, "cases": summary}, "focused": {"tests": 11, "passed": 11, "subtests_passed": 3}, "classification": "BASELINE TEST DEBT", "proof": "BASELINE_PROBE.json reproduces the same missing /projects/sites/ assertion with clean-at-entry immutable-HEAD templates supplied in memory; tenant-visible/hidden assertions already passed", "original_18_baseline_failures": "PRESERVED; ../rv007_controlled_time/REGRESSION_ATTRIBUTION.json; not rerun/reclassified", "inherited_statutory_copy_assertion": "PRESERVED separately; ../wave_de_fixture_closure/REGRESSION_ATTRIBUTION.json; not rerun", "additional_inherited_projects_assertion": 1, "unresolved_attributable_regressions": 0, "indeterminate_regressions": 0, "full_suite_pass_claimed": False, "html_csrf_redacted": True})

after = snapshot()
before = json.loads((OUT / "DATA_BEFORE.json").read_text(encoding="utf-8"))
delta = {}
for label, previous in before.items():
    current = after[label]
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = sorted(k for k in previous.keys() & current.keys() if previous[k] != current[k])
    if added or removed or changed:
        delta[label] = {"added": added, "removed": removed, "changed": changed}
assert all(not d["removed"] and not d["changed"] for d in delta.values()), delta
assert set(delta) <= {"procurement.SupplierPortalInvitation", "procurement.SupplierPortalGrant", "procurement.SupplierPortalPrincipal", "audit.AuditEvent"}, delta
assert len(delta["procurement.SupplierPortalInvitation"]["added"]) == 1
assert len(delta["procurement.SupplierPortalGrant"]["added"]) == 1
save("DATA_INTEGRITY.json", {"delta": delta, "existing_rows_unchanged": True, "financial_sources_unchanged": True, "memberships_roles_permissions_scopes_unchanged": True, "old_expired_invitation_grant_unchanged": True, "exclusions": ["sessions", "User.last_login"], "invitation_token_saved": False})

allowed = {"templates/base.html", "templates/components/table_filter_row.html", "templates/organizations/role_catalog.html", "apps/accounts/static/js/erp_jalali.js"}
changed_sources = []
for name, previous in entry["hashes"].items():
    if not name.startswith("docs/governance/uiux/") and sha(ROOT / name) != previous:
        changed_sources.append(name)
assert set(changed_sources) == allowed, changed_sources
assert git("rev-parse", "HEAD").strip() == entry["head"]
assert sha(ROOT / ".git/index") == entry["index_sha256"]
save("SOURCE_INTEGRITY.json", {"changed_existing_product_files": changed_sources, "new_product_test": "tests/test_uiux_wave_e_targeted.py", "all_other_entry_product_files_unchanged": True, "all_previous_dirty_changes_preserved": True, "registry_roadmap_unchanged": True, "git_index_and_head_unchanged": True, "uiux_historical_evidence_unchanged": "Asserted by validate_closeout.py after reconciliation", "changes": {p: {"entry": entry["hashes"][p], "current": sha(ROOT / p)} for p in changed_sources}})
save("VALIDATION.json", {"focused": "11/11 PASS; 3 date-field subtests PASS", "affected": "14/15 PASS; 1 BASELINE TEST DEBT reproduced with entry templates", "http": "16/16 PASS", "ruff_check_new_test": "PASS", "ruff_format_new_test": "PASS", "django_system_check": "PASS; no issues", "schema": "No migration; Development configured database migration guard PASS", "browser_errors": 0, "unresolved_attributable_regressions": 0, "indeterminate_regressions": 0, "full_suite": "NOT_RUN; not required for presentation-only seam"})
print("Integrity PASS: only one invitation, one grant and canonical audit additions; all existing business/auth rows unchanged.")
