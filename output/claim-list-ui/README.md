# Claims list UI refresh — 2026-11-03

Scope: the Human-requested UI/UX change only; no CEP execution or production action.
Branch: main. HEAD and origin/main at start: 28a9896086faa50064bf6f8d53a66a4628657b22.
Pre-existing dirty changes were inspected and preserved. No branch/worktree or Git checkpoint created.

## Product touch set

- `apps/billing/templates/billing/claim_list.html`: short breadcrumb, unified header actions, compact project/contract context, combined controls, summary strip, conditional context column, currency headers and existing row links.
- `apps/billing/static/billing/claim_list.css`: scoped density, neutral money, net emphasis, consistent badges, responsive controls and contained table scrolling.
- `templates/components/filter_bar.html`: optional compact-layout attribute and asset cache version.
- `apps/accounts/static/js/erp_filter_bar.js`: opt-in expanded quick filters at all widths; existing pages retain their breakpoint behavior.
- `apps/billing/test_claim_list.py`: focused navigation regression for the short trail and retained context identity/return link. The claim-list parent expectation in `test_mvp03_breadcrumbs.py` is aligned with the requested shorter trail.
- This directory: disposable-database verification runner, browser JSON and screenshots.

No models, migrations, services, views, forms, permission rules, workflow, billing calculations, sort/filter semantics or Product Surface changes.
No change to sidebar, module selector, shell navigation or working-context selectors.
Contract/project repetition is removed only when `selected_contract` is present; general/project lists retain their identifying column.
Single-currency pages put the actual snapshot currency in monetary headers. Mixed-currency pages keep one row currency marker beside net; mobile labels retain currency because column headers are replaced by row labels.

## Verification

- `python manage.py check`: PASS, no issues.
- `node --check apps/accounts/static/js/erp_filter_bar.js`: PASS.
- Ruff check and format check of the adjusted Python test: PASS.
- Scoped `git diff --check`: PASS.
- Existing ClaimsListBrowserTests.test_chrome_acceptance, through the isolated runner: PASS. Covers general/scoped desktop and mobile, pagination, sort retention, row menu, advanced filters, clear filters, empty results, and restricted-user create visibility.
- Final requested-viewports run: PASS (1 test, 7 Chrome scenarios). Contract and general lists at 1440, 1024, 390 plus mobile status-filter submission retaining contract scope. JSON: `browser/batch-contract-1440.json`.
- Chrome assertions: Persian/RTL, no page-level horizontal overflow, visible status/apply controls, correct context-column count, export in header, uniform neutral monetary text, no JS or page HTTP errors, no flagged technical selector labels.
- Visual inspection: contract 1440 and 1024; filtered 390, with large synthetic financial values and a long Persian project name. Tablet table scrolls within its container; mobile uses the existing responsive row presentation.
- Final HTTP scope/navigation regression: PASS, 4/4 (`ClaimsListTests`, including the new independent context-navigation assertion). Command: `.venv/Scripts/python.exe scripts/verification/claim_list_validate.py apps/billing/test_claim_list.py::ClaimsListTests --reuse-db -q --tb=short`.
- Adjacent existing `BusinessBreadcrumbTests.test_claim_baseline_progress_details_lists_and_create_have_real_parents`: BASELINE TEST DEBT. Fails on the first baseline-detail breadcrumb assertion: expects `/billing/baselines/` but implementation supplies `/billing/baselines/?contract=<fixture>&versions=1`. The changed claims page is never reached. Baseline-detail product code was not modified. Its claim-list expectation is aligned with this change; the failing baseline-detail expectation is unchanged. Focused claims navigation is verified separately.

The first visual pass exposed the shared filter disclosure closing below 1280; the opt-in expanded behavior resolves it. Verification-fixture-only failures (protected contract title and a fill-only browser step requiring navigation) were corrected in the disposable runner. No product invariant was weakened.

Only dedicated disposable PostgreSQL `test_bonira_claim_list_clone_20261101` was used for these fixtures. Its migrations are managed by Django's test runner; no application or production migration was executed.

## Review state

VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
Human Sign-off / Production Certification / Production Cutover: NOT EXECUTED.
Git add / commit / push / merge: NOT EXECUTED; changes remain uncommitted.
