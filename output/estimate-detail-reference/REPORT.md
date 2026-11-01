# Estimate Detail visual acceptance — execution scope

Date: 2026-11-01 (Asia/Tehran). Explicit bounded user request; not a CEP execution.
Branch: main. Start HEAD and origin/main: 5b760e853b329e2b03415da7b046641359db6a62.
Existing working tree contains unrelated user changes; preserved. No Git writes authorized.
Reference: user-attached ChatGPT Image Nov 1, 2026, 09_34_41 PM.png.
Graph vocabulary: estimate, detail, approval, permission, revision; query used for navigation only, current code inspected.

Actual intended touch set:
- templates/estimates/detail.html and detail_currency.html (presentation only)
- apps/estimates/static/estimates/detail.css (scoped appearance)
- apps/estimates/test_detail_reference.py (isolated HTTP/browser verification)
- scripts/verification/estimate_detail_validate.py (disposable test DB runner)
- output/estimate-detail-reference/ (evidence)

Models, migrations, services, calculations, permissions, views, forms, tenant/project scope,
approval/revision semantics and Product Surface stay unchanged.
No row edit/delete/revision endpoints or linked-contract creation flow exist in current UI.
No invented row menus or contract creation link will be shown. Real secondary navigation
is grouped under the header ellipsis. Empty Draft approval remains unavailable.

## Validation environment and findings

- Validation is confined to synthetic PostgreSQL test databases and the existing real Chrome/CDP driver.
- Empty source `test_bonira_estimates_sites_ready_20261101`: all 446 current migrations present,
  zero organizations, no open sessions. Copied to `test_bonira_estimate_detail_clone_20261101`.
  The source was not changed. Django still checks/applies migrations against the clone.
- An initial concurrent fresh-database setup collided; the second run was stopped and
  all subsequent checks run serially. This is test infrastructure error, not product evidence.
- Initial new-fixture failures (invalid unit category `mass`, implicit legacy USD label)
  were corrected in synthetic fixtures only. UnitCategory.WEIGHT and explicit IRR are used.
- Pre-existing finding: original Estimate Detail uses `request.organization.currency`.
  `Organization.currency` is described as legacy in the model; the canonical configuration
  boundary is OrganizationSettings. This task preserves the original page's currency source;
  the IRR label is localized without conversion. No new financial authority is inferred.
  Currency-source remediation requires its own bounded follow-up and is not claimed here.

## Implemented result

- Coherent title/number/project/status header; existing permitted nonempty Draft approval
  is primary. Real secondary navigation is behind the native ellipsis disclosure.
- Four compact actual-data KPIs and a compact info grid, including real creation date,
  creator and optional phase/contract. Shared status badges, breadcrumbs, icon components
  and canonical BONIRA tokens remain consistent with Contracts Detail.
- Seven-column current-revision table with formatted quantities/money and a clear total
  footer outside horizontal scrolling, visible on mobile. No fake row actions.
- Native add-item disclosure is in the table heading and uses the existing POST form,
  validation, choices, CSRF and project context. Form errors keep it open.
- Approved, revised and archived states keep their existing read-only presentation.
- Component clipping resolves actual mobile document overflow while local RTL table
  scrolling still reaches all columns. Decorative total-card icon is omitted on mobile.
- No models, migrations, views, forms, services, workflow, permission catalog, scopes,
  Product Surface or calculation changes. No new edit/delete/revision/contract-linking flow.

## Final validation

Command:
`.venv/Scripts/python.exe -u scripts/verification/estimate_detail_validate.py apps/estimates/test_detail_reference.py apps/estimates/test_mvp03_estimate_ux.py --reuse-db -q`

- `final-validation.txt`: **15 tests PASS, 11 subtests PASS**, 185.48 seconds.
- `validation-summary.json`: **21 Chrome scenarios PASS**. Desktop 1440/1672 pixels,
  mobile 390 pixels. Draft with/without rows, approved, revised, archived, linked/unlinked
  contract, restricted reader desktop/mobile, native no-JS disclosure, header menu,
  invalid form/reopened editor, real append and real approval retaining project context.
- Real append: five rows become six; canonical total 89,220,000 becomes 89,222,500.
  Real approval then hides both mutation entry points. Restricted forged POSTs remain 403;
  cross-tenant read remains 404. Prior workflow/tenant/context tests pass unchanged.
- Zero page JavaScript exceptions or HTTP asset errors in accepted scenarios. The existing
  absent favicon is excluded by the shared driver.
- Django system check: PASS (0 issues). Both templates compile; scoped static CSS found.
  Ruff check/format: PASS. Scoped `git diff --check`: PASS. Protected backend paths unchanged.
- Final desktop/mobile PNGs were visually inspected against the attached acceptance reference.
  Layout, hierarchy, spacing, density, KPI placement and table/action hierarchy conform
  within existing capabilities and the unchanged shared BONIRA shell. No pixel-identity claim.
- The first desktop probe imposed an unnecessary panel-bottom <900px heuristic; it was
  replaced with compact-card geometry plus visual footer review (not a user requirement).
  Initial genuine mobile overflow was fixed, and all accepted mobile scenarios now explicitly
  prove local table scrolling and a footer within the viewport. Temporary diagnostic probes
  were removed from test source; intermediate failure diagnostics are not final acceptance.

Final previews:
- `browser/f61-owner-draft-1440.png`
- `browser/f61-owner-menu-1672.png`
- `browser/f61-owner-draft-390.png`
- `browser/f61-owner-approved-390.png`
- `browser/estimate-detail-reader-restricted-est-linked-390.png`

ESTIMATE DETAIL UX: PASS
STATE-AWARE UX: PASS
BROWSER VALIDATION: PASS
REFERENCE VISUAL CONFORMANCE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

Branch remains main; HEAD and origin/main remain the recorded start revision.
Git add/commit/push/merge and branch/worktree creation: NOT EXECUTED.
Human Sign-off, Production Certification and Production Cutover: NOT EXECUTED.
