"""Append F-135/RV-025 dispositions; retain accepted evidence and debt."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from entry import ROOT, OUT, save, sha

BASE = OUT.parent
NOW = datetime.now(ZoneInfo("Asia/Tehran")).isoformat()
KEY = "f135_closure"
WAVE = "WAVE_E_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT"
FINAL = "TARGETED_RUNTIME_VALIDATION_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT"


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def append(name, data):
    p = BASE / name
    assert ("\n" + KEY + ":") not in p.read_text(encoding="utf-8")
    p.write_bytes(p.read_bytes().rstrip() + ("\n\n" + KEY + ":\n  " + json.dumps(data, ensure_ascii=False, indent=2).replace("\n", "\n  ") + "\n").encode("utf-8"))


entry = read("ENTRY.json")
assert read("VALIDATION.json")["browser_keyboard_tests"] == "22/22 PASS"
for name in ("UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "UIUX_FINDINGS_REGISTER.yaml", "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md", "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md"):
    assert sha(BASE / name) == entry["hashes"]["docs/governance/uiux/" + name]
    (OUT / ("entry_" + name)).write_bytes((BASE / name).read_bytes())

coverage = {"axes": "UI dimension x Persona x Module x State", "retained_authority": "../wave_e_targeted_closure/COVERAGE_RECONCILIATION.json", "accepted_wave_d": "UNCHANGED; not repeated", "accepted_wave_e": "UNCHANGED except the F-135 keyboard interaction delta; no responsive or portal journey replay", "delta_cells": [{"module": "Projects", "persona": "P-01 / uiux.persona.project-operations", "state": "Empty date desktop; populated from-bound mobile", "dimensions": ["Escape dismissal", "focus retention/return", "visible focus", "normal Tab continuation", "unchanged date/URL", "RTL/LTR"], "viewports": [[1440, 900], [390, 844]], "classification": "DIRECT_RUNTIME_EVIDENCE", "result": "PASS"}, {"module": "Quality", "persona": "P-25 reader / uiux.audit.project", "state": "Empty date desktop; populated from-bound mobile; next date boundary", "dimensions": ["Escape dismissal", "focus retention/return", "visible focus", "normal Tab continuation", "unchanged date/URL", "non-Escape key", "RTL/LTR"], "viewports": [[1440, 900], [390, 844]], "classification": "DIRECT_RUNTIME_EVIDENCE", "result": "PASS"}], "tablet": "RETAINED_ACCEPTED_LAYOUT; keyboard behavior is representative equivalence from identical shared handler; no CSS/breakpoint change", "other_representative_cells": "RETAINED_ACCEPTED; hashes preserved", "blocked_or_unrepresented_material_cell": None, "evidence": "KEYBOARD_TESTS.json + CAPTURES.json"}
save("COVERAGE_DELTA.json", coverage)
record = {"evidence_id": "RV-EV-065", "scenario_id": "RV-025", "finding_ids": ["UIUX-F-135"], "result": "PASS", "executed_at": NOW, "runtime": {"environment": "Development / Non-Production", "base_url": "http://127.0.0.1:8000", "branch": entry["branch"], "head": entry["head"], "dirty_source": "ENTRY.json + SOURCE_INTEGRITY.json", "browser": "BROWSER_METADATA.json", "viewports": [[1440, 900], [390, 844]]}, "personas": ["P-01 / uiux.persona.project-operations: existing member and scoped Projects", "P-25 reader / uiux.audit.project: existing project-scoped quality_issues.view authority"], "preconditions": ["F-135 is RV-025's sole remaining supported failure", "Previous F-110/F-134/positive external portal results accepted and retained", "Existing accounts/permissions/scopes; ordinary login using existing DPAPI secrets in memory", "Development migration guard PASS; no business fixture changes"], "steps": ["Focus date input with keyboard", "Press Escape from input, associated trigger, month and day controls", "Verify picker hidden and appropriate focus remains/returns without reopening", "Reopen using existing trigger Enter behavior", "Verify Escape outside the picker preserves focus and closed-picker Escape is a no-op", "Verify non-Escape caret key keeps picker open", "Tab to next date boundary and dismiss that picker", "Repeat affected desktop/mobile empty/populated states; compare date values and query URL before/after", "Inspect RTL page/LTR date fields, focus visibility, viewport bounds and runtime logs"], "expected": "Open picker dismisses on Escape; focus never remains in hidden picker; no value/date/query/authorization/business change", "actual": "22/22 keyboard assertions PASS; all Escape origins close picker; input/trigger focus retained, popup-button focus returned to its associated trigger; Tab reaches next date boundary; populated date values and URLs unchanged; Persian RTL/LTR intact; zero runtime errors", "screenshots": [r["name"] + ".jpg" for r in read("CAPTURES.json")], "keyboard_focus": "KEYBOARD_TESTS.json", "source_delta": "SOURCE_DELTA.diff", "tests": "18/18 PASS; 3 subtests PASS", "authorization_integrity": "DATA_INTEGRITY.json; no business/auth changes; previous server-isolation evidence retained", "limitations": ["F-135 revalidation only; not full WCAG/screen-reader certification or all calendar forms", "Tablet layout and other completed Wave E evidence retained without repetition", "Native JPEG bitmap sizes may differ from directly measured CSS viewport; unmodified provider captures retained", "Full browser build unavailable; same-provider metadata limitation retained"], "credentials_tokens_csrf_saved": False}
save("EVIDENCE_RECORDS.json", [record])
current = {"recorded_at": NOW, "current_authority": "Supersedes only F-135 and RV-025 failure pointers in wave_e_targeted_closure; historical evidence preserved", "F-135": {"status": "RESOLVED", "result": "PASS", "evidence_id": "RV-EV-065"}, "RV-025": {"result": "PASS", "basis": "Accepted cross-role/responsive/portal evidence plus RV-EV-065 closes sole remaining F-135 accessibility failure", "retained_evidence": ["RV-EV-060 accepted completed cells only", "RV-EV-061", "RV-EV-062", "RV-EV-063"], "superseded_failure": "RV-EV-064 remains historical; F-135 corrected and revalidated"}, "wave_d": "WAVE_D_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT", "wave_e": WAVE, "final_uiux_status": FINAL, "accepted_wave_d_e_repeated": False, "prior_closures": {"F-110": "PASS_RETAINED", "F-134": "PASS_RETAINED", "external_positive_portal": "PASS_RETAINED; no renewal/replay"}, "accepted_baseline_test_failures": 18, "separate_statutory_and_projects_assertion_debt": "RETAINED_UNCHANGED; not rerun/reclassified", "other_unrelated_findings": "RETAINED; no unrelated remediation", "unresolved_attributable_regressions": 0, "indeterminate_regressions": 0, "focused_affected_tests": "18/18 PASS + 3 subtests PASS", "browser_keyboard_tests": "22/22 PASS", "runtime_errors": 0, "UX_READY_FOR_UAT": "NOT_ISSUED", "new_product_decision_required": False, "full_wcag_or_uat_or_production_certification": "NOT_ISSUED", "evidence": "f135_closure/EVIDENCE_RECORDS.json", "coverage": "f135_closure/COVERAGE_DELTA.json", "report": "f135_closure/COMPLETION_REPORT.md", "regression": "f135_closure/REGRESSION_ATTRIBUTION.json", "schema_migration": "NONE", "business_workflows_authorization_date_semantics": "UNCHANGED", "production": "UNTOUCHED", "cep078079": "NOT_EXECUTED", "human_signoff": "NOT_EXECUTED", "git_writes": "NOT_EXECUTED", "next_action": "STOP after F-135 / RV-025 reconciliation"}
save("FINAL_RECONCILIATION.json", current)
append("UIUX_RUNTIME_VALIDATION_RESULTS.yaml", current)
p = BASE / "UIUX_RUNTIME_VALIDATION_RESULTS.yaml"
data = p.read_bytes().replace(b"current Wave E/final results are wave_e_targeted_closure;", b"current F-135/RV-025 and Wave E/final results are f135_closure;", 1)
p.write_bytes(data)
append("UIUX_FINDINGS_REGISTER.yaml", {"recorded_at": NOW, "historical_findings": "PRESERVED_UNCHANGED", "current_dispositions": {"UIUX-F-135": "RESOLVED; Escape dismisses open picker; focus retained/returned visibly; date/filter behavior preserved; RV-EV-065 PASS"}, "retained_closures": ["UIUX-F-110", "UIUX-F-134"], "new_findings": [], "current_max_finding_id": "UIUX-F-135", "report": current["report"], "evidence": current["evidence"]})
append("UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", {"recorded_at": NOW, "finding": "UIUX-F-135", "disposition": "RESOLVED_SHARED_PICKER_ESCAPE_INTERACTION", "root_pattern": "UNMAPPED retained; no new pattern mapping/static sweep", "source": "apps/accounts/static/js/erp_jalali.js", "cache_reference": "templates/base.html existing Jalali script query version only", "unchanged_patterns_and_history": True, "report": current["report"], "evidence": current["evidence"]})

report = f"""# F-135 / RV-025 closure — 2026-10-23

**F-135 PASS / RESOLVED. RV-025 PASS.**

**{WAVE}** and **{FINAL}** remain unchanged. **UX_READY_FOR_UAT = NOT_ISSUED**. This closes the sole remaining RV-025 interaction failure using a targeted delta; it is not full WCAG certification, Human Sign-off or Production authority.

## Minimum repair

One guarded `keydown` listener in the existing Jalali script handles Escape only while its active picker is open. It hides the picker; focus on the date input or trigger stays there. If focus is inside calendar content, it moves to that field's existing calendar trigger, so it cannot remain hidden or reopen the picker through input-focus behavior. Existing trigger Enter behavior still reopens normally. Focus outside the picker is preserved. Escape on a closed picker is a no-op and non-Escape keys retain existing behavior.

The existing script reference changes only its cache-version query so the browser loads this repair. No CSS, calendar redesign, date conversion, parsing, masking, filter, submit/change/input handler, workflow, authorization, service, model or schema change. [Exact session delta](SOURCE_DELTA.diff) and [source proof](SOURCE_INTEGRITY.json) demonstrate that all existing script content outside the new listener is identical to entry, including prior F-110 names.

## Validation

**18/18 focused/affected tests PASS, with 3 additional date-field subtests PASS**: seven Jalali form/format cases plus eleven existing date/filter/name/localization cases. [JUnit](focused_affected.xml), [test output](focused_affected.txt). JavaScript syntax check, Django system check and changed-file whitespace check PASS. No full-suite PASS is claimed.

**22/22 authenticated keyboard cases PASS**, Projects and Quality at **1440×900** and **390×844** CSS viewports. Empty desktop and populated mobile date fields are observed. Escape closes from the input, trigger, month navigation and day buttons. Focus stays visible, returns from hidden picker content to the correct trigger, and Tab continues to the next boundary. Escape outside the picker does not steal focus; repeated Escape on a closed picker does not alter state; non-Escape caret input keeps the picker open. Populated `1404/01/01` values and query URLs are identical before/after. Persian RTL, LTR dates and viewport containment remain intact. [Keyboard assertions](KEYBOARD_TESTS.json), [captures](CAPTURES.json), [RV-EV-065](EVIDENCE_RECORDS.json).

Browser/runtime errors: **0**. Development Tailwind warnings remain explicit in [logs](BROWSER_LOGS.json). The full browser build is unavailable; the prior same-provider metadata limitation remains. Native provider JPEG dimensions may differ from the directly measured CSS viewport; original native images are retained without resizing. Temporary viewport overrides were reset and the temporary tab closed. No dates were selected or saved and no business form was submitted.

## Accepted evidence and debt

Accepted Wave D and completed Wave E evidence is preserved without replay. F-110, F-134 and positive authenticated external portal coverage retain PASS. RV-025 combines those accepted records (RV-EV-060's completed cells and RV-EV-061/062/063) with current RV-EV-065. The former F-135 failure RV-EV-064 remains historical. Tablet layout evidence is retained; the new shared handler has no breakpoint/CSS branch, with desktop/mobile direct interaction evidence supplying representative equivalence. [Coverage delta](COVERAGE_DELTA.json).

The **18 accepted baseline failures** remain unchanged debt. The separately evidenced inherited statutory-copy and Projects navigation assertions also remain explicit, unrepaired and not rerun. Other unrelated open findings remain outside this bounded repair. **Zero unresolved attributable or indeterminate regressions.** [Attribution](REGRESSION_ATTRIBUTION.json). One draft browser assertion compared animation-progress shadow values; the stable focus identity, picker visibility, date values and URL were unchanged, and the corrected assertion verifies those behavior contracts. JUnit includes the three successful subtests in its total of 21; this is 18 parent cases plus 3 subtests, not additional failures.

## Integrity and stop

[Entry](ENTRY.json), [source integrity](SOURCE_INTEGRITY.json) and [data integrity](DATA_INTEGRITY.json) prove preservation of unrelated dirty changes, all business/financial/authorization records, prior fixtures and expiry. **No business rows added, changed or deleted**; only normal sessions/last-login bookkeeping is excluded. Existing accounts use normal login with existing DPAPI credentials held only in memory. No credential, permission, membership or scope changes.

HEAD, Git index, CEP Registry and Roadmap remain unchanged. CEP-078/079, Production actions/certification/cutover/migration, Human Sign-off and Git writes: **NOT EXECUTED**. No Product Decision was required or inferred. **STOP after this F-135 / RV-025 reconciliation.**
"""
(OUT / "COMPLETION_REPORT.md").write_text(report, encoding="utf-8")
(BASE / "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md").write_text(f"# Wave E current disposition — 2026-10-23\n\n**{WAVE}**. **RV-025 PASS**: the sole remaining inherited F-135 Escape-dismissal failure is repaired and revalidated. F-110, F-134 and positive external portal PASS evidence is retained without replay.\n\nFinal UIUX: **{FINAL}**. **UX_READY_FOR_UAT = NOT_ISSUED**. Original 18 baseline failures and the separately evidenced statutory/Projects assertion debt remain explicit; no attributable or indeterminate regressions.\n\nF-135 validation: 18 focused/affected tests PASS (+3 subtests), 22 authenticated desktop/mobile keyboard cases PASS, zero runtime errors. Business/authorization data and date/filter semantics unchanged.\n\n[Current report](f135_closure/COMPLETION_REPORT.md), [evidence](f135_closure/EVIDENCE_RECORDS.json), [coverage delta](f135_closure/COVERAGE_DELTA.json). Accepted Wave D/E history is preserved. No CEP-078/079, Production, Human Sign-off or Git writes. **STOP.**\n", encoding="utf-8")
p = BASE / "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md"
prefix = f"# Current F-135 / RV-025 reconciliation — 2026-10-23\n\n**F-135 PASS / RESOLVED. RV-025 PASS.**\n\n**{WAVE}** and **{FINAL}** remain unchanged. **UX_READY_FOR_UAT = NOT_ISSUED**. Accepted Wave D/E evidence, F-110/F-134/external portal PASS and existing baseline debt are retained.\n\n18 focused/affected tests PASS (+3 subtests); 22 authenticated desktop/mobile keyboard assertions PASS; zero runtime errors or attributable/indeterminate regressions. Existing business/authorization data and date/filter semantics unchanged.\n\n[Current report](f135_closure/COMPLETION_REPORT.md), [results](f135_closure/FINAL_RECONCILIATION.json), [evidence](f135_closure/EVIDENCE_RECORDS.json). Earlier sections below remain historical. No CEP-078/079, Production, Human Sign-off or Git writes. **STOP.**\n\n---\n\n"
p.write_bytes(prefix.encode("utf-8") + p.read_bytes())
print("F-135 RESOLVED; RV-025 PASS; Wave E/final complete-with-debt statuses retained. STOP after reconciliation.")
