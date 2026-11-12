# Companies List reference alignment

2026-11-10 · Asia/Tehran

`VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW`

`PRODUCT OWNER VISUAL ACCEPTANCE: PENDING`

The user selected the attached Redesign-2 image as the primary visual reference.
This follow-up adds compact summary cards, circular metric icons, pill-shaped
status badges, clearer Search/Clear actions and blue management links. Table
column proportions and filter widths were refined for the reference layout.
The shared page header, shell and navigation retain their existing components.

The three cards show registered, active and suspended company counts from the
authorized Companies read queryset. Their lifecycle conditions match the existing
Platform Dashboard, excluding deleted companies. They show the overall company
summary before search, while the table toolbar shows the filtered result count.
The table continues to show membership counts and audit-based latest activity.
Summary values come from stored records.

## Files changed in this follow-up

| File | Change |
| --- | --- |
| [platform_company_list.html](../../../apps/organizations/templates/organizations/platform_company_list.html) | Shared metric cards, filter action options and active-status icon |
| [erp_platform_company_list.css](../../../apps/organizations/static/css/erp_platform_company_list.css) | Page-scoped reference styling and responsive widths |
| [platform_views.py](../../../apps/organizations/platform_views.py) | Read-only lifecycle summary using existing records |
| [filter_bar.html](../../../templates/components/filter_bar.html) | Optional icons and Clear caption, with existing defaults retained |
| [test_platform_companies.py](../../../apps/organizations/test_platform_companies.py) | Summary regression covering filtered, invalid and deleted-record cases |

Existing uncommitted work, including concurrent edits to other Platform Admin
pages, was preserved. This follow-up adds no models, migrations, permissions,
company statuses or management destinations.

## Verification

- Final focused Companies and shared Contracts Filter Bar suites passed with
  **25 tests and 44 subtests**. The summary test checks lifecycle counts across
  unfiltered search, company search, invalid filters and a deleted company.
- Real Chrome passed three viewport scenarios and seven interaction journeys.
  Coverage includes company-name/code search, status, individual chip removal,
  Clear, empty results, sort toggling, browser Back, mobile sorting, Create,
  management links, multi-page state retention, search without JavaScript and
  keyboard traversal through Search, Status, Search action and Clear.
- Rendered captures were visually inspected at **1440 × 900**, **1024 × 768**
  and **390 × 844**. Desktop/tablet filters occupy one row. The representative
  table fits at both desktop widths. Mobile records use compact cards.
- Django checks, template compilation, Ruff check, Ruff format check,
  isolated database migration check and whitespace checks passed.
- Existing tenant/platform denials and tenant-specific activity isolation passed
  in the focused suite.

[Final focused log](focused-tests.txt) · [Combined browser/test run](verification.txt) ·
[Checks](checks.txt) · [Viewport measurements](browser-after.json) ·
[Interaction outcomes](browser-journeys.json)

| Width | Previous version | Reference alignment |
| --- | --- | --- |
| 1440px | [Before](before-1440.png) | [After](after-1440.png) |
| 1024px | [Before](before-1024.png) | [After](after-1024.png) |
| 390px | [Before](before-390.png) | [After](after-390.png) |

Before captures are retained from the preceding verified iteration. After
captures use synthetic records in the dedicated PostgreSQL test environment.
The final focused rerun adds deleted-record coverage after the combined run.
An initial tablet filter wrap was fixed and the browser scenarios rerun.
The existing browser driver excludes the legacy favicon 404 from page asset
error assertions.

The configured development database's previously recorded pending
`payroll.0010_cep069_reviewed_statutory_context` remains an environment finding.
The isolated test database has all 457 migrations. Changes are uncommitted.
Product Owner visual acceptance remains pending.
