# MVP-04A — Purchase Request

Bounded execution under the Product Owner's 2026-11-01 chat instruction. Only
MVP-04A is authorized. MVP-04B and later tranches are NOT STARTED. This MVP task
is not a CEP; no CEP lifecycle or gate is reopened.

Start: clean local `main`, HEAD and `origin/main`
`da88f0a23cc66696d688da7c9fba8e4152e0a87e`, upstream divergence 0/0.

Intended touch set: procurement PR presentation forms, views, templates and
read-only UI helpers; RFQ creation adapter/form/template solely for the existing
PR continuation; scoped choice endpoint; focused HTTP/browser tests and bounded
evidence in `output/mvp-04a/`. Shared reference components are reused. The
existing Chrome driver receives one test-only correction: default business-field
fills target `main`, avoiding the shell search field with the same name.
No models, migrations, lifecycle, permission catalog, SoD, workflow, Product
Surface, inventory, financial or RFQ commercial-scope changes are authorized.

## Implemented boundary

- PR List adopts the accepted Contracts reference CSS/components: business
  search, status/project filters, Jalali need-date advanced filters, removable
  chips, full result count, allowlisted sorting, compact table/mobile cards,
  row menu and pagination. Resolved project context survives filtering, clearing,
  creation, detail and return navigation.
- PR Create reuses the reference Create components and qualified Tom Select
  project selection. An inherited project is server-resolved, hidden and
  restricted during POST validation. Existing number/title/date/notes fields
  remain the entire header contract; there is no invented edit lifecycle.
- Detail prioritizes items, a compact summary and state guidance. Item entry
  uses tenant-scoped material names, business codes and units. Invalid item
  values remain bound with inline server errors. Decision/cancellation forms
  retain errors with distinct accessible field IDs.
- CTAs intersect state, existing project permissions, creator/management rules,
  active workflow candidacy/assignment, transition permissions, delegation and
  SoD checks. Existing transactional services re-authorize all real actions.
- Approved PRs expose contextual RFQ creation only within existing RFQ create
  authority. The PR/project are carried automatically; the reference is hidden,
  server-resolved and POST-restricted. The general RFQ Create entry uses a
  scoped, business-labelled approved-PR selector instead of UUID entry.
  Existing RFQ source/status/time prerequisites remain enforced by create_rfq.
  The PR page explains unavailable continuation in business language.

No direct PR → PO shortcut, RFQCommercialScope work, RFQ downstream UI redesign,
new dependency, model, migration, permission grant, workflow semantics, Product
Surface or financial/inventory behavior was introduced.

## Validation

Execution began on 2026-11-01 and continued into 2026-11-02 (Asia/Tehran).

**MVP-04A implementation and bounded validation: COMPLETE.**
Final adapted run: **38/38 tests PASS**, including seven focused PR journey
checks, 29 existing affected-boundary regression checks and two real-Chrome
tests executing **30 scenarios**. The isolated database applied the existing
446-migration history and was destroyed after the successful run.
There is no in-scope functional or browser blocker.

Commands and durable results:

- `python output/mvp-04a/run_validation.py` — fresh task-isolated PostgreSQL,
  actual installed Chrome via the existing CDP driver, existing migrations.
  Result: PASS, 38 tests in 150.465 seconds after fresh database preparation
  ([final-validation.log](../../../output/mvp-04a/final-validation.log)).
- Django `check`: PASS ([log](../../../output/mvp-04a/system-check.log)).
- Configured database currency: the earlier PASS claim is withdrawn; that
  command did not preserve its own exit code. The 2026-11-02 MVP-04B plan
  identifies pending unrelated `payroll.0010_cep069_reviewed_statutory_context`
  plus the new Procurement migration. The unrelated migration is not executed.
  This does not change the fully migrated isolated MVP-04A test result.
- `makemigrations --check --dry-run`: PASS, no changes detected
  ([log](../../../output/mvp-04a/migration-drift.log)).
- Ruff/format and diff whitespace: PASS
  ([lint](../../../output/mvp-04a/lint.log),
  [format](../../../output/mvp-04a/format.log),
  [diff](../../../output/mvp-04a/diff-check.log)).
- Modified Persian UI strings: valid UTF-8, no replacement/mojibake patterns.
- Models, existing mutation services, workflow, authorization and Product Surface
  were verified unchanged by Git diff.

### Baseline test attribution

The initial unadapted regression run is retained in
[focused-regression.log](../../../output/mvp-04a/focused-regression.log):

1. **BASELINE TEST DEBT:** the unchanged pilot `_manager_with_position` helper
   creates a legacy manager membership without its explicit effective role
   assignment. The strict multistage test fails in unchanged
   `create_purchase_request` authorization before reaching any modified view,
   form or template.
2. **TEST INFRASTRUCTURE DEBT:** the unchanged RFQ concurrency test body reaches
   teardown, whose normal flush fails because retained `payments_payment`
   references `projects_project`. The failed flush leaves reused catalogs
   incomplete, causing subsequent reused-database fixture failures.
3. The newly added SoD fixture initially lacked a second eligible reviewer;
   this task's fixture was corrected with explicit membership authority.

The bounded validation harness supplies the missing effective manager assignment
and reuses the existing isolated-test CASCADE cleanup, guarded by a `test_`
database-name assertion. Serialized rollback restores the migration-seeded
catalog between browser/concurrency tests. Original service assertions are
retained; no baseline product or test file is edited. These adaptations do not
turn the unadapted regression command into a PASS.

## Browser evidence and scope

The [browser evidence directory](../../../output/mvp-04a/browser/) contains
synthetic-data screenshots and per-batch JSON results. Validation uses the real
installed `C:\Program Files\Google\Chrome\Application\chrome.exe` in headless
mode, with viewport emulation at 1440, 1024 and 390px. No customer data or
credentials are included in evidence.

The bounded claim covers PR List/Create/Detail/item/workflow screens and the
contextual RFQ Create entry. RFQ lines, commercial scopes, issue/close/buyer
workspaces, PO, GRN and Inventory are unchanged and are not certified here.
Intentional 403/404 responses for unauthorized or inaccessible context are
expected denials; valid journey pages must have no 404/500. The existing missing
favicon is excluded by the qualified driver from page-asset checks.

### Requested browser matrix

| Check | Result | Evidence |
| --- | --- | --- |
| PR list, search/filter/sort/chips/pagination | PASS | `batch-list-1440.json`, `batch-list-pagination-mobile.json` |
| Create PR and parent project retention | PASS | `create-save`, `create-validation-retention` |
| Search/select material, add item | PASS | `add-submit-approve` |
| Submit and approve | PASS | `add-submit-approve`; HTTP service/state assertions |
| Reject path | PASS | `rejectPR-REJECT` |
| Cancel draft and submitted | PASS | `cancelPR-CANCEL`, `cancelPR-CANCEL-S` |
| Approved PR → RFQ contextual entry | PASS | `batch-approved-entry-1440.json`; HTTP RFQ persistence test |
| Unauthorized user | PASS | `batch-viewer-approved-no-rfq.json`; forged POST denials |
| Wrong project/tenant | PASS | `batch-wrong-project-detail.json`; HTTP context/material/source isolation |
| Validation-error retention | PASS | `create-validation-retention`, `item-invalid-retention`; empty reason HTTP checks |
| Desktop 1440, tablet 1024, mobile 390 | PASS | List/Create/Draft Detail/Approved Detail/RFQ entry at all three widths |
| State/permission CTAs, no UUID entry/default object labels | PASS | Scenario DOM assertions, selector contract, screenshot review, SoD HTTP test |
| No horizontal overflow, JS exceptions or valid-route 404/500 | PASS | All 30 scenarios; intentional denials/validation errors distinguished |

[Browser summary](../../../output/mvp-04a/browser-summary.json) records actual
width/scroll dimensions, response statuses and browser errors. Detailed batch
files and screenshots remain in the linked browser directory. Codex visually
compared the PR list with the accepted Contracts reference and inspected Create,
Detail, validation and RFQ-entry captures across the required sizes.
Final presentation-only review also added LTR isolation around business PR
numbers in the Detail heading and RFQ source summary; no action or validation
behavior changed.

## Closeout

Branch and end HEAD remain `main` /
`da88f0a23cc66696d688da7c9fba8e4152e0a87e`; changes are uncommitted.
No CEP Registry or Roadmap lifecycle/direction change is applicable to this
explicit, bounded MVP tranche. Original baseline test debt remains recorded;
only the qualified validation harness adapts those fixtures. There is no claim
of a full-repository regression run or completion of the whole MVP-04 package.

- Models/migrations, domain mutation services, workflow/SoD, permission catalog,
  tenant/project authority, Product Surface and inventory/financial behavior:
  unchanged.
- New dependency: NONE. Production action, Human sign-off/certification: NOT EXECUTED.
- Branch/worktree creation, git add/commit/push/merge: NOT EXECUTED.
- MVP-04B and all later tranches: NOT STARTED. STOP after MVP-04A.
- Product Owner visual acceptance: PENDING; automation and Codex screenshot
  review do not constitute Human acceptance.

```text
MVP-04A FUNCTIONAL: PASS
PR JOURNEY: PASS
PR → RFQ CONTINUATION: PASS
TECHNICAL LEAKAGE: PASS
BROWSER VALIDATION: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

No commit, push, branch/worktree creation, production action or Human sign-off.
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING.


# MVP-04B — Explicit RFQ Commercial Scope (2026-11-02)

Status: BOUNDED COMMERCIAL-SCOPE IMPLEMENTATION COMPLETE. This section supersedes MVP-04A's earlier stop boundary only
for the bounded scope explicitly authorized by the Product Owner's 2026-11-02
Commercial Scope decision in this chat. MVP-04A results/history remain intact.

Authority: authorized users explicitly define commercial applicability from the
approved PR and selected RFQ/PR lines; no silent/default scope, award structure,
supplier selection, quantity allocation or commercial assumption. Existing line,
lot, partial-quantity, split-award, alternate, permission, SoD, tenant/project and
audit contracts remain authoritative. Issue must validate and version-pin the
effective scope; material changes use explicit addendum/version history.
Authorization excludes PO, GRN, Inventory, AP, Accounting and Treasury changes.

Grounding: same local main/HEAD da88f0a23cc66696d688da7c9fba8e4152e0a87e,
upstream divergence 0/0. All uncommitted MVP-04A changes are preserved.

Intended touch set: additive immutable RFQ scope-definition persistence and
version reference, new-RFQ scope requirement with legacy migration preservation;
focused scope service plus issue/addendum integration, existing RFQ edit/addendum
authority, dedicated scope form/view/template and RFQ detail links, explicit
audit action, tests and evidence. No permission grant or downstream financial
authority change. Scope definition is part of existing RFQ change/addendum
capability, not a parallel permission system.

MVP-04C and later: NOT STARTED. No commit/push or production action.

Development migration finding: `payroll.0010_cep069_reviewed_statutory_context`
is pending and outside this tranche. Do not execute it. Only Procurement 0017
may be applied to development after validation. The earlier MVP-04A currency
claim is corrected above; its command lacked a retained exit code.

## MVP-04B implementation contract and evidence

- `RFQCommercialScopeDefinition` is an append-only, tenant/RFQ-owned explicit
  configuration with actor, target version, revision, source fingerprint and
  idempotency evidence. Its JSON members retain approved PR item references and
  the quantities the user actually chose. No supplier or award allocation is
  created during definition.
- The user explicitly chooses LINE or LOT, member quantities, lot quantity/unit
  where applicable, independent awardability, split-award and alternate-offer
  applicability. Partial line quantities are bounded by the chosen RFQ/PR line.
  Existing LOT indivisibility and downstream award/alternate rules are retained.
  No new full-coverage, allocation, exclusivity or supplier-selection policy is
  inferred.
- Definition uses existing `rfqs.change` before first issue and `rfqs.addendum`
  for the next issued version. Existing scope/tenant status and membership checks
  run inside the transaction. Issuing remains under `rfqs.issue`; downstream
  permissions, confidential-access grants and SoD policies are unchanged.
- RFQ locks serialize scope preparation against issue/addendum. Expected
  revision, target version and source fingerprints reject stale forms. Identical
  retries return the immutable definition; changed-payload key reuse fails.
- Issue validates the exact latest explicit definition, includes its identity
  and fingerprint in the version fingerprint/audit, pins its FK and atomically
  creates validating immutable `RFQCommercialScope` rows alongside version
  lines/invitations. Neither issue nor GET creates a default definition.
- Each managed addendum requires an explicit definition for its next version.
  Previously issued definitions, scopes and version pointers cannot be edited.
  The existing addendum service now refreshes only the RFQ header projection
  after recording its immutable addendum; direct issued-header edits continue
  to fail. Previously that refresh incorrectly passed through the model's
  direct-edit guard.
- The dedicated scope page shows approved PR/project context, business material
  and unit labels, editable explicit quantities, validation retention and
  recorded member provenance. RFQ line/supplier inputs use scoped business
  selectors and idempotency references are hidden. A bounded addendum page
  exposes the existing versioning action; no downstream UI redesign is claimed.

Migration: Procurement `0017_mvp04b_explicit_rfq_scope` adds the immutable
definition table, nullable version reference and a new-RFQ requirement flag.
Existing RFQs are backfilled only with `commercial_scope_required=False`;
no commercial scope is inferred, no old version hash is recomputed and no old
commercial evidence is modified. Newly constructed RFQs default to True and
normal model saves cannot disable their requirement. This additive migration
is the minimum persistence needed to separate explicit preparation from issue.

Focused tests: **12/12 PASS** in
[focused-tests.log](../../../output/mvp-04b/focused-tests.log). Includes no-default
issue denial; exact/partial line and LOT lineage; invalid member/unit/quantity/
flag rejection; retries/stale edits; definition and version immutability; atomic
rollback; explicit addendum and unchanged prior version; authorization/scope;
HTTP retention/replay; concurrent revision conflict; and legacy migration
preservation.

Affected regression and Chrome run: **53/53 tests PASS** in 175.373 seconds,
[final-validation.log](../../../output/mvp-04b/final-validation.log). This includes
12 focused scope tests, 40 affected RFQ/custody/comparison/award/workspace/PR
regression checks, and one real-Chrome test executing **14 scenarios**.
The isolated PostgreSQL database is fully migrated through the 447-migration
history. It is reused only for this task to avoid repeating the costly complete
migration preparation. The validation runner retains baseline fixture-only
adaptations for effective role assignments and guarded test-only CASCADE cleanup.
Existing RFQ regression fixtures now call the real explicit producer before
issue; comparison/award tests consume the resulting pinned scopes instead of
constructing them after issue. Original downstream business assertions remain.

Development migration application: **Procurement 0017 APPLIED**, command exit 0;
[application log](../../../output/mvp-04b/development-migration.log),
[target migration state](../../../output/mvp-04b/procurement-migration-state.log).
The target-specific plan contained only Procurement 0017. Unrelated pending
`payroll.0010_cep069_reviewed_statutory_context` remains untouched and is the only
remaining planned migration
([remaining plan](../../../output/mvp-04b/remaining-development-migrations.log)).
No development or production Payroll/statutory activation is authorized here.
Product Owner visual acceptance: PENDING.

### MVP-04B final verification and limitations

- Real installed Chrome at 1440, 1024 and 390px: explicit blank scope form, no
  preselected structure/policy, no visible UUID/default object labels; business
  validation retention; missing-scope issue denial; explicit definition and
  pinned issue; missing-next-definition addendum denial; explicit next definition;
  addendum page at all sizes; new issued scope with unchanged prior version;
  unauthorized user denial. All 14 scenarios PASS with zero horizontal overflow,
  JavaScript exceptions or valid-route 404/500. Expected 400 validation and 403
  denial responses are retained. The qualified driver's missing-favicon exclusion
  remains; no broader network-health claim is made.
- [Browser summary](../../../output/mvp-04b/browser-summary.json),
  [captures and batch results](../../../output/mvp-04b/browser/) retain synthetic
  evidence only. Codex reviewed desktop/mobile scope and addendum screenshots.
- Scope/LOT/partial quantity, split and alternate contract checks: PASS. Existing
  comparison/award tests now use scopes produced before RFQ issue, including
  strict finalization policies, explicit splits and concurrency. No downstream
  financial behavior is changed or certified.
- System checks, Ruff and formatting, changed-template compilation and migration
  drift: PASS ([system](../../../output/mvp-04b/system-check.log),
  [lint](../../../output/mvp-04b/lint.log),
  [format](../../../output/mvp-04b/format.log),
  [templates](../../../output/mvp-04b/templates-check.log),
  [drift](../../../output/mvp-04b/migration-drift.log)).

The [first broader attempt](../../../output/mvp-04b/validation-attempt-1.log) is
retained as FAIL evidence. One historical custody concurrency class was omitted
from the harness's catalogue-restore/CASCADE adaptation, causing missing-role,
cleanup and subsequent duplicate-fixture errors. A directly imported browser
TestCase was also accidentally discovered and ran two unrelated billing tests.
The harness now covers that concurrency class and the scope browser imports its
shared helper as a module. Its addendum selector now targets Submit specifically,
not the calendar button injected earlier in the form. These were validation
harness issues; no assertion or product rule was weakened to obtain the final
53-test PASS. The earlier failed run is not relabelled as passing.

Only the authorized commercial-scope producer, gate and versioning boundary is
complete. This is not certification of the whole RFQ journey, MVP-04, production
or any downstream tranche. The isolated test database is retained under its
explicit task-owned `test_mvp04b_...` identity for inexpensive reproducibility.
No credentials are stored in evidence.

Final branch/HEAD: main / da88f0a23cc66696d688da7c9fba8e4152e0a87e. Earlier
MVP-04A changes are preserved. No git add, commit, push, merge, branch or worktree
creation. No CEP Registry state or Roadmap direction change is implied.
No PO, GRN, Inventory, AP, Accounting or Treasury behavior change.
MVP-04C and later: NOT STARTED. Stop at this bounded MVP-04B boundary.

```text
MVP-04B COMMERCIAL SCOPE: PASS
EXPLICIT SCOPE / PR LINEAGE: PASS
ISSUE GATE / VERSION PINNING: PASS
ADDENDUM / IMMUTABLE HISTORY: PASS
AFFECTED REGRESSION: PASS (53 tests; documented fixture adaptations)
BROWSER VALIDATION: PASS (14 real-Chrome scenarios)
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

Final read-side check: version-bound scope definitions and scope units are
prefetched for RFQ history, avoiding per-scope unit queries. The existing HTTP
retention/replay/issue/detail test was rerun after this query-only improvement:
**1/1 PASS** ([log](../../../output/mvp-04b/final-detail-query-check.log)).
The final system, lint and formatting checks remain PASS.

## MVP-04B1 — RFQ Preparation & Issue (2026-11-02)

### Authority and boundary

Human request: attached “Continue from the current uncommitted main…” execution
instruction, authorizing MVP-04B1 only, together with the explicit Product Owner
Commercial Scope decision reproduced in the preceding bounded producer section.
The checkpoint remains `main` at `da88f0a23cc66696d688da7c9fba8e4152e0a87e`,
matching `origin/main` (0/0 divergence). All earlier MVP-04A and explicit-scope
changes remain uncommitted and are preserved. No Git integration or production
action is authorized or performed.

This section supersedes the preceding producer-only stop statement solely for
RFQ preparation and issue. It does not certify all of MVP-04. MVP-04B2 quote
capture, opening, comparison and award remediation: **NOT STARTED**. PO, GRN,
Inventory, AP, Accounting and Treasury behavior: unchanged.

### Delivered behavior

- RFQ List uses the accepted Contracts List reference, including header/Create,
  scoped search by number/title/PR/project, status/project quick filters, Jalali
  deadline filters, active business-label chips, count, whitelist sorting,
  compact status table, row `⋮` actions, pagination and RTL responsive layout.
- Contextual Create reloads the approved PR from existing create authority,
  preserves PR/project as a restricted hidden parent, and presents business
  identity. General Create uses the qualified scoped searchable approved-PR
  selector. Dates, identity and terms are grouped; field/service errors retain
  entered business values. Opening-before-deadline receives an inline error.
- Draft Detail is a preparation workspace: identity/project/PR, compact dates,
  actual state guidance, selected material/quantity/unit rows as primary content,
  source-line entry, explicit scope readiness and submission. Already selected
  PR lines are excluded from the entry selector. No quantities or scope policies
  are silently selected. Existing service validation remains authoritative.
- Submitted Detail presents tenant-owned active `BusinessParty` suppliers using
  business labels and checkboxes. Keys are generated in hidden fields. Missing
  scope/suppliers or invalid input cannot issue an RFQ. Selected suppliers are
  retained after validation failure.
- Every mutation control checks actual status, active tenant and project-scoped
  business permission. PR navigation additionally checks PR-view permission.
  Direct requests continue to use existing decorators and transactional services.
- Issued Detail is read-only for preparation. It shows each immutable version's
  own dates, terms, material/quantity/unit rows, pinned scope and policy flags,
  and supplier invitations. Version history uses related-object prefetching.
  Existing next-version scope and addendum entry are secondary `⋮` actions.
- Existing downstream buyer navigation remains a permission-aware secondary
  link; quote/comparison/award queries and panels were removed from the
  preparation page. No downstream action, service, permission or rule changed.
  The existing CEP-032 UI assertion now checks the preparation presentation
  instead of requiring the replaced quote-metadata panel.
- Choice validation translates malformed UUID errors and inaccessible selections
  into business-readable errors without echoing submitted technical values.
  Hidden-field errors use refresh/reopen guidance. Service retry-key terminology
  is translated at the presentation boundary; validation is not relaxed.

B1 touchset: `rfq_forms.py`, `rfq_ui.py`, `rfq_workspace.py`, `urls.py`, the
RFQ list/create/detail templates, `commercial_scope_forms.py` and
`commercial_scope_views.py` (error presentation), `test_cep032_workspace.py`,
new `test_mvp04b1.py` / `test_mvp04b1_browser.py`, and bounded evidence/report.
B1 adds **no models, migrations, permission codes, lifecycle transitions or
Product Surface configuration**. The already approved producer/migration from
MVP-04B is preserved, including historical legacy treatment and immutable scope
pinning. No new development migration was necessary for B1. The unrelated
pending Payroll 0010 remains outside this tranche; no full database currency
claim is made.

### Validation evidence and attribution

Validation uses the retained, fully migrated, task-owned isolated PostgreSQL
`test_mvp04b_...` database and the documented fixture-only explicit membership
assignments / guarded CASCADE cleanup / serialized rollback. The B1 runner is
[run_validation.py](../../../output/mvp-04b1/run_validation.py). Production and
normal development business data are not used as browser fixtures.

Initial focused run: 7/8 PASS; one new foreign-item fixture attempted to add an
item to an already approved PR. The fixture was corrected to respect the existing
draft-only item invariant; product rules were unchanged
([initial log](../../../output/mvp-04b1/focused-tests.log)).
The next attempt's business journey and Chrome checks passed but one forged-input
assertion correctly detected Django's raw malformed-UUID error; this was fixed in
the form layer. [Attempt log](../../../output/mvp-04b1/validation-attempt-2.log)
is retained as FAIL, with the full synthetic HTML response redacted because it
contained ephemeral CSRF fields. Neither failed run is relabelled PASS.

The first explicit-file lint invocation included an auto-generated migration
that repository Ruff configuration excludes; rerunning with `--force-exclude`
respected the existing policy. No migration was reformatted for B1. Both attempt
logs are retained under `output/mvp-04b1/*explicit-migration-attempt.log`.

Final source checks and real-Chrome responsive review are recorded below.

### B1 verification coverage

| Required area | Evidence |
| --- | --- |
| RFQ List, filters, chips, count, sorting, pagination | Chrome `list-1440/1024/390`, `list-filter-sort-chips`; HTTP list search/project/deadline/sort/page assertions |
| Approved PR contextual Create | Chrome `contextual-create-1440/1024/390`, `create-contextual-draft`; persisted PR/project equality assertions |
| General searchable approved-PR Create | Chrome `general-create-1440/1024/390`, `general-create-save`; scoped selector HTTP assertions |
| Eligible PR lines and explicit quantities | Chrome `line-invalid-retains-selection`, `line-select-add`; HTTP excludes selected/foreign lines and rejects excess quantity |
| Explicit scope; no default commercial assumptions | Chrome `explicit-scope-and-submit`; producer tests cover LINE/LOT/partial/split/alternate policies and PR lineage |
| Validation retention and technical-input rejection | Chrome `create-retains-validation`, `line-invalid-retains-selection`, `issue-key-error-retains-supplier`, `forged-hidden-pr-rejected`; HTTP forged PR/line/supplier/unit/key tests |
| Supplier selection and submit/issue | Chrome `supplier-selection-1440/1024/390`, `issue-supplier-required`, `issue-freezes-scope-and-invitations`; persisted invitations/scope/quantity assertions |
| Frozen issued history and addendum entry | Chrome `issued-readonly-1440/1024/390`, `addendum-navigation-back-refresh`; producer/addendum/immutable evidence regressions |
| Unauthorized, wrong tenant/project | Chrome `viewer-readonly`, `viewer-create-denied`, `viewer-scope-denied`, `foreign-tenant-reference`, `wrong-project-detail`, `wrong-project-contextual-create`; direct POST HTTP denials |
| Back, refresh and retry safety | Chrome scope PRG refresh and addendum Back/issued refresh; HTTP repeats the same issue submission and proves exactly one issued version |
| No pre-opening quote disclosure | Preparation page no longer queries/displays quote revisions, comparisons or awards; existing sealed-custody/sourcing regressions remain authoritative |
| Responsive RTL and route health | All principal list/create/draft/submitted/issued screens at 1440/1024/390; Chrome checks width, JS exceptions, response health, labels and visible UUID/hash absence |

Browser evidence uses installed Google Chrome
`C:\Program Files\Google\Chrome\Application\chrome.exe`, version
`156.0.8078.48`, headless via CDP, not a substituted Chromium runtime.
Only expected 400 validation / 403 permission / 404 inaccessible-reference
responses are accepted in denial scenarios. The qualified driver's existing
favicon-only network exclusion remains. Synthetic live-server teardown
“Broken pipe” messages are retained; they are not application 500 responses.

Source identity is captured in
[source-sha256.json](../../../output/mvp-04b1/source-sha256.json).
[Preserved-domain proof](../../../output/mvp-04b1/preserved-domain.json) verifies
that models, RFQ services, explicit scope services and Procurement 0017 match
their approved-producer checkpoint hashes exactly. B1 made no further mutation
to those authorities.

### B1 final result

- **61/61 regression tests PASS** in 313.598 seconds:
  [regression log](../../../output/mvp-04b1/final-validation.log). This covers
  existing RFQ/close/concurrency, sealed custody, sourcing comparison/award rules,
  explicit producer/migration/addendum boundaries, CEP-032 source/scope behavior,
  MVP-04A HTTP regression and the B/B1 Chrome tests. No B2 product remediation
  was undertaken to run these existing regressions.
- **21/21 final-source follow-up tests PASS** in 173.222 seconds:
  [follow-up log](../../../output/mvp-04b1/final-source-followup.log). After the
  final scope-unit error translation and responsive menu/layout fixes, this
  reran seven B1 HTTP tests, twelve producer tests and both B1 Chrome tests.
  Together the two runs validate **62 distinct tests**; repeat executions are
  not counted as additional distinct coverage.
- **36/36 B1 Chrome scenarios PASS**:
  [summary](../../../output/mvp-04b1/browser-summary.json),
  [batch results and screenshots](../../../output/mvp-04b1/browser/).
  Zero horizontal overflow, JavaScript exceptions, tracebacks or technical
  selector labels. Visible UUID/hash absence passes all B1 scenarios. No
  legitimate-route 404/500 or pre-opening quote disclosure was observed.
  Codex reviewed the list, create, draft, supplier and issued captures, including
  corrected desktop/mobile `⋮` menus and issued full-width item presentation.
  Product Owner visual acceptance is still **PENDING**.
- [System checks](../../../output/mvp-04b1/system-check.log),
  [template compilation](../../../output/mvp-04b1/templates-check.log),
  [migration drift](../../../output/mvp-04b1/migration-drift.log),
  [Ruff](../../../output/mvp-04b1/lint.log),
  [format checks](../../../output/mvp-04b1/format.log) and final diff whitespace:
  **PASS**. Ruff uses the repository's existing generated-migration exclusions.

Final branch/HEAD remain `main` /
`da88f0a23cc66696d688da7c9fba8e4152e0a87e` with all changes uncommitted.
No stage, commit, push, merge, branch or worktree operation occurred.
No CEP Registry or Roadmap state was changed. The retained isolated test DB and
bounded synthetic evidence remain available for reproducibility. No production
certification or full database currency is claimed.

**MVP-04B1 stops here. MVP-04B2 and later tranches: NOT STARTED.**

```text
MVP-04B1 FUNCTIONAL: PASS
RFQ PREPARATION JOURNEY: PASS
COMMERCIAL SCOPE PRODUCER: PASS
RFQ ISSUE / VERSION FREEZE: PASS
TECHNICAL LEAKAGE: PASS
TENANT/PERMISSION ISOLATION: PASS
BROWSER VALIDATION: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```


## MVP-04B2 — Quote → Protected Opening → Comparison → Award (2026-11-02)

Status: BOUNDED IMPLEMENTATION AND VALIDATION COMPLETE under the explicit attached Human request for MVP-04B2 only.
This bounded MVP tranche is not a CEP lifecycle event; the completed CEP queue
and production gates remain unchanged. The request is the execution contract.
Grounding: current uncommitted main; HEAD = origin/main =
`da88f0a23cc66696d688da7c9fba8e4152e0a87e`, upstream divergence 0/0.
Prior dirty changes and their hashes are recorded in
[the start-state artifact](../../../output/mvp-04b2/start-state.json).

Actual touch set: existing `rfq_actions.py`, `rfq_action_forms.py`, new read-only
`buyer_ui.py`, buyer workspace/action templates, the bounded confidential-document
URL, focused HTTP/real-Chrome tests, task validation harness/evidence, and this
report. Shared Chrome driver receives only a source-file upload test capability
if required. No models, migrations, Domain services/algorithms, permissions,
SoD, Product Surface or downstream purchasing/inventory/financial changes.
Prior uncommitted MVP-04A, commercial-scope and MVP-04B1 work is preserved.

Established Domain constraints: receipt metadata precedes commercial assertions;
internal custody requires a closed RFQ and an effective submitted revision.
Capture derives receipt integrity from actual supplied bytes and disposes of
the temporary source; it does not claim file custody or scanner approval.
The UI explains retaining the original for post-close protected custody.
Only real processing assessments can satisfy opening; no processing evidence
is manufactured by product code. Award rejection/abstention are not registered
Domain transitions. No new state is invented. Existing lot indivisibility also
applies to No Award preparations; unsupported combinations remain denied.


### Delivered MVP-04B2 boundary

- One RTL buyer workspace groups invitation/receipt history, protected opening,
  admissibility, comparison/evaluators and award decisions. Contextual menus and
  business-labelled selectors carry exact RFQ/revision/comparison references;
  technical keys are hidden. Issued RFQ materials/quantities remain explicitly
  distinguished from confidential supplier assertions.
- Receipt capture hashes actual structurally validated source bytes, records only
  existing metadata and removes its private temporary file. No fingerprint or
  internal source-reference entry is required. The screen explicitly explains
  that the original must be retained for post-close custody. Corrections use new
  immutable revisions; submit/supersede/withdraw call the original services.
- Post-close original/attachment custody is connected to each effective submitted
  quote. Attachment slots and retry identities are generated internally. The
  compatibility custody page also hides its optional technical controls, checks
  the existing permission against the exact project on GET, and supplies source
  navigation. No new permission or default grant is introduced.
- Per-revision guidance distinguishes sealed, awaiting prerequisites, eligible
  for opening, pending independent approval, opened without content access,
  accessible, late, withdrawn and superseded records. Actual timing, closing,
  package, independent actor, processing and grant requirements remain enforced
  by the unchanged Domain services.
- The new RFQ-bound document delivery adapter uses the existing audited protected
  delivery service. Content/comparison selectors intersect exact active grants
  and opening events; revoked grants hide commercial data and deny downloads.
  Buyer pages and delivered/denied document responses are private/non-cacheable.
- Admissibility proposals and immutable decisions retain reasons, evidence,
  independent approval and explicit correction lineage. Late and superseded bids
  remain visible in metadata history; they are not silently discarded or made
  eligible for opening by the UI.
- Comparison cards separate supplier assertions, server-derived normalized
  amounts and evaluator recommendations/evidence. Source locators, alternate
  bases, admissibility, evaluator appointments and conflict disposition remain
  visible only to authorized readers. No client-side commercial calculation or
  supplier ranking/selection is introduced. Finalized versions remain immutable;
  completed preparation records no longer advertise another evaluation step.
- Award proposals carry explicit quantities from the selected final comparison.
  Independent finalization, split/partial/lot/alternate constraints and explicit
  No Award call the existing services. History displays approver, reason,
  evidence, RFQ version, comparison and quote-revision/quantity lineage. Only an
  effective awarded decision describes a future PO step; a superseded award does
  not continue toward PO. No PO is created or linked to an active creation action.
- Exact contextual submit/withdraw/revocation retries retain the original target
  and resolve through Domain idempotence. Invalid or out-of-scope choices still
  fail closed; hiding a control never substitutes for authorization.

Touch-set refinement: the compatibility custody form/template and its scoped
read adapter in `forms.py`, `views.py` and `sealed_evidence_custody.html` are part
of this same sourcing capability. Existing buyer-action regression fixtures now
supply actual source files and explicit test-only Commercial Scope definitions;
`test_quotes.py` adds the same explicit fixture definition before issue. No
assertion was removed or weakened. The shared Chrome driver adds actual local
file-input handling and awaited browser assertions for content-denial checks.

### Validation and attribution

**MVP-04B2 implementation and bounded validation: COMPLETE.**
No unresolved in-scope functional or browser blocker remains.

- [Final validation](../../../output/mvp-04b2/final-validation.log): **22/22 PASS**,
  104.735 seconds. Includes eight new HTTP/security/retry checks, four original
  quote/revision/concurrency tests, eight buyer-action regressions, the existing
  custody-route isolation test and final-history Chrome validation.
- [Affected-boundary run](../../../output/mvp-04b2/regression-attempt-1.log):
  95 tests; 91 passed and four quote fixture errors occurred before receipt code
  was reached. Each failed at the unchanged explicit Commercial Scope issue gate.
  Their shared fixture now explicitly defines its scope; all four original tests
  pass in final validation. The other 91 successful checks remain evidence for
  unchanged RFQ, close, sealed custody, opening, admissibility, comparison/award,
  Commercial Scope, MVP-04B1, PR and workspace boundaries. This original command
  remains recorded as FAILED; it is not relabelled or represented as a fresh
  95-test clean run. Unchanged heavy migration/concurrency checks were not rerun.
- [Initial browser run](../../../output/mvp-04b2/browser-attempt-1.log): the
  comparison/admissibility/conflict/award journey passed; the opening fixture
  stopped because its synthetic owner lacked explicit protected-opening
  permission. The fixture was corrected; no product grant was changed.
- [Opening/split/lot/forms run](../../../output/mvp-04b2/browser-final.log): all
  three selected Chrome tests, compatibility custody check and existing custody
  isolation test passed. Four extra portal checks initially failed at the same
  quote fixture scope gate. The corrected shared fixture resolves that gate.
- [Broader focused replay](../../../output/mvp-04b2/final-focused-regression.log):
  23/24 passed. One **BASELINE TEST DEBT** remains outside the bounded buyer UI:
  `SupplierPortalUiTests.test_external_context_is_exact_scope_and_submission_is_idempotent`
  sends only a fingerprint/source reference at lines 79–90, omitting the actual
  upload required by the existing external-portal original-evidence contract.
  The unchanged portal submission endpoint correctly returns 400. This stale
  portal test was not altered or counted as PASS. The final focused command
  includes only its directly affected custody-route check, which passes.
- [Browser summary](../../../output/mvp-04b2/browser-summary.json): **77 distinct
  successful real installed-Chrome scenarios**, headless, with emulated viewports
  1440/1024/390px. All checked document widths equal scroll widths; no JS exception,
  valid-journey 404/500 or unexpected page HTTP error occurred. Intentional
  400/403/404 denials are retained. The qualified driver excludes the existing
  missing favicon from asset-error checks. Screenshots and completed batches are
  retained in [browser evidence](../../../output/mvp-04b2/browser/).
- Django [system check](../../../output/mvp-04b2/system-check.log),
  [Ruff](../../../output/mvp-04b2/lint.log), formatting, UTF-8/template parsing and
  [whitespace check](../../../output/mvp-04b2/diff-check.log): PASS. Git emits only
  expected LF/CRLF advisory messages. [Migration drift](../../../output/mvp-04b2/migration-drift.log):
  no changes detected.
- [Configured Development migration plan](../../../output/mvp-04b2/development-migration-plan.log):
  only unrelated `payroll.0010_cep069_reviewed_statutory_context` is pending; it
  was not applied. There is no new MVP-04B2 migration. Tests use the previously
  migrated task-owned `test_mvp04b_7a7f83c96a` PostgreSQL database, retained for
  reproducibility, with documented explicit actor-assignment and guarded CASCADE
  fixture cleanup adaptations. No production action occurred.

### Requested browser matrix

| Criterion | Result / retained scenario examples |
| --- | --- |
| Issued RFQ / invitation state | PASS — `issued-invitations-*` |
| Capture / revision / submit | PASS — `capture-source-receipt`, `correction-new-revision`, `submit-*` |
| Withdraw / supersede / immutable history | PASS — `withdraw-current-revision`, submitted revision/state assertions and original regressions |
| Early opening / closed-before-time denial | PASS — `early-opening-denied-issued`, `closed-before-opening-time` |
| Protected custody / real-readiness requirement | PASS — `custody-original-source`, `opening-missing-processing-denial` |
| Independent opener / authorized opening | PASS — `opening-independent-actor-denial`, `independent-opening-approved` |
| Confidential / revoked content access | PASS — `document-sealed-access-denied`, `opened-without-access-grant`, `authorized-source-document`, `revoked-document-access` |
| Admissibility / nonconformance / correction | PASS — `nonconformance-*`, `admissibility-corrective-*` |
| Late / withdrawn / superseded records | PASS — `late-receipt-metadata`, quote history and original service assertions |
| Comparison create / evaluate / immutable finalize | PASS — `comparison-explicit-assertions`, `evaluate-source-assertions`, `comparison-independent-finalize` and Domain regressions |
| Conflict / independent disposition | PASS — `declare-evaluator-conflict`, `unresolved-conflict-blocks-evaluation`, `independent-conflict-disposition` |
| Award proposal / independent approval / SoD denial | PASS — `partial-award-proposal`, `award-self-approval-denied`, `award-independent-finalize` |
| Split / partial / indivisible lot / alternate | PASS — `split-*`, `lot-partial-allocation-denial`, `lot-complete-allocation`, `alternate-*` |
| Explicit No Award / preserved previous decision | PASS — `no-award-explicit-*`, `final-history-*` |
| Cross-project / tenant / unauthorized user | PASS — `cross-project-workspace-denial`, `cross-tenant-workspace-denial`, `unauthorized-capture-denial` |
| Refresh / back / retries | PASS — `submit-effective-revision` reload/back/forward, receipt/award/revocation replay HTTP assertions |
| 1440 / 1024 / 390, forms and workspace | PASS — issued/comparison/award/history captures and `capture/comparison/award-form-*` |
| No technical-key entry / no overflow / no automatic PO | PASS — scenario DOM assertions, width metrics, protected-content assertions and downstream-count checks |

### Browser storage-isolation closeout

The first opening browser fixture used the default private storage root and left
one 47-byte synthetic original. Its bytes were verified against the generated
`synthetic-source.pdf` before removing only that exact file; no customer file or
recursive directory cleanup was performed. See [cleanup evidence](../../../output/mvp-04b2/storage-cleanup.log).
The fixture now uses a task-temporary protected root with automatic cleanup.
The complete receipt → close → custody → opening → grant → download → revocation
Chrome test was rerun with that isolation: **1/1 PASS**
([isolated-storage validation](../../../output/mvp-04b2/opening-isolated-storage-validation.log)).
No protected-document file remains in Git status from this task.

### Explicit limits and closeout

CLEAN processing assessments in browser/Domain tests are **clearly identified
synthetic fixtures in the isolated test database**. No product code, Development
record, scanner result or processing adapter was fabricated to unlock opening.
The missing-processing browser denial is independently proved before adding the
fixture. These results do not certify a deployed scanner or production readiness.

The existing Domain has no separate Award Rejected or evaluator-abstention
transition. Browser validation proves approval and rejection of prohibited
commands; it does not claim a new persisted business rejection/abstention state.
No Award is supported where the existing Domain permits it; unchanged lot
indivisibility denies a zero-allocation lot No Award. No new policy was inferred.
Product Owner visual acceptance, real-user UAT and production certification remain
PENDING / NOT EXECUTED. Codex inspected desktop, tablet and mobile screenshots;
that is not Human visual acceptance.

[Preservation check](../../../output/mvp-04b2/preservation-check.json) confirms all
15 prior modified files outside the intentional overlap are byte-identical,
including the existing models, audit catalogue, Commercial Scope producer,
RFQ lifecycle and earlier templates/tests. Intentional overlap is confined to the
buyer/custody UI, route additions, prior procurement view file and Chrome helper.
No permission catalog, SoD policy, comparison/award algorithm, Product Surface,
PO/GRN/Inventory, AP/Accounting/Treasury or financial posting changes were made.

Final branch/HEAD: `main` /
`da88f0a23cc66696d688da7c9fba8e4152e0a87e`, matching cached `origin/main`.
All changes remain uncommitted. No branch/worktree, add, commit, push or merge.
No CEP Registry lifecycle or Roadmap direction change is applicable.
**MVP-04C Purchase Order and later work: NOT STARTED. STOP after MVP-04B2.**

```text
MVP-04B2 FUNCTIONAL: PASS
QUOTE JOURNEY: PASS
PROTECTED OPENING: PASS
ADMISSIBILITY / COMPARISON: PASS
AWARD / NO-AWARD: PASS
CONFIDENTIALITY / SOD: PASS
TECHNICAL LEAKAGE: PASS
TENANT/PERMISSION ISOLATION: PASS
BROWSER VALIDATION: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```


## MVP-04C — Award → Purchase Order (2026-11-02)

Status: COMPLETE within the attached bounded Human request for MVP-04C only;
Product Owner visual acceptance remains PENDING.
Entry gate: latest MVP-04B2 section records successful bounded completion and no
unresolved in-scope blocker. Its external-portal stale-test debt and pending
Human visual acceptance do not reopen B2. No B2 repair or domain expansion.
Grounding: uncommitted local main; HEAD = cached origin/main =
`da88f0a23cc66696d688da7c9fba8e4152e0a87e`, divergence 0/0.
The [start snapshot](../../../output/mvp-04c/start-state.json) records prior files.

Intended touch set: new PO presentation forms/selectors/adapters and workspace
views; PO list/create/detail/source templates; PO URL targets; existing legacy
Create presentation integration; buyer award continuation only; minimal existing
GRN Create context adapter; focused HTTP and installed-Chrome tests, harness and
evidence; this completion report. Models/migrations, Domain mutation services,
Award algorithms, PO lifecycle, permission catalogue/SoD, Product Surface and all
receiving/inventory/financial business behavior remain unchanged.

Existing consumer contract: `create_purchase_order_from_award` consumes explicitly
selected whole allocations for exactly one supplier. It rejects superseded and
No Award decisions, any prior active consumption, unmapped lots, missing unit
prices and prices incompatible with two-decimal PO storage. Partial award
quantities remain valid whole allocations; no arbitrary sub-allocation quantity
entry or inferred lot-to-line mapping will be added. Issuing uses the original
immutable PO-version service; no award automatically creates or issues a PO.
GRN work is limited to carrying a qualified issued-PO parent into the existing
Create screen, with no GRN lifecycle or posting change.

### Delivered behavior and preserved authority

- Final effective awards expose permission-scoped, supplier-specific
  `ایجاد سفارش خرید` continuation. The server resolves Award, RFQ, supplier and
  project; business-labelled checkboxes select eligible whole allocations.
  Awarded quantities and prices are inherited, never manually reconstructed.
  Split awards produce separate supplier drafts and display consumed/remaining
  quantities. Superseded, No Award, wrong-supplier and consumed sources fail
  closed. No Award automatically creates or issues a PO.
- The adapter calls the existing `create_purchase_order_from_award` service.
  It locks and revalidates context/authorization inside its transaction and
  rejects forged source, supplier, project, quantity and allocation inputs.
  Exact retries must match the existing header and allocation set; the original
  business-number idempotency contract is retained. Concurrent requests for the
  same allocation yield one draft and one business denial, conserving quantity.
- PO List follows the accepted Contracts pattern: search, scoped filters, active
  chips, count, allowlisted sorting, pagination, status badges, compact RTL
  rows/mobile cards and secondary actions. Create and Detail use the accepted
  forms and state-aware layout. Errors retain valid entered values and use safe
  business labels, including invalid-allocation errors without UUID echo.
- The original direct Create service path and validation remain available with
  scoped business selectors. Direct and sourced lineage are distinguished;
  historical direct POs receive no fabricated RFQ/Award lineage. The generic
  line-add UI cannot append ungoverned rows to a sourced PO; legacy draft line
  entry continues through its existing service.
- Explicit Issue invokes the original lifecycle/version service. Issued Detail
  presents immutable current-version rows, source Award/allocation lineage and
  version history. Existing Domain amounts/properties remain authoritative; no
  new financial metrics or calculations were introduced. Repeated Issue cannot
  create another issued version.
- Eligible issued POs expose `ثبت رسید کالا` only with existing GRN permission,
  project scope and current-version prerequisites. The minimal context adapter
  pins a server-qualified PO in the existing GRN Create screen. Browser entry
  creates no receipt; GRN lifecycle/business rules were not changed.

Implementation: `order_ui.py`, `order_forms.py`, `order_workspace.py`, their PO
templates and URL targets; bounded presentation integration in existing
`views.py`, `rfq_actions.py`, buyer workspace and shared procurement form.
Focused tests are `test_mvp04c.py` and `test_mvp04c_browser.py`.

### Validation and regression attribution

- [Affected regressions](../../../output/mvp-04c/regression-attempt-1.log):
  **41/41 PASS**. Includes Award/comparison, allocation consumption, PO
  create/issue/version, RFQ buyer actions, MVP-04B2, legacy direct PO, source
  authorization/CSRF and concurrent allocation consumption.
- [Financial boundary check](../../../output/mvp-04c/financial-boundary-validation.log):
  **1/1 PASS**, added after the affected suite. Actual sourced Create and Issue
  leave organization-scoped counts unchanged for GoodsReceipt, StockTransaction,
  SupplierInvoice, Obligation, JournalEntry, TreasuryMovement and ProjectCostFact.
  Thus **42 successful focused checks across these two runs**, not a claimed
  single 42-test run.
- [Final Chrome run](../../../output/mvp-04c/browser-final.log): **3/3 PASS**;
  retained legacy browser test passed in
  [the initial browser run](../../../output/mvp-04c/browser-attempt-1.log).
  Four browser test methods have successful retained evidence. The
  [browser summary](../../../output/mvp-04c/browser-summary.json) records
  **46 distinct successful scenarios**, using installed Chrome headless at
  **1440 / 1024 / 390px**. Every retained scenario has no horizontal overflow
  and no JavaScript exception; no application HTTP 500 or valid-route 404.
  Expected 400/403/404 denials are explicitly asserted; missing favicon noise
  is excluded by the established driver.
- Scoped Ruff lint/format, Django system check, six-template parse and
  UTF-8/Persian integrity checks PASS. Migration drift: **No changes detected**.
  Development migration plan retains only unrelated
  `payroll.0010_cep069_reviewed_statutory_context`; it was not applied. There is
  no MVP-04C migration or production action.

Browser coverage and retained evidence under `output/mvp-04c/browser/`:

| Required behavior | Successful scenario evidence |
| --- | --- |
| Final award entry, fixed source/supplier/project, partial awarded quantity | `award-contextual-po-entry`, `source-create-*`, `fixed-source-create-*`, `single-partial-award-po-draft` |
| Split suppliers, exact remaining quantities | `split-supplier-selection`, `split-supplier-1-draft`, `split-supplier-2-draft`, `split-all-consumed-remaining-zero` |
| Duplicate/excess/wrong supplier and forged source denial | `duplicate-allocation-consumption-denied`, `source-excess-quantity-denied`, `forged-supplier-denied`, `forged-project-denied`, `forged-allocation-denied`, `split-wrong-supplier-allocation-denial` |
| Draft/source lineage, explicit Issue, frozen issued Detail | `draft-detail-*`, `issue-po-explicit-action`, `issued-detail-*` |
| Legacy Create, validation retention, line entry and Issue | `legacy-create-*`, `legacy-create-retention`, `legacy-create-draft`, `legacy-line-entry-and-issue` |
| Search/filter/sort/chips/pagination | `po-list-*`, `list-filter-sort-chips`, `list-pagination-second-page` |
| Sourced form retention and refresh/back/forward/retry | `source-validation-retention`, `single-partial-award-po-draft`; HTTP exact-replay checks |
| User, tenant and project boundaries | `unauthorized-po-create`, `unauthorized-source-entry`, `wrong-tenant-po-detail`, `wrong-tenant-award-source`, `wrong-project-po-detail`, `wrong-project-source` |
| Issued PO to existing GRN Create, no automatic receipt | `issued-po-grn-entry-*` |

`*` denotes the three required widths. Chrome batches retain screenshots,
document dimensions, text, HTTP status and console evidence. Codex inspected
desktop and mobile screenshots; this does not confer Human visual acceptance.

Initial focused attempts failed on missing authorization-helper `message`
arguments and a test-helper argument collision; these were corrected and the
focused suite passed. The first browser run found a real UUID echo in invalid
allocation validation. Safe business error messages fixed it, and subsequent
source/split/final browser runs passed. Failed logs retain their original status;
they are not relabelled as successful. The legacy browser scenario passed in
that first run and is retained without unnecessarily repeating it.

The isolated, fully migrated PostgreSQL validation database and qualified B2
harness use explicit fixture actor assignments and guarded fixture cleanup for
existing foreign keys. CLEAN document assessments are synthetic test fixtures;
they neither alter product processing rules nor certify a deployed scanner.
No protected-document file from this tranche appears in Git status.

### Limits, preservation and closeout

Partial awards are supported as approved whole allocations. The unchanged
consumer does not support arbitrary partial consumption of one allocation;
the UI does not invent it. Unmapped lots and incompatible price precision keep
their existing fail-closed behavior. No new business policy was inferred.

The [preservation check](../../../output/mvp-04c/preservation-check.json)
confirms **42 pre-existing files byte-identical** outside the five declared
overlap files. Models, Domain mutation services, migrations, Award algorithms,
RFQ/Quote/comparison rules, permission catalogue/SoD and Product Surface are
unchanged from the start snapshot. Prior uncommitted MVP work is preserved.
No GRN business implementation, Inventory, AP, Accounting, Treasury/payment or
Project Cost authority change was made. No CEP lifecycle was reopened; Registry
and Roadmap changes are not applicable to this explicit bounded MVP tranche.

Final branch/HEAD: `main` /
`da88f0a23cc66696d688da7c9fba8e4152e0a87e`, equal to cached `origin/main`,
divergence 0/0. All changes remain uncommitted. No branch/worktree, add, commit,
push or merge. Product Owner visual acceptance, real-user UAT and production
certification remain PENDING / NOT EXECUTED.

**MVP-04D: NOT STARTED. STOP after MVP-04C.**

```text
MVP-04C FUNCTIONAL: PASS
AWARD → PO JOURNEY: PASS
AWARD ALLOCATION CONSUMPTION: PASS
PO CREATE / ISSUE: PASS
SOURCE LINEAGE: PASS
LEGACY DIRECT PO REGRESSION: PASS
TECHNICAL LEAKAGE: PASS
TENANT/PERMISSION ISOLATION: PASS
PO → GRN CONTINUATION: PASS
BROWSER VALIDATION: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```


## MVP-04D — Purchase Order → Goods Receipt (2026-11-02)

Status: COMPLETE within the explicit attached bounded Human request for MVP-04D.
Product Owner visual acceptance remains PENDING. The MVP-04C entry gate passed:
its latest section records successful completion without an unresolved in-scope
blocker. No MVP-04C repair or expansion was performed.

Branch: current uncommitted `main`; start/end HEAD and cached `origin/main`:
`da88f0a23cc66696d688da7c9fba8e4152e0a87e`, divergence 0/0.
[Start state](../../../output/mvp-04d/start-state.json) and
[authority/boundary manifest](../../../output/mvp-04d/authority-and-boundary-manifest.json)
retain the dirty-tree inventory and source/request hashes. This explicit MVP
tranche is not a CEP lifecycle event; Registry and Roadmap updates do not apply.
The earlier MVP-04D NOT STARTED statements above remain historical closeout text.

### Delivered behavior and preserved Domain contracts

- Issued PO → contextual GRN Create → Draft Detail → receipt lines → explicit
  Post → posted Detail/history is complete. Context is tenant/project-scoped and
  server-resolved; PO is fixed, supplier/project are inherited read-only business
  labels, and the existing service selects the governing issued version.
  Ineligible visible POs show a business explanation; inaccessible sources fail
  closed. General Create uses the existing searchable-selector infrastructure
  over eligible scoped POs, with searchable business labels and no manual IDs.
- List follows the accepted BONIRA pattern: header/action, business search,
  status/project/supplier/date filters, chips, count, allowlisted sorting,
  compact RTL table/mobile cards, status badges, `⋮` actions and pagination.
  Create retains valid inputs on errors. No warehouse selector was added to GRN.
- Receipt quantities come from pinned PO-version lines and the same posted
  GoodsReceiptItem sums used by the existing posting service. Ordered, other
  valid posted receipts, current receipt and remaining quantities are explicit.
  Other receipts are labelled as current evidence, not a fabricated historic
  cutoff. Drafts do not reserve quantities. Invalid/excess/duplicate/foreign PO,
  project and tenant lines fail closed, including transaction-time revalidation.
  Decimal precision and existing units are retained.
- Preparation uses focused transactional adapters calling the original
  `create_goods_receipt` / `add_goods_receipt_item` services. Exact header retries
  reuse the original receipt only for matching PO/version/date/notes; changed
  payloads fail closed. Concurrent identical creation retains one receipt.
  Receipt-number uniqueness remains the existing business identity contract.
- Explicit Post calls the original `post_goods_receipt`. Original locks,
  authorization, audit, pinned-version control, posted-quantity recheck and PO
  completion remain intact. Competing draft posts cannot over-receive. Repost
  is denied without duplicate receipt or audit effects. Posted evidence is
  read-only; posted header/line model mutation remains denied.
- Draft actions follow actual lifecycle support: adding unused eligible lines
  and posting valid receipts. There is no existing line-update or draft-void
  service; neither operation was invented. Posted Void uses the original service
  and reason requirement, retains immutable lineage, and reopens a completed PO
  only under its existing rule. Posted downstream Inventory receipts block Void;
  Procurement never reverses Inventory.
- Detail shows PO identity, supplier/project, received date, governing version,
  quantities, immutable issued-source evidence, created/posted/voided actors and
  timestamps, void reason and all sibling receipt history. Stock handoff status
  is shown from actual stock evidence only with the existing viewing permission.
- `ثبت ورود به انبار` appears per eligible posted line only when the existing
  Inventory permission, Product Surface and compatible warehouse/material/source
  prerequisites allow it. Its link qualifies the source through the existing
  Inventory form queryset and prefills receipt line/material/project/quantity and
  reference. Navigation, refresh and back/forward create no Inventory draft or
  movement. Inventory's existing forms, source contract, services, posting and
  reversal rules were not redesigned.
- Posting GRN remains Procurement evidence only. Tests compare organization-
  scoped StockTransaction, SupplierInvoice, Obligation, JournalEntry,
  TreasuryMovement and ProjectCostFact counts and the real Inventory balance
  before/after partial/full receipt and handoff navigation: unchanged.
  No AP, Accounting, Treasury/payment or Project Cost authority was introduced.

Actual touch set: new `receipt_actions.py`, `receipt_forms.py`, `receipt_ui.py`,
`receipt_workspace.py`; receipt URL targets; Create/List/Detail and quantity
partial templates; a 22-line context-only addition to Inventory's existing
Create view; focused HTTP/concurrency/Chrome tests; isolated validation harness,
evidence and this report. Product models, migrations, Domain mutation services,
Award/RFQ/Quote behavior, PO lifecycle/version semantics, permissions/SoD and
Product Surface remain unchanged from entry.

### Validation and evidence

- [Final affected regression](../../../output/mvp-04d/affected-regression-final-2.log):
  **40/40 PASS**. This run includes 18 MVP-04D checks (original service/model
  assertions reused with explicit fixture authority included), all 10 MVP-04C
  checks, and all 12 existing CEP-034 Inventory receipt-contract checks.
  Covers partial/second/full receipt, four-decimal remaining quantity, concurrent
  header retry and posting, wrong source/tenant/project, permissions, CSRF,
  suspended-tenant mutation denial, history, Inventory-dependent Void denial,
  financial boundaries and independently approved PO version changes with older
  GRNs retaining their original pin.
- [Final Chrome run](../../../output/mvp-04d/browser-final.log): **3/3 PASS**,
  **39 distinct successful scenarios** retained in the
  [browser summary](../../../output/mvp-04d/browser-summary.json). Actual installed
  Chrome runs headless at **1440 / 1024 / 390px**, with screenshots, text,
  dimensions, HTTP and JavaScript evidence. All retained scenarios have zero
  horizontal overflow, zero JavaScript exceptions and zero HTTP 500s. No valid
  application-route 404; expected 400/403/404 denials are explicitly asserted.
  The existing driver's favicon exclusion remains unchanged. Codex inspected
  desktop/mobile screenshots and corrected the empty Create-project label and
  cramped mobile quantity heading; final screenshots verify both fixes.
- [Lint](../../../output/mvp-04d/lint.log),
  [format](../../../output/mvp-04d/format.log),
  [Django check](../../../output/mvp-04d/system-check.log),
  [template/Persian integrity](../../../output/mvp-04d/templates-check.log),
  [diff whitespace](../../../output/mvp-04d/diff-check.log) and
  [migration drift](../../../output/mvp-04d/migration-drift.log): PASS.
  No schema/data migration was added. The development migration plan still has
  only unrelated `payroll.0010_cep069_reviewed_statutory_context`; not applied.
  The isolated validation database has
  [zero unapplied migrations](../../../output/mvp-04d/isolated-migration-plan.log).
- [Preservation check](../../../output/mvp-04d/preservation-check.json):
  **55 pre-existing source files outside declared overlap are byte-identical**;
  no unexpected changes across 412 snapshotted files.
  [Final source manifest](../../../output/mvp-04d/final-source-manifest.json)
  identifies delivered code/template bytes.

| Browser requirement | Successful retained scenarios |
| --- | --- |
| Issued PO, inherited context, eligible general search | `issued-po-contextual-create`, `context-create-*`, `general-create-*`, `general-eligible-po-search-and-second-grn` |
| Business PO-line labels, partial/second/full quantities | `partial-line-entry`, `partial-post-grn`, `second-receipt-exact-remaining-full-post` |
| Excess/wrong source/project/tenant denial | `excess-receipt-denied`, `wrong-po-line-denial`, `forged-project-context-denial`, `cross-tenant-*`, `cross-project-*` |
| Draft, posted immutable Detail and completed PO | `draft-detail-*`, `posted-detail-*`, `posted-immutable-retry-refresh`, `completed-po-*` |
| Valid Void and Inventory-dependent denial | `valid-void-with-business-reason`, `void-denied-inventory-dependency` |
| Retry, refresh and navigation safety | `duplicate-line-retry-denied`, `header-create-and-exact-retry`, `posted-immutable-retry-refresh`, `posted-grn-inventory-context` |
| Existing Inventory contextual entry, no automatic effects | `posted-grn-inventory-context`; focused and Chrome database boundary assertions |
| Unauthorized user, List/forms/responsiveness | `unauthorized-receipt-create`, `receipt-list-*`, `list-filter-sort-active-chips`, `list-pagination-second-page`, `create-validation-retains-input` |

`*` covers the required widths where applicable. Automated screenshots do not
confer Product Owner visual acceptance or real-user UAT.

### Failed attempts, environment qualification and closeout

Failed logs retain their original outcomes. Initial focused tests exposed fixture
mistakes (missing balance-reader actor and stale in-memory PO after Issue), then
11/11 passed. Added validation found that suspended-session requests can safely
redirect to organization selection after context removal; the assertion now
requires that exact redirect and unchanged receipt data. An independent change
approver also needed an explicit membership role assignment in the test fixture.
Neither finding changed product authorization or tenant lifecycle.

The first broader run exposed legacy retained-FK cleanup/catalog restoration debt
in the existing Inventory concurrency fixture. The local MVP-04D harness applies
its established guarded CASCADE cleanup and serialized fixture restoration, with
no changes to legacy product code. Fresh isolated schema initialization was
cancelled when migration overhead became excessive; its incomplete synthetic DB
was discarded. A clone of the fully migrated isolated baseline was used instead.
Retained synthetic rows initially caused setup-only uniqueness collisions; the
clone was flushed. Secondary-alias post-migrate validation encountered a default-
alias catalog lookup, after which the runner's default isolated test connection
restored the catalog correctly. Final regression and Chrome runs pass on that
qualified clone. See [database qualification](../../../output/mvp-04d/database-qualification.json).
No production operation or development business-data mutation was performed.

No unresolved in-scope blocker or required validation remains. UI is limited to
existing line-add/post/posted-void semantics; unsupported line updates and draft
void remain unavailable. Receipt history intentionally reports current sibling
receipt states and quantities. Inventory handoff implementation/remediation is
reserved for MVP-04E; only the authorized contextual entry adapter was added here.

Branch/worktree created: NO. Git add/commit/push/merge: NOT EXECUTED.
All work remains uncommitted on `main`; prior MVP work is preserved.
Human Sign-off, real-user UAT, Production Certification and Production Cutover:
NOT EXECUTED. Product Owner visual acceptance: PENDING.

**STOP after MVP-04D. MVP-04E: NOT STARTED.**

```text
MVP-04D FUNCTIONAL: PASS
PO → GRN JOURNEY: PASS
PARTIAL / FULL RECEIPT: PASS
GRN POST / IMMUTABILITY: PASS
GRN VOID RULES: PASS
NO AUTOMATIC INVENTORY EFFECT: PASS
GRN → INVENTORY CONTINUATION: PASS
TECHNICAL LEAKAGE: PASS
TENANT/PERMISSION ISOLATION: PASS
BROWSER VALIDATION: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```


## MVP-04E — GRN → Inventory Handoff (2026-11-02)

Status: COMPLETE within the explicit attached bounded Human request for MVP-04E.
Product Owner visual acceptance remains PENDING. Entry gate: the latest MVP-04D
section records successful completion with no unresolved in-scope blocker.
MVP-04D was not reopened or expanded. Earlier NOT STARTED statements are retained
as historical closeout text.

Branch: current uncommitted `main`. Start/end HEAD = cached `origin/main` =
`da88f0a23cc66696d688da7c9fba8e4152e0a87e`, divergence 0/0.
[Start state](../../../output/mvp-04e/start-state.json) and
[authority/boundary manifest](../../../output/mvp-04e/authority-and-boundary-manifest.json)
retain dirty-tree grounding and request/source hashes. This explicit bounded MVP
tranche does not reopen a CEP or change program direction; Registry and Roadmap
updates do not apply.

### Delivered journey and authority boundaries

- Posted GRN → contextual Inventory receipt entry → receipt draft → explicit
  Inventory Post → real warehouse balance is complete. The source is reloaded
  from tenant/project-scoped posted GRN lines with a governing PO version.
  Opening the page, refreshing or navigating back/forward creates no draft or
  stock effect. Unposted, void, inaccessible and already-consumed entry links
  fail closed. Existing consumed/reversed occurrences are reached through their
  retained movement Detail, never reset to a new source occurrence.
- General Create offers a scoped, searchable eligible GRN-line selector using
  the existing business-choice widget. Selection remains on the page until
  explicit Continue, using the existing explicit-submit control. The contextual
  form fixes the source and displays material, unit, project and exact complete
  source quantity as business labels. Only number, compatible destination,
  movement date, reference and notes require business input. Source values are
  derived again for the service call; forged source/material/unit/project/
  quantity/type/source-warehouse values are denied, never silently accepted.
- Warehouse choices reuse the existing scoped active/archival rules and the
  existing movement requirement for matching project or a central warehouse.
  No Site ownership or new warehouse policy was introduced. Incompatible and
  foreign warehouses fail server-side validation; valid entered values remain.
  Search results, forms and errors use business names without customer UUID/key
  entry or raw Django labels.
- Create calls the existing `create_stock_transaction` receipt contract and
  redirects to Draft Detail. It never posts automatically. The existing contract
  retains one exact occurrence: equivalent draft/posted/reversed retries reuse
  the original target and state; changed payloads or competing new references
  fail. No new retry-key or deduplication policy was added. Original organization
  serialization, source locks, retained audit evidence and uniqueness remain
  authoritative. Concurrent HTTP acceptance produces one draft and no balance.
- List follows the accepted BONIRA pattern: page header/action, business search,
  status/warehouse/project/type/date filters, active chips, count, allowlisted
  sorting, compact RTL rows/mobile cards, badges, `⋮` actions and pagination.
  Warehouse, quantity/unit, material/project, source GRN and dates are readable;
  no unsupported financial valuation is shown. Existing non-receipt preparation
  remains available through the other-movements form and original services.
- Draft, posted and reversed Detail show source lineage, quantity/unit, project,
  warehouses, date/reference/notes and actor/timestamp evidence. Drafts expose
  explicit `ثبت نهایی ورود به انبار` when state and permission allow. Post calls
  the original Inventory posting authority, including workflow enforcement;
  posted evidence is read-only. Existing non-receipt workflow-request routes
  and controls remain available. No permissions, assignments or SoD rule changed.
- Current warehouse balance is read from `get_stock_balance` under its existing
  permission and scope controls, with qualified warehouse navigation. Receipt
  creation leaves balance unchanged; Post increases it by the exact source
  quantity. Balance is labelled as current ledger-derived evidence, not an
  invented transaction-specific valuation or accounting figure.
- Explicit Reverse calls the original Inventory reversal authority and requires
  the existing reversal number/reason. It retains the original posted history,
  creates the governed opposite movement and exposes reciprocal original/reversal
  links and reason/evidence. Insufficient available stock blocks reversal without
  changing history or balance. A valid reversal restores the net balance without
  automatically voiding the GRN. Procurement's existing explicit Void prerequisite
  then behaves as before; Procurement never performs the Inventory reversal.
- GRN history links its actual stock occurrence to Inventory Detail; Inventory
  Detail and its reversal link back to the exact source GRN. Source/stock status
  comes only from real records, under the existing viewing permissions.
- Procurement still owns GRN evidence; Inventory remains the stock quantity,
  posting, balance and reversal authority. Tests assert unchanged organization-
  scoped SupplierInvoice, Obligation, JournalEntry, TreasuryMovement and
  ProjectCostFact counts across GRN receipt, Inventory create/post/reverse.
  No AP, Accounting, Treasury/payment or Project Cost behavior was introduced.

Actual touch set: new Inventory `journey_forms.py`, `journey_ui.py`,
`journey_views.py`; existing named Inventory URL targets plus scoped selector
lookup; source/Create/List/Detail/Reverse and preserved other-movement templates;
one reciprocal stock link in the existing GRN history template; focused HTTP,
concurrency and Chrome tests, isolated harness/evidence and this report.
No product models, migrations, Inventory mutation services/source contract,
workflow authority, valuation policy, Procurement/PO/Award/RFQ semantics,
permissions/SoD or Product Surface changes. Prior MVP-04D code and its old context
adapter remain byte-identical; the authorized E URL targets now serve the richer
Inventory journey.

### Validation and evidence

- [Affected regression](../../../output/mvp-04e/affected-regression-attempt-1.log):
  **40/40 PASS**: 10 MVP-04E checks, all 18 MVP-04D checks and all 12 existing
  CEP-034 Inventory receipt-contract checks. Includes create/post/reverse,
  four-decimal source quantities, exact/conflicting/concurrent retries, source
  immutability and lineage, balances, reversal availability, GRN Void dependency,
  source/warehouse forgery, tenant/project/permission/CSRF isolation and financial
  boundaries. The three original Inventory affected service regressions are
  included in the existing CEP-034 suite.
- [Final focused run](../../../output/mvp-04e/focused-final.log): **10/10 PASS**
  after the browser corrections. These repeat the E checks, not ten additional
  unique scenarios. [Final isolation strengthening](../../../output/mvp-04e/isolation-final.log):
  **2/2 PASS**, one HTTP method and one Chrome method repeated after adding
  forged cross-scope retry POSTs and testing an otherwise eligible unused source.
- [Chrome run](../../../output/mvp-04e/browser-attempt-2.log): **3/3 PASS**;
  **39 distinct successful scenarios** in the
  [browser summary](../../../output/mvp-04e/browser-summary.json). Installed Google
  Chrome runs headless through the existing CDP harness at **1440 / 1024 / 390px**.
  All retained scenarios have zero horizontal overflow, zero JavaScript exceptions
  and zero HTTP 500s. No valid application-route 404; explicit ineligible-source,
  permission and scope denials are asserted. The existing favicon exclusion is
  unchanged. Screenshots, dimensions, status and console evidence are retained;
  Codex inspected desktop/mobile Create, List, Draft/Posted and reversed Detail.
- [Lint](../../../output/mvp-04e/lint.log),
  [format](../../../output/mvp-04e/format.log),
  [Django check](../../../output/mvp-04e/system-check.log),
  [seven-template/Persian check](../../../output/mvp-04e/templates-check.log),
  [whitespace](../../../output/mvp-04e/diff-check.log) and
  [migration drift](../../../output/mvp-04e/migration-drift.log): PASS.
  No migration added. Development retains only unrelated
  `payroll.0010_cep069_reviewed_statutory_context`; not applied. The isolated
  PostgreSQL validation DB has
  [447 applied migration records and zero unapplied migrations](../../../output/mvp-04e/isolated-migration-plan.log).
- [Preservation](../../../output/mvp-04e/preservation-check.json): **70 pre-existing
  source files outside declared overlap are byte-identical**, with no unexpected
  changes among 498 snapshotted files.
  [Final source hashes](../../../output/mvp-04e/final-source-manifest.json) identify
  delivered implementation and test bytes.

| Required browser behavior | Retained successful scenarios |
| --- | --- |
| Posted GRN context, eligible/general source, exact derived fields | `posted-grn-contextual-inventory-entry`, `receipt-entry-*`, `inventory-source-selection-*`, `general-eligible-grn-line-search` |
| Compatible warehouse search and incompatible/forged denial | `inventory-receipt-create-draft`, `incompatible-warehouse-denied`, `source-value-and-warehouse-forgery-denied`, `receipt-validation-retains-input` |
| Draft creation without Post, explicit Post and real balance | `inventory-draft-detail-*`, `draft-refresh-and-identical-retry`, `explicit-inventory-post`, `inventory-posted-detail-*`, `posted-source-navigation-and-warehouse-balance` |
| Equivalent/conflicting/duplicate receipt retry | `draft-refresh-and-identical-retry`, `posted-equivalent-conflicting-duplicate-retries`, `reversed-retry-retains-history-and-zero-balance` |
| Valid reversal, history, zero balance and separate GRN Void | `valid-inventory-reversal`, `inventory-reversed-history-*`, `grn-void-prerequisite-after-inventory-reversal` |
| Unauthorized/ineligible/tenant/project access | `unauthorized-inventory-entry`, `unposted-grn-line-denied`, `cross-tenant-*`, `cross-project-*` |
| List, filters/chips/sort/pagination and responsive RTL | `inventory-list-*`, `inventory-list-search-chips-sort`, `inventory-list-pagination` |
| Refresh/back/forward with no automatic mutation | `posted-grn-contextual-inventory-entry`, `draft-refresh-and-identical-retry`, `posted-source-navigation-and-warehouse-balance` |

`*` denotes required width profiles where applicable. Database assertions also
prove exact source quantity/material/unit/project and no financial side effects.
Automated screenshots do not confer Product Owner visual acceptance or Human UAT.

### Failed attempts and closeout

Initial focused validation found one actual List rendering error: a missing source
warehouse was evaluated as a fallback-filter argument for a receipt. Explicit
optional-warehouse rendering fixed it. The initial Chrome run found the general
source selector inherited automatic GET-filter navigation; the existing
`data-filter-submit="explicit"` control now preserves the deliberate Continue
step. A Chrome balance assertion also expected Persian digits although the
established number formatter returns Latin digits; the assertion was corrected
without changing formatting or balance semantics. The subsequent focused,
affected and Chrome evidence is retained with its actual outcomes; failed logs
remain failed and were not relabelled.

[Database qualification](../../../output/mvp-04e/database-qualification.json): the
E tests use a separate isolated clone of the already-qualified, fully migrated D
validation database. Existing guarded CASCADE teardown and serialized fixture
restoration are reused. All actors and work data are synthetic explicit fixtures.
No production operation or development business-data mutation occurred.

No unresolved in-scope blocker or required validation remains. Receipt entry
uses the existing complete-line quantity contract; arbitrary partial stock
acceptance, source reactivation after reversal, new warehouse policy and financial
valuation/integration were not invented. Legacy source occurrences without valid
retained contract evidence keep their existing fail-closed behavior.

Branch/worktree created: NO. Git add/commit/push/merge: NOT EXECUTED.
All work remains uncommitted on `main`; prior work is preserved.
Human Sign-off, real-user UAT, Production Certification and Production Cutover:
NOT EXECUTED. Product Owner visual acceptance: PENDING.

**STOP after MVP-04E. MVP-04F final End-to-End verification: NOT STARTED.**

```text
MVP-04E FUNCTIONAL: PASS
GRN → INVENTORY JOURNEY: PASS
SOURCE-DERIVED INVENTORY RECEIPT: PASS
INVENTORY DRAFT / POST: PASS
DUPLICATE / RETRY SAFETY: PASS
REVERSAL / HISTORY: PASS
WAREHOUSE BALANCE: PASS
TECHNICAL LEAKAGE: PASS
TENANT/PERMISSION ISOLATION: PASS
BROWSER VALIDATION: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

## MVP-04F — End-to-End Verification (2026-11-02)

### Authority, start state and final touch set

Executed only the Human-authorized MVP-04F attached request. The entry gate read
this report and found MVP-04A, the Commercial Scope producer, MVP-04B1, MVP-04B2,
MVP-04C, MVP-04D and MVP-04E successfully completed without an unresolved in-scope
blocker. The request explicitly stops continuation after F. No MVP-05 work began.

[Exact start state](../../../output/mvp-04f/start-state.json): current dirty `main`,
HEAD and cached `origin/main` both
`da88f0a23cc66696d688da7c9fba8e4152e0a87e`, cached divergence 0/0.
The pre-existing tracked/untracked A–E work was retained; no clean-tree assumption,
reset, staging, commit, push, branch or worktree creation occurred.
[Request, governance and domain-boundary hashes](../../../output/mvp-04f/authority-and-boundary-manifest.json)
identify the authority and implementation inspected. This is bounded MVP
verification, not a CEP lifecycle transition or a production authorization.

The only F product correction is read-only forward history navigation, discovered
when auditing the complete journey: approved PR → existing RFQ, finalized Award →
existing supplier PO, and PO → existing GRNs. Each uses business labels and
requires the downstream read permission and existing organization/project scope.
Existing domain services, write paths and lifecycle rules remain authoritative.

Final F touch set:

- `apps/procurement/request_ui.py`, `apps/procurement/order_ui.py`:
  permission-scoped history query context.
- `apps/procurement/templates/procurement/request_detail.html`,
  `apps/procurement/templates/procurement/rfq_buyer_workspace.html`,
  `apps/procurement/templates/procurement/order_detail.html`: the corresponding business links.
- `apps/procurement/test_mvp04f.py`, `apps/procurement/test_mvp04f_browser.py`:
  connected HTTP secondary journeys and principal installed-Chrome journey.
- This report and `output/mvp-04f/`: isolated validation harness, logs, screenshots,
  source proofs and closeout evidence.

No F model, migration, business permission, Product Surface, domain/posting policy,
financial integration or dependency change.
[Source hashes](../../../output/mvp-04f/final-source-manifest.json) cover the seven
implementation/test files. [Preservation](../../../output/mvp-04f/preservation-check.json)
qualifies the 572 pre-existing snapshotted files: before report append, 567 were
byte-identical and exactly the five declared UI overlaps changed; after append the
report is the sixth declared overlap. No unexpected changed or missing file.

### Connected canonical and secondary journeys

**Primary full PR → Inventory journey: PASS.**
The fixture starts with tenant masters, memberships, explicit role assignments,
project, material/unit, suppliers and warehouse only. It asserts no PR, RFQ,
quote revision or stock transaction exists. It does not seed upstream commercial
documents, an Award, PO, GRN or stock result.

The final Chrome run executes all business transitions through rendered forms and
contextual links: create PR and material row → submit → separate approval → create
RFQ from approved PR → select PR row → explicit Commercial Scope → select supplier
and issue → actual source-byte upload/capture → submit → corrected second quote
revision/submit → close → custody attachment → protected opening request and
independent approval → exact-revision access → admissibility preparation and
independent approval → comparison preparation/evaluator appointment/evaluation and
independent finalization → partial award preparation/independent finalization →
supplier PO/Issue → first partial GRN/Post → Inventory draft/explicit Post → later
GRN/Post → second Inventory draft/explicit Post → completed PO → explicit reversals.

The test clock satisfies existing close/opening timing rules; processing assessment
and versioned separation policies are explicit isolated test fixtures. Custody and
quote capture use actual uploaded synthetic bytes. This does not certify a real
scanner, arbitrary document rendering or deployment processing infrastructure.

| Scenario | Exact result |
| --- | --- |
| Primary partial procurement | PR 10; RFQ scope 10; award 6; unawarded 4; PO 6; posted GRNs 2 + 4; posted Inventory receipts 2 + 4; balance 0 → 2 → 6; PO completed |
| Split award | One newly created PR/RFQ, two effective supplier quotes, allocations 4 + 6, separate supplier-specific POs and independent GRNs/Inventory receipts; total balance 10; no supplier crossover |
| No Award | Complete upstream process through finalized comparison, explicit finalized No Award, retained history, no allocation/PO continuation and zero PO/GRN/stock rows |
| Reversal | Two explicit Inventory reversals, originals retained with reversal links, four stock records total, balance 6 → 0; both source GRNs remain posted |

[Canonical lineage](../../../output/mvp-04f/canonical-lineage.json),
[split lineage](../../../output/mvp-04f/split-lineage.json),
[No Award](../../../output/mvp-04f/no-award.json) and
[reversal proof](../../../output/mvp-04f/canonical-reversal.json) retain exact
source FKs and Decimal quantities. Technical identifiers in these restricted
engineering artifacts are not business-user inputs or visible UI labels.

### Source, quantities, finance and lifecycle integrity

**Source lineage and quantity conservation: PASS.** Assertions verify PR row,
RFQ row/version, effective quote revision (including corrected/superseded history),
comparison input, Award allocation, supplier-specific PO and issued version,
pinned GRN source row, stock source, material, unit, project and warehouse.
Primary conservation is `10 = 6 awarded + 4 unawarded` and
`6 ordered = 2 + 4 received = 2 + 4 stock posted`.
Split conservation is `10 = 4 + 6` independently through each supplier's order,
receipt and stock lineage. No quantity semantics were changed: PO creation consumes
whole selected approved allocations; Inventory receipt uses the existing complete
posted-GRN-line contract. The primary partial flow uses partial award and partial
GRNs, not an invented arbitrary partial-allocation PO or stock-acceptance policy.

Business-readable forward navigation is clicked in Chrome from PR through RFQ,
buyer workspace, existing PO, existing GRN and Inventory transaction. Backward
links agree with the retained source chain. Posted/completed records expose their
history and existing frozen-state behavior. Parent-only readers cannot see RFQ or
GRN history links without the corresponding downstream read permission.

**Financial boundary: PASS.** The connected tests hash both row contents and counts
before and after the journey checkpoints. Supplier Invoice, AP Obligation,
Accounting Journal Entry, Treasury Movement, Payment Request, retained payment
evidence and Project Cost Fact remain byte-equivalent at the row projection level
(tenant baseline counts zero). All retained tenant-owned tables with `payment` in
their name are included by database introspection, including legacy
`payments_payment`, `payments_paymentallocation`, `payments_paymentdocumentlink`
and Treasury payment transition/request tables. No financial fact, settlement,
recognition or posting is generated by any operational stage or reversal.
The complete hashes/checkpoints are in the canonical/split/No-Award/reversal proofs.

### Browser, technical leakage and security

[Final installed-Chrome run](../../../output/mvp-04f/browser-attempt-2.log):
**1/1 test method PASS, 425.745 seconds**, comprising
[83 distinct scenarios](../../../output/mvp-04f/browser-summary.json).
The full business journey runs at 1440. Representative PR List/Detail, RFQ
Create/Detail, Buyer Workspace, Award, PO List/Detail, GRN List/Detail and Inventory
List/Detail run at 1440, 1024 and 390. Document widths account for the browser
scrollbar. No horizontal overflow, JavaScript exception, unexpected HTTP error,
visible technical-label match or non-Persian/RTL document state was detected.
Expected repeated-transition 400s and explicit isolation 403/404s are recorded
separately; they are not valid-route failures. Favicon requests are not business
route evidence.

Screenshots are retained in [the browser evidence directory](../../../output/mvp-04f/browser/).
Visual inspection included mobile PR history, completed-PO receipt history,
buyer workspace and reversed Inventory history/balance, plus desktop Award
workspace. Contextual selectors, primary actions and retained history remain
readable; existing list/filter/menu and form-retention behavior is also exercised
by the affected A–E coverage. No broad visual redesign occurred.

Visible-content assertions cover UUIDs, hashes/fingerprints, managed retry and
idempotency keys, raw model/object labels, internal source/allocation/revision
references, backend enum values and permission/service terminology. Source values
are server-derived or managed form state; none must be manually reconstructed.

| Boundary | Executed evidence |
| --- | --- |
| Unauthorized, other tenant and wrong project | Final Chrome receipt-create 403, stock-detail cross-tenant 404 and GRN project-scope 404; affected A–E and receipt-contract tests enforce reads and direct mutations |
| Forged parent/source, supplier and project | A/B1 contextual PR/RFQ denials, B2 cross-context quote/award denial, C forged supplier/project/allocation/direct bypass and excess consumption, D source/version/context denial |
| Warehouse and source-derived stock values | E forged material/unit/quantity/value/source and incompatible warehouse denial, unposted/void source denial and scope/CSRF coverage |
| Stale and excessive quantities | Commercial Scope optimism/source drift/freeze tests, protected opening/admissibility/comparison freshness tests, Award excess/split/tie rules, PO consumption and GRN excess/version tests |
| History-link authorization | F parent-only reader test suppresses RFQ/GRN history links while authorized parent detail remains readable |
| Concurrency | Existing scoped Commercial Scope, custody, opening, admissibility, comparison/Award, GRN and Inventory receipt concurrency tests in the affected run |

**Retry / idempotency: PASS.** Final Chrome captures each actual rendered form's
managed state, submits it and replays the identical POST after success for RFQ
Issue, Award finalization, Award→PO, PO→GRN (both receipts), and GRN→Inventory draft
(both receipts). Final rows remain one RFQ version, one Award, one PO, two GRNs
and two original stock transactions. Refresh/back/forward preserve that state.
Repeating finalized Issue/GRN Post/Inventory Post is rejected by the existing
contract with 400, without duplication. A–E regression covers conflicting retries,
equivalent source retries, reversal retries and concurrent identical acceptance.
Existing deny/reuse semantics were preserved rather than changed to force success.

### Regression, failed attempts and limitations

[Affected regression](../../../output/mvp-04f/affected-regression-attempt-1.log):
**123/123 PASS, 555.113 seconds**, after the forward-link correction. Scope:
`test_mvp04f`, `test_mvp04a`, `test_mvp04b_scope`, `test_mvp04b1`,
`test_mvp04b2`, `test_mvp04c`, `test_mvp04d`, Inventory `test_mvp04e`,
`test_p5_s08_sealed_custody`, `test_p5_s09_protected_opening`,
`test_p5_s10_admissibility`, `test_p5_s11_comparison_award`, and Inventory
`test_cep034_receipt_contract`. This covers PR, RFQ and scope, quote/custody/opening,
admissibility, comparison/Award, PO, GRN, Inventory draft/Post/reversal, source and
financial boundaries, permissions/tenant/project isolation and concurrency.
The two new HTTP secondary methods, including the downstream-history denial
assertions, pass in this final run. No in-scope product failure, unrelated failure,
skip or expected failure remains in this 123-test command.
The isolated wrapper supplies explicit historical actor role assignments and the
existing guarded CASCADE/serialized fixture teardown; these are test-fixture
adaptations, not runtime authorization changes.

[Initial HTTP attempt 1](../../../output/mvp-04f/connected-http-attempt-1.log) failed
because the new harness posted to the detail URL rather than the rendered form
action. [Attempt 2](../../../output/mvp-04f/connected-http-attempt-2.log) failed on
an incorrect fixture ORM relation. Both are harness failures, retained as failed;
no Domain correction was needed. [Attempt 3](../../../output/mvp-04f/connected-http-attempt-3.log)
passed both connected HTTP scenarios (2/2, 59.316 seconds).
[Initial Chrome](../../../output/mvp-04f/browser-attempt-1.log) passed the complete
primary journey (1/1, 346.866 seconds). After the objective forward-navigation gap
was corrected, final Chrome reran the whole journey and affected tests re-exercised
the links and denial assertions. No failed command is relabelled as PASS.

The [initial closeout checker](../../../output/mvp-04f/closeout-evidence-attempt-1.log)
failed because it compared CRLF evidence bytes to the normalized LF report append.
Only the checker normalization was corrected; the
[final closeout](../../../output/mvp-04f/closeout-check.json) proves all previous
report bytes are preserved, every new report link resolves and no unexpected
file changed.

Lint, formatting, Django system check, template parse/UTF-8 and model/migration
drift checks pass; logs are retained in `output/mvp-04f/`.
[Isolated migration qualification](../../../output/mvp-04f/isolated-migration-plan.json)
shows 447 applied migration records and zero pending migrations in each of the
two separate PostgreSQL validation clones. The initial
[database qualification](../../../output/mvp-04f/database-qualification.json)
identifies the already-migrated E template. Development still has the unrelated
`payroll.0010_cep069_reviewed_statutory_context` pending; it was not applied.
No production migration, development business-data mutation or production action.

Known external supplier-portal fixture debt remains historical:
`SupplierPortalUiTests.test_external_context_is_exact_scope_and_submission_is_idempotent`
sends a fingerprint instead of the upload required by the existing capture contract.
That previously identified command is not represented as passing and was not
silently expanded into buyer/Inventory product scope. Synthetic policy, actors,
clock, source bytes and processing assessments qualify functional tests; they do
not prove real supplier participation, deployed scanning, Human UAT or statutory
or production readiness. Full-repository regression was not run.

**MVP-04 FUNCTIONAL IMPLEMENTATION COMPLETE.** No unresolved in-scope functional
blocker remains. Product Owner visual acceptance: PENDING. Human Sign-off,
real-user UAT, Production Certification and Production Cutover: NOT EXECUTED.
All work remains uncommitted on `main`; no commit or push. Stop after MVP-04F;
MVP-05 and later work: NOT STARTED.

```text
MVP-04F FUNCTIONAL: PASS
FULL PR → INVENTORY JOURNEY: PASS
SOURCE LINEAGE: PASS
QUANTITY CONSERVATION: PASS
PARTIAL / SPLIT JOURNEYS: PASS
NO-AWARD JOURNEY: PASS
INVENTORY POST / REVERSAL: PASS
FINANCIAL BOUNDARY: PASS
TECHNICAL LEAKAGE: PASS
TENANT/PERMISSION ISOLATION: PASS
RETRY / IDEMPOTENCY: PASS
RESPONSIVE BROWSER VALIDATION: PASS
MVP-04 FUNCTIONAL PACKAGE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```
