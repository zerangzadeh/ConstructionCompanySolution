# CEP-021 Execution Manifest

## Grounding and authority — 2026-10-17

- Branch and baseline: `main` at `76362e23fbbd18c5f280343ece064e95eeae4881`; `origin/main` matches the Registry reconciliation baseline.
- Standing authority: active for eligible current-governed non-production CEPs. The prompt's generic authorization language is superseded only by current governance; package-specific source, financial-boundary and migration constraints remain authoritative.
- Canonical prompt: SHA-256 `d724e1fdd5e691087f7d04de27b60a69e14e9ef0936bbf78fbeb6e921b1dda45`, matching `CEP_PROMPT_MANIFEST.yaml`.
- Prerequisites: none. `GATE-01` and `GATE-02` are PASS. CEP-021 does not depend on blocked CEP-015 or CEP-020 and does not use configuration-profile behavior.
- Migration impact: `NONE`.

## Repository grounding

The available `apps.accounting.recognition_registry` is the frozen SPEC-002 recognition-owner policy set. It defines Direct Expense and Employee Reimbursement as Expenses-owned, states `NO generic AP`, identifies Treasury as settlement owner, requires exact source identity/version, and fails closed for unknown policy rows. Existing `Expense` records preserve a UUID and direct/indirect classification but have no reimbursement beneficiary, source-version field, or durable link to a Treasury payment request. Existing `PaymentRequest` preserves only generic purpose and idempotency data; it has no expense identity or version relationship.

The existing deterministic idempotency controls cannot supply a durable source relation, version/correction lineage, or distinguish an employee reimbursement from a direct expense without unsupported encoding in generic text or keys. That would not meet the authoritative-persistence and no-double-count obligations.

## Actual execution touch set before product mutation

Product touch set: **NONE**. Completing the source boundary would require a governed durable reimbursement identity and expense-to-Treasury request relationship/versioning. This is schema and migration work, but CEP-021 explicitly sets Migration Impact to `NONE`; no source authorizes an implicit schema expansion or a text/idempotency convention as a replacement.

Governance/evidence touch set: this manifest, CEP-021 acceptance/evidence/change manifests, completion report, and `CEP_EXECUTION_REGISTRY.yaml`.

## CEP-021-FINDING-001 — BLOCKER-REPOSITORY-MIGRATION

The approved recognition policy is present, but repository reality lacks the durable data structures necessary to satisfy CEP-021 AC-1 through AC-5 and its DoD. `Expense` cannot identify an employee reimbursement or preserve an Expense version, and `PaymentRequest` cannot identify/link an Expense occurrence/version. A controlled request and correction/history no-double-count proof would otherwise depend on invented semantics.

Resolution requires a separately governed decision that either supplies an approved no-migration durable contract already owned by the relevant domains, or explicitly authorizes a bounded schema/migration contract defining reimbursement beneficiary, expense source/version identity, Expense↔Treasury request lineage, correction/reversal behavior, and associated transaction guarantees. Re-ground CEP-021 after that authority is present.

Final lifecycle: **BLOCKED BEFORE PRODUCT MUTATION**. No schema, migration, product code, test, production, Human Sign-off, or Git-write action was executed.

## 2026-10-17 Human decision and resumed execution

The Human Decision Authority approved `BONIRA-CONSOLIDATED-20261017`, which
acknowledges the frozen Expense/Treasury boundary and grants a bounded
non-production migration exception to the prompt's `Migration Impact = NONE`.
The prior blocked finding remains historical. At `main`
`fb6a1feaa78168748741c3c3253e2dea0871cda8`, `origin/main` matches; the
working tree contains unrelated CEP-027/028 records and CEP-028 preparation that
must be preserved. The canonical prompt SHA-256 remains
`d724e1fdd5e691087f7d04de27b60a69e14e9ef0936bbf78fbeb6e921b1dda45`.
There are no CEP prerequisites, and GATE-01/GATE-02 are PASS.

Intended bounded touch set: `apps/expenses` source identity, reimbursement
beneficiary, correction lineage and settlement request service; `apps/treasury`
request-kind/source-link validation and existing release lifecycle; expand-only
`expenses`/`treasury` migrations; focused domain and negative-path tests; this
CEP's evidence, mapping, change manifest and Completion Report. The existing
Accounting recognition registry, AP route, Treasury posting producer and
CEP-028 legacy migration preparation remain outside the touch set.

## Resumed implementation and migration finding

`CEP-021-FINDING-001` is resolved by the cited Human authorization for a
bounded non-production expand-only schema. The implementation adds nullable
reimbursement/source links, Expense source version and replacement lineage,
and a Treasury request-to-movement link. Existing rows retain their values;
no legacy reimbursement backfill, destructive contract, production migration,
or accounting/AP posting is part of this package. Generated migrations are
`expenses.0009` and `treasury.0009`. The latter depends on the former and
replaces only the payment-request beneficiary check to include the governed
reimbursement kind. Source and request links have one-to-one database
uniqueness, with service/model tenant, state, amount, version, beneficiary,
and project checks. The PostgreSQL test database applied, reversed, and
reapplied both migrations; a legacy Expense and PaymentRequest retained UUIDs,
amounts, party and row counts. Twenty-five focused Expense/Treasury/migration
tests, Django system check, migration drift
check, and touched source/test lint passed. The development database migration
plan contains existing `documents.0011` and `workforce.0010` prerequisites;
no development or production migration was executed. AC 6/6 and DoD PASS;
remaining runtime verification and deployment are UTV. Execution closed at a
clean non-production boundary with no Git write.
