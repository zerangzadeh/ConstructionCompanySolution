# Payable Certificate Detail — visual reference remediation

Authorization: explicit user request, presentation only; no commit or push.
Branch: main. Start HEAD/origin/main: 5b760e853b329e2b03415da7b046641359db6a62.
The working tree already contained unrelated edits. They were retained; the existing
billing/views.py changes were preserved and only the detail context was extended.

## Actual touch set

- apps/billing/templates/billing/payable_certificate_detail.html
- apps/billing/templates/billing/payable_currency.html
- apps/billing/templates/billing/payable_decision_dialog.html
- apps/billing/static/billing/payable_detail.css
- apps/billing/static/billing/payable_detail.js
- apps/billing/payable_detail.py (read-only presentation of existing action authority)
- apps/billing/views.py (detail context and related unit loading only)
- apps/billing/test_payable_detail.py
- scripts/verification/payable_detail_validate.py
- this evidence directory

No model, migration, calculation, mutation service, workflow, permission catalog,
project/tenant scope, financial handoff or Product Surface change. Browser JavaScript
only opens/closes native dialogs and restores focus. Existing POST endpoints, CSRF,
forms and domain validation remain authoritative. Known generated adjustment codes
are translated at rendering; user-entered descriptions remain unchanged. Signed
adjustments are displayed as stored, without reversing signs or inventing totals.
Missing snapshot fields show a dash; rates are already stored in percent and are
formatted directly, without multiplying them. All dates come from record fields.

## Validation environment

Isolated PostgreSQL test_bonira_payable_detail_ready_20261101, cloned from the idle,
fully migrated test_bonira_payable_list_ready_20261101 (446 recorded migrations,
zero tenant organizations, zero certificates). Development database was not changed.
Initial full test database migration was stopped because it was costly; that partial
scratch database was not used as validation evidence.

Command: .venv/Scripts/python.exe scripts/verification/payable_detail_validate.py
Checks: manage.py check; Ruff for touched Python; git diff --check for touched files.
Chrome: real installed Google Chrome, headless CDP, isolated profile, authenticated
Django static live server. The existing qualified driver checks HTTP status, page
errors, JS exceptions, RTL, technical labels and document horizontal overflow.
Favicon 404 is an existing shell issue explicitly excluded by that driver.
All business data in captures is synthetic isolated test data, generated through
existing application services. No Development certificate was mutated for testing.

The first run exposed a test assumption: the current certificate selector requires
organization scope. The project-only reader correctly received 404. The final
read-only reader has organization scope and only payable_certificates.view.
The implementation preserves the existing selector and authorization behavior.
Visual review also corrected legacy button class names and localized generated
contract_term.* adjustment descriptions before final validation.

## Reference adaptation

Header identity and revision; state-aware primary CTA and secondary menu; three-step
workflow; net payable emphasis; gross, signed deductions, due date; actual-section
anchors; basis/caps; measurement units and quantities; on-demand deduction panel;
modal reasons; actual timestamps, lineage and collapsed technical evidence.
Desktop uses the existing BONIRA shell. Mobile stacks financial cards and renders
measurement/deduction table rows as labelled cards without horizontal scrolling.
Existing navigation and capability exposure are unchanged.

Product Owner visual acceptance remains PENDING.

## Results

- Chrome: 18/18 PASS, desktop 1440 and mobile 390; all authorized documents HTTP
  200; no document horizontal overflow, JavaScript exceptions, or non-favicon asset
  errors. See browser-summary.json, batch JSON files and 18 PNG captures.
- Verified: Draft, Submitted, Approved, Returned, linked corrected draft; positive
  certificate without deductions; certificate with deductions; restricted reader.
- Actual UI POST journeys: submit, approve, return, correction, add documented
  deduction. Modal open/focus and absence of unauthorized mutation controls proved.
- Visual review: draft desktop/mobile, submitted decision dialog/mobile, corrected
  mobile, financial values, translated deduction descriptions, and real lineage.
- System check and Ruff PASS. No Git writes.
- Expanded regression: 6 passed, 1 BASELINE TEST DEBT (expanded-regression.txt).
  The extra inherited test_explicit_ap_and_non_operational_posting_handoffs calls
  recognize_obligation before any view/template rendering and fails in unchanged
  apps/accounting/services.py:332 because its fixture lacks an approved effective
  ControlAccountMappingVersion. The new display helper is never reached. The exact
  inherited test body was reused unchanged; no financial service was modified.
  This extra unrelated legacy test was not retained in the bounded UI test module.
  Accounting/AP certification or full-suite regression PASS is not claimed.

PAYABLE CERTIFICATE DETAIL UX: PASS
WORKFLOW ACTION UX: PASS
FINANCIAL DATA PRESENTATION: PASS
BROWSER VALIDATION: PASS
REFERENCE VISUAL CONFORMANCE: PASS (structural adaptation in existing product shell)
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

Final focused functional run: 5 passed, 1 browser test deselected in 52.29s;
see focused-tests.txt. The browser test passed in the preceding expanded run,
with all 18 scenarios retained in browser-summary.json.
Final HEAD remains the start HEAD. No commit, push, branch, or worktree created.

## Section selection follow-up

The first section-only static probe did not cover browser-cached page assets.
CSS and JS URLs now use v=20261101-section-selection-2. A direct click handler
updates aria-current immediately while native anchor navigation remains intact;
hash changes and reload still synchronize selection. All five links are tested
on the complete Django-rendered certificate page in actual Chrome at 1440 and
390 pixels, including returning to Summary and reloading with Basis selected.
Assertions verify exactly one aria-current link, a 4px underline only on that
link, and no underline on inactive links. Mobile screenshot was visually reviewed
and shows Basis selected with Summary inactive. Evidence: section-selection-live.txt
and browser/batch-actual-detail-section-selection-1440.json.
