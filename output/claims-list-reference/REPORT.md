# Claims List visual-reference implementation — 2026-11-01

Authorization: explicit user request, bounded Claims List UX; no CEP lifecycle change.
Branch: main. Start HEAD: 5b760e85 (origin/main aligned, 0/0).
Existing dirty and untracked work preserved. No branch/worktree, staging, commit,
push, merge, production action, or Development-data mutation.

## Actual touch set

- apps/billing/views.py: only claim_list delegates read-only list presentation;
  its existing selector, project/contract scope, create authority, routes and
  breadcrumbs remain. Other pre-existing edits preserved exactly; see
  views-session.diff relative to views-before.py.
- apps/billing/claim_list.py: validated presentation filters, scoped choices,
  deterministic sorting/pagination, result and status counts.
- apps/billing/templates/billing/claim_list.html: official Contracts components,
  requested header, existing journey navigation, scope context, filter chips,
  summary, table, detail links, vertical menu and pagination.
- apps/billing/static/billing/claim_list.css: page-scoped layout and column sizing.
- apps/billing/test_claim_list.py and scripts/verification/claim_list_validate.py:
  focused scope/filter and actual Chrome verification on isolated PostgreSQL.
- output/claims-list-reference/: grounding, delta, validation, screenshots/report.

No models, migrations, calculation services, workflow, permissions, Product
Surface, tenant/project authority or financial authority changed. No dependencies.

## Presentation decisions grounded in existing data

Search matches contract title/number, project name and exact numeric claim number
(including Persian digits). Status and exact persisted period are quick filters;
project/contract are advanced filters over the authorized claim queryset only.
The claim_contract parameter is distinct from the existing contract journey
context. Scoped lists omit project/contract choices. Clear/chip removal retain
contract/project context and sorting; pagination retains filters.

Counts describe all filtered authorized records, before pagination. No financial
sum or currency-mixing KPI added. Gross, signed adjustments, net, creation date
are existing persisted fields. adjustment_amount includes both negative
withholdings and positive tax; it is accurately labelled کسورات و اضافات.

Primary number/revision opens existing Detail. The vertical menu exposes only the
existing detail route in a new tab, identical to Contracts. No new lifecycle
command or state-dependent authority is invented. Create CTA uses existing
can_create_claim/create_url computation, including Product Surface and scoped
contract eligibility. Empty state gives concise existing prerequisites.

## Validation

- validation.txt: 4 focused tests PASS (filters/counts, stable pagination,
  invalid inputs, project isolation and choices, restricted and denied users).
- regression.txt: 16 existing MVP-03 tests PASS (real claim calculation,
  approval/return workflow, tenant isolation, object/project scope, CSRF/method
  controls, existing navigation and session context).
- Django manage.py check: PASS, zero issues.
- Ruff check and new-file format check: PASS. git diff --check on changed tracked
  product files: PASS.
- Browser: installed Google Chrome executable, headless CDP; existing repository
  browser driver; isolated Django static live server and PostgreSQL test DB.
- browser/batch-CL-global-desktop.json: 10 scenarios PASS: Global desktop/mobile,
  page 2 with sort retained, row menu open, status chip/Clear All, advanced
  disclosure, scoped filter submit/context retained, scoped filtered mobile,
  filtered empty, real detail route.
- browser/batch-CL-restricted.json: 2 restricted-user desktop/mobile scenarios PASS;
  no create CTA. All 12: no page/asset HTTP errors, JS exceptions or document
  horizontal overflow. Legacy shell favicon excluded by existing driver.
- Screenshots visually reviewed: Global desktop, scoped filtered mobile,
  row menu and advanced filters. Initial narrow status-column wrapping corrected
  and revalidated. BONIRA Contracts typography/components and responsive cards
  retained; attachment guides hierarchy, density and composition. No fabricated
  financial total, row command, filter or page-size control added.

Fresh full test migration setup was slow and interrupted. Final validation uses a
separate clone of the idle existing baseline test database:
  test_bonira_claim_list_clone_20261101
Django/pytest checked/applied its configured test migrations. All records are
synthetic test fixtures; no Development data changed. Initial fixture assumptions
and driver navigation-wait errors were corrected before the final passing run.

CLAIMS LIST UX: PASS
CONTRACT-SCOPED UX: PASS
BROWSER VALIDATION: PASS
REFERENCE VISUAL CONFORMANCE: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

Human Sign-off: NOT EXECUTED. Production Certification/Cutover: NOT EXECUTED.
Git add/commit/push/merge: NOT EXECUTED.
