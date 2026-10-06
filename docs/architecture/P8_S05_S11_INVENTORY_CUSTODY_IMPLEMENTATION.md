# P8-S05–S11 Inventory Quantity and Custody Implementation

**Recorded:** 2026-10-04  
**Status:** Product Owner accepted on 2026-10-04 within the authorized
non-production boundary  
**Authority:** the Product Owner accepted P8-S01–S04, selected P8-D01–D06 = A,
and authorized only section 10 of
`P8_S01_S04_ENTRY_AND_ARCHITECTURE_DECISION_PACKET.md`.

## 1. Delivered boundary

P8-S05–S11 adds Inventory-owned quantity and custody controls only:

- posted-quantity availability, project reservations, allocations, partial
  fulfillment linkage, reasoned release/cancel/expiry states and locked
  over-allocation protection;
- Tenant/warehouse-scoped bins and an explicit `LEGACY-UNLOCATED` allocation
  path that records unknown historical custody without inventing bin, lot,
  serial, expiry, value or cost facts;
- immutable versioned Material traceability profiles, lot or quantity-one serial
  evidence, expiry-controlled hard issue gates, and available/quarantined/closed
  quality states;
- physical/cycle counts with a frozen movement watermark, counted lines,
  independent approval, stale-freeze rejection and linked Inventory adjustment
  transactions;
- two-sided custody transfers with separate dispatch debit, in-transit state,
  independent destination acceptance, receipt credit and explicit shortage,
  damage or rejection evidence;
- quantity/custody reconciliation, expiry queue, Persian-first RTL operational
  adapters and read-only Django Admin inspection.

All mutations use active membership, dedicated `BusinessPermissionCode` checks,
Tenant and project/warehouse scope, transactions and row locks. New permissions
are seeded and reconciled to the protected default roles by organization migration
`0096`; Inventory migration `0002` is expand-only.

## 2. Source lineage and correction

`StockTransaction` remains the authoritative posted quantity ledger.
`StockTraceAllocation` identifies its movement, direction, warehouse, optional
bin and exactly one optional lot/serial. Reservations point to the eventual posted
issue used for fulfillment. Count variance lines point to their adjustment
movement. Transfer lines point separately to dispatch and receipt movements.

Posted movement evidence is immutable. Existing stock reversal creates the
equal-and-opposite movement and copies trace allocation lineage with its direction
reversed. Transfer retries and count-post retries fail after the first committed
transition. Final correction remains explicit reversal/replacement; no service
silently edits or deletes posted custody history.

## 3. Accepted decisions and preserved later gates

The accepted policy register is:

| Decision | Accepted disposition | Effect in this tranche |
| --- | --- | --- |
| P8-D01 | A — perpetual moving weighted average | Implemented and accepted in P8-S12–S17; this custody tranche itself added no valuation layer or value calculation. |
| P8-D02 | A — versioned risk-based profiles | Implemented for none/lot/serial quantity traceability. |
| P8-D03 | A — profile hard expiry gate | Implemented for issue/reservation selection; notification scheduling remains absent. |
| P8-D04 | A — source-backed capitalization and monthly straight-line book depreciation | Recorded only. Fixed Assets and depreciation runtime remain absent. |
| P8-D05 | A — Equipment owns operational maintenance | Boundary retained; no Equipment runtime changed. |
| P8-D06 | A — explicit Inventory issue/return linked to maintenance work | Recorded for a later tranche; maintenance/spares integration is not implemented here. |

No valuation layer, landed cost, Equipment usage/fuel/cost allocation, maintenance
redesign or spare-parts consumer, Fixed Asset, depreciation, journal/GL producer,
Project Cost actual, payable, Treasury/cash mutation, P7 Payroll proposal consumer,
background queue, production cutover or production activation is introduced.
Existing Equipment maintenance `cost` remains descriptive only.

## 4. Migration and reconciliation

The schema change only adds new tables, constraints, indexes/relationships and
permission rows. It does not replace or reinterpret an existing movement. The
legacy backfill service is explicit, permissioned, auditable and idempotent: it
creates only unknown-custody allocations for already posted/reversed movement
sides lacking allocations. It never fabricates traceability or financial facts.

The reconciliation workbench reports partial movement-allocation mismatches,
open in-transit transfers, unresolved acceptance variances and active
reservations. Zero allocation on retained legacy history is distinguished from a
partial mismatch until the explicit backfill is run; the backfill makes the
unknown position visible through `is_legacy_unknown` and its legacy bin.

## 5. Acceptance evidence

Focused PostgreSQL tests cover Tenant denial, reservation over-allocation,
lot/expiry issue blocking, immutable trace/reversal lineage, count maker-checker
and linked adjustment, transfer maker-checker/conservation/retry, concurrent count
posting and transfer dispatch, explicit/idempotent legacy backfill, downstream
no-effects, RTL workbench scope, and migration rollback/reapply. Django system
checks, migration-drift checks and targeted Ruff validation are required in the
closeout run.

Closeout evidence on 2026-10-04:

- clean PostgreSQL database plus the complete focused file: **9 passed**, including
  migration rollback/reapply and serialized concurrency cases;
- Django system check: **0 issues**; migration drift: **none**; targeted Ruff:
  **passed**;
- the retained Inventory regression run exposed the pre-existing Procurement
  fixture mismatch in
  `test_goods_receipt_can_enter_inventory_once_and_must_reverse_before_void`:
  its legacy test receipt has no pinned `PurchaseOrderVersionLine`, so it fails in
  `post_goods_receipt` before reaching Inventory. A later broad retry was stopped
  during the repository's expensive serialized-fixture rebuild; this does not
  reduce the clean focused P8 evidence, but the retained fixture remains a named
  follow-up rather than being silently claimed green.

This evidence is not production certification. Representative Tenant migration,
performance/capacity, penetration/least-privilege, backup/restore, operating
procedure, training, monitoring and production runbook gates in section 11 of the
entry packet remain open.

## 6. Next authorization boundary

P8-S12–S17 and P8-S18–S23 are now Product Owner accepted within their
non-production boundaries. P8-S24–S27 is subsequently Product Owner accepted under C01–C38=A and bounded runtime.
Any next implementation requires explicit Product Owner authorization naming the
exact session range and accepting its own implementation contract. The
authorization must preserve Inventory,
Equipment, Fixed Assets, Procurement, Accounting and Project Cost authority
separation; prohibit P7 Payroll proposal consumption; require explicit
reversal/replacement and expand-only non-fabricating migration; and state whether
production behavior remains disabled. P8-D01=A alone does not authorize a
valuation-layer implementation.

The Product Owner supplied the following architecture/decision authorization; the
resulting contract is
`P8_S12_S17_VALUATION_AND_FINANCIAL_HANDOFF_DECISION_PACKET.md`:

> I accept P8-S05–S11 within its documented non-production boundaries. I
> authorize preparation of a P8-S12–S17 valuation and financial-handoff
> architecture-decision packet only. This does not authorize valuation-layer
> runtime, Inventory-to-GL posting, Project Cost actuals, Equipment or Fixed Asset
> runtime, P7 Payroll proposal consumption, migration cutover, production
> activation, or P8-S18+.

Runtime implementation of P8-S12–S17 requires a second explicit authorization
that references the resulting accepted contract and repeats its migration,
reconciliation, correction, acceptance-evidence and non-production gates.
