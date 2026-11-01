# Contracts List — visual conformance review

Date: 2026-11-01, Asia/Tehran. Bounded Product Owner UI request, not a CEP lifecycle update.

```text
FUNCTIONAL VALIDATION: PASS
BROWSER VALIDATION: PASS
REFERENCE VISUAL CONFORMANCE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

Visual conformance means practical alignment of the Contracts List with the supplied
reference while retaining actual BONIRA fields, supported interactions and canonical
design tokens. It does not mean pixel identity or Product Owner sign-off.

## Direct comparison

- Approved source: [approved-reference.png](approved-reference.png).
- Supplied previous page: [provided-before.png](provided-before.png).
- Final real Chrome desktop: [after-desktop-final.jpg](after-desktop-final.jpg).
- Final real Chrome mobile: [after-mobile-final.jpg](after-mobile-final.jpg).
- Mobile context form: [mobile-context-final.jpg](mobile-context-final.jpg).

The desktop comparison uses the five existing contracts for the existing Baghe Stan
project, ordered by contract number. This produces comparable five-row content without
adding or changing records. The default list still has its original filtering, ordering
and page-size behavior. Desktop screenshots were reviewed directly against the supplied
reference; mobile was reviewed for adaptation of the same hierarchy and real content.

| Area | Final comparison |
| --- | --- |
| Composition and header | Separate header, filter bar, chips, advanced panel, result toolbar, table and pagination. Document icon beside the title; primary CTA opposite the title. Working context occupies the top header on Contracts only. |
| Search and quick filters | Wide search, status, contract side, searchable project, More and explicit Apply. Existing GET submission and accessible labels retained. Controls wrap at narrower desktop sizes. |
| Active chips | Independent band above advanced filters, removable chips and clear-all opposite the chips. Existing URLs preserve the remaining filters and parent context. |
| Advanced panel | Bordered panel, distinct heading and left-aligned Apply/Clear actions. Only the three supported secondary text filters appear. |
| Result toolbar | Actual filtered count on the left; compact sorting menu on the right using the existing five allowlisted sort destinations. |
| Table | Actual eight columns retained. Strong title/project hierarchy, location icon, isolated LTR contract numbers, numeric alignment, currency in the header, compact badges, restrained alternating rows, and the existing detail action. |
| Density | Final measured title top 117.5px, search top 192px, table top 558.1px and row height 50.3px. Approximate reference landmarks are 120px, 186px, 550px and 47px. The main vertical composition differences have been reduced to small spacing/density differences. |
| Pagination | Real current/adjacent/first/last page destinations; disabled edges for a single actual page. Existing filter/sort/context parameters retained. |
| Responsive and direction | Mobile retains compact record cards and collapsible filters. Tablet/narrow desktop retains a semantic table with scrolling inside its container. No page overflow at the inspected sizes; contract identifiers remain LTR. |

Intentional differences required by the request: no invented export, bulk actions,
selection model, column-visibility control, amount aggregate, date/amount/type filter,
page-size selector or unsupported sort. The real counterparty-side labels, signing
dates, values, currencies and statuses remain authoritative. Completed remains a
positive semantic status. Canonical BONIRA blue/neutral colors and Vazirmatn are reused.
The real shell navigation and available domains remain intact. These are bounded
capability/data/design-system differences, not remaining unimplemented list styling.

## Validation

Final combined command:

```text
.venv/Scripts/python.exe scripts/verification/mvp03_validate.py apps/contracts/test_filter_bar.py apps/contracts/test_filter_bar_browser.py apps/contracts/test_reference_list_browser.py --reuse-db -q
10 passed, 8 subtests passed in 242.67s
```

[Full result](test-results.txt), [filter regression](filter-regression/),
[pagination/navigation browser evidence](reference-browser/).
The two browser tests cover 20 Chrome scenarios, including combined filters, chip
removal, Back/Forward/refresh, clear-all, receivable/payable labels, inherited project
context, mobile apply, advanced filters, empty results, no JavaScript, remote project
lookup beyond the initial window, denied permission, pagination and detail navigation.
Tests use the isolated PostgreSQL database `test_bonira_mvp03_20261029`.

Manual connected-Chrome checks additionally covered 320, 390, 768, 1280 and 1672px,
the new result-toolbar sorting menu retaining the selected project, and the unchanged
POST/CSRF working-context form with readable full-width mobile controls.
See [responsive-checks.json](responsive-checks.json),
[desktop-metrics.json](desktop-metrics.json) and
[toolbar-sort-check.json](toolbar-sort-check.json).

`manage.py check`: no issues. Seven affected templates compiled. `node --check`
passed for the changed JavaScript. `git diff --check` passed. Two early browser runs
found quick-filter horizontal overflow; wrapping was corrected and the final combined
suite passed. Browser tooling also produced transient screenshot/interaction timeouts;
final screenshots were captured successfully and visually inspected.

## Scope and repository preservation

Branch `main`; HEAD and grounded `origin/main`:
`5b760e853b329e2b03415da7b046641359db6a62`. The working tree was already dirty.
Existing Contracts list work and unrelated Projects work were preserved.

This request changed `templates/contracts/list.html`, opt-in presentation branches in
the shared page-header/filter/chips/toolbar/pagination/context components, one empty
header extension block in `templates/base.html`, the existing filter-bar JavaScript,
and Contracts-scoped rules in `apps/accounts/static/css/erp_reference_list.css`.
Other pages do not opt into the new layout. Existing tests were reused.

No backend Python, services, query/permission/tenant/project scope, workflow, model,
migration, financial rule, dependency or production setting was changed by this request.
No application data was changed in the live development database. Only read/filter/
navigation actions were exercised there. Regenerated tracked historical browser files
were copied into this review and restored to their clean entry content.

Reference SHA-256:
`28e4bcb90f7c76bde8b28e51c4f24f85065591badef8ee0d1a745e76be1a0c8d`.

No branch/worktree creation, staging, commit, push, merge, production action or Human
sign-off. Changes remain uncommitted. Product Owner visual acceptance remains pending.
