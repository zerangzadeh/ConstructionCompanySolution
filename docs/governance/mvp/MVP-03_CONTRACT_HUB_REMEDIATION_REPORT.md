# MVP-03 — Contract Hub quantities and measurement navigation

Date: 2026-11-02. Bounded non-production presentation/navigation remediation under the current Human request and reference image. The F4 report contains `SHARED FRONTEND FOUNDATION: ACCEPTED`; its representative-scope acceptance is the entry gate. No CEP lifecycle, roadmap scope, production authority or Human visual acceptance is inferred.

## Scope and accepted assessment

Reviewed `docs/ui-guidelines.md`, the F4 conformance report, current shared navigation/interactions, the two assessments in the existing **Assess Contract progress UX** chat (`01a198c5-9e13-7840-aba0-e7816b9aa38f`), and existing Contract/Billing implementation reports under `output/contract-state-aware/`, `output/billing-journey-navigation/` and `output/billing-journey-content/`. The historical reports are evidence, not new instructions or live lifecycle authority.

The assessment's **Accept with revisions** bounds this change: one Contract Hub, direction-specific contents, separate measurement history and analytical progress, independent baseline line identities, preserved historical versions and no mandatory wizard. New receivable measurement-entry screens, new analytics, quantity/rate revision semantics and workflow changes remain deferred. The image's illustrative figures and “ثبت کارکرد” controls do not establish business rules or authorize a new entry adapter.

## Delivered behavior

- Existing Contract Detail identity/context and state-specific overview remain. Its local journey groups contract quantities and receivable measurement bases under **مقادیر و بهای قرارداد**, distinct from **وضعیت پیشرفت** and the document section. Draft preparation remains available through its existing service-backed forms.
- The quantities workspace uses the existing Contract route (`?section=quantities`). Contract lines and measurement-basis lines remain separate. Payable subcontracts use ContractItem; supplier/unsupported contracts gain no subcontract operations.
- Receivable basis view selects the approved version by default, otherwise the latest visible version; explicitly selected historical snapshots show original state, effective date, ceiling and approval evidence. Version links stay inside this workspace; existing detail/all-version URLs remain available. Rows are paginated; the latest 20 version shortcuts link to the complete existing version collection.
- Unmapped BaselineItem rows retain direct measurement-history links. Contract-scoped `line_key` filtering spans authorized historical versions without description matching, ContractItem inference or rewriting original sources. Payable history narrows by existing contract/line identity. These filters only intersect the canonical authorized selectors.
- Scoped receivable Billing navigation returns authorized Contract readers to the quantities workspace. Global collections and readers with independent child permissions but no Contract permission retain their existing destinations.
- Measurement lists identify original baseline versions and use **سوابق اندازه‌گیری و کارکرد**. Approved/returned/source workflows and direct record URLs remain. Context persists through existing search/clear/pagination mechanisms.
- Existing terms, amendments and linked estimates are presented under their corresponding local sections. No new financial total, physical percentage, posting, settlement or mutation service is introduced.
- Measurement verify/reject forms opt into the existing shared SweetAlert2 confirmation attributes. Required reasons remain inline/native validation; cancellation preserves text and sends no POST. Existing endpoints/services, CSRF and workflow decisions retain authority.

## Repository and safety boundary

Branch `main`, entry HEAD/local `origin/main` `b97fcc45a92737b83e9c3ffb14b589cfdc4250d7`. Entry state and exact touch set: [entry evidence](../../../output/contract-hub-remediation/entry.json). A concurrent Purchase Request Detail task owns the procurement edits and its evidence; this task does not modify those files. No index/commit/push/branch/worktree operation.

No model, schema/migration, permission grant, domain/calculation service, Product Surface policy, shared navigation registry, module selector, runtime library or dependency change. No Development or production data mutation. Synthetic verification data is confined to `test_bonira_contract_hub_20261102`; the configured migration graph initializes that disposable test database.

## Validation

| Check | Result | Evidence |
| --- | --- | --- |
| Affected Contract state, dashboard, payable projection, Hub and Billing server checks | 28 tests / 16 subtests PASS | [server log](../../../output/contract-hub-remediation/server-tests.txt) |
| Final Hub/filter/context checks after review | 8 tests / 4 subtests PASS; includes source ordering for rows with equal sort order | [final server log](../../../output/contract-hub-remediation/final-server-tests.txt) |
| Shared navigation, Module Selector presentation and Product Surface boundaries | 12 tests / 7 subtests PASS | [shared boundary log](../../../output/contract-hub-remediation/shared-boundary-tests.txt) |
| Installed real Chrome, headless, isolated synthetic PostgreSQL | 1 test PASS; 27/27 browser cases, 9 at each requested width | [browser test](../../../output/contract-hub-remediation/browser-tests.txt), [case evidence](../../../output/contract-hub-remediation/browser/results.json) |
| Tailwind reproducibility and actual rendered utility coverage | Rebuild byte-identical; 160/160 required utilities compiled; zero missing/forbidden scan paths | [rebuild](../../../output/contract-hub-remediation/tailwind-reproducibility.json), [coverage](../../../output/contract-hub-remediation/tailwind-coverage.json) |
| Shared source preservation | All 43 original shared-component hashes match; no tracked runtime/navigation/Product Surface diff | [preservation](../../../output/contract-hub-remediation/shared-preservation.json) |
| Django checks, focused Ruff check/format, JS syntax and scoped whitespace | PASS | [static checks](../../../output/contract-hub-remediation/static-checks.json) |

The final browser run uses **Chrome/156.0.8078.48**, fresh profile, disabled cache/service-worker bypass and an exact loopback-origin network allowlist. An external negative control is blocked. Its 27 cases cover Contract overview → quantities → measurement basis → line history by physical clicks, receivable empty contract lines, approved and superseded basis versions, payable ContractItem rows, cross-version history, a restricted Contract-only reader, actual remote Project Tom Select search/selection and independent measurement decisions at **1440, 1024 and 390 × 900**.

All 27 pages exercise the unchanged Module Selector Drawer: exact server-authorized labels/routes and active set, keyboard focus/Tab, close/Escape/backdrop, scroll lock, reduced motion and unchanged project/site and desktop/mobile navigation. Existing standalone measurement routes have **no active-module alias in the current authority**; the same empty active set is preserved rather than inventing an alias/registry entry. Existing Contract routes retain their correct active module.

Tom Select preserves native value/FormData/change events and idempotent HTMX mounting at all three widths. Measurement verification/rejection uses the shared local SweetAlert2 includes and attributes: inline/native required reason remains, cancellation is focused, cancel/Escape preserve text with **zero POSTs**, and the final independent verification sends **exactly one POST** to the original service-backed endpoint. Database assertions confirm the original measurement becomes verified, without creating a duplicate.

[Network/console evidence](../../../output/contract-hub-remediation/network-summary.json): **671 responses, 37 successful documents, 0 application external requests, 0 JavaScript exceptions, 0 console API errors, 0 unexpected network failures**. One superseded lookup fetch cancellation has a successful replacement response. One browser-generated `/favicon.ico` 404 is retained as the existing shared-shell baseline; no required asset error is waived. There are no other browser log errors or attributable shared frontend regressions in the representative scope.

Representative desktop, 1024 and mobile captures were directly inspected for Persian RTL, legibility, correct direction-specific contents, version evidence and contained horizontal navigation/tables. Horizontal table/navigation scrolling is intentional; document overflow checks pass. Review images: [desktop receivable basis](../../../output/contract-hub-remediation/browser/receivable-basis-1440-quantities.png), [1024 basis](../../../output/contract-hub-remediation/browser/receivable-basis-1024-quantities.png), [mobile basis](../../../output/contract-hub-remediation/browser/receivable-basis-390-quantities.png), [mobile payable](../../../output/contract-hub-remediation/browser/payable-items-390-quantities.png), [mobile shared confirmation](../../../output/contract-hub-remediation/browser/measurement-decision-390-verify-confirmation.png).

### Failed-attempt attribution

- Initial command named a nonexistent test class: collection failed, no tests ran. Its log remains [initial-tests.txt](../../../output/contract-hub-remediation/initial-tests.txt). The following fresh bootstrap was interrupted before assertions and replaced with the guarded test clone described above.
- Browser attempt 1 assumed every route had an active module alias. Canonical navigation has none for standalone measurement routes. Corrected the test oracle to preserve the canonical active set, with a required single active module on Contract routes. No shared navigation change. [Attempt log](../../../output/contract-hub-remediation/browser-attempt-1-fixture.txt).
- Browser attempt 2 preflight authentication rotated a retained restricted-reader session. Each preflight now uses a separate test client. This was a fixture failure. [Attempt evidence](../../../output/contract-hub-remediation/browser-attempt-2-session/).
- Browser attempt 3 proved an attributable integration defect: the measurement page's new confirmation attributes lacked the shared asset includes. Added the existing interaction CSS/JS includes; the final run proves both dialogs and the original POST. [Failed evidence](../../../output/contract-hub-remediation/browser-attempt-3-assets/). No new dialog framework or duplicate component.
- Initial static format checks required ordinary formatting. An initial raw HEAD-blob hash comparison also included Windows CRLF differences and concurrent-task evidence changes; the final preservation method above checks the correct sources. These initial outcomes are not represented as passes; the corrected final checks pass.

The final review also retains canonical row order (`sort_order`, then creation time, with a stable pagination tie-breaker). The final eight-test run verifies multiple equal-order draft rows. This does not change the one-row browser fixtures or rendered layout. No unresolved remediation-attributable failure remains.

### Reproduction and outcome

Use `.venv/Scripts/python.exe scripts/verification/contract_hub_validate.py` with the test selections in the four evidence logs/XML files, `--reuse-db -q`. The runner restricts cleanup to `test_bonira_contract_hub_20261102`; the Chrome driver uses no new automation dependency. The final source/touch-set manifest is [closeout.json](../../../output/contract-hub-remediation/closeout.json).

```text
F1-F4 FRONTEND FOUNDATION PRESERVED: PASS
TOM SELECT CONFORMANCE: PASS
SWEETALERT2 CONFORMANCE: PASS
SHARED NAVIGATION PRESERVED: PASS
OFFLINE RUNTIME PRESERVED: PASS
ATTRIBUTABLE SHARED FRONTEND REGRESSIONS: 0
VISUAL UX REMEDIATION: READY FOR HUMAN REVIEW
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

These results cover the bounded remediation and representative frontend checks, not a full-repository/all-page regression or production readiness. New measurement-entry screens, payable inherited create context, new analytics, schema/domain evolution and workflow changes remain deferred. No stage/commit/push or CEP Registry update. The changes remain uncommitted for review.

Human Sign-off, Product Owner Visual Acceptance, Production Certification and Production Cutover: NOT EXECUTED.


## Product Owner follow-up — focused Claims List

The Human reviewed the Contract → “مشاهده همه صورت‌وضعیت‌ها” handoff and requested that Claims List omit the three sibling-workspace buttons. This instruction supersedes the earlier sibling-navigation expectation for Claims List only.

Removed the `billing/journey_nav.html` include from `billing/claim_list.html`. Claims List is a focused document collection in both global and contract-scoped modes. Contract identity, the existing “بازگشت به قرارداد” link, permitted create action, filters/search, summaries, sorting, pagination, record details and all server-side scope/permission rules are preserved. Baseline, measurement, claim detail/create and the Contract Hub retain their current navigation. No shared component, navigation registry, asset, CSS/JS, service, permission or Product Surface policy changed.

Updated affected navigation assertions and browser journeys to reflect the focused collection and return through Contract Hub. Historical sibling-page title expectations in the older remediation suite were not expanded into this follow-up.

Validation: **6/6 tests PASS**: existing Claims list filtering/counts/pagination/isolation, independent child permissions/baseline routing, and a real installed Chrome test with **3/3 physical “View all claims” handoffs at 1440, 1024 and 390**. Each browser case proves no sibling bar, exact contract query, working return/detail links, no document overflow, no JS exceptions and no required-page/asset HTTP errors. Synthetic test data only, using the same isolated test database. Desktop and mobile screenshots were directly inspected.

- [Focused test log](../../../output/contract-hub-remediation/claims-list-followup/tests.txt)
- [Desktop](../../../output/contract-hub-remediation/claims-list-followup/browser/f61-owner-view-all-claims-1440.png)
- [1024](../../../output/contract-hub-remediation/claims-list-followup/browser/f61-owner-view-all-claims-1024.png)
- [Mobile](../../../output/contract-hub-remediation/claims-list-followup/browser/f61-owner-view-all-claims-390.png)

The previous offline/shared frontend evidence remains applicable to unchanged assets and shared components. This follow-up removes one local include and introduces no runtime asset. Focused Ruff and changed-file whitespace checks PASS. Changes remain uncommitted; no production operation or Human visual acceptance is inferred.

```text
F1-F4 FRONTEND FOUNDATION PRESERVED: PASS
TOM SELECT CONFORMANCE: PASS
SWEETALERT2 CONFORMANCE: PASS
SHARED NAVIGATION PRESERVED: PASS
OFFLINE RUNTIME PRESERVED: PASS
```


## Product Owner follow-up — quantities layout and stale asset key

The Human supplied Contract quantities and receivable-basis screenshots showing unpadded/right-compressed tables, crowded numeric columns, disorganized version metadata and large unused panel space. The correction is bounded to `templates/contracts/detail.html`, `templates/contracts/hub_quantities.html` and the existing Contract-local `detail.css`, with a focused synthetic fixture in `test_hub.py`.

A direct read of the running Development server's `contracts/detail.css?v=1` matched the source and included the prior quantity rules; `findstatic` located one source. The screenshot resembles the new markup with missing quantity styling. **Old client cache is a supported hypothesis, not a reproduced root cause in the Human browser session.** The template had retained the old `?v=1` URL after CSS/JS changes. Contract CSS and JS references now use `?v=20261102-quantities-2`; a live-server read of that CSS key matches the final source. [Before served-asset check](../../../output/contract-hub-remediation/quantities-layout-followup/served-css.json), [after](../../../output/contract-hub-remediation/quantities-layout-followup/served-css-after.json).

The domain-local layout now uses full-width, spaced desktop columns with separate description/unit/quantity/amount/action cells, LTR numeric isolation and non-wrapping money. It reuses the existing shared `erp-responsive-list` and data-label pattern for cards below 1200px rather than defining a second responsive table component. Local subsection links wrap and remain fully visible on mobile. Baseline version/status, effective date and stored ceiling use a structured fact block; original approver/time/reason remain available in a readable disclosure, with long source references wrapping safely. Historical guidance remains inline. No values, lifecycle, baseline selection, history mapping, actions or permissions are changed.

Validation: **6 tests / 4 subtests PASS**, comprising the five existing Hub source/scope tests and one installed real Chrome test. The browser test passes **6/6 scenarios**: both panes at **1440, 1024 and 390**, with two long Persian descriptions and synthetic **16,733,750,000,000 / 13,691,250,000,000 IRR** rows. Geometry checks prove full card/table width, no document overflow, fitted subsection controls, readable untruncated amounts, inherited responsive row cards, and the new asset URL. Real disclosure clicks prove long approval evidence fits and closes without changing the snapshot. The first layout-only six-case pass also exercised an unset-currency label; the final fixture explicitly configures canonical OrganizationSettings IRR and asserts that warning is absent. This is test configuration only, not a new product default.

All final six documents return 200, with no JS exceptions or required page/asset HTTP errors. Desktop, 1024 and mobile captures were directly inspected. The existing favicon exclusion in the inherited driver remains historical baseline behavior. Source checks confirm **43 shared component hashes match** and **no tracked shared runtime/navigation/Product Surface change**. The local Tailwind rebuild remains byte-identical. Focused Ruff check/format, Django checks and scoped whitespace PASS; initial Ruff fixture integer-literal formatting was corrected before the final checks.

- [Final validation and source hashes](../../../output/contract-hub-remediation/quantities-layout-followup/validation.json)
- [Tests](../../../output/contract-hub-remediation/quantities-layout-followup/tests.txt)
- [All six browser cases](../../../output/contract-hub-remediation/quantities-layout-followup/browser/f61-owner-results.json)
- [Desktop basis, including table](../../../output/contract-hub-remediation/quantities-layout-followup/browser/f61-owner-quantities-basis-1440-bottom.png)
- [1024 contract rows](../../../output/contract-hub-remediation/quantities-layout-followup/browser/f61-owner-quantities-items-1024-bottom.png)
- [Mobile basis](../../../output/contract-hub-remediation/quantities-layout-followup/browser/f61-owner-quantities-basis-390.png)
- [Unchanged Tailwind build](../../../output/contract-hub-remediation/quantities-layout-followup/tailwind.json)

```text
F1-F4 FRONTEND FOUNDATION PRESERVED: PASS
TOM SELECT CONFORMANCE: PASS
SWEETALERT2 CONFORMANCE: PASS
SHARED NAVIGATION PRESERVED: PASS
OFFLINE RUNTIME PRESERVED: PASS
```

No shared facility, vendor/dependency, remote asset, schema, service, finance/measurement semantics, workflow, permission or Product Surface mutation. The previous Claims List correction remains. No Git writes or production action; changes remain uncommitted and Product Owner visual acceptance remains pending.


## Follow-up — focused measurement history collection

Continuing the Human's preceding collection-navigation feedback, the supplied “سوابق اندازه‌گیری و کارکرد” screen was treated as a focused history collection. Its existing destination is correct for contract-wide history and stable-line history. Removed its sibling-navigation include, matching Claims List. Global and scoped Progress List remain available; baseline and measurement detail/create workflows retain their existing navigation and actions.

The view reuses the existing authenticated/scoped `breadcrumb_contract` resolution once, passing that same authorized object to the context panel and breadcrumbs. The parent link returns to `contracts:detail?section=quantities`, respects the existing central Product Surface filter and does not write global project/site context. Users with independent `progress.view` and no Contract permission retain their scoped records without gaining a Contract return link. The stale “پیشرفت کار” list breadcrumb and measurement-detail collection breadcrumb now use “سوابق اندازه‌گیری و کارکرد”. Records, dates, units, period/cumulative quantities, verification statuses, search/clear/pagination and stable cross-version line filtering are unchanged.

Validation: **5 tests / 4 subtests PASS**, covering scoped/global list presentation, authorized parent context, independently permitted history readers without Contract access, existing independent baseline permissions/routing, and cross-version stable-line history with retained search/clear context. One browser test passes **6/6 installed real Chrome handoffs**: contract-wide and line-specific history at **1440, 1024 and 390**. Each physically clicks the existing history action, proves exact contract/line query state, no sibling bar, the scoped parent link and retained source-detail link, no document overflow, no JS exceptions and no required-page/asset HTTP errors. Synthetic data remains confined to the existing guarded test database. Desktop and mobile screenshots were directly inspected.

- [Tests](../../../output/contract-hub-remediation/measurement-history-followup/tests.txt)
- [Source/validation evidence](../../../output/contract-hub-remediation/measurement-history-followup/validation.json)
- [Six Chrome cases](../../../output/contract-hub-remediation/measurement-history-followup/browser/f61-owner-results.json)
- [Desktop contract history](../../../output/contract-hub-remediation/measurement-history-followup/browser/f61-owner-history-contract-1440.png)
- [Mobile line history](../../../output/contract-hub-remediation/measurement-history-followup/browser/f61-owner-history-line-390.png)

Focused Ruff check/format, Django checks and scoped whitespace PASS. The same 43 shared component hashes match entry, and tracked shared assets/navigation/Product Surface have no diff. No CSS/JS, vendor/dependency, runtime asset or shared component change in this follow-up; previous offline and shared interaction evidence remains applicable to those unchanged facilities. No models, migrations, domain services, calculation, approval/workflow, permission grant or source authority change. No Git writes or production action. Product Owner visual acceptance remains pending.

```text
F1-F4 FRONTEND FOUNDATION PRESERVED: PASS
TOM SELECT CONFORMANCE: PASS
SWEETALERT2 CONFORMANCE: PASS
SHARED NAVIGATION PRESERVED: PASS
OFFLINE RUNTIME PRESERVED: PASS
```


## Follow-up — explain the measurement-history purpose and reading model

The Human could not understand the list's purpose. This follow-up makes explicit that each row is one measurement source record for one work item/date, rather than a distinct work category, contract total or physical progress percentage. Inline reading guidance explains **کارکرد این ثبت** and **تجمعی تا این ثبت**, including that cumulative figures from different dates must not be summed. Result counts now say **ثبت اندازه‌گیری**.

The contract-filtered view keeps contract/project identity in its context header instead of repeating the same title in every row. Global/independent-reader views keep source identity per row. Each row shows original baseline version/planned quantity/unit, measured date and period, unchanged period/cumulative amounts and state. A focused **جزئیات اندازه‌گیری** control opens the original detail URL. **سوابق همین قلم** uses the existing contract-scoped stable `line_key`; a visible line-context panel offers **همه اقلام این قرارداد**. Text search additionally matches the authorized baseline line's description. The selected-line context is resolved from the same scoped measurement queryset before text search, so a zero-result search retains useful context without exposing other records. No new totals, calculations, weighting, latest-value inference or state semantics are added.

Existing shared responsive table/cards, status badges, controls, chips and page header remain. Presentation CSS is local to Billing's existing journey stylesheet; its URL revision changed to avoid the stale-asset key. Persistent guidance remains inline. This task does not introduce a selector, dialog framework, navigation registry, remote asset or dependency.

Validation: **4 tests / 4 subtests PASS**, including description search, empty-search line context, invalid-scope rejection, independent-reader/context behavior, cross-version stable history and a real Chrome test with **6/6 cases at 1440, 1024 and 390**. The fixture reproduces eight verified measurements for two work items across four dates. Physical browser interactions exercise description search → four records, clear → eight, focus one line → four and return to all lines → eight. Database snapshot equality proves no quantity or status changed. All browser documents return 200, with no JS exceptions, required-page/asset errors or document overflow. Desktop, 1024 and mobile captures were directly inspected. Focused Ruff check/format, Django checks and whitespace PASS. The Tailwind build is byte-identical to the runtime file.

Concurrent work changed Module Selector assets/template and its presentation helper while this test ran; its visible label changed to “ماژول‌ها”. This task did not edit those files, suppress their changes or certify that separate work. Earlier shared-frontend preservation evidence is historical for its recorded source snapshot. Current conformance here is scoped to the unchanged facilities consumed by this page and the attributable diff; a full shared-navigation requalification is not claimed.

- [Validation and attribution](../../../output/contract-hub-remediation/history-clarity/validation.json)
- [Tests](../../../output/contract-hub-remediation/history-clarity/tests.txt)
- [Six browser cases](../../../output/contract-hub-remediation/history-clarity/browser/f61-owner-results.json)
- [Desktop reading guide and table](../../../output/contract-hub-remediation/history-clarity/browser/f61-owner-history-reading-1440.png)
- [Mobile single-line history](../../../output/contract-hub-remediation/history-clarity/browser/f61-owner-history-one-line-390.png)
- [Unchanged Tailwind build](../../../output/contract-hub-remediation/history-clarity/tailwind.json)

F1-F4 FRONTEND FOUNDATION PRESERVED: PASS (attributable change scope; concurrent drawer work separately owned)
TOM SELECT CONFORMANCE: PASS (no selector contract/asset change)
SWEETALERT2 CONFORMANCE: PASS (no interaction contract/asset change)
SHARED NAVIGATION PRESERVED: PASS (this task makes no shared navigation change)
OFFLINE RUNTIME PRESERVED: PASS (local-only source references; no new dependency)

No Git writes or production action. Product Owner visual acceptance remains pending.


## Follow-up — measurement detail hierarchy (2026-11-03)

The Human supplied the measurement-detail screen and requested design remediation. Product touch set: existing `billing/progress_detail.html`, presentation context in `billing/views.py`, and new local layout-only `billing/measurement_detail.css`. Current branch/HEAD remain `main` / `b97fcc45a92737b83e9c3ffb14b589cfdc4250d7`. Existing uncommitted Hub, procurement and concurrent Module Selector work are preserved.

The screen now describes **one measurement record**, with source work-item description, contract/project, original baseline version and existing state together. Three separate value cards show the original period quantity (**کارکرد این ثبت**), original cumulative quantity (**تجمعی تا این ثبت**) and original baseline planned quantity/unit. No progress percentage, derived balance, valuation or replacement measurement is inferred. Inline guidance explains the cumulative values. Dedicated panels show measured date/period and the existing state-specific review result, including original verifier/rejector, time and reason where recorded. Draft and submitted states show accurate explanatory copy and their existing permitted forms. The original long source reference and evidence remain readable in a disclosure rather than dominating the page. No source value is rewritten or hidden by data migration.

Removed the three sibling-workspace buttons from this detail page. The shared page header, badges, fields, buttons and interaction includes are reused. A secondary **بازگشت به سوابق همین قلم** link and the collection breadcrumb use the exact authorized record's contract/stable-line context, preserving historical source identity. Global project/site controls reuse the existing header-context presentation; no session context is changed. Existing independent history readers retain access without receiving Contract permission or a Contract detail link. No new mutation endpoint, permission grant or service call is introduced.

Verify/reject forms retain required inline reasons and the existing SweetAlert2 opt-in attributes. Draft submission now uses the same focused confirmation pattern. Cancellation leaves the original record and reason unchanged. Existing transactional domain/workflow services remain authoritative for any confirmed action; lifecycle and maker/checker rules are unchanged. Persistent record guidance and review results remain inline, not dialogs.

Validation: **6 tests PASS**, including server projection/return-context/independent-reader checks, existing source/search/permission/navigation boundaries, and one installed real Chrome test with **12/12 scenarios**: Draft, Submitted, Verified and Rejected at **1440, 1024 and 390**. Browser checks prove original three quantities, no document overflow, long-reference/evidence disclosure behavior, responsive cards, local shared RTL decision dialogs with cancel focus, retained reasons and cancelled draft submission. Database assertions prove all four record states remain unchanged after dismissals. All twelve documents return 200 with no JS exceptions or required-page/asset errors. Desktop and mobile captures were directly inspected. Ruff check/format, Django checks, template compilation, static-asset resolution and scoped whitespace PASS.

The initial run had **one test-oracle failure**, with the other five tests (including twelve Chrome cases) passing: a read-only assertion searched the entire rendered document and matched unrelated shell POST forms. The corrected assertion inspects only `.measurement-detail`. No product permission relaxation was needed. Final rerun: six PASS. The failed-attempt outcome is retained; raw rendered HTML was excluded from retained failure evidence to avoid ephemeral form tokens.

- [Final validation and source hashes](../../../output/contract-hub-remediation/measurement-detail/validation.json)
- [Final tests](../../../output/contract-hub-remediation/measurement-detail/tests.txt)
- [Initial assertion failure](../../../output/contract-hub-remediation/measurement-detail/initial-tests.txt)
- [Twelve Chrome cases](../../../output/contract-hub-remediation/measurement-detail/browser/f61-manager-results.json)
- [Verified desktop](../../../output/contract-hub-remediation/measurement-detail/browser/f61-manager-measurement-verified-1440.png)
- [Verified mobile](../../../output/contract-hub-remediation/measurement-detail/browser/f61-manager-measurement-verified-390.png)
- [Submitted decisions](../../../output/contract-hub-remediation/measurement-detail/browser/f61-manager-measurement-submitted-1440-bottom.png)

```text
F1-F4 FRONTEND FOUNDATION PRESERVED: PASS (attributable page scope)
TOM SELECT CONFORMANCE: PASS (no selector contract/asset change)
SWEETALERT2 CONFORMANCE: PASS (shared dialogs exercised at all three widths)
SHARED NAVIGATION PRESERVED: PASS (no shared navigation change by this task)
OFFLINE RUNTIME PRESERVED: PASS (all referenced assets local; no new dependency)
```

Concurrent Module Selector work remains separately owned and is not certified here. No model/schema/migration, financial or measurement calculation, permission, Product Surface policy, workflow, dependency, remote asset, production operation or Git write. Changes remain uncommitted; Product Owner visual acceptance remains pending.


## Human-authorized terminology and persisted review sample — 2026-11-03

The Human explicitly requested the recommended user-facing “کارکرد” terminology and one persisted sample contract with varied lines, large quantities/prices and different claims for manual page checks. This grants bounded local demo-data authority for this task, separately from the prior isolated-test-only work. It does not authorize a policy/rate change, statutory activation, production action or Git write.

Labels now use **سوابق کارکرد**, **جزئیات کارکرد ثبت‌شده**, **مقدار کارکرد دوره**, and **کارکرد تجمعی تا این تاریخ**. Parent links, actions, counts, search wording and focused guidance follow that vocabulary. **تاریخ انجام اندازه‌گیری** preserves `measured_on` meaning; it is not relabeled as the time data was entered. Model/field/URL/service names, status catalog and approval semantics remain unchanged. No CSS/JS, selector, vendor, dependency, shared navigation registry or Product Surface edit was required by this terminology task.

Created **UAT-WORK-1405-01**, “نمونه کنترل مقادیر، متره و کارکرد — سازه و تأسیسات باغستان”, in existing local Development tenant `demo-construction-02` / گروه عمرانی افق تهران and project مجتمع مسکونی باغستان. Six lines span m³, kg, m², m and ea, including fractional quantities, varied completion patterns and high rates. Contract/base value: **1,269,687,618,125 IRR**. One approved measurement basis preserves exact ContractItem links.

The sample has **33 work records**: 30 verified across five dates for six lines, plus one submitted, one rejected and one draft record. The three unverified examples occur after the October claim cutoffs. **Six claims/revisions**: two approved, one submitted, one returned, its draft revision and a separate draft claim. All record creation, baseline/term approval, independent verification and claim transitions use existing application services with two distinct existing active tenant members. No direct status UPDATE, fabricated role/grant or domain bypass. Every sample is marked synthetic; existing source contract/party and tenant-owned unit masters are reused, without changing their data.

The seed is Development/local-PostgreSQL-only and dry-run-by-default, transactional and marked-idempotent. It verifies the current migration graph; the existing unrelated pending Payroll migration is recorded and unchanged. It reuses the existing published regulatory policy already used by this tenant's sample contracts, verifying exact effective policy identity for each period. It creates no policy/source/rate/classification or activation. All existing policy rows retain their hash. Contract, ContractItem, ContractTermVersion, baseline, work-record and claim rows present at entry retain their hashes. Accounting JournalEntry, subledger Obligation, TreasuryMovement and PaymentRequest counts are unchanged; no financial recognition/posting/payment/settlement is performed.

The first dry run rolled back on the verifier's mistaken exact comparison of pre-round line sums to final currency-rounded gross. Inspection of the existing calculation snapshot proved the canonical final-monetary-rounding rule. The verifier now independently checks line arithmetic, gross intermediate, quantization using snapshotted currency decimal places/ROUND_HALF_UP, net intermediate/final and gross+adjustment=net. It does not weaken the check or alter production calculation. Corrected dry run PASS, then separately authorized-by-request apply PASS. No sample existed after the failed/rolled-back attempts.

Validation: **10 tests / 4 subtests PASS** on the isolated test database for vocabulary/source/filter/context/permission boundaries; **44/44 sample HTTP pages PASS** transactionally before commit; **22/22 installed real Chrome cases PASS** on the persisted local sample, spanning 1440/1024/390 quantities, baseline, work history, work detail and claims plus remaining document states. Before/after persisted verification proves browser viewing changes no sample business row. Screenshots with real large/fractional values were directly inspected. Ruff check/format, Django system/template checks and scoped whitespace PASS. Concurrent drawer/procurement work remains separately owned and preserved.

- [Open persisted sample](http://127.0.0.1:8000/contracts/931cc7d4-1a8a-408f-903f-9c6170504d2b/)
- [Human review guide: exact quantities, rates, amounts and record links](../../../output/contract-hub-remediation/work-sample/REVIEW.md)
- [Final validation](../../../output/contract-hub-remediation/work-sample/validation.json)
- [Applied sample manifest](../../../output/contract-hub-remediation/work-sample/result.json)
- [Rollback dry run](../../../output/contract-hub-remediation/work-sample/dry-run.json)
- [Initial rounding-verifier failure](../../../output/contract-hub-remediation/work-sample/initial-rounding-check.txt)
- [Focused terminology/source tests](../../../output/contract-hub-remediation/work-sample/terminology-tests.txt)
- [Persisted Chrome verification](../../../output/contract-hub-remediation/work-sample/browser-verification.json)
- [Desktop real sample quantities](../../../output/contract-hub-remediation/work-sample/browser/sample-review-sample-quantities-1440.png)
- [Mobile real sample work detail](../../../output/contract-hub-remediation/work-sample/browser/sample-review-sample-work-detail-390.png)

```text
F1-F4 FRONTEND FOUNDATION PRESERVED: PASS (attributable task scope)
TOM SELECT CONFORMANCE: PASS (existing selector behavior retained)
SWEETALERT2 CONFORMANCE: PASS (existing shared interaction contracts retained)
SHARED NAVIGATION PRESERVED: PASS (no shared-navigation edit by this task)
OFFLINE RUNTIME PRESERVED: PASS (no external runtime reference or dependency added)
```

This is a manual-review sample, not Human UAT acceptance or production certification. Changes remain uncommitted. No CEP Registry lifecycle update or Git write.
