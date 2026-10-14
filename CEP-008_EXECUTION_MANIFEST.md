# CEP-008 Execution Manifest

## Historical and authorization state

- Historical attempt: `EXECUTION FAILED / BLOCKED BEFORE MUTATION` (preserved).
- Authorization: `BOUNDED HUMAN AUTHORIZATION CONFIRMED`.
- `CEP-008-FINDING-001`: `RESOLVED` by canonical source recovery.
- Environment: Development / non-production only.

## Repository grounding — 2026-10-15

- Branch: `cep/CEP-008-accounting-recognition-owner`
- Baseline HEAD: `821f6cc92c9ed198bd049b3e40904946bb3438d5`
- Isolated worktree: `E:\Construction_Company_Solution-CEP-008`
- Baseline attribution: `origin/main` is an ancestor of the baseline; the prior
  CEP-008 recovery-only `ROADMAP.md` edit remains in its original worktree and
  was not copied or overwritten.
- Baseline working tree: clean.

## Canonical identity

- Prompt SHA-256: `7246bfd8f8b9d0286e0fcfcf57946f01ea3938598a8a58565473e32f8d932eeb`
  (verified).
- PD-030: `FOUND / FROZEN`.
- IMB-0055: `FOUND / CANONICAL`; six acceptance criteria and the canonical DoD
  recovered.
- SPEC-002: `FOUND / COMPLETE / AUTHORITATIVE`.
- Recognition Owner Matrix: 18 authoritative rows verified.

## Actual execution touch set

| Surface | Change | Migration impact |
| --- | --- | --- |
| `apps/accounting/recognition_registry.py` | New code-owned, static 18-row policy resolver; canonical identity, source/tenant/scope validation, replay classification, competing-owner rejection, and audit/reconciliation metadata. | None |
| `apps/accounting/test_cep008_recognition_registry.py` | Focused domain, negative-path, identity, replay, conflict, tenant/scope and reconciliation-linkage tests. | None |
| CEP-008 evidence files and `ROADMAP.md` | Execution evidence and current roadmap reconciliation. | None |

No models, migrations, journal writer, posting contract, source-domain integration,
configuration, business data, permission catalog, or downstream CEP surface is
changed.

## Regression closure — 2026-10-15

`CEP-008-FINDING-002 / BLOCKER-REGRESSION-EXECUTION`: `RESOLVED`.

- `pytest apps/accounting --collect-only -q` collected 60 tests in 0.17 seconds;
  collection is not the bottleneck.
- The four selected database-backed journal-service tests reached test-database
  schema setup, not their test bodies. Schema creation failed on the existing
  `accounting_fiscalyear` UUID GiST exclusion constraint because the test
  PostgreSQL environment has no default UUID GiST operator class. This is
  classified as `BASELINE / OUT-OF-SCOPE TEST DEBT`; CEP-008 did not change the
  affected model, migration, journal service, or posting contract.
  - `AccountingFoundationTests::test_post_is_idempotent_and_source_key_conflict_is_rejected`
  - `AccountingFoundationTests::test_submission_fails_closed_without_precision_and_rounding_values`
  - `AccountingFoundationTests::test_reversal_is_balanced_linked_immutable_and_idempotent`
  - `AccountingFoundationTests::test_retained_correction_chain_ties_reversal_and_replacement`
- The bounded representative command
  `python -m pytest -q apps/accounting/tests.py::AccountingPolicyCalculationTests apps/accounting/test_cep008_recognition_registry.py`
  passed (10 tests, 28 subtests). Four existing `posting_registry` contracts also
  resolved successfully.

No CEP-008 regression was found. Scoped DoD is `PASS`; CEP-008 execution is
`EXECUTION COMPLETE`. This closure does not evaluate GATE-01.
