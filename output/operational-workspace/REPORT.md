# BONIRA Operational Workspace standardization

Latest Inbox appearance and verification: [visual reference alignment, 2026-11-06](reference-alignment/REPORT.md). This follow-up supersedes the earlier Inbox screenshots and adds the compact 21-record reference verification.

Date: 2026-11-05 (Asia/Tehran). Technical implementation complete; Product Owner acceptance is pending. Changes remain uncommitted on local `main`; no commit or push was performed.

## Coverage

| Surface | Outcome |
| --- | --- |
| Central Workflow Inbox | Pilot: compact routing-count navigation, shared Filter Bar and active chips, result count, pagination, semantic states, Jalali deadlines, responsive records and existing actions/history. |
| Inventory custody | Compact existing reconciliation summary with explicit company-wide scope; bounded reservation/count/transfer histories, badges, quantities and expiry dates; labeled cards at tablet/mobile widths. |
| Equipment operations | Existing daily/maintenance/planning groups and bounded summary retained; opt-in workspace composition and labeled work-order cards at tablet/mobile widths keep all permitted actions visible. |
| Timekeeping | Source-separated attendance, corrections, leave/mission, overtime and timesheets retained with existing filters and independent pagination; calendar/shift setup follows operational records. |
| Safety and Quality | Existing accepted List Pages verified at all three widths; no replacement dashboard, KPI layer or template mutation. |

Excluded from redesign: accepted shell, List Pages, Compact/Sectioned Forms and Detail Pages; manager/My Requests workspaces; specialized inventory valuation and equipment costing; other hidden/FULL_ERP capabilities. No Product Surface expansion or generic cross-domain queue was introduced.

## Reuse and files changed

Reused Page Header, Filter Bar/build_filter_bar, active-filter chips, result summary, pagination, Status Badge, empty state, record-detail links, working context, native workforce selectors and existing Equipment operation partials. No new framework or dependency, migration, model, service, permission or workflow changes.

Changed existing files:

- `templates/workflows/workbench.html`
- `templates/workflows/_work_item_table.html`
- `templates/workflows/_work_item_row.html`
- `templates/inventory/custody_workbench.html`
- `templates/equipment/operations_workbench.html`
- `templates/timekeeping/workbench.html`
- `docs/ui-guidelines.md` — appended section 52, Operational Workspace Pattern.

Added:

- `templates/components/operational_workspace.html`
- `templates/components/workspace_summary_item.html`
- `apps/accounts/static/css/erp_operational_workspace.css` — opt-in composition only.
- `apps/accounts/templatetags/operational_workspaces.py` — adapts existing scoped filter choices without database queries or queue filtering.
- `tests/test_operational_workspace.py`
- `tests/test_operational_workspace_domains.py`
- `scripts/verification/operational_workspace_validate.py`

Evidence is under `output/operational-workspace/`. Pre-existing Equipment and guideline edits were retained; starting copies are under `baseline/`. Protected shell/component/List hashes are in `protected-files.json`. Existing action URL tags and permission condition sets match the starting Inventory/Equipment/Timekeeping templates. The earlier guideline content is retained verbatim.

## Validation

- [Focused suite](final-tests.txt): **24 passed, 2 pre-existing failures** across 26 tests. Covers workflow tenant isolation, permission-scoped actions, CSRF, claim/release/approval, multi-position filtering, bounded queues, Equipment actions/limits, Timekeeping scope/filter/pagination and Inventory custody.
- [Original-template comparison](query-baseline.txt): both query-budget failures reproduce with the original HEAD Inbox templates and the current working-tree backend: **86 queries versus a 45-query ceiling**, identical to the new Inbox. No limit was weakened and no unrelated backend refactor was made.
- [Browser evidence](screenshots.md): **56 scenarios passed** using actual Chrome and a dedicated disposable PostgreSQL test database. Requested viewport widths: **1440, 1024 and 390px**. Includes populated and empty states, filtering/clear/Back/reload, source navigation, claim/release/approval, no-JavaScript GET filtering, read-only membership and 403 denials. Successful pages reported no JavaScript/HTTP errors, no document-wide horizontal overflow and no external frontend requests. Browser results: [JSON](browser-scenarios.json).
- Tablet visual review found Equipment actions requiring local horizontal scrolling. Mixed-record tables now become labeled cards below 1200px; updated screenshots show every action directly. Follow-up: **13/13 passed** ([tablet-recheck.txt](tablet-recheck.txt)).
- `manage.py check`: PASS. Eight new/changed templates compile. New CSS is discovered by staticfiles. Scoped Ruff checks and whitespace checks: PASS. Protected accepted shell/components/List templates match starting hashes. No corrupted Persian literals found in changed/new UI sources.
- Existing migrations were applied only to the isolated test database to establish fixtures; no migration files were created or changed by this work and no production action was taken.

## Remaining findings and acceptance

Two existing Inbox query-budget checks remain failing, with identical original-template evidence above. This is the remaining test-suite limitation; the scoped UI behavior and browser scenarios passed. Safety/Quality preserve their accepted tablet local-scroll List behavior. No in-scope implementation blocker remains. Product Owner acceptance, Human sign-off and production certification were not issued or inferred.
