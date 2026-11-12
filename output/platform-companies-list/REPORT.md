# Platform Admin Companies List

The latest visual alignment and verification are recorded in the
[Redesign-2 follow-up report](reference-match/REPORT.md). The evidence below
records the initial redesign.

2026-11-10 · Asia/Tehran

`VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW`

`PRODUCT OWNER VISUAL ACCEPTANCE: PENDING`

## Result

The Companies List uses the approved shared page header, breadcrumbs, Filter Bar,
result summary, sortable headers, status badges, empty states and pagination.
Search, status, Search and Clear share one desktop/tablet row. Mobile uses compact
record cards with the existing management destination. Pagination appears for
multiple result pages. The reliable filtered result count supplies the summary.

Company name/code, legal-name search compatibility, membership counts, audit-based
latest activity, all four existing statuses, the default company-name ordering,
the 25-record page size and the management/Create URLs retain their meanings.
The requested read-only sorting uses name, status, member count and creation
timestamp, with UUID tie-breaking. Latest activity remains informational.
Dates use the existing Jalali formatter and Persian numeral font presentation.
Technical company identifiers use isolated LTR text and canonical digits.

The written request and current UI guidelines governed implementation. The two
attached images supplied visual direction. The existing Platform Admin shell and
navigation supply the surrounding layout.

## Changed files

| File | Change |
| --- | --- |
| [platform_company_list.html](../../apps/organizations/templates/organizations/platform_company_list.html) | Shared header, filters, result workspace, table/cards, empty states and conditional pagination |
| [erp_platform_company_list.css](../../apps/organizations/static/css/erp_platform_company_list.css) | Page-scoped column widths, responsive layout and existing-token styling |
| [platform_views.py](../../apps/organizations/platform_views.py) | Companies List presentation context and whitelisted stable sorting |
| [platform_forms.py](../../apps/organizations/platform_forms.py) | Existing Companies search widgets and placeholder |
| [table_filters.py](../../apps/accounts/templatetags/table_filters.py) | Opt-in effective sort state so the default ascending sort toggles correctly on the first click |
| [filter_bar.html](../../templates/components/filter_bar.html) | Optional submit caption, retaining the shared default |
| [list_result_toolbar.html](../../templates/components/list_result_toolbar.html) | Forward the existing optional result-page context to the shared summary |
| [test_platform_companies.py](../../apps/organizations/test_platform_companies.py) | Stable pagination/sort, unknown-sort fallback, single-page controls and empty-state regressions |

The three shared changes are opt-in or optional parameters. Existing Contracts
Filter Bar tests passed. Models, migrations, permissions and domain services have
no changes from this task.

## Evidence

| Verification | Result |
| --- | --- |
| Focused Companies, Platform Console and Contracts Filter Bar suites | 38 tests and 57 subtests passed |
| Chrome rendered before/after captures | 1440 × 900, 1024 × 768 and 390 × 844 passed |
| Company-name and code search, combined status filtering | Passed |
| Individual filter removal, Clear and browser Back | Passed |
| Default sort toggle, descending sort, mobile creation-date sort | Passed |
| More than 25 results, next/previous links and query preservation | Passed |
| Sort change resets pagination and retains filters | Passed |
| Create Company and existing management destinations | Passed |
| Filtered empty state and clearing it | Passed in Chrome |
| Empty inventory, invalid status and missing activity | Passed in focused render tests |
| GET search without JavaScript | Passed in Chrome |
| RTL, no document overflow, desktop control alignment, mobile cards | Passed |
| Platform role enforcement, unauthorized tenant users, cross-tenant activity exclusion | Passed in focused tests |
| Django system checks, template compilation, static discovery | Passed |
| Ruff check and format check on all four changed Python files | Passed |
| git diff --check | Passed |

[Focused test log](focused-tests.txt) · [Checks](checks.txt) ·
[Before measurements](browser-before.json) ·
[After measurements](browser-after.json) · [Interaction journeys](browser-journeys.json)

The three after captures were visually inspected. At 1024px the table has a
contained horizontal scroll area. At 390px all record fields and management links
fit within cards. One-page captures contain no pagination controls. Browser
results show no JavaScript exceptions or page asset errors. The existing browser
driver excludes the legacy favicon 404 from page asset error checks.

| Viewport | Before | After |
| --- | --- | --- |
| 1440px | [Before](before-1440.png) | [After](after-1440.png) |
| 1024px | [Before](before-1024.png) | [After](after-1024.png) |
| 390px | [Before](before-390.png) | [After](after-390.png) |

## Environment and execution

Entry was local `main` at `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`,
matching the local origin/main reference. The pre-existing untracked
`docs/validation/comprehensive-product/` work was preserved.
Concurrent Company Detail changes appeared later in its template/CSS and in
separate activity-search hunks of the forms, views and tests. Other concurrent
organization/workforce edits were also preserved. The focused test count includes
the concurrent Company Detail activity-search regression. Tests used the
resulting shared working tree.

Validation used a private loopback PostgreSQL 18.6 copy of a shut-down synthetic
test cluster from the same revision. Its source schema contained 457 applied
migrations and zero users/companies. The isolated migration check passed.
Synthetic actors and companies were created only in disposable test databases.
Before captures re-render the original saved list view, form and template against
the same representative synthetic company names and statuses.

The final focused command selected only:

```text
python -m pytest apps/organizations/test_platform_companies.py
  apps/organizations/test_platform_console.py apps/contracts/test_filter_bar.py
  --ds=platform_companies_validation_settings --reuse-db -v --tb=short -rA
```

The temporary settings selected a dedicated test database. The browser harness
selected only its CompaniesBrowser class and used the existing
`scripts/verification/mvp02_browser.mjs` Chrome driver. Retained browser JSON
contains compact, sanitized outcomes.

Early validation attempts were superseded. A fixture import initially collected
two unrelated browser tests and regenerated existing evidence. Those generated
files were restored through Git's working-tree filters, and their final diff is
empty. A synthetic audit timestamp update was rejected by append-only protection
and removed from the fixture. A wrapped desktop filter group was corrected and
retested. The final report counts only the successful selected runs.

## Remaining issues

The configured development database had the pre-existing pending migration
`payroll.0010_cep069_reviewed_statutory_context`. Its migration state is separate
from the fully migrated isolated validation environment.

Human visual acceptance remains pending. Changes are left uncommitted.
The private PostgreSQL instance is stopped. Final teardown left zero users and
zero companies in the dedicated validation database.
