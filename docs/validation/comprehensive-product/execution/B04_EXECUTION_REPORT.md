# B04 Equipment, Safety, Quality and Expenses

**12 November 2026 · Asia/Tehran · MVP · 66 planned execution IDs**

| Scenario | Planned | Original PASS | FAIL | BLOCKED | Current PASS | FAIL | BLOCKED |
|---|---:|---:|---:|---:|---:|---:|---:|
| UAT-05 | 20 | 18 | 2 | 0 | 19 | 1 | 0 |
| UAT-06 | 17 | 11 | 2 | 4 | 13 | 0 | 4 |
| CV-EQP-01 | 14 | 3 | 3 | 8 | 14 | 0 | 0 |
| CV-EXP-01 | 15 | 13 | 2 | 0 | 15 | 0 | 0 |
| **B04** | **66** | **45** | **9** | **12** | **61** | **1** | **4** |

**NOT_RUN: 0 at both stages. B04 is not acceptance-ready.** Seven confirmed defects/gaps were recorded; four bounded defects were fixed and independently retested. Two unresolved P1 findings and one P2 product decision remain. Formal PO acceptance is **NOT EXECUTED**.

The [MVP matrix](../TEST_EXECUTION_MATRIX_MVP.csv) records original outcomes. The [retest overlay](B04_RETEST_RESULTS.csv) retains the same 66 IDs and separate original/current results. The [planned baseline](evidence/wave-04-865fa3f3/planned-baseline.csv) preserves the original B04 planning rows. BLOCKED is a disposition, not a passed downstream assertion.

## Environment and boundaries

- Local `main`; HEAD and `origin/main` `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`. Existing dirty source, prior tests, PO-edited designs and concurrent changes were preserved. No branch/worktree, commit, push or CEP lifecycle update was performed. This wave uses the user's explicit bounded validation/remediation authority.
- A newly initialized PostgreSQL 18.6 loopback cluster held independent original/retest clones of the existing synthetic schema snapshot. Each runtime had **457 applied migrations, zero pending**, and explicitly ran `migrate`: no migrations to apply. The snapshot contained no users/tenants before synthetic seeding. Database name, port and data-directory guards precede fixture/server/witness operations. No existing Development/Production database was opened for writes.
- The original server retained pre-fix modules with reload disabled. Original and retest browser mutations used separate databases and private media/DMS roots. Google Chrome **156.0.8078.80** ran through Playwright with separate owner, independent reviewer, site-scoped reporter, sibling-site, restricted reader, foreign-tenant and expense maker/approver contexts. Requests were restricted to the task's loopback origin. ORM witnesses were read-only.
- Synthetic fixtures reuse B02 authorization utilities, the existing equipment stock-issue utility and the accepted-budget expense fixture. Equipment cost requires a **disclosed service-provisioned usage/deployment source**. Browser-created usage cannot supply that link through the present form. This is not an end-to-end browser handoff PASS.
- The first temporary location exhausted its drive while cloning. Only this wave's new cluster was stopped and relocated to the workspace drive. The isolated cluster later disabled durable-write settings to reduce historical migration overhead; no durability/crash-recovery assertion is made. A from-zero technical migration attempt was stopped at 387/457; it is not reported as a test PASS. See [technical evidence](evidence/wave-04-865fa3f3/technical.md).

[Run manifest](evidence/wave-04-865fa3f3/RUN_MANIFEST.md) · [Source/provenance hashes](evidence/wave-04-865fa3f3/baseline.json) · [Touch set](evidence/wave-04-865fa3f3/touch-set.md)

## Business and persisted-state results

| Journey | Observed result and limit |
|---|---|
| Equipment registration and allocation | Chrome created a tenant-owned asset and same-project/site assignment. A second overlapping assignment was rejected without another row. Authorized cancellation, retirement and archive persisted. There is no equipment edit route in this MVP surface; no new edit feature was added. |
| Meter and usage | Reading 100 → 103 persisted; an uncorrected decrease to 99 was rejected. A two-hour usage retained its source identity and Decimal runtime. Original local times stored with the wrong offset. Current input/storage/reload agree with Tehran. End-before-start now shows the domain error and retains safe fields with zero invalid writes. A separate overlapping **20.000-hour runtime in two elapsed hours was accepted** and remains FAIL. |
| Maintenance and operations | Browser-created maintenance, plan and work order followed available transitions. Evidence/reference and posted spare-issue linkage persisted without mutating inventory. Operator qualification, fuel quantity/unit and downtime persisted. Equipment work-order evidence is an existing reference field; it is not represented as an exact-version DMS pin. |
| Safety and Quality operations | Scoped reporters created correctly related records. Independent operational reviewers assigned responsibility and progressed Safety to resolved and Quality to verified. Readers and foreign/sibling-site actors were denied. These operational transitions do not approve the separate record-review lifecycle. |
| Separate record review and closure | The actual source-bound DMS action submitted each record with an exact version. The MVP has **no record approve/return/reject control or domain HTTP route**. The existing approved-record closure gate rejected close. Both final-state detail rows and close rows remain BLOCKED. Draft/resolved/verified/submitted details were inspected; approved/closed details were not claimed as executed. |
| Exact DMS custody | Foreign-version registration wrote no revision. The selected clean v1 remained pinned after Chrome uploaded v2; the v1 download hash matched custody and the reader without download permission got 403. The first pending-version probe demonstrated the existing, intentional rule: quarantined metadata may accompany Safety/Quality review, while delivery is denied. Corrected clean-v1 journeys use separate records; no quarantined probe was relabelled a product defect. |
| Cost policy and handoff | The original policy form returned 500 and blocked eight downstream rows. Retest created policy/rate in Chrome, independently reviewed/published, and computed **3.000 × 125000 = 375000 IRR**. Independent finalization and handoff review persisted. Repeating the same handoff retained one envelope. Reconciliation records the supplied reference only; it proves no destination Project Cost fact. |
| Cost reversal/source change | The finalizer's attempted reversal was correctly denied. A different authorized actor created one **−375000** reversal, marked the source reversed and retained the original amount/history. Exact reversal replay added no row/audit. The existing reconciled envelope retained its source snapshot. No accounting recognition or new financial correction path was introduced. |
| Expenses | Chrome exercised category create/list/detail/archive, legacy recorded expense, controlled draft, budget coding, submit, independent approval, return, void, recurrence and proposal. The two controlled expenses retained **125000** and **75000 IRR** and their allocation context. Self-approval and repeated approval were denied without extra audit. An exact replay of the browser's actual draft POST returned the same record. Missing CSRF returned 403. A contextual receipt upload returned to the same expense and created one typed document link. The expense displayed the receipt. Foreign upload/download and pending file delivery returned 403. A forged foreign document link returned 400 and wrote no link. [Receipt evidence](evidence/wave-04-865fa3f3/retest/receipt-closeout/results.json) |
| Financial/scope boundaries | Forty-nine restricted mutation probes were denied with unchanged audit count. Foreign tenant and sibling-site source checks were exercised; the sibling cost probe disclosed no source actions. JournalEntry, TreasuryMovement, PaymentRequest and ProjectCostFact counts remained zero. Hidden Accounting returned denial. No Treasury/Cashbook/petty-cash balance was inferred from expenses. |

Daily Report equipment descriptions were not treated as Equipment Usage producers. No automatic deployment/operator association, new rate policy, financial posting rule or petty-cash workflow was added.

## UI/UX and navigation

Applied the existing [design registry](../APPROVED_DESIGN_CONFORMANCE_REGISTRY.md), [UI guidelines](../../../ui-guidelines.md), compact form, sectioned form and Expense Detail boards. Preserved the current shared components and PO-edited project/company work. DC-07 retains its existing separate PO-review status.

- Executed product patterns and available workflow forms were compared at **1440, 1024 and 390 CSS px**. Retest observations have RTL, one main landmark and no document-width overflow. Representative screenshots are retained; other observations use JSON rather than redundant image copies.
- Equipment, assignment/maintenance, operations/cost workbenches, Safety/Quality, expense/category and recurrence pages retain their existing archetypes. Search filters were actually submitted on equipment, Safety, Quality and expenses lists. Business context, row/detail actions, evidence entry and exact-version links were exercised.
- The invalid usage form now displays the existing business error and retains valid input. Expense CBS/cost-center choices now display business names/codes instead of `CBSNode object (UUID)` / `CostCenter object (UUID)`.
- Equipment/HSEQ input, output and expense history use organization-local time. Jalali dates, Persian labels, stacked narrow forms and available action states were inspected. Synthetic fixture names may be English; they are data, not an application localization claim.
- The absent record-decision journey, missing usage linkage and absence of an exposed petty-cash balance/report remain product-surface decisions. No approved page was redesigned. Visual/product acceptance remains pending.

[Original observations](evidence/wave-04-865fa3f3/original/) · [Retest observations](evidence/wave-04-865fa3f3/retest/)

## Defects, regressions and decisions

| Defect | Severity | Disposition |
|---|---|---|
| BON-DEF-0022 — organization-local timestamp input/output | P1 | FIXED / RETESTED_PASS |
| BON-DEF-0023 — cost policy create 500 | P1 | FIXED / RETESTED_PASS |
| BON-DEF-0024 — uncaught equipment model validation | P2 | FIXED / RETESTED_PASS |
| BON-DEF-0025 — expense coding model/UUID labels | P2 | FIXED / RETESTED_PASS |
| BON-DEF-0026 — no MVP record decision, closure blocked | P1 | NEEDS_PO_REVIEW / BLOCKED |
| BON-DEF-0027 — excessive/overlapping equipment runtime | P1 | NEEDS_PO_REVIEW / RETESTED_FAIL |
| BON-DEF-0028 — usage lacks deployment/operator input | P2 | NEEDS_PO_REVIEW / BLOCKED |

[Shared defect register](../DEFECT_REGISTER.md) · [Reproductions and remediation](../DEFECT_REGISTER.csv)

The timestamp failure pattern recurs in these separate form families; the B02/B03 fixes and pending decisions were preserved. The original legacy suite produced permission-fixture failures before B04 mutation and a retired-table flush error. Those are separately attributed; they are not a full-suite PASS. The bounded regression reproduced the original failures and passed after correction. See the technical evidence for exact commands, current boundary-suite outcome and limits.

PO must decide the bounded exposure/placement of record decisions; permitted usage concurrency/runtime and correction semantics; and the MVP deployment/operator input contract. Any petty-cash balance/workflow exposure also needs its existing product authority. The concurrent B03 addendum owns the current disposition of its earlier findings. B04 leaves their decisions and updated defect entries intact. [B03 addendum](B03_DAILY_REPORTS_FIELD_OPERATIONS_REPORT.md#final-remediation-addendum--2026-11-12)

## Acceptance and next wave

**Not ready for B04 acceptance:** one failed row, four blocked rows and two outstanding P1 findings. The four fixes are ready for PO review. Formal visual acceptance, Human Sign-off and production certification are **NOT EXECUTED**.

The next planned wave is **B05: UAT-07–09 and CV-BIL-01**, using independent approved estimate/baseline/terms fixtures and reviewers. Recommend resolving the B04 decisions or explicitly carrying their unresolved disposition before acceptance. **B05 was not started.** No production operations, existing-database mutations, new migration files, commit or push were performed.
