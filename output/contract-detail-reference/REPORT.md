# Contract Detail reference implementation — 2026-11-01

Bounded Human authority: the current user request for a visual implementation of Contract Detail, preserving existing behavior, scope, permissions, workflow and financial authority. This is not serial CEP execution or production enablement.

Branch: `main`. Start HEAD / observed `origin/main`: `5b760e853b329e2b03415da7b046641359db6a62`. The initial dirty tree is recorded in `initial-status.txt`, `initial-diff.txt`, and `initial-stat.txt`. Existing work, including Contracts List and Project Command Center changes, was preserved. No branch/worktree, staging, commit, push, merge, deployment or production operation.

## Touch set

- `apps/contracts/views.py`: only Contract Detail composition; existing scoped querysets and permission decisions retained. Other pre-existing edits in this file belong to prior work.
- `apps/contracts/detail_dashboard.py`: read-only presentation aggregates, exact Decimal values, bounded recent rows.
- `templates/contracts/detail.html`, `templates/contracts/detail_icon.html`: header, one-row context, five KPIs, two visualization areas, journey navigation, information, latest claims and record-backed events. Existing insurance forms, items, estimates and baseline links retained.
- `apps/contracts/static/contracts/detail.css`, `detail.js`: opt-in responsive presentation and existing Chart.js asset reuse.
- `apps/contracts/test_detail_dashboard.py`, `scripts/verification/contract_detail_validate.py`: isolated functional and installed-Chrome checks.
- This evidence directory only. No models, migrations, permission catalogs, domain services, workflow, exposure authority or financial transaction behavior changed.

## Data contract

- Effective amount = original contract value + approved tenant-owned amendments. This mirrors the existing billing ceiling arithmetic; this dashboard does not change an approved baseline or authorize a claim.
- Amounts are gross period amounts. Issued = approved + submitted ordinary claims. Draft, returned, superseded and cancelled rows are excluded. Pending and remaining are clearly distinguished from approved; no cash/payment/receivable balance is asserted.
- Financial ratio = approved gross / current effective amount, only for comparable currency and nonnegative amounts within a positive effective amount. Monetary arithmetic is server-side Decimal; JSON retains exact strings, chart geometry alone uses JS numbers. Text and tooltips retain exact amounts.
- Canonical OrganizationSettings supplies currency. Missing settings, incompatible currencies, active corrective records or noncomparable amounts suppress the affected aggregate/chart. No legacy currency fallback.
- Physical progress remains unavailable: the current implementation has no authoritative contract-wide physical percentage. No duration in months, project image, guarantee or missing action was invented.
- Existing authenticated tenant/project-scoped read selectors supply claims/baselines/estimates. Product-surface checks only preserve exposure. Payable contracts receive no receivable Claim/Baseline links.
- Recent events use actual created/submitted/approved/returned timestamps of accessible claim revisions, plus contract creation. They do not read privileged audit logs or infer events from current status.
- Exact visible legend and accessible data table remain available with JavaScript disabled.

## Environment and infrastructure attribution

Configured development database: PostgreSQL; one pre-existing unapplied migration was observed (`payroll.0010_cep069_reviewed_statutory_context`). No development migration was applied by this task.

The first shared-test-database attempt failed before page validation with `accounts_user_username_key` / `f61-owner` duplicate fixture data. A fresh dedicated DB was then prepared, but its full historical migration preparation was interrupted due to excessive runtime. A separate empty, previously migrated test DB (`test_bonira_mvp03_20261029`, 446 applied migration records, zero users, no active sessions) was copied to `test_bonira_contract_detail_ref_20261101`. The source was read-only; all fixtures and browser traffic target the separate copy. The reusable verification script selects only that test DB. Browser fixtures are explicit synthetic data, including large amounts and fractional minor units, never program seed data. The test organization is labelled “داده آزمون”.

## Validation

- Original combined run: 26 passed, 1 failed, 2 subtests passed. The sole failure was a new assertion checking the whole HTML for receivable links; it incorrectly included the existing shared sidebar. The assertion was corrected to inspect only Contract Detail. Existing regression: **20/20 PASS** (`apps/billing/test_mvp03.py`, `apps/contracts/test_review_navigation.py`). See `final-tests.txt`.
- Focused final run: **6/6 functional tests PASS**. The browser in that run caught a real 8px mobile overflow introduced by the accessible chart data table; its positioning was corrected within the financial card. See `final-detail-tests.txt` and the retained `*-overflow-diagnostic.*` historical artifacts.
- Final installed Chrome rerun: **PASS** (`final-browser-tests.txt`, exit 0): 9/9 scenarios. Rich receivable, little-data receivable, payable and restricted-permission user at 1440px / 390px, plus rich-data JavaScript-disabled fallback. Final screenshot and result JSON files replace earlier captures. No JS exceptions or page HTTP errors; no document horizontal overflow. The shared favicon 404 is excluded by the existing browser harness.
- Decimal amounts, gross/net distinction, ordinary claim status exclusions, incompatible currencies, correction fallback, missing canonical currency, zero denominator, restricted records/events/links, cross-tenant denial and payable journey exclusions covered.
- Django system check: PASS. Ruff check and format check: PASS for new Python files. JS syntax: PASS. Scoped Git whitespace check: PASS. Full unrelated suite not run.

## Direct reference comparison

Reference and final desktop/mobile captures were visually inspected. Final page follows the reference sequence: compact title/status/actions, one-row key context on desktop, one five-KPI strip, physical/financial comparison on the right and financial composition on the left, journey navigation, then information / recent claims / activity cards. The initial chart area was too tall; it was reduced so all three lower cards and their footers fit the 900px desktop capture.

| Area | Result |
| --- | --- |
| Header, one-row desktop context, five KPI placement | Implemented; narrower shared content width changes exact proportions |
| Two visualization areas | Correct placement; financial chart uses scoped real values; physical progress intentionally unavailable |
| Journey | Existing routes and local sections; payable excludes receivable Claim/Baseline paths |
| Information, recent claims table, recent events | Three-column desktop / stacked mobile; exact source data and permissions |
| Empty and restricted states | Explicit unavailable messages; no invented numbers or permission-derived records |
| Remaining visual differences | Existing shared shell is wider and its exposed navigation differs from the reference; the financial legend is denser/smaller; no verified project photograph or physical percentage; unavailable Edit/Print, guarantees and other absent capabilities are not fabricated |

The shared shell and its navigation were kept to preserve the existing product surface and other in-progress work. The implementation is materially closer to the supplied reference, but the residual proportions and visual details do not justify a full reference conformance PASS. No Product Owner acceptance is inferred.

- [Rich desktop](browser/f61-owner-rich-1440.png)
- [Rich mobile](browser/f61-owner-rich-390.png)
- [Little-data desktop](browser/f61-owner-little-1440.png)
- [Little-data mobile](browser/f61-owner-little-390.png)
- [Payable desktop](browser/f61-owner-payable-1440.png)
- [Payable mobile](browser/f61-owner-payable-390.png)
- [Restricted desktop](browser/contract-reader-restricted-1440.png)
- [Restricted mobile](browser/contract-reader-restricted-390.png)
- [No JavaScript](browser/f61-owner-rich-no-js.png)

CONTRACT DETAIL FUNCTIONAL: PASS
CONTRACT DETAIL BROWSER: PASS
CHART DATA INTEGRITY: PASS
REFERENCE VISUAL CONFORMANCE: FAIL

PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

Reference SHA-256: `cd9558e056f5cec7801f3a92628b0aa0bec56529896fc7e1c75d263cc4c85191`
