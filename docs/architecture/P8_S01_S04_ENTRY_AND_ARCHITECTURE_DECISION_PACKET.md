# P8-S01–S04 Entry and Architecture Decision Packet

**Prepared:** 2026-10-04
**Status:** Product Owner accepted on 2026-10-04; P8-D01–D06 = A recorded;
P8-S05–S11 and P8-S12–S17 Product Owner accepted within documented
non-production boundaries
**Authority:** the original execution was limited to P8-S01–S04. The Product Owner
later authorized only P8-S05–S11 under section 10. P8-S12–S17 and P8-S18–S23 are
subsequently Product Owner accepted within documented non-production boundaries.
P8-S24–S27 is subsequently Product Owner accepted under C01–C38=A and bounded runtime. At the time of this entry packet, P8-S28–S30,
Accounting/GL posting, Project Cost actuals and production activation remained
unauthorized. Later P8-S28–S30 Product Owner acceptance is recorded in
`P8_FINAL_ASSURANCE_CLOSEOUT_AND_P9_HANDOFF.md` and does not authorize any
downstream posting or production activation.

## 1. Entry gate and bounded four-session result

The prerequisite is satisfied: `ROADMAP.md` and
`P7_FINAL_ASSURANCE_CLOSEOUT_AND_P8_HANDOFF.md` record consolidated
P7-S01–S36 as Product Owner accepted on 2026-10-04. P7 Payroll-owned downstream
records remain immutable proposals and reconciliation evidence only. They are not
Inventory value, recognized labor cost, Project Cost actuals, Accounting journals,
asset cost, depreciation, liabilities, payments, or production authority.

The same-date Product Owner disposition accepted this packet and selected
P8-D01=A, P8-D02=A, P8-D03=A, P8-D04=A, P8-D05=A and P8-D06=A. The bounded
implementation and evidence are recorded in
`P8_S05_S11_INVENTORY_CUSTODY_IMPLEMENTATION.md`. D01 and D04–D06 are recorded
policy for later packages and did not expand the S05–S11 quantity/custody scope.
The later valuation and financial-handoff design contract is
`P8_S12_S17_VALUATION_AND_FINANCIAL_HANDOFF_DECISION_PACKET.md`; it is
architecture/decision preparation only and preserves the same non-production
boundary.

| Session | Completed design result |
| --- | --- |
| P8-S01 | Reconciled current Inventory, Equipment, Fixed Asset, Accounting, Project Cost, Procurement, Materials/UOM, Parties and P7 source boundaries. |
| P8-S02 | Defined one authoritative owner per operational, quantity, value, asset, journal and project-cost fact, plus lifecycle and correction boundaries. |
| P8-S03 | Prepared explicit Product Owner choices for valuation, traceability/expiry, capitalization/depreciation, maintenance ownership and spare-parts consumption. |
| P8-S04 | Defined lineage, Tenant isolation, permissions, reconciliation, migration, recovery, production-readiness gates and the bounded P8-S05–S11 implementation handoff. |

This packet stops at design. No existing runtime behavior changes.

## 2. Verified current implementation boundary

| Area | Current authority | Important limitation retained by this tranche |
| --- | --- | --- |
| Materials/UOM | `Material`, categories, aliases/supersession, attributes, technical approvals, canonical UOM, effective conversion/rounding evidence | Inventory movements currently require the material's canonical active UOM. Material identity/UOM is master data, not stock custody or valuation. |
| Procurement | Versioned issued PO/change evidence, `GoodsReceipt`/item, service acceptance, supplier invoice and match evidence | A posted goods receipt proves Procurement acceptance. It does not automatically create stock, payable, journal, Project Cost or cash. Price and invoice evidence are not an approved Inventory valuation layer. |
| Inventory | Tenant-scoped `Warehouse` and `StockTransaction`; quantity is derived from posted/reversed receipt, issue, adjustment, transfer and reversal movements | There are no reservations, bins, lots, serial instances, expiry controls, count documents, in-transit custody, valuation layers, issue-to-WBS/activity, Inventory posting producer or financial subledger. A receipt movement explicitly references one posted goods-receipt item. |
| Equipment | `Equipment`, non-overlapping project/site assignments and preserved maintenance records | No meter/usage, operator qualification, fuel, downtime, maintenance plan/work-order aggregate, spare-part line, cost allocation or fixed-asset link. `MaintenanceRecord.cost` has no currency, source-line, posting, capitalization or Project Cost authority and is therefore descriptive operational evidence only. |
| Fixed Assets | No implemented fixed-asset register or depreciation ledger | Equipment identity, ownership type and acquisition date do not constitute capitalization, carrying value, depreciation, impairment or disposal accounting. |
| Project Controls | Approved producer-contract structure and append-only commitment/accrual/actual fact structure exist | No Inventory, Equipment, Fixed Asset or P7 Payroll producer is activated. Coverage is intentionally incomplete; no P8 or Payroll proposal may be treated as a Project Cost actual. |
| Accounting | Sole journal authority with code-owned posting contracts, source/version/line identity, immutable posting and reversal/replacement | No registered Inventory or Fixed Asset operational posting contract exists. Inventory posting or depreciation cannot bypass Accounting or write journal rows directly. |
| Parties/DMS | `BusinessParty` owns supplier/service-provider identity; DMS owns protected files/versions | P8 must reuse them. It must not create parallel supplier, maintenance-provider, attachment or certificate masters. |
| P7 Payroll | Payroll owns finalized results and immutable liability/Accounting/payment/Project Cost proposals | Proposals have no downstream recognition effect. P8 cannot reinterpret them as equipment operator cost, capitalized labor, inventory burden or Project Cost actual. |

### Current compatibility facts that constrain later design

- A posted/reversed stock transaction is immutable; correction already uses a
  linked equal-and-opposite posted reversal.
- The current `transfer` movement changes source and destination in one posting.
  It has no dispatch, in-transit or receiving-custody state.
- A goods-receipt item may have at most one draft or unreversed posted Inventory
  receipt movement. Any later bin/lot/serial detail must conserve the parent
  quantity without duplicating Procurement acceptance.
- Adjustment movements are quantity evidence but are not currently sourced from
  an approved physical-count document.
- An issue requires a project, but not site, WBS, activity, CBS, cost center,
  reservation, maintenance work or valuation evidence.
- Equipment maintenance is finalized history, but its single optional cost value
  cannot be promoted into AP, Inventory, Accounting, Fixed Assets or Project Cost.

## 3. Authoritative ownership decisions

These architecture boundaries are fixed for later P8 work unless the Product
Owner explicitly changes them in a new decision tranche.

| Fact | Authoritative owner | Permitted downstream use | Must not happen |
| --- | --- | --- | --- |
| Material identity, canonical UOM and conversion policy | Materials/UOM | Referenced by Procurement, Inventory, Equipment spares and reporting | Inventory or Equipment creates a duplicate material/UOM master. |
| Commercial order price and accepted delivery | Procurement; invoice assertion remains AP-owned | Inventory pins exact PO version/line and goods-receipt/item evidence | Receipt or match silently creates stock value, payable, journal or actual cost. |
| Warehouse/bin custody and posted quantity movement | Inventory | Rebuildable balances, reservations, traceability, counts and later value layers | Editable on-hand balance or Procurement-owned stock. |
| Reservation | Inventory | Availability control against a project and optional site/WBS/activity demand | Reservation changes on-hand, recognizes cost or guarantees Procurement supply. |
| Lot/serial/expiry identity in stock | Inventory, referencing Material policy | Custody, issue/return, recall and expiry evidence | Lot/serial becomes a second Material or equipment/asset identity. |
| Operational equipment identity, deployment, meter, fuel, downtime and maintenance execution | Equipment | Later approved utilization/cost evidence and operational reporting | Equipment stores asset carrying value or posts journals. |
| Spare-part issue/return quantity | Inventory, linked to Equipment-owned maintenance work | Maintenance consumes the referenced movement; later valuation may derive cost | Maintenance completion decrements stock or invents a unit cost. |
| Capitalization, asset book, carrying value, depreciation, impairment and disposal | Future Fixed Assets authority | Accounting posting proposals/contracts and Project Cost consumption after separate approval | `Equipment` is relabeled as `FixedAsset`, or Accounting derives an asset from ownership type alone. |
| Journal and ledger balance | Accounting | Financial statements and reconciliations | Inventory, Equipment, Fixed Assets or Project Cost writes journal lines directly. |
| Commitment/accrual/actual projection | Project Controls through an approved producer contract | Cost/forecast/reporting with exact source lineage | A source proposal or operational record is treated as an actual without approved recognition. |
| File/version evidence | DMS | Typed links from each owning domain | P8 creates another blob/version store. |

Operational `Equipment` and financial `FixedAsset` are separate identities with an
optional effective-dated, Tenant-scoped link. One equipment may be rented/leased
and have no owned asset; one asset may represent a component or grouped item and
need not be currently deployed as equipment. Neither identity grants lifecycle or
permission authority over the other.

## 4. Lifecycle boundaries

### 4.1 P8-S05–S11 quantity and custody target

- Reservation: `draft -> active -> partially_fulfilled/fulfilled`, with
  `draft/active -> cancelled` and explicit release/expiry evidence. It reduces
  available-to-reserve only; it never reduces posted on-hand.
- Bin: active location master -> inactive/archived only after no stock, active
  reservation, open count or in-transit receipt depends on it. Bin activation is
  warehouse-local and never changes Material identity.
- Lot/batch: recorded -> available/quarantined -> exhausted/expired/closed as
  applicable. Corrections preserve the original identifier and use reasoned
  adjustment/transfer/reclassification evidence rather than rewriting movements.
- Serial: received/available -> reserved/issued/transferred/in-transit/returned/
  quarantined/retired as derived custody states. A serial has quantity one in the
  configured canonical discrete UOM and cannot occupy two active custody states.
- Count: draft -> frozen -> counted -> submitted -> independently approved ->
  posted, or cancelled before posting. Posting creates linked Inventory adjustment
  movements; it never edits the derived balance.
- Transfer custody: draft -> dispatched -> in_transit -> accepted, with cancellation
  only before dispatch and explicit rejected/short/over/damaged exception evidence
  after dispatch. Source relief and destination receipt remain conserved and
  idempotent; a single actor cannot silently dispatch and accept when separation is
  required.

### 4.2 Later P8 lifecycle targets, not implementation authority

- Valuation layers are immutable after finalization. Revaluation/correction uses
  linked reversal and replacement under an open Accounting period and approved
  policy; quantity history is never rewritten to fix value.
- Maintenance planning/work execution belongs to Equipment. Final work history is
  immutable; correction is a successor/reversal record. Procurement service
  acceptance, Inventory spare movements, AP invoice evidence and DMS documents
  remain separate linked facts.
- Fixed Asset lifecycle is candidate -> under review -> capitalized -> in service ->
  suspended/impaired/transferred -> disposed, with capitalization, depreciation,
  impairment, transfer and disposal each recorded as immutable transactions.
  Financial correction is linked reversal/replacement, never a carrying-value edit.

## 5. Product Owner decision register

Six decision points covering the five requested policy areas are **OPEN**; expiry
is separated from general bin/lot/serial depth so the safety gate is explicit.
Recommendations below are design proposals, not accepted policy and not permission
to implement.

### P8-D01 — Inventory valuation method and release boundary

| Option | Consequence |
| --- | --- |
| **A — Perpetual moving weighted average (recommended)** | Maintain immutable value layers and a moving-average pool per Tenant/material/warehouse; transfers carry source value and update the destination pool without gain. Issues/returns/reversals pin their originating layer/policy. First release remains IRR-only and fails closed when acquisition cost, landed-cost policy, period or mapping is missing. |
| B — Perpetual FIFO | Strong receipt-layer traceability but higher operational and migration complexity; every issue/return/transfer must consume and preserve ordered layers. |
| C — Standard cost with variance | Stable operational rates but requires governed standard versions, variance accounts and period-close policy before trustworthy actuals. |
| D — Quantity-only first release | Keeps P8 operational but defers financial valuation, GL and Project Cost consumption entirely. |

**Recommendation:** A, with no historical value invention. Opening valuation
requires separately reviewed source evidence and reconciliation; otherwise legacy
quantity remains explicitly `value_unknown` and financial release fails closed.

**Decision:** PENDING PRODUCT OWNER.

### P8-D02 — Bin, lot and serial traceability depth

| Option | Consequence |
| --- | --- |
| **A — Versioned risk-based profile (recommended)** | Each Material has an effective profile of `none`, `lot`, or `serial`; bin control is enabled per warehouse and may be mandatory per profile. Profile strengthening is prospective and existing stock receives explicit unknown/unlocated migration evidence, not fabricated identifiers. |
| B — Universal lot and bin tracking | Consistent but burdens bulk construction materials and creates low-value capture. |
| C — Universal serial tracking | Unsuitable for divisible materials and operationally excessive. |
| D — No traceability | Lowest effort but cannot support expiry, recall, high-value custody or controlled spares. |

**Recommendation:** A. Serial control requires a discrete canonical unit and
quantity-one conservation. Lot/serial policy versions are pinned to movements;
later master changes do not reinterpret history.

**Decision:** PENDING PRODUCT OWNER.

### P8-D03 — Expiry policy within traceability

| Option | Consequence |
| --- | --- |
| **A — Profile-controlled expiry with hard issue gate (recommended)** | Expiry is mandatory only for expiry-controlled lot/serial profiles. Expired stock is quarantined from normal reservation/issue; an explicit permissioned disposition, return or approved exceptional issue records reason and evidence. FEFO is an allocation recommendation, not silent auto-posting. |
| B — Advisory expiry only | Easier operation but allows unsafe ordinary issue after expiry. |
| C — Expiry required for all materials | Creates invented dates and unnecessary work for non-expiring materials. |

**Recommendation:** A. Notification scheduling remains separately gated; P8-S05–S11
may provide deterministic queues only, without Celery, SMS or external channels.

**Decision:** PENDING PRODUCT OWNER.

### P8-D04 — Capitalization and depreciation policy

| Option | Consequence |
| --- | --- |
| **A — Source-backed capitalization with straight-line book depreciation first (recommended)** | A distinct Fixed Asset is capitalized only after reviewed acquisition/construction cost, ownership, ready-for-use date, useful life, residual value, asset class and Accounting mapping are complete. Monthly straight-line book depreciation is the first method; componentization is explicit where material. Tax depreciation and alternative methods remain separate future books/policies. |
| B — Multiple methods/books in first release | Supports broader accounting cases but materially expands policy, legal-review, migration, close and reconciliation risk. |
| C — Treat every owned Equipment as an asset | Simple but wrong for expensed, grouped, already depreciated, leased or incomplete acquisitions. |

**Recommendation:** A. Existing Equipment acquisition dates or maintenance costs
must never be used to infer capitalization cost, in-service date, useful life,
residual value or accumulated depreciation.

**Decision:** PENDING PRODUCT OWNER.

### P8-D05 — Equipment maintenance ownership

| Option | Consequence |
| --- | --- |
| **A — Equipment owns operational maintenance (recommended)** | Equipment owns plans, work, meter triggers, downtime and completion. Inventory owns spare custody; Procurement owns external order/acceptance; AP owns invoice; Fixed Assets/Accounting decide capital versus expense; Project Controls consumes only approved producer facts. |
| B — Inventory owns maintenance | Collapses service work into parts custody and cannot represent labor/provider/meter/downtime. |
| C — Fixed Assets owns maintenance | Mixes operational availability with financial carrying-value authority. |

**Recommendation:** A. The existing `MaintenanceRecord` remains compatibility
history until an approved expand/migrate/switch plan maps it to later work evidence.

**Decision:** PENDING PRODUCT OWNER.

### P8-D06 — Spare-parts consumption

| Option | Consequence |
| --- | --- |
| **A — Explicit issue/return linked to maintenance work (recommended)** | Inventory posts reserved or direct issue to a specific Equipment maintenance work record; unused material returns through a linked movement. Completion checks required parts evidence but never changes stock itself. Later valuation supplies immutable cost lineage. |
| B — Consume on maintenance completion | Hides custody timing, prevents returns and risks duplicate or missing movements. |
| C — Record text/amount only on maintenance | Cannot reconcile material quantity, traceability or cost. |

**Recommendation:** A. Emergency issue may be permitted only by explicit permission
and reason, followed by reconciliation to maintenance work; it is not a bypass of
Tenant, stock, expiry or serial controls.

**Decision:** PENDING PRODUCT OWNER.

## 6. Source lineage and handoff contract

Every future P8 handoff must retain `organization`, stable source type/id/version,
source line/allocation identity, occurrence/idempotency identity, actor and event
time, material/UOM or equipment/asset identity, project/site/WBS/activity where
applicable, status, correction/reversal link and policy version. Monetary handoffs
also require IRR currency, amount, valuation layer/policy, Accounting period and
mapping/rule version.

| Handoff | Required pinned source | Consumer-created fact | Failure behavior |
| --- | --- | --- | --- |
| Procurement -> Inventory receipt | Governing PO version/line plus posted goods-receipt/item and accepted quantity/UOM | Explicit Inventory receipt movement and optional traceability allocations | Missing/mismatched Tenant, project, material, UOM, quantity or final Procurement state rejects; no automatic movement. |
| Reservation -> issue | Reservation version/allocation and demand coding | Posted issue plus fulfillment evidence | Stale/overallocated reservation, insufficient available/on-hand, expired/quarantined stock or scope mismatch rejects. |
| Count -> Inventory | Frozen scope, expected snapshot, count lines, independent approval and variance reason | Linked adjustment movements | Stale freeze, unresolved in-transit movement or changed stock rejects/requires recount. |
| Transfer -> Inventory | Transfer/custody version, dispatch lines and acceptance/exception evidence | Linked source-relief and destination-receipt movements | Duplicate event returns existing result; payload conflict or unbalanced quantity rejects. |
| Inventory -> valuation (later) | Posted movement and exact trace allocations plus effective valuation policy and acquisition-cost evidence | Immutable valuation layer(s) | Missing cost/policy/period leaves value pending/unknown; quantity is not rolled back or invented. |
| Inventory -> Project Cost/Accounting (later) | Final valuation/correction layer, coding, source movement/version and reconciliation identity | Approved Project Cost fact and/or Accounting journal through their own service | No approved producer contract/mapping/open period means no downstream fact. |
| Equipment maintenance -> Inventory | Final maintenance work identity and required part demand | Reservation/issue/return owned by Inventory | Maintenance cannot mutate stock directly. |
| Equipment/Fixed Asset -> Project Cost/Accounting (later) | Approved usage/cost or asset transaction/depreciation line and policy versions | Consumer-owned cost fact/journal | Operational status or descriptive maintenance cost is insufficient. |

## 7. Tenant isolation, object scope and permissions

- Resolve the active organization from active membership/session state; never trust
  an organization identifier from a form, URL, import or request body.
- Every new aggregate, child allocation, history, policy application, reconciliation
  and idempotency key is explicitly Tenant-scoped. Cross-row validation must also
  enforce project/site, warehouse, material/UOM, equipment/maintenance and source
  context.
- Suspended Tenants may read only where existing lifecycle policy permits and
  cannot perform business mutations. Cancelled Tenants cannot use normal P8 paths.
- Warehouse/project/site grants only restrict an already permissioned membership;
  they never grant permission. Positions, equipment assignment, custody and
  workflow candidacy also never grant business authority.
- Sensitive asset cost, valuation, supplier price and financial mappings require
  separate finance permissions from operational quantity/custody access.

Existing warehouse, stock, equipment, maintenance, Project Cost and Accounting
permissions remain unchanged in P8-S01–S04. P8-S05–S11 must add dedicated catalog
codes, default-role grants and data migrations for the capabilities it actually
implements. At minimum the implementation design must separate:

| Capability | Required separation |
| --- | --- |
| Reservations | view; prepare/allocate; release/cancel; exceptional override |
| Bins/traceability/expiry | view; master/profile administration; quarantine/disposition or exceptional expired issue |
| Counts | prepare/freeze/count; independent approve; post variance |
| Transfer custody | prepare; dispatch; independently accept/record exception; resolve variance |
| Reconciliation/export | view reconciliation; sign off/resolve; export if any export is approved |

Final permission names and default grants belong to the S05 implementation diff,
but deny-by-default, active membership/Tenant status, object scope, row locking,
maker-checker where stated and append-only audit evidence are acceptance criteria.

## 8. Reconciliation and correction contract

### Quantity/custody reconciliations for P8-S05–S11

1. Procurement posted received quantity vs explicit Inventory receipt quantity,
   grouped by exact goods-receipt item; missing, duplicate and reversed differences
   remain visible.
2. Posted warehouse quantity vs the sum of bin/lot/serial allocations; unknown
   migrated positions are a named exception class, never silently balanced.
3. On-hand minus active reservation allocations equals available-to-reserve;
   reservations never alter on-hand.
4. Transfer dispatch equals accepted quantity plus open in-transit and explicit
   shortage/damage/rejection disposition.
5. Count expected quantity plus posted approved variance equals post-count quantity,
   with freeze watermark and intervening-event detection.
6. Serial custody is unique; lot/bin quantities conserve the parent movement and
   canonical UOM conversion snapshot.

### Later financial reconciliations

Inventory quantity must reconcile to valuation quantity before Inventory value can
reconcile to Accounting control accounts or Project Cost. Fixed Asset acquisition,
depreciation, impairment and disposal ledgers must reconcile to Accounting by asset
transaction and period. Equipment usage/maintenance cost and Payroll proposals are
separate sources and must not be netted or promoted to actuals to force a tie.

Corrections preserve finalized history:

- draft records may be edited/cancelled within their owner;
- posted stock changes use linked equal-and-opposite reversal and, if needed, a
  replacement with the corrected source/policy;
- count variances use linked adjustments, not balance edits;
- dispatched transfers use acceptance exception, return/re-dispatch or linked
  correction, not status rewind;
- lot/serial/bin mistakes use reasoned reclassification/transfer/adjustment while
  preserving original custody evidence;
- later value/asset/journal/cost corrections each use their own linked reversal or
  replacement and reconcile across domains by shared source/event identity.

## 9. Expand-only migration and recovery gates

1. **Inventory and classify:** measure existing warehouses, stock movements,
   goods-receipt links, material/UOM validity, negative/zero balances, transfers,
   equipment, assignments and maintenance history per Tenant.
2. **Expand:** add companion aggregates/allocations without renaming, deleting or
   changing the meaning of current `Warehouse`, `StockTransaction`, `Equipment` or
   `MaintenanceRecord` rows.
3. **Backfill only knowable facts:** retain exact source identifiers. Existing
   unlocated/untracked stock receives explicit `legacy_unlocated`/
   `traceability_unknown` evidence if the accepted policy requires it. Do not
   invent bins, lots, serials, expiry dates, acquisition cost, asset lives,
   depreciation or maintenance-part usage.
4. **Dual-read/shadow reconciliation:** compare legacy derived on-hand and the new
   allocation/custody projection per Tenant/material/warehouse before switching any
   read path. Do not dual-write independent authorities.
5. **Switch by bounded Tenant pilot only after separate authorization:** require
   zero unexplained quantity difference, accepted exception disposition, rollback
   rehearsal, permission/audit review and operator sign-off.
6. **Retain compatibility:** old fields/rows remain until dependencies, retention,
   rollback, source lineage and Tenant isolation are verified and their removal is
   separately approved.

Rollback before authoritative posting may disable the new path and return to the
retained read path. After a new custody/movement fact is authoritative, recovery is
forward correction/reversal; database rollback must never erase business history.

## 10. P8-S05–S11 bounded implementation contract

This is a handoff contract, not present authorization.

| Session | Authorized result only after the exact Product Owner authorization in section 12 |
| --- | --- |
| P8-S05 | Reservation aggregate and availability foundation using posted quantity only; no value or automatic Procurement action. |
| P8-S06 | Reservation allocation, partial fulfillment, release/cancel, expiry of reservation evidence and concurrency controls. |
| P8-S07 | Warehouse-bin master/custody allocation plus explicit legacy-unlocated migration state. |
| P8-S08 | Versioned Material traceability profile, lot/serial/expiry evidence, quarantine and quantity-one serial conservation according to accepted P8-D02/D03. |
| P8-S09 | Physical/cycle count freeze, lines, independent approval and linked quantity adjustments. |
| P8-S10 | Two-sided transfer custody, dispatch/in-transit/acceptance and explicit variance/exception handling. |
| P8-S11 | Quantity/custody reconciliation workbench, bounded Persian-first RTL adapters, migration/shadow checks and focused acceptance closeout. |

### Included

- Only the quantity, reservation, bin, traceability/expiry, count and transfer
  custody capabilities above.
- New dedicated permissions/audit actions required by those capabilities.
- Reuse of current Tenant, project/site scope, Material/UOM, Warehouse,
  Procurement goods-receipt, DMS, Workflow and audit authorities.
- Expand-only compatibility and deterministic synchronous services.

### Explicitly excluded

- Inventory valuation layers, landed cost, price/tax allocation, Inventory-to-GL,
  Inventory-to-Project Cost, Accounting producer registration or journal creation.
- Equipment meter/usage/operator/fuel/downtime/cost allocation; maintenance redesign
  or spare-parts consumption implementation.
- Fixed Asset register, capitalization, depreciation, impairment, transfer or
  disposal.
- Project Cost producer activation or actuals, including all P7 Payroll proposals.
- Background queues, barcode hardware/provider integration, notifications/SMS,
  broad offline sync, production data cutover or production activation.
- Destructive schema contraction or fabricated historical traceability/value.

### Minimum acceptance evidence

- PostgreSQL-backed service/integration tests for permission denial, Tenant and
  project/warehouse isolation, quantity conservation, canonical UOM, traceability,
  reservation over-allocation, expired/quarantined stock, count freeze races,
  dispatch/accept races, retry/idempotency and immutable correction.
- Clean-schema migration/rollback-reapply evidence and no migration drift.
- Reconciliation proves no unexplained quantity difference for the test/pilot
  dataset and reports unknown legacy positions explicitly.
- Negative assertions prove no valuation layer, equipment effect, Fixed Asset,
  journal, Project Cost fact/actual, payable, Treasury/cash, Payroll mutation or
  production behavior is created.
- Django system check, targeted Ruff and documentation reconciliation pass.

## 11. Production-readiness gates preserved

P8-S01–S04 is not production certification. P8-S05–S11, if later authorized and
accepted, also remains non-production until all applicable gates pass:

- accepted Product Owner policy decisions and professional accounting/legal review
  where value, asset or statutory treatment is involved;
- representative Tenant data inventory, exception disposition, migration rehearsal,
  backup/restore and rollback/forward-correction rehearsal;
- concurrency, idempotency, performance and capacity evidence for warehouse-scale
  posting/count/transfer operations;
- least-privilege role review, object-scope and cross-Tenant penetration tests,
  sensitive value/price access review and immutable audit verification;
- reconciliation ownership, close calendar, operating procedures, training,
  support/incident response and monitored production runbooks;
- separately accepted valuation, Accounting, Project Cost, maintenance, spare-part
  and Fixed Asset implementation tranches before any such downstream behavior;
- existing repository-wide production gates for secrets/TLS, object storage,
  dependency locking/security audit, observability, retention/export, backups and
  recovery remain unresolved unless current evidence proves otherwise.

## 12. Exact authorization required for P8-S05–S11

Implementation must not start until the Product Owner supplies an explicit
decision and authorization substantially equivalent to:

> I accept P8-S01–S04 and choose P8-D01 = [A/B/C/D], P8-D02 = [A/B/C/D],
> P8-D03 = [A/B/C], P8-D04 = [A/B/C], P8-D05 = [A/B/C], and P8-D06 = [A/B/C].
> I authorize implementation of P8-S05–S11 only under section 10 of
> `P8_S01_S04_ENTRY_AND_ARCHITECTURE_DECISION_PACKET.md`, including its exclusions,
> migration rules, acceptance evidence and non-production gates. This authorization
> does not include P8-S12+, valuation layers, Equipment cost/usage, Fixed Assets,
> Accounting/GL posting, Project Cost actuals, P7 Payroll proposal consumption,
> production cutover or production activation.

If the Product Owner wishes to defer financial/asset/maintenance decisions, the
authorization must still explicitly record their deferred state and choose P8-D02
and P8-D03 before S07–S11. In that case P8-D01 = D is the safe quantity-only
boundary; P8-D04–D06 remain named gates for their later tranches. Silence, roadmap
placement, acceptance of P7, or acceptance of this packet is not implementation
authorization.
