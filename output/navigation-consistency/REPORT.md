# BONIRA navigation consistency audit

Recorded 2026-11-06 on local main at 59f2fde6, aligned with origin/main. The working tree already contained extensive changes and continued receiving unrelated edits during validation. This report covers the navigation changes and the recorded source snapshot.

## Coverage and counts

| Measure | Verified result |
| --- | --- |
| Application and project HTML sources inspected and compiled | 439 templates, including shared partials and legacy templates |
| Configured URL patterns inventoried | 1,271, including Admin and non-page endpoints |
| Application namespaces | 32 application namespaces, plus Django Admin |
| Representative rendered entrypoints | 33, covering all application namespaces and Home |
| Redundant return controls removed | 15, including one conditional removal on Contract Detail |
| Return and cancellation declarations retained | 83 |
| Retained return declarations | 38 |
| Retained inline cancellation declarations | 22 |
| Retained shared form-footer invocations | 23 |
| Desktop/mobile screenshot evidence | 31 captures |
| Chrome navigation scenarios | 122, comprising 121 expected 200 responses and one expected 403 |
| Module Home/Back/Forward round trips | 32, all application namespaces |
| Focused navigation tests | 29 passed and 16 subtests passed |

Counts describe source declarations. Shared includes can render on multiple routes. The Contract Detail declaration is removed in the ordinary collection-parent branch and retained in the estimate-origin branch. Template counts include partials and do not mean 439 independent browser pages. The URL inventory includes POST actions, feeds, downloads and parameterized patterns.

[Control decisions](control_decisions.csv) records every classified return/cancellation declaration and every removal with a reason. [Template inventory](template_inventory.json) records source hashes, inheritance and includes. [Route inventory](route_inventory.json) records configured names, patterns, callbacks and source files.

## Remediation

The 15 removals cover Expense Detail, Progress Detail, Baseline List, Baseline Detail, Claim List, Workforce Field Detail, Timekeeping Record Detail, Timesheet Detail, Evidence Detail, Equipment Operations, Project Detail, Project Control Comparison, Project Control Exceptions, RFQ Buyer Workspace and ordinary Contract Detail.

Claim List now renders its full existing authorized project/contract hierarchy through the shared breadcrumb. RFQ workspace, action and scope pages reuse the shared breadcrumb/header rather than rendering two independent trails. Project control pages distinguish the project from its controls page and check the existing object permission before linking the controls parent.

The measurement header's obsolete action column was removed. Empty record action groups collapse through the existing empty-state CSS, with the shared record layout trimming template whitespace. Contract actions collapse when empty. Existing primary actions remain present.

## Shared components

- templates/components/breadcrumbs.html wraps long labels in narrow RTL layouts.
- templates/components/record_detail_page.html removes whitespace inside empty action groups so the existing CSS can collapse them.
- templates/components/form_footer.html renders cancellation only when a destination exists.

Page consolidation reuses the existing page_header.html and breadcrumb_trail tag. The narrow presentation additions in Project and Contract views use existing permissions and already-validated context.

## Preserved exceptions

- Project commercial-summary anchors and contract quantity-section queries carry destinations absent from ordinary breadcrumbs.
- Progress Detail retains its contract and line_key context in the breadcrumb. Baseline Detail retains contract and versions=1.
- Document Detail retains its originating record's related-document section. Evidence Detail uses the exact authorized source URL in its breadcrumb.
- Contract Detail keeps the contracts collection link when the breadcrumb instead describes an originating estimate.
- Form cancellation remains available independently of breadcrumbs. RFQ action/scope exits are labeled انصراف. Project photo cancellation was moved into the form and respects the existing gallery permission.
- Print pages, password-reset pages, error states and legacy operational pages retain return controls where they have no equivalent breadcrumb.
- Admin-to-ERP navigation crosses a context boundary not represented by Admin's internal breadcrumb.
- Pagination, workflow decisions, financial reversal actions, section tabs, modal/drawer closing and wizard controls retain their existing purposes.

## Validation evidence

Chrome/CDP checks ran through the repository's existing local-only browser driver against dedicated disposable PostgreSQL databases. Synthetic actors included Tenant Owner, a project-scoped reader, explicit Platform Admin and Django superuser. FULL_ERP was applied only in test settings to inspect hidden capabilities.

Recorded scenarios cover the 15 affected route/template families, expense list/detail Back and Forward, exact contract/line/version return queries, workforce project/site context, attendance and timesheets, project controls, photo cancellation, expense creation cancellation, RFQ workspace/scope/action cancellation and retained section links, document evidence source return, workflow workbench, Platform Admin expense groups and role catalog, Admin home and group list, and expected denial of tenant-model Admin access.

Screenshots at 1440 and 320 px cover changed page families. Additional journey checks use 390 px. No recorded scenario has horizontal document overflow. Screenshots for claims, progress, contracts, expenses, project controls and baseline lists were visually inspected.

The final focused run in verification/bonira-navigation-regression.log passed 29 tests and 16 subtests. All 439 templates compiled. Django system checks, Ruff checks on changed Python files and git diff whitespace checks passed. Shared footer rendering was also checked with an absent destination and a destination containing preserved query state.

The final module journey run passed Home, Back and Forward round trips in all 32 application namespaces. These exercise the existing shared Home link, including on legacy pages without breadcrumbs.

The final Chrome scenario counts are in [browser_summary.json](browser_summary.json). Browser batch results and screenshots are under browser/. Reproduction helpers and test logs are under verification/.

## Regression attribution and limits

A broader run recorded 42 passing tests and nine failures before the final focused correction.

- Six ProjectControlPresentationTests fail while constructing BudgetPreparationTests fixtures at create_project. Those fixtures create legacy owner memberships without current role assignments. The failure precedes page rendering and the changed navigation code. This is baseline test debt for this task.
- Two related-document subtests expect data-related-documents-nav on Expense Detail and Daily Report Detail. The overlapping templates use manually rendered section links without that marker. The navigation task only removed the separate expense return link and made no Daily Report Detail edit. These remain unrelated overlapping-work failures.
- One old forged-contract breadcrumb expectation assumed a 200 response from Baseline List. Its existing fail-closed implementation returns 404. The assertion now matches that behavior and passes in the final focused run.

An earlier browser harness expected a superuser to browse tenant Organization Admin records. The existing Admin boundary returned 403. The corrected Platform Admin checks explicitly verify that denial and test permitted Admin navigation separately. No product permission was changed to satisfy the harness.

The audit inventories all current template sources and configured patterns and validates representative module journeys plus affected navigation. Every lifecycle state, permission combination, historical record shape and parameterized URL instance has not been browser-tested. Exhaustive runtime coverage and full-suite regression PASS are not claimed.

Three Platform Admin company templates arrived during the audit. Their two Back links and one cancellation link have no equivalent breadcrumb and are retained in the final source inventory. Their new route patterns are inventoried and their templates compile. Their runtime implementation belongs to concurrent work and was not included in the already-recorded Chrome matrix.

## Working-tree handoff

Changes remain uncommitted on main. No commit or push was performed. Existing and concurrent unrelated changes remain in the working tree. Model, migration, financial, workflow, URL-contract and product-surface files changed by other work are outside this navigation task's change set.

The browser databases are disposable test copies with complete migration histories. Development and production records were not seeded for this audit.
