# BONIRA shared defect register

[Editable defect register](DEFECT_REGISTER.csv)

There are zero Phase A runtime defects recorded. Prior issues remain in their source registers and are mapped in [Coverage and gaps](COVERAGE_AND_GAPS_REPORT.md). Enter a new defect only after observing an outcome or independently reproducing a historical item.

Use `BON-DEF-0001` onward. Link journey, step and inventory row, page/URL and method, scenario persona and fixture keys, baseline and reproducible sequence. Capture expected vs actual state and side effects, screenshots/video, technical witness and impacted module. Redact all credentials and protected values. Link any historical finding and distinguish recurrence from a new issue.

| Severity | Criterion |
|---|---|
| P0 | Cross-tenant data or write, privilege escalation, sensitive credential disclosure, material corruption or loss of immutable evidence, or broad critical outage. |
| P1 | Core journey/approval unusable, incorrect critical calculation, blocked eligible role with no workaround or material duplicate business transaction. |
| P2 | Contained behavior or usability issue with viable workaround; significant responsive/accessibility or reporting issue with limited impact. |
| P3 | Minor presentation, terminology or inconvenience without material workflow, data or authorization impact. |

Track `OPEN`, `TRIAGED`, `FIXED` and `RETESTED` in their respective fields. FIXED requires an identified change; RETESTED requires independent results and a baseline including the change. A failed retest returns the defect to OPEN and records the attempt. `PO_ACCEPTED` requires a separate named and dated decision. Phase A records observations only. Keep the defect open when a fix or explicit disposition is still pending.

## Wave 01 confirmed findings

| Defect | Scenario | Classification | Severity | Finding |
|---|---|---|---|---|
| BON-DEF-0001 | PA-08 | DESIGN_NONCONFORMANCE | P2 | Company chooser exposes a redundant unnamed combobox. |
| BON-DEF-0002 | PA-10 | USABILITY_DEFECT | P2 | Audit date fields say Gregorian but use Jalali input. |
| BON-DEF-0003 | PA-09 | DESIGN_NONCONFORMANCE | P2 | Retiring an active global protected-operation version takes effect without confirmation. |

The [editable register](DEFECT_REGISTER.csv) records actual evidence, exact reproduction, expected behavior and proposed minimal fixes. Their original Wave 01 outcomes are preserved. Current fix and retest status is recorded below.

## Wave 02 confirmed findings

| Defect | Scenario | Classification | Severity | Finding |
|---|---|---|---|---|
| BON-DEF-0004 | UAT-04 | BUSINESS_LOGIC | P1 | Time entry persists wall time as UTC |
| BON-DEF-0005 | CV-TIME-01 | BUSINESS_LOGIC | P1 | Approval permits overlapping finalized attendance |
| BON-DEF-0006 | CV-TIME-01 | AUTHORIZATION | P2 | Correction form reveals ungranted record existence |
| BON-DEF-0007 | UAT-02 | FUNCTIONAL | P1 | WBS child rejected for a valid parent |
| BON-DEF-0008 | UAT-04 | NAVIGATION_UX | P2 | Ending assignment loses list context |
| BON-DEF-0009 | CV-TIME-01 | NAVIGATION_UX | P2 | Approved correction omits replacement link |
| BON-DEF-0010 | UAT-02 | NAVIGATION_UX | P2 | Project hub links to a denied Controls page |

UIUX-F-018 remains observable on the Projects list. The existing historical ID is retained in the Wave 02 matrix.
See the [original B02 execution report](execution/B02_PROJECT_WORKFORCE_TIMEKEEPING_REPORT.md) for reproduction and evidence. All seven defects were OPEN at Wave 02 closeout. Their later dispositions are recorded below.


## Wave 01 bounded remediation · 2026-11-10

| Defect | Fix status | Independent retest | PO acceptance |
|---|---|---|---|
| BON-DEF-0001 | FIXED | RETESTED_PASS | NOT_RECORDED |
| BON-DEF-0002 | FIXED | RETESTED_PASS | NOT_RECORDED |
| BON-DEF-0003 | FIXED | RETESTED_PASS | NOT_RECORDED |

The [remediation report](execution/WAVE_01_UX_REMEDIATION_REPORT.md) and its browser/state evidence record current results. Severity remains P2 for all three. The original Wave 01 matrices and reports retain the historical FAIL outcomes. Unrelated Wave 02 findings and unexecuted cases retain their existing status.

UX-R-OBS-01 is an additional audit-filter observation for review. Invalid date input fails closed, but the automatic GET refresh redisplays an empty field while retaining the invalid query in the URL. The report records its evidence and a proposed bounded correction. The date-label fix preserves this existing filtering behavior.

## B02 targeted remediation · 2026-11-11

| Defect | Severity | Fix status | Retest | PO acceptance |
|---|---|---|---|---|
| BON-DEF-0004 | P1 | FIXED | RETESTED_PASS | NOT_RECORDED |
| BON-DEF-0005 | P1 | FIXED | RETESTED_PASS | NOT_RECORDED |
| BON-DEF-0006 | P2 | FIXED | RETESTED_PASS | NOT_RECORDED |
| BON-DEF-0007 | P1 | FIXED | RETESTED_PASS | NOT_RECORDED |
| BON-DEF-0008 | P2 | FIXED | RETESTED_PASS | NOT_RECORDED |
| BON-DEF-0009 | P2 | FIXED | RETESTED_PASS | NOT_RECORDED |
| BON-DEF-0010 | P2 | FIXED | RETESTED_PASS | NOT_RECORDED |

The [remediation report](execution/B02_REMEDIATION_REPORT.md), [corrected baseline](execution/evidence/b02-remediation-20261110/CORRECTED_BASELINE.json), and [execution retest overlay](execution/B02_REMEDIATION_RETEST.csv) record current evidence. The original execution matrix remains unchanged. UIUX-F-018 passed its Projects-specific correction; the independent Projects visual reference is still pending. The five original blocked operator paths retain `BLOCKED` and have specific Product Owner decisions in the report.

## B03 Daily Reports and Field Operations · 2026-11-11

| Defect | Severity | Finding | Fix and retest |
|---|---|---|---|
| BON-DEF-0011 | P1 | Granted site actors denied Field Operations | FIXED / RETESTED_PASS |
| BON-DEF-0012 | P1 | Field and proposal wall times persisted in UTC and disappeared on re-render | FIXED / RETESTED_PASS |
| BON-DEF-0013 | P1 | Stale draft overwrote newer revision and exact replay returned an error | FIXED / RETESTED_PASS |
| BON-DEF-0014 | P1 | Capture-only editor received precise location | FIXED / RETESTED_PASS |
| BON-DEF-0015 | P1 | Scoped workflow candidate denied Daily Report approval | FIXED / RETESTED_PASS |
| BON-DEF-0016 | P2 | Missing Field entry and report context links | FIXED / RETESTED_PASS |
| BON-DEF-0017 | P1 | Daily Report self-approval and missing Return branch | NEEDS_PO_REVIEW / RETESTED_FAIL |
| BON-DEF-0018 | P1 | Identical valid labor POST appended a duplicate | NEEDS_PO_REVIEW / RETESTED_FAIL |
| BON-DEF-0019 | P2 | Proposal review has no operator control | NEEDS_PO_REVIEW / BLOCKED |
| BON-DEF-0020 | P2 | Field labels, timestamps and review feedback missed localization standards | FIXED / RETESTED_PASS |
| BON-DEF-0021 | P2 | Five inline forms dropped valid values on error | FIXED / RETESTED_PASS |

The original B03 outcomes are retained in the MVP matrix. Post-remediation results and all pending PO decisions are recorded separately. [B03 report](execution/B03_DAILY_REPORTS_FIELD_OPERATIONS_REPORT.md) · [Row outcomes](execution/evidence/wave-03-865fa3f3/row-outcomes.csv)

## B03 final remediation · 2026-11-12

| Defect | Fix status | Retest | Residual blocker |
|---|---|---|---|
| BON-DEF-0017 | PARTIALLY_FIXED | Self-approval/independent approval PASS; overall BLOCKED | Existing contracts have no safe Return/edit/resubmit branch. NEEDS_PO_REVIEW for a separately bounded correction contract. |
| BON-DEF-0018 | FIXED | RETESTED_PASS | None. |
| BON-DEF-0019 | FIXED | RETESTED_PASS | None. |

The user's final-remediation instruction explicitly authorizes MVP separation, logical-request labor idempotency and contextual proposal review. Formal PO acceptance remains NOT_RECORDED. Original reproduction, prior results and blocked Return are preserved separately in the [final report](execution/B03_FINAL_REMEDIATION_REPORT.md) and [22-row latest overlay](execution/B03_FINAL_REMEDIATION_RETEST.csv). Original B03 tables above are historical. Wave 01/B02 results and the five B02 blocked rows are unchanged. This task did not start B04.


## B04 Equipment, Safety, Quality and Expenses · 2026-11-12

| Defect | Severity | Finding | Fix and retest |
|---|---|---|---|
| BON-DEF-0022 | P1 | Equipment and HSEQ wall times persisted with UTC offset; expense history also displayed in server zone. | FIXED / RETESTED_PASS |
| BON-DEF-0023 | P1 | Equipment cost policy create returns HTTP 500. | FIXED / RETESTED_PASS |
| BON-DEF-0024 | P2 | Invalid equipment operation returns server error and loses usable form. | FIXED / RETESTED_PASS |
| BON-DEF-0025 | P2 | Expense coding selectors expose model class names and UUIDs. | FIXED / RETESTED_PASS |
| BON-DEF-0026 | P1 | Safety/Quality record decision has no MVP operator route, blocking governed closure. | NEEDS_PO_REVIEW / BLOCKED |
| BON-DEF-0027 | P1 | Usage accepts excessive runtime and an overlapping interval for the same asset. | NEEDS_PO_REVIEW / RETESTED_FAIL |
| BON-DEF-0028 | P2 | Browser-created usage lacks deployment/operator linkage needed for equipment-cost handoff. | NEEDS_PO_REVIEW / BLOCKED |

Original MVP outcomes remain separate from the [B04 retest overlay](execution/B04_RETEST_RESULTS.csv). [Execution report](execution/B04_EXECUTION_REPORT.md) contains the prerequisites, limits and pending PO decisions. Earlier-wave records and decisions were preserved.
