# P8-S12–S17 Inventory Valuation Implementation

**Status:** Product Owner accepted on 2026-10-05 within the documented non-production boundary.  
**Authority:** P8-V01–P8-V16=A and the bounded authorization recorded in \`P8_S12_S17_VALUATION_AND_FINANCIAL_HANDOFF_DECISION_PACKET.md\`.

## Delivered foundation

- Inventory-owned immutable valuation-event, moving-WAC pool, missing-cost exception and downstream-proposal records.
- Tenant-scoped finalization service that requires a posted stock movement, a non-empty version-pinned source reference, a Decimal non-negative cost, and the active versioned monetary policies.
- Per-organization idempotency keys, row locking of source movement and pool, immutable final records, no-negative enforcement, and proposal envelopes that do not create journals or Project Cost actuals.
- Permission catalog and default-role migration for valuation view, preparation, reversal, reconciliation and supply.

## Not yet complete

Return without authoritative reversal lineage and Replacement/Correction remain fail-closed by design. Transfer-pair valuation, read-only reconciliation, focused PostgreSQL validation, and clean-schema migration validation are complete within the authorized non-production boundary. P8-S18–S23 and P8-S24–S27 are subsequently Product Owner accepted under C01–C38=A and bounded runtime. Production behavior/downstream posting remains unauthorized.

## Accepted structural limitations

- Replacement/Correction attempts cannot be detected as records because no
  authoritative Replacement/Correction custody model exists. They remain
  unsupported and fail closed; no predecessor may be inferred.
- A missing required Accounting or Project Cost proposal cannot be detected
  generically because no authoritative `proposal_required` state exists. Existing
  proposal envelopes are reconciled for invalid source, stale/reversed source,
  source/version, amount, currency and duplicate anomalies only.

These limits are accepted domain boundaries for P8-S12–S17 and do not authorize
new custody or downstream semantics.

## Focused acceptance evidence

`apps/inventory/test_p8_s12_s17.py` passed 3 tests in 4.14 seconds against
PostgreSQL using the existing `test_construction_erp` database. Coverage includes
unvalued posted movement detection, persistent missing-cost exceptions, read-only
reconciliation, and RTL valuation workbench reachability. A disposable empty
database `test_p8_s12_s17_20261005` applied the complete migration graph (340
migrations), including Inventory 0002–0005 and organizations 0097; expected
valuation tables were present and the database was removed after validation.

## Custody-to-valuation evidence mapping

| Custody concept | Existing authority and durable relationship | Valuation conclusion |
| --- | --- | --- |
| Original movement | `StockTransaction` identity, posted status and material/quantity/warehouse fields | Sufficient source movement identity for one valuation event. |
| Reversal | `StockTransaction.reversal_of` is a one-to-one equal-and-opposite posted movement; original becomes `reversed` | Proven predecessor relationship for linked valuation reversal only. |
| Replacement/correction | No distinct custody replacement predecessor field | Must not be inferred from number, date, quantity or notes. |
| Transfer source | `InventoryTransferLine.dispatch_transaction` is a one-to-one custody movement | Direct source-side lineage exists. |
| Transfer destination | `InventoryTransferLine.receipt_transaction` is a one-to-one custody movement populated on independent acceptance | Direct destination-side lineage exists through the transfer line. |
| Return | No separate return type or origin field; only `reversal_of` is enforced inverse lineage | Must fail closed unless represented by the proven reversal relationship. |
| Commercial source/version | Receipt links to `GoodsReceiptItem`; valuation requires explicit source/version pins | No descriptive or inferred cost is authoritative. |
