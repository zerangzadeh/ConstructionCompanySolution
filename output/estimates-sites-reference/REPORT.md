# Estimates and sites list visual alignment

Authorization: direct Human request, 2026-11-01, to align `/estimates/` and
`/projects/sites/` with the existing Contracts list. Ordinary bounded UI task;
no CEP execution or lifecycle change.

Repository grounding: local `main`, HEAD and `origin/main` at `5b760e85`,
ahead/behind 0/0. Pre-existing tracked and untracked changes were present,
including Contracts/shared presentation work and `apps/projects/views.py`.
Those changes are preserved; no Git writes are authorized or performed.

Intended/actual touch set: the two target list templates; an opt-in stylesheet;
a presentation-only template tag and toolbar partial; optional search-field
selection in `core/list_filters.build_filter_bar`; this evidence directory.
No models, migrations, business services, views, permission or query semantics
are changed. Existing filter parameter names remain authoritative.

Implemented: existing Contracts stylesheet, header context, shared filter bar,
result count, sorting menu, compact table, status badges, row menus and pagination.
Opt-in CSS handles these six-column tables and mobile cards without changing
Contracts styling. The presentation adapter does not access the database.
Original estimate `title`, `number`, `project`, `status` and site `site`, `project`
GET parameters are retained. No invented global search, status filter for sites,
financial sum, site-create route or lifecycle action is added.

Browser verification (connected Chrome, existing local demo session):

- Both global lists render with exactly one filter bar and footer.
- Estimates: 16 authorized demo rows; title search yields 4, then draft status
  yields 3; number sorting works. Existing project context yields 9 rows and
  remains in Create/Detail URLs, hidden filter controls and Clear All/empty-state
  clear links. A zero-result search clears back to those 9 scoped rows.
- Sites: 4 demo rows; unmatched search yields zero and a filtered empty state;
  Clear All restores 4. Mobile project-text filtering yields 1 matching row.
- Mobile cards verified at a 390px viewport override (375px content plus scrollbar)
  on both pages: no document horizontal overflow. Filter disclosure and the site
  row menu work; Escape closes the menu; Detail opens via the existing URL in a
  new tab. Screenshots are saved beside this report.
- Django initially rejected a tag placed in uninstalled `core`; corrected by
  locating it in installed `apps.accounts.templatetags`. Final pages render.

Focused automated validation: **44 tests PASS, 68 subtests PASS; 3 baseline test
debt failures**. Command: `.venv/Scripts/python.exe
output/estimates-sites-reference/validate.py`; complete output: `validation.txt`.
Coverage: existing Estimate UX/context tests, Sites tenant-isolation test,
Contracts shared filter-bar tests, and localization/accessibility regression.
No affected Estimate/Sites/filter-bar test failed. No full-regression PASS is
claimed.

The three baseline test-debt failures are in
`core/test_cep003_localization_accessibility.py`:

- `DeferredUiPatternTests.test_ess_grouping_preserves_permission_gates`
- `DeferredUiPatternTests.test_navigation_denies_ungranted_destinations_and_has_no_dead_placeholders`
- `DeferredUiReferenceTests.test_navigation_uses_existing_availability_flags_and_omits_empty_groups`

Attribution: these tests directly render `workforce/_ess_navigation.html` or
`components/navigation_links.html` with legacy minimal `Context` dictionaries.
They do not render either changed list, its new tag/toolbar or `build_filter_bar`.
The two navigation templates, the failing test file and the product-surface tag
are unchanged from HEAD (`git diff --exit-code HEAD -- <those four paths>` PASS).
Current main navigation expects `product_navigation_groups`, absent from those
legacy test contexts; ESS is hidden by the current MVP product surface. These
expectations are independent of this list work. The unrelated failures are
retained without mutation.

First setup used an incompletely migrated
test baseline and was interrupted during test-only migration preparation; no test
PASS is claimed for it. Final run uses a separate clone of the idle
`test_bonira_mvp03_20261029` baseline, checked to contain all 446 migrations.
Development database/schema and records are not mutated by validation.
The dedicated final test database is `test_bonira_estimates_sites_ready_20261101`;
all test fixtures/mutations are confined there. The interrupted initial test-only
database is retained, with no production/development migration performed.

Static checks: Django system check PASS (zero issues); Ruff lint and format PASS
for both Python product files; changed tracked product files pass `git diff --check`;
all six product files pass UTF-8/mojibake inspection.

Out-of-scope baseline finding: `/estimates/?sort=amount&direction=asc` raises
`FieldError` before template rendering. At unchanged HEAD, the view maps `amount`
to `total_amount`, while `Estimate.total_amount` is a Python property, not a
database field. No view/model/service fix is made. The new UI displays the exact
existing amount but does not expose the broken amount-sort link in either header
or sort menu. Direct legacy amount-sort URLs remain a known backend limitation.

Full regression, production deployment/cutover, Human Sign-off and Production
Certification are not executed. Git add/commit/push/merge are not executed.
