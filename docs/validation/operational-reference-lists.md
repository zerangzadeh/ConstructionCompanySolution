# Expenses, Safety and Quality reference lists — 2026-11-03

Implemented the explicitly authorized three-page UI remediation. No commit, push,
branch creation, production action or Product Owner visual acceptance.
Branch `main`; start/end HEAD `560bc3c9f136a3b76c6816dc127a80d74bcb7a1d`.

## Changed files and shared implementation

- `templates/expenses/list.html`, `templates/safety/list.html`,
  `templates/quality/list.html`: domain-specific cells and existing permitted links.
- `templates/components/operational_list.html`: one inherited page shell for all
  three, using the current Contracts reference CSS and existing shared components.
- `templates/components/list_detail_action.html`: shared vertical disclosure with
  the existing detail URL opened in a new tab; no fabricated mutations.
- `apps/accounts/static/css/erp_operational_lists.css`: locally scoped column,
  filter and output-action adaptations. No build or dependency addition.
- `apps/accounts/templatetags/reference_lists.py`: extends the existing
  presentation-only adapter with three profiles and date ranges. Existing
  estimate/site profiles retain their prior quick-filter behavior.
- `apps/{expenses,safety,quality}/views.py`: three added context lines per view:
  scoped existence check, its result, and profile name. Scoped services, filters,
  sorting, pagination, export/print datasets and permission definitions unchanged.
- `tests/test_operational_list_adapter.py` and
  `tests/test_operational_reference_lists.py`: adapter and actual Chrome coverage.

Reused `page_header`, breadcrumbs, `list_working_context`, `filter_bar`,
`filter_bar_field`, `list_active_filters`, `reference_list_toolbar`,
`list_result_summary`, `list_pagination`, `status_badge`, `filtered_empty_state`,
`empty_state`, `output_action`, `print_action`, shared GET query helpers,
`erp_filter_bar.js` and `JalaliDateInput`.

The actual stylesheet is `apps/accounts/static/css/erp_reference_list.css`, served
at `/static/css/erp_reference_list.css`. This task did not edit that stylesheet or
the Contracts template. Concurrent work generalized reference selectors and
changed shared headers/toolbars and Projects pages during verification; those
changes were inspected and preserved. This task never edited Projects List,
Projects detail/dashboard, the shared base, Tailwind output or header identity.
The final working tree contains those separate concurrent changes.

## Result per page

All three use the compact reference header, breadcrumbs, permitted CTA, unified
GET search/quick filters, initially collapsed advanced filters, removable chips,
clear-all, authorized result count, existing sort options, dense RTL table,
detail links, real status badges, shared row menu, and query-preserving pagination.
Filtered-empty is determined against the authorized unfiltered queryset, never a
global existence check. Genuine-empty creation links remain permission-aware.

Expenses keeps description/vendor, project/phase, expense group, date and amount.
Status has its own column; Operations now contains the detail disclosure.
Amounts use LTR `bdi`, numeric alignment and organization currency; dates use the
shared Jalali formatter. Filtered XLSX/Print and recurrence navigation remain.

Safety keeps number, project/site, type, severity, status and occurrence datetime.
Quality keeps number, project/site, type, severity, status and identification
datetime. Both retain permission-aware sibling-module and Compliance links.
Global Project/Site Working Context stays in the shared header, distinct from
page-level text filters. Product Surface and F1–F4 foundations are retained.

## Browser and visual evidence

Installed Google Chrome through the existing Chrome/CDP driver against a Django
live server and synthetic records in the configured PostgreSQL **test** database.
`FULL_ERP` is an explicit test-only override for Safety/Quality; runtime Product
Surface configuration is unchanged. No development business records were seeded.

Before: 12 captures (three target pages plus Contracts, each at 1440/1024/390).
After: **33 scenarios PASS**, covering those 12 views, nine interaction journeys,
three filtered-empty views, three detail/back journeys, three view-only mobile
views and three genuine-empty views with an explicit empty project scope.
Every scenario has no page-level horizontal overflow. Tablet tables retain a
local horizontal scroll area, as in Contracts; mobile rows use reference cards.
Screenshots at all requested widths were visually inspected against the current
Contracts captures. This is engineering verification, not Human visual acceptance.

Search and quick-filter URL state, advanced disclosure, Jalali date submission,
individual chip removal, clear-all, sort toggling, 25+3 pagination, row menu and
detail/back state were verified. View-only membership requires explicit project
scope, hides create/recurrence controls and retains permitted reads. Empty scope
cannot disclose records or even their existence in another scope.

Artifacts under `output/operational-reference-lists/`:

- `before/`, `after/`: current screenshots and browser batch JSON.
- `after-tests.txt`: successful final Chrome test run.
- `browser-summary.json`: 33 scenarios, status and overflow geometry.
- `contracts-image-comparison.json`: **byte-identical Contracts PNGs** at all
  three widths, with before/after SHA-256 values.
- `contracts-regression/`: existing Contracts Chrome regression evidence.
- `baseline/templates/`: preserved original target templates.

## Tests and attribution

- Focused adapter/query checks, including legacy profile preservation: PASS
  (also included in the affected regression run).
- Focused Ruff lint and formatting: PASS. `manage.py check`: PASS.
  Scoped `git diff --check`: PASS. No models/migrations changed.
- Affected regression: **68 run, 43 PASS, 25 errors**. Command and complete
  tracebacks: `regression.py`, `regression-tests.txt` in the evidence directory.
- Ten Safety/Quality errors were missing compatibility WorkflowTemplate seeds
  after the existing live-server teardown flush. Restored the canonical seed
  functions only in the test database. Follow-up Safety/Quality tests plus the
  existing Contracts browser regression: **18/18 PASS**, recorded in
  `domain-and-contracts-tests.txt`.
- All selected operational XLSX/Print tests and Contracts filtering tests passed
  in the broader run. Expenses coverage includes authorized filtered datasets,
  full-list output independent of page, date/text/project filtering, empty output,
  foreign tenant/project scope, missing permission, cancellation and no-write
  print assertions. Export and printing implementation was not modified.
- **Remaining unrelated fixture debt:** 15 `apps.expenses.tests.ExpenseServiceTests`
  errors occur in `setUp -> create_project -> PermissionDenied`: legacy owner
  membership lacks the explicit role/scope fixtures used by current tests. None
  reaches the changed list adapter/view/template. Production authorization was
  not weakened to accommodate the fixtures.
- **Remaining baseline assertion debt:**
  `tests.test_filter_bar.FilterBarTests.test_rendered_chips_escape_search_and_expose_business_choice_labels`
  expects `data-filter-result-count` inside `filter_bar.html`. The current
  reference renders this via the separate result toolbar; neither the failing
  test nor `filter_bar.html` nor `core/list_filters.py` was changed here.
  Reproduction is in `filter-bar-baseline-test.txt`.

Initial attempts also exposed stale test database rows, a browser-driver misuse
of navigation clicks for disclosure-only interactions, an overbroad empty-state
text assertion matching export help, a missing explicit reader scope grant, and
an accidentally overlapping regression process. These test setup/driver issues
were corrected; suites then ran serially. No product authorization workaround.
Full repository regression and Human UAT are not claimed.

Stop boundary: these three pages only; all changes left uncommitted.
