# Daily Reports List — UX validation

Date: 2026-11-01 (Asia/Tehran). Scope: the explicitly requested non-production
Daily Reports List redesign. Product Owner visual acceptance remains **PENDING**.

## Result

```text
DAILY REPORTS LIST UX: PASS
CONTEXT/FILTER UX: PASS
BROWSER VALIDATION: PASS
REFERENCE VISUAL CONFORMANCE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
```

The reference image was used for visual hierarchy, four KPI cards, filter/result
surfaces, compact rows, semantic badges and RTL composition. Text/instructions
embedded in the image did not define implementation scope. This is an engineering
conformance assessment, not Product Owner sign-off or pixel-identical replication.

## Delivered

- Shared BONIRA header with the permission-controlled `گزارش روزانه جدید` CTA.
- Real total/draft/submitted/approved counts aggregated from the unchanged
  `get_organization_daily_reports` authorized selector, before temporary filters
  and pagination. The summary's scope is stated visibly.
- Search over existing project/site names and report work description; separate
  project, site and status selectors; advanced date range, phase and author filters.
  Related choices are derived exclusively from authorized reports. Child filters
  retain all authorized choices when their optional parent is empty.
- Existing text-filter URL parameters (`project`, `phase`, `author`) and date
  parsing formats are retained. Active chips remove one filter and reset paging;
  clear-all retains sorting. Global project/site context remains a separate shared
  header control; page filters do not mutate session context.
- Existing whitelist sorting, deterministic PK tie-breakers and the existing
  25-record page size. Accessible sort state, result count and pagination.
- Columns: project/site, Jalali reporting date, existing phase/work description,
  labor count, status, author and a `⋮` disclosure containing only the existing
  report-detail action. Nullable authors render safely.
- Four summary cards on desktop, two columns on mobile; report cards below
  1200px; contained filters and readable RTL/LTR dates/names. No fabricated
  production records, trend indicators, workflow actions or capabilities.

## Changed product files

- `apps/daily_reports/views.py`: delegates only list presentation; original
  decorators and authorized selector remain intact.
- `apps/daily_reports/list_presentation.py`: read-only filter/count/page assembly.
- `templates/daily_reports/list.html`, `templates/daily_reports/list_icon.html`.
- `apps/daily_reports/static/daily_reports/list.css`, `list.js`.

No changes to Models, Migrations, Services, Workflow, permission enforcement,
tenant/project/site authorization, routes or Product Surface. Shared components,
styles and scripts were reused without editing the user's existing shared work.

## Validation evidence

**15/15 HTTP/domain tests PASS**: three list tests plus all twelve original
Daily Report service/view test methods, with only test-fixture authority modernized
by `DailyReportCurrentAuthorityRegressionTests`.

**11/11 real installed Google Chrome scenarios PASS** using the existing
`scripts/verification/mvp02_browser.mjs` driver and an isolated PostgreSQL test DB:

- Empty desktop/mobile; populated desktop and clean desktop reference.
- Populated mobile and clean mobile reference; tablet (1024px) and narrow mobile
  (360px); mobile reference at 390px; desktop at 1440px.
- Search with no results, advanced Jalali date/phase filters, and a no-JavaScript
  GET fallback. The JavaScript-enabled layouts were visually inspected.
- Real clicks verify pagination, filter submission, visible active chips,
  chip removal, page reset, sorting, row disclosure and responsive filter panels.
- Zero runtime JavaScript exceptions, zero page-asset HTTP errors and zero
  horizontal document overflow. The existing unrelated `/favicon.ico` 404 is
  excluded by the repository's shared browser driver.

Machine-readable browser evidence:
[empty states](browser/batch-empty-desktop.json),
[populated/interactions](browser/batch-desktop.json).

Visual evidence:
[desktop](browser/daily-report-owner-desktop-reference.png),
[mobile viewport](browser/daily-report-owner-mobile-reference-viewport.png),
[full mobile cards](browser/daily-report-owner-mobile-reference.png),
[tablet](browser/daily-report-owner-tablet.png),
[advanced filters](browser/daily-report-owner-advanced.png).

Native Chrome was also opened against the existing local development page and
visually inspected at desktop and 390×844 device emulation. No development data
was seeded or changed. Automated screenshots use synthetic test-only records.

Additional checks: Ruff PASS; JavaScript syntax PASS; Django system check PASS;
`makemigrations daily_reports --check --dry-run` reports no changes; scoped
`git diff --check` PASS; modified Persian source has no mojibake markers.

Reproduce focused tests and browser checks:

```powershell
.venv\Scripts\python.exe scripts\verification\daily_report_list_validate.py
```

The dedicated DB is `test_bonira_daily_list_ready_20261101`. It was cloned from
an inactive, already migrated test baseline containing zero Daily Reports;
Django's normal migration setup then ran against the dedicated clone. The
incomplete session-created initial test DB was removed after verifying no active
connections. The source test baseline and configured development DB were preserved.

## Findings and corrected validation failures

The unmodified original `apps/daily_reports/tests.py` suite has twelve fixture
failures at `setUp`, line 72, before the list is called: legacy membership role
fields do not supply current explicit role/scope assignments, so project creation
correctly denies access. This is baseline test-fixture debt, not a product
authorization change. The original file was preserved. The new test-only wrapper
uses the existing `explicit_fixture_roles` helper before fixture project creation
and retains the original twelve test methods and assertions unchanged; all pass.

The first test DB setup raced snapshot creation and was retried after completion.
Browser test expectations were corrected to accept the shared controller's
`page=1` reset and to use a non-navigation click for the advanced-filter disclosure.
Final Chrome verification passed after those test-only corrections.

## Repository and acceptance boundary

- Branch: `main`; HEAD `5b760e85`; ahead/behind `origin/main`: `0/0`.
- Existing dirty files preserved; no branch/worktree created.
- `git add`, `git commit`, `git push`, `git merge`: **NOT EXECUTED**.
- No CEP lifecycle/Registry changes, production action, Human Sign-off or
  Production Certification. Further CEP execution was not started.
- Product Owner visual acceptance: **PENDING**.
