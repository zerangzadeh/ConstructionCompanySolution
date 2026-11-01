# Contract Detail — authorized empty states show zero, 2026-11-01

The user explicitly requested 0 Rial and 0 percentages instead of unavailable values when a contract has no statements. This is a presentation change; no financial source records, lifecycle, permission, workflow, schema or product exposure changes.

## Behavior

- Authorized statement querysets with no ordinary approved/submitted records now produce exact Decimal zero approved, pending and issued amounts, with financial progress 0%. Draft and returned records remain excluded as before.
- The existing effective contract value is retained. Remaining = effective minus issued, so an unbilled contract retains its actual full remaining amount; it is not falsely set to zero. A positive fully-unbilled contract has 0% approved, 0% pending and 100% remaining composition.
- For a zero-value empty contract, the explicit empty-state percentage is zero; no division by zero occurs. This is a UI empty-state rule, not a claim that the 0/0 ratio is mathematically defined.
- Physical progress shows 0% only when the existing, independently authorized, tenant/project/contract-scoped measurement selector proves there are no records. That state is labelled “اندازه‌گیری پیشرفت ثبت نشده”. Existing measurements without a governed contract-wide rollup still remain unavailable; no physical percentage is inferred from missing claims.
- Missing source permission/scope, unsupported source, missing authoritative currency, incompatible currency/corrections and noncomparable amounts retain fail-closed unavailable values. Unknown/access-denied is not converted to zero.

## Touch set and preservation

Product files: `apps/contracts/detail_dashboard.py`, Contract Detail only in `apps/contracts/views.py`, and `templates/contracts/detail.html`. Existing affected tests were adjusted and a focused empty receivable/payable plus denied-source test was added in `apps/contracts/test_detail_dashboard.py`. No changes to models, migrations, domain services, permission catalogs/grants, workflow, JavaScript/CSS, seed records or financial authority. `task-diff.patch` compares against the saved task-start versions; unrelated working-tree changes are preserved. Branch main, HEAD/origin-main observed `5b760e853b329e2b03415da7b046641359db6a62`. No staging, commit, push, merge or deployment.

## Validation

- Dedicated existing isolated PostgreSQL test DB: **13 tests + 2 subtests PASS**, covering rich/empty receivable/payable, existing measurement versus no measurement, denied source/measurement permissions, zero value, exact amounts, mixed/corrective fallback and retained source links. Includes the previous 9-scenario Chrome matrix and 4 payable rich/restricted Chrome scenarios.
- Actual development contract CTR-02-02-04: installed Chrome PASS at 1440px and 390px. Approved and issued amounts are 0 Rial; financial and physical progress are 0%; effective and remaining amounts both remain 54,800,000,000 Rial. Empty statement table still explains that no statement is registered.
- No JS/page HTTP errors or horizontal overflow. Captures visually inspected.
- Read-only live probe business fingerprints match before/after (contract, certificates, measurements); no business records modified.
- Ruff check and format check: PASS. Django system check: PASS. Scoped whitespace check: PASS.

Evidence: `tests.txt`, `live-verification.json`, `live-browser/seed-owner-empty-zero-1440.png`, `live-browser/seed-owner-empty-zero-390.png`.

This focused empty-state fix does not claim full conformance to the original visual reference or Product Owner acceptance.
