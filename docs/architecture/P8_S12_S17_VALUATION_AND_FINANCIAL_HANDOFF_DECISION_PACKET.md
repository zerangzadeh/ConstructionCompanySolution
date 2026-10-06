# P8-S12–S17 Valuation and Financial-Handoff Decision Packet

**Prepared:** 2026-10-04  
**Status:** P8-V01–P8-V16 = A and P8-S12–S17 Product Owner accepted on 2026-10-05 within the documented non-production boundary  
**Predecessor acceptance:** P8-S01–S04 and P8-S05–S11 are Product Owner accepted. P8-D01–D06 = A are closed.  
**Authority:** this packet was the sole P8-S12–S17 design contract and bounded implementation authority. P8-S18–S23 and P8-S24–S27 are subsequently Product Owner accepted under C01–C38=A and bounded runtime; production cutover and activation remain unauthorized.

## 1. Bounded purpose and exclusions

P8-S12–S17 prepares the contract for a future Inventory-owned, perpetual moving weighted-average valuation capability and its strictly one-way source boundaries. It may describe future valuation evidence, but creates none now.

It excludes runtime Inventory valuation; Accounting or GL posting; Project Cost actual creation; Equipment cost allocation; Fixed Assets, capitalization and depreciation runtime; P7 Payroll proposal consumption; production cutover or activation; and every P8-S18+ activity. The existing Equipment maintenance \`cost\` remains descriptive operational evidence only.

## 2. Proposed session decomposition

| Session | Proposed design/implementation result when separately authorized | Must not occur in the session |
| --- | --- | --- |
| P8-S12 | Value-source catalogue, event taxonomy, quantity-to-value lineage and immutable source/version pinning | Infer or backfill cost from a quantity movement |
| P8-S13 | Perpetual moving weighted-average engine and immutable valuation-layer/event lifecycle | Create a journal, Project Cost actual or physical custody movement |
| P8-S14 | Costed receipt, issue, return, transfer, count-adjustment, correction and reversal contracts | Edit finalized quantity or value evidence in place |
| P8-S15 | Finance/Project Controls/Equipment-spares handoff envelopes, reconciliation, SoD and privacy contracts | Let an Inventory event mutate Accounting or Project Controls authority |
| P8-S16 | Expand-only migration, verified opening-value import, pre-production shadow/rehearsal and exception handling | Invent historical price, traceability, value, capitalization or cost facts |
| P8-S17 | Permissioned Persian-first RTL evidence/workbench, concurrency/idempotency hardening and acceptance evidence | Production cutover, activation, P8-S18+ or downstream runtime activation |

No row is implementation authority until the Product Owner accepts the decision register and supplies the bounded runtime authorization in section 10.

## 3. Exact ownership and data-flow model

| Fact or action | Authoritative owner | Required lineage / no-effect rule |
| --- | --- | --- |
| Commercial price, currency, supplier terms, receipt acceptance and source revision | Procurement | A future valuation event references an accepted, immutable commercial source and its exact version/line; it never edits or reclassifies Procurement. |
| Quantity, custody, reservations, traceability, counts and valuation evidence | Inventory | \`StockTransaction\`/custody evidence remains the quantity authority. A future valuation event is a separate immutable value record linked to one posted quantity event and source evidence. |
| Journal, account selection, recognized liability, FX accounting and GL balance | Accounting | Inventory can publish a reviewable proposed source envelope only. Accounting independently validates, accepts, posts, reverses and reconciles its own journal. |
| Project Cost actual, cost classification, period and project-control reporting | Project Controls | Inventory can publish a proposed source envelope only. Project Controls independently accepts it before any actual exists. P7 Payroll proposals are not an input. |
| Equipment identity, deployment and maintenance work | Equipment | A maintenance work reference may be linked to an explicit Inventory issue/return. No maintenance completion, descriptive \`cost\`, or Equipment record creates quantity, valuation, Accounting or Project Cost facts. |
| Capitalization, carrying amount, depreciation and disposal | future Fixed Assets | No Inventory valuation event capitalizes an asset or creates an asset-register fact. |

The permitted future direction is:

\`Procurement versioned commercial evidence -> posted Inventory quantity event -> Inventory valuation event/layer -> proposed downstream envelope -> independently accepted Accounting or Project Controls fact\`.

The arrows are references, not writes into the next authority. For an internal transfer, the path is only \`source Inventory custody/value -> destination Inventory custody/value\`; there is no Procurement, Accounting or Project Cost effect.

## 4. Proposed valuation lifecycle and data model

### 4.1 Perpetual moving weighted average

P8-D01=A fixes the method: the valued pool for an organization, material and approved valuation scope carries quantity and functional-currency value. A valued receipt increases both; a valued issue decreases quantity and value using the current moving average. The average is recalculated after each finalized inbound value event. Warehouse/bin/lot/serial custody remains separate from the cost pool unless a later accepted policy explicitly changes pool granularity.

The future design must define one deterministic posting order for equal timestamps, pin it in finalized evidence, and never silently recompute history after a later source change. Back-dated events are controlled correction/replacement work, not an in-place reorder.

### 4.2 Proposed records (future concepts, not current schema)

| Record | Minimum immutable fields | Lifecycle |
| --- | --- | --- |
| \`InventoryValuationEvent\` | organization, public id, event type, posted \`StockTransaction\` id, material, valuation pool, quantity direction, functional-currency amount, source evidence/version/line, event ordering key, actor/time/idempotency key, correction lineage | prepared -> source-validated -> finalized -> reversed/replaced |
| \`InventoryValuationLayer\` | organization, event id, quantity/value before and after, unit cost, rounding policy version, functional currency, remaining/consumed quantity where applicable, finalization/reversal linkage | draft evidence -> finalized immutable layer -> fully/partly consumed or reversed |
| \`InventoryValueException\` | organization, blocked quantity event, reason code, missing/conflicting source, owner, resolution/replacement linkage | open -> investigated -> resolved or rejected |
| \`DownstreamCostSourceEnvelope\` | organization, Inventory valuation event/layer reference, consumer (\`accounting\` or \`project_controls\`), classification status, source/version pins, amount/currency and idempotency key | prepared -> supplied -> independently acknowledged/rejected; no consumer fact is created by Inventory |

The schema must be expand-only and retain existing custody records unchanged. A finalized valuation event/layer is append-only: correction is an explicit linked reversal and, where needed, a separately finalized replacement.

### 4.3 Event treatment

| Quantity event | Proposed valuation treatment | Source requirement |
| --- | --- | --- |
| Receipt | Inbound valuation event increases pool quantity/value and recomputes average | Accepted Procurement receipt plus pinned commercial-cost source/version, or separately approved verified opening evidence |
| Issue | Outbound event uses the finalized pool average at its deterministic ordering point | Explicit posted Inventory issue; optional maintenance/project reference is descriptive lineage only |
| Return | Prefer reversal of the linked prior issue at the original pinned unit cost; an unlinked return is an exception until a separately approved source rule resolves it | Original issue/layer link, or exception evidence |
| Transfer | Carry the same value between Inventory custody locations; no gain/loss, new commercial source or downstream fact | Linked two-sided finalized transfer and source valuation event/layer |
| Count adjustment | Quantity remains governed by approved count adjustment. Value needs a separately defined, evidenced adjustment rule; absent one it remains blocked/unvalued, never guessed | Approved count lineage plus verified value basis or exception |
| Reversal/replacement | Record equal-and-opposite reversal of the exact finalized layer/event, then a new linked replacement if required | Original immutable identifiers and correction reason/actor/time |

Quantity availability does not depend on valuation finalization unless a future separately accepted policy says otherwise. A missing or unresolved cost therefore cannot create a false value, ledger effect or Project Cost actual; it enters the exception/reconciliation queue.

### 4.4 Negative, rounding and currency boundaries

- Normal valuation finalization must hard-reject negative stock and negative pool value. A pre-production-only exception/rehearsal record may expose the condition but must not create a fabricated layer.
- Monetary scale, rounding mode and functional currency are organization-level policy inputs owned by Accounting configuration. Inventory pins the policy version used for calculation; it does not create monetary policy. Calculation precision, display precision and residual handling require Product Owner choice P8-V09 before runtime.
- Inventory valuation is in the organization functional currency. Procurement may retain source-document currency and approved conversion evidence. FX selection, remeasurement and journal treatment are Accounting concerns; no Inventory FX gain/loss or multi-currency valuation is in this tranche.

## 5. Controls, reconciliation and evidence

Future services must resolve active organization from membership, require active tenant status, and validate material, warehouse/site/project and all referenced records within that tenant. Cost evidence must have a separate view permission from ordinary quantity/custody access. Default deny and maker-checker separation apply at minimum to value preparation, source resolution, exception disposition, correction/reversal approval, downstream-envelope supply and reconciliation review. No position, workflow assignment or UI visibility grants a permission.

Finalization must lock the affected valuation pool and source quantity event, re-read state and re-check authorization in one transaction. Stable source-event and consumer-envelope keys make retries idempotent. Concurrency races, duplicate source references, cross-tenant references, stale source versions and conflicting reversals fail closed and leave auditable evidence. Audit records capture actor, time, prior/new lifecycle state, reason, policy version, source pins and correlation/idempotency key while applying existing sensitive-data minimization.

Required future reconciliations include:

1. Each finalized valuation event has exactly one linked posted quantity event; the event quantity/material/organization agrees with it.
2. Pool roll-forward equals finalized inbound/outbound/reversal layers and never creates an unlinked value.
3. Receipt value references one accepted Procurement commercial source/version; source changes do not mutate finalized Inventory value.
4. Transfer source/destination value is conserved; count, return and correction exceptions remain visible until resolved.
5. A downstream envelope is uniquely keyed by Inventory layer/event and consumer; it is not a journal or Project Cost actual, and an acknowledgment cannot be counted twice.
6. Equipment/spares references reconcile to explicit Inventory issue/return evidence only; descriptive maintenance \`cost\` and P7 Payroll proposals have no route into valuation or cost actuals.

The future UI is Persian-first RTL and evidence-led: value status, source/version, quantity/value separation, exception reason, immutable correction lineage and reconciliation result must be visible to authorized users. It must not imply a GL posting, Project Cost actual, capitalization or production activation.

## 6. Migration and historical-data assumptions

Migration is expand-only. Existing \`StockTransaction\`, custody, reservation, traceability, count and transfer history remains authoritative for quantity but is not automatically a valuation layer. The migration must not invent historical cost, traceability, valuation, capitalization, Accounting entry or Project Cost fact.

Before any production runtime, each organization must choose a controlled opening valuation date and provide verified opening quantity/value evidence with source, functional currency, policy version, preparer/reviewer and exception status. Records without a verified basis remain explicitly unvalued and reconciled as exceptions. Legacy fixture or source gaps—including the known Procurement fixture without a pinned \`PurchaseOrderVersionLine\`—are defects to resolve independently; they are not evidence that a value may be inferred. A rehearsal may use isolated, non-production copied evidence with an audit trail and reconciliation report; it must not alter production history.

## 7. Product Owner decision register

P8-D01–D06 and P8-V01–V16=A are Product Owner accepted and no longer open. The following table preserves the accepted implementation decisions and their rationale.

| Decision | Options | Recommended disposition |
| --- | --- | --- |
| P8-V01 valuation pool | A: organization/material functional-currency pool; B: warehouse pool; C: bin/lot/serial pool | **A** — preserves moving-average policy and keeps custody separate; changing pool needs later authorization. |
| P8-V02 event/layer grain | A: one immutable valuation event per posted quantity event plus source slice; B: periodic aggregate | **A** — preserves source lineage and reversibility. |
| P8-V03 receipt cost source | A: accepted, version-pinned Procurement commercial evidence only; B: manually entered cost; C: inferred historical cost | **A** — missing evidence becomes an exception. |
| P8-V04 unlinked return | A: block until linked original issue or reviewed exception rule; B: use current average automatically | **A** — prevents silent value distortion. |
| P8-V05 count adjustment value | A: require approved verified value basis or leave unvalued exception; B: automatically use current average | **A** — avoids invented value. |
| P8-V06 correction timing | A: linked equal/opposite reversal then replacement, no history rewrite; B: edit layer | **A** — immutable finalized history. |
| P8-V07 negative policy | A: hard reject negative quantity/value finalization; B: permit temporary negative layers | **A** — exceptions are visible but unvalued. |
| P8-V08 late/back-dated events | A: controlled correction/replacement with pinned deterministic order; B: silently recalculate prior layers | **A** — preserves finality and auditability. |
| P8-V09 monetary precision | A: Accounting-owned policy version with explicitly approved calculation/display/residual rules; B: Inventory local defaults | **A** — Accounting owns monetary policy; exact scales/mode must be recorded before build. |
| P8-V10 currency | A: functional-currency Inventory valuation; Procurement source currency/conversion pinned, no Inventory FX; B: multi-currency pools | **A** — bounded and compatible with Accounting ownership. |
| P8-V11 Accounting handoff | A: immutable proposed source envelope, independently accepted/posted by Accounting; B: automatic journal | **A** — no GL authority crosses the boundary. |
| P8-V12 Project Cost handoff | A: immutable proposed source envelope, independently classified/accepted by Project Controls; B: automatic actual | **A** — no Project Cost actual is created by Inventory. |
| P8-V13 Equipment/spares | A: explicit Inventory issue/return linked to maintenance reference only; B: maintenance completion/descriptive cost drives value | **A** — preserves Inventory custody/value and Equipment operational ownership. |
| P8-V14 opening value | A: verified opening evidence or explicit unvalued exception; B: calculated backfill from legacy movements | **A** — no historical invention. |
| P8-V15 access/SoD | A: default-deny, cost-sensitive view and separated prepare/approve/reverse/reconcile/supply permissions; B: reuse broad warehouse access | **A** — protects commercial cost and finality. |
| P8-V16 release gate | A: non-production shadow/rehearsal, reconciliations and accepted evidence before any runtime/cutover request; B: direct activation | **A** — preserves production-readiness gates. |

## 8. Validation and acceptance criteria for a later runtime tranche

Before a separately authorized runtime implementation can be accepted, it must provide PostgreSQL-backed evidence for tenant/site/project isolation; default-deny permissions and SoD; source/version pinning; locking and retry idempotency; concurrent same-pool finalization; no duplicate downstream envelope; immutable reversal/replacement; negative/missing-cost failure; transfer conservation; count exception behavior; rounding/currency policy pinning; RTL evidence visibility; and all reconciliation roll-forwards. Migration evidence must prove expand-only behavior and demonstrate that unknown historical data stays unknown.

Acceptance also requires an explicit no-effect proof that Inventory valuation has not posted GL, created a Project Cost actual, allocated Equipment cost, created a Fixed Asset/depreciation fact, or consumed a P7 Payroll proposal. The retained Procurement regression caused by a legacy fixture lacking a pinned \`PurchaseOrderVersionLine\` remains a separately tracked unresolved fixture issue; it is neither resolved nor accepted by this packet.

## 9. Production-readiness gates preserved

This packet is not production certification. Runtime requires a clean migration path, data-quality/reconciliation evidence, support/recovery runbook, authorization and audit review, cost/privacy review, performance/concurrency evidence, explicit downstream ownership acceptance and a separate Product Owner cutover/activation decision. All accepted behavior remains non-production. P8-S18–S23 and P8-S24–S27 are subsequently Product Owner accepted under C01–C38=A and bounded runtime.

## 10. Exact bounded runtime authorization required

After the Product Owner has explicitly accepted P8-V01 through P8-V16 (including exact P8-V09 scale/mode/residual values), runtime work may start only with wording substantially equivalent to:

> I accept \`P8_S12_S17_VALUATION_AND_FINANCIAL_HANDOFF_DECISION_PACKET.md\` and choose P8-V01 through P8-V16 as recorded. I authorize implementation of P8-S12–S17 only within sections 1–9 of that packet: Inventory-owned perpetual moving weighted-average valuation evidence, explicit source/version lineage, immutable reversal/replacement, controlled exceptions, proposed downstream envelopes, expand-only non-fabricating migration, and required acceptance evidence. This authorization does not authorize P8-S18+, Inventory valuation beyond the accepted scope, Accounting/GL posting, Project Cost actual creation, Equipment cost allocation, Fixed Assets, depreciation, P7 Payroll proposal consumption, production cutover, or production activation.

The authorization must name any approved deviation from a recommended decision; silence does not authorize it.
