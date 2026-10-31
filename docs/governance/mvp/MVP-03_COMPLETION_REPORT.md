# MVP-03 — Contract & Billing Customer Journey

Implementation complete, 2026-10-29; functional/browser validation passed within
the coverage below, with independently attributed baseline test debt. Explicit
bounded Human request in the attached
MVP-03 instruction is the execution contract; these MVP packages are not CEPs.
No CEP is reopened and no Registry lifecycle change is implied.

## Shared Filter Bar and Contract List UX — 2026-10-31

Completed the explicit bounded Human UI/UX request on current `main`, HEAD and
`origin/main` `1f4a07062d017e678dfc3eabf8075a642a24ffd5`. Earlier local remediation
changes were preserved. No commit/push, branch/worktree, migration, MVP-04 or CEP
lifecycle changes.

Section 13 of `docs/ui-guidelines.md` now specifies the shared Filter Bar:
prominent business search, compact quick filters, optional secondary disclosure,
removable chips, clear-all, total count, inherited context, mobile disclosure and
GET/URL state. `components/filter_bar.html` / `filter_bar_field.html` and
`core.list_filters.build_filter_bar` supply reusable presentation state and markup.
The small `erp_filter_bar.js` only controls responsive disclosure layout; the
existing explicit-submit table script continues to navigate by GET. Existing Tom
Select and Jalali widgets are reused without dependencies or a new UI framework.
No HTMX partial-refresh behavior is introduced.

Contract List is the only adopted list. Search covers Contract number/title,
Project name and both retained/current counterparty names. Quick filters are
Status, «سمت قرارداد» and optional searchable Project. The backend sides render
as «با کارفرما» and «با پیمانکار / تأمین‌کننده». The `side` query parameter avoids
colliding with the existing `direction` sort parameter. Existing number/title/
counterparty bookmarks remain supported under «فیلترهای بیشتر». The business
table and Create header placement are retained; Apply/Clear/count/chips belong to
the Filter Bar rather than a detached column-filter toolbar.

Inherited `project_id` is resolved through the existing Project context function,
shown as context and retained through filtering, chip removal and clear-all,
without a duplicate selector. The optional `project` filter remains transient and
removable. Project options, validation and paginated remote lookup at the same
Contract List route use only Projects from the existing tenant/object-scoped
Contract read source under `contracts.view`; no Create permission is required and
no role/permission behavior changes. Selected Projects beyond the initial 40
options are pinned on reload. Invalid filter values return no results with field
errors. Server scope and filtering remain authoritative; session context is not
mutated. Chip removal resets the page, retains other filters and preserves sort;
clear-all retains inherited context and sort.

Validation: **24 functional tests / 13 subtests PASS**, plus **two real Chrome
tests / 24 scenarios PASS** (17 new Filter Bar scenarios and seven existing
Project hub/handoff scenarios). The final combined run contains 25 tests including
the new browser test; the existing browser regression passed separately.
Coverage includes general/scoped lists, all search sources, combined filters,
business labels, chips/removal/clear, actual Back/Forward and refresh, desktop
1440px/mobile 390px, no-JavaScript rendering, authorized remote Project search
beyond the initial window, tenant/project isolation and explicit missing-read
permission denial. RTL, enhanced selectors, visible technical-label checks and
no horizontal page overflow passed. General/scoped desktop, secondary filters
and mobile general/scoped renders were visually inspected.

Ruff check/format (eight Python files), JavaScript syntax, Django system check and
diff whitespace PASS. Existing shared list-filter tests passed. Initial failures
were superseded test adaptations: preserving sort on clear, targeting list rather
than header search, checking the existing numeric DOM representation, and using
an explicit no-permission fixture instead of assuming a Member cannot read
Contracts. There is no unresolved attributable failure; broader unrelated ERP
regression and Human visual acceptance are not claimed.

Product mutations are limited to UI guidelines, the shared helper/templates/layout
script, Contract List form/read adapter and template. Models, migrations, domain
services, permissions, Product Surface, calculations and workflows remain
unchanged. Only isolated test database business data was written. The existing
Project browser evidence was copied into this task's evidence directory and its
previous artifacts restored after the regression run.

Evidence: [validation](../../../output/mvp-03/contract-filter-bar/VALIDATION.json),
[final test log](../../../output/mvp-03/contract-filter-bar/verified.log),
[Chrome captures](../../../output/mvp-03/contract-filter-bar/browser/),
[Project handoff regression](../../../output/mvp-03/contract-filter-bar/project-hub-regression.json),
[grounding](../../../output/mvp-03/contract-filter-bar/grounding.json) and
[source preservation](../../../output/mvp-03/contract-filter-bar/preservation.json).

SHARED FILTER BAR FOUNDATION: PASS

MVP-03 CONTRACT LIST FILTER UX: PASS

PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

## Contract direction remediation — 2026-10-31

Completed the explicit bounded Human request on current `main`. Entry HEAD and
`origin/main` were `6e7e6d05ad862854c439731b8a67aeb97943f772`. During validation,
an external Human checkpoint advanced both to
`1f4a07062d017e678dfc3eabf8075a642a24ffd5`, including the product fixes. Codex did
not run add, commit, push, merge, branch or worktree creation. Later test fixes and
this report remain local. Existing unrelated changes were preserved.

- Contract detail exposes the existing receivable Claim/baseline journey only for
  receivable contracts. Payable contracts retain related Estimates and have no
  receivable Claim or baseline links; no payable capability is newly exposed.
- Contract detail and contextual Claim List now share a presentation-only Create
  entry check against the existing permission/tenant-scoped Contract source:
  active, receivable, with a non-deleted Project. Invalid, empty, ambiguous,
  foreign, inaccessible and inactive references cannot create a CTA. Existing
  server-side Create guards remain authoritative and unchanged.
- Contract-scoped lists identify the authorized Contract, preserve it through
  status filtering/clear links, omit irrelevant Contract/Project search and ignore
  stale `q` values. Direct lists retain search and normal valid creation.
- Eligibility means the existing Create-entry rules, without adding new business
  rules: an active authorized receivable Contract without an approved baseline
  still opens the existing prerequisite guidance. Submission/calculation retains
  all existing baseline, term, regulatory, date and workflow validation.

Validation: **11 focused functional tests / 12 subtests PASS**; **one real Chrome
test / 15 scenarios PASS** in MVP, including actual contextual and general Claim
creation, payable desktop/mobile absence of receivable actions, invalid/inactive
contexts and real filter/clear submissions. All traversed document responses were
200; favicon requests are outside the journey. Representative mobile scoped List,
desktop payable Contract and successful Claim renders were inspected. Ruff check,
format check (six Python files), Django system check and diff whitespace PASS.

The initial broader affected run recorded 49 tests and 14 subtests passing, with
five failures: two new fixture/assertion issues (corrected), one old Claim List
search assertion updated to meaningful status filtering (now PASS), and two
unrelated prior-path assertions. The latter are the broad `AR` substring check
on unchanged Claim Detail and an Estimate approval-form lookup on unchanged
Estimate UI. Evidence confirms Claim Detail functions are structurally unchanged
and prior unrelated source bytes remain identical to entry. They are recorded as
UNRELATED_FAILURE, not a global regression PASS. An initial browser assertion also
matched the shared global search rather than the list filter; scoping that test
to `main` produced the final 15-scenario PASS without another product change.

Product touch set: `apps/billing/journey_views.py`, `apps/billing/views.py`,
`apps/contracts/views.py`, `apps/billing/templates/billing/claim_list.html`,
`templates/contracts/detail.html`. Tests add the two Contract direction modules
and update one scoped-filter assertion. No model, migration, calculation,
service/domain workflow, permission or Product Surface policy changed. No
Development/production business data writes, MVP-04 work, CEP lifecycle change,
production action or Human sign-off.

Evidence: [grounding](../../../output/mvp-03/contract-direction-remediation/grounding.json),
[validation](../../../output/mvp-03/contract-direction-remediation/VALIDATION.json),
[focused results](../../../output/mvp-03/contract-direction-remediation/final.log),
[final browser results](../../../output/mvp-03/contract-direction-remediation/browser.log),
[browser captures](../../../output/mvp-03/contract-direction-remediation/browser/),
[preservation/attribution](../../../output/mvp-03/contract-direction-remediation/preservation.json).

MVP-03 CONTRACT DIRECTION REMEDIATION: PASS

PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

## Estimate → Contract UX remediation — 2026-10-31

Completed the explicit bounded Human request on `main`, HEAD/local `origin/main`
`6e7e6d05ad862854c439731b8a67aeb97943f772`. Previous Estimate UX work and
other existing changes are preserved. No commit/push, migration or MVP-04 work.

The P6 read-only commercial timeline/comparison/exception workspace was inheriting
MVP exposure from the mixed `contracts` namespace. Under D2's capability-level
boundary and non-MVP Commercial exclusion, `contracts:commercial_review` now has
an explicit route override in the existing centralized `commercial` capability.
The Contract action uses the existing Product Surface template filter in addition
to its unchanged permission check. MVP hides the action and denies direct HTTP
access, including a forged `?profile=FULL_ERP`. Internal `FULL_ERP` verification
still exposes it only with existing business permission and object scope.
The route, permission catalog, models and backend read service are unchanged;
the authorized backend service is explicitly tested as active in MVP.

When an Estimate navigation reference resolves through the existing permitted,
tenant/project-scoped related-Estimate source, the business breadcrumb suffix is
**Project → Estimate → current Contract**. Project and Estimate remain real links
where permitted; Contract remains the final non-link with `aria-current="page"`.
The inserted Contracts collection is omitted only in that contextual case.
General entry, inaccessible Estimate context and malformed/foreign/unrelated/
ambiguous references retain the normal **Project → Contracts → current Contract**
hierarchy. The existing Home/conceptual group prefix and shared renderer remain.
No domain relationship, workflow, authorization or session behavior changed.

Validation: **42 focused functional/surface/permission tests / 16 subtests PASS**.
The five affected breadcrumb tests were rerun with exact contextual hierarchy,
invalid-context fallback and independent parent-permission assertions; PASS.
**Two real Chrome tests / 56 scenarios PASS**: 19 new scenarios across `MVP` and
`FULL_ERP`, desktop 1440px/mobile 390px, plus 37 existing breadcrumb scenarios.
They exercise Estimate → related Contract, actual breadcrumb returns to Estimate
and Project, normal direct Contract entry, hidden MVP action/direct URL denial,
permitted Full-ERP review opening and hiding/denial after permission removal.
RTL/current-item/real-link and horizontal overflow assertions pass. Representative
MVP mobile contextual/general and Full-ERP desktop captures were inspected.

Focused Ruff, Django system check, migration drift (`No changes detected`) and
`git diff --check` PASS. Fifteen backend/route/auth/shared sources match HEAD;
thirteen prior dirty source/test files remain byte-identical to entry. Product
mutations are limited to `core/product_surface.py`, Contract detail breadcrumb
construction and Contract detail action rendering. Existing Full-ERP review tests
now declare their verification profile explicitly. Only the isolated test DB was
written. Full ERP regression and production validation are not claimed.

Evidence: [validation](../../../output/mvp-03/estimate-contract-remediation/VALIDATION.json),
[test results](../../../output/mvp-03/estimate-contract-remediation/test-results.json),
[new browser captures](../../../output/mvp-03/estimate-contract-remediation/browser-index.json)
and [source preservation](../../../output/mvp-03/estimate-contract-remediation/static-source-evidence.json).
No CEP lifecycle/dependency/authorization records were changed. Human visual
acceptance remains pending.

`MVP-03 ESTIMATE-CONTRACT UX REMEDIATION: PASS`

`PRODUCT OWNER VISUAL ACCEPTANCE: PENDING`

## Estimate UX remediation — 2026-10-31

Completed the explicit bounded Estimate request on initially clean `main`, HEAD
`6e7e6d05ad862854c439731b8a67aeb97943f772`, equal to local `origin/main`.
No branch, commit, push, migration, new model or MVP-04 work.

| Requirement | Implementation and evidence |
| --- | --- |
| Preserve local Project context | Project hub Estimate create/recent links and all three Estimate list detail links retain validated `project_id`. Detail/create collection breadcrumbs return to the scoped Estimates list; validation, item submission, creation and approval redirects retain it. The existing explicit exit to global records remains available. Legacy `?project=` create entry remains supported and leads to the same scoped detail/list context. |
| Preserve scope and session | Context is reloaded from existing tenant/permission-scoped Project sources. Invalid, ambiguous, foreign, conflicting or mismatched detail/create context fails closed. Forged create parents remain invalid. General entry remains global, including for an Estimate-only reader without Project-view permission. Tests retain a different active Project **and Site**, without changing either session selection. |
| Remove technical item order | `sort_order` is absent from `EstimateItemForm`; forged form values are ignored. The existing transactional append service assigns the next current-revision sequence after acquiring its existing Estimate row lock. Explicit service order remains supported, stored fields and historical orders remain unchanged, and revision copies retain their order. Tests cover sequences 12→13→14, historical/current revision isolation, and real browser creation of rows 1→2. |
| Reject empty approval | The shared authoritative approval service rejects a current revision with no items using `برای تأیید برآورد، حداقل یک ردیف برآورد ثبت کنید.` The draft UI hides approval and shows that message. Direct service calls, forged HTTP POSTs, legacy revision fallback and active workflow domain commands are covered. Failed workflow approval rolls back the claim/decision and leaves the work item open; valid items still complete the existing workflow. Historical items do not qualify an empty current revision. |
| Minor form cleanup | Optional Contract/Phase labels are explicit. Existing Tailwind utilities pair fields on desktop, retain a mobile stack and reduce Notes to three rows. The existing searchable Unit of Measure selector is preserved and exercised through real search/selection. |

Only the two requested Estimate service rules changed: automatic append order
when omitted, and rejection of empty approval. Model/schema, Estimate workflow
definition/runtime, price-book checks, authorization, Product Surface and other
domain services remain unchanged. The shared breadcrumb renderer remains in use;
current pages remain final non-links with `aria-current="page"`.

Validation: **35 focused/affected functional tests PASS** (11 new, 24 existing),
plus **5 live Chrome tests / 92 scenarios PASS** (14 new Estimate scenarios,
34 contextual-create, 7 Project hub, 37 existing breadcrumb scenarios).
Desktop 1440px and mobile 390px cover actual Project/list/detail/back clicks,
inherited create/error/success, no item-order control, two automatic items,
searchable units, nonempty workflow approval and unchanged Project/Site session.
Ruff check/format, Django system check, three template compilations, migration
drift and `git diff --check` PASS. Fourteen protected sources match HEAD.
Only the isolated reusable test database was written; the pre-existing pending
Development migration `payroll.0010_cep069_reviewed_statutory_context` was not run.

Initial failures were test-fixture/assertion issues: missing Unit category,
service-error redirect versus form error, breadcrumb direct-child markup,
global versus explicitly scoped expected parent URLs, TomSelect-adjusted label
targets, and uppercase identifier normalization. These were corrected and
rerun without weakening application controls; all run summaries are retained.
Representative desktop list/create/empty and mobile create captures were visually
inspected. Full ERP regression and production validation are not claimed.

Evidence: [validation](../../../output/mvp-03/estimate-ux-remediation/VALIDATION.json),
[test attribution](../../../output/mvp-03/estimate-ux-remediation/test-results.json),
[14 new browser captures](../../../output/mvp-03/estimate-ux-remediation/browser-index.json)
and [affected browser regression](../../../output/mvp-03/estimate-ux-remediation/browser-regression-index.json).
These paths are repository-root artifacts under `output/mvp-03/estimate-ux-remediation/`.

Git add/commit/push/merge: **NOT EXECUTED**. CEP lifecycle/dependency/authorization
records were not changed by this bounded MVP remediation.

`MVP-03 ESTIMATE UX REMEDIATION: PASS`

`PRODUCT OWNER VISUAL ACCEPTANCE: PENDING`

## Breadcrumb UX remediation — 2026-10-30/31

Completed the explicit breadcrumb-only Human request on current `main`, still
`58656e8657b3b316dcb418ec8a3084fd2b4b294b` and equal to local `origin/main`.
All preceding uncommitted work is preserved. No commit, push or migration.

The existing page-header breadcrumb markup is now a shared
`components/breadcrumbs.html` partial used by the page header and the custom
MVP breadcrumb patterns. Existing Product Surface URL filtering remains in that
single renderer. The final item is always a non-link with `aria-current="page"`,
even if a caller supplies a URL. Invalid/hidden destinations and bare `#` do not
become links. Conceptual levels without a dedicated business destination remain
text; the existing Workforce link to a real Home section remains valid.

| Journey / pattern | Result |
| --- | --- |
| Project → Estimate / Contract | Validated Project detail and permitted collection parents are links on scoped list, create and detail paths. |
| Estimate → existing Contract | The existing related-Contract link carries temporary Estimate navigation context. Contract breadcrumbs reload that Estimate from the existing permission/tenant/project-scoped related source; unrelated, foreign or malformed references never become breadcrumb parents. Ordinary Contract access is unchanged. No Estimate is chosen implicitly from multiple related records. |
| Contract → Claim | Permitted Project, Contract, Contract collection and Claim collection parents are linked, including create, validation errors and detail. |
| Baseline / Progress | Detail and validated Contract-filtered list paths expose the real, permitted Project/Contract/collection destinations. General list pages retain a single current item. |
| Workforce / Timekeeping | Worker create/edit/detail reuse the existing Workforce breadcrumb builder. Attendance/work forms and Timesheet detail link the existing workbench when permitted, retaining validated navigation context. Existing assignment/team hierarchy and permission checks remain. |
| Other shared patterns | Project detail/gallery/upload, Daily Report detail, Inventory transaction detail and legacy Employee detail use the shared renderer. The Materials list has a shared Home/current breadcrumb. Party/Document list patterns were browser-checked. No unrelated headings/forms were redesigned. |

All data/permission changes are presentation adapters and read-only navigation
metadata. Destination pages retain their existing authorization. No backend
domain rules, calculations, financial authority, workflows, models, exposure
catalogs or permission grants changed. Existing UI-guideline breadcrumb rules
already specify the requested behavior and were not duplicated.

Evidence: `output/mvp-03/breadcrumb-remediation/VALIDATION.json`, browser index,
test-result attribution and static-source evidence in the same directory.

- Focused functional/security and existing journey checks: **40 PASS / 2
  subtests PASS** (89.77s), including five new shared/business breadcrumb tests,
  contextual create regressions and the adjusted shared navigation contract.
- Related Workforce permission/navigation, Product Surface, Project hub and
  previous UI regression checks: **31 PASS / 40 subtests PASS** in the combined
  browser run. The two browser failures from that attempt were resolved or
  qualified as described below; none of these 31 checks failed.
- Final Chrome closeout: **2/2 live tests PASS** (212.23s). **37 new scenarios /
  captures**, including desktop/mobile MVP-03 parents, actual breadcrumb clicks
  to Project/Estimate/Contract, validation error, scoped/general Billing lists,
  Workforce, Timekeeping, gallery/upload, Materials, Party and Document pages.
  **15 existing journey scenarios** also pass through calculation, submission
  and independent approval. Browser assertions require real parent links and
  exactly one final non-clickable current item; no bare `#`, backend hierarchy
  labels or horizontal page overflow are accepted.
- Representative mobile Contract, Claim and Workforce captures were inspected:
  business labels and hierarchy are readable and wrap correctly. Human visual
  acceptance remains pending.
- Initial browser findings: Materials had no breadcrumb and received the shared
  minimal trail. One independent-reviewer control lookup failed on the first
  regression attempt. An explicit HTTP assertion now proves the existing
  reviewer decision authority before Chrome; the complete final browser rerun
  passed. No permission, approval or workflow source was changed for that result.
- **13 templates compile; 24 protected domain/model/authorization/workflow/
  settings/Surface sources match HEAD.** Ruff, Node syntax, Django check and
  `git diff --check` pass. Migration drift: **no changes detected**. The existing
  pending Development `payroll.0010_cep069_reviewed_statutory_context` remains;
  this task applied no migrations.

```text
BREADCRUMB UX REMEDIATION: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

## Contextual Create follow-up — 2026-10-30

Explicit Human request authorizes a reusable UI-guideline rule and bounded
contextual creation for Project → Estimate/Contract and Contract → Claim,
including server-reloaded parents, inherited-field presentation, navigation and
tests. Entry main/origin/main remain `58656e8657b3b316dcb418ec8a3084fd2b4b294b`;
the preceding UI remediation is still uncommitted and must be preserved.
Intended changes: UI guidelines; shared business-choice/form presentation helper;
Estimate/Contract/Billing create forms/views/templates and related-record links;
focused tests, Chrome evidence, this report. No models/migrations, domain services,
authorization catalogs, calculations, workflow semantics or Product Surface change.

Domain limitation C: Estimate owns an optional FK to an existing Contract
(`apps/estimates/models.py`, Estimate.contract); Contract has no Estimate parent.
`create_contract` accepts no Estimate, and no existing service links a previously
created Estimate to a new Contract. `create_estimate` accepts an existing Contract.
Do not silently mutate Estimate.contract or invent conversion/attachment workflow.
An existing authorized related Contract can be opened; an unlinked Estimate must
receive truthful guidance rather than a misleading create-and-link action.

The second domain boundary is `baseline_one_current_approved_contract`, the
conditional database uniqueness constraint in ProjectBaseline. Approval supersedes
the previous approved version atomically. Multiple approved versions cannot be
represented as an eligible live set without violating the existing domain. The
UI does not arbitrarily choose when more than one choice is returned, but tests
must not disable this constraint or fabricate an illegal live browser fixture.

Implemented within those boundaries:

| Entry | Before → After |
| --- | --- |
| Project → Estimate | A preselected editable Project selector → visible inherited Project name/code and parent link; no redundant selector. The restricted required field rejects a forged or missing submitted parent. |
| Project → Contract | The same inherited Project presentation and validation, without changing existing optional Estimate associations. |
| Estimate → Contract | Existing authorized Contract opens directly; a guarded Estimate reference also redirects to it without creation. An unlinked Estimate explains the unsupported create-and-link relationship. No conversion, new FK, or direct attachment write was introduced. |
| Contract → Claim | Visible inherited Contract title/number and derived Project; no Contract selector. Approved Baselines are restricted to that Contract and Project. Exactly one is selected automatically; none displays the actual prerequisite and prevents the contextual create action. No arbitrary selection if more than one candidate is returned. |
| General Create | Explicit parent selectors, dependent choices and successful creation remain available for Estimates, Contracts and Claims. |
| Navigation | Validation re-renders preserve the trusted parent; Cancel returns to its detail; successful creation opens the created record with permission-checked parent links. Global Project/Site session state stays separate. |

The concise `Contextual Create & Parent-Child Context Preservation` rule is now
in `docs/ui-guidelines.md`, with no technical implementation prescription or
D1–D7 change. Presentation reuses the existing business-choice forms and one
shared inherited-parent summary. Parent references are reloaded from existing
tenant/permission/object-scoped sources on every request, including POST; existing
domain services remain responsible for transactional business validation.

Validation evidence: `output/mvp-03/contextual-create/VALIDATION.json` and its
linked static/source, test and Chrome artifacts.

- New functional/security suite: **15/15 PASS**. Includes missing/forged parents,
  wrong Contract Baseline and derived Project, foreign tenant, invalid/empty/
  duplicate references, revoked membership, independent create permissions,
  explicit Project scope, soft-deleted Project, closed Contract and a genuinely
  superseded approved Baseline. The database constraint's exact name is asserted
  for the forbidden multiple-current-approved-Baseline case.
- Affected existing functional/regression suite: **57 tests / 28 subtests PASS**
  in the combined run, including existing journeys, Project hub, shared filters,
  Product Surface and Billing read scope. Final focused closeout:
  **16/16 PASS** (15 new functional checks and one live Chrome test, 77.43s).
- New Chrome evidence: **34 scenarios / 34 captures PASS**, desktop 1440×900 and
  mobile 390px. Real Project/Contract links, invalid forms, Cancel, successful
  creation, inherited identity, single/no eligible Baseline, existing related
  Contract, unlinked Estimate limitation, all three general create submissions,
  native selector fallback, forged references, tenant/permission and stale parent
  rejection are covered. The second live test exercises 28 contextual scenarios;
  the closeout live test exercises 6 general/native scenarios.
- Existing calculation → submit → independent approval Chrome journey:
  **15 scenarios PASS**, including remote selector search and mobile final state.
  This uses the existing remediation evidence directory; its three batch files
  are explicitly referenced in the new evidence manifest.
- Representative desktop/mobile captures inspected: consistent parent summary,
  visible Persian validation/prerequisite messages, isolated LTR identifiers,
  readable RTL layout, and no page-level horizontal overflow.
- Ruff, Django system check, seven affected templates and `git diff --check`:
  **PASS**. `makemigrations --check --dry-run`: **no changes detected**.
  Eleven protected model/service/authorization/workflow/settings/Surface sources
  match HEAD. No Development migrations were applied; the pre-existing pending
  `payroll.0010_cep069_reviewed_statutory_context` remains unchanged.

Coverage limits and observations:

- Estimate → new connected Contract and multiple eligible current approved
  Baselines remain the evidenced domain limitations above, rather than newly
  implemented business capabilities. No illegal multi-Baseline browser fixture
  was created; this branch is not claimed as live qualified.
- An extra fully JavaScript-disabled diagnostic exposed the existing dependency
  on runtime Tailwind CDN generation. This is outside this contextual-create
  request and was not remediated. Native-selector fallback was separately
  qualified in the normal JavaScript-enabled Chrome runtime; this report does
  not claim full JavaScript-disabled visual support.
- Intermediate test-harness failures (fixture approval evidence, consumed flash
  message, duplicate helper argument and that extra diagnostic) were corrected
  or attributed; no required failure is carried into the final results.

No models, migrations, financial calculations, approval semantics, new business
workflow, global context mechanism, CEP lifecycle, or MVP-04 scope changed.
Preceding uncommitted remediation is preserved. No commit or push was performed.

```text
FUNCTIONAL VALIDATION: PASS
BROWSER INTERACTION VALIDATION: PASS
VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

## Targeted UI/UX remediation — 2026-10-30

Completed the explicitly requested thirteen presentation fixes on clean local
main at `58656e8657b3b316dcb418ec8a3084fd2b4b294b`, also local origin/main.
The original implementation sections below retain their 2026-10-29 evidence;
this section and the linked remediation artifacts describe the current changes.

| Request | Result |
| --- | --- |
| 1 | Baseline/Progress document titles contain only page identity and BONIRA; pagination stays in the body. |
| 2 | Estimate approved/revised/archived messages are state-specific; approval and item-add forms are separate and balanced. Existing lifecycle/permission conditions remain. |
| 3 | Claim filters use all six existing model status values with their Persian labels, including Superseded and Cancelled. |
| 4 | Project heading names Estimates, Contracts and Claims; each summary has its own explicit list action. No detailed workflow is embedded. |
| 5 | The existing Billing navigation uses the Workforce active-button convention on list/detail/create pages, in a consistent order below the header. |
| 6 | Contract identity visibly includes its canonical LTR number; dates use the shared Jalali formatter. Project, party, direction and status remain. |
| 7 | Claim title includes number/revision; state section is «وضعیت و اقدام بعدی». Correction/cancellation copy and success messages describe the selected operation without changing services. |
| 8 | Temporary-filter clearing retains applied Project/Contract query context. A separate explicit exit link leaves that context; global session context is unchanged. |
| 9 | Lists distinguish a genuinely empty scoped dataset from no matches within an existing scoped dataset, with context-preserving recovery. |
| 10 | Draft prerequisites are distinguished from verified-measurement inputs to meaningful work valuation. A real service-backed test creates a zero-work draft without measurements. |
| 11 | Persian descriptions/links remain RTL; canonical contract identifiers use isolated LTR boundaries. |
| 12 | Progress verification/rejection reasons have visible Persian labels and multiline required controls, with distinct existing button variants. |
| 13 | Contract/Estimate filters render after header/context, using the shared components; Billing header/navigation/context/filter/content/pagination order is retained. |

The shared table JavaScript previously intercepted Clear and deleted every GET
form's query controls, including context fields. Commercial lists now opt into
the server-built same-page Clear URL; unrelated default behavior is retained.
The runtime table tag is owned by accounts; the unused core duplicate is unchanged.

Validation and bounded regression evidence:

- Affected functional/regression run: **57 tests and 28 subtests PASS** (105.52s),
  including existing journey/security, scoped Project hub, shared list-filter,
  Product Surface and Billing read-scope checks.
- Final post-fix closeout: **18 tests and 8 subtests PASS** (180.62s), including
  16 focused/shared-filter checks and two complete real-Chrome live tests.
- Independent final Project handoffs: **1 live test PASS** (42.99s).
- Combined browser evidence: **58 scenarios / 58 captures PASS**, desktop 1440px
  and mobile 390px. Includes Project → Contracts/Estimates/Claims, Estimate →
  Contract, Contract → Claim, all six actual Claim states on desktop/mobile,
  Superseded/Cancelled filtering, Project/Contract-preserving Clear actions,
  both empty-state meanings, Jalali Contract identity/dates and a real independent
  Progress rejection. All Claim states were produced by existing governed services;
  Estimate non-draft fixtures are read-only presentation fixtures, not new transitions.
- **16 changed templates compile**; explicit rendered-tag balance checks pass;
  Ruff check/format on **11 Python files**, both JavaScript syntax checks,
  Django system check, schema-drift and diff checks PASS.
- Eleven protected model/service/authorization/workflow/Product Surface/settings
  sources match the entry commit. No source financial or lifecycle logic changed.
  This is bounded regression evidence, not a new global ERP acceptance claim.
- Agent inspected representative desktop/mobile renders. Product Owner visual
  acceptance remains **PENDING**. Existing historical baseline fixture debt below
  is retained; the entire legacy ERP suite was not rerun or reclassified.

Superseded checks exposed the actual Clear interception defect and stale caption
expectations. The browser harness also needed explicit UTF-8 subprocess capture
on Windows and form-scoped field selection for two independently required `reason`
fields. The test now fills the rejection form and completes the actual POST;
native/backend validation was not weakened. Final checks above pass.

Evidence: [remediation validation](../../../output/mvp-03/remediation-20261030/VALIDATION.json),
[source/static checks](../../../output/mvp-03/remediation-20261030/static-source-evidence.json),
[migration evidence](../../../output/mvp-03/remediation-20261030/migration-evidence.json),
[functional run](../../../output/mvp03-remediation-functional.log),
[final closeout](../../../output/mvp03-remediation-closeout.log),
[Project handoffs](../../../output/mvp03-remediation-project-links.log),
[desktop/mobile captures](../../../output/mvp-03/remediation-20261030/browser/).

All data remains synthetic in the existing dedicated test database. No Development
data mutation or migration was performed; payroll.0010 remains the sole pending
Development migration. No models/migrations, permissions, workflow/calculation/
financial semantics, Product Surface architecture, dependencies, production
actions, MVP-04 work, branch/worktree, commit or push. HEAD/origin/main unchanged.

## Grounding and intended touch set

- Branch main; HEAD and local origin/main
  `3134ae9137da2ea9258561a87444aad1888bbd50`.
- Existing Human edits: docs/ui-guidelines.md and
  docs/architecture/web_stack_specification.md. Read as current guidance and preserved.
- Development PostgreSQL: only pending migration is
  payroll.0010_cep069_reviewed_statutory_context. Do not apply it.
- Bounded touch set: Estimate/Contract forms, views and templates; Billing journey
  presentation forms/selectors/views/URLs and receivable list/detail/baseline/progress
  templates; existing searchable-choice enhancement; centralized Product Surface
  classification for settlement controls; focused journey/security tests, browser
  verification and output/mvp-03 evidence; this report. The explicitly authorized
  follow-up also touches Project detail, its read projection and summary/context
  templates, and project-hub tests.
- No model/schema/migration, statutory policy, calculation, posting, settlement,
  indexation activation, workflow-engine or dependency change is intended.
- Existing source contracts: Estimate.contract is optional and points to an
  existing Contract. There is no supported automatic Estimate-to-Contract conversion.
  Receivable claim deductions are generated by recalculate_progress_claim from
  pinned approved terms and reviewed effective policy. No arbitrary adjustment
  entry service exists; do not invent one. Indexation engine remains fail-closed
  without approved formula/index/adapter (CEP-036).
- Read governing policy/playbook, Registry entry/program context, Roadmap MVP
  section, frozen D1–D7, current UI and web guidance, Billing architecture, and
  CEP-035/036/037 completion evidence; inspected actual forms, views, services,
  models, routes, workflow and tests. Existing graph contains insufficient direct
  claim-service mappings, so current source inspection supplies implementation evidence.

## Boundaries

### 2026-10-30 targeted UI/UX remediation

Explicit Human follow-up authorizes the thirteen presentation fixes in the
attached remediation request. Entry main and origin/main are
`58656e8657b3b316dcb418ec8a3084fd2b4b294b` (MVP_03); working tree clean.
Intended surface: existing Contract/Estimate/Billing list/detail/form and Project
summary templates; their presentation contexts in views/journey forms/views and
Project summary adapter; shared list-filter/context/empty-state presentation;
shared table-filter JavaScript; focused tests and existing Chrome verification
harness; this report and MVP-03
evidence. No models, migrations, source services, authorization, workflow,
calculation, financial authority, Product Surface, settings or dependency changes.
No Development data mutation, MVP-04 work, commit or push. Human visual acceptance
remains pending. Earlier implementation evidence below describes the prior build.

The subsequent explicit Human instruction authorizes Project as a contextual
Contract & Claims hub. This bounded follow-up adds a read-only summary and
project-scoped navigation to the existing dedicated workspaces, plus associated
tests/templates. Detailed forms, calculation and approval remain on business
pages. No source service, financial authority or lifecycle changes are authorized.

No commit/push/branch/worktree. MVP-04 not started. XLSX remains MVP-05 and
Progress Claim print remains MVP-06. Human visual acceptance remains pending.

## Journey implementation

Before: linked estimates displayed a contract number without a contextual handoff;
contracts had no related-estimate/claim journey; receivable claims had list/detail
HTTP pages but no create/refresh/submit/decision adapters. Claim details exposed
source adjustment codes, internal calculation-version identifiers and a settlement
form instructing users to enter hidden financial workspaces. Billing lists were
unpaginated and had little search/context support.

After:

- A permitted existing Estimate.contract link opens the scoped Contract. Contract
  detail shows independently permission-checked related estimates, measurement
  baselines and claims, with contextual routes to full filtered lists.
- Active receivable contracts and approved measurement baselines hand off to a
  new claim form using the existing create_progress_claim service. Contract and
  baseline selection, dates, source measurement, approved terms and effective
  reviewed policy retain their existing validation and financial ownership.
- Draft calculation refresh, submission, independent approval/return, returned
  revision navigation and linked correction/cancellation call existing services.
  The shared workflow still owns candidates, assignment, separation, atomic
  completion and audit. No second engine, status, direct model mutation or posting.
- Claim detail exposes current state, permitted next action, source context,
  cumulative quantities, Persian deduction labels, snapshotted percentage/base/
  amount and immutable revision history. Financial settlement UI is FULL_ERP-only,
  and its direct endpoint is classified centrally under the finance capability.
- Estimate and Contract creation use one integrated selector per governed
  relationship. Counterparty snapshots are copied from the selected party; new
  estimate lines use the selected unit master. Legacy service/model fields remain.
- The qualified MVP-02 searchable widget is shared from core, preserving its
  old import, template, vendor and asset paths. Consumer lookups reuse each form's
  scoped queryset, paginate, retain selected values and fail closed for invalid
  parents. Explicit no-JavaScript refresh cannot create a record.
- Breadcrumbs use the centralized Product Surface group label. Billing sibling
  navigation, contextual filters and pagination retain contract scope without
  writing global Company/Project/Site session context.
- Project now shows a compact, read-only commercial section: source-scoped record
  counts, one state count and one recent record each for Estimates, Contracts and
  Claims. Source permissions and centralized exposure independently control each
  card; project-scoped creation permissions control Estimate/Contract links.
  There are no commercial forms, calculation/approval controls or aggregated
  financial balances on Project. Detailed operations stay on dedicated pages.
- Project links open exact project-filtered lists, with a visible project label
  and return link. Estimate/Contract creation receives the local project without
  changing the active global context. Claim creation continues through a selected
  Contract; the project-filtered Claims page links to project Contracts for that
  handoff. Query filters intersect the existing source scopes, reject malformed
  or foreign projects, and persist through filter submission and pagination.

## Superseded validation findings

- Initial reused-test-database run: missing seeded WorkflowTemplate rows stopped
  execution before changed behavior. New fixture restores exact code-owned
  compatibility catalogs, only in test setup.
- Following focused run: 9/11 PASS; the remaining checks expected a different
  hidden-route HTTP code and Django's default required-field wording. The existing
  exposure boundary returns 403. Added explicit Persian required-field messages.
- Next run: original 11 focused checks PASS. Browser fixture setup attempted to
  rename a finalized contract and correctly failed; fixture now supplies its name
  before contract creation. Reused database teardown also revealed a retired
  payments_payment FK outside the installed-app flush set. The full fresh-schema
  rehearsal reproduced this: those tables intentionally survive their historical
  state-only retirement. This is not merely a stale-schema assumption. No domain
  guard, retired table, FK or product migration was changed. The browser test uses
  the existing MVP-02 guarded test-only flush pattern, with cascade for retained
  FK dependents, inside test_bonira_mvp03_20261029. A failed test's ordinary teardown
  was completed only after checking current_database() against that exact name;
  code-owned authorization and three compatibility workflow catalogs were restored.
- The fresh database bootstrap applied the configured historical migration graph;
  one intermediate run overlapped edits and retained an older form class in memory.
  The next fresh process resolved that import-version mismatch. A new unit fixture
  was also corrected to supply its required volume category. These are superseded
  test-harness/fixture failures, not remaining product defects.
- A browser substring assertion matched AR inside the synthetic business code
  SEARCH-044. The check now targets the actual financial instruction. The final
  Chrome run passed all scenarios. Raw rendered HTML in intermediate failure logs
  was omitted to avoid retaining ephemeral form tokens.
- The first Project browser pass found that the shared layout had already rendered
  the table filter under its shared form ID. The project-context hidden field was
  corrected to associate with that actual form; the final browser pass exercised
  real Contract, Estimate and Claim filter submissions successfully.

## Final validation and evidence

The configured surface is MVP. All positive browser data is synthetic and resides
only in the dedicated PostgreSQL test database, including explicitly test-only
reviewed regulatory inputs. This does not activate or certify official statutory
content, create a Development demo tenant or issue Human UAT.

| Check | Result | Evidence |
| --- | --- | --- |
| Journey/security/forms and Project hub | Final combined run: 22 tests and 6 subtests PASS, including 20 focused checks and two live-browser tests; 137.10s | [final combined evidence](../../../output/mvp03-project-final.log) |
| Affected regression | 50 tests and 45 subtests PASS; 29 baseline fixture failures separately attributed | [regression log](../../../output/mvp03-regression.log), [attribution](../../../output/mvp-03/baseline-attribution.json) |
| Real Chrome interaction | 22/22 scenarios PASS in two live-server tests, included in the combined run | [A–E](../../../output/mvp-03/browser/batch-A-estimate-contract-handoff.json), [F–L](../../../output/mvp-03/browser/batch-F-mobile-claim-deductions.json), [M–O](../../../output/mvp-03/browser/batch-M-decision-required-reason.json), [P–V](../../../output/mvp-03/browser/batch-P-project-hub-desktop.json) |
| Responsive/visual inspection | 22 screenshots; desktop 1440px, mobile 390px; agent inspected representative journey and Project renders | [screenshots](../../../output/mvp-03/browser/) |
| Static checks | Ruff check and format: 17 changed Python files PASS; JavaScript syntax and diff whitespace PASS; 18 templates compile | [template compilation](../../../output/mvp-03/template-compilation.json), [static checks](../../../output/mvp03-project-static.log) |
| Django/system/schema | System check PASS; no migration drift | [system check](../../../output/mvp03-project-static.log), [drift](../../../output/mvp03-project-schema.log) |

Reproducible focused/browser entrypoint:
`python scripts/verification/mvp03_validate.py` (uses the dedicated test DB).
It reuses the qualified real Chrome/CDP driver at
scripts/verification/mvp02_browser.mjs; the driver's environment names are legacy.
The affected regression selection contains Contract and Estimate service/view
suites, MVP-02 selector/UI tests, Product Surface tests, Billing read-scope tests
and seven existing claim calculation, fail-closed policy, snapshot, approval,
separation, idempotency, rollback and dormant financial-handoff assertions.
Detailed commands/results and the actual touch set are in
[VALIDATION.json](../../../output/mvp-03/VALIDATION.json) and
[grounding-and-touch-set.json](../../../output/mvp-03/grounding-and-touch-set.json).

All 29 regression failures (13 Contract, 16 Estimate) stop in unchanged setUp →
create_project authorization, before the changed journey/forms/views execute.
Those fixtures create legacy role fields without the current explicit membership
role/scope grants. The fixture files, projects/services.py and
organizations/authorization.py match HEAD; the attribution artifact records that
comparison. Classification: BASELINE TEST DEBT. They were not weakened or silently
rewritten. There is no global regression PASS claim and no unresolved attributable
MVP-03 failure within the tested coverage.

## Browser scenario coverage

| Scenario | Exercised behavior |
| --- | --- |
| A | Actual Estimate → related Contract click |
| B | Actual Contract → new Claim click; contract and approved baseline retained |
| C | Integrated search beyond the initial option window; parent change clears baseline; authorized empty result |
| D | Required-field validation with retained business selections |
| E | Real browser claim creation; existing calculation produces contractual retention |
| F | Mobile draft, source context, totals, deductions and contained item tables |
| G | Draft refresh through existing calculation service |
| H | Submission to shared workflow and resulting pending-review state |
| I | Filtered empty state and permitted recovery action |
| J | Mobile create form and integrated selectors |
| K | Approved measurement baseline detail and contextual create action |
| L | Contract-filtered progress list |
| M | Decision reason validation |
| N | Different actor approves through existing shared work item |
| O | Mobile final state and retained deduction evidence |
| P–Q | Desktop/mobile Project hub, bounded summaries, source links and no embedded commercial forms |
| R–T | Actual Project → Contract/Estimate/Claim list clicks and filter submissions retain exact project context |
| U–V | Actual Project → dedicated Contract/Estimate creation; project retained, including mobile |

The test proves gross 60, retention -6 and net 54 using the explicit synthetic
contractual 10% fixture. It does not establish an official rate. Representative
review images: [Contract](../../../output/mvp-03/browser/f61-owner-A-estimate-contract-handoff.png),
[draft](../../../output/mvp-03/browser/f61-owner-E-create-claim.png),
[mobile form](../../../output/mvp-03/browser/f61-owner-J-mobile-create-form.png),
[mobile approved claim](../../../output/mvp-03/browser/f61-manager-O-mobile-approved.png).
Project hub review: [desktop](../../../output/mvp-03/browser/f61-owner-P-project-hub-desktop.png)
and [mobile](../../../output/mvp-03/browser/f61-owner-Q-project-hub-mobile.png).
The new browser journey qualifies the touched receivable path; untouched payable,
statutory and broader Commercial UI are not newly qualified by this evidence.

## Security, migration and closeout

- Authentication, CSRF, active membership, organization lifecycle, source business
  permissions and tenant/project/object scope remain server enforced. Focused
  tests cover foreign tenants, out-of-scope project readers, forged parent/child
  choices, unauthorized lookup/action, CSRF, method restrictions and session
  context preservation. UI candidacy is advisory; the existing transactional
  workflow services re-check the real assignment and separation policy.
- Technical source descriptions, calculation-version UUID disclosure, raw line
  keys/source types, transaction UUIDs, internal adjustment-model terminology and
  MVP settlement instructions were removed from the touched user journey.
  Source-pinning validation wording is translated at the presentation boundary.
  Full ERP backend settlement, financial ownership and source history remain.
- No application model/schema change, new permission, dependency, production
  operation or migration was introduced. Development migrations applied: NONE.
  payroll.0010_cep069_reviewed_statutory_context remains the sole pending
  Development migration, unchanged from entry. No Development data reset.
- Actual implementation files are enumerated in the touch-set artifact. Initial
  Human edits to UI guidelines and web-stack guidance were preserved. D1–D7,
  eight-package scope, canonical CEP prompts, Registry and Roadmap are unchanged;
  this separately authorized MVP package does not change CEP lifecycle state.
- Remaining business prerequisites fail closed under the existing services. This
  package adds no automatic BOQ conversion, arbitrary manual claim deductions,
  official indexation formula/adapter, legal policy, posting, AR/AP recognition,
  Treasury settlement authority or second context/workflow system.
- Deferred: shared XLSX/Billing XLSX remains MVP-05; required Claim print remains
  MVP-06; unrelated P1 forms/outputs and full demo/final MVP E2E remain MVP-07/08.
  Existing exports/prints were not replaced. MVP-04 was NOT STARTED.
- Branch main and end HEAD/local origin/main remain
  3134ae9137da2ea9258561a87444aad1888bbd50. No branch/worktree/index/commit/push/
  merge/rebase/reset/clean/stash operation. Changes remain uncommitted for review.
  Human Sign-off, Production Certification and Production Cutover: NOT EXECUTED.

FUNCTIONAL VALIDATION: PASS

BROWSER INTERACTION VALIDATION: PASS

VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW

PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
