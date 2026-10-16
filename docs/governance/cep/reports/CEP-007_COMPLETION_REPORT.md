# CEP-007 Completion Report — 2026-10-14

## Final execution verdict: CLOSED — VERIFIED

| Checkpoint | Result |
| --- | --- |
| CEP / Primary IMB | CEP-007 / IMB-0052 only |
| Authorization | AUTH-BATCH-001 bounded development/non-production execution |
| Repository baseline | `main @ 0b0cfcdabb93e4e6215d6f2805e763dd82f99cf4`; execution branch `cep/CEP-007-cash-idempotency` |
| Changed components | Treasury movement creation service and focused tests; CEP-007 artifacts/output and ROADMAP disposition |
| Migrations / data changes | None; existing tenant/key uniqueness and occurrence UUID used; no migration execution or backfill |
| Acceptance Criteria | AC-1 through AC-5 PASS; see `CEP-007_ACCEPTANCE_MAPPING.csv` |
| Canonical DoD | PASS within the authorized enabler: stable occurrence on retries; no duplicate cash movement; narrow account/key serialization; exact conflict; existing authorization/source scope and success audit retained; dependent tests may consume the service |
| Required checks | 2 focused PostgreSQL tests PASS; Ruff check PASS; focused format check PASS; whitespace check PASS |
| Evidence IDs | CEP-007-EV-001 through CEP-007-EV-006 |
| Findings / blockers | None unresolved. No repository contradiction requiring scope expansion was found. |
| Remaining UTV | Performance/concurrency certification at operational load; no browser/accessibility or production certification is applicable to this package. |
| Downstream readiness | Treasury movement creation enabler verified for separately authorized dependent work; no dependent business capability or producer activation is claimed. |
| GATE-01 / Human Sign-off | Global exit gate pending other required IMBs; NOT EVALUATED/PASSED by this package. Human Sign-off NOT EXECUTED. |
| Git commit / push / merge | NOT EXECUTED; unrelated pre-existing worktree changes remain for Product Owner review alongside this CEP's unstaged changes. |
| Final lifecycle status | Bounded CEP-007 implementation VERIFIED; production activation and Go-Live not authorized. |

The service keeps its transaction boundary and existing account row locks. It reads current tenant status without locking the entire organization, validates membership, business permission, object scope and account ownership, then uses the existing tenant/key unique constraint as the final concurrent arbiter. A losing insert rolls back to a savepoint; matching payload returns the original movement and occurrence UUID, while changed payload raises a validation error. The winning transaction creates the leg and exactly one success audit event. Posting retains the occurrence UUID in its journal and immutable posting evidence.

The final command was `.venv\Scripts\python.exe -m pytest apps/treasury/tests.py::TreasuryOccurrenceIdempotencyTests::test_parallel_same_source_key_has_one_cash_occurrence_and_audit apps/treasury/tests.py::TreasuryFoundationTests::test_direct_receipt_posts_once_with_exact_evidence_and_reconciles -q --reuse-db --no-migrations --disable-warnings --maxfail=1`: **2 passed in 21.23s** (`output/cep-007/test-output.txt`). Ruff check on both touched Python files, format check on the changed test file, and `git diff --check` passed. The service file has an unrelated pre-existing Ruff-format suggestion at line 1487; whole-file format was intentionally not applied. Initial system `python` invocation could not start; a fresh-database test setup was interrupted after more than 90 seconds without a result. Neither is treated as a package test failure or passing evidence.

No new UI, schema, permission, producer, posting policy, audit action, production operation, other CEP, or Human Sign-off was implemented. Conflicting requests surface a `ValidationError`; they leave no partial movement or false success audit. Existing created-movement audit and source-to-GL linkage supply the package audit evidence. Operational-load performance remains UTV until a separately applicable runtime verification.
