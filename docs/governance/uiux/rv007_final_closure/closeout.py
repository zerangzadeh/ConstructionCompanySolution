"""Record truthful blocked RV-007 closure; preserve historical/current CEP state."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
os.environ["GIT_OPTIONAL_LOCKS"] = "0"


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, default=str, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


entry, proof = read("ENTRY.json"), read("FEASIBILITY.json")
assert proof["procurement_all_model_fingerprints_unchanged"]
assert not proof["synthetic_rfq_retained"]
source_changes = [p for p, h in entry["source_hashes"].items() if not (ROOT / p).is_file() or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
assert not source_changes, source_changes
assert hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest() == entry["index_sha256"]
assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() == entry["head"]
tests = {}
for kind in ("focused", "affected"):
    tree = ET.parse(OUT / (kind + ".xml"))
    suites = tree.findall(".//testsuite")
    tests[kind] = {k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
    tests[kind]["failed_cases"] = [{"test": case.get("classname") + "." + case.get("name"), "message": case.find("failure").get("message")} for case in tree.findall(".//testcase") if case.find("failure") is not None]
    tests[kind]["pytest_summary"] = (OUT / (kind + ".txt")).read_text(encoding="utf-8").strip().splitlines()[-1]
assert not tests["focused"]["errors"] and not tests["affected"]["errors"]
checks = (OUT / "django_check.txt").read_text(encoding="utf-8")
assert "System check identified no issues" in checks
save("VALIDATION.json", {"tests": tests, "system_check": "PASS", "product_source_changes": source_changes,
    "git_head_and_index_unchanged": True, "new_business_rows_retained": 0,
    "scope": "Focused opening and affected RFQ/quotes/custody/admissibility/comparison/buyer-action regression; not full repository regression",
    "isolated_test_fixture_time_is_not_live_runtime_evidence": True,
    "prior_baseline_debt": "../wave_c_final_closure/REGRESSION_ATTRIBUTION.json",
    "additional_failure_classification": "UTV: unchanged session-entry source; failures precede intended assertions; historical Wave C attribution not established; not accepted as baseline",
    "production": "UNTOUCHED", "git_writes": "NOT_EXECUTED"})
blocked = "BLOCKED_CANONICAL_TEMPORAL_PREREQUISITE"
requirements = [
    ("protected opening", blocked),
    ("independent opening/approval duties", "Existing separate actors and exact project permissions verified; positive live lifecycle BLOCKED"),
    ("confidential comparison access", blocked),
    ("unauthorized same-tenant denial", "Isolated regression only; requested new live fixture BLOCKED"),
    ("site-only denial", "Requested live fixture NOT EXECUTED"),
    ("cross-tenant denial", "Isolated regression only; requested new live fixture BLOCKED"),
    ("manipulated-action denial", "Isolated regression only; requested new live fixture BLOCKED"),
    ("source/hash/scan integrity", "Custody unreachable for late revision; no fabricated source/custody/scan verdict"),
    ("stage/next-action UI", "Isolated regression only; requested opened live fixture BLOCKED"),
    ("authenticated desktop/mobile browser", "NOT EXECUTED for requested positive lifecycle; diagnostic Chrome tab reached login and was closed"),
]
matrix = json.loads((OUT.parent / "wave_c_final_closure/WAVE_C_FINAL_MATRIX.json").read_text(encoding="utf-8"))
matrix.update({"decision": "WAVE_C_BLOCKED", "recorded_at": proof["recorded_at"], "RV007_final_attempt": blocked,
    "pass_count": 11, "pending_real_time_count": 1, "full_required_execution_complete": False, "wave_closed": False,
    "unresolved_attributable_regressions": None, "additional_failures_pending_historical_attribution": tests["affected"]["failures"],
    "requirements": [{"requirement": k, "result": v} for k, v in requirements],
    "no_wave_c_completion_issued": True})
for row in matrix["scenario_results"]:
    if row["scenario_id"] == "RV-007":
        row.update({"result": blocked, "coverage": "Real-clock canonical rollback probe proves newly past-close RFQ cannot acquire effective submitted quote. Retained RFQ early close/opening denied and preserved.", "evidence": "FEASIBILITY.json"})
    else:
        row["evidence"] = "../wave_c_final_closure/" + row["evidence"]
save("RV007_MATRIX.json", matrix)
sources = ["apps/procurement/quote_services.py", "apps/procurement/rfq_services.py", "apps/procurement/custody_services.py", "apps/procurement/opening_services.py", "apps/procurement/portal_services.py"]
save("CANONICAL_PATHS.json", {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources})
report = f"""# RV-007 Final Closure — 2026-10-23

**EXECUTION PARTIAL. RV-007: {blocked}.**
Current Wave C result: **WAVE_C_BLOCKED** (11 prior scenario results retained;
RV-007 unresolved and additional regression attribution UTV).
`WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT` is not issued.

## Authority and bounded execution

Human request: current Development only; one synthetic past-close RFQ through
canonical services, 24 hours from close to allowed opening, no direct database
fabrication/authorization bypass, retained RFQ unchanged, no Production/Git,
no Wave D or CEP-078/079. Repository main/HEAD `{entry['head']}` and origin/main
match. Existing dirty source is preserved. Touch set is this evidence directory
and append-only result/report reconciliation. No product source, schema, migration,
dependency, permission, scope, policy, production or CEP lifecycle change.

## Canonical blocker and reproduction

`capture_quote_revision` assigns server `received_at=timezone.now()` and marks
receipt after close `is_late=True` (quote_services.py:165–180).
`submit_quote_revision` rejects server time after version close (line 254).
Backdating the supplied `supplier_submitted_at` does not replace receipt time.
The manifest requires SUBMITTED, not late, and both receipt/submission at or
before close (rfq_services.py:177–193). Custody requires that effective submitted
manifest entry (custody_services.py:289–315); opening also requires it
(opening_services.py:178–211). The portal rejects after close too
(portal_services.py:389–391,523–524). No canonical retrospective quote-import
path was found in Procurement services or management commands. The existing
workflow backfill imports Purchase Request workflow history, not RFQ quotes.

The [real Development probe](FEASIBILITY.json) uses existing authorized tenant,
project, approved Purchase Request, supplier and independent specialists. It
creates and issues exactly one synthetic RFQ **inside a transaction that is
rolled back**: close 25 hours ago, earliest opening 24 hours after close (one hour
ago). It captures a SHA-256 of benign synthetic bytes without representing them
as custodial/scan evidence. Canonical submission fails with the explicit
after-deadline error; close records `no_effective_submission`; opening is denied.
The entire probe rolls back, including its audits. **No new RFQ is retained.**
The initial probe also rolled back after a source-reference format validation
error; the final probe uses a valid technical source reference.

A compliant retained fixture cannot be completed now with these services.
Completing it requires a separately governed canonical historical-import path,
or an on-time submitted fixture followed by the real close and 24-hour wait.
Neither a clock patch nor direct date/state writes were used. No permission was
granted, no authorization check was bypassed, and no CLEAN verdict was fabricated.

## Retained evidence and runtime limits

The retained `WAVE-C-RFQ-A` remains issued, close **October 24, 2026 14:46:11 Tehran**,
earliest opening **October 25, 2026 14:46:11 Tehran**; the gap is exactly 24 hours.
Its real early close and opening attempts were denied in rollback transactions.
The opening denial first reaches the missing closed/effective manifest guard;
it is **not isolated live proof of the later 24-hour guard**. The opening unit
suite separately exercises the earliest-opening boundary in its test database.
All Procurement model fingerprints match before/after; retained row hash matches.

The [ten-requirement matrix](RV007_MATRIX.json) distinguishes isolated tests from
live evidence. Positive opening/independent approval/confidential comparison,
valid source/custody/scan and opened-stage desktop/mobile verification remain
unexecuted. New-fixture live same-tenant/site/cross-tenant/manipulated-action
controls are not claimed PASS. A diagnostic Chrome tab reached the login page
and was closed without altering authentication. No authenticated desktop/mobile
success is claimed and no UI success was inferred from HTTP or unit tests.

## Validation and integrity

Focused: **{tests['focused']['pytest_summary']}**.
Affected: **{tests['affected']['pytest_summary']}**.
See [focused output](focused.txt), [affected output](affected.txt), JUnit XML and
[validation](VALIDATION.json) for actual coverage/failure details. These are
isolated test-database runs, not the requested populated live Development journey.
Django checks PASS. No schema change; Development migration plan is empty.
All entry product-source fingerprints and Git HEAD/index hashes are unchanged.
The prior accepted [baseline attribution](../wave_c_final_closure/REGRESSION_ATTRIBUTION.json)
remains explicit; full-repository regression is not claimed green. The additional
27 failures occur before intended assertions: one duplicate active role assignment,
18 shared opening-approver setup denials and eight shared buyer setup close denials.
Product source matches this session's entry, but that does not prove these
broader failures are unrelated to earlier Wave C source changes. Their historical
attribution is **UTV**, not accepted baseline debt and not a passing regression.
No unrelated test repair or permission weakening was performed. The earlier
zero-unresolved-regression claim covered a smaller selection and is not extended
to this broader result.

CEP Registry/roadmap/previous closed findings remain unchanged. Human Sign-off,
Production Certification/Cutover, Wave D, CEP-078/079, branch/worktree creation,
Git add/commit/push/merge: **NOT EXECUTED**. Production: **UNTOUCHED**.

**STOP.**
"""
(OUT / "COMPLETION_REPORT.md").write_text(report, encoding="utf-8")
results = ROOT / "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_RESULTS.yaml"
text = results.read_text(encoding="utf-8")
assert "\nrv007_final_closure_attempt:" not in text
text += f"""
rv007_final_closure_attempt:
  recorded_on: '2026-10-23'
  decision: WAVE_C_BLOCKED
  RV-007: BLOCKED_CANONICAL_TEMPORAL_PREREQUISITE
  report: rv007_final_closure/COMPLETION_REPORT.md
  proof: rv007_final_closure/FEASIBILITY.json
  matrix: rv007_final_closure/RV007_MATRIX.json
  validation: rv007_final_closure/VALIDATION.json
  synthetic_rfq_retained: false
  canonical_synthetic_probe: ROLLED_BACK; late submission denied; no effective submitted manifest entry
  retained_rfq: UNCHANGED; early close and opening denied
  pass_count: 11
  pending_real_time_count: 1
  full_required_execution_complete: false
  wave_closed: false
  requested_complete_with_explicit_baseline_debt: NOT_ISSUED
  additional_failure_attribution: UTV; not accepted baseline; earlier zero claim not extended
  additional_failure_count: {tests['affected']['failures']}
  focused: '{tests['focused']['tests']} tests / {tests['focused']['failures']} failures'
  affected: '{tests['affected']['tests']} tests / {tests['affected']['failures']} failures'
  product_source: UNCHANGED
  prior_baseline_debt: wave_c_final_closure/REGRESSION_ATTRIBUTION.json
  CEP_registry: UNCHANGED
  production: UNTOUCHED
  git_writes: NOT_EXECUTED
  wave_d_cep078079: NOT_EXECUTED
  next_action: STOP; canonical historical import or real on-time fixture maturation required
"""
results.write_text(text, encoding="utf-8")
wave_report = ROOT / "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md"
with wave_report.open("a", encoding="utf-8") as stream:
    stream.write("\n\n## RV-007 final closure attempt — 2026-10-23\n\n"
        "**WAVE_C_BLOCKED — RV-007 BLOCKED_CANONICAL_TEMPORAL_PREREQUISITE.** "
        "The real-clock canonical rollback probe proves a newly created past-close RFQ receives a late quote, "
        "cannot submit it, and has no opening-eligible manifest entry. No canonical retrospective quote-import "
        "path exists in the inspected Procurement services. No new RFQ is retained. The existing RFQ, all "
        "Procurement model fingerprints, product source and Git HEAD/index remain unchanged. "
        "Early close/opening denial is retained; the manifest guard precedes the separate opening-time guard.\n\n"
        f"Focused: **{tests['focused']['pytest_summary']}**. "
        f"Affected: **{tests['affected']['pytest_summary']}**. "
        "[Report](rv007_final_closure/COMPLETION_REPORT.md), "
        "[proof](rv007_final_closure/FEASIBILITY.json), "
        "[matrix](rv007_final_closure/RV007_MATRIX.json), "
        "[validation](rv007_final_closure/VALIDATION.json). Positive live opening/comparison/source-scan "
        "and authenticated desktop/mobile verification remain unexecuted. No completion status is issued. "
        "Prior baseline debt and 11 prior scenario results are preserved. The additional 27 fixture "
        "failures have historical attribution UTV; they are not accepted as baseline debt and the "
        "earlier zero-unresolved-regression claim is not extended to this broader selection. "
        "Production, Wave D, CEP-078/079, Human Sign-off and Git writes: **NOT_EXECUTED**. **STOP.**\n")
print(json.dumps(tests, indent=2))
print("Evidence reconciled; Wave C blocked; STOP.")
