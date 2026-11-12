# Wave 01 UI/UX remediation and retest

**2026-11-10 Asia/Tehran.** Branch `main`, HEAD and local `origin/main` at `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`. All three targeted defects are **FIXED / RETESTED_PASS**, with formal Product Owner acceptance pending.

## Baseline and company-page preservation

The entry working tree contained eight modified paths covering the company List/Detail templates, platform forms/views, company tests, table filters and shared filter/result components. The two dedicated company CSS files and existing validation/output folders were untracked. The [entry record](evidence/wave-01-ux-remediation/baseline.json) fingerprints 129 protected implementation, dependency and historical-result files.

During verification, seven protected paths received incoming edits, covering the company views, List/Detail templates, dedicated List/Detail CSS, company tests and shared filter component. Their individual authorship cannot be established from Git. Their complete current contents were preserved in successive checkpoints, ending with the [closeout protected checkpoint](evidence/wave-01-ux-remediation/protected-closeout-checkpoint.json). The test server was restarted against that source before the last bounded company checks. **128 of 129 tested checkpoint files still match at closeout.** A further incoming change to `erp_platform_company_list.css` arrived after that pass and was preserved. Responsive verification of this last CSS delta is **BLOCKED by the moving baseline**; the captured revision has verified results below. The protected-operation catalog is the sole intentional template change within that wider fingerprint set. [Preservation verification](evidence/wave-01-ux-remediation/preservation.json)

| Page | Current record | Bounded results |
|---|---|---|
| PA-03 Companies List | PO_EDITED_CURRENT_BASELINE / FUNCTIONAL_VERIFICATION_PASS / VISUAL_ACCEPTANCE_PENDING | Captured RTL layout passed at 1440, 1024 and 390 px. Real search, status filter, no-results state, page 2 and company-detail links worked. Responsive verification of the last incoming CSS delta remains BLOCKED. |
| PA-02 Company Detail | PO_EDITED_CURRENT_BASELINE / FUNCTIONAL_VERIFICATION_PASS / VISUAL_ACCEPTANCE_PENDING | Current identity/status, owner/member information, edit/return links, section links, keyboard disclosure and responsive layout checked. Cancel preserved state; existing sensitive-action flow suspended/reactivated a synthetic company and retained audit. |

The supplied `/organizations/platform/companies/9f952d50-c609-4d8d-a6ef-aeec15b1e417/` was exercised with a synthetic company created at that key in the private clone. List navigation reached the correct target. Its incomplete-onboarding action created the missing starters and disappeared; the independent final witness confirms onboarding is complete. The existing Development record was outside the test environment. [Latest company browser checks](evidence/wave-01-ux-remediation/browser-latest-company-closeout.json) · [Supplied route and onboarding](evidence/wave-01-ux-remediation/browser-supplied-example.json) · [Lifecycle witnesses](evidence/wave-01-ux-remediation/company-reactivated.json) · [Final state](evidence/wave-01-ux-remediation/final-state.json)

## Corrections and independent retests

| Defect | Correction | Actual retest |
|---|---|---|
| BON-DEF-0001, P2 | The Platform tenant selector opts into suppressing its native source from the accessibility tree after successful Tom Select initialization. Destroy restores the original attribute. The source remains enabled and available without JavaScript. | Before, Chromium exposed two comboboxes, one unnamed. After, exactly one named company combobox at all three widths. Real keyboard search/Enter submitted the same authorized company. Native fallback and destroy restoration passed. |
| BON-DEF-0002, P2 | Audit range labels now say “از تاریخ شمسی” and “تا تاریخ شمسی”. | Labels and layout checked at all three widths. Jalali 1405/08/17 and 1405/08/20 became ISO 2026-11-08 and 2026-11-11. Focused tests verified inclusive lower/upper date boundaries, exclusion of adjacent days and safe invalid-date results. |
| BON-DEF-0003, P2 | The existing retirement form now uses shared SweetAlert2 confirmation with operation name, code, version, consequences and explicit confirm/cancel. | Before, one click immediately retired the synthetic version. After, cancel made zero POSTs and left operation/audit unchanged. Confirm made exactly one POST, retained the version history and added exactly one retirement audit event. Stable dialogs were measured at all three widths. Tenant-owner POST and invalid CSRF requests returned 403. |

Before evidence · [Original reproduction](evidence/wave-01-ux-remediation/browser-before.json) · [Selector and label reproduction](evidence/wave-01-ux-remediation/browser-before-retry.json)

After evidence · [Selector, labels and protected-page checks](evidence/wave-01-ux-remediation/browser-after-initial.json) · [Retirement cancel/confirm](evidence/wave-01-ux-remediation/browser-after-retry.json) · [Fallback and company lifecycle](evidence/wave-01-ux-remediation/browser-after-supplement.json) · [Date validation](evidence/wave-01-ux-remediation/browser-date-boundaries.json) · [Stable responsive confirmation](evidence/wave-01-ux-remediation/browser-dialog-layout.json) · [Cancel witness](evidence/wave-01-ux-remediation/after-cancel-retire.json) · [Confirm witness](evidence/wave-01-ux-remediation/after-confirm-retire.json)

Early browser scripts had selector-event, navigation-timing and assertion-wording failures. Those attempts are retained. The later named runs supersede their affected harness results. PASS in a before-reproduction group means the original defect was observed as expected.

## Remaining concerns and acceptance

- **UX-R-OBS-01.** On Audit, enter the impossible date `1405/13/50` and allow the automatic GET filter refresh. The query retains the invalid value and the server fails closed, but the field redisplays empty. Reproduced at 1024 and 390 px. This behavior lies in the existing shared automatic-filter/date redisplay path. The label-only fix preserves it. Proposed follow-up is to keep the invalid visible value and field error while avoiding an automatic refresh that loses it. [Current evidence](evidence/wave-01-ux-remediation/browser-date-boundaries.json)
- The two company design-reference gaps now point to the current PO-edited implementation. Current checks supersede the earlier missing-reference concern for those pages. Formal visual acceptance remains pending.
- The five login/public-recovery rows retain `NEEDS_PO_REVIEW`. A candidate login HTML design was located at `E:/ERP_Construction_Documents/Main Page/BONIRA_Login_10of10_v7_palette_aligned.html`. No explicit approval record for it or a separate public-recovery design was established. Existing shared form, RTL, feedback and accessibility standards continue to apply. No replacement design was introduced.
- Existing blocked/not-run Wave 01 cases and unrelated Wave 02 findings retain their recorded state. Historical Wave 01 reports and both execution matrices remain byte-identical to their entry fingerprints. Current technical fix/retest states are recorded separately in the defect register. No Product Owner decision or Human sign-off was populated.

## Verification environment and checks

Actual Google Chrome **156.0.8078.80** used synthetic identities in separate contexts, with reference widths **1440, 1024 and 390 CSS px**. Both native and enhanced selection paths were exercised.

Mutable tests used a newly named browser database and a separate technical test database cloned from the retained clean test schema on the verified private PostgreSQL cluster. The settings explicitly pin MVP and isolate media, protected storage, cache, sessions and captured email. No migrations were run. Database/port/data-directory identity was asserted before the harness accessed data.

Private Django and PostgreSQL services were stopped at closeout. Temporary plaintext credentials and raw request logs were removed. The synthetic databases remain in the stopped private test cluster.

**Focused tests · 41 PASS and 51 subtests PASS.** The selection covers company behavior, Platform console/roles, authorization and three focused regression checks. A company-only rerun against the closeout incoming changes passed **16 tests and 36 subtests**. These are overlapping selections. Django system check, changed Python Ruff lint/format, JavaScript syntax and whitespace checks passed. [First selection](evidence/wave-01-ux-remediation/focused-tests.log) · [Closeout company selection](evidence/wave-01-ux-remediation/closeout-company-tests.log)

## Exact authored file changes

| File | Change |
|---|---|
| apps/organizations/role_presentation.py | Opt in the Platform company selector to native-source accessibility suppression. |
| apps/workforce/static/workforce/field_choices.js | Apply suppression after initialization and restore it on destroy for opted-in controls. |
| apps/organizations/platform_console.py | Correct two date labels. |
| apps/organizations/templates/organizations/protected_operation_catalog.html | Add shared retirement confirmation attributes. |
| apps/organizations/test_wave01_ux_remediation.py | Add targeted fallback, date-boundary and retirement/CSRF regression checks. |
| docs/validation/comprehensive-product/APPROVED_DESIGN_CONFORMANCE_REGISTRY.md | Record current PO-edited company references and retained auth gaps. |
| docs/validation/comprehensive-product/DEFECT_REGISTER.md | Append current Wave 01 fix/retest status and remaining observation. |
| docs/validation/comprehensive-product/DEFECT_REGISTER.csv | Update only current fix/retest fields for BON-DEF-0001–0003. |
| docs/validation/comprehensive-product/execution/WAVE_01_UX_REMEDIATION_REPORT.md | This report. |
| docs/validation/comprehensive-product/execution/evidence/wave-01-ux-remediation/ | Run-specific baseline, screenshots, browser, test and state witnesses. |

The pre-existing and incoming company-page changes remain the Product Owner baseline. No company-page template, style, control, destination or section was edited by this remediation.
