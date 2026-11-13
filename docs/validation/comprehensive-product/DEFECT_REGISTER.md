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


## B04 final remediation · 2026-11-12

| Defect | Current disposition | Retest evidence |
|---|---|---|
| BON-DEF-0026 | FIXED / RETESTED_PASS | Independent Safety and Quality approval, return, correction, rejection, evidence and governed closure. |
| BON-DEF-0027 | FIXED / RETESTED_PASS | Runtime cap, overlap rejection, adjacent intervals and exact/concurrent replay. |
| BON-DEF-0028 | FIXED / RETESTED_PASS | Chrome-created usage through active deployment and optional qualified operator to independently reviewed cost handoff. |

The final overlay records 66 PASS. Formal PO acceptance is pending. The B04 table above remains the historical checkpoint. [Final report](execution/B04_REMEDIATION_REPORT.md) · [Final row overlay](execution/B04_FINAL_REMEDIATION_RETEST.csv)

## B03 Return implementation · 2026-11-12

| Defect | Fix | Retest | PO acceptance |
|---|---|---|---|
| BON-DEF-0017 | FIXED | RETESTED_PASS | NOT_RECORDED |

The linked-revision Return/correction/resubmission journey passed PostgreSQL and Chrome qualification. The [implementation report](execution/B03_RETURN_IMPLEMENTATION_REPORT.md) and [new B03 overlay](execution/B03_RETURN_IMPLEMENTATION_RETEST.csv) record 22 PASS / 0 FAIL / 0 BLOCKED. Earlier results remain historical. This task stopped after B03.

## B05 Estimates, Contracts, Billing and Claims · 2026-11-12

| Defect | Severity | Finding | Disposition |
|---|---|---|---|
| BON-DEF-0029 | P2 | Invalid estimate quantity clears the line form. | FIXED / Chrome retest passed |
| BON-DEF-0030 | P2 | Payable measurement exposes the contract item UUID. | FIXED / RETESTED_PASS at 1440, 1024 and 390 px |
| BON-DEF-0031 | P3 | Estimate unit price and line total repeat the currency label. | FIXED / RETESTED_PASS at 1440, 1024 and 390 px |
| BON-DEF-0032 | P1 | Guarantee and compliance successor detail returns HTTP 500. | FIXED / RETESTED_PASS for both detail pages at all three widths and for new Chrome renewal submissions |
| BON-DEF-0033 | P2 | The catalog expects automatic conversion of an unlinked estimate. | PO scope disposition approved. Standalone creation and existing associations passed. Automatic conversion is deferred to post-MVP. |
| BON-DEF-0034 | P2 | The receivable measurement compatibility starter permits self-verification. | FIXED / RETESTED_PASS in two-user Chrome and PostgreSQL. The PO approved mandatory MVP separation. |

[B05 closeout](execution/B05_CLOSEOUT_REPORT.md) · [Final row outcomes](execution/B05_FINAL_RETEST.csv) · [B05 execution and reproduction evidence](execution/B05_EXECUTION_REPORT.md) · [Original outcomes](execution/B05_ORIGINAL_RESULTS.csv) · [Current outcomes](TEST_EXECUTION_MATRIX_MVP.csv)


## B06 Procurement, Materials and Inventory · 2026-11-12

| Defect | Severity | Finding | Current disposition |
|---|---|---|---|
| BON-DEF-0035 | P1 | Atomic reservation creation | FIXED / RETESTED_PASS |
| BON-DEF-0036 | P1 | Atomic stock count submission | FIXED / RETESTED_PASS |
| BON-DEF-0037 | P1 | Destination-project transfer access | FIXED / RETESTED_PASS |
| BON-DEF-0038 | P2 | Searchable custody selectors | FIXED / RETESTED_PASS |
| BON-DEF-0039 | P2 | Supplier invitation search | FIXED / RETESTED_PASS |

[Execution report](execution/B06_EXECUTION_REPORT.md) · [Original outcomes](execution/B06_ORIGINAL_RESULTS.csv) · [Current MVP results](TEST_EXECUTION_MATRIX_MVP.csv)


## B07 Tenant Isolation, Workflows and Parties · 2026-11-12

| Defect | Severity | Finding | Current disposition |
|---|---|---|---|
| BON-DEF-0040 | P1 | Member status form | FIXED / RETESTED_PASS |
| BON-DEF-0041 | P2 | Authorization observer controls | FIXED / RETESTED_PASS |
| BON-DEF-0042 | P1 | Invalid temporary password confirmation | FIXED / RETESTED_PASS |
| BON-DEF-0043 | P1 | Unknown connection decision | FIXED / RETESTED_PASS |
| BON-DEF-0044 | P2 | Material governance context | FIXED / RETESTED_PASS |
| BON-DEF-0045 | P2 | Protected canonical Party archive | FIXED / RETESTED_PASS |
| BON-DEF-0046 | P3 | Repeated Party management entry | FIXED / RETESTED_PASS |
| BON-DEF-0047 | P2 | Existing supplier selection | FIXED / RETESTED_PASS |
| BON-DEF-0048 | P2 | Cartable purchase-request rejection | FIXED / RETESTED_PASS |

Nine defects have bounded fixes and independent Chrome and PostgreSQL retests. The tenant and workflow guards retained denial behavior. Formal PO acceptance remains unrecorded. [B07 execution report](execution/B07_EXECUTION_REPORT.md) · [Original outcomes](execution/B07_ORIGINAL_RESULTS.csv) · [Current MVP matrix](TEST_EXECUTION_MATRIX_MVP.csv)


### B07 expiry qualification · 2026-11-13

| Defect | Severity | Finding | Current disposition |
|---|---|---|---|
| BON-DEF-0049 | P2 | Role and scope expiry used plain datetime inputs | FIXED / RETESTED_PASS |

The final B07 total is ten fixed defects. Chrome submitted a Jalali expiry through both forms and independently verified equal timezone-aware stored values and two authorized audit events. [Original observation](execution/evidence/b07-24ad220f/original-expiry/supplemental.json) · [Retest](execution/evidence/b07-24ad220f/retest-expiry/supplemental.json)


## B08 Excel exports, print, reporting and audit · 2026-11-13

| Defect | Severity | Finding | Current disposition |
|---|---|---|---|
| BON-DEF-0050 | P2 | Reporting timestamps used UTC and showed the previous Jalali day around Tehran midnight. | FIXED / RETESTED_PASS |

The dashboard now renders timestamps in the configured organization timezone. The same retained metric sources and values reconciled after the fix. [Original screenshot](execution/evidence/b08-24ad220f/retest/reporting-dashboard-390.png) · [Independent Chrome retest](execution/evidence/b08-24ad220f/retest/dashboard-final/rows.json) · [Execution report](execution/B08_EXECUTION_REPORT.md)

## B10 Platform Admin · 2026-11-13

| Finding | Severity | Current disposition |
|---|---|---|
| BON-DEF-0001–0003 | P2 | Existing fixes passed current Chrome retests. |
| UX-R-OBS-01 | Observation | The Wave 01 correction passed current Chrome retest. Invalid Jalali input remains visible with validation. |
| BON-DEF-0051 | P2 | FIXED / RETESTED_PASS. Policy draft redisplays and preserves its saved source basis. |
| BON-DEF-0052 | P1 | FIXED / RETESTED_PASS. Stale policy draft edits and publication attempts preserve the newer draft. |
| BON-DEF-0053 | P1 | FIXED / RETESTED_PASS. Retirement replay cannot retire a different protected-operation version. |

Formal PO acceptance remains unrecorded. [B10 report](execution/B10_FINAL_EXECUTION_REPORT.md) · [Original reproductions](execution/evidence/b10-24ad220f/reproduce-focused.log) · [Chrome catalog retests](execution/evidence/b10-24ad220f/catalog/browser-results.json)

## B09 Documents and Cross-Module Evidence · 2026-11-13

| Defect | Severity | Finding | Disposition |
|---|---|---|---|
| BON-DEF-0054 | P2 | Standalone document expiry calendar | RETESTED_PASS |
| BON-DEF-0055 | P1 | Employee document routes inherit MVP exposure | RETESTED_PASS |
| BON-DEF-0056 | P1 | Contractual record creation returns HTTP 500 | RETESTED_PASS |
| BON-DEF-0057 | P1 | Exact contractual evidence retry duplicates the link and audit | RETESTED_PASS |
| BON-DEF-0058 | P2 | Contractual stale or invalid action lacks controlled feedback | RETESTED_PASS |
| BON-DEF-0059 | P2 | Standalone document forms display a hidden Treasury target | RETESTED_PASS |
| BON-DEF-0060 | P2 | Guarantee correction loses its inherited expiry date | RETESTED_PASS |
| BON-DEF-0061 | P2 | Document detail omits a configured access deadline | RETESTED_PASS |

[Execution report](execution/B09_EXECUTION_REPORT.md) · [Original outcomes](execution/B09_ORIGINAL_RESULTS.csv) · [Retest outcomes](execution/B09_FINAL_RETEST.csv)

## B11 final UI/UX conformance · 2026-11-13

| Finding | Severity | Independently observed disposition |
|---|---|---|
| BON-DEF-0062 | P2 | FIXED / RETESTED_PASS. Supplier deadlines and receipt times use the authorized organization timezone and Jalali display. Receipt identity is preserved. |
| BON-DEF-0063 | P2 | FIXED / RETESTED_PASS. Equipment Category has one enhanced accessible control. Native labels are restored on cleanup for Equipment and the Platform tenant selector. Related mechanism BON-DEF-0001. |
| BON-DEF-0064 | P2 | FIXED / RETESTED_PASS. Two populated Billing selectors use business labels. Queryset/tenant scope and invalid-input retention remain enforced. |

[Original findings](execution/evidence/b11-24ad220f/labels-before.json) · [Portal original](execution/evidence/b11-24ad220f/portal-before.json) · [Independent label retest](execution/evidence/b11-24ad220f/labels-after.json) · [Portal retest](execution/evidence/b11-24ad220f/portal-after.json) · [Lifecycle and scope regression](execution/evidence/b11-24ad220f/exact-regression.json) · [B11 report](execution/B11_EXECUTION_REPORT.md)

The supplier receipt UUID and privileged audit source identifiers retain their documented contexts. Native Chrome file-picker text is browser UI. No new PO acceptance is recorded. Statutory positive-detail blockers and legacy test debt remain separate from these corrected UI defects.
