"""Reconcile this bounded delta, preserving accepted D/E and historical evidence."""
import copy
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from entry import OUT, ROOT, save, sha

BASE = OUT.parent
NOW = datetime.now(ZoneInfo("Asia/Tehran")).isoformat()
KEY = "wave_e_targeted_closure"
FINAL = "TARGETED_RUNTIME_VALIDATION_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT"
WAVE = "WAVE_E_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT"


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def append_mapping(name, data):
    p = BASE / name
    assert ("\n" + KEY + ":") not in p.read_text(encoding="utf-8")
    p.write_bytes(p.read_bytes().rstrip() + ("\n\n" + KEY + ":\n  " + json.dumps(data, ensure_ascii=False, indent=2).replace("\n", "\n  ") + "\n").encode("utf-8"))


entry = read("ENTRY.json")
targets = ("UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "UIUX_FINDINGS_REGISTER.yaml", "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "UIUX_RUNTIME_FIXTURE_REGISTRY.yaml", "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md", "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md")
for name in targets:
    assert sha(BASE / name) == entry["hashes"]["docs/governance/uiux/" + name]
    (OUT / ("entry_" + name)).write_bytes((BASE / name).read_bytes())

fixture = read("PORTAL_FIXTURE.json")
captures = read("BROWSER_CAPTURES.json")
prior = json.loads((BASE / "wave_de_fixture_closure/COVERAGE_RECONCILIATION.json").read_text(encoding="utf-8"))
coverage = copy.deepcopy(prior)
for cell in coverage["cells"]:
    cell["screenshots"] = ["../wave_de_fixture_closure/" + p for p in cell["screenshots"]]
    cell["evidence_basis"] = "RETAINED_ACCEPTED; not repeated; prior evidence and integrity hashes remain valid"
    if cell["surface"] in {"ordinary_projects", "quality_reader", "platform_admin", "external_portal"}:
        stem = {"ordinary_projects": "projects_layout", "quality_reader": "quality", "platform_admin": "platform", "external_portal": "portal"}[cell["surface"]]
        cell["screenshots"] = [f"{stem}_{w}.jpg" for w in (1440, 1024, 390)]
        cell["evidence_basis"] = "DIRECT_RUNTIME_EVIDENCE; bounded target delta at all three canonical viewports"
        cell["confidentiality"] = "DIRECT_RUNTIME_EVIDENCE: HTTP_CONTROLS.json + unchanged effective membership/role/scope snapshot"
        cell["runtime_errors"] = "DIRECT_RUNTIME_EVIDENCE: BROWSER_LOGS.json; zero errors; Development Tailwind warnings retained"
        cell["limitations"] = "Representative populated/list state; other completed evidence retained; no certification of specialist mutation or all lifecycles"
        if stem in {"projects_layout", "quality"}:
            cell["accessible_names"] = "DIRECT_RUNTIME_EVIDENCE: distinct associated Persian boundaries and corresponding named calendar actions; F-110 PASS"
            cell["keyboard_residual"] = "UIUX-F-135: inherited calendar popover does not dismiss with Escape; names repair does not change that behavior"
        if stem == "platform":
            cell["localization"] = "DIRECT_RUNTIME_EVIDENCE: static organization-filter label شرکت; stored role names/codes unchanged; F-134 requested label PASS"
        if stem == "portal":
            cell["path"] = fixture["path"]
            cell["dimension_cells"] = {k: "DIRECT_RUNTIME_EVIDENCE" for k in cell["dimension_cells"]}
            cell["forms"] = "DIRECT_RUNTIME_EVIDENCE: labelled required file/reference fields and keyboard-reachable submit action; no business submission"
            cell["limitations"] = "Fresh exact invitation context only; all positive cells observed while valid; no quotation posted; old expired denial remains negative evidence"
coverage["unrepresented_material_cell"] = None
coverage["supplemental_evidence"] = ["INTERACTIONS.json", "HTTP_CONTROLS.json", "../wave_de_fixture_closure/WAVE_E_INTERACTIONS.json"]
coverage["coverage_status"] = "COMPLETE_FOR_TARGETED_REPRESENTATIVE_SCOPE_WITH_EXPLICIT_BASELINE_DEBT"
coverage["retention"] = "Accepted 48 positive Wave E captures and other prior states retained, not replaced; only four affected surfaces retested; old portal 404 never promoted to positive evidence"
save("COVERAGE_RECONCILIATION.json", coverage)

common = {"executed_at": NOW, "scenario_id": "RV-025", "runtime": {"environment": "Development / Non-Production", "sha": entry["head"], "branch": entry["branch"], "base_url": "http://127.0.0.1:8000", "browser_metadata": "BROWSER_METADATA.json", "viewports": [[1440, 900], [1024, 768], [390, 844]], "dirty_source": "ENTRY.json + SOURCE_INTEGRITY.json"}, "authority": "Direct Human targeted F-110/F-134/fresh canonical portal fixture request", "credentials_in_evidence": False, "production": "UNTOUCHED", "keyboard": "INTERACTIONS.json", "authorization": "HTTP_CONTROLS.json + DATA_INTEGRITY.json"}
records = [
    dict(common, evidence_id="RV-EV-061", result="PASS", finding_ids=["UIUX-F-110"], personas=["P-01 / uiux.persona.project-operations", "P-25 reader / uiux.audit.project"], preconditions=["Existing project/Quality read scopes unchanged", "Only shared associated labels and calendar accessible names changed"], steps=["Normal authenticated login", "View Projects and Quality at each viewport", "Reach date/calendar controls with keyboard", "Inspect programmatic labels, focus, RTL dates, contained table scrolling", "Verify actual Jalali inclusion/exclusion through authenticated HTTP"], expected="Each boundary has a unique associated Persian label and calendar action; filtering unchanged", actual="Four Projects and two Quality boundaries and calendar triggers distinctly named; keyboard outline visible, no page overflow; existing from/to names, values and filtering retained", screenshots=[c["name"] + ".jpg" for c in captures if c["name"].startswith(("projects", "quality"))], limitations=["Shared consumers represented by template contract; only requested Projects/Quality surfaces freshly captured", "Inherited Escape dismissal issue recorded independently as F-135; no full accessibility PASS claimed"]),
    dict(common, evidence_id="RV-EV-062", result="PASS", finding_ids=["UIUX-F-134"], persona="P-18 / admin; separate existing Platform authority, no active tenant context", preconditions=["Existing independent Platform assignment"], steps=["Normal Platform login", "Inspect catalogue/filter at all three sizes", "Tab from localized select to display action", "Verify tenant-admin denial and preserved organization query parameter"], expected="Static Tenant label uses existing Persian company vocabulary", actual="شرکت labels organization-filter; underlying organization parameter/options, stable codes, stored role identifiers/names and permissions unchanged", screenshots=[f"platform_{w}.jpg" for w in (1440, 1024, 390)], limitations=["Existing English system-role display names remain outside the authorized static-label repair"]),
    dict(common, evidence_id="RV-EV-063", result="PASS", finding_ids=[], persona="P-26 / uiux.wcd.external; zero tenant memberships", preconditions=["Fresh invitation/acceptance through canonical services", "Same retained supplier/exact issued RFQ version", "Clock and old expiry unchanged"], steps=["Create and accept fresh invitation through canonical services; discard token", "Normal external browser login", "View positive context/form at all three sizes", "Tab from supplier reference to submit action without submitting", "Check required file label, RTL/LTR, table scroll, overflow, runtime logs", "Deny expired grant, wrong actor, foreign opportunity identifier, manipulated POST and tenant workspaces"], expected="Positive exact-scope portal while valid; no tenant access or cross-supplier disclosure", actual="Positive portal and keyboard-reachable primary action at all sizes; no page overflow or runtime errors; 16/16 authenticated HTTP controls PASS; zero memberships and no quote submissions", screenshots=[c["name"] + ".jpg" for c in captures if c["name"].startswith(("portal", "external"))], fixture="PORTAL_FIXTURE.json", limitations=["Synthetic RFQ terms/line carry UIUX_TEST_ONLY_NON_AUTHORITATIVE", "No file uploaded or quotation lifecycle replayed; prior accepted lifecycle evidence retained", "Evidence proves the capture-time state; fresh grant expires normally"]),
    dict(common, evidence_id="RV-EV-064", result="FAIL_ACCESSIBILITY", finding_ids=["UIUX-F-135"], persona="P-01 / uiux.persona.project-operations", preconditions=["Existing auto-open-on-focus non-modal Jalali picker; no Escape handler in entry script"], steps=["Focus Projects date boundary", "Tab to named calendar button", "Press Escape", "Observe visible popover remains; retain focus/DOM evidence"], expected="Keyboard dismissal without selecting/changing a date", actual="Escape leaves one calendar popover visible; outside click dismisses; no focus trap or business change asserted", screenshots=["projects_390.jpg", "projects_mobile_focus_next.jpg"], classification="INHERITED_BASELINE_UI_DEBT; source clean at entry and name-only diff does not alter handlers", scope="Recorded only; no independent product behavior invented or remediation absorbed"),
]
save("EVIDENCE_RECORDS.json", records)

finding = {"finding_id": "UIUX-F-135", "module": "Shared Jalali calendar / Projects and Quality", "surface_id": "SURF-074", "route": "/projects/", "category": "ACCESSIBILITY", "severity": "MEDIUM", "status": "RUNTIME_CONFIRMED_BASELINE_DEBT", "runtime_classification": "FAIL_ACCESSIBILITY", "problem": "The inherited non-modal date picker opens on input focus and remains visible after Escape; keyboard dismissal without choosing a date is not supplied.", "evidence": {"evidence_ids": ["RV-EV-064"], "paths": ["wave_e_targeted_closure/INTERACTIONS.json", "wave_e_targeted_closure/projects_mobile_focus_next.jpg"], "source": "apps/accounts/static/js/erp_jalali.js: existing focus/click handlers; no Escape handler in clean-at-entry immutable HEAD source"}, "regression_attribution": "INHERITED_BASELINE_UI_DEBT; only trigger name derives from associated labels; original script and screenshot behavior support attribution", "user_impact": "Keyboard users cannot dismiss the focused calendar with Escape while preserving the date value.", "recommendation": "A separately bounded keyboard-dismissal repair should preserve date/filter semantics and verify focus return.", "business_logic_impact": "NONE_PERFORMED", "needs_domain_review": False, "remediation_performed": False, "root_pattern_candidate": [], "root_pattern_review": "Unmapped runtime accessible interaction issue; no static pattern sweep or invented mapping"}
current = {"recorded_at": NOW, "current_authority": "Supersedes current Wave E/final pointers in wave_de_fixture_closure only; accepted Wave D/completed Wave E evidence preserved", "wave_d": "WAVE_D_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT", "wave_d_reexecuted": False, "wave_e": WAVE, "coverage": "COMPLETE_FOR_TARGETED_REPRESENTATIVE_SCOPE_WITH_EXPLICIT_BASELINE_DEBT", "targeted_closures": {"UIUX-F-110": "PASS; shared labels and calendar names fixed; Projects/Quality direct runtime", "UIUX-F-134": "PASS; static organization label localized only", "external_positive_portal": "PASS; fresh canonical invitation and exact-scope non-member grant"}, "RV-025": {"result": "FAIL_ACCESSIBILITY", "execution": "COMPLETE", "positive_external_coverage": "PASS", "finding_ids": ["UIUX-F-135"], "reason": "All requested closures pass and coverage is complete; inherited Escape-dismissal accessibility debt remains explicit. No all-accessibility PASS is inferred."}, "final_uiux_status": FINAL, "completion_semantics": "Evidence-complete targeted runtime validation, including supported residual failures; not all findings remediated, full WCAG PASS, UX readiness or risk acceptance", "UX_READY_FOR_UAT": "NOT_ISSUED", "accepted_baseline_test_failures": 18, "inherited_statutory_assertion_debt": "RETAINED separately; not rerun", "additional_inherited_projects_assertion_debt": 1, "additional_inherited_ui_debt": "UIUX-F-135", "baseline_debt_reclassified": False, "unresolved_attributable_regressions": 0, "indeterminate_regressions": 0, "tests": "Focused 11 PASS (+3 subtests); affected 14 PASS / 1 proved inherited assertion FAIL", "http": "16/16 PASS", "runtime_errors": 0, "new_product_decision_required": False, "evidence": "wave_e_targeted_closure/EVIDENCE_RECORDS.json", "coverage_evidence": "wave_e_targeted_closure/COVERAGE_RECONCILIATION.json", "report": "wave_e_targeted_closure/COMPLETION_REPORT.md", "regression": "wave_e_targeted_closure/REGRESSION_ATTRIBUTION.json", "authorization_models_roles_codes_stored_values": "UNCHANGED", "schema_migration": "NONE", "cep078079": "NOT_EXECUTED", "production": "UNTOUCHED", "human_signoff": "NOT_EXECUTED", "git_writes": "NOT_EXECUTED", "next_action": "STOP after Wave E/final UIUX reconciliation"}
save("FINAL_RECONCILIATION.json", current)
append_mapping("UIUX_RUNTIME_VALIDATION_RESULTS.yaml", current)
p = BASE / "UIUX_RUNTIME_VALIDATION_RESULTS.yaml"
text = p.read_text(encoding="utf-8")
text = text.replace("  status: TARGETED_RUNTIME_VALIDATION_PARTIAL", "  status: " + FINAL, 1)
text = text.replace("Current D/E results are wave_de_fixture_closure; RV-020/RV-022 remain retained PASS and earlier sections are historical.", "Accepted Wave D is wave_de_fixture_closure; current Wave E/final results are wave_e_targeted_closure; earlier sections remain historical.", 1)
p.write_text(text, encoding="utf-8")
append_mapping("UIUX_FINDINGS_REGISTER.yaml", {"recorded_at": NOW, "historical_findings": "PRESERVED_UNCHANGED", "current_dispositions": {"UIUX-F-110": "RESOLVED_AUTHORIZED_ACCESSIBLE_NAME_SCOPE; direct Projects/Quality evidence; shared-consumer representative equivalence", "UIUX-F-134": "RESOLVED_AUTHORIZED_STATIC_FILTER_LABEL; stored role names/codes unchanged", "UIUX-F-135": "OPEN_INHERITED_BASELINE_ACCESSIBILITY_DEBT; no unrelated remediation"}, "new_findings": [finding], "current_max_finding_id": "UIUX-F-135", "evidence": current["evidence"], "report": current["report"]})
append_mapping("UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", {"recorded_at": NOW, "report": current["report"], "UIUX-F-110": "Shared associated date-boundary labels/calendar action names repaired; no new pattern mapping invented", "UIUX-F-134": "RP-C01-TECHNICAL-LANGUAGE-LEAK: static company-filter label resolved", "UIUX-F-135": "UNMAPPED inherited keyboard-dismissal finding; recorded only", "unchanged_patterns_and_historical_evidence": True, "coverage": current["coverage_evidence"]})

p = BASE / "UIUX_RUNTIME_FIXTURE_REGISTRY.yaml"
old = json.loads(p.read_text(encoding="utf-8"))
data = {"recorded_at": NOW, "fresh_portal": fixture, "replaces_expired_context_for_positive_evidence_only": True, "old_grant_retained_and_denied": True, "membership_roles_permissions_scopes_unchanged": True, "data_integrity": "wave_e_targeted_closure/DATA_INTEGRITY.json", "reference_accounts": "RETAINED; no reset/deletion/deactivation", "evidence_valid_at_capture": True}
p.write_bytes(p.read_bytes().rstrip()[:-1].rstrip() + (',\n  "' + KEY + '": ' + json.dumps(data, ensure_ascii=False, indent=2).replace("\n", "\n  ") + "\n}\n").encode("utf-8"))
new = json.loads(p.read_text(encoding="utf-8"))
assert all(new[k] == v for k, v in old.items())

report = f"""# Wave E targeted closure — 2026-10-23

**{WAVE}**. **{FINAL}**.

All three requested closures PASS: F-110 accessible names, F-134 static company label and positive authenticated external portal coverage. RV-025 is fully executed for its targeted representative coverage, but retains **FAIL_ACCESSIBILITY** for independently observed inherited **F-135**, calendar Escape dismissal. Completion means supported evidence and explicit debt, not an all-accessibility PASS or risk acceptance. **UX_READY_FOR_UAT = NOT_ISSUED**.

| Target | Result and evidence |
|---|---|
| F-110 | PASS — RV-EV-061; four Projects/two Quality Persian boundary labels with matching distinct calendar action names; unchanged names, values and filters |
| F-134 | PASS — RV-EV-062; static `Tenant` filter label becomes `شرکت`; stored names/codes/values and authorization unchanged |
| P-26 positive portal | PASS — RV-EV-063; same external identity, fresh service-created/accepted invitation, exact issued RFQ version; zero memberships |
| Inherited F-135 | FAIL_ACCESSIBILITY — RV-EV-064; Escape leaves the auto-open calendar visible; independently recorded without remediation |

## Scope and implementation

The shared filter row associates separate Persian labels with each from/to input. The Jalali trigger derives its accessible name from the associated field label. A version query on the existing script reference refreshes the previously cached script; live generic names persisted until that cache refresh. No date parsing, filtering, input values, events or picker lifecycle changed. The Platform catalogue changes only one literal presentation label. English stored role display names remain as observed and outside the static-label closure.

The invitation manager `uiux.wavec.portal` uses its existing effective permission; neither Buyer nor Owner was assumed to hold it. `create_supplier_portal_invitation` → `accept_supplier_portal_invitation` → `get_supplier_portal_rfq_context` creates and verifies the test context. The one-time token exists only in memory and is discarded. No delivery message is sent. The fresh invitation expires normally at **2026-10-23 18:58:32 Asia/Tehran**, before the unchanged RFQ deadline; capture-time evidence does not extend its validity. The old accepted invitation/grant remains unchanged and denied after expiry. No membership, account, privilege, RFQ, quote, financial or source record is modified.

## Validation and retained debt

Focused: **11/11 PASS**, with three date-field subtests. Affected regression: **14/15 PASS**, one inherited Projects assertion for the absent `/projects/sites/` link. [Entry-template probe](BASELINE_PROBE.json) reproduces the identical failure with immutable HEAD versions of all three changed templates supplied in memory; these files were clean at entry. Its preceding positive/negative tenant assertions pass. No repository files or Git state were restored. **Zero unresolved attributable or indeterminate regressions**. [Attribution](REGRESSION_ATTRIBUTION.json), [affected JUnit](affected.xml), [focused JUnit](focused_final.xml).

The original **18 accepted baseline failures** remain unchanged debt; no unrelated suite was rerun or reclassified. The prior separately recorded statutory-copy assertion remains separate. The newly exposed inherited Projects navigation assertion and baseline UI keyboard finding F-135 are also separate; none is hidden in the 18. No full-suite PASS is claimed. Ruff check/format of the new presentation test and Django system check PASS. Development migration guard PASS; no migration created or executed.

Authenticated HTTP: **16/16 PASS**, normal login/cookies/CSRF. Positive scoped context, old expiry, wrong internal principal, foreign opportunity identifier, manipulated unauthorized submission, tenant/Platform boundaries and actual Jalali inclusion/exclusion are verified. The denied POST creates no submission. [HTTP controls](HTTP_CONTROLS.json).

Browser: **1440×900, 1024×768, 390×844** for all four affected surfaces. Positive portal context, required upload/reference labels, keyboard-reachable submit action and visible focus are directly observed without uploading/posting a quote. Projects/Quality have distinct field/calendar names and keyboard focus; tables scroll inside their containers, with Persian RTL and LTR dates/identifiers. No horizontal page overflow or unexpected browser errors. Tailwind Development warnings remain explicit. The full browser build is not exposed; prior same-provider reduced version metadata is retained with that limitation. [Browser captures](BROWSER_CAPTURES.json), [interactions](INTERACTIONS.json), [logs](BROWSER_LOGS.json).

F-135 is inherited: the entry script has no Escape-dismissal handler, and the only script behavior diff is the trigger name. The observed popover remains visible after Escape; no full WCAG or screen-reader certification is claimed. This item is recorded, not silently absorbed into the two presentation repairs. It prevents an RV-025 accessibility PASS, but creates no missing positive coverage cell or indeterminate regression. Runtime Playbook §12 permits evidence-backed failure dispositions at closure.

## Coverage and preservation

Accepted Wave D remains **WAVE_D_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT**, unchanged and not reexecuted. Accepted completed Wave E surfaces/interactions remain preserved; only Projects, Quality, Platform label and positive portal receive this delta. [Coverage reconciliation](COVERAGE_RECONCILIATION.json) combines the retained evidence with direct current evidence. The earlier expired portal denial is never promoted into positive evidence. Inventory/Quality reader perspectives still do not certify specialist write authority; current representative states do not certify all routes/lifecycles or all 26 personas on every surface. No material positive portal cell remains blocked.

[Entry](ENTRY.json), [source integrity](SOURCE_INTEGRITY.json) and [data integrity](DATA_INTEGRITY.json) preserve existing dirty changes and historical evidence. Database additions are exactly one invitation, one grant and two canonical audit events; existing rows, authorization, financial sources and the expired grant are unchanged. Session/last-login bookkeeping is excluded explicitly. All retained identities remain active as before. HEAD/index, CEP Registry and Roadmap remain unchanged.

CEP-078/079, Production actions/certification, Human Sign-off and Git writes: **NOT EXECUTED**. No Product Decision is requested or inferred. **STOP after this reconciliation.**
"""
(OUT / "COMPLETION_REPORT.md").write_text(report, encoding="utf-8")
(BASE / "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md").write_text(f"# Wave E current disposition — 2026-10-23\n\n**{WAVE}**. All requested closures PASS and positive portal coverage is complete. RV-025 remains **FAIL_ACCESSIBILITY**, solely for separately recorded inherited calendar Escape-dismissal finding **F-135**. No accessibility PASS is inferred.\n\nFinal UIUX: **{FINAL}**; **UX_READY_FOR_UAT = NOT_ISSUED**. This is evidence completion with explicit debt, not all findings remediated or Human risk acceptance. Wave D/completed prior Wave E evidence remains preserved and was not replayed.\n\nFocused 11 PASS; affected 14 PASS / 1 proved inherited Projects assertion FAIL; HTTP 16/16 PASS. Original 18 baseline failures and prior inherited statutory-copy assertion remain separate explicit debt. No attributable/indeterminate regressions.\n\n[Current completion report](wave_e_targeted_closure/COMPLETION_REPORT.md), [evidence](wave_e_targeted_closure/EVIDENCE_RECORDS.json), [coverage](wave_e_targeted_closure/COVERAGE_RECONCILIATION.json). No CEP-078/079, Production, Human Sign-off or Git writes. **STOP.**\n", encoding="utf-8")
p = BASE / "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md"
prefix = f"# Current Wave E/final reconciliation — 2026-10-23\n\n**{WAVE}**. **{FINAL}**. F-110, F-134 and authenticated external positive portal coverage PASS; RV-025 retains **FAIL_ACCESSIBILITY** for inherited **F-135** keyboard-dismissal debt. **UX_READY_FOR_UAT = NOT_ISSUED**. Completion records supported results and explicit residual failures, not an all-accessibility PASS.\n\nWave D and all accepted completed evidence remain preserved. Original 18 accepted baseline failures and prior inherited statutory-copy assertion remain explicit; one additional inherited Projects assertion is separately reproduced with entry templates. Zero attributable or indeterminate regressions.\n\n[Current report](wave_e_targeted_closure/COMPLETION_REPORT.md), [coverage](wave_e_targeted_closure/COVERAGE_RECONCILIATION.json), [current results](wave_e_targeted_closure/FINAL_RECONCILIATION.json). Earlier content below is historical. No CEP-078/079, Production, Human Sign-off or Git writes. **STOP.**\n\n---\n\n"
p.write_bytes(prefix.encode("utf-8") + p.read_bytes())
print("Wave E/final results reconciled with complete evidence and explicit baseline debt; RV-025 accessibility failure retained truthfully; STOP.")
