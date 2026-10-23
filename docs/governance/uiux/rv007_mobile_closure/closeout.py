"""Browser-only Wave C evidence reconciliation; no product or business writes."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
PRIOR = OUT.parent / "rv007_controlled_time"
sys.path.insert(0, str(PRIOR))
from support import guard, snapshot, REAL_NOW
from django.db import connection, transaction


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


guard()
entry = read(OUT / "ENTRY.json")
browser = read(OUT / "BROWSER.json")
attribution = read(PRIOR / "REGRESSION_ATTRIBUTION.json")
assert browser["result"] == "PASS"
assert browser["actor"] == "uiux.wavec.buyer"
assert browser["viewport"]["width"] == 390 and browser["viewport"]["height"] == 844
for layout in (browser["initial_layout"], browser["expanded_actions"], browser["final_layout"]):
    assert layout["mainCount"] == 1
    assert layout["documentWidth"] <= layout["clientWidth"]
assert not browser["initial_layout"]["duplicateIds"]
assert not browser["final_layout"]["duplicateIds"]
assert browser["expanded_actions"]["detailsOpen"]
assert "1499.50000000" in browser["initial_layout"]["mainText"]
assert "مرحله استعلام: بسته‌شده" in browser["initial_layout"]["mainText"]
assert not [x for x in browser["runtime_logs"] if x["level"] == "error"]
assert all("cdn.tailwindcss.com should not be used in production" in x["message"] for x in browser["runtime_logs"])
assert attribution["counts"] == {"ATTRIBUTABLE_REGRESSION": 9, "BASELINE_PREEXISTING": 18, "INDETERMINATE": 0}
assert attribution["unresolved_attributable_regressions"] == 0
assert not entry["prior_data_drift"]

# Verify every retained prior artifact byte, including test and scan evidence.
prior_artifacts = read(PRIOR / "ARTIFACTS.json")
assert all(digest(ROOT / path) == sha for path, sha in prior_artifacts.items())
source_delta = subprocess.check_output([
    "git", "diff", "--", "apps/procurement/test_cep032_buyer_actions.py",
    "apps/procurement/test_rfq_close.py",
], text=True, encoding="utf-8", stderr=subprocess.DEVNULL)
assert source_delta == (PRIOR / "SOURCE_DELTA.diff").read_text(encoding="utf-8")
assert all(digest(ROOT / path) == sha for path, sha in entry["hashes"].items())
assert digest(ROOT / ".git/index") == entry["index_sha256"]
assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() == entry["head"]
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
    after = snapshot()
assert after == read(OUT / "DATA_BEFORE.json")
assert after == read(PRIOR / "DATA_AFTER.json")
save("INTEGRITY.json", {
    "recorded_at": REAL_NOW(), "result": "PASS",
    "all_non_session_rows_unchanged": True,
    "snapshot_exclusions": "Django sessions and User.last_login; existing authenticated session reused",
    "prior_closeout_data_drift": {}, "retained_original_rfq": "UNCHANGED",
    "synthetic_rfq_quote_opening_comparison": "UNCHANGED; no new fixtures",
    "business_rules_authorization_architecture_default_roles": "UNCHANGED",
    "all_entry_file_hashes_unchanged_before_reconciliation": True,
    "prior_test_source_delta_matches_exactly": True,
    "prior_artifacts_verified_unchanged": len(prior_artifacts),
    "schema_migrations": "UNCHANGED; Development migration plan empty; no migration command run",
    "git_head_index": "UNCHANGED", "production": "UNTOUCHED",
    "product_clock_and_server": "UNCHANGED; existing normal port 8000 used",
    "new_attributable_regressions": 0, "new_indeterminate_regressions": 0,
    "regression_basis": "No product/source/data drift; browser check PASS; accepted prior focused/affected evidence retained without rerun",
    "baseline_preexisting_failures_retained": 18,
})

decision = "WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT"
matrix = read(PRIOR / "WAVE_C_MATRIX.json")
for row in matrix["scenario_results"]:
    if row["scenario_id"] == "RV-007":
        row.update(result="PASS", coverage="Prior accepted controlled-time lifecycle and attribution retained; final authenticated mobile opened-workspace browser capture PASS", evidence="COMPLETION_REPORT.md")
for requirement in matrix["rv007_requirements"]:
    if requirement["requirement"] == "authenticated desktop/mobile opened-stage journey":
        requirement.update(result="PASS", evidence="BROWSER.json and mobile JPG captures; prior desktop/mobile comparison evidence retained at ../rv007_controlled_time/BROWSER.json")
    else:
        requirement["evidence"] = "Prior accepted ../rv007_controlled_time/: " + requirement["evidence"]
matrix.update(
    decision=decision, recorded_at=str(REAL_NOW()), pass_count=12,
    pending_real_time_count=0, blocked_environment_count=0,
    full_required_execution_complete=True, wave_closed=True,
    browser_evidence="BROWSER.json", integrity="INTEGRITY.json",
    original_baseline_failures=18, unresolved_attributable_regressions=0,
    prior_controlled_time_report="../rv007_controlled_time/COMPLETION_REPORT.md",
    regression_attribution="../rv007_controlled_time/REGRESSION_ATTRIBUTION.json",
    evidence_clock="Prior synthetic lifecycle used an expressly authorized process-only application clock; this final browser capture uses existing normal Development server and wall clock",
    forbidden_actions="Wave D/E, CEP-078/079, Production, Human Sign-off, Git writes and branch/worktree creation NOT EXECUTED",
)
assert all(row["result"] == "PASS" for row in matrix["scenario_results"])
save("WAVE_C_MATRIX.json", matrix)

report = """# Wave C final browser closure — 2026-10-23

**EXECUTION COMPLETE. RV-007 = PASS.**
**WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT**

The single remaining authenticated mobile opened-workspace evidence gap is closed.
All 12 Wave C scenario dispositions are PASS within their previously authorized
scope. This is Development evidence closure, with the **18 BASELINE_PREEXISTING
failures explicitly retained**. Full repository regression is not claimed green.
Earlier baseline debt and the statutory exclusions remain unchanged.

The Human authorized only this browser capture and Wave C reconciliation. The
[prior report](../rv007_controlled_time/COMPLETION_REPORT.md) remains authoritative
historical evidence for the completed lifecycle, independent approvals, genuine
scan/hash/custody, isolation denials and regression attribution. Its former
environment blocker is superseded only by this final browser result. No prior
report, artifact, screenshot, test result or attribution was overwritten.

## Browser verification

Google Chrome **155.0.8059.82**, Windows, enabled Chrome Browser extension.
Exact version comes from read-only ProductVersion/FileVersion metadata of the
running `C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe`.
Viewport **390 × 844 CSS px**; content width 375 px plus 15 px vertical scrollbar.
Actor **uiux.wavec.buyer**, active, verified through `/accounts/settings/` in the
existing authenticated session. No new login credential, account or grant was
needed. Route:
`http://127.0.0.1:8000/procurement/rfqs/5bdf8343-48e3-4618-a13b-20afb06265e2/buyer/`.
Capture UTC timestamps are in [BROWSER.json](BROWSER.json); local date is
October 23, 2026, Asia/Tehran.

Expected: the retained RFQ is closed, its protected quote has already been
opened, the permitted populated comparison is reachable, actions disclose their
prerequisites, and mobile layout and runtime remain usable.

Actual: **PASS**. RFQ status is correctly **بسته‌شده** (closed), current version 1,
one registered quote. Quote opening is the retained immutable event proved by
prior evidence; the RFQ itself does not have an invented “opened” state.
`RV007-SYNTHETIC-LINE` remains prepared, with the authorized supplier/version,
**1499.50000000 IRR** and `page-1-synthetic-unit-price` visible. The operations
disclosure expands on mobile and presents the same permitted actions and explicit
prerequisite warning as the accepted desktop evidence. Keyboard traversal reaches
the evaluator action within the viewport; comparison preparation is reachable in
the same action list. No business action was submitted. Independent opening
approval and an unauthorized final award are not offered to this requester.

The authenticated actor has the existing exact confidential grant. The prior
service/HTTP authorization and isolation denials remain accepted and unchanged;
this closure does not repeat other identities or broaden confidential scope.
Collapsed and expanded layouts both have **one main**, no duplicate IDs and no
horizontal/page overflow (document/body width equals client width, 375 px).
Scrolling reaches the populated comparison and final history. **No console error**
was captured. Four Development Tailwind CDN production-use warnings were observed;
they do not invalidate this journey, and no Production readiness is inferred.
Temporary viewport override was reset successfully.

Evidence: [workspace viewport](opened_workspace_mobile.jpg),
[full workspace](opened_workspace_mobile_full.jpg),
[permitted actions](opened_actions_mobile.jpg),
[full expanded workspace](opened_actions_mobile_full.jpg),
[populated comparison](opened_comparison_mobile.jpg),
[actor identity](actor_identity.ax.txt), [browser observations](BROWSER.json).
The browser version page was blocked by the allowed-protocol policy; no bypass
was attempted. Local executable metadata supplies the version without a browser
protocol action. Two automation inspection/locator attempts failed before capture
(unsupported navigator inspection and summary role mismatch); the supported DOM
and observed summary ID completed verification. These were tool failures, with no
product/runtime error or product mutation.

## Integrity and retained regression debt

[INTEGRITY.json](INTEGRITY.json) verifies no drift from the prior final business
snapshot and no changes throughout this browser journey. The original
`WAVE-C-RFQ-A`, synthetic RFQ/quote/opening/comparison, business rules, authorization
architecture, default roles, schema/migrations, source/configuration, Git HEAD and
index remain unchanged. Prior artifact hashes all match; the two prior test fixes
match their retained exact source diff. Development migration plan is empty.
No Production connection or action occurred. Normal existing server port 8000 was
used; no temporary clock server, application clock patch or OS clock change was
needed. No new RFQ or business fixture was created.

Accepted prior validation is retained: **focused 9 PASS**; affected regression
**34 PASS, 18 baseline FAIL, 21 subtests PASS**. Of the original 27 failures,
**9 attributable are fixed; 18 are BASELINE_PREEXISTING; 0 are INDETERMINATE;
0 attributable remain unresolved**. The 18 failures are not reclassified or
silently remediated. Earlier separately attributed baseline debt remains explicit
in [the prior Wave C attribution](../wave_c_final_closure/REGRESSION_ATTRIBUTION.json).
No new attributable or indeterminate issue was discovered. No regression rerun
was warranted because this closure changed evidence/documents only and verified
no material source, schema, configuration or business-data drift.

## Reconciliation and stop

[Final matrix](WAVE_C_MATRIX.json) supersedes current Wave C disposition only.
The canonical results and Wave C report point to this closure; prior sections
remain historical. RV-018 official statutory success remains outside Wave C
certification under D03. Completion does not accept or erase baseline debt.

Wave D, Wave E, CEP-078, CEP-079, Production deployment/certification/cutover,
Human Sign-off, unrelated remediation, Git add/commit/push/merge/reset/clean/stash
and branch/worktree creation: **NOT EXECUTED**. CEP Registry and Roadmap unchanged.
No Product Decision expansion. **STOP.**
"""
(OUT / "COMPLETION_REPORT.md").write_text(report, encoding="utf-8")
results = ROOT / "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_RESULTS.yaml"
with results.open("a", encoding="utf-8") as stream:
    stream.write("""
wave_c_final_browser_closure:
  recorded_on: '2026-10-23'
  decision: WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT
  RV-007: PASS
  report: rv007_mobile_closure/COMPLETION_REPORT.md
  matrix: rv007_mobile_closure/WAVE_C_MATRIX.json
  browser: rv007_mobile_closure/BROWSER.json
  integrity: rv007_mobile_closure/INTEGRITY.json
  supersedes_current_disposition: rv007_controlled_time
  prior_historical_evidence: PRESERVED_UNCHANGED
  authenticated_mobile_opened_workspace: PASS
  browser_version: Google Chrome 155.0.8059.82
  viewport: 390x844
  actor: uiux.wavec.buyer
  pass_count: 12
  blocked_environment_count: 0
  pending_real_time_count: 0
  full_required_execution_complete: true
  wave_closed: true
  original_27_classification:
    ATTRIBUTABLE_REGRESSION: 9
    BASELINE_PREEXISTING: 18
    INDETERMINATE: 0
  unresolved_attributable_regressions: 0
  new_attributable_or_indeterminate_issues: 0
  regression_attribution: rv007_controlled_time/REGRESSION_ATTRIBUTION.json
  focused_prior_evidence: 9 PASS
  affected_prior_evidence: 34 PASS; 18 baseline FAIL; 21 subtests PASS
  prior_baseline_debt: wave_c_final_closure/REGRESSION_ATTRIBUTION.json
  regression_rerun: NOT_REQUIRED; evidence-only closure with no material drift
  statutory_success: OUT_OF_WAVE_C_CERTIFICATION_UNDER_D03
  retained_rfq_business_rules_authorization_default_roles_schema: UNCHANGED
  CEP_registry_and_roadmap: UNCHANGED
  production_and_human_signoff: NOT_EXECUTED
  wave_d_wave_e_cep078079: NOT_EXECUTED
  git_writes_branch_worktree: NOT_EXECUTED
  next_action: STOP
""")
wave_report = ROOT / "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md"
current_notice = """> Current Wave C disposition — 2026-10-23: **WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT**.
> **RV-007 PASS; 12/12 scenarios PASS; 18 pre-existing baseline failures retained.**
> [Final closure](rv007_mobile_closure/COMPLETION_REPORT.md) · [final matrix](rv007_mobile_closure/WAVE_C_MATRIX.json).
> Earlier sections below preserve historical attempts and their then-current blockers.

"""
wave_report.write_text(current_notice + wave_report.read_text(encoding="utf-8") + """

## Final mobile browser reconciliation — 2026-10-23

**WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT. RV-007 = PASS.**
The retained opened-quote workspace passes authenticated mobile verification in
Google Chrome 155.0.8059.82 at 390 × 844 as `uiux.wavec.buyer`. Correct closed RFQ
stage, populated authorized comparison, reachable permitted operations, one main,
no overflow/duplicate IDs and no console error are evidenced. All 12 current
scenario dispositions PASS. **18 BASELINE_PREEXISTING failures remain debt**;
9 attributable failures are fixed, 0 indeterminate and 0 unresolved attributable.
Prior focused 9 PASS and affected 34 PASS / 18 baseline FAIL / 21 subtests PASS
are retained, without an unnecessary browser-only regression rerun. Original RFQ,
business data/rules, authorization/default roles, source, migrations and Production
are unchanged. Earlier evidence and earlier baseline debt are preserved.
[Final report](rv007_mobile_closure/COMPLETION_REPORT.md),
[matrix](rv007_mobile_closure/WAVE_C_MATRIX.json),
[browser evidence](rv007_mobile_closure/BROWSER.json),
[integrity](rv007_mobile_closure/INTEGRITY.json).
Wave D/E, CEP-078/079, Production actions, Human Sign-off, Git writes and
branch/worktree creation: **NOT EXECUTED**. **STOP.**
""", encoding="utf-8")
findings = ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
with findings.open("a", encoding="utf-8") as stream:
    stream.write("""
wave_c_final_browser_reconciliation:
  recorded_on: '2026-10-23'
  decision: WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT
  RV-007: PASS
  report: rv007_mobile_closure/COMPLETION_REPORT.md
  UIUX_F008_F009: Final authenticated mobile opened-workspace evidence PASS; prior desktop/mobile comparison evidence retained
  full_wave_closed: true
  prior_closed_findings_and_historical_evidence: PRESERVED
  baseline_preexisting_failures_retained: 18
  prior_baseline_debt: wave_c_final_closure/REGRESSION_ATTRIBUTION.json
  unresolved_attributable_regressions: 0
  indeterminate_regressions: 0
  new_product_defects: 0
  next_action: STOP
""")
save("FINAL_VERIFICATION.json", {
    "decision": decision, "rv007": "PASS", "pass_count": 12,
    "baseline_preexisting_failures_retained": 18,
    "unresolved_attributable_regressions": 0, "indeterminate": 0,
    "browser_gap_closed": True, "product_mutations": 0,
    "prior_evidence_preserved": True, "next_action": "STOP",
})
print(decision + "; RV-007 PASS; 12/12; 18 baseline failures retained; STOP")
