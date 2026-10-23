"""Reconcile only current D/E audit authorities; preserve historical evidence."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
NOW = datetime.now(ZoneInfo("Asia/Tehran")).isoformat()

def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def append_mapping(filename, key, value):
    p = BASE / filename
    text = p.read_text(encoding="utf-8")
    assert f"\n{key}:" not in text, "Do not overwrite a prior closeout"
    p.write_text(text.rstrip() + "\n\n" + key + ":\n" + "\n".join("  " + line for line in json.dumps(value, ensure_ascii=False, indent=2).splitlines()) + "\n", encoding="utf-8")

# These two captures occurred after template hot reload, not before repair.
browser = read("BROWSER.json")
for row in browser:
    if row["name"].startswith("rv021_history_before_"):
        old = row["name"]
        new = old.replace("_before_", "_final_")
        for suffix in (".jpg", ".ax.txt"):
            (OUT / (old + suffix)).rename(OUT / (new + suffix))
        row.update(name=new, phase_note="Captured after repair; draft capture name corrected before closeout")
save("BROWSER.json", browser)

# Assertion HTML is irrelevant to the result and can contain synthetic CSRF
# values. Retain assertion/stack/counts, omit entire response dumps.
redactions = []
for p in OUT.glob("*.txt"):
    text = p.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    kept = ["[Synthetic response HTML omitted; assertion and stack retained.]" if "<!doctype html>" in line else line for line in lines]
    if kept != lines:
        p.write_text("\n".join(kept) + "\n", encoding="utf-8")
        redactions.append(p.name)
for p in OUT.glob("*.xml"):
    tree = ET.parse(p)
    changed = False
    for failure in tree.findall(".//failure") + tree.findall(".//error"):
        message = failure.attrib.get("message", "")
        if "<!doctype html>" in message:
            failure.set("message", message.splitlines()[0])
            changed = True
        lines = (failure.text or "").splitlines()
        cleaned = ["[Synthetic response HTML omitted; assertion and stack retained.]" if "<!doctype html>" in line else line for line in lines]
        if cleaned != lines:
            failure.text = "\n".join(cleaned)
            changed = True
    if changed:
        tree.write(p, encoding="utf-8", xml_declaration=True)
        redactions.append(p.name)
save("EVIDENCE_REDACTION.json", {"artifacts":redactions, "reason":"Remove synthetic test-response HTML/CSRF payloads; result counts, assertion messages and stacks retained", "test_outcomes_changed":False, "live_credentials_persisted":False})

gate = read("WAVE_D_GATE.json")
assert gate["wave_e_entry"] == "PASS"
regression = read("REGRESSION_ATTRIBUTION.json")
assert regression["unresolved_attributable_regressions"] == 0 and regression["indeterminate"] == 0
e = read("WAVE_E_BROWSER.json")
assert len(e) == 54 and len({r["label"] for r in e}) == 18
positive = [r for r in e if r["label"] not in {"external_portal", "manager_equipment"}]
assert len(positive) == 48
assert all(r["metrics"]["doc"] <= r["metrics"]["w"] and r["metrics"]["main"]["scroll"] <= r["metrics"]["main"]["client"] for r in positive)
assert all(not r["metrics"]["duplicateIds"] for r in positive)
assert not [t for r in positive for t in r["metrics"]["tables"] if t["width"] > t["ancestors"][0]["client"] + 2 and not any(p["overflow"] in {"auto", "scroll"} for p in t["ancestors"])]
logs = read("BROWSER_RUNTIME_LOGS_FINAL.json")
errors = [r for r in logs if r["level"] == "error"]
assert not errors

personas = {
    "ordinary_home":("P-01","ordinary operational / Home"),
    "ordinary_projects":("P-01","ordinary operational / Projects"),
    "ordinary_ess":("P-09","explicit own ESS"),
    "manager_home":("P-17","Project Manager"),
    "owner_equipment":("P-15","Owner / authorized Equipment workbench"),
    "owner_statements":("P-15","Owner / authorized Accounting statements"),
    "tenant_admin":("P-16","Tenant Admin"),
    "platform_admin":("P-18","separate Platform Admin"),
    "document_control":("P-19","Document Control specialist"),
    "payroll":("P-20","Payroll specialist"),
    "inventory":("P-22","Inventory read perspective only; existing viewer, no storekeeper write claim"),
    "commercial":("P-23","Contract/Commercial specialist"),
    "commercial_form":("P-23","Contract/Commercial create form; not submitted"),
    "project_controls":("P-24","Project Controls specialist"),
    "quality_reader":("P-25","Quality read perspective only; no specialist write claim or RV-020 repeat"),
    "buyer":("P-03","Buyer specialist"),
    "external_portal":("P-26","external supplier with no tenant membership"),
    "manager_equipment":("P-17","negative scope boundary only"),
}
coverage = []
for label, (persona, perspective) in personas.items():
    rows = [r for r in e if r["label"] == label]
    dims = {dimension:"DIRECT_RUNTIME_EVIDENCE" for dimension in ("navigation","viewport_layout","rtl_ltr","primary_actions","tables_overflow","role_conditioned_ui")}
    if label == "external_portal":
        dims = {k:"BLOCKED" for k in dims}
    if label == "manager_equipment":
        dims = {k:"NOT_APPLICABLE" for k in dims}
        dims["role_conditioned_ui"] = "DIRECT_RUNTIME_EVIDENCE"
    coverage.append({"surface":label,"persona":persona,"perspective":perspective,"actor":rows[0]["actor"],"path":rows[0]["metrics"]["url"],"viewports":[[r["metrics"]["w"],r["metrics"]["h"]] for r in rows],"dimension_cells":dims,"confidentiality":"DIRECT_RUNTIME_EVIDENCE: E_HTTP.json + live effective authority; representative backend boundary, not security certification", "forms":"DIRECT_RUNTIME_EVIDENCE" if label in {"commercial_form","owner_statements","ordinary_projects","quality_reader"} else "REPRESENTATIVE_EQUIVALENCE: shared field/shell behavior; no distinct mutation tested", "runtime_errors":"DIRECT_RUNTIME_EVIDENCE: no unexpected browser errors; expected expired-context 404 separated", "screenshots":[r["name"]+'.jpg' for r in rows],"limitations":("Positive portal is BLOCKED_TEST_DATA: expired invitation, unchanged" if label == "external_portal" else "Existing F-110 accessible date-boundary names fail" if label in {"ordinary_projects","quality_reader"} else "F-134 static English Tenant label; system role names also observed English" if label == "platform_admin" else "Representative state only; not every lifecycle or route")})
save("COVERAGE_RECONCILIATION.json", {"axes":"UI dimension x Persona x Module x State", "cells":coverage,"state_limit":"Current populated/list/empty/read/form/drawer states only. Prior Wave C lifecycle and confidentiality evidence retained, not rerun. No claim for all 26 personas on all pages.", "supplemental_evidence":"WAVE_E_INTERACTIONS.json", "unrepresented_material_cell":"P-26 positive portal; BLOCKED, no silent omission"})

common = {"executed_at":NOW,"runtime":{"environment":"Development / Non-Production","base_url":"http://127.0.0.1:8000","sha":"43ac319c6e73e48ca9626461b73987922c498ec3","dirty_source":"ENTRY.json + SOURCE_INTEGRITY.json","browser":"ChatGPT in-app Browser id 2","version":"Full build not exposed; prior same-provider reduced Chromium 155.0.0.0 metadata retained, no fresh version claim","viewports":[[1440,900],[1024,768],[390,844]]},"authority":"Direct Human D fixtures / gated E / reconciliation request","authorization":"READINESS.json + HTTP.json + E_HTTP.json; actual authorities retained","credentials_in_evidence":False,"schema_migration":"NONE","production":"UNTOUCHED"}
records = [
    dict(common,evidence_id="RV-EV-058",scenario_id="RV-016",result="PASS",persona="P-09 functional own-data shape: uiux.persona.project-operations, existing member role + A/B project scopes",preconditions=["Explicit synthetic Person.user and current WorkRelationship through canonical services","Existing payroll_ess.view_own permission; no grant or default-role change"],steps=["Normal sign-in","Open own ESS/profile and Payroll history","Inspect desktop/mobile role-conditioned four-link navigation, empty/unavailable states and RTL identifier isolation","Deny other worker, foreign tenant, another finalized payslip, linked account without Payroll permission and account without subject"],expected="Only explicitly linked own data; clear empty history and readable mobile UI",actual="Own dashboard and Payroll ESS 200, truthful empty Payroll state, no page overflow, restricted reads fail closed; source codes remain in read model but no longer primary employee copy",screenshots=[p.name for p in OUT.glob('rv016*final*.jpg')],limitations=["No new finalized payroll source or inquiry/category was manufactured; populated finalized-source isolation/export/lineage tested by existing ESSPayrollTests","Broad F-022 navigation regrouping remains open outside the four-link fixture","Natural populated ready-state projection proven by affected ESS dashboard tests, not a live new request"],finding_ids=["UIUX-F-021","UIUX-F-022"],fixture="RV016_FIXTURE.json"),
    dict(common,evidence_id="RV-EV-059",scenario_id="RV-021",result="PASS",persona="P-12 curator functional perspective: existing Tenant Owner; independent Tenant Admin author; P-18 existing admin duty without active tenant context",preconditions=["Canonical accepted synthetic FieldObservation, independent source review and complete Knowledge publication lifecycle","Sanitized requested promotion; separately assigned current Platform Admin verified credential, no reset"],steps=["View prepared publication/history on desktop/mobile/narrow","Open correction/promotion and source-ID disclosures using keyboard; retain technical hash behind disclosure","Inspect canonical form labels, unique IDs and focus","Normal Platform Admin sign-in; inspect sanitized requested queue","Verify project-only reader/history/platform/implicit-tenant denials through actual server"],expected="Article and human labels primary; traceability explicit and protected; sanitized platform queue only",actual="Published article/history and requested platform queue work; unique form IDs, shared form components, Persian labels and keyboard disclosures; no unexpected browser errors or overflow",screenshots=[p.name for p in OUT.glob('rv021*final*.jpg')]+["rv021_promotion_form_mobile.jpg","rv021_correction_form_mobile.jpg","rv021_history_disclosure_mobile.jpg","rv021_platform_form_mobile.jpg"],limitations=["No platform review/approve/publish business command sent from browser","Requested queue state directly observed; other platform lifecycle states remain represented by existing tests","F-103 human-readable source reference enrichment beyond localized producer type/status remains open"],finding_ids=["UIUX-F-099","UIUX-F-100","UIUX-F-103"],fixture="RV021_FIXTURE.json"),
    dict(common,evidence_id="RV-EV-060",scenario_id="RV-025",result="FAIL_ACCESSIBILITY",coverage_status="PARTIAL_BLOCKED_TEST_DATA",preconditions=["WAVE_D_GATE.json PASS with explicit baseline debt","Existing identities/roles/permissions/scopes and retained business sources only"],steps=["Sweep matrix Home/Projects/Buyer/ESS/Statements/Equipment plus required role representatives at all three canonical sizes","Open mobile drawer and close with Escape","Scroll wide Projects table in RTL","Reach Commercial form primary action with keyboard without submission","Inspect role-conditioned UI, labels, LTR identifiers, overflow, confidentiality and console/server controls"],expected="Reachable responsive surfaces, reachable actions, named controls and positive external representative",actual="48 positive viewport captures across 16 surfaces, three negative manager-scope captures, three expired external-context captures; contained wide tables, RTL scroll and primary-action reachability pass. Existing F-110 date-field naming failure confirmed on Projects/Quality; new F-134 localization issue confirmed. Positive external portal is BLOCKED_TEST_DATA.",screenshots=[r["name"]+'.jpg' for r in e],findings=["UIUX-F-016","UIUX-F-017","UIUX-F-110","UIUX-F-134"],coverage="COVERAGE_RECONCILIATION.json",portal="E_PORTAL_BLOCKER.json",limitations=["No responsive PASS for expired portal denial page; its debug 404 is not the positive portal UI","Inventory and Quality reader perspectives do not certify specialist mutation authority","Not exhaustive WCAG/screen reader/touch-device certification or all 33 scenarios reexecution"])
]
save("EVIDENCE_RECORDS.json", records)

finding = {"finding_id":"UIUX-F-134","module":"Organizations / Platform administration","surface_id":"SURF-016","route":"/organizations/platform/roles/","page_title":"مدیریت نقش‌ها","category":"LOCALIZATION","severity":"LOW","status":"RUNTIME_CONFIRMED","runtime_classification":"FAIL_UIUX","problem":"The Persian-first Platform role catalogue uses a hardcoded English Tenant label for the organization filter. Several existing system display names are also English; stable role codes remain intentionally unchanged.","evidence":{"evidence_ids":["RV-EV-060"],"source_paths":["templates/organizations/role_catalog.html"],"screenshots":["wave_de_fixture_closure/e_platform_admin_1440.jpg","wave_de_fixture_closure/e_platform_admin_390.jpg"],"observed_literals":["Tenant","Accountant","Company Owner"]},"recommendation":"Localize the static organization-filter label through the existing Persian UI vocabulary; assess existing governed system display labels separately, preserving all stable codes, grants and user-authored names.","business_logic_impact":"NONE_EXPECTED","needs_domain_review":False,"remediation_performed":False,"root_pattern_candidate":["RP-C01-TECHNICAL-LANGUAGE-LEAK"]}
dispositions = {"UIUX-F-021":"BOUNDED_PRESENTATION_REMEDIATION_VERIFIED: employee copy/status labels/deep links and truthful empty state; source status data and isolation retained", "UIUX-F-022":"OPEN: four-link prepared own-data shape usable at mobile; broad grouping/priority redesign not performed or globally closed", "UIUX-F-048":"RESOLVED_RETAINED; RV-022 not repeated", "UIUX-F-099":"RUNTIME_VERIFIED_MATRIX_ARTICLE_REMEDIATION: canonical authority label, technical hash disclosure, shared form fields and unique IDs", "UIUX-F-100":"BOUNDED_REMEDIATION_VERIFIED: requested sanitized queue content/action primary, technical hash disclosed and required reason labelled; other queue states not freshly observed", "UIUX-F-103":"PARTIALLY_REMEDIATED: producer-derived type/status and review labels, technical identifiers disclosed; richer source-business references not inferred", "UIUX-F-110":"RUNTIME_CONFIRMED_ON_PROJECTS_AND_QUALITY: repeated unnamed date-boundary inputs; unchanged shared pattern, no unrelated remediation", "UIUX-F-134":"NEW_RUNTIME_CONFIRMED_LOCALIZATION; no remediation"}
current = {"recorded_at":NOW,"current_authority":"This section supersedes prior current D/E blocker pointers only; all prior results/evidence remain historical", "wave_c":"COMPLETE_WITH_EXPLICIT_BASELINE_DEBT_RETAINED", "wave_d":"WAVE_D_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT", "wave_d_scenarios":{"RV-016":"PASS","RV-020":"PASS_RETAINED_NOT_REPEATED","RV-021":"PASS","RV-022":"PASS_RETAINED_NOT_REPEATED"},"wave_d_counts":{"PASS":4,"BLOCKED":0},"wave_e_entry":"PASS","wave_e":"WAVE_E_PARTIAL_WITH_EXPLICIT_FINDINGS_AND_BASELINE_DEBT","RV-025":{"result":"FAIL_ACCESSIBILITY","coverage":"PARTIAL_BLOCKED_TEST_DATA","known_failure":"UIUX-F-110","new_finding":"UIUX-F-134","blocked_subtarget":"P-26 positive portal: expired accepted invitation; no validity/grant mutation"},"wave_e_counts":{"scenario_count":1,"executed_partially":1,"PASS":0,"FAIL_ACCESSIBILITY":1,"positive_surface_viewport_captures":48,"negative_scope_captures":3,"blocked_external_captures":3},"final_uiux_status":"TARGETED_RUNTIME_VALIDATION_PARTIAL","UX_READY_FOR_UAT":"NOT_ISSUED","test_validation":"49 tests: 48 PASS, 1 pre-entry inherited statutory-copy assertion retained; original 18 baseline failures remain explicit and unchanged","additional_preentry_assertion_debt":1,"original_baseline_failures":18,"baseline_debt_reclassified":False,"unresolved_attributable_regressions":0,"indeterminate_regressions":0,"new_product_decision_required":False,"findings":dispositions,"new_findings":["UIUX-F-134"],"http_controls":{"D":"15/15 PASS","E":"18/18 PASS","business_posts":0},"runtime_errors":{"unexpected_browser_errors":0,"development_tailwind_warnings":len(logs),"expected_portal_404":"Fixture blocker, not positive UI evidence"},"evidence":"wave_de_fixture_closure/EVIDENCE_RECORDS.json","coverage":"wave_de_fixture_closure/COVERAGE_RECONCILIATION.json","report":"wave_de_fixture_closure/COMPLETION_REPORT.md","regression":"wave_de_fixture_closure/REGRESSION_ATTRIBUTION.json","authorization_model_default_roles_scopes":"UNCHANGED","schema_migration":"NONE","production":"UNTOUCHED","cep078079":"NOT_EXECUTED","human_signoff":"NOT_EXECUTED","cep_registry_roadmap":"UNCHANGED","git_write":"NOT_EXECUTED","next_action":"STOP after D/E reconciliation; no automatic continuation"}
save("FINAL_RECONCILIATION.json", current)
append_mapping("UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "wave_de_fixture_closure", current)
p = BASE / "UIUX_RUNTIME_VALIDATION_RESULTS.yaml"
text = p.read_text(encoding="utf-8")
text = text.replace("Current RV-022 and Wave D/E counts are rv022_business_label_revalidation; earlier sections remain historical.", "Current D/E results are wave_de_fixture_closure; RV-020/RV-022 remain retained PASS and earlier sections are historical.")
p.write_text(text, encoding="utf-8")
append_mapping("UIUX_FINDINGS_REGISTER.yaml", "wave_de_fixture_closure", {"recorded_at":NOW,"historical_findings":"PRESERVED_UNCHANGED","current_dispositions":dispositions,"new_findings":[finding],"current_max_finding_id":"UIUX-F-134","report":current["report"],"evidence":current["evidence"]})
append_mapping("UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "wave_de_fixture_closure", {"recorded_at":NOW,"report":current["report"],"presentation_patterns":["RP-C01-TECHNICAL-LANGUAGE-LEAK","RP-C02-MODEL-REPRESENTATION-EXPOSED","RP-C13-OPERATIONAL-AUDIT-CONFLATION","RP-C15-SHARED-FORM-PATTERN-BYPASS"],"bounded_findings":["UIUX-F-021","UIUX-F-099","UIUX-F-100","UIUX-F-103"],"new_finding":{"finding":"UIUX-F-134","pattern":"RP-C01-TECHNICAL-LANGUAGE-LEAK"},"F110":"Existing unmapped accessible-name issue extended to Projects/Quality; no invented root pattern or static sweep", "F048":"RESOLVED retained, no RV-022 rerun", "coverage":current["coverage"]})
fixture_path = BASE / "UIUX_RUNTIME_FIXTURE_REGISTRY.yaml"
fixture = json.loads(fixture_path.read_text(encoding="utf-8-sig"))
fixture["wave_de_fixture_closure"] = {"recorded_at":NOW,"RV-016":read("RV016_FIXTURE.json"),"RV-021":read("RV021_FIXTURE.json"),"platform_session":read("PLATFORM_CREDENTIAL_READINESS.json"),"Wave_E_external_blocker":read("E_PORTAL_BLOCKER.json"),"roles_permissions_scopes_unchanged":True,"reference_accounts":"RETAINED; no deletion/deactivation/reset"}
fixture_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")

(BASE / "UIUX_RUNTIME_VALIDATION_WAVE_D_REPORT.md").write_text("# Wave D current disposition — 2026-10-23\n\n**WAVE_D_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT** — **4 PASS, 0 BLOCKED**.\n\nRV-016 and RV-021 now PASS after canonical Development fixture preparation and bounded presentation repair. RV-020 and RV-022 remain accepted PASS and were not repeated. F-048 remains resolved. No new Product Decision is required.\n\nValidation: 48 PASS / 1 unchanged inherited statutory-copy assertion retained; the original 18 baseline failures remain explicit. Zero unresolved attributable or indeterminate regressions. Wave E entry PASS and RV-025 executed immediately afterward.\n\n[Current report](wave_de_fixture_closure/COMPLETION_REPORT.md), [gate](wave_de_fixture_closure/WAVE_D_GATE.json), [evidence](wave_de_fixture_closure/EVIDENCE_RECORDS.json). No Production, CEP, Human Sign-off or Git write authority is issued.\n",encoding="utf-8")
(BASE / "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md").write_text("# Wave E current disposition — 2026-10-23\n\n**WAVE_E_PARTIAL_WITH_EXPLICIT_FINDINGS_AND_BASELINE_DEBT**. RV-025: **FAIL_ACCESSIBILITY**, coverage **PARTIAL_BLOCKED_TEST_DATA**.\n\nThe Wave D gate passed. The sweep captured 48 positive views across 16 representative surfaces at 1440×900, 1024×768 and 390×844, plus three scope-denial and three expired-portal views. Reachable layout/RTL/table scrolling/action checks pass. Existing F-110 unnamed date filters fail on Projects/Quality. New F-134 records the English Tenant filter label in the Platform role catalogue.\n\nP-26 positive portal remains BLOCKED_TEST_DATA: its accepted invitation expired at 2026-10-23 03:28:23 Asia/Tehran. The RFQ remains issued; expiry and grant were not changed. The 404 is negative evidence only, not a positive responsive PASS. Inventory and Quality are reader perspectives, not specialist write certifications.\n\n**Final UIUX status: TARGETED_RUNTIME_VALIDATION_PARTIAL. UX_READY_FOR_UAT: NOT_ISSUED.** Original 18 baseline failures and one newly exposed pre-entry statutory-copy assertion remain explicit debt.\n\n[Current report](wave_de_fixture_closure/COMPLETION_REPORT.md), [coverage](wave_de_fixture_closure/COVERAGE_RECONCILIATION.json), [portal blocker](wave_de_fixture_closure/E_PORTAL_BLOCKER.json). CEP-078/079, Production actions and Human Sign-off were not executed. **STOP after reconciliation.**\n",encoding="utf-8")
completion = BASE / "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md"
historical = completion.read_text(encoding="utf-8")
completion.write_text("# Current D/E reconciliation — 2026-10-23\n\n**Wave D: WAVE_D_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT.** RV-016/RV-021 PASS; RV-020/RV-022 retained PASS without repetition.\n\n**Wave E: WAVE_E_PARTIAL_WITH_EXPLICIT_FINDINGS_AND_BASELINE_DEBT.** RV-025 FAIL_ACCESSIBILITY; positive external portal coverage remains BLOCKED_TEST_DATA due expired invitation. Final UIUX status: **TARGETED_RUNTIME_VALIDATION_PARTIAL**; **UX_READY_FOR_UAT = NOT_ISSUED**.\n\n[Current completion report](wave_de_fixture_closure/COMPLETION_REPORT.md) and [dimension/persona/module/state reconciliation](wave_de_fixture_closure/COVERAGE_RECONCILIATION.json) govern this delta. Earlier content below remains historical. Original 18 baseline failures remain explicit; one additional inherited pre-entry statutory-copy assertion is separately evidenced. No CEP, Production, Human Sign-off or Git writes. **STOP.**\n\n---\n\n"+historical,encoding="utf-8")

report = f"""# Development UIUX Wave D/E fixture closure — 2026-10-23

**Wave D: WAVE_D_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT.** RV-016/RV-021 PASS; RV-020/RV-022 retained PASS and not repeated. F-048 remains resolved.

**Wave E: WAVE_E_PARTIAL_WITH_EXPLICIT_FINDINGS_AND_BASELINE_DEBT.** RV-025 **FAIL_ACCESSIBILITY**, coverage **PARTIAL_BLOCKED_TEST_DATA**. Final UIUX status **TARGETED_RUNTIME_VALIDATION_PARTIAL**; **UX_READY_FOR_UAT = NOT_ISSUED**.

The two D fixture blockers are resolved. E was executed immediately after the objective D gate passed. Reachable responsive checks pass; shared date-boundary naming fails and the positive external portal is unavailable because its existing invitation expired. No pass is inferred from its denial page.

| Scenario | Supported result | Evidence |
|---|---|---|
| RV-016 | PASS in prepared own-data/empty-history shape | RV-EV-058; explicit subject, unchanged member permission; desktop/mobile, server privacy and affected populated-source tests |
| RV-020 | PASS retained | Prior accepted authority; not repeated |
| RV-021 | PASS within matrix publication/history/requested-queue targets | RV-EV-059; independent canonical fixture, separate Platform Admin normal login, no platform lifecycle mutation |
| RV-022 | PASS retained; F-048 resolved | Prior accepted authority; not repeated |
| RV-025 | FAIL_ACCESSIBILITY; partial positive coverage | RV-EV-060; 48 positive captures, 3 manager scope denials, 3 expired portal views; F-110 and F-134 explicit |

## Fixture resolution and bounded changes

RV-016 uses retained `uiux.persona.project-operations` with its existing `member` role and project A/B scope. `create_person(user=explicit account)` and `create_work_relationship` supply a labelled synthetic own identity. No email/name inference, role addition, scope change, Employee relink or financial source was used. Payroll history is legitimately empty; another employee's finalized payslip and same/foreign-worker URLs are denied. Existing tests cover populated finalized-source privacy/export/replacement lineage. The actual role exposes four navigation links; F-022's broader regrouping remains open.

RV-021 uses the existing Tenant Admin as author and separate Tenant Owner as reviewer/approver/publisher. A synthetic FieldObservation follows capture → submit → independent review → acceptance; Knowledge then follows create → submit → independent recommendation → approval → publication → sanitized promotion request. Only canonical services create state. No eligible source existed initially. No source or publication status was forced. The Platform Admin is the separately assigned retained `admin` duty, logged in normally without an active tenant context. Its exact existing seed credential was verified and placed only in the established current-user DPAPI store; no credential reset or new platform duty occurred.

Presentation changes are limited to established Persian/RTL UI contracts: employee copy/localized status without changing read-model status or source links; Knowledge authority/review/producer status labels; technical identifiers in explicit disclosures; shared form components and unique form IDs; labelled platform review reason. No business rule, permission check, workflow or financial logic changed. Knowledge tests receive only explicit intended fixture scope, including the negative source-permission actor so it reaches the intended denial. Two affected copy assertions now match the approved display text. Existing unrelated dirty changes were preserved.

## Validation and attribution

Final affected selection: **49 tests — 48 PASS, 1 pre-entry assertion FAIL**, in 40.54 seconds. [JUnit](verified_focused_affected.xml), [output](verified_focused_affected.txt), [attribution](REGRESSION_ATTRIBUTION.json). The retained failure is the inherited statutory UI test asserting the obsolete heading `کارگاه مقرراتی مالیات و بیمه کارکنان` and provider wording. Its test, statutory template, Payroll view and authorization sources exactly match session-entry hashes; it is outside the changed ESS/Knowledge seam. It was not fixed or hidden. The prior **18 baseline failures remain unchanged** at their accepted authority; this additional pre-entry assertion is separately recorded, not silently folded into or subtracted from those 18.

Initial results were 34 PASS / 15 FAIL: 13 legacy Knowledge fixture scope barriers repaired, one attributable copy assertion updated, one unrelated pre-entry assertion retained. A follow-up exposed the same missing scope on the intended negative-source actor, repaired in the fixture only. **Zero unresolved attributable or indeterminate regressions.** No full repository-suite PASS is claimed. The first run was stopped during test-database migration startup to preserve migration work and rerun final imports with `--reuse-db`; it supplies no result claim. Fixture-preparation exceptions (no eligible existing source, invalid draft harness enum, incorrect draft status literal) rolled back the entire Knowledge transaction; final preparation uses canonical enums/lifecycle. One HTTP expectation initially assumed a project-only reader could access an organization-scoped workbench; the actual 403 was correct and the evidence expectation was corrected without product authorization changes.

Authenticated HTTP: **D 15/15 PASS; E 18/18 PASS**, ordinary login/cookie/CSRF paths, no successful business POSTs from these controls. E checks include tenant/platform separation, foreign project/RFQ denial, actual specialist lists/workbench and external non-membership/internal-workspace denial. [D controls](HTTP.json), [E controls](E_HTTP.json). Django check: zero issues. Scoped Ruff and whitespace checks recorded in VALIDATION.json. Model/schema migration impact NONE; configured Development migration plan is empty.

## Wave E coverage and limitations

[Coverage reconciliation](COVERAGE_RECONCILIATION.json) covers UI dimension × persona × module × state. The six canonical representative targets (Home, Projects, Buyer, own ESS, Accounting statements, Equipment operations) and managerial, Owner, Tenant Admin, Platform Admin, Document Control, Payroll, Inventory, Contract/Commercial, Project Controls, Quality and external perspectives were evaluated at **1440×900**, **1024×768**, **390×844**.

There are **48 positive viewport captures across 16 surfaces**, plus three project-manager Equipment scope denials and three expired external-context captures. All positive pages fit the viewport/main container; wide tables have a horizontal scroller. The Projects RTL scroller moved from 0 to approximately −921px. Mobile drawer opening/Escape closure, Buyer action disclosure and Commercial form primary action keyboard reachability are directly proved. Commercial submit remained unsubmitted and visible with focus at y≈763–803 in the 844px viewport. Identifiers/numeric controls use existing LTR isolation inside RTL pages. No duplicate IDs on the positive sweep. No unexpected browser console errors; {len(logs)} Development Tailwind warnings remain non-production evidence. No separate true-touch-device, exhaustive WCAG/screen-reader or all-lifecycle certification is claimed.

The existing **F-110** ambiguous date-boundary accessible names recur on Projects and Quality, independent of viewport size. New **F-134** records the static English `Tenant` label in the Persian Platform role catalogue; existing English system display names are observed without changing codes or names. Existing disabled-navigation findings F-016/F-017 remain open. These were recorded without unrelated remediation. F-021/F-099/F-100/F-103 receive bounded repair dispositions, not blanket closure of all unobserved states; richer source references and broad ESS regrouping remain explicit.

The P-26 external account still has **zero tenant memberships**. Its accepted portal invitation expired **2026-10-23 03:28:23 Asia/Tehran**, while its RFQ remains issued. Browser context returns the configured Development 404 and the canonical service rejects the expired grant. Its positive layout, form and action cells remain **BLOCKED_TEST_DATA**. The debug denial page is not a positive portal UI or responsive pass; its debug-page overflow is not promoted into a defect in the unavailable portal content. No expiry rewrite, replacement grant or tenant membership was created because fixture repair authority in this request is bounded to D. No new Product Decision is required; existing expiry/isolation semantics are clear.

Inventory and Quality evidence uses actual reader permissions and does not certify specialist write authority. Managerial project scope did not permit the organization Equipment workbench; positive Equipment coverage uses the existing authorized Owner, and the denial is retained separately. Prior Wave C lifecycle/security evidence remains accepted rather than replayed.

## Integrity, authority and stop

Branch `main`, HEAD/origin/main **43ac319c6e73e48ca9626461b73987922c498ec3**, divergence 0/0. [ENTRY.json](ENTRY.json) and [SOURCE_INTEGRITY.json](SOURCE_INTEGRITY.json) prove starting dirty state and preservation. Runtime uses only `config.settings.development`, DEBUG true, loopback PostgreSQL `construction_erp`; no Production connection was opened. [DATA_INTEGRITY.json](DATA_INTEGRITY.json) proves existing business rows, all authorization models and financial sources unchanged; additions are only declared synthetic fixture/history/audit rows. Normal session and last-login bookkeeping is excluded explicitly. No user was reset, deleted or deactivated. No existing approved/posted/paid record was edited.

The browser is this task's in-app Browser id 2; full engine-build metadata is not exposed. Prior same-provider reduced Chromium 155.0.0.0 metadata is retained with that limitation, not presented as a fresh exact build. Temporary viewports were reset and the created tab closed. Automation-only parser/locator/navigation transients were recovered through fresh observations. Misnamed draft history captures were corrected before closeout because they were captured after template hot reload. Test assertion HTML was removed to avoid preserving synthetic CSRF values; assertion stacks and outcome counts remain, with explicit redaction evidence.

CEP-078, CEP-079, Production deployment/migration/certification/cutover, Human Sign-off: **NOT EXECUTED**. CEP Registry/Roadmap unchanged. No Git add/commit/push/merge/reset/clean/stash, branch or worktree operation. All changes remain uncommitted. **STOP after Wave D/E reconciliation.**
"""
(OUT / "COMPLETION_REPORT.md").write_text(report, encoding="utf-8")
print("D/E current authorities reconciled; E failures and blocked coverage remain explicit.")
