"""Append bounded current audit dispositions; preserve historical evidence."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
BASE = OUT.parent


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append(path, key, value):
    text = path.read_text(encoding="utf-8")
    assert "\n" + key + ":" not in text
    encoded = json.dumps(value, ensure_ascii=False, indent=2)
    path.write_text(text.rstrip() + "\n\n" + key + ":\n" + "\n".join("  " + line for line in encoded.splitlines()) + "\n", encoding="utf-8")


assert not (OUT / "SCENARIOS.json").exists(), "Never overwrite a completed attempt"
browser, entry, metadata, http = read("BROWSER.json"), read("ENTRY.json"), read("BROWSER_METADATA.json"), read("HTTP_SUMMARY.json")
assert http["all_passed"] and http["count"] == 18
assert "8 passed" in (OUT / "affected_final.txt").read_text(encoding="utf-8")
by_name = {r["name"]:r for r in browser}
for name, family in (("d020_safety_retest_desktop","info"),("d020_safety_action_retest_mobile","info"),("d020_quality_retest_mobile","success"),("d020_quality_retest_tablet","success"),("d020_quality_closed_retest_mobile","success"),("d020_safety_closed_retest_mobile","success")):
    facts = by_name[name]["facts"]
    assert facts["mainCount"] == 1 and not facts["duplicateIds"] and not facts["unlabelled"]
    assert facts["documentWidth"] <= facts["clientWidth"]
    assert "erp-badge--" + family in facts["badges"][0]["class"]

decisions = [{
    "id":"PD-WD-022", "classification":"PRODUCT_DECISION_REQUIRED", "scenario":"RV-022", "finding":"UIUX-F-048",
    "surface":"/workflows/administration/versions/521eb6af-b641-4c39-9024-c60c1ed2fda0/",
    "observed":"Step names appear alongside raw keys/types. Transitions require reading legacy_approval -> approved / start -> legacy_approval and machine outcome codes. JSON is already in a keyboard-operable disclosure.",
    "canonical_gap":"The matrix asks to assess process comprehension and visual representation need. F-048 recommends a visual model, but is a finding/recommendation, not an approved choice of the primary administrative information hierarchy. The generic UI guidelines do not select between a business process review view and a technical configuration review view for this administrator surface.",
    "exact_human_question":"Which should be the primary Workflow version review view: a business-labelled process overview with technical configuration in a disclosure, or technical configuration for administrators?",
    "options":[{"choice":"Business-labelled overview first","impact":"Requires bounded presentation design/remediation and a runtime retest; preserve the registered declarative model, routes and lifecycle services."},{"choice":"Technical configuration primary","impact":"Requires explicit product disposition of F-048 and its comprehension expectations; does not itself prove usability PASS or accept security/business risk."}],
    "other_scenarios_can_continue":True,
    "wave_e_semantic_dependency":"No direct target dependency: RV-025 does not designate this Workflow detail as a representative surface. Wave E is nevertheless gated off by separate RV-016/RV-021 fixture blockers.",
    "status":"PENDING_HUMAN_RESPONSE; no decision inferred",
}]
save("PRODUCT_DECISIONS_REQUIRED.json",decisions)
scenarios = [
    {"scenario":"RV-016","result":"BLOCKED_AUTHORIZATION_FIXTURE","execution":"PARTIAL_POSITIVE_RUNTIME","evidence_id":"RV-EV-053","finding_ids":["UIUX-F-021","UIUX-F-022"],"detail":"Explicitly linked uiux.wavec.time has positive own-profile dashboard/empty-request and mobile evidence. It lacks payroll_ess.view_own; /payroll/ess/ returns 403. Other retained own-payroll permission holders lack an explicit ESS subject. No grant or identity link was added. Populated request/raw-status and positive Payroll ESS evidence remain unproved."},
    {"scenario":"RV-020","result":"PASS","execution":"EXECUTED_SCOPED_MATRIX_TARGETS","evidence_id":"RV-EV-054","finding_ids":["UIUX-F-090","UIUX-F-091"],"detail":"Separate Safety and Quality reader perspectives through retained P-11/P-25 uiux.audit.project A-only scope; authorized managerial comparison through P-17 uiux.persona.project-manager A/B. Populated closed, action-in-progress and verified details, inline next actions, Jalali dates, labels/headings, visible keyboard focus and bounded desktop/mobile/tablet layout observed. Three demonstrated semantic badge cases fixed and retested. No lifecycle submitted; no specialist create/review authority or exhaustive WCAG certification claimed."},
    {"scenario":"RV-021","result":"BLOCKED_TEST_DATA","execution":"NEGATIVE_BOUNDARY_ONLY","evidence_id":"RV-EV-055","finding_ids":["UIUX-F-099","UIUX-F-103"],"detail":"No tenant KnowledgePublication or KnowledgePublicationVersion exists. No mapped P-12 curator fixture. Existing P-18 admin is a verified Platform Admin, but has no existing credential in the retained DPAPI store or current authenticated browser session. Tenant Admin correctly denied the platform queue. No article/history/promotion success inferred from a denial or missing data; no publication, grant or credential created."},
    {"scenario":"RV-022","result":"BLOCKED_PRODUCT_DECISION","execution":"POSITIVE_RUNTIME_REVIEW_COMPLETE_PENDING_PRODUCT_DISPOSITION","evidence_id":"RV-EV-056","finding_ids":["UIUX-F-048"],"detail":"Verified explicit existing Tenant Admin workflow permissions and organization scope used for the functional administration perspective; not a new P-13 identity or narrow role claim. Populated immutable published version reviewed on desktop/mobile; keyboard disclosure works, no overflow/duplicate IDs. Raw transitions confirm F-048; PD-WD-022 records the primary review representation question. No arbitrary visual designer or authoring/lifecycle changes invented."},
]
save("SCENARIOS.json",scenarios)
records=[]
for row in scenarios:
    prefix = "d" + row["scenario"].split("-")[1]
    captures = [r for r in browser if r["name"].startswith(prefix)]
    records.append({
        "evidence_id":row["evidence_id"],"scenario_id":row["scenario"],"executed_at":captures[0]["at"] if captures else None,
        "runtime":{"environment_name":"Development","base_url":"http://127.0.0.1:8000/","git_sha":entry["head"],"dirty_source_manifest":"ENTRY.json#hashes","browser":metadata["browser"],"browser_version":metadata["reportedChromiumVersion"],"full_engine_build":"NOT_EXPOSED","viewports":metadata["viewports"]},
        "persona":{"effective_permission_bundle_reference":"READINESS.json#personas","effective_scope_reference":"SCOPES.json","verified_shapes":[r["persona"] for r in captures]},
        "preconditions":["Existing active membership/explicit effective permissions and scope; no account or grant creation","Existing domain state only; no production access","Accepted Wave C closure and retained 18 baseline failures"],
        "steps":["Verify actual identity and effective server authority","Open the canonical reachable populated surface, or explicitly record missing fixture","Inspect semantic DOM and responsive viewport; use Tab/Enter on existing controls where applicable","Save screenshots/AX observations and compare role-conditioned controls","Supplement with real-cookie server read/scope controls; no successful business POST"],
        "expected_result":"Canonical scenario validation targets in UIUX_RUNTIME_VALIDATION_MATRIX.yaml; denied/empty pages cannot satisfy required populated success evidence",
        "actual_result":row["detail"],"result":row["result"],"existing_finding_ids":row["finding_ids"],"new_finding_ids":[],
        "screenshots":[r["name"] + ".jpg" for r in captures],"browser_observations":"BROWSER.json","server_controls":"HTTP.json","console":"RUNTIME_LOGS.json",
        "accessibility":{"keyboard_notes":"d016_keyboard.json; d020_keyboard.json; Workflow disclosure Enter captured; not exhaustive WCAG audit","labels_landmarks_headings":"Per-capture semantic DOM, not inferred for blocked positive targets"},
        "responsive":{"notes":"Per-capture width equals client width; required positive targets missing for RV-016/RV-021. No Wave E coverage inferred."},
        "business_mutation_performed":False,"product_remediation":"Only RV-020 observed action_in_progress/verified/closed badge presentation; original text/status values remain unchanged"})
save("EVIDENCE_RECORDS.json",records)
summary={"recorded_on":"2026-10-23","environment":"Development / Non-Production","wave_d":"WAVE_D_BLOCKED_AUTHORIZATION_FIXTURE_AND_TEST_DATA","wave_e":"WAVE_E_NOT_STARTED_DUE_TO_WAVE_D_DEPENDENCY","scenarios":scenarios,"counts":{"wave_d":{"required":4,"positive_runtime_reviewed":3,"negative_only":1,"PASS":1,"BLOCKED":3,"PARTIAL_as_final_disposition":0},"wave_e":{"required":1,"executed":0,"NOT_STARTED":1}},"product_decisions":"wave_d_e/PRODUCT_DECISIONS_REQUIRED.json","required_product_decision_count":1,"focused_and_affected_regression":"8 unique tests PASS; affected_final.xml (4 shared localization/accessibility + 4 Safety/Quality view/admin)","authenticated_http":"18/18 PASS; no successful business POST","baseline_failures":18,"baseline_review":"wave_d_e/BASELINE_DEBT_REVIEW.json","new_observed_attributable_regressions":0,"new_observed_indeterminate_regressions":0,"regression_claim_limit":"Scoped verification only; full repository suite not rerun or claimed green","findings_fully_closed":0,"existing_finding_partially_remediated":"UIUX-F-090: three directly observed status cases; remaining untested lifecycle statuses retained","new_findings":0,"schema_migration":"NONE; configured Development migration plan empty","browser_metadata":"wave_d_e/BROWSER_METADATA.json","report":"wave_d_e/COMPLETION_REPORT.md","wave_e_gate_report":"UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md","wave_c":"ACCEPTED_CLOSURE_RETAINED; no business/source drift except intentionally bounded badge colors that do not invalidate accepted journey evidence","production":"UNTOUCHED","cep078079":"NOT_EXECUTED","cep_registry_and_roadmap":"UNCHANGED","human_signoff":"NOT_EXECUTED","git_writes":"NOT_EXECUTED","next_action":"STOP; no Wave E or CEP continuation"}
append(BASE / "UIUX_RUNTIME_VALIDATION_RESULTS.yaml","wave_d_e_serial_execution",summary)
append(BASE / "UIUX_FINDINGS_REGISTER.yaml","wave_d_e_runtime_reconciliation",{
    "recorded_on":"2026-10-23","report":"wave_d_e/COMPLETION_REPORT.md","new_finding_count":0,"fully_closed_finding_count":0,"historical_finding_records":"PRESERVED_UNCHANGED",
    "current_dispositions":{"UIUX-F-021":"OPEN; source wording confirmed on own dashboard; populated raw-status behavior unvalidated because requests empty","UIUX-F-022":"OPEN; five permission-conditioned ESS destinations form the observed flat strip; no business-priority redesign","UIUX-F-048":"BLOCKED_PRODUCT_DECISION; populated Workflow raw transitions confirmed; PD-WD-022","UIUX-F-090":"PARTIALLY_REMEDIATED_RUNTIME_VERIFIED: observed action_in_progress=>info; verified/closed=>success; other lifecycle statuses not closed","UIUX-F-091":"OBSERVED_SAFETY_QUALITY_DATES_JALALI; no global finding closure or reclassification","UIUX-F-099":"BLOCKED_TEST_DATA; no populated publication UI evidence","UIUX-F-103":"BLOCKED_TEST_DATA; no populated history UI evidence"},
    "evidence":"wave_d_e/EVIDENCE_RECORDS.json","baseline_debt":"18 BASELINE_PREEXISTING retained; D nonblocking, E intersection explicit","wave_d":summary["wave_d"],"wave_e":summary["wave_e"],"production":"UNTOUCHED","git_writes":"NOT_EXECUTED"})
append(BASE / "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml","wave_d_bounded_runtime_delta",{"recorded_on":"2026-10-23","pattern":"RP-C25-STATUS-SEMANTICS-INCOMPLETE","finding":"UIUX-F-090","scope":"Only demonstrated action_in_progress, verified and closed badge cases on Safety/Quality; remaining status coverage not inferred","report":"wave_d_e/COMPLETION_REPORT.md","evidence":"wave_d_e/EVIDENCE_RECORDS.json","wave_e":"NOT_STARTED_DUE_TO_WAVE_D_DEPENDENCY"})
path=BASE / "UIUX_RUNTIME_VALIDATION_RESULTS.yaml"
text=path.read_text(encoding="utf-8")
assert "Waves D-E not executed." in text
path.write_text(text.replace("Waves D-E not executed.","Current Wave D/E disposition is wave_d_e_serial_execution; earlier sections remain historical.",1),encoding="utf-8")
save("FINAL_RECONCILIATION.json",summary)
print("Four Wave D dispositions and explicit Wave E gate reconciled; historical finding rows retained.")
