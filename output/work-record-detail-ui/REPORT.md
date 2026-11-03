# Work Record Detail remediation

Authority: explicit bounded user request (2026-11-03); no CEP execution or lifecycle changes.
Grounding: local main, HEAD/origin/main 28a98960, 0/0 divergence. Existing dirty and untracked work preserved.

Intended touch set: progress_detail.html, measurement_detail.css; detail breadcrumb title in billing/views.py; additive exact Persian quantity filter in accounts/templatetags/erp_format.py; focused rendering/browser tests (including the existing contracts/test_hub.py detail-label assertions), read-only real-data probe, and this evidence folder. No models, migrations, services, permissions, calculations, data changes, or Product Surface changes.

Validation results and limitations will be recorded after checks.

Implemented: four compact areas; prominent current quantity and line-history return; exact Persian quantity digits/separators with no float/rounding; original baseline version/status; conditional review metadata; verbatim wrapped and bidi-isolated evidence; native keyboard-accessible disclosure; existing submit/verify/reject forms retained.

Read-only local-data check: `python scripts/verification/work_record_detail_real_data.py` PASS for one existing record in each of verified/submitted/rejected/draft (82 available). Probe uses a PostgreSQL READ ONLY transaction and does not save authentication sessions. No older-version baseline records exist in that dataset; historical supersession is validated with isolated fixtures.

Initial `pytest ... --reuse-db` failed at fixture setup due pre-existing duplicate f61-owner users, before changed behavior was reached (TEST INFRASTRUCTURE DEBT). Fresh dedicated PostgreSQL databases are used for conclusive checks; no application data cleanup was performed.

Changed files (this task only):
- apps/billing/templates/billing/progress_detail.html
- apps/billing/static/billing/measurement_detail.css
- apps/billing/views.py (current breadcrumb label only)
- apps/accounts/templatetags/erp_format.py (additive erp_quantity_fa; existing filters unchanged)
- apps/billing/test_work_record_detail.py
- apps/billing/test_journey_content.py (detail expectations only)
- apps/contracts/test_hub.py (detail browser expectations only)
- scripts/verification/work_record_detail_validate.py
- scripts/verification/work_record_detail_real_data.py
- output/work-record-detail-ui/REPORT.md and browser captures/results

Preserved: exact stored period/cumulative/baseline values, original source and baseline relationships, corrections, review evidence, URLs, permission-filtered actions, CSRF and confirmation flows. No model/schema/migration/service/financial-authority/Product-Surface changes. No commits, pushes, branch changes, or production actions.

Final validation:
- Focused fresh-migration PostgreSQL run: 9 tests PASS + 5 quantity subtests (work-record tests and existing JourneyContentTests). Full graph: 447 migration nodes; setup took most of the 36m19s run.
- Latest enhanced work-record tests: 6 PASS + 5 subtests in 17.41s, including real superseded-baseline access, original quantity/source preservation, correction linkage, optional reviewer/time handling, escaped multiline evidence, exact extreme quantities, read-only scoped access, and denied foreign-tenant session access.
- Actual headless Chrome: 2 tests PASS in 38.52s, covering 7 scenarios: verified at 1440/1024/390/320px, pending at 390px, rejected at 1440px, and return navigation retaining contract + line_key. Verified-page assertions include RTL, one H1, no document overflow, evidence expansion, no JS/HTTP errors. Batch evidence is in browser/batch-*.json.
- Visually inspected actual captures: verified 1440/390/320, rejected 1440, pending 390. Compact summary, primary metric, readable evidence, single-column mobile, accessible real controls; no visual overflow observed.
- Read-only existing-data probe repeated after final markup changes: all four available lifecycle states PASS; 82 available records; no historical-version records in that dataset.
- Ruff check PASS on all changed Python files. Ruff format check PASS on modified production Python and new scripts/tests. Django system check PASS (0 issues). Focused git diff whitespace check PASS.

Reproduction after initial setup:
`python scripts/verification/work_record_detail_validate.py --nomigrations`
Latest focused rerun reused that disposable schema via runpy followed by pytest on apps/billing/test_work_record_detail.py with --reuse-db --nomigrations. This supplemental presentation-only rerun used a model-synchronized PostgreSQL schema, not migration-rehearsal evidence; the earlier focused 9-test run used full migrations. PostgreSQL btree_gist was explicitly enabled only in test_bonira_work_detail_ui_20261103 for schema synchronization. No application database mutation occurred.

Validation corrections / residuals:
- The initial browser runner accidentally collected an imported browser TestCase. Its project-to-estimates filter scenario failed outside the work-record path (UNRELATED FAILURE); other imported journey tests passed. The runner now imports the module rather than the TestCase, so only its two intended tests are collected. Incidental tracked captures regenerated by that imported class were restored to their initially clean HEAD bytes.
- The first verified browser scenario treated a disclosure click as navigation and timed out (TEST INFRASTRUCTURE DEBT). Changed only the test instruction to toggleSelector; the final browser run passes.
- A migration-free supplemental setup initially lacked btree_gist; subsequent test cleanup removed code-owned roles. The dedicated test extension and explicit per-test catalog bootstrap resolved those fixture issues. No product permissions or role definitions were changed.
- Human visual acceptance / UAT was not issued. Full unrelated repository regression was not run. Extreme quantities and historical/correction states have focused rendering/HTTP coverage; browser screenshots use representative synthetic records. Stored English/technical evidence is deliberately retained verbatim.
- Existing unrelated working-tree edits, including additional changes made during the long validation run, were preserved. All implementation remains uncommitted; no push or production action.
