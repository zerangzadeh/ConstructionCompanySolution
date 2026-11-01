# Estimate Create visual acceptance

Authority: explicit user request; image used for visual layout only. Image text is not executable scope.
Branch: main. Start HEAD and origin/main: 5b760e853b329e2b03415da7b046641359db6a62.
Existing dirty working tree was inspected and preserved. No branch/worktree or Git writes.

Touch set:
- templates/estimates/create.html
- templates/estimates/create_field.html
- apps/estimates/static/estimates/estimate_create.css
- apps/estimates/test_create_reference.py
- scripts/verification/estimate_create_validate.py
- scripts/verification/estimate_create_browser.mjs
- output/estimate-create-reference/ (acceptance evidence)

Product change: single surface, full-width project and notes, desktop paired
contract/phase and number/title, mobile single column, required/optional labels,
accessible adjacent errors, shared searchable choices and shared footer.
Existing project inheritance, active-project initialization, cancel destination,
CSRF, choice cascade and media retained. No new workflow step or field.
Models, migrations, services, form validation, permissions, tenant/project scope,
contract/phase eligibility and Product Surface are unchanged.

Validation uses installed Google Chrome via CDP and a Django static live server,
with a dedicated disposable PostgreSQL database:
test_bonira_estimate_create_acceptance_20261101.
This was cloned from an inactive, fully migrated test database with zero users,
organizations, projects and estimates. No source data or development DB was changed.
The initial fresh migration build was interrupted; its unused test DB remains
separate from the final acceptance run.
Command: .venv/Scripts/python.exe scripts/verification/estimate_create_validate.py
Results:
- Existing contextual-create / Estimate UX regression: 26 passed, 8 subtests passed.
  Evidence: validation.log (the initial run also contains a subsequent browser
  harness failure; it is not the final browser result).
- Final Chrome acceptance: 1 test passed, 18 scenarios. Evidence:
  browser-validation.log and browser/batch-*.json.
- RTL and LTR form direction: desktop 1440/1024, mobile 390/320; no overflow.
  The product remains Persian RTL; LTR tests set the form container direction.
- Real Tab/Shift+Tab; searchable project/contract/phase selection with real
  ArrowDown/Enter; adjacent required errors with aria-invalid/aria-describedby;
  duplicate-number errors retain entered values; create with/without optional
  relations; inherited project cancel; active-project initialization; local
  project choices leave global context unchanged; member denied with HTTP 403
  on desktop/mobile.
- Django system check: no issues. Ruff check and format check: PASS.
  Node syntax and scoped git diff whitespace check: PASS.
- Visual review: desktop/mobile, selected optionals, required errors, LTR 320.
  Hierarchy, single surface, spacing, field grouping and actions conform to the
  user prompt and reference. No illustrated two-step workflow was introduced.

Harness findings resolved: headless Chrome needed focus emulation; the required
project test needed to clear the intentionally preserved active-project default;
a non-navigating fill step needed an inspection continuation. No product/domain
validation was changed to satisfy these tests.

ESTIMATE CREATE UX: PASS
FORM VALIDATION UX: PASS
BROWSER VALIDATION: PASS
REFERENCE VISUAL CONFORMANCE: PASS
Product Owner visual acceptance: PENDING.
Commit: NOT EXECUTED. Push: NOT EXECUTED.
