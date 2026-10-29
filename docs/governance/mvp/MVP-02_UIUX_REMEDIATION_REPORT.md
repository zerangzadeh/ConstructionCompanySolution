# MVP-02 UI/UX Remediation — 2026-10-29

**Status: READY_FOR_HUMAN_REVIEW — Development/non-production only.**

The Human Product Owner authorized UI/UX remediation in the supplied request,
following visual rejection of the functionally completed MVP-02. This report
supplements the original completion report; it does not overwrite that evidence,
change D1–D7, issue Human acceptance, or authorize a Git checkpoint.

## Repository and actual touch set

- Branch: `main`; entry/exit HEAD: `13e0b1d85f766336eca8286a904e3080b4597f9c`.
  Local `HEAD...origin/main`: `0/0`; no remote freshness beyond that reference.
- Entry tree: existing uncommitted MVP-02 source, migrations, tests and evidence,
  plus pre-existing governance/architecture changes. They are preserved in place.
- Exit tree: original changes plus bounded uncommitted UI, tests, vendor assets,
  documentation and evidence. Exact entry grounding is in
  [baseline.json](../../../output/mvp-02/uiux/baseline.json).
- Product touch set: shared field widget/helper/media, scoped choice presentation
  endpoint, Workforce/Assignment forms/views/templates/navigation labels,
  Timekeeping forms/templates and presentation-only native-list refresh guards.
  The shared table-filter serializer clears disabled cascading masters from URLs
  and ignores unnamed internal selector-search inputs.
- Supporting touch set: selector/regression tests and existing Chrome/CDP probe;
  UI guidelines, Roadmap, this report and an appended original-report note.
- Models, migration files, domain services, identity boundaries, national-ID
  behavior, permissions, authorization guards and Product Surface route semantics
  are unchanged from remediation entry. Source hashes support that boundary.
- Git writes: **NONE**. No branch/worktree/index/ref creation, commit, push,
  merge, reset, stash or other Git mutation. MVP-03: **NOT STARTED**.

## Shared correction and information architecture

The root cause was `SearchChoiceSelect` / `searchable_choices`: its shared widget
rendered a separate search input, search button, native select and technical
40-result helper. All consumers inherited that rejected interaction.

The widget now progressively enhances one native Django select through locally
pinned **Tom Select 2.6.2**, core plus `virtual_scroll`. One integrated RTL control
supports typing, keyboard selection, remote search, further result loading,
empty/loading/failure/retry states and escaped business labels. Technical result
limits and independent selector-search buttons are removed. Native values and
server-rendered validation remain authoritative; selected values outside the
initial window and existing inactive teams survive redisplay. Media loads only
on consuming forms. HTMX initialization/cleanup is idempotent.

Project → Site and Project/Site → Worker choices cascade in both the browser and
scoped form querysets; changes clear descendant values/caches. Stale or foreign
combinations fail server validation. Attendance Calendar → Shift and allocation
Project/Site → Activity choices also follow their existing relationships.
Assignment history filters and their dedicated lookup list only workers in
authorized assignment history. A history-only viewer cannot enumerate unrelated
workers through the general lookup. Assignment creation deliberately permits
authorized unassigned workers; it does
not incorrectly require an assignment before creating one. Validated Project,
Site, Daily Report and worker entry context is prefilled.

`نیروهای کار` identifies the worker master/current operational projection.
`تخصیص نیرو به پروژه و کارگاه` identifies assignment history and responsibility,
start, end and state. The assignment page no longer repeats the legacy HR tab
bar over the same destinations. Distinct Workforce/Assignment tasks remain in internal navigation; Timekeeping
retains its separate primary entry. Worker master and assignment history are separate concepts.
Existing assignment maintenance remains end/cancel; no new history-edit service
or silent finalized-history edit was introduced. `role_title` remains an existing
assignment description, not a duplicate of a selected Position master. Skills and
qualifications remain permissioned read-only facts on this surface.

The shared controls have standard field height and a single border; filters are
compact and Timekeeping entry forms use the existing desktop two-column/mobile
one-column system. No global Home or unrelated MVP-01 redesign was performed.

Without JavaScript, the simple-list link opts into the full already-authorized
native choices. A presentation-only refresh updates dependent lists without
creating a worker, assignment or time record. The ordinary server submission and
validation remain available. This fallback deliberately avoids remote search
requirements when JavaScript is unavailable.

## Reviewed surface inventory

Every page below was checked in real Chrome at desktop and mobile sizes, with
screenshots, Persian/RTL checks, overflow checks and selector contract assertions
where selectors exist:

| Surface | Coverage |
| --- | --- |
| Worker list/filter | Canonical Project/Site filters, worker projection, navigation |
| Worker create/edit/detail | Crew selector, identity fields, selected-value/error retention |
| Assignment list | Canonical worker/project/site filters, role/date/status filters, history/end action |
| Assignment create and worker-specific assignment | One selector per entity, validated initial context, Project → Site |
| Timekeeping workbench | Project/Site/Worker and date filters, source-separated histories |
| Attendance entry | Context, Worker, Calendar/Shift and dates |
| Leave/mission and overtime | Context, scoped worker, distinct requests |
| Attendance correction | Existing correction form and contextual return |
| Timesheet creation and allocation | Employee/context reuse and Project/Site/Activity choices |
| Project and Site detail | Contextual Workforce/Timekeeping entry links |
| Daily Report detail | Contextual Workforce/Timekeeping links; no inferred workforce facts |

The existing A–H browser scenarios additionally click Project → Site → Workforce
and Daily Report → Timekeeping and create independent Attendance, Timesheet and
Overtime records. The report manpower aggregate remains unchanged.

## Verification and evidence

- Functional validation: **PASS** — affected regression **192 PASS / 0 FAIL**,
  **65 subtests PASS**, five documented baseline deselections. Final follow-up
  after the history-only lookup restriction: **19 PASS / 0 FAIL**, four subtests
  PASS (selector/permission checks, Timekeeping and both browser tests).
- Browser interaction validation: **PASS — 66 scenarios** (48 remediation +
  18 retained functional/permission/context checks).
- Visual UX remediation: **READY_FOR_HUMAN_REVIEW**; no attributable regression
  remains. Desktop/mobile screenshots and both QA contact sheets were reviewed.
- Product Owner visual acceptance: **PENDING**.
- Final affected test command: [affected-test-argv.json](../../../output/mvp-02/uiux/affected-test-argv.json).
  [Final regression log](../../../output/mvp-02/uiux/final-validation.log),
  [final follow-up log](../../../output/mvp-02/uiux/final-followup.log).
  Reproducer: `python output/mvp-02/uiux/run_validation.py` (scopes synthetic
  uploads to evidence and preserves historical test-generated traces).
- Coverage retains Workforce identity, national ID and migration/concurrency,
  assignments, Timekeeping, Product Surface, tenant isolation and permissions.
  Five previously reproduced baseline failures retain their original documented
  deselections; they are not changed or represented as passing.
- Exploratory wider run: **198 PASS / 19 FAIL** before corrections. Sixteen
  failures are `PRE_EXISTING` legacy Workforce fixtures: all stop at unchanged
  management-authorization guards before changed UI code. The obsolete role-field
  fixtures do not establish current effective roles/scopes. No assertions or
  guards were weakened. The other three were an in-scope retry defect (fixed),
  a stale calendar-label expectation (updated), and a test option-count defect
  that included shell selectors (fixed). See
  [failure-attribution.json](../../../output/mvp-02/uiux/failure-attribution.json)
  and [exploratory log](../../../output/mvp-02/uiux/final-tests.log).
- Early verification also corrected a synthetic browser fixture and shared-test-DB
  overlap. Subsequent runs are serial. These are test-infrastructure findings,
  not claims of product regression or authority to repair legacy authorization.
- Browser results and screenshots: [browser evidence](../../../output/mvp-02/uiux/browser/).
  Desktop primary captures use the actual 1440×900 viewport; full-page clipping in
  Chrome shifted fixed RTL shell elements, so it is not used for final desktop
  primary images. Mobile captures are 390px wide and include full form height.
  **56 scenario screenshots**, one additional viewport capture and two contact
  sheets are retained. See [desktop contact sheet](../../../output/mvp-02/uiux/browser/QA-contact-desktop.png)
  and [mobile contact sheet](../../../output/mvp-02/uiux/browser/QA-contact-mobile.png).
- Test-generated media remains under `output/mvp-02/uiux/test-media/`. Historical
  CEP-062 traces generated by regression tests are restored byte-for-byte to their
  pre-run contents. No user documents are deleted.

Django system check, migration drift (`No changes detected`), 12 template
compilations, five static resolutions, Ruff, new-Python format checks, three
JavaScript syntax checks and `git diff --check` PASS. See
[static-checks.json](../../../output/mvp-02/uiux/static-checks.json) and
[VALIDATION.json](../../../output/mvp-02/uiux/VALIDATION.json).

## Dependency, migration and documentation boundary

No new migration or Python/runtime package installation. The two original MVP-02
migrations and their Development evidence remain intact; the known unrelated
Payroll migration is not applied by this remediation.

Tom Select is the repository's preferred advanced-select utility, with no
installed equivalent. Vendored runtime cost is **61,668 bytes raw / 20,532 bytes
gzipped** across core, virtual-scroll plugin and CSS, plus the small BONIRA adapter.
The unmodified files were verified against npm tarball integrity and recorded
SHA-256 values. Apache-2.0 license and included dependency notices are retained in
[the vendor directory](../../../apps/workforce/static/workforce/vendor/tom-select-2.6.2/).
No jQuery, SPA framework or new runtime CDN dependency is introduced.
Primary references: [official usage](https://tom-select.js.org/docs/),
[virtual scrolling](https://tom-select.js.org/plugins/virtual_scroll/),
[versioned package](https://github.com/orchidjs/tom-select/blob/v2.6.2/package.json),
[Apache license](https://github.com/orchidjs/tom-select/blob/v2.6.2/LICENSE).
RTL, keyboard choice, accessible control names/error associations, native
fallback, pagination and HTMX lifecycle are covered by the browser configuration;
this is not a claim of independent assistive-technology certification.

`docs/ui-guidelines.md` now permanently prohibits the rejected pseudo-select,
duplicate canonical name inputs, raw-ID entry and business-visible technical
result limits, and requires Human visual acceptance for UI package closure.
`ROADMAP.md` preserves the eight-package plan, records pending visual acceptance,
and retains broader Form / Master-Data Selection Delta Remediation in MVP-07 for
surfaces outside package-specific work. The original completion report receives
only an appended clarification; frozen D1–D7 and the CEP Registry are unchanged.

## Product Owner navigation/IA follow-up — 2026-10-29

**Follow-up status: READY_FOR_HUMAN_REVIEW.** The Product Owner accepted the
selector improvement as progress but required further Workforce navigation and
layout changes before Human Visual Acceptance. This remains the same MVP-02
remediation, with no new package, roadmap entry or D1–D7 change.

- Removed only the redundant assignment primary navigation entry from the
  central `NAVIGATION_GROUPS` catalogue (desktop, mobile and Home share it).
  Assignment capability routes, views and permissions remain intact. Workforce
  is highlighted as the parent on assignment/team pages through central
  `NavigationLink.active_routes`; the template adapter merely renders that state.
  Timekeeping's label is consistently `حضور و کارکرد`.
- One shared internal navigation now provides `نیروها` / `تخصیص به پروژه و کارگاه`
  / `گروه‌های کاری`, with permission/exposure checks, an active state and validated
  Project/Site context preservation. `تخصیص جدید` also carries this validated
  context into the existing assignment form; no raw URL identifiers are copied.
  It is shared by worker pages, assignment
  pages and the MVP team-list navigation. The old FULL_ERP tab set remains intact.
  Removed the extra Assignment header shortcut and the unrelated legacy HR tab
  bar from this MVP journey. Contextual create/cancel/back actions remain distinct.
- The assignment page opts into a shared header variant placing `تخصیص جدید`
  beside its title/copy on desktop and directly below on mobile, without changing
  other pages' header layout. Filters use `تاریخ شروع از` and `تاریخ شروع تا` and
  reduced padding. Workforce filters fit one desktop row; inactive assignment
  projection uses the existing neutral badge `بدون تخصیص فعال`.
- Responsibility is intentionally descriptive assignment text:
  `apps/workforce/models.py: EmployeeProjectAssignment.role_title` is an optional, blank-allowed
  `CharField(max_length=255)`, not a FK to Position,
  Profession or a governed Role. `EmployeeAssignmentForm.role_title` and
  `FieldAssignmentForm.role_title` are `CharField`s and assignment services accept
  the string. The independent `Employee.position` identity is not its source of
  truth. Retained text input; created no master data and changed no domain rule.
- The successful Tom Select adapter is unchanged. Site querysets/server checks,
  invalid-context denials and assignment candidate rules are unchanged; new
  assignments still allow authorized workers who have no existing assignment.
- Follow-up touch set and evidence are recorded under
  [navigation evidence](../../../output/mvp-02/uiux/navigation/). The entry hashes
  protect the original dirty tree, models/services/migrations and view/selector
  semantics. Existing untracked `protected_documents` directories at follow-up
  entry are preserved; no user files were moved or deleted.
- Initial focused validation: 62 PASS, one test-database deadlock caused by an
  accidentally overlapping browser run. That browser process was stopped; final
  verification is serial. Classification: `ATTRIBUTABLE` verification
  infrastructure, not product behavior; the aborted runs are not PASS evidence.
- The first serial rerun completed **63 PASS / 24 subtests PASS** and then failed
  browser fixture restoration because the reused database snapshot contained
  leftover published test workflow records. A temporary reset was insufficient
  and was removed. Browser verification rebuilds only the isolated test database
  with `--create-db`, using unchanged migrations and fully enabled guards.
- The fresh database exposed retained legacy Payments tables from their
  state-only retirement migration: Django's ordinary flush omitted those tables
  and failed on their FKs. The browser test class now uses Django's standard
  cascading flush, guarded to a `test_` database, with serialized rollback's
  existing post-migrate inhibition. No table, migration or domain guard changed.
  An intervening manual catalogue-restore attempt used the wrong database alias;
  its first statement was rejected by the content-type FK, with no successful
  restore write. That approach was discarded. Final tests use the normal runner
  setup and migration history; no Development schema/data repair was performed.
- Browser diagnostics identified a probe race between native fallback matches
  and the debounced remote popup update. The probe now waits beyond the selector's
  load throttle, checks settled results, and measures click targets after layout.
  The product selector adapter and its scoped endpoint remain byte-for-byte
  unchanged. The targeted context/create journey passes on desktop and mobile.
- Final serial verification: **64 tests PASS / 24 subtests PASS / zero failures**,
  including the browser test with **12/12 scenarios PASS** at 1440px desktop and
  390px mobile. See [final validation log](../../../output/mvp-02/uiux/navigation/final-validation.log)
  and [browser results](../../../output/mvp-02/uiux/navigation/browser/mvp02-nav-owner-results.json).
  Assertions cover primary/internal navigation, active parent, actual internal
  navigation and create clicks, validated prefilled context, unassigned candidates,
  text responsibility, Project/Site cascades, integrated widgets, RTL and no page
  horizontal overflow. Existing table overflow remains contained inside its wrapper.
- All **12 current scenario screenshots** were inspected. Primary review captures:
  [Workforce desktop](../../../output/mvp-02/uiux/navigation/browser/mvp02-nav-owner-NAV-workforce-desktop.png),
  [Assignment desktop](../../../output/mvp-02/uiux/navigation/browser/mvp02-nav-owner-NAV-assignment-desktop.png),
  [Workforce mobile](../../../output/mvp-02/uiux/navigation/browser/mvp02-nav-owner-NAV-workforce-mobile.png),
  [Assignment mobile](../../../output/mvp-02/uiux/navigation/browser/mvp02-nav-owner-NAV-assignment-mobile.png).
  Full inventory/source hashes are in [the follow-up validation manifest](../../../output/mvp-02/uiux/navigation/VALIDATION.json).
  Earlier 66-scenario evidence above belongs to the preceding selector revision.
- Ruff, format, JavaScript syntax, ten template compilations, Django system checks
  and whitespace checks PASS. All **611 protected source hashes** match entry;
  the vendor/adapter and backend remain unchanged. No product regression was
  observed in the focused checks. Earlier failed/aborted verification attempts
  remain retained and attributed; none is counted as PASS evidence.
- Product Owner visual acceptance: **PENDING**.

## Workforce breadcrumb hierarchy follow-up — 2026-10-29

- Workforce list: `خانه → عملیات پروژه و کارگاه → نیروهای کار`.
- Assignment list: `خانه → عملیات پروژه و کارگاه → نیروهای کار → تخصیص نیرو به پروژه و کارگاه`.
- The shared header renders the explicit chain; the separate Operations eyebrow
  is removed on these two pages. The final current item is always non-clickable
  and marked `aria-current="page"`. Breadcrumbs wrap on narrow screens.
- Parent labels/destinations reuse the central navigation catalogue and its
  permission-filtered groups. Operations links to the existing Home section;
  Workforce links back to its list with validated Project/Site context. A parent
  without an available destination remains text. No new route or authority.
- Existing focused tests now check breadcrumb order, parents, current item,
  absence of the detached eyebrow, context and restricted-parent behavior:
  **15 tests / 7 subtests PASS**. Browser verification: **4/4 scenarios PASS**
  (both requested pages at 1440px desktop and 390px mobile), with all four
  screenshots inspected. No page horizontal overflow, duplicate section eyebrow
  or clickable current item. Shared header fallback, system checks, template
  compilation, Ruff/format and whitespace checks PASS.
- Current source hashes, screenshots and checks are retained in
  [breadcrumb evidence](../../../output/mvp-02/uiux/breadcrumbs/VALIDATION.json).
  Prior navigation evidence remains the preceding revision; no historical
  screenshot or result is overwritten.

## Persistent Workforce tab placement follow-up — 2026-10-29

- One `_field_header.html` now composes the page header, the existing ordered
  internal navigation, then validated Project/Site context. All nine MVP page
  routes (worker list/create/detail/edit/assignment, assignment list/create,
  team list/create) use it, including the legacy Employee entry aliases.
- The row remains `نیروها` / `تخصیص به پروژه و کارگاه` / `گروه‌های کاری` directly
  below the header. Context summaries no longer intervene. Team creation now
  includes the same row; permission filtering and active destinations remain.
  Tabs stay on one row, with contained horizontal scrolling on narrow screens.
- Page-level primary actions consistently use the header action area: create
  worker, create assignment, create team, and edit worker. Removed the duplicate
  worker create/edit buttons from page content. Scoped record actions and form
  submission controls stay with their record/form. FULL_ERP team list/form
  rendering retains its prior layout and tabs.
- Initial layout assertions counted CSS class definitions as buttons; corrected
  them to parse rendered anchor elements. That failed run is retained as test
  attribution, not PASS evidence. Final focused verification: **15 tests and
  16 subtests PASS**. Browser verification: **22/22 scenarios PASS** at 1440px
  desktop and 390px mobile, covering nine page routes in both sizes plus four
  cascade journeys. All header/tab layouts were visually reviewed, including
  the new team-form navigation and contextual worker forms.
  The final combined run is **16 tests / 16 subtests PASS**, including the
  browser test, with single-row alignment assertions and zero failures.
- Review captures: [desktop header contact sheet](../../../output/mvp-02/uiux/tabs/browser/QA-tabs-desktop.png)
  and [mobile header contact sheet](../../../output/mvp-02/uiux/tabs/browser/QA-tabs-mobile.png).
  Screenshots preserve the prior revision separately. Permission filtering,
  validated context, breadcrumbs, selectors and tenant checks remain intact.
- Current source inventory, checks and screenshots are retained in
  [tab consistency evidence](../../../output/mvp-02/uiux/tabs/VALIDATION.json).
  Earlier navigation and breadcrumb results remain historical evidence.

## Work Teams hierarchy and page-filter follow-up — 2026-10-29

- Removed the legacy HR eyebrow from the MVP team list/create forms. The team
  list now uses `خانه → عملیات پروژه و کارگاه → نیروهای کار → گروه‌های کاری`.
  Create remains in the shared near-title header action area, above the common
  tab row. Domain ownership and backend business behavior are unchanged.
- Workforce and Assignment list controls now identify themselves as page filters.
  On first entry, a small view/form adapter defaults them from the middleware's
  already validated global Project/Site. Explicit GET selections override those
  defaults. An explicit clear marker keeps cleared controls empty instead of
  silently reapplying the global selection. No session or global-context writer
  changes. Existing scoped resolvers/querysets and Project/Site validation remain
  authoritative. Mutation views, services and models keep their prior contracts.
- Removed the Workforce list's duplicate context summary; its selected values
  are shown inside the labelled filter block. Detail and mutation-form journey
  context remains intact. Changing page filters changes page results only.
- The MVP team list uses one compact RTL filter block containing its existing
  team/department/lead controls, `اعمال فیلتر` and `پاک کردن`, even on empty results.
  A base-template block override suppresses automatic detached table controls
  for this page only. The explicit-submit opt-in in the shared table adapter
  prevents premature submission while typing; other pages retain their existing
  automatic behavior. FULL_ERP retains its previous team layout.
- Initial focused validation caught the base layout's auto-inserted duplicate
  controls; the scoped override resolves it. Final focused checks: **17 tests /
  26 subtests PASS**. Final combined verification: **18 tests / 26 subtests PASS**,
  including **20/20 Chrome scenarios PASS** at 1440px desktop and 390px mobile.
  Browser checks cover default initialization, per-page override/cascade and
  clear on both lists, explicit team filter submission/results/clear, hierarchy,
  header actions and team creation. Global Organization/Project/Site session
  values are asserted unchanged after all browser interactions.
- Primary visual captures: [Work Teams desktop](../../../output/mvp-02/uiux/context-filters/browser/mvp02-context-owner-TEAM-layout-desktop.png),
  [Work Teams mobile](../../../output/mvp-02/uiux/context-filters/browser/mvp02-context-owner-TEAM-layout-mobile.png),
  [global context with a different page filter](../../../output/mvp-02/uiux/context-filters/browser/mvp02-context-owner-CTX-cascade-workers-desktop.png).
  Representative default, override, clear, team filter and creation layouts were
  inspected. Existing domain/migration/security sources remain unchanged except
  the two declared list-view adapters that bind presentation filter values.
- Source inventory, session-isolation checks and desktop/mobile captures are in
  [context/filter evidence](../../../output/mvp-02/uiux/context-filters/VALIDATION.json).

No Human sign-off, production action, MVP-03 work or Git checkpoint is performed.

## Assignment create-flow follow-up (2026-10-29)

Scope: the two existing assignment creation entry points only. There is no
assignment edit route or update service in the current implementation; this
follow-up does not introduce a new permission, edit lifecycle or Master Data.

- Both entry points use the complete Home / Project & Site Operations /
  Workforce / Project-Site Assignment / New Assignment breadcrumb chain. Parent
  links retain permission/exposure checks; the final page is non-clickable.
- Assignment selectors render business names prominently and codes on a smaller
  secondary line. Native fallback labels and remote search retain names and
  codes. Other forms retain their previous label layout.
- The worker-specific form shows its fixed worker first, then Project, Site,
  responsibility, start and notes. Notes use the existing assignment notes field
  through the existing service; no new persistence mechanism is introduced.
- Responsibility remains optional assignment-specific text: the authoritative
  `EmployeeProjectAssignment.role_title` is a `CharField`, without a relationship
  to Position or any other master. A worker's Position remains a separate concept.
- Browser validation exposed stale Site context in the worker-specific form's
  remote lookup after Project changed. The shared adapter now removes a
  selector's own stale URL parameter before requesting its options. Existing
  Project → Site clearing and server tenant/scope validation remain authoritative.

**End-date decision pending:** the existing model explicitly rejects `end_date`
for `status=active`; its create service accepts no end date. The existing
`transition_project_assignment_status` service records an end date when ending
or cancelling an assignment, with its separate governed permission and audit.
The user was asked whether a creation-time end date means a planned end while
remaining active (a narrow domain-rule change), or an already-ended assignment
through the current completion lifecycle. Neither interpretation is inferred.
No optional end-date field, status-rule change or new edit lifecycle is shipped
while that required decision is pending. Empty-end active creation and later
ending retain their existing contract.

Verification: **22 tests / 28 subtests PASS**, including **14/14 real Chrome
scenarios PASS**. Four assignment scenarios cover both entry points at 1440px
and 390px; ten targeted shared-selector regression scenarios cover cascade,
validation retention, native/no-JS fallback, HTMX lifecycle, retry/error,
pagination and filters. Representative desktop/mobile captures were visually
inspected. The focused lifecycle test proves required start, active creation
with no end, notes persistence and the existing later end action. The existing
model lifecycle validation test also passes. The first UI test assertion
incorrectly included global navigation; it was corrected to inspect the page
header. The first browser attempt found the stale Site URL defect described
above; final verification passes after correction.

Captures: [desktop creation](../../../output/mvp-02/uiux/assignment-flow/browser/mvp02-assignment-owner-ASSIGN-create-desktop.png),
[mobile creation](../../../output/mvp-02/uiux/assignment-flow/browser/mvp02-assignment-owner-ASSIGN-create-mobile.png),
[mobile contextual assignment](../../../output/mvp-02/uiux/assignment-flow/browser/mvp02-assignment-owner-ASSIGN-worker-mobile.png).

Current follow-up evidence and exact verification results:
[assignment-flow validation](../../../output/mvp-02/uiux/assignment-flow/VALIDATION.json).
This follow-up remains **PARTIAL_PENDING_END_DATE_DECISION**; prior completed
follow-ups and their passing evidence retain their historical status.

## Work Team registration follow-up (2026-10-29)

- The current repository has registration/list/archive routes and no Work Team
  edit route or update service. This change corrects the existing registration
  flow; it does not introduce an edit lifecycle or permission.
- `WorkTeam` belongs to `Organization`, with optional Department and Employee
  lead relationships; it has no Project/Site fields. The form now states its
  company-level scope and shows no local Project/Site ownership controls or
  operation-context summary. Global context remains visible and unchanged.
- The breadcrumb is Home / Project & Site Operations / Workforce / Work Teams /
  Register Work Team, with permission/exposure-aware parent links and one final
  non-clickable current item. This Work Team form has no HR eyebrow in either
  MVP or FULL_ERP; other generic forms retain their prior presentation.
- Unit and Supervisor reuse the approved integrated Tom Select component and
  its native fallback, bounded initial options, full remote search and paging.
  Their empty placeholders are `انتخاب واحد سازمانی` and `انتخاب سرپرست گروه`.
  Business names are primary, with codes secondary. The read-only lookup kinds
  require the existing `work_teams.create` permission and match the form's
  existing active, unarchived, organization-owned choice querysets. They do not
  apply an unrelated Project/Site or assignment restriction to company masters.
  Server-side form/service tenant validation remains authoritative.
- Code stays required and user-managed. The model has no generation default,
  enforces organization/code uniqueness and normalizes the supplied identifier;
  the create service requires the caller to supply the code. No numbering rule,
  relationship, model, migration, service or permission catalog is changed.
- The form uses a narrower two-column desktop grid, a full-width description,
  tighter spacing and the existing bottom primary-action area for Save/Cancel.
  The native list-refresh submit is explicitly prevented from creating a record.

The first two browser attempts exposed test-driver expectations (the exact
Persian required-field message and the driver's combined fill/submit contract);
they were corrected without changing product behavior. An exploratory fully
JavaScript-disabled run exposed the shared layout's existing reliance on the
Tailwind CDN runtime: utility layout/preflight styles are absent across the
entire application, with oversized navigation and content-box form overflow.
The native catalog itself contains all scoped choices. The source is the shared
`templates/base.html` runtime dependency, not team ownership or selector scope.
This application-wide no-JS layout issue is **OUT_OF_SCOPE**, retained in
`browser-final.log`, `native-diagnostic.log` and the overflow diagnostic capture.
No global CSS/build change is absorbed into this task. Final visual browser
coverage targets the normal enhanced desktop/mobile registration flow; focused
tests separately verify complete native choices and non-mutating list refresh.

Final verification: **23 tests / 31 subtests PASS**, including **6/6 real Chrome
scenarios PASS** at 1440px desktop and 390px mobile. Both sizes cover empty
placeholders/hierarchy/scope, remote selection plus required-field errors and
selection retention, and successful registration. Saved teams retain the chosen
company-owned Unit/Supervisor, including a supervisor without Project/Site
assignment. The browser asserts that global Organization/Project/Site session
values stay unchanged. Native catalog completeness and refresh-without-creation
are separately tested. Source review aligned the new master lookup guards with
registration's required organization scope; project-only grants are rejected.
All **576 entry-protected model/service/migration/authorization sources** remain
unchanged; no unexpected prior source delta exists. This Work Team follow-up is
**READY_FOR_HUMAN_REVIEW** for its declared normal-browser scope.

Captures: [desktop form](../../../output/mvp-02/uiux/work-team-form/browser/mvp02-team-form-owner-TEAMFORM-empty-desktop.png),
[mobile form](../../../output/mvp-02/uiux/work-team-form/browser/mvp02-team-form-owner-TEAMFORM-empty-mobile.png),
[mobile validation and selected masters](../../../output/mvp-02/uiux/work-team-form/browser/mvp02-team-form-owner-TEAMFORM-validation-mobile.png).

Verification and source-boundary evidence:
[Work Team form validation](../../../output/mvp-02/uiux/work-team-form/VALIDATION.json).
The prior assignment end-date decision remains pending in its own follow-up;
this task does not reopen it. No MVP-03, Git writes or Human visual sign-off.

## Assignment planned-end clarification (2026-10-29)

The Human explicitly resolved the prior date decision: planned end is optional,
does not terminate an assignment, and is distinct from the actual end. This
bounded authorization includes the smallest additive schema change if needed.
The prior pending-decision sections remain historical and are superseded by
this clarification; no package closure or Human visual acceptance is inferred.

- Source inspection found no planned/expected assignment end field. Migration
  `0017_mvp02_assignment_planned_end` adds nullable/blank `planned_end_date` and a
  database check that it is null or no earlier than `start_date`. There is no
  default date, data inference/backfill, replacement of `end_date`, or change to
  existing uniqueness/status constraints.
- The model validates the new date; both existing create services accept it as
  an optional argument defaulting to None. Both assignment form entry points
  accept an optional Jalali date after required Start Date and before Notes,
  with a field-level error for an earlier planned date. An elapsed planned date
  still leaves the assignment active. No scheduler/background action is added.
- Actual `end_date`, status transitions, permission checks and audit action
  remain the existing End Assignment contract. Actual termination can occur on
  a different date; it does not replace the stored plan.
- Responsibility remains optional assignment-specific free text, labelled
  `مسئولیت در این پروژه/کارگاه`, with help text distinguishing it from the
  worker's canonical position/profession. No master relationship is introduced.
- There is still no assignment edit route or update service. The existing
  general and worker-specific creation forms are covered; no new edit lifecycle
  or permission is introduced by this date clarification.
- Only the new migration was applied to Development. Before/after checks prove
  all eight existing assignments retain every prior column value, with all new
  planned-end values null. No production action or backfill occurred. The
  [Development migration receipt](../../../output/mvp-02/uiux/planned-end/development-migration.json)
  records aggregate counts/hashes without exposing personnel records.

Verification: **52 affected regression tests / 36 subtests PASS**, plus the
**historical-row migration preservation test PASS** and **12/12 real Chrome
scenarios PASS** (one browser test). This is **54 distinct passing tests** in
total. The regression covers current Workforce identity, tenant/permission/site
isolation, existing actual-end lifecycle, Timekeeping projections and UI filters
alongside the new model/service/form/database date checks. Empty, equal-start,
later and invalid earlier plans are checked. Responsibility remains optional;
worker Position is untouched. The migration test proves active and completed
historical rows survive with every prior field unchanged and planned end null.

Both creation entry points were exercised at 1440px desktop and 390px mobile:
final form, earlier-plan validation with input retention, and successful save.
Saved rows remain active, with planned end stored and actual end empty, even
though the planned date is already in the past. Global Company/Project/Site
session context stays unchanged. Representative desktop/mobile form and error
captures were visually inspected. The first browser attempt used a worker in a
new-project URL context before assignment; the existing scope resolver correctly
returned 404. The fixture was corrected to use the normal worker selector (or
change Project inside the worker-specific form); no scope rule was weakened.

Django system check, migration consistency and focused Ruff checks PASS.
Of the 576 entry-protected sources, only the three explicitly authorized
assignment model/service files changed; the other **573 remain unchanged**.
The single new migration and tests are separately inventoried. No unexpected
changes to prior source evidence were found. No scheduler, new dependency,
permission, Master Data, actual-end transition change or unrelated Timekeeping
change is introduced. This clarification is **READY_FOR_HUMAN_REVIEW**.

Captures: [desktop assignment form](../../../output/mvp-02/uiux/planned-end/browser/mvp02-planned-owner-PLAN-form-create-desktop.png),
[mobile assignment form](../../../output/mvp-02/uiux/planned-end/browser/mvp02-planned-owner-PLAN-form-create-mobile.png),
[mobile planned-date validation](../../../output/mvp-02/uiux/planned-end/browser/mvp02-planned-owner-PLAN-invalid-worker-mobile.png).

Final verification and source-boundary evidence:
[planned-end validation](../../../output/mvp-02/uiux/planned-end/VALIDATION.json).

PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
