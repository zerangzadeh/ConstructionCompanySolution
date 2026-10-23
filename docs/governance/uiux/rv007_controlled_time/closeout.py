"""Reconcile RV-007 truthfully; browser environment gaps never become PASS."""
from support import *
from xml.etree import ElementTree as ET

guard()
entry = read("ENTRY.json")
fixture = read("FIXTURE.json")
attribution = read("REGRESSION_ATTRIBUTION.json")
integrity = read("INTEGRITY.json")
http = read("HTTP_SUMMARY.json")
browser = read("BROWSER.json")
assert attribution["counts"] == {"ATTRIBUTABLE_REGRESSION": 9, "BASELINE_PREEXISTING": 18, "INDETERMINATE": 0}
assert attribution["unresolved_attributable_regressions"] == 0
assert integrity["retained_rfq_unchanged"] and integrity["git_head_index_unchanged"]
assert http["all_expected"] and http["observations"] == 12
assert all(x["main_count"] == 1 and not x["overflow"] and not x["duplicate_ids"] for x in browser)
labels = {x["label"] for x in browser}
mobile_opened = "opened_comparison_mobile" in labels
decision = "WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT" if mobile_opened else "WAVE_C_BLOCKED_ENVIRONMENT"
rv_result = "PASS" if mobile_opened else "BLOCKED_ENVIRONMENT"
save("BROWSER_RECONCILIATION.json", {"desktop_opened_comparison": "PASS", "desktop_opened_actions": "PASS", "desktop_confidential_comparison_form": "PASS", "mobile_confidential_comparison_form": "PASS", "mobile_opened_workspace": "PASS" if mobile_opened else "NOT_EXECUTED: local browser tool repeatedly reports disabled in Work settings", "browser_observations": len(browser), "screenshots": [str(p.name) for p in OUT.glob("*.png")], "authenticated_actor": "uiux.wavec.buyer", "desktop_viewport": "1440x900", "mobile_viewport": "390x844", "single_main_no_overflow_unique_ids": True, "viewport_reset": "NOT_EXECUTED: blocked by disabled browser tool", "permission_settings": "Browser local Work control is not exposed by connected ChatGPT plugin permission tool; no global permission changed", "authorized_retry_after_user_browser_tag": "Tool still reports local browser use disabled; no workaround or setting bypass"})
requirements = [
    ("protected opening", "PASS", "SERVICE_CONTROLS.json / FIXTURE.json: denied one microsecond before close+24h; opened one second afterward"),
    ("independent duties and approval", "PASS", "FIXTURE.json: buyer requests, opening-approver approves; buyer prepares admissibility, separate custodian approves; self-approval disabled"),
    ("populated confidential comparison", "PASS", "FIXTURE.json / HTTP.json / BROWSER.json: real normalized amount and exact source locator visible only to authorized buyer"),
    ("source/hash/custody/scan", "PASS", "SCAN.json / INTEGRITY.json: actual retained PDF; real Defender result; canonical assessment; pinned package and delivery hashes match; immutable source writes denied"),
    ("same-tenant unauthorized denial", "PASS", "SERVICE_CONTROLS.json / HTTP.json: HR service denied and HTTP403"),
    ("site-only denial", "PASS", "SERVICE_CONTROLS.json / HTTP.json: Project-level confidential service denied and RFQ HTTP404"),
    ("cross-tenant denial", "PASS", "SERVICE_CONTROLS.json: foreign actor/tenant cannot deliver quote; HTTP.json: buyer cannot resolve foreign RFQ, HTTP404"),
    ("manipulated-action denial", "PASS", "SERVICE_CONTROLS.json / HTTP.json: changed idempotency payload, unknown action, other-RFQ quote, malformed UUID, missing CSRF denied"),
    ("stage and next-action UI", "PASS", "BROWSER.json / HTTP.json: closed RFQ, retained prepared comparison, exact source choices and permissions; independent approval control unavailable to requester"),
    ("authenticated desktop/mobile opened-stage journey", "PASS" if mobile_opened else "BLOCKED_ENVIRONMENT", "Desktop opened workspace and desktop/mobile comparison form verified; final mobile opened-workspace capture " + ("verified" if mobile_opened else "still blocked by local Work browser setting")),
]
matrix = json.loads((OUT.parent / "wave_c_final_closure/WAVE_C_FINAL_MATRIX.json").read_text(encoding="utf-8"))
for row in matrix["scenario_results"]:
    if row["scenario_id"] == "RV-007":
        row.update(result=rv_result, coverage="Controlled application-clock lifecycle and exact regression attribution complete; " + ("browser complete" if mobile_opened else "final authenticated mobile opened-workspace capture remains blocked"), evidence="COMPLETION_REPORT.md")
    else:
        row["evidence"] = "../wave_c_final_closure/" + row["evidence"]
matrix.update(decision=decision, recorded_at=REAL_NOW(), pass_count=12 if mobile_opened else 11, pending_real_time_count=0, blocked_environment_count=0 if mobile_opened else 1, unresolved_attributable_regressions=0, original_baseline_failures=18, full_required_execution_complete=mobile_opened, wave_closed=mobile_opened, regression_classification=attribution["counts"], rv007_requirements=[{"requirement": k, "result": v, "evidence": e} for k,v,e in requirements], evidence_clock="Explicit Human-authorized frozen application clock only; actual and simulated timestamps recorded separately", prior_baseline_debt="../wave_c_final_closure/REGRESSION_ATTRIBUTION.json")
save("WAVE_C_MATRIX.json", matrix)
report = f"""# RV-007 Controlled-Time Final Closure — 2026-10-23

**EXECUTION {'COMPLETE' if mobile_opened else 'PARTIAL'}. RV-007: {rv_result}.**
**{decision}.** No full closure is issued while the required final mobile
opened-workspace capture is missing. Eleven prior scenario PASS results are
preserved; this attempt does not reopen them or official statutory certification.

## Authorized result and exact scope

The Human explicitly authorized application-only controlled time, canonical
synthetic RFQ/on-time quote, existing independent duties, real scan evidence,
attribution of all 27 failures, and fixes only for attributable regressions.
The separate Option 1 reply authorizes one Development admissibility policy with
`allow_self_approval=false` and one independent approver with revision-confidential
permission, exact Project only. Subsequent browser-only authorizations do not
expand this scope. No business rule, default role, authorization architecture,
schema, migration or Production setting changed. No Git writes occurred.

The actual source touch set is **test_rfq_close.py** and
**test_cep032_buyer_actions.py** plus this evidence directory and append-only
Wave C results/report/findings reconciliation. Existing dirty source was preserved.
Branch `main`, HEAD/origin/main `{entry['head']}`. CEP Registry/roadmap unchanged:
no CEP lifecycle, new gate authority, Human Sign-off or certification inferred.

## Synthetic lifecycle and clock boundary

Exactly one new RFQ `{fixture['rfq']}` / `RV007-CONTROLLED-DEV-001` is retained.
It uses the existing tenant, Project, approved Purchase Request, line, supplier
and separately authorized buyer/custodian/opening approver. Canonical RFQ and
quote services create, issue, capture and submit. Server receipt and submission
are on time; `is_late=false`. Closing and allowed opening are set once at creation
exactly **24 hours apart**, then never directly edited. No SQL/date/state repair.

The evidence scripts and loopback-only `127.0.0.1:8017` server temporarily patch
`django.utils.timezone.now` within their processes. The normal Development server,
OS/system clock and product clock implementation are unchanged. CLOCK.json and
FIXTURE.json distinguish application time from real wall-clock time. Simulated
opening is `{fixture['application_opened_at']}`; actual wall clock was
`{fixture['actual_opening_wall_clock']}`. This is controlled-time Development
evidence, not an assertion that 24 real hours elapsed.

Canonical close freezes the effective submitted revision. The custodian retains
a real synthetic PDF in protected storage. A genuine Microsoft Defender custom
scan reports `found no threats`, exit 0, with identical pre/post hashes. Only then
does the existing canonical processing service record CLEAN. No scanner output,
assessment, source, custody or package was mocked or fabricated. Scanner authority
was assigned canonically to the separate custodian for five minutes; it is now
expired and authorization denies it. No expired duty was revived. The initial
scanner assignment to the former DMS actor was rejected by an expired-but-
unrevoked uniqueness constraint; no row changed on that attempt.

Protected opening is denied after close and at close+24h minus one microsecond.
At close+24h plus one second the buyer requests; a different opening approver
approves. Retry returns the same event. Permission without an exact revision grant
cannot read the quote; revision-only grants are canonically issued by the separate
access manager. Delivery hashes match the original, custody, document version,
assessment and pinned package. Unauthorized CLEAN assessment and immutable source,
custody and opening writes are denied. The source SHA-256 is
`{fixture['source_sha256']}`.

Buyer admissibility preparation is independently approved by the existing
Project-scoped custodian, with the expressly authorized additional custom role.
The new policy is selected/applied through governed policy services with
self-approval disabled and bounded Development effective dates. No Owner/Admin
default permissions changed. See PREREQUISITES.json and canonical grant audits.

Populated comparison is prepared through `prepare_comparison` from exact source
assertions (120 units, 12.50 IRR unit price, explicit 0.50 discount; synthetic
values copied from the synthetic PDF), yielding **1499.50000000 IRR**. The
commercial scope has no application creator service in the repository; the
existing immutable validating domain constructor is used under an explicit
`rfq_quotes.prepare_comparison` permission and exact tenant/version/line checks.
No direct dates/states are assigned, and no alternate service or business rule
was introduced. Comparison finalization, award and downstream financial actions
are outside this requested access/comparison evidence and were not executed.

## Authorization, browser and retained history

SERVICE_CONTROLS.json, HTTP.json and INTEGRITY.json cover same-tenant HR,
site-only, cross-tenant and permission-without-grant denials; changed idempotency
payload, source overwrite, unregistered action, other-RFQ selector, malformed UUID,
missing CSRF and invalid comparison are denied. Twelve real authenticated HTTP
observations PASS, including actual cookie login and CSRF-bearing POSTs, without
changing quote/opening/comparison counts. Foreign-owner credentials were absent;
that actor's cross-tenant denial is proved directly through the service, while
HTTP proves the authorized buyer cannot resolve a foreign tenant RFQ. No new
account/password or foreign quote was manufactured.

Authenticated Chrome evidence verifies desktop opened workspace, populated
comparison, permitted-action disclosure, and desktop/mobile confidential
comparison forms. Four captures have one main, unique IDs and no page overflow.
The final authenticated **mobile opened-workspace capture is not executed**:
local browser access became disabled in Work settings. The tool continued to
deny access after explicit Human retries and the Browser plugin mention. Connected
ChatGPT plugin permission inspection does not expose the Work local-browser
switch; no global permissions or security settings were changed. No HTTP/unit
result substitutes for the missing browser evidence, and no workaround bypasses
that access restriction. The temporary viewport reset is also blocked by that
restriction. See BROWSER_RECONCILIATION.json.

The retained `WAVE-C-RFQ-A` is unchanged: close October 24, 2026 14:46:11 Tehran;
earliest opening October 25 at 14:46:11. Real-clock early close/opening remain
denied. Its early opening hits the missing effective-close manifest first; the
synthetic scenario separately isolates the 24-hour boundary. All preexisting rows
are retained. The only changed preexisting rows are the expected DMS number
sequence and authorized approver membership migration timestamp updated by the
canonical Initial Grant service. Existing business histories, workforce identity,
financial/Payroll/Inventory facts and retained RFQ fingerprints are preserved.

## Exact attribution and validation

All **27 original failures** are individually classified in
[REGRESSION_ATTRIBUTION.json](REGRESSION_ATTRIBUTION.json):

- **9 ATTRIBUTABLE_REGRESSION, all RESOLVED**: one duplicate active assignment/
  broad fixture scope; eight buyer custom-role compatibility fields ignored after
  the accepted shared migrated-role bootstrap. Reuse the existing assignment,
  remove the test's broad scope before its denial assertion, and explicitly assign
  the already intended isolated custom role. Existing permission sets and test
  assertions are preserved. No product permission weakening.
- **18 BASELINE_PREEXISTING, retained**: shared legacy approver setup has no scope;
  it fails before scenario assertions. `_make_actor`, `_grant` and relevant
  authorization ASTs match immutable HEAD. Exact immutable-HEAD probes reproduce
  the permission-present/scope-absent denial and confirm the old buyer custom
  compatibility role plus scope authorizes close. Probes run in an isolated test
  database and roll back. Full frozen-suite migration replay was superseded by
  these exact-seam probes; no full frozen-suite PASS is claimed.
- **0 INDETERMINATE; 0 unresolved attributable regressions; 0 new failures.**

Final focused: **{attribution['final_focused']}**.
Final affected: **{attribution['final_affected']}**.
Full repository regression is not claimed green. Earlier baseline debt in
wave_c_final_closure/REGRESSION_ATTRIBUTION.json remains explicit and unchanged.
Django checks, migration drift, focused Ruff lint/format PASS. No migration.

## Reconciliation and stop

The remaining blocker is environmental: final mobile opened-workspace browser
evidence. The positive controlled-time service lifecycle and regression attribution
are complete, but RV-007 cannot yet receive full PASS under the requested browser
criterion. `WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT` is **NOT ISSUED**.
The current [matrix](WAVE_C_MATRIX.json) supersedes only this attempt's current
RV-007 disposition and attribution; all earlier evidence remains historical.

Production, Wave D, CEP-078/079, Human Sign-off, Production Certification/Cutover,
Git add/commit/push/merge/branch/worktree: **NOT EXECUTED**. Temporary loopback
server is stopped at closeout; no product clock override remains active.

**STOP.**
"""
(OUT / "COMPLETION_REPORT.md").write_text(report, encoding="utf-8")
results = ROOT / "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_RESULTS.yaml"
with results.open("a", encoding="utf-8") as stream:
    stream.write(f"""
rv007_controlled_time:
  recorded_on: '2026-10-23'
  decision: {decision}
  RV-007: {rv_result}
  report: rv007_controlled_time/COMPLETION_REPORT.md
  matrix: rv007_controlled_time/WAVE_C_MATRIX.json
  regression_attribution: rv007_controlled_time/REGRESSION_ATTRIBUTION.json
  integrity: rv007_controlled_time/INTEGRITY.json
  positive_controlled_time_service_lifecycle: PASS
  application_clock: Explicit Human-authorized process-only freeze; OS and normal server unchanged
  source_scan_custody: PASS; genuine Defender scan and canonical assessment
  authenticated_desktop_opened_workspace: PASS
  authenticated_mobile_comparison_form: PASS
  authenticated_mobile_opened_workspace: {'PASS' if mobile_opened else 'BLOCKED_ENVIRONMENT; local browser use disabled in Work settings'}
  original_27_classification:
    ATTRIBUTABLE_REGRESSION: 9
    BASELINE_PREEXISTING: 18
    INDETERMINATE: 0
  unresolved_attributable_regressions: 0
  focused: 9 PASS
  affected: 34 PASS; 18 baseline FAIL; 21 subtests PASS
  prior_baseline_debt: wave_c_final_closure/REGRESSION_ATTRIBUTION.json
  pass_count: {12 if mobile_opened else 11}
  blocked_environment_count: {0 if mobile_opened else 1}
  pending_real_time_count: 0
  full_required_execution_complete: {str(mobile_opened).lower()}
  wave_closed: {str(mobile_opened).lower()}
  retained_rfq: UNCHANGED; real-clock early close/opening denied
  product_rules_and_default_roles: UNCHANGED
  temporary_scanner_duty: EXPIRED; canonical five-minute interval
  CEP_registry: UNCHANGED
  production: UNTOUCHED
  wave_d_cep078079: NOT_EXECUTED
  git_writes: NOT_EXECUTED
  next_action: STOP
""")
wave_report = ROOT / "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md"
with wave_report.open("a", encoding="utf-8") as stream:
    stream.write(f"\n\n## RV-007 controlled-time reconciliation — 2026-10-23\n\n**{decision}.** "
        "The explicitly authorized application-only clock completes the canonical positive opening, "
        "independent approval/admissibility, exact confidential comparison, real source/hash/custody/scan "
        "and authorization controls. OS clock, normal server, retained RFQ, business rules/default roles "
        "and Production remain unchanged. All 27 original regression failures are attributed: "
        "**9 attributable, fixed; 18 baseline, retained; 0 indeterminate; 0 unresolved attributable**. "
        "Focused **9 PASS**; affected **34 PASS / 18 baseline FAIL + 21 subtests PASS**. "
        "Twelve real authenticated HTTP controls PASS. Desktop opened workspace and desktop/mobile "
        "comparison form pass; final mobile opened-workspace capture remains blocked because local "
        "browser use is disabled in Work settings. No full RV-007/Wave C PASS or completion status is issued. "
        "[Report](rv007_controlled_time/COMPLETION_REPORT.md), "
        "[matrix](rv007_controlled_time/WAVE_C_MATRIX.json), "
        "[attribution](rv007_controlled_time/REGRESSION_ATTRIBUTION.json), "
        "[integrity](rv007_controlled_time/INTEGRITY.json). "
        "Prior findings and baseline debt preserved. Wave D, CEP-078/079, Production, Human Sign-off "
        "and Git writes: **NOT_EXECUTED**. **STOP.**\n")
findings = ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
with findings.open("a", encoding="utf-8") as stream:
    stream.write(f"""
rv007_controlled_time_revalidation:
  decision: {decision}
  recorded_on: '2026-10-23'
  report: rv007_controlled_time/COMPLETION_REPORT.md
  current_RV007_service_coverage: Positive opening, independent approval, confidential comparison, genuine source/custody/scan and negative authorization controls PASS under explicitly authorized application clock
  UIUX_F008_F009: Desktop opened workspace and mobile comparison form verified; final mobile opened-workspace verification remains BLOCKED_ENVIRONMENT
  regression_attribution: rv007_controlled_time/REGRESSION_ATTRIBUTION.json
  original_27: 9 attributable RESOLVED; 18 baseline RETAINED; 0 indeterminate
  unresolved_attributable_regressions: 0
  prior_closed_findings_preserved: true
  full_wave_closed: {str(mobile_opened).lower()}
  next_action: STOP
""")
save("FINAL_VERIFICATION.json", {"decision": decision, "rv007": rv_result, "positive_service_lifecycle": "PASS", "regression_attribution_complete": True, "unresolved_attributable_regressions": 0, "final_mobile_opened_workspace": "PASS" if mobile_opened else "BLOCKED_ENVIRONMENT", "closure_complete_status_issued": mobile_opened, "retained_rfq": "UNCHANGED", "production": "UNTOUCHED", "git_writes": "NOT_EXECUTED", "wave_d_cep078079": "NOT_EXECUTED"})
print(decision, "RV007", rv_result, "STOP")
