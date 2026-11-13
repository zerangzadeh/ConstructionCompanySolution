# B11 — Final UI/UX conformance and cross-module journeys

2026-11-13. MVP profile. Validation completed with explicit PO, statutory and scope exclusions below. This report does not issue Product Owner acceptance or production certification.

| Planned | PASS | FAIL | BLOCKED | NOT_RUN | NEEDS_PO_REVIEW |
|---:|---:|---:|---:|---:|---:|
| 302 | 285 | 0 | 2 | 2 | 13 |

Underlying technical UI outcomes are **298 PASS, 2 BLOCKED and 2 NOT_APPLICABLE**. The 13 PO rows have technical verification but retain their outstanding discretionary decisions. The two NOT_RUN rows are MVP-hidden employee-document screens, whose direct-request guards passed. They are excluded screens rather than unattempted visible work.

[Final 302-row retest](B11_FINAL_RETEST.csv) · [Counts](evidence/b11-24ad220f/closeout-counts.json) · [Original observations](evidence/b11-24ad220f/original-route-observations.json) · [Original result classifications](evidence/b11-24ad220f/original-results.csv) · [Check-level coverage and limits](evidence/b11-24ad220f/check-coverage.json)

## Baseline, isolation and preservation

Branch `main`, HEAD and local `origin/main` were `24ad220f0376cb0b6232b745938b35433843a32d`, with zero recorded divergence. Existing B03–B10 modifications and untracked work were captured before execution and preserved. No fetch, commit, push, production operation or CEP lifecycle mutation was performed.

The entry fingerprint covers 2,021 source files and is `2119f0f7f2d0dd001d704ab13b7d12621ca532b3974feb164996f9560a16291a`. The final source fingerprint is `c0e26d83e8f5e6fc1f687fa9c3ccac85bc1f4124735f2a5527068d5c1f54e739`. Exactly eight product files changed within B11. The final delta and complete per-file hashes distinguish these changes from the incoming dirty worktree.

Company List PA-03, Company Detail PA-02, their dedicated styles, Projects List and the captured Project Detail sources retain their entry hashes. All **829 non-B11 matrix rows** and the **61 existing defect records** retain their logical contents. Historical execution reports and browser attempts remain intact.

[Entry source](evidence/b11-24ad220f/entry-source.json) · [Entry Git state](evidence/b11-24ad220f/entry-status.txt) · [Final source delta](evidence/b11-24ad220f/final-source.json) · [Complete hash maps](evidence/b11-24ad220f/source-hashes.json) · [Compatibility and protected hashes](evidence/b11-24ad220f/source-compatibility.json)

A fresh loopback-only PostgreSQL **18.6** cluster was initialized under `.scratch/b11-validation/pg`. Its empty baseline database received all **462 migrations**. Original and independent retest databases were cloned from that baseline. Separate `test_b11_*` databases hosted Python tests. Runtime checks assert both the allowed database name and private cluster data directory before fixture/browser access. Storage and email were private synthetic/local fixtures. Existing Development, demo and Production databases were not used or changed.

`synchronous_commit=off` was applied only to this disposable cluster for test performance. It is not a production durability qualification. The final system, migration application and migration-drift checks passed with no B11 schema change. Installed Google Chrome **156.0.8078.80** ran through Playwright's `channel='chrome'`, at 100% zoom and 1440×900, 1024×768 and 390×844 CSS px.

[Environment](evidence/b11-24ad220f/environment.json) · [Empty catalog and migration count](evidence/b11-24ad220f/catalog.log) · [Migration execution](evidence/b11-24ad220f/migration.log) · [Final checks](evidence/b11-24ad220f/final-checks.log)

## Entry reconciliation and carried evidence

| Wave | Reconciled disposition relevant to B11 |
|---|---|
| B01 | Five authentication/recovery reference gaps remain PO-dependent. Shared behavior and accessibility are independently testable. |
| B02 | Later decisions explicitly accept the existing Projects List. Project Detail has approved design direction with final visual acceptance pending. Later worker scope exclusions are preserved. |
| B03 | The subsequent Return implementation reports 22 PASS and the integration migration gate passed. Earlier matrix dispositions are historical. |
| B04 | Final remediation reports 66 PASS. Independent Safety/Quality review and Equipment boundaries are retained. |
| B05 | Latest closeout reports 60 PASS and 13 blocked statutory positive scenarios. The older Wave 05 summary is not substituted for that closeout. |
| B06 | 88 PASS and the later inbound enhancement remain the business/lineage basis. B11 observes current source controls and navigation without repeating the complete financial chain. |
| B07 | 48 PASS. Its governed authorization scenarios remain the security basis, supplemented with current restricted/direct requests. |
| B08 | **21 technical PASS** in the current output/reporting/audit wave. Scanner/storage deployment verification remains external and unverified. Legacy assertion debt is recorded independently. |
| B09 | **65 technical PASS** in the final closeout. Its complete final source fingerprint exactly equals the B11 entry fingerprint. Employee-document routes are intentionally MVP-hidden. |
| B10 | **66 technical PASS**, including two protected Company rows pending PO acceptance. Compared with B11 entry, only Billing forms and Document Detail differ, outside the Platform seams. |

All 302 B11 rows have an exact inventory-ID historical match. [History index](evidence/b11-24ad220f/history-index.json) resolves the later closeouts without changing previous records. The [direct carry-forward index](evidence/b11-24ad220f/carry-forward-index.json) contains 64 route candidates, of which 39 qualify for the specifically described prior UI assertions after the final selector retest override. These are overlapping supporting observations, not 64 skipped current rows.

All 302 rows received current Chrome route, source-control or direct-guard observations. The merged current route evidence contains **807 viewport measurements across 269 rendered route rows**, with **zero document overflow**. Fifteen additional source page-state captures cover draft controls, the award continuation form, Equipment cost forms, receipt empty/draft/posted controls and the draft insurance selector. Additional portal, selector and representative journey evidence is retained separately rather than counted repeatedly.

B08 did not publish a complete final-source digest. Its entry map plus two closeout hashes qualify unchanged output dependencies only. The compatibility record explicitly marks the whole final digest unavailable. B09's exact entry equivalence does not automatically qualify the B11 changes. The eight-file delta was assessed by assertion, followed by current affected-page retests.

## Design conformance and UI checks

Existing DC-01–DC-11 authorities were applied. Lists retain their existing filter/status/table patterns. Record hubs retain source/context/history. Compact forms retain their approved card/footer and narrow stacking. Specialized transaction, identity and document workspaces retain documented exceptions. Sectioned forms preserve their supplied board and pending PO decision. No new layout standard was introduced.

The sweep observes Persian `lang/dir`, approved font loading, headings, control names, business labels, visible actions, source/return paths, document bounds, browser failures, keyboard entry and restricted variants. Representative journeys cover populated/empty search, invalid input retention, contextual cancellation/return, workflow transitions and mobile navigation. Prior qualified scenarios supply unchanged domain state, source calculations, output reconciliation and shared component behavior. Check-level evidence distinguishes direct observation, sampled shared behavior, historical business context, exclusions and blocked positives.

Keyboard evidence includes the mobile drawer's Enter/Esc interaction and restored focus, current named controls, selector pointer submission and native fallback restoration. Home/sidebar/mobile navigation exposed the same **29 entitled destinations** in the representative actor. Five hidden-module direct requests returned 403. The final contrast spot checks of rendered headings, labels and primary controls passed their size-dependent thresholds. There were no unresolved B11-attributable P0/P1 defects.

[Current route evidence](evidence/b11-24ad220f/original-route-observations.json) · [Field retest](evidence/b11-24ad220f/field-retest-route-observations.json) · [Document and role fixture retest](evidence/b11-24ad220f/evidence-retest-route-observations.json) · [Changed surfaces](evidence/b11-24ad220f/changed-final-route-observations.json) · [Final contrast and invitation timestamp](evidence/b11-24ad220f/invitation-and-contrast-final.json)

This is a desktop-Chrome responsive/keyboard validation with explicit sampling. It does not establish full WCAG certification, screen-reader/platform coverage, physical-device keyboard behavior or exhaustive combinations of pagination, asynchronous errors and validation on every route. Native file-picker text follows installed Chrome. The supplier's immutable receipt UUID is explicitly required by the supplier-portal guideline. Privileged audit target identifiers retain their designated administrative evidence context. Neither exception permits model representations in ordinary business selectors.

## Cross-module navigation

| Required journey | Final evidence-backed result |
|---|---|
| Company → Project → Site | PASS. Explicit company switch, project/site links and browser return observed. |
| Project → Daily Reports | PASS. Project filter retained before opening the report. |
| Workforce → Timekeeping | PASS. Explicit worker identity link and employee-filtered attendance navigation. |
| Project → Equipment and Operations | **PARTIAL_CONTEXT**. Shared module navigation reaches the asset and Operations. No direct project-to-equipment link or project-filter handoff was established. Keep this question in final Project Detail PO review. |
| Safety and Quality → Review/Closure | PASS with scoped reuse. Current independent decisions and persisted statuses passed. Closure remains the qualified B04 result and was not repeated in B11. |
| Contract → Baseline → Progress Claim | PASS. Contract basis pane, exact baseline and retained claim source observed. |
| Procurement → Inventory | PASS. Receipt/stock source lineage and return path observed. |
| Inventory → Inbound Transfers | PASS. Pending inbound navigation, transfer source and sibling/foreign denials observed. |
| Business Record → Related Documents | PASS. Canonical source links and an actual pointer-selected existing document were submitted. Exactly one new link persisted and the return includes `#related-documents`. |
| Workflow Inbox → Source → Decision | PASS. Current claim/release/reclaim and independent decision completed the work item and source atomically in the synthetic fixture. |
| Platform → Companies/Users/Roles | PASS technically. Directory/source navigation and tenant denial passed. Company visual acceptance remains separate. |

[Final journey assessment](evidence/b11-24ad220f/final-journeys.json) links the successful attempt for each case and retains the Equipment context limit. Earlier missing-fixture and locator attempts remain in the original journey files. Their superseding successful observations are separately cited. The Equipment context limit is not converted into a PASS for a project-filter handoff.

## Corrected defects and independent retest

| Finding | Correction and independent evidence |
|---|---|
| BON-DEF-0062 · P2 | Supplier deadline, receipt time and invitation expiry render in the authorized organization's timezone with Jalali/Persian display. Stored timestamps, receipt version and immutable receipt identity remain unchanged. Wrong principals receive 404. [Before](evidence/b11-24ad220f/portal-before.json), [after](evidence/b11-24ad220f/portal-after.json), [invitation](evidence/b11-24ad220f/invitation-and-contrast-final.json). |
| BON-DEF-0063 · P2 | Equipment Category opts into the existing enhanced-source suppression. Shared cleanup restores the original label target as well as native accessibility state. Related mechanism BON-DEF-0001. Chrome confirms one Category control, a labeled native fallback and correct Platform tenant-selector cleanup. [Before](evidence/b11-24ad220f/labels-before.json), [after](evidence/b11-24ad220f/labels-after.json), [lifecycle retest](evidence/b11-24ad220f/exact-regression.json). |
| BON-DEF-0064 · P2 | Payable item and taxpayer source-claim choices display contract/business references and descriptions or revision numbers. Chrome populated options contain no model/UUID representation. Scope, deny-by-default membership handling and invalid-input retention passed. [Before](evidence/b11-24ad220f/labels-before.json), [after](evidence/b11-24ad220f/labels-after.json), [scope regression](evidence/b11-24ad220f/exact-regression.json). |

Final visual spot checks retain the approved compact composition and specialized Billing form patterns. [Equipment](evidence/b11-24ad220f/equipment-final.png) · [Payable form](evidence/b11-24ad220f/payable-final.png) · [Taxpayer form](evidence/b11-24ad220f/taxpayer-final.png) · [Portal](evidence/b11-24ad220f/portal-after-context-390.png)

The optional prior-invoice choice label also uses business terms. A populated positive statutory correction selector was not created or certified. No financial calculation, posting rule, permission, tenant resolver, Product Surface rule, model or migration changed.

## Focused regression and attribution

| Run | Actual outcome | Outstanding failure attribution |
|---|---|---|
| Product Surface, Home, B10, B09, inbound transfer focused suite | 96 PASS, 59 subtests PASS, **1 FAIL** | Reporting test patches `reporting.views.render`, while the B08 implementation calls the organization-time helper. The HTTP response is 200. Relevant view/test bytes were unchanged by B11. |
| Supplier portal and localization/accessibility suite | 32 PASS, 52 subtests PASS, **4 FAIL** | One PostgreSQL flush/foreign-key teardown failure. Three legacy navigation assertions expect pre-MVP availability contracts. No B11 navigation or schema mutation. |
| Changed-surface Python suite | 24 PASS, 37 subtests PASS, **1 FAIL** | Equipment's legacy fixture supplies a legacy owner role without effective governed assignment. It fails closed with 403 before reaching the changed form. Explicit-grant Chrome actors pass. |
| Final exact regressions | **5/5 PASS** | Authorized explicit organization time and ambient restoration, payable labels/scope/retention, taxpayer source scope/business labels, Equipment cleanup and Platform selector cleanup. |
| Static/system/schema checks | PASS | Ruff check/format for changed Python, JavaScript syntax, Django system check, migration application/drift and scoped Git whitespace checks. |

[Commands, counts and failure seams](evidence/b11-24ad220f/regression-results.json) · [Focused raw log](evidence/b11-24ad220f/focused-regression.log) · [Portal/localization raw log](evidence/b11-24ad220f/portal-localization-regression.log) · [Changed-surface raw log](evidence/b11-24ad220f/changed-surface-regression.log). Runs overlap and must not be summed as unique tests. The wider suites are **not green**. Their assertion/infrastructure failures remain visible as regression debt. Concurrency was not repeatedly rerun or re-certified following display-only changes.

## Remaining PO decisions and release boundary

The following **13 rows** remain `NEEDS_PO_REVIEW`, with `PO_ACCEPTANCE=NOT_RUN`.

1. Accepted page-specific visual references for Login and the four public password-recovery screens, DC-01.
2. Formal visual acceptance of preserved Company List PA-03 and Company Detail PA-02, DC-10.
3. Final Project Detail dashboard visual acceptance under `PO-B02-PROJECT-DASHBOARD-20261112`, including confirmation of the intended Equipment context handoff. Existing Projects List acceptance is preserved.
4. Separate Sectioned Form standard visual acceptance for Expense Create, Expense Draft, Daily Report Create, Safety Create and Quality Create, DC-07.

Two positive B11 rows remain blocked, `INV-BILLING-CONTRACTOR-COMPLIANCE-DETAIL--CV-UI-01` and `INV-BILLING-TAXPAYER-INVOICE-DETAIL--CV-UI-01`. They depend on the reviewed statutory/source prerequisites still absent in B05. B11 neither seeds statutory approval nor claims those records were validated. The two MVP-hidden employee-document screen rows remain NOT_RUN with explicit scope exclusion and verified denial.

B11 supplies evidence for conditional MVP UI review. Final MVP acceptance remains open because of the PO decisions, the Equipment context question and statutory positive coverage. Broader release readiness also retains B08 deployment scanner/storage verification and the disclosed regression assertion/teardown debt. B11 does not resolve those by accepting residual risk, changing policy semantics or enabling production. All three confirmed B11 UI defects are independently retested and no attributable P0/P1 remains unresolved.

[Replay instructions](evidence/b11-24ad220f/replay/README.md) · [Final integrity and resource closeout](evidence/b11-24ad220f/closeout-integrity.json)
