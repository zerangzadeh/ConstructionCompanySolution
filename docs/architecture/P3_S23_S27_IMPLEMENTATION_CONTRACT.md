# P3-S23–S27 AP/AR Implementation Contract

**Status:** accepted implementation contract — authorized by the Product Owner on
2026-10-01. This contract is the application-change boundary for P3-S23–S27.

## 1. Scope and session allocation

| Session | Authorized outcome |
| --- | --- |
| P3-S23 | Expand-only Tenant AP/AR obligation, permission and audit foundation. |
| P3-S24 | Exact source registration and immutable obligation recognition boundary. |
| P3-S25 | Treasury-linked settlement allocation, cap enforcement and reversal. |
| P3-S26 | Exact as-of aging and retained AP/AR-to-GL reconciliation evidence. |
| P3-S27 | Controlled write-off/reversal gate, focused PostgreSQL acceptance and closeout. |

Legacy `Payment` cutover/backfill, production activation, UI, background
processing, external integrations, P3-S28+, and `MATERIAL_DOCUMENTS_LINK` are out
of scope. No recognition rule, posting mapping, aging bucket, tolerance,
threshold, write-off authority, numeric limit, currency, or financial policy is
introduced by this package.

## 2. Ownership, lifecycle, and exact lineage

The `subledgers` app owns AP/AR obligations, open amounts, settlement allocations,
write-off evidence, aging snapshots and AP/AR reconciliation evidence. Source
domains continue to own commercial facts, Treasury owns cash movements and
Accounting owns journals. None of those records is relabelled as another
authority.

An obligation is immutable recognized evidence with direction `receivable` or
`payable`, exact source kind/UUID/version/line identity, a canonical source hash,
source status and date snapshots, party/tax-identity snapshot, optional exact
project/contract scope, IRR currency, original amount, recognition date and an
optional source-supplied due date. Its computed collection/payment state is
`open`, `partial`, or `settled`; correction never rewrites the obligation.

Source eligibility is closed and code-registered. Registration must validate the
live locked source, Tenant, direction, final source version/status, amount,
currency, party and object scope and return the complete canonical snapshot.
Retries reuse the same source identity only when the payload hash is identical.
No source producer was registered in this tranche. Subsequent authorized
P6-S07–S13 work added the complete approved-claim snapshot and explicit AR source
resolver; recognition remains an explicit permissioned call and no AP source or
automatic producer exists.

Settlement allocation is immutable evidence linking one obligation to one exact
posted, unreversed Treasury receipt for AR or disbursement for AP. Reversal is a
linked append-only record; it reopens both obligation and movement capacity and
never changes cash. A write-off is likewise a distinct adjustment occurrence,
not cash, settlement or journal, and its reversal is linked append-only evidence.

## 3. Tenant, object scope, permissions, audit, and SoD

Every read/service boundary requires an active membership in the same active
Tenant plus the dedicated permission. Project/site scope can only restrict an
obligation whose exact source carries that scope; it never grants Tenant-wide
financial access. Every related party, project, contract, Treasury movement,
Accounting journal and source identity must share the Tenant and, when present,
the same project/contract context.

Dedicated permissions cover AP/AR view, obligation recognition, settlement
allocation, settlement reversal, aging, reconciliation, write-off proposal,
write-off approval and write-off reversal. Recognition and settlement permissions
are default-granted only through the existing finance-restricted role pattern.
Write-off approval/reversal permissions are catalogued but receive no operational
default grant until the Product Owner selects write-off authority.

Create, recognize, allocate, reverse, write off, reverse write-off, aging and
reconciliation events record actor, membership, time, reason, source identifiers,
old/new effect and idempotency identity through append-only domain evidence and
the shared audit service. Role names, positions, ownership and UI visibility are
never authority.

Write-off approval is always fail-closed until an explicit authority contract is
approved. That contract must identify default-role grants (if any), whether the
existing platform Self-Approval policy is extended to AP/AR or independent
checker is mandatory, and whether any amount/scope threshold exists. No threshold
or implied Owner/Admin bypass is supplied here. Reversal remains independently
permissioned and cannot erase the original.

## 4. Lock order, concurrency, and idempotency

Mutating services use one transaction and lock in this order:

1. Organization financial coordination row;
2. active maker/checker memberships in primary-key order;
3. source record or exact source-registration coordination row;
4. obligation;
5. Treasury movement;
6. active settlement/write-off rows in primary-key order;
7. Accounting fiscal period/journal only inside a separately registered producer.

The service rechecks Tenant, permission, scope, lifecycle, source eligibility,
capacity and SoD after locking. Organization-scoped idempotency keys plus canonical
payload hashes return the existing result for the same request and reject a
conflicting retry. Database uniqueness and locked aggregate sums prevent duplicate
recognition, lost updates and concurrent over-allocation.

## 5. Amount, allocation, Treasury, and Accounting boundaries

Amounts are positive `Decimal` values using the already accepted IRR precision
and rounding policy; missing or incompatible effective configuration fails
closed. Active settlements plus active write-offs may not exceed the obligation
amount. Active allocations against a Treasury movement may not exceed its exact
posted amount. Partial allocation is permitted because no minimum/full-settlement
policy is required; over-allocation is prohibited with no tolerance.

An AR allocation accepts only an exact posted, unreversed Treasury receipt; AP
accepts only an exact posted, unreversed disbursement. Transfers, drafts,
submitted/approved-but-unposted movements, reversals and incompatible party or
project context are ineligible. Reversing the linked Treasury movement is blocked
while active AP/AR settlements exist; the settlement must be reversed first.

This tranche does not register an Accounting producer or select recognition,
settlement, write-off, clearing or control-account mappings. Obligation,
allocation and write-off services retain optional exact journal identities only
when a future code-registered synchronous producer supplies them atomically.
Absent registration, any operation requiring a journal fails closed; AP/AR never
creates or edits a journal directly.

## 6. Aging and as-of semantics

Aging is an exact retained projection, not a mutable balance. `as_of_date`
includes obligations recognized on or before that date and subtracts only active
allocations/write-offs whose effective date is on or before it. Later reversals
restore the amount from their effective reversal date; they do not rewrite an
earlier as-of result. Future-dated facts are excluded.

The snapshot records Tenant, direction, as-of date, obligation IDs, exact per-item
original/settled/written-off/outstanding amounts, due date, days past due when a
source supplied the date, undated status, totals, canonical hash and idempotency
key. It does not invent buckets. Any bucketed presentation remains blocked until
the Product Owner approves exact boundaries.

## 7. Correction, reversal, and reconciliation

Recognized obligations are not silently edited, voided or deleted. A source
correction requires a separately registered source-correction contract that
creates linked adjustment/reversal evidence and, when applicable, a linked
Accounting reversal. Settlement reversal and write-off reversal require a reason,
authorized actor, unique occurrence and an open applicable fiscal boundary if a
journal is involved. A cash refund is a separate Treasury movement.

AP/AR reconciliation retains exact as-of population, active allocation/write-off
IDs, source and journal identities, subledger totals, supplied posted GL control
totals, differences, exception facts and a canonical hash. It never posts,
adjusts, signs off or applies a tolerance. Missing mappings/journals are explicit
exceptions rather than fabricated balances.

## 8. Migration, rollback, and acceptance

Migrations are expand-only: create the `subledgers` schema and add permission/audit
catalogue entries. They do not backfill or reinterpret `Payment`,
`PaymentAllocation`, `ClaimSettlementAllocation`, claims, Treasury movements or
Accounting journals. Before activation, rollback may remove only the unused new
schema. After authoritative facts exist, recovery is forward-only; no financial
evidence is deleted or silently returned to legacy authority.

Focused PostgreSQL acceptance must cover Tenant/scope/permission denial, closed
source registration, idempotency conflicts, concurrent recognition/allocation
caps, partial and over-allocation, direction and posted/reversal eligibility,
as-of/reversal semantics, no invented aging buckets, write-off fail-closed
authority, immutable reversal evidence, and subledger/Treasury/GL reconciliation
without Accounting mutation. Retained Treasury/Accounting regressions,
migration rollback/reapply and drift checks, Ruff and Django checks remain
mandatory.

## 9. Product Owner activation decisions

| ID | Accepted decision (2026-10-01) | Runtime effect until separately authorized and implemented |
| --- | --- | --- |
| P3-S27-Q01 | **A:** stage AR from an approved immutable `ProgressClaim` revision only after its explicit immutable due-date, party/tax/currency snapshot and linked post-approval correction facts exist; recognize on the Tenant-local date of `approved_at`; reverse dependent evidence and original recognition before replacement. No AP source is eligible yet. | P6-S07–S13 registers the exact AR source adapter for explicit recognition. Automatic recognition remains absent; correction fails closed after recognition until reversal/replacement orchestration is authorized. |
| P3-S27-Q02 | **A, clarified:** use explicit directional subledger event kinds and versioned source-specific mappings. AR settlement uses the exact Treasury-created unapplied-receipt/settlement-clearing role, never cash/bank; AP uses equivalent outgoing-clearing semantics. Subledgers never select or mutate cash postings. | No AP/AR Accounting producer is registered; journal-required actions remain fail-closed. |
| P3-S27-Q03 | **A-Revised:** proposal retains its Accountant default; approval/reversal have no default grant and require explicit scoped assignment. Existing Platform/Tenant Self-Approval policy governs; independent memberships are required where that policy says so. Absolute prohibition applies only to explicitly classified Protected Operations; write-off/reversal are not implicitly classified. No threshold is introduced. Missing policy/authority fails closed; decisions retain versioned audit and exact lineage. | Write-off approval and reversal remain disabled pending separately authorized implementation; no threshold or Protected-Operation classification is inferred. |
| P3-S27-Q04 | **A:** retain exact unbucketed as-of aging; no bucket boundaries are authorized. | Exact aging remains available; bucketed aging remains absent. |

These choices close Q01–Q04 only as Product Owner decisions. They do not authorize
their implementation, production activation, legacy cutover/backfill, UI,
external integration, background processing or P3-S28+.
