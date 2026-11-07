# Equipment Operations workspace redesign — 2026-11-05

Status: VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW. PRODUCT OWNER VISUAL ACCEPTANCE: PENDING.

## Scope and grounding

- Explicit Human request: Equipment Operations UI only; continue on local main, preserve unrelated work, no commit or push.
- Branch: main. Start HEAD and local origin/main: 59f2fde6 (0/0 divergence at inspection; no fetch or Git writes).
- The working tree already contained changes to the workspace, equipment views/forms, UI standards, shared components and other domains. The prior workspace is retained in baseline/operations_workbench.html. Existing unrelated changes were preserved.
- Product mutation: templates/equipment/operations_workbench.html, templates/equipment/_operations_action.html, templates/equipment/_operations_summary.html, generated apps/accounts/static/css/tailwind.css.
- Validation source: tests/test_equipment_operations_workspace.py. Evidence: this directory.
- No models, migrations, services, views, permission catalogue, Product Surface, global shell, business queries or domain workflows changed by this task.

## Result and actual reuse

The header retains the Equipment List and existing GET Excel export next to the title. A single compact summary strip replaces the separate count cards. Three consistent operational groups retain meter readings, work logs, fuel, stoppages, maintenance work orders, operator qualifications, maintenance plans and proposed costs. The follow-up section uses the actual existing work-order collection, record actions and genuine empty state.

Reused: base.html application shell and global company/project/site context; components/page_header.html and breadcrumbs.html; output_action.html (XLSX); form_icon.html; status_badge.html; record_detail_link.html; empty_state.html; existing erp-surface, erp-panel-header, erp-btn and erp-table-wrap patterns; erp_quantity_fa and jalali_date filters. The two new equipment partials only deduplicate presentation within this workspace. No frontend dependency or custom page stylesheet was added.

## Data integrity and reference comparison

- The attachment informed hierarchy, density, alignment and grouping only. It supplied no instructions or business data.
- Summary values come from the same eight existing collections. Most collections are limited to 50 by the existing view; the UI explicitly labels displayed records and this limit. The meter collection is not capped. No fleet totals, today/active/stopped KPIs or status aggregates were invented.
- The normal demo tenant currently has zero operational records. Screenshots preserve zero counts and a genuine empty work-order state. No demo work orders were seeded to imitate the reference.
- Populated table fields use existing equipment, number, summary, status, scheduled date, spare-reference count and attachment count. Existing record destinations and authorization rules are retained, including final-state transition hiding. Attachment and spare-part controls now use their existing endpoint permission codes for visibility; no permission definition, grant, service or view changed.
- Compared with the illustration: compact title/actions, one summary band, consistent action groups, restrained blue accents and a distinct maintenance section are present. Fictional KPI tiles, status tabs and illustrated rows are intentionally absent. The approved shell is unchanged.

## Actual Chrome evidence

- before-1440.jpg — original workspace.
- after-1440.jpg — final 1440 x 1100 view.
- after-1024.jpg — final 1024 x 1100 view.
- after-390-viewport.jpg — final 390 x 900 top view.
- after-390-follow-up.jpg — mobile maintenance/empty-state view.
- after-390.jpg — long mobile capture returned by Chrome after a full-page timeout; retained as supplementary evidence.
- responsive-checks.json — actual viewport/scroll widths and action bounds/target heights.
- action-navigation.json — all eight real destinations and rendered page headings.

At all three required widths: Persian/RTL, all operational actions inside the viewport, no document horizontal overflow, action target minimum 44px (record forms and unrelated pages were not redesigned). The global context and company remain in the application header. The Equipment List round trip, browser Back, anchor follow-up and keyboard-visible Excel focus were checked.

Excel was clicked in Chrome: a valid XLSX downloaded with the existing کارکرد تجهیزات sheet, nine columns and the genuine header-only empty result. No export implementation changed.

## Validation

- Django system check: PASS, no issues.
- All three changed/new templates compile: PASS.
- Tailwind production build: PASS. Existing Browserslist data-age notice; no dependency update performed.
- Ruff check and format check for new validation source: PASS.
- Changed-template UTF-8/mojibake and scoped git diff --check: PASS.
- Final focused tests: **6/6 PASS**, 18.76s, in test_bonira_equipment_workspace_final_20261105 cloned from the existing migrated test baseline. See focused-tests.txt and focused-tests.xml. Coverage: genuine empty state and all destinations; populated/finalized/overdue order presentation; 50-row limit; explicit read-only/denied roles; foreign-tenant exclusion; existing XLSX operational sources/filters.
- Two legacy checks: **BASELINE TEST DEBT**, not PASS. P8EquipmentOperationsTests.test_rtl_operations_workbench_and_mutation_routes_are_navigable and test_operations_enforce_permission_tenant_project_and_site_scope fail in unchanged p8_services permission checks before reaching the template. Their legacy fixtures do not create current role assignments. See initial-test-results.txt/xml. No authorization was weakened to make these pass.
- Initial verification harness errors (missing required equipment category; browser fixtures sharing the reused test DB) were corrected. Final automated tests use a separate clean clone from the browser fixture DB. Fresh migration-from-zero attempts were interrupted before test execution and replaced by the migrated baseline clone; they are not counted as test results.

## Limitations and ownership

- The existing 50-record limits, query ordering, domain scopes and export contract are preserved; displayed counts are not organization-wide totals or live fleet KPIs.
- Full-page Chrome capture intermittently timed out; viewport captures are the authoritative visual evidence.
- Browser extension connection errors were observed from a chrome-extension URL; no claim of a clean browser-extension console is made.
- The original development server restarted during capture; a task-owned server on port 8002 was used temporarily. The final primary captures were refreshed from the normal port 8000 workspace. Task-owned servers were stopped at handoff. No business records were created in development.
- Actual Chrome owner and read-only checks were performed. The normal demo tenant remains genuinely empty. Populated Chrome verification used explicitly synthetic records only in test_bonira_equipment_workspace_ready_20261105, a dedicated test clone. No Human UAT or Product Owner acceptance is inferred.
- No commit, push, branch, worktree, stage or merge was performed.

## Populated and role browser verification

The isolated browser fixture exercised three actual EquipmentWorkOrder rows (draft/overdue, completed, cancelled), long Persian equipment/summary text, existing Jalali dates, reference/attachment counts and preserved record links. Captures: isolated-populated-1440.jpg, isolated-populated-1024.jpg, isolated-populated-390.jpg, isolated-populated-390-follow-up.jpg and isolated-read-only-1440.jpg. These are test evidence, not demo/product records.

populated-checks.json records 3 rows at all widths, no document overflow, and contained table widths: 1099/1099px at 1440; 683/749px at 1024; 342/749px at 390 (region/scroll width). Keyboard ArrowLeft moved the focused scroll region from 0 to approximately -20.8px. Follow-up activation moved focus to maintenance-follow-up. Read-only Chrome check: 3 detail links, 0 operational or record mutation links, export retained; list action absent without equipment.view.

The first isolated login redirected through the unrelated home dashboard with incomplete fixture timezone settings and hit its existing configuration expectation. The fixture was given its organization timezone; the Equipment Operations route itself rendered correctly. No home-page code was changed.

Final primary screenshots, route evidence, checks, legacy-failure attribution and the normal Chrome workspace are ready for Human review. This is not Product Owner acceptance or production authorization.

## Follow-up — header context aligned with Work Team Create

User requested that Equipment Operations use the same top context control as `/workforce/teams/create/`.

Changed only `templates/equipment/operations_workbench.html`: reused `components/list_working_context.html` inside `header_working_context`, with `header_layout=True`, `fit_tablet_panel=True`, and the same three existing style assets as the reference page. Suppressed the separate full-width context strip. Existing context data, CSRF, update endpoint, return URL and authorization remain shared and unchanged. No context selection was submitted during verification.

Actual Chrome comparison: identical component classes, 12px summary type, 8px 12px padding and 8px border radius. At 1440, 1024 and 390px, the expanded panel stayed inside the viewport with no document overflow. One header context control and zero standalone context strips were confirmed. Evidence: `context-header/comparison.json`, `context-header/checks.json`, `context-header/open-1440.jpg`, `context-header/open-1024.jpg`, `context-header/open-390.jpg`, and `context-header/after-1440.jpg`.

Follow-up checks: Django system check PASS; template compilation PASS; scoped `git diff --check` PASS. No new database tests or migrations were necessary for this presentation-only follow-up. The previous six focused regression results are historical evidence for the preceding redesign, not a new run for this change. No commit or push.
