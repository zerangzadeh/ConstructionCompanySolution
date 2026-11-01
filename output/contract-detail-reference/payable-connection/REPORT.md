# Contract Detail — payable source connection, 2026-11-01

The user reported that the existing seeded payable subcontract did not show its certificates. Root cause: Contract Detail queried only receivable ProgressClaim rows. PayableCertificate records existed and were visible in their own pages, but were absent from dashboard composition.

## Change and boundary

- Contract Detail now loads payable subcontract certificates through the existing `get_payable_certificates` selector, only with its registered `PAYABLE_CERTIFICATES_VIEW` permission. The selector's organization-scope gate is preserved; contract readability does not grant certificate access. Project-only readers denied by that selector receive an unavailable section without certificate data, links or events; the rest of their permitted contract page still renders.
- A presentation adapter selects either receivable claims or payable certificates, with the source-specific number, detail route, status label and list route. Every source is additionally constrained to the authenticated organization and resolved contract/project.
- Recent rows, existing gross-amount KPI arithmetic, financial composition, approved financial ratio and record-backed events now consume the correct payable source. No receivable Claim/Baseline path is shown for payable contracts.
- The payable journey targets its on-page contract records. The existing unfiltered certificate-list footer is labelled “فهرست گواهی‌های پرداخت”; it does not pretend to filter that list to this contract. Receivable list context is retained.
- Physical progress remains unavailable: no governed contract-wide physical rollup is invented from measurements.

Product touch set: `apps/contracts/views.py` (Contract Detail only plus ContractType import), `apps/contracts/detail_dashboard.py`, `templates/contracts/detail.html`. Test touch set: updated one presentation-key assertion in `apps/contracts/test_detail_dashboard.py`, plus new `apps/contracts/test_payable_detail_dashboard.py`. Evidence and read-only live probe are confined to this directory. `task-diff.patch` compares the three product files with the captured pre-task versions; unrelated in-progress Contract Create, list and Project work is preserved.

No models, migrations, domain services, permission definitions/grants, workflow rules, product exposure, seed records, accounting recognition, posting, payment or financial authority changed. Git remains on main at `5b760e853b329e2b03415da7b046641359db6a62`; no add/commit/push/merge/worktree.

## Validation

- Existing tests/regression and original Chrome matrix: 27 PASS, 2 subtests PASS, in `tests.txt`. Five new tests initially failed during setup before reaching the changed view because their explicit synthetic approver lacked workflow claim/act and certificate-view permissions. Only that isolated fixture role was completed; production roles were untouched.
- Final payable suite: 5/5 PASS, in `final-payable-tests.txt`: exact independent source amounts, record links and events, receivable/payable permission separation, existing selector scope enforcement, and fail-closed currency/correction cases. Includes 4 installed-Chrome scenarios (rich and restricted payable at 1440/390).
- Original browser matrix: 9 installed-Chrome scenarios retained through the regression run, including receivable rich/little, payable empty, restricted and no-JavaScript fallback.
- Real local development contract `UAT-SUB-02-03`: individual Chrome assertions and screenshots PASS at 1440 and 390; 3 payable rows, exact approved/pending/remaining amounts 8,910,000,000 / 4,455,000,000 / 16,335,000,000 IRR and financial ratio 30%. Detail links all target payable certificates; no receivable paths. No page JS/HTTP errors or document horizontal overflow. An initial aggregate live assertion failed; its detailed replay and final captures passed all conditions. See `live-verification.json` and `live-browser/`.
- Live contract, certificate and measurement fingerprints match before/after read-only verification. Session/login metadata used for the probe is outside these business records.
- Ruff check/format on affected helper/tests: PASS. Django check: PASS. Scoped Git whitespace check: PASS. No unrelated full suite rerun.

## Current live result

- [Desktop](live-browser/seed-owner-live-payable-1440.png)
- [Mobile](live-browser/seed-owner-live-payable-390.png)

The seeded contract now displays all three payable certificates and its source-derived financial summary. This closes the source-connection limitation recorded in the earlier seed report. It does not claim full conformance to the original visual reference or Product Owner acceptance.

CONTRACT DETAIL FUNCTIONAL: PASS
CONTRACT DETAIL BROWSER: PASS
CHART DATA INTEGRITY: PASS
REFERENCE VISUAL CONFORMANCE: FAIL (prior broader visual differences remain outside this focused fix)
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING
