# BONIRA Record Detail rollout

Status: **Ready for visual review. No Product Owner acceptance asserted.**

Working branch: `main`; entry/final HEAD: `59f2fde64fc3684f09871b82a2b1945905c28aab`.
No commit or push. The extensive pre-existing dirty tree and concurrent Equipment
Operations workspace edits were preserved. Entry evidence: `initial-status.txt`
and `initial-diff-stat.txt`. This report describes only the incremental Detail task.

## Standard and inventory

- Standard: `docs/ui-guidelines.md`, section 17, with section 42 retained.
- Supplied image preserved unchanged: `docs/detail-page-reference.png`.
  SHA-256: `6B2879CFC732184653865D345048C5B96D08273DAE88B87F0EEED5A44D18AFCB`.
- Reuse instructions: `templates/components/README.md`, Record Detail guide.
- [Complete route classifications](catalog.md), machine-readable `catalog.json`;
  discovery source: `catalog-discovery.json`.

46 named MVP-visible detail routes were classified. Nine standard records were
migrated: **Expense, Safety Incident, Quality Issue, Equipment master, operational
Business Party, Project Phase, Project Site, Equipment Maintenance and Equipment
Work Order**.

Seven specialized/hybrid routes received shared visual conventions while retaining
their existing body: **Material, Material Category, Expense Category, Organization
Member, Daily Report, Document and Warehouse**. Materials/categories keep their
combined Compact detail/editor and its real fields and actions. DMS retains
versions, quarantine/download restrictions, source links, retention and archive.
Daily Report retains operational entry forms, HSE references and documents.
Warehouse retains its stock/balance and transaction workspace.

The other 30 routes retain their specialized structure: Contract/contractual,
Billing/compliance/guarantee/measurement/claims, Estimate, Procurement, inventory
transactions/counts/transfers, Workflow version administration, governed Party,
protected document routes, field observation, Workforce identity and Timekeeping.
Projects Detail remains under the explicit Projects Exception in section 30.
Per-route reasons and compatibility aliases are listed in `catalog.md`.
Zero routes already used the newly introduced exact shared Detail component at
entry; existing specialized designs are not claimed to have passed this review.

## Reuse and presentation

Reused `page_header`, breadcrumbs, `form_section_header`, `form_field`,
`form_errors`, `status_badge`, global `list_working_context`, field journey,
existing DMS/evidence panels, related lists and existing Compact cards/footers.

Added the small `record_detail_page`, `record_summary_item`, `record_detail_value`
and `record_review_history` components and opt-in `erp_record_detail.css`.
The base provides the same application context interaction as Warehouse List,
with no standalone duplicate selector bar. CSS uses existing tokens, compact
surfaces, definition lists and controlled wrapping. Actual sections use ordinary
anchor links, remain visible without JavaScript and have no empty simulated tabs.

Resolved inconsistent identity/action placement, non-semantic statuses, fragmented
information cards, detached context presentation, oversized summary wrapping at
1024px and missing historical context. Existing Expense dates/actors/reasons and
ordered tenant-scoped HSE review revisions supply history; no audit events are
invented. Revision actors are fetched with the revision query.

Expense has no supported Detail Edit/Clone/Print routes, so those illustrated
buttons were not introduced. Existing Submit, allocation, independent approval,
Return and Void endpoints remain. Maker approval and approved-record Void controls
are suppressed to match existing service restrictions; backend rules are unchanged.

Browser inspection also found duplicate IDs across Daily Report entry forms.
Distinct `auto_id` patterns fix label association while preserving POST names,
widget targets, choices and validation. An existing English allocation label was
localized through `ExpenseAllocationForm.Meta.labels`, without changing fields.

## Files

[Exact incremental file list](changed-files.json): 31 source/documentation/test/
reference paths, plus this evidence directory. It includes 13 consuming templates,
four new components, six presentation-context views, one form-label change, the
shared stylesheet, documentation/reference, two focused browser suites and one
browser-driver navigation polling fix. The driver now tolerates a transient absent
`document.body` during real navigation; it still reports actual script exceptions.

This task changes no models, migrations, validation, business services,
authorization, tenant/project isolation, Product Surface, `base.html`, accepted
List designs, Compact/Sectioned components or their styles. Such files may already
be dirty from earlier authorized work; entry evidence distinguishes that work.

## Verification and screenshots

Actual installed Chrome through the existing CDP runner against Django's isolated
LiveServer and the dedicated test PostgreSQL database; synthetic tenant records.
The operational development database was not populated by these tests.

- All 16 adopted route outcomes captured at **1440, 1024 and 390px**.
- Six Expense states: draft, recorded, submitted, returned, approved, void;
  an independent reviewer and a denied user; real Void POST/reason persistence,
  section link, Tab focus, browser Back and refresh.
- Safety/Quality real Review POSTs; existing services carry records through their
  governed lifecycles to closed. Closed pages retain actual review history, have
  no mutation form and do not mutate source records on reads.
- Denied access for all 15 non-Expense routes; project-restricted HSE read without
  action authority; out-of-project Warehouse denied; cross-tenant Material Category
  denied; read-only Material/Category/ExpenseCategory controls stay disabled.
- Unique field IDs and valid label targets on Equipment, Document and Daily Report.
  Real Daily Report labor submission succeeds with unchanged names; material
  widget target IDs remain valid.
- RTL, valid section targets, one primary heading, no page horizontal overflow
  and no JavaScript exceptions on successful Detail scenarios.
- Compact Create/Edit regression exercises validation, value retention, actual
  browser Save/Cancel and existing field grids/context/footer conventions.
- Allocation scope tests exercise existing capability, membership, tenant,
  project/WBS, budget, structure, amount and lifecycle guards.

[Screenshot gallery](gallery.html) links viewport, genuine full-page and bottom
captures, all route widths, Expense pilot before/after and closed HSE states.
Before captures exist for Expense only (six states at 1440px, top/bottom viewport).
Other originals are source snapshots, not claimed before-browser screenshots.
Reference comparison used actual captured rendering: compact identity/actions,
actual summary/status, tinted section headings, two-column desktop information
and mobile stacking. Existing operational bodies deliberately retain their
specialized layout.

Final results:

| Check | Result | Evidence |
|---|---|---|
| Five Detail browser tests + 12 allocation scope tests | **17 PASS; 42 subtests PASS** | `final-detail-tests.txt`, `final-detail-tests.xml` |
| Compact regression + operational accessibility/submission rerun | **2 PASS; 26 subtests PASS** | `final-regression-tests.txt`, `final-regression-tests.xml` |
| Successful distinct Detail Chrome scenarios | **80**, all RTL, HTTP 200, no page horizontal overflow or JS exceptions | `browser-summary.json`, `adopters/batch-*.json`, `expense/batch-*.json` |
| Django system check | **PASS**, no issues | `system-check.txt` |
| Migration drift | **PASS**, no changes detected | `migration-check.txt` |
| Changed Python/form/test files Ruff | **PASS**, with existing Organizations import-order exception separately attributed | `ruff-check.txt`, `organization-ruff-check.txt`, `baseline-organization-ruff.txt` |
| Browser driver syntax / scoped diff whitespace | **PASS** | `node --check scripts/verification/mvp02_browser.mjs`; `diff-check.txt` |
| Existing explicit POST routes | **PASS**, all preserved across 12 consuming templates | `source-contract-check.json` |

The two test-log rows overlap one accessibility method: **18 distinct test methods**
were exercised, rather than claiming 19 unique tests. Compact regression covers
41 actual Chrome scenarios in addition to the 80 distinct Detail scenarios.
Final targeted checks supersede earlier passing pilot captures. Earlier failed
accessibility and harness-race logs are retained for traceability; both causes were
fixed and rerun successfully.

## Limits and remaining review

Follow-up continuation: existing DMS availability/version behavior, invalid-upload
rendering, related-document expansion, long record identity and source return were
additionally verified in actual Chrome at 1440/1024/390. **3 focused tests PASS**,
with the extended source-return method rerun successfully; **27 distinct Chrome
scenarios**. Evidence: `follow-up/tests.txt`, `follow-up/source-return-tests.txt`,
`follow-up/summary.json`, and [follow-up gallery](follow-up/gallery.html).
Clean/unsafe/unassessed current versions, an old clean version with a new
quarantined current version, two clean versions, and a read-only user without
download authority were exercised. Actual download responses also preserve
availability checks and attachment delivery. No product code changes were needed
in this follow-up; entry-hash comparison is `follow-up/protected-source-check.json`.

- No in-scope implementation blocker remains. Product Owner
  visual review is still required.
- Excluded specialized routes and hidden FULL_ERP consumers were not browser
  certified by this rollout. The shared read-only component retains their supplied
  rows/disclosures, but no visual claim is made for those hidden consumers.
- Expense state fixtures prove presentation and action visibility; they do not
  establish a new financial approval/ledger qualification. Allocation guards are
  independently exercised by the existing focused tests.
- Every possible related-record volume, DMS clean/quarantined/download/retention
  combination and lifecycle branch on every specialized page was not exhaustively
  enacted. Existing backend enforcement is retained.
- Chrome responsive emulation and keyboard access were tested; physical mobile
  devices and a screen-reader audit were not performed.
- Whole-file Ruff has a pre-existing import-order I001 in Organizations views,
  reproduced from HEAD (`baseline-organization-ruff.txt`). It was left untouched;
  other checks for that file pass with this existing diagnostic excluded.
