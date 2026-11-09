# Projects List and Project Detail UI/UX

Status: implementation and scoped verification COMPLETE (2026-11-04).
Work began 2026-11-03. Direct Human request and the two local PNGs authorize this
bounded presentation task. No CEP/Registry state, Product Surface authority,
production state or Git integration is changed.

## Implementation and source integrity

Projects List now has the existing shared header, real scoped status summary,
local Chart.js doughnut, accepted Contracts filter/chip/sort/pagination pattern,
and only existing Project columns. Summary counts cover every project returned
by get_organization_projects before filters/pagination. A cancelled-project card
appears when its count is nonzero; the chart legend always covers all five model
statuses. No Excel/Print controls are offered because Projects has no applicable
existing output implementation.

Project Detail uses compact identity/navigation, authorized KPI cards, existing
commercial summaries, recent source records, quick links and project information.
The existing cost projection remains authoritative. The presentation now also
requires actual recognized/reversed cost evidence, beyond currency compatibility,
so commitment-only evidence cannot fabricate a zero actual-cost KPI or bar chart.
Partial-coverage/source details stay visible. No legacy actual_budget substitution,
physical/scheduled progress percentage, budget remainder, conversion, posting,
financial recognition or JavaScript domain calculation is introduced.

Chart.js 4.6.1 and its existing MIT/provenance files are reused locally, unchanged.
Backend strings preserve Decimal precision; JavaScript draws approximate geometry
and formats exact source strings for Persian tooltips. Accessible server-rendered
values survive disabled JavaScript or a blocked chart library.

## Files changed by this task

| Files | Change |
| --- | --- |
| apps/projects/views.py | Scoped status aggregation and Projects sort options for presentation |
| apps/projects/dashboard.py | KPI presentation metadata, contract total, actual-evidence display guard |
| apps/projects/static/projects/workspace.css | Responsive Projects layouts using canonical tokens |
| apps/projects/static/projects/dashboard_charts.js | Semantic status colors, RTL Persian charts/tooltips and section-tab state |
| apps/projects/templates/projects/list.html | Real summary/chart plus shared reference-list components |
| apps/projects/templates/projects/detail.html | Compact command-center composition and permitted navigation |
| apps/projects/templates/projects/commercial_summary.html | Compact source-backed commercial summary rows |
| templates/components/dashboard_chart.html | Existing chart component gains optional ring center/side legend/icon |
| templates/components/page_header.html | Existing header supports the shared layers icon |
| templates/components/form_icon.html | Extend the existing icon catalog |
| templates/components/list_result_toolbar.html | Optional caller-owned sort choices; Contracts defaults preserved |
| apps/accounts/static/css/erp_reference_list.css | Opt-in reference-pattern selector reuse and canonical semantic tokens |
| apps/projects/test_command_center.py | Count/chart scope, soft deletion, pagination independence, empty and commitment-only cases |
| apps/projects/test_command_center_browser.py | Real Chrome cases, synthetic visual fixtures, corrected Jalali/mobile test controls |
| scripts/verification/projects_workspace_validate.py | Dedicated PostgreSQL runner, guarded seed replay, isolated browser evidence |
| docs/validation/projects-ui.md | This report |
| output/projects-ui-20261103/ | Grounding, migration-only fixture, JUnit, browser JSON and screenshots |

Unrelated initial and concurrent work, including the header/profile, global
loading, operational lists, generated Tailwind, expenses, quality and safety, is
preserved. This task changes no model, migration, domain service, workflow, permission or
tenant scope implementation. No new runtime dependency is added.

## Verification

Environment: installed headless Google Chrome, Django live server, dedicated
PostgreSQL test_bonira_projects_workspace_ready_20261103, 447 applied repository
migrations. Test fixtures are synthetic; source seed has zero users. No development
business records are created or changed. The source test DB is unchanged.

Commands:

```powershell
.venv/Scripts/python.exe scripts/verification/projects_workspace_validate.py --reuse-db -q --tb=short --junitxml=output/projects-ui-20261103/tests.xml
.venv/Scripts/python.exe scripts/verification/projects_workspace_validate.py apps/projects/test_command_center_browser.py apps/projects/test_mvp03_business_hub.py --reuse-db -q --tb=short --junitxml=output/projects-ui-20261103/browser-final.xml
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe -m ruff check apps/projects/views.py apps/projects/dashboard.py apps/projects/test_command_center.py apps/projects/test_command_center_browser.py scripts/verification/projects_workspace_validate.py
.venv/Scripts/python.exe -m ruff format --check apps/projects/views.py apps/projects/dashboard.py apps/projects/test_command_center.py apps/projects/test_command_center_browser.py scripts/verification/projects_workspace_validate.py
node --check apps/projects/static/projects/dashboard_charts.js
git diff --check
```

The full bounded run passed 24 tests plus 14 subtests; its one failed existing
browser scenario targeted the hidden desktop advanced-filter button on mobile.
It now targets the actual mobile native summary. An earlier existing test entered
Gregorian text into the Jalali widget; it now enters formatted Jalali text. No
product date parser or filter semantics were changed for those fixture fixes.
Final directed rerun covers all Projects browser cases and commercial-hub tests
after the compact-summary and mobile-budget refinements.

Final directed run: **7/7 PASS**, 6 subtests PASS. Combined latest results for
all **25 unique tests: PASS** (the prior mobile-scenario failure is superseded by
its passing rerun). The full run also passed 14 subtests; overlapping subtests
are not counted twice. Both JUnit runs remain available so history is transparent.

**33 real Chrome scenarios PASS**: 30 Projects cases and 3 Contracts regression
cases, including configured viewports 1672×941, 1440×900, 1024×900 and 390×900,
plus resize transitions. Recorded usable client widths also reflect scrollbars.
All final scenario responses were HTTP 200; zero viewport overflows and zero
external frontend requests. JS exception and page/asset failure assertions passed.
Tenant/project rejection and source-permission behavior are additionally covered
by HTTP/integration tests, including cross-tenant 403 responses.

Django check, Ruff check/format, JavaScript syntax, template compilation, Persian
UTF-8 integrity and diff whitespace checks: PASS. Chart asset SHA-256 matches its
existing provenance. Final desktop, mobile, source-cost and empty screenshots
were visually inspected; no remaining in-scope layout defect was observed.

Evidence: `output/projects-ui-20261103/validation-summary.json`, `tests.xml`,
`browser-final.xml`, and per-batch JSON under `browser/`. Final reference-sized
screenshots are `browser/ProjectWorkspaceBrowserTests/f61-owner-visual-list-1672.png`
and `f61-owner-visual-detail-1672.png`; the corresponding `*-390.png` files show
mobile. `budget-preparer-PCC-cost-evidence-desktop.png` proves the real-source bar
chart and readable source/coverage details. All use synthetic test records.

Browser assertions cover real status data and tooltips, cost evidence/coverage,
empty/filtered-empty states, absent unauthorized metrics/actions, project scope,
filter/chip removal, Jalali dates, sorting/pagination preservation, navigation,
Desktop/Mobile and resizing, JS-disabled/library-failure fallbacks, RTL and LTR
business codes, horizontal viewport overflow, JS exceptions and page/asset HTTP
failures. The driver excludes the pre-existing missing /favicon.ico from page
asset checks. Local-only network interception rejects external dependencies.

## Visual differences and limits

The references guide layout, not business data or feature availability. Visual
review is qualitative, not a pixel-difference acceptance claim. Main differences:

- Canonical BONIRA colors, fonts and the existing shell/profile are retained;
  reference portrait, role, organization name, decorative gradients and example
  figures are not copied. Legacy company-role/position absence is shown honestly.
- No Excel or Print buttons without existing real implementations. Dates stay in
  the accepted advanced filter panel; no unsupported combined time-range filter.
- Full, grouped money values and their real units are retained instead of inferring
  rounded billion-unit amounts. Mobile budget uses a full-width KPI for legibility.
- Financial bars disappear without equivalent actual evidence. Partial-coverage
  notices remain, so the financial card differs from the illustrative bar chart.
- Navigation, KPIs, summary rows and actions follow exposure and independent source
  permissions. Page height varies with actual data and available sections.
- Progress availability/source details and the existing protected archive form
  remain lower in the information section; no physical/scheduled progress metric.
- Latest items are source records ordered by creation time, not a fabricated audit
  feed. Existing producer selection remains bounded to the retained dashboard.

Known adjacent baseline issue, not changed: the shared erp_money.js globally
relabels legacy USD/EUR/GBP/AED text as Rial (enhanceLabeledMoney). Browser currency
validation here covers the configured canonical IRR surface; the server currency
mismatch guard is tested. Legacy non-IRR global presentation needs separately
bounded formatter remediation; it is not certified by this task.

Initial generic test DB migration drift and the clone-start race are documented
in output/projects-ui-20261103/GROUNDING.md; neither was a product regression.

Branch main. No branch/worktree created. No git add, commit, push, merge or other
Git-write action. Human visual acceptance/production certification is not issued.


## Concurrent edit compatibility

After the complete browser run, independent Related Documents work modified the
same Project Detail template and added its own tag/assets/navigation/panel, plus
its own gallery wording. These additions were preserved and are not attributed
to this task. The current-template smoke passed **2/2 tests**, rerunning the reference-sized desktop/mobile,
empty, library-failure/no-JS visual batch and the restricted-metrics/tenant HTTP
test. Source hashes in `output/projects-ui-20261103/validated-source-hashes.json`
record this stable combined version; hashes remained unchanged through smoke completion. Related Documents domain implementation
itself remains outside this report's acceptance scope.
