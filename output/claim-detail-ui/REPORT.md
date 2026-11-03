# Claim detail UI refinement — 2026-11-03

Authorization: User explicitly requested implementation of the preceding claim-detail design review. This is a bounded UI task, not CEP execution or production authorization.

Grounding: main; start HEAD and origin/main `28a9896086faa50064bf6f8d53a66a4628657b22`.
Existing unrelated tracked changes: `scripts/verification/mvp02_browser.mjs`, `templates/daily_reports/detail.html`; pre-existing MVP-08 untracked files were preserved. `apps/procurement/rfq_actions.py` changed concurrently during this task and was not edited here.

## Touch set

- `apps/billing/templates/billing/claim_detail.html`: compact header, adjacent print/Excel actions, structured contract/project/period metadata, signed adjustment summary, clear period labels, draft-action guidance, quantity headings, ea presentation as عدد.
- `apps/billing/templates/billing/journey_nav.html`: opt-in detail navigation labels/wrapping; preserve routes, permission conditions and all other callers' behavior.
- `apps/accounts/static/css/tailwind.css`: regenerate existing Tailwind bundle.
- `scripts/verification/claim_detail_validate.py`: reusable isolated PostgreSQL and Chrome visual/action verification, reusing existing fixtures and browser driver.
- `output/claim-detail-ui/`: verification evidence and this report.

No models, migrations, domain services, calculations, permissions, approval authority, or stored business data were changed. All existing POST endpoints and CSRF controls remain in use.

## Supported presentation semantics

`apps/billing/services.py` computes adjustment_amount as net minus gross; the UI displays its existing signed value and explains its effect without calculating new financial values.

There is no independent calculation timestamp or freshness marker in the inspected claim contract. The page truthfully labels updated_at as the last update of the version. It does not claim that source data is current.

The contract number remains visible as a legitimate business identifier, including test fixture numbers such as UAT-REC. No real data or business identifier was rewritten to remove test content. The existing tax type label remains unchanged because this UI task does not authorize redefining its financial meaning.

## Validation

- Tailwind build: PASS.
- Django system check: PASS, zero issues.
- UTF-8/mojibake scan of changed templates: PASS.
- Ruff check and format of verification script: PASS.
- git diff --check: PASS (only repository CRLF notices).
- Focused existing regression: 21 PASS / 2 FAIL, 1229.88 seconds including cold database creation/migrations. Selection: `apps/billing/test_mvp03.py`, `apps/billing/test_journey_navigation.py::JourneyNavigationTests`, `apps/billing/test_mvp03_breadcrumbs.py`; isolated DB `test_bonira_claim_detail_ui_20261103`.
- Failures: breadcrumb tests expected an unfiltered baseline-list URL while the baseline-detail page emitted a contract/version-filtered URL; a foreign/unrelated-estimate baseline-list request expected HTTP 200 but received 404. Both are outside this UI touch set. Attribution: both failures reproduced identically with both changed templates supplied from HEAD through an in-memory loader (2 failed, 37.88 seconds). Classification: BASELINE TEST DEBT. No source files were reverted for this comparison; see baseline-attribution.txt.
- Browser assertions: 8/8 PASS in real headless Chrome. Draft at 1440, 1024, 390 and 320px; no-JavaScript mobile; recalculate and submit through existing CSRF-protected forms; independent manager approval; approved mobile. All page responses HTTP 200. No viewport overflow in checked scenarios. Screenshots visually reviewed at desktop and mobile; see browser-summary.json and browser/.
- Harness outcome: the first full browser run reported 1 FAIL solely in final database flush (retained unmanaged payments_payment FK to accounts_user), after all eight browser scenarios and both persisted-state assertions passed. Classification: TEST INFRASTRUCTURE DEBT, not a product regression. Added the repository-established allow_cascade cleanup with an exact disposable-database guard. The corrected cleanup was executed independently; see cleanup-verification.txt. The entire browser harness was not rerun after this cleanup-only correction.
- Reproduction: `.venv/Scripts/python.exe scripts/verification/claim_detail_validate.py`. The runner now uses --create-db for a pristine migration-seeded fixture baseline; cold migrations are expensive. A separate cold visual-DB preparation was stopped before browser execution once the completed regression DB was available. No non-test database was mutated.

Human Sign-off, production deployment, and certification: NOT EXECUTED.
Git branch/worktree creation, add, commit, push, merge: NOT EXECUTED.

Final HEAD unchanged. Additional concurrent procurement print-output changes were preserved. Product mutation remains limited to the two billing templates and generated CSS bundle.
