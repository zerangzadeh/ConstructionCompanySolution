# BONIRA User journey catalog

Reuse the original MVP-08 guide under docs/governance/mvp for each UAT-01–15, including the exact historical seed and browser actions. Add the current-baseline assertions below. CV cases cover additional boundaries or depth. E2E family links refer to existing journey IDs in the current CSV and are planning associations, with row-level runtime coverage still pending.

[Exact route/action worklist](TEST_EXECUTION_MATRIX.csv)

## Scenarios

<a id="uat-01"></a>

### UAT-01 · Sign in and find authorized work

**Batch and status** · B01 · NOT_RUN · 6 worklist rows

**Actors and seed** · operator, restricted, anonymous. MVP08 operator, multi-member and inactive accounts

**Browser sequence** · Sign in. Compare desktop/mobile menus, switch tenant, search an authorized project, open it and log out.

**Expected UI** · Role and active company determine cards, menus and results. Revisit a bookmark after logout and try an external next URL.

**Persisted state, cross-module and negative checks** · Compare session user/company and search hits with membership and object scope. Probe invalid password and no active membership.

**Evidence** · Login/menu and safe redirect/search traces.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-01. E2E-AUTH (8 existing IDs, E2E-AUTH-001 through E2E-AUTH-008). E2E-NAV (1 existing IDs, E2E-NAV-001 through E2E-NAV-001). E2E-ORG (25 existing IDs, E2E-ORG-001 through E2E-ORG-025).

<a id="uat-02"></a>

### UAT-02 · Set up project, site and phases

**Batch and status** · B02 · NOT_RUN · 23 worklist rows

**Actors and seed** · project lead, site user, viewer. Two sibling sites/projects and a foreign tenant. Unique project code.

**Browser sequence** · Create project and contextual site. Open All Sites, apply filters and follow contextual return. Exercise phase/WBS/activity and archive where offered.

**Expected UI** · Parent defaults, breadcrumbs and selectors stay consistent. Confirmation and empty/error states identify next action.

**Persisted state, cross-module and negative checks** · Compare Project, ProjectSite and control ancestry in dashboard and downstream selectors. Forge parent IDs and duplicate code. Verify denied archive and no residual rows.

**Evidence** · URLs, selector payload and parent/child snapshots.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-02. E2E-PROJ (45 existing IDs, E2E-PROJ-001 through E2E-PROJ-045).

<a id="uat-03"></a>

### UAT-03 · Create, submit and review daily work

**Batch and status** · B03 · NOT_RUN · 14 worklist rows

**Actors and seed** · site recorder, independent reviewer, viewer. Authorized active project/site and synthetic labor, equipment and material records

**Browser sequence** · Create a daily report and add supported entries. Submit, approve independently and return a separate draft. Open linked context and print.

**Expected UI** · Totals and states agree across detail, project and print. Invalid hours/context preserve authorized input.

**Persisted state, cross-module and negative checks** · Compare report and entry records, workflow state and actor audit. Probe replay, foreign site, invalid shift and wrong reviewer.

**Evidence** · Draft/review/print captures and state diff.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-03. E2E-PROJ (45 existing IDs, E2E-PROJ-001 through E2E-PROJ-045). E2E-FIELD (15 existing IDs, E2E-FIELD-001 through E2E-FIELD-015).

<a id="uat-04"></a>

### UAT-04 · Allocate workforce and keep time records distinct

**Batch and status** · B02 · NOT_RUN · 32 worklist rows

**Actors and seed** · workforce maintainer, timekeeper, reviewer. Synthetic non-login Person, work relationship, two sites, calendar/shift and unconfigured site

**Browser sequence** · Create field worker and team. Assign, end and reassign. Record attendance, timesheet and overtime separately. Compare workbench tabs.

**Expected UI** · Eligible workers, site context and Jalali dates persist. Unconfigured calendar shows actionable guidance.

**Persisted state, cross-module and negative checks** · Check Person/WorkRelationship and assignment effective dates, legacy compatibility and authoritative minutes. Probe duplicate ID, conflicting dates, foreign worker and no calendar.

**Evidence** · Worker ID redacted, three time views and stored minute/scope values.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-04. E2E-FIELD (15 existing IDs, E2E-FIELD-001 through E2E-FIELD-015). E2E-WORK (21 existing IDs, E2E-WORK-001 through E2E-WORK-021). E2E-TIME (22 existing IDs, E2E-TIME-001 through E2E-TIME-022).

<a id="uat-05"></a>

### UAT-05 · Allocate equipment and track usage

**Batch and status** · B04 · NOT_RUN · 20 worklist rows

**Actors and seed** · controller, operator, reviewer. Ready asset, site, eligible and ineligible operators and opening meter 100

**Browser sequence** · Assign asset. Log meter 103 and usage. Open maintenance and work order, move through permitted lifecycle and compare project context.

**Expected UI** · Scoped asset/operator choices and clear units, dates and maintenance status.

**Persisted state, cross-module and negative checks** · Compare assignment, meter/usage and maintenance events with project/daily report links. Reject overlapping allocation, lower meter without correction, wrong operator and replay.

**Evidence** · Assignment/usage/work-order capture and row/audit diff.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-05. E2E-EQP (21 existing IDs, E2E-EQP-001 through E2E-EQP-021).

<a id="uat-06"></a>

### UAT-06 · Track safety and quality operational and review lifecycles

**Batch and status** · B04 · NOT_RUN · 17 worklist rows

**Actors and seed** · site reporter, assignee, record reviewer. Incident, issue and synthetic same-site evidence

**Browser sequence** · Create incident and issue, assign and follow up. Submit record reviews, return/revise one and approve the other where configured.

**Expected UI** · Separate operational and review badges. Reasons and actions follow state and role.

**Persisted state, cross-module and negative checks** · Compare incident/issue, action and immutable review revisions. Reject wrong reviewer, invalid transition, foreign site/version. Review approval must preserve independent operational state.

**Evidence** · Both timelines, evidence versions and audit.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-06. E2E-HSEQ (18 existing IDs, E2E-HSEQ-001 through E2E-HSEQ-018). E2E-SAF (7 existing IDs, E2E-SAF-001 through E2E-SAF-007). E2E-QA (7 existing IDs, E2E-QA-001 through E2E-QA-007).

<a id="uat-07"></a>

### UAT-07 · Create a contract and verify an existing estimate association

**Batch and status** · B05 · NOT_RUN · 8 worklist rows

**Actors and seed** · estimator, reviewer, contract maintainer. Two estimate revisions, project, eligible parties, configured contract terms

**Browser sequence** · Create an estimate with Decimal lines and approve the intended revision. Create a contract from the Contracts list, select the project, party and direction, and open its detail. Use an already associated estimate and contract to verify links to the project, estimate and supported measurement baseline. Open a separate, unlinked estimate and verify that it offers no conversion action.

**Expected UI** · Project, party, commercial values, breadcrumb and current version agree. The independent estimate retains its original identity and history. Automatic estimate-to-contract conversion is deferred to the [post-MVP roadmap](../../../ROADMAP.md#12-deferred-and-post-v1-scope) under BON-DEF-0033.

**Persisted state, cross-module and negative checks** · Calculate line quantities × rates with estimate rounding. Confirm the approved revision, existing association, and independently created contract. Probe wrong project or party and a write against a finalized estimate revision. Verify that viewing an unlinked estimate creates no contract.

**Evidence** · Estimate, contract and hub screens and saved Decimal values.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-07. E2E-EST (15 existing IDs, E2E-EST-001 through E2E-EST-015). E2E-CON (26 existing IDs, E2E-CON-001 through E2E-CON-026).

<a id="uat-08"></a>

### UAT-08 · Measure and price claim from eligible sources

**Batch and status** · B05 · NOT_RUN · 13 worklist rows

**Actors and seed** · surveyor, verifier, claim preparer. Approved baseline, verified and unverified progress, configured terms, MVP08 specimen

**Browser sequence** · Open baseline, submit/verify measurement where exposed, select eligible sources and build claim. Compare current/previous quantities, period and deductions.

**Expected UI** · Missing terms lead to recovery guidance. Source labels and deductions are readable.

**Persisted state, cross-module and negative checks** · Recompute each persisted quantity/rate and adjustment using saved term version, bases and rounding. For identical MVP08 specimen verify gross 50,000,000 and net 36,700,000 IRR. Reject unverified, duplicate or foreign source.

**Evidence** · Claim detail, source/version rows and arithmetic reconciliation.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-08. E2E-BIL (37 existing IDs, E2E-BIL-001 through E2E-BIL-037). E2E-EST (15 existing IDs, E2E-EST-001 through E2E-EST-015). E2E-CON (26 existing IDs, E2E-CON-001 through E2E-CON-026).

<a id="uat-09"></a>

### UAT-09 · Return, approve and revise without overwriting history

**Batch and status** · B05 · NOT_RUN · 4 worklist rows

**Actors and seed** · maker, independent reviewer, viewer. Approved original and submitted draft, audit and configured correction reason

**Browser sequence** · Return draft, resubmit if allowed, independently approve. Create allowed replacement/cancellation of original and follow history links.

**Expected UI** · Current and prior claims distinct. Rejected or stale action leaves useful message.

**Persisted state, cross-module and negative checks** · Compare immutable original, successor linkage, work item, authorized actor and audit. Race two approvals and try self-approval, no reason, foreign ID and replay. Check for implicit settlement/posting.

**Evidence** · Claim/work-item lineage, before/after and race results.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-09. E2E-BIL (37 existing IDs, E2E-BIL-001 through E2E-BIL-037). E2E-WF (24 existing IDs, E2E-WF-001 through E2E-WF-024).

<a id="uat-10"></a>

### UAT-10 · Reconcile every XLSX and print surface

**Batch and status** · B08 · NOT_RUN · 19 worklist rows

**Actors and seed** · output reader, scoped user, foreign user. Multiple pages, excluded site, empty results and approved claim

**Browser sequence** · Use each B08 output row. Filter/sort, download actual XLSX, print A4 and return. Try direct URL in restricted sessions.

**Expected UI** · One action, preserved query, readable headers, page breaks and print-only business content.

**Persisted state, cross-module and negative checks** · Check MIME, OOXML contents, numeric typing, formula-like text, authorized filtered count beyond page and saved totals. Verify zero writes and deny scope probes.

**Evidence** · Workbook, print PDF, hashes and field/count diff.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-10. E2E-REP (23 existing IDs, E2E-REP-001 through E2E-REP-023). E2E-BIL (37 existing IDs, E2E-BIL-001 through E2E-BIL-037). E2E-PROC (38 existing IDs, E2E-PROC-001 through E2E-PROC-038). E2E-INV (22 existing IDs, E2E-INV-001 through E2E-INV-022). E2E-EXP (11 existing IDs, E2E-EXP-001 through E2E-EXP-011). E2E-TIME (22 existing IDs, E2E-TIME-001 through E2E-TIME-022). E2E-EQP (21 existing IDs, E2E-EQP-001 through E2E-EQP-021). E2E-EST (15 existing IDs, E2E-EST-001 through E2E-EST-015).

<a id="uat-11"></a>

### UAT-11 · Take approved purchase need into explicit RFQ scope

**Batch and status** · B06 · NOT_RUN · 9 worklist rows

**Actors and seed** · requester, approver, buyer. MVP08 PR-F and MVP08-UAT-PR clones, independent PR grants

**Browser sequence** · Create/add line, submit and approve independently. Start RFQ and select exact source lines and quantities. Reject or cancel separate copy.

**Expected UI** · Clear PR status and RFQ context; RFQ needs explicit scope selection.

**Persisted state, cross-module and negative checks** · Check request, item, work item and RFQ scope records. Reject self-approval where barred, foreign site, zero and excess quantity, replay. Confirm no implicit RFQ.

**Evidence** · PR/RFQ screens, status and scope diff.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-11. E2E-PROC (38 existing IDs, E2E-PROC-001 through E2E-PROC-038). E2E-WF (24 existing IDs, E2E-WF-001 through E2E-WF-024).

<a id="uat-12"></a>

### UAT-12 · Issue, open and evaluate sealed offers

**Batch and status** · B06 · NOT_RUN · 39 worklist rows

**Actors and seed** · preparer, supplier, custodian, opening approver, evaluator, award reviewer. MVP08-RFQ02 v1, two suppliers, synthetic sealed artifacts and independent policies

**Browser sequence** · Prepare/issue, invite, submit or capture quotes, try early comparison, complete protected opening, evaluate and award. Exercise addendum on clone.

**Expected UI** · Supplier sees own context and receipt. Sealed offers hidden before authorized opening. Version/decision labels clear.

**Persisted state, cross-module and negative checks** · Check grant, RFQ/quote version, sealed custody, approval, evaluation and award. Try replay, wrong supplier, raw file, early open, same actor and stale award. Verify failed capture rollback.

**Evidence** · Redacted portal/RFQ timeline and decision/version witnesses.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-12. E2E-PROC (38 existing IDs, E2E-PROC-001 through E2E-PROC-038). E2E-PARTY (17 existing IDs, E2E-PARTY-001 through E2E-PARTY-017). E2E-WF (24 existing IDs, E2E-WF-001 through E2E-WF-024).

<a id="uat-13"></a>

### UAT-13 · Issue order and receive partially then fully

**Batch and status** · B06 · NOT_RUN · 15 worklist rows

**Actors and seed** · buyer, receiver, reader. Issued quote and award, PO line quantity 5 with compatible unit

**Browser sequence** · Create PO from award, issue, receive 2 and inspect remaining 3, then receive 3. Check GRN links.

**Expected UI** · Award/PO source and quantity badges remain accurate.

**Persisted state, cross-module and negative checks** · Compare PO/GRN lines and remaining quantity. Check no stock increase until explicit posting. Attempt 4 with 3 left, wrong item or UOM, duplicate and simultaneous final receipts.

**Evidence** · PO, two GRNs, balances and losing-request diff.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-13. E2E-PROC (38 existing IDs, E2E-PROC-001 through E2E-PROC-038). E2E-INV (22 existing IDs, E2E-INV-001 through E2E-INV-022).

<a id="uat-14"></a>

### UAT-14 · Post and reverse inventory with provenance

**Batch and status** · B06 · NOT_RUN · 12 worklist rows

**Actors and seed** · stock keeper, independent reviewer, viewer. Warehouse, eligible receipt, MVP08-IN01 showing 2 units, policy roles

**Browser sequence** · Explicitly post draft receipt movement. Reverse with unique reference and reason after approval where applicable. Open original and reversal.

**Expected UI** · Current balance and reversible action align with posted/reversed badge. Original is visible and linked.

**Persisted state, cross-module and negative checks** · Verify opening +2 then opening, StockTransaction lineage, receipt unchanged, no duplicate or GL side effect. Attempt second reversal, duplicate posting, foreign warehouse and race.

**Evidence** · Movement/balance snapshots and actor audit.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-14. E2E-INV (22 existing IDs, E2E-INV-001 through E2E-INV-022). E2E-PROC (38 existing IDs, E2E-PROC-001 through E2E-PROC-038). E2E-WF (24 existing IDs, E2E-WF-001 through E2E-WF-024).

<a id="uat-15"></a>

### UAT-15 · Cross-check role, tenant and responsive boundaries

**Batch and status** · B01 · NOT_RUN · 26 worklist rows

**Actors and seed** · limited, foreign, project/site-scoped, tenant admin, PA-only. T-A and T-B with identical labels and distinct IDs

**Browser sequence** · Replay permitted/denied navigation at 1440/1024/390. Substitute IDs in detail, selector, export, download and POST. Open hidden routes from address bar.

**Expected UI** · Authorized links only, safe denial and no page overflow. No data in errors or search/selector counts.

**Persisted state, cross-module and negative checks** · Assert request boundary, CSRF, scoped query, unchanged state and no foreign labels across direct or dynamic links.

**Evidence** · Viewport/denial captures and before/after snapshots.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · docs/governance/mvp/MVP-08_HUMAN_UAT_GUIDE.md § UAT-15. E2E-NAV (1 existing IDs, E2E-NAV-001 through E2E-NAV-001). E2E-ORG (25 existing IDs, E2E-ORG-001 through E2E-ORG-025). E2E-AUTH (8 existing IDs, E2E-AUTH-001 through E2E-AUTH-008).

<a id="cv-auth-01"></a>

### CV-AUTH-01 · Validate public recovery and profile

**Batch and status** · B01 · NOT_RUN · 7 worklist rows

**Actors and seed** · anonymous, active and inactive accounts. Isolated mail sink and two browser sessions

**Browser sequence** · Request reset for eligible, unknown and inactive accounts, consume synthetic token, retry used/expired token, change profile and force initial password change fixture.

**Expected UI** · Generic response, usable validation and safe post-reset landing.

**Persisted state, cross-module and negative checks** · Check recipient, token/replay, old session/credential and no enumeration; test throttle and unsafe return.

**Evidence** · Redacted mail and session trace.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-AUTH (8 existing IDs, E2E-AUTH-001 through E2E-AUTH-008).

<a id="cv-guard-01"></a>

### CV-GUARD-01 · Validate hidden and mixed profile routes

**Batch and status** · B01 · NOT_RUN · 269 worklist rows

**Actors and seed** · anonymous, ordinary, tenant admin, PA-only. Independent MVP and FULL_ERP processes/copies

**Browser sequence** · Probe every hidden row with syntactically valid synthetic objects. For mixed ESS test leave, overtime, correction and restricted kinds. Compare portal, search, workflow and direct links.

**Expected UI** · MVP deny/login as coded. Valid MVP exceptions remain permission scoped. FULL_ERP runs underlying original guard.

**Persisted state, cross-module and negative checks** · Verify profile result versus view authz, no tenant/session change or writes. Record Django Admin mount separately.

**Evidence** · Direct-route traces and menu evidence.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-NAV (1 existing IDs, E2E-NAV-001 through E2E-NAV-001). E2E-ORG (25 existing IDs, E2E-ORG-001 through E2E-ORG-025). E2E-WORK (21 existing IDs, E2E-WORK-001 through E2E-WORK-021). E2E-REP (23 existing IDs, E2E-REP-001 through E2E-REP-023).

<a id="cv-time-01"></a>

### CV-TIME-01 · Correct time and handle leave/mission/overtime

**Batch and status** · B02 · NOT_RUN · 13 worklist rows

**Actors and seed** · timekeeper, distinct reviewer, explicitly linked worker. Finalized attendance, valid shift and competing absence

**Browser sequence** · Request correction and review. Submit and review leave, mission and overtime separately. Check My Requests source detail.

**Expected UI** · Original history and state stay clear. No implicit identity or work log.

**Persisted state, cross-module and negative checks** · Check correction/approval minutes and source links. Probe overlap, wrong reviewer, foreign worker, absent identity and replay.

**Evidence** · Before/after history, evidence and negative traces.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-TIME (22 existing IDs, E2E-TIME-001 through E2E-TIME-022). E2E-WORK (21 existing IDs, E2E-WORK-001 through E2E-WORK-021). E2E-WF (24 existing IDs, E2E-WF-001 through E2E-WF-024).

<a id="cv-exp-01"></a>

### CV-EXP-01 · Track expenses and petty cash

**Batch and status** · B04 · NOT_RUN · 15 worklist rows

**Actors and seed** · preparer, reviewer, cash custodian, reader. Two amounts 125000 and 75000 IRR, category, site and configured petty cash

**Browser sequence** · Create expense, attach eligible receipt where offered, submit/review and reject a separate copy. Compare filtered petty-cash summary and outputs.

**Expected UI** · Status, amount, scope and available actions agree across detail and summary.

**Persisted state, cross-module and negative checks** · Verify Expense and cash records, persisted totals and audit; reject invalid amount, foreign category/document, replay and wrong reviewer. Check no unauthorized Treasury/GL effect.

**Evidence** · Screens, state/balance diff and output proof.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-EXP (11 existing IDs, E2E-EXP-001 through E2E-EXP-011).

<a id="cv-eqp-01"></a>

### CV-EQP-01 · Validate operations and equipment cost handoff

**Batch and status** · B04 · NOT_RUN · 14 worklist rows

**Actors and seed** · controller, cost reviewer, scoped observer. Qualification, downtime, fuel, usage and effective policy/rate

**Browser sequence** · Log fuel/downtime and work order evidence. Create cost allocation, finalize/reverse and review handoff when authorized.

**Expected UI** · Distinct operation, allocation and projection state; source and confirmation clear.

**Persisted state, cross-module and negative checks** · Recompute Decimal amount from source and effective rate. Check immutable allocation, policy and handoff audit. Try expired operator, wrong project, duplicate finalize.

**Evidence** · Source, policy and history snapshots.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-EQP (21 existing IDs, E2E-EQP-001 through E2E-EQP-021). E2E-PROJ (45 existing IDs, E2E-PROJ-001 through E2E-PROJ-045).

<a id="cv-bil-01"></a>

### CV-BIL-01 · Cover conditional payable and commercial control branches

**Batch and status** · B05 · NOT_RUN · 48 worklist rows

**Actors and seed** · commercial preparer, independent reviewer, scoped reader. Payable contract, eligible measurement, retention rules and synthetic guarantee/clearance; statutory configuration off

**Browser sequence** · Probe route exposure and navigation. Exercise payable measurement and certificate, guarantee revision, evidence and release where enabled. Inspect statutory activation guard separately.

**Expected UI** · Business purpose and version history clear. Unconfigured branches give safe denial/guidance.

**Persisted state, cross-module and negative checks** · Verify payable/guarantee/evidence/release snapshots, approved lineage and amounts. Try missing policy, invalid clearance, excess release and foreign IDs. No implicit statutory activation.

**Evidence** · Screens, policy snapshot and arithmetic/negative traces.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-BIL (37 existing IDs, E2E-BIL-001 through E2E-BIL-037). E2E-CON (26 existing IDs, E2E-CON-001 through E2E-CON-026).

<a id="cv-inv-01"></a>

### CV-INV-01 · Validate reservation, stock count, transfer and valuation

**Batch and status** · B06 · NOT_RUN · 13 worklist rows

**Actors and seed** · stock controller, count approver, receiver. Two warehouses, known balance and count variance, valuation snapshot

**Browser sequence** · Reserve/release, submit and approve/post count separately. Dispatch/accept transfer and inspect custody/valuation workbenches.

**Expected UI** · Stock, reserved and in-transit quantities have distinct meanings and states.

**Persisted state, cross-module and negative checks** · Check authoritative quantities, count variance and immutable movement history. Probe over-reserve, wrong site, repeat dispatch/receipt and partial failure.

**Evidence** · Balances, source and audit snapshots.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-INV (22 existing IDs, E2E-INV-001 through E2E-INV-022).

<a id="cv-ten-01"></a>

### CV-TEN-01 · Manage tenant accounts, membership and grants

**Batch and status** · B07 · PASS · 15 worklist rows

**Actors and seed** · owner, local admin, limited, foreign admin. Two tenants, active owner, pending member and scoped project grant

**Browser sequence** · Open company settings and members, create eligible account, update member/grants and exercise recovery and connection request where offered. Switch among authorized companies.

**Expected UI** · Role and grant change shows correct target, reason and approval when required.

**Persisted state, cross-module and negative checks** · Verify Membership, assignment/scope and audit. Deny self-elevation, last owner removal, cross-tenant edit and platform duty grant.

**Evidence** · Membership, outbox and authz/audit diff.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-ORG (25 existing IDs, E2E-ORG-001 through E2E-ORG-025). E2E-AUTH (8 existing IDs, E2E-AUTH-001 through E2E-AUTH-008).

<a id="cv-wf-01"></a>

### CV-WF-01 · Configure declarative workflow and act in workbench

**Batch and status** · B07 · PASS · 11 worklist rows

**Actors and seed** · designer, candidate, assignee, requester, reviewer. Starter and draft, routed claim/PR, separate actor identities

**Browser sequence** · Configure allowed steps, publish eligible definition, submit source, open My Tasks, My Requests and Manager, then act or reassign/delegate where implemented.

**Expected UI** · Definition version, candidate and source links match active context. Invalid config gives actionable error.

**Persisted state, cross-module and negative checks** · Verify definition/version, instance, assignment, source state and audit as one transaction. Probe unregistered command, published edit, expired delegation, wrong actor and race.

**Evidence** · Version, queue and before/after rows.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-WF (24 existing IDs, E2E-WF-001 through E2E-WF-024).

<a id="cv-par-01"></a>

### CV-PAR-01 · Manage parties and materials used downstream

**Batch and status** · B07 · PASS · 22 worklist rows

**Actors and seed** · master maintainers, procurement reader. Eligible parties, unit/category, referenced and unreferenced masters

**Browser sequence** · Create party/roles and material/unit/category, select in PR/RFQ or contract, archive/deactivate where available.

**Expected UI** · Eligible options searchable, linked historical records readable.

**Persisted state, cross-module and negative checks** · Verify tenant ownership, duplicate rules and FK integrity. Probe wrong role/unit, foreign/inactive master and denied archive.

**Evidence** · Source and selectors, business keys and FKs.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-PARTY (17 existing IDs, E2E-PARTY-001 through E2E-PARTY-017). E2E-MAT (21 existing IDs, E2E-MAT-001 through E2E-MAT-021).

<a id="cv-rep-01"></a>

### CV-REP-01 · Reconcile operational metrics and tenant audit

**Batch and status** · B08 · NOT_RUN · 2 worklist rows

**Actors and seed** · report reader, auditor, restricted. Known procurement timestamps, stock quantities/values and audit events

**Browser sequence** · Open dashboard, compare filters and drilldown where present. Open tenant activity, filter actor/action/date where present.

**Expected UI** · MVP operational metrics and cutoff labels only. Audit event labels safe and scoped.

**Persisted state, cross-module and negative checks** · Reconcile procurement_cycle_time and inventory_quantity_value to eligible persisted results and cutoff. Check foreign events/metrics, hidden refresh route and no writes.

**Evidence** · Metric derivation and event/deny captures.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-REP (23 existing IDs, E2E-REP-001 through E2E-REP-023). E2E-AUD (3 existing IDs, E2E-AUD-001 through E2E-AUD-003).

<a id="cv-doc-01"></a>

### CV-DOC-01 · Upload, version, associate and download DMS content

**Batch and status** · B09 · NOT_RUN · 30 worklist rows

**Actors and seed** · uploader, linker, reader, downloader, foreign. Distinct PDF bytes A/B, eligible contextual targets, restricted linked context and disallowed file

**Browser sequence** · Upload A, add B, associate existing document and contextually upload on each allowed target. Inspect versions, download both and archive independent sample.

**Expected UI** · Scoped selectors, safe return, localized errors and exact version information.

**Persisted state, cross-module and negative checks** · Reconcile hashes, sizes, current pointer and typed/legacy links. Try foreign or mixed contexts, unsafe return, bad file and unsigned/expired intent. Check archive/expiry/quarantine denies bytes.

**Evidence** · Source/return screens, hashes, link records and deny traces.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-DOC (20 existing IDs, E2E-DOC-001 through E2E-DOC-020).

<a id="cv-doc-02"></a>

### CV-DOC-02 · Register specialized evidence pinned to exact version

**Batch and status** · B09 · NOT_RUN · 35 worklist rows

**Actors and seed** · domain recorder/reviewer, DMS reader/downloader, foreign. Eight Phase 3 targets, clean v1/v2, stale Material selection and quarantined evidence

**Browser sequence** · Run Safety, Quality, Material, Field Observation, Contractual Record, Guarantee, Compliance Evidence and Retention Release. Register/select v1 in source form, advance document and reopen the source-bound v1 evidence.

**Expected UI** · Current versus pinned versions distinct, suppressed rows/count for inaccessible evidence, quarantine label where authorized.

**Persisted state, cross-module and negative checks** · Compare exact domain relation/hash and revision. Try unlinked version, swapped actor/source, archived and restricted evidence, stale Material and approved mutation.

**Evidence** · Eight source/DMS captures and relation/version snapshots.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-DOC (20 existing IDs, E2E-DOC-001 through E2E-DOC-020). E2E-HSEQ (18 existing IDs, E2E-HSEQ-001 through E2E-HSEQ-018). E2E-CON (26 existing IDs, E2E-CON-001 through E2E-CON-026). E2E-MAT (21 existing IDs, E2E-MAT-001 through E2E-MAT-021). E2E-BIL (37 existing IDs, E2E-BIL-001 through E2E-BIL-037). E2E-FIELD (15 existing IDs, E2E-FIELD-001 through E2E-FIELD-015).

<a id="cv-field-01"></a>

### CV-FIELD-01 · Capture and reconcile field observation and follow-up

**Batch and status** · B03 · NOT_RUN · 8 worklist rows

**Actors and seed** · site recorder, coordinator, scoped reviewer. Draft field observation, project/site and eligible clean document

**Browser sequence** · Reach observation from its implemented source context, capture, attach evidence, and use supported transition or follow-up. Return to site or daily context.

**Expected UI** · Shows business labels, evidence version and relevant source links.

**Persisted state, cross-module and negative checks** · Check source FK, actor, history and idempotent operation key. Try repeated attach, invalid evidence and foreign site.

**Evidence** · Observation source and audit snapshots.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-FIELD (15 existing IDs, E2E-FIELD-001 through E2E-FIELD-015). E2E-PROJ (45 existing IDs, E2E-PROJ-001 through E2E-PROJ-045). E2E-DOC (20 existing IDs, E2E-DOC-001 through E2E-DOC-020).

<a id="cv-ui-01"></a>

### CV-UI-01 · Run route-level UI acceptance across entry patterns

**Batch and status** · B11 · NOT_RUN · 302 worklist rows

**Actors and seed** · entitled and limited per route, PO observer. Synthetic populated, empty and validation-error variants, Chromium

**Browser sequence** · Apply applicable UI-01 to UI-13 to every included page row. Check filters, dialogs and output actions where discovered. Trace unresolved affordances against rendering.

**Expected UI** · Persian RTL, keyboard and layout standards hold at all required widths.

**Persisted state, cross-module and negative checks** · Measure overflow and focus, capture console/network, confirm context and denied controls. Mark missing fixture or unreachable state BLOCKED with exact cause.

**Evidence** · Route/state/width evidence index and PO decision record.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · E2E-NAV (1 existing IDs, E2E-NAV-001 through E2E-NAV-001).
