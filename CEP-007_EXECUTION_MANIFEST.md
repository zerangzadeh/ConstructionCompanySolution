# CEP-007 Execution Manifest

## Repository grounding (2026-10-14; before product mutation)

- Authorization: Human Decision Authority `AUTH-BATCH-001` authorizes only CEP-007 in development/non-production context. Human sign-off remains outstanding.
- Grounding branch/base: `main` at `0b0cfcdabb93e4e6215d6f2805e763dd82f99cf4` (the prompt's historical design baseline is `d75a9334d8e27683159c5f756725c0540651ec43`). Execution branch: `cep/CEP-007-cash-idempotency`, created from that HEAD after grounding.
- Existing worktree changes: `ROADMAP.md`, `apps/audit/models.py`, `docs/architecture/P4_S14_S20_IMPLEMENTATION_CONTRACT.md`, CEP-005 artifacts, `apps/audit/migrations/0054_cep005_integration_attempt_action.py`, `apps/projects/commitment_integration.py`, `apps/projects/test_cep005_commitment_integration.py`, and `output/cep-005/`. They are unrelated and must be preserved.
- Prerequisite CEPs/external dependencies: none in the authorized prompt. `GATE-01` is an exit gate; no global passage is inferred.
- Repository reality: `TreasuryMovement` already has an immutable `occurrence_id`, a unique `(organization, idempotency_key)` constraint, payload hash, and audit on creation. `create_movement` returns an existing movement for matching key/hash, rejects conflicting content, and currently locks `Organization` plus involved accounts. GL source linkage uses the movement UUID/version and occurrence UUID; posting evidence is immutable. A concurrent duplicate with disjoint accounts can reach the unique constraint without service-level conflict/retry translation. The existing organization lock serializes all tenant movement creations.
- Migration state: the relevant uniqueness and occurrence fields exist in committed migration `apps/treasury/migrations/0001_initial.py`; no schema change is planned. No migration is executed in this package.

## Actual Execution Touch Set

| Surface | Intended disposition |
| --- | --- |
| `apps/treasury/services.py` | Narrow movement-creation locking and race-safe same-key retry/conflict behavior, preserving authorization and active-tenant checks. |
| `apps/treasury/tests.py` or a focused CEP-007 test module | Service, integration, concurrency, and regression evidence for the approved enabler. |
| `ROADMAP.md` | Reconcile only CEP-007 implementation disposition in the existing roadmap. |
| `CEP-007_*` artifacts and `output/cep-007/` | Acceptance, evidence, change, completion, and focused check records. |

No model, migration, permission catalog, UI, production deployment, or other CEP work is in this touch set. If implementation requires such a change, stop and record a finding first.

## Final execution findings and touch set

- Product edits stayed in `apps/treasury/services.py` and `apps/treasury/tests.py`. The existing `(organization, idempotency_key)` database constraint supplies narrow source-key serialization; a nested savepoint translates the losing concurrent insert into exact retry or content conflict. Existing account row locks remain. The movement occurrence UUID is created once and returned unchanged on retry, then remains the GL/posting-evidence identity.
- `Organization` is freshly read and checked active before permission validation, without acquiring a tenant-wide row lock in movement creation. Membership, business permission, object scope and account tenant checks remain in the same atomic service.
- Success audit remains exactly one `TREASURY_MOVEMENT_CREATED` event; rejected conflicting attempts raise `ValidationError` and create no cash movement, leg, posting or success audit. No new audit action/catalog or persistent failure-attempt record was introduced under the no-migration scope.
- Focused PostgreSQL test setup without reuse produced no test result after 90 seconds and was interrupted. An existing migrated test database with `--reuse-db --no-migrations` produced the final passing run. The system `python` alias was unavailable; the repository `.venv` supplied Python and Ruff.
- Actual documentation/evidence touch set: this manifest, CEP-007 acceptance/evidence/change/completion artifacts, `output/cep-007/` test/lint/format output, and one CEP-007 status entry in `ROADMAP.md`. No other product surface was changed by this CEP. Existing CEP-005 and other worktree changes are preserved.
- Gate state: `GATE-01` remains a global exit gate pending other required IMBs per `ROADMAP.md`; this bounded package does not claim global gate passage or Human Sign-off.
