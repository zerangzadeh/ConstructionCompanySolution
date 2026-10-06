# P8-S18–S23 Equipment Operations Architecture and Product Owner Decision Packet

**Prepared:** 2026-10-05  
**Status:** P8-E01–E22 = A and **P8-S18–S23 = Product Owner accepted** (2026-10-05). P8-S01–S17 Product Owner acceptance is recorded in `ROADMAP.md` and the P8-S12–S17 packet.  
**Scope:** P8-S18–S23 only: Equipment operational extensions.  
**Authority boundary:** No model, migration, permission catalogue, runtime UI, workflow, Inventory mutation, Accounting/GL posting, Project Cost actual, Fixed Asset, capitalization, depreciation, P7 Payroll proposal consumption, production cutover/activation, or P8-S24+ work is authorized by this packet.

## 1. Session decomposition

| Session | Proposed bounded result when separately authorized | Explicitly excluded |
| --- | --- | --- |
| P8-S18 | Equipment operational-event foundation: meter types/readings, immutable reading corrections, and deployment/assignment compatibility review | Financial cost, fuel stock movement, asset register, automatic project cost |
| P8-S19 | Equipment-operator qualification relationship, validity/expiry evidence references, and approved operational usage/runtime capture | Workforce permission grants, payroll/timekeeping consumption, legal certification interpretation |
| P8-S20 | Fuel-log operational evidence and downtime incident/interval lifecycle, including availability-state interaction | Inventory fuel decrement/revaluation, fuel valuation, emissions/tax calculation, financial actuals |
| P8-S21 | Maintenance plan and work-order lifecycle, scheduling triggers from approved meter/time rules, work execution and maintenance evidence | Automatic purchasing, supplier liability, Accounting posting, capitalization |
| P8-S22 | Maintenance spare-part request/reference linkage to authoritative Inventory issue/return transactions, reconciliation and correction paths | Equipment-created stock reservation, issue, return, adjustment, valuation, or custody mutation |
| P8-S23 | Persian-first RTL operational workbench/evidence views, authorization/SoD hardening, migration rehearsal, concurrency/idempotency and acceptance evidence | Production cutover/activation, P8-S24+, downstream financial consumer activation |

Each session is independently gated. Later sessions require the preceding accepted data/lifecycle contract but no session may broaden its boundary by inference.

## 2. Ownership and one-way data flow

| Fact/action | Owner | Boundary |
| --- | --- | --- |
| Equipment identity, operational status, deployment, meter, usage, downtime, operator-equipment qualification, maintenance plan/work/evidence | Equipment | Equipment owns the operational record and its immutable history. Existing `EquipmentAssignment` and `MaintenanceRecord` history is preserved. |
| Material master, spare-part quantity/custody/reservation/traceability, issue/return and valuation | Inventory | A maintenance work order may reference an authoritative Inventory transaction; Equipment never writes or revalues stock. |
| Employee identity, employment/workforce qualification evidence | Workforce | Equipment stores a scoped operational authorization/qualification relationship or immutable reference/snapshot; it does not alter employee qualification authority or create payroll facts. |
| Journal, accounts, liability, recognized expense/capital asset accounting | Accounting | Equipment operational costs and fuel quantities are not journals, postings, capitalization basis, depreciation basis, or accounting actuals. |
| Project Cost actual and classification | Project Controls | Equipment may later propose a source envelope only under separate authorization; no P8-S18–S23 event creates an actual. |
| Asset register, carrying amount, depreciation, impairment, disposal | future Fixed Assets | Equipment `ownership_type`/`acquired_on` and operations must not be mistaken for a fixed-asset fact. |

Permitted lineage is strictly reference-only:

`Equipment maintenance work order -> maintenance spare-part reference -> posted Inventory issue/return transaction -> Inventory-owned quantity/value history`.

The reference must include organization, maintenance work-order public identifier, Inventory transaction public identifier, material, direction, quantity/UOM snapshot, transaction status/version and link actor/time. It cannot duplicate an editable stock balance, on-hand amount, unit value, or Inventory lifecycle. Inventory remains the source for current transaction status and correction/reversal lineage.

## 3. Conceptual relationships and invariants

Future concepts, not schema commitments, are:

| Concept | Key relationships / invariant |
| --- | --- |
| `EquipmentMeter` / `MeterReading` | One equipment can have multiple typed meters. A finalized reading has observed-at, unit, source/evidence, actor, stable external/retry key and sequence/order key. It is immutable; an erroneous reading is superseded by a linked correction, never edited. Readings for the same meter must be monotonic unless a reviewed replacement/reset event explains the discontinuity. |
| `EquipmentDeployment` | The existing assignment is the compatibility authority until an expand-only migration maps it. An active operational event must resolve an effective Equipment deployment or explicitly record an unassigned/exception context; project/site must share tenant and site must belong to project. |
| `OperatorEquipmentQualification` | Links Equipment (or approved equipment class) to an Employee and Workforce-owned qualification/evidence snapshot, effective period and operational status. It routes eligibility only; position/qualification never grants a business permission. |
| `EquipmentUsageLog` | References equipment, operational date/time interval or finalized meter delta, deployment context, operator (optional only where policy permits), purpose and evidence. It cannot overlap incompatibly for the same equipment and source identity. |
| `FuelLog` | Equipment-owned observed dispensing/consumption evidence: date/time, quantity/UOM, meter/deployment, supplier/document reference and optional Inventory transaction reference. Fuel quantity is operational; price/cost stays descriptive and has no valuation or financial effect. |
| `DowntimeEvent` | Equipment, classification/reason, start/end, deployment impact, evidence and linked maintenance work order(s). Open intervals prevent contradictory availability and must be resolved/cancelled through controlled lifecycle actions. |
| `MaintenancePlan` / `MaintenanceWorkOrder` | A plan is versioned and scheduled by time/meter condition; a work order captures one execution lifecycle. Finalized completion snapshots the plan/rule, readings, work, evidence and linked spare-part references. |
| `MaintenanceEvidence` | Immutable typed DMS link/reference plus metadata, captured by/from actor and time. It does not create a second document store and completion may require evidence by policy. |
| `MaintenanceSparePartReference` | A line-level Equipment reference to one final/posted Inventory issue/return transaction and its source-line identity. Duplicate active links and mismatched tenant/material/UOM/direction fail closed. Inventory correction becomes visible in Equipment; Equipment does not repair it. |

All concepts are tenant-scoped, use UUID public identifiers, preserve actor/timestamps, and validate same organization at every relationship. Operational “cost” fields (including the legacy `MaintenanceRecord.cost`) are optional descriptive evidence only and must be labelled non-financial; no new cost field carries accounting, project-cost, capitalization, depreciation, or Inventory-value authority.

## 4. Lifecycle, workflow, correction and audit model

| Aggregate | Proposed lifecycle | Correction rule |
| --- | --- | --- |
| Meter/usage/fuel observation | captured -> validated -> finalized -> superseded/voided | Finalized observation is append-only; correction links an explicit reason and prior observation. |
| Deployment | scheduled -> active -> completed/cancelled | Preserve existing conflict-safe assignment history; no final-history edit. |
| Downtime | reported -> triaged -> active -> resolved/cancelled | Close with end/evidence; correction is a linked event, never silent interval rewrite. |
| Qualification relationship | proposed -> verified -> active -> expired/suspended/revoked | Effective-date change creates successor/revocation evidence; Workforce source remains intact. |
| Maintenance plan | draft -> reviewed -> active -> superseded/retired | Published plan/rule is versioned; later changes do not change prior work orders. |
| Maintenance work order | draft -> scheduled -> released -> in-progress -> completed -> closed; cancelled before completion | Completion locks execution, meter/evidence/spare references. Post-completion correction is a controlled corrective/reopen successor, never ordinary edit. |
| Spare-part reference | pending Inventory confirmation -> linked -> reconciled; unlinked/exception | Inventory transaction reversal/return/correction creates a visible Equipment exception or linked reference change; Equipment cannot alter Inventory history. |

Workflow is optional and must reuse the existing bounded Work Management runtime only where a Product Owner-approved lifecycle requires approval. The Equipment service remains the domain authority; workflow cannot generically mutate status. At minimum, completion/reopen, meter reset/replacement, qualification override, and spare-reference exception disposition require auditable reason and configured reviewer/SoD control.

Audit evidence must record organization, public IDs, actor, time, previous/new state, reason, source/version/evidence identifiers, deployment/project/site context, policy/rule version, correlation ID and idempotency key. Audit is append-only at the application layer and minimizes restricted employee/qualification and commercial evidence data.

## 5. Authorization and separation of duties

Future runtime must introduce dedicated default-deny `BusinessPermissionCode`s through the normal registry/data-migration/default-role process; this packet creates none. Proposed codes are `equipment.meter.reading.record`, `equipment.meter.reading.correct`, `equipment.usage.record`, `equipment.fuel.record`, `equipment.downtime.manage`, `equipment.qualification.manage`, `equipment.maintenance.plan.manage`, `equipment.maintenance.work.manage`, `equipment.maintenance.complete`, `equipment.maintenance.reopen`, `equipment.maintenance.evidence.view`, `equipment.maintenance.evidence.manage`, `equipment.spare_link.manage`, `equipment.spare_link.reconcile`, and `equipment.operations.audit.view`.

Every read/mutation resolves active organization from membership and checks tenant state, permission and project/site object scope at the view and service boundary. UI visibility, position, work-item candidacy, assignment, operator qualification, or a supplied organization identifier grants nothing. Sensitive qualification/evidence and fuel/commercial-document references need separately restricted viewing.

Recommended minimum SoD: the person who captures a reading/fuel/usage record cannot approve its correction; the person completing a maintenance work order cannot independently approve a reopen or material spare-link exception; a person who records an Inventory issue/return cannot act as the Equipment-side exception approver for the same link where such review is configured. Smaller tenants may use an explicitly accepted, audited self-approval exception only; it must never be implicit.

## 6. Idempotency, locking and failure behavior

- Capture commands require a stable client/source idempotency key scoped to organization, aggregate and action; same key/same payload returns the original result, and a different payload fails closed.
- Finalization locks Equipment, relevant meter(s), active deployment/usage/downtime interval, maintenance work order and linked reference rows in a deterministic order, re-reads state and re-checks authorization inside `transaction.atomic()`.
- Meter order, overlapping usage/downtime, active maintenance uniqueness, deployment overlap and duplicate Inventory transaction/line links must have database constraints where possible and service checks otherwise.
- Inventory linkage is read/validate/reference only. The integration fails closed if the Inventory transaction is absent, cross-tenant, not in a permitted final state, material/UOM/direction mismatches, or a returned/reversed status cannot be reconciled.
- Concurrent correction, completion or duplicate external/mobile submission must leave one authoritative result plus auditable conflict/duplicate evidence. No retries may write a downstream financial fact.

## 7. Migration and historical-data assumptions

Use expand -> map/backfill -> validate -> switch only after a later authorization. Retain existing `Equipment`, `EquipmentAssignment` and `MaintenanceRecord` unchanged as historical operational records. Map legacy assignments to a new deployment only if every tenant/project/site/date relationship validates; otherwise retain and mark a migration exception. Existing maintenance records are history, not automatically completed work orders, evidence, meter readings, costs, spare usage or financial facts.

Do not infer meters, runtime, fuel, operator qualification, downtime, maintenance plan, parts consumption, unit cost, Inventory issue/return, capitalization, depreciation, Accounting posting, or Project Cost actual from legacy notes/cost fields. An opening meter reading, active downtime, open work order, active qualification and active deployment requires verified source evidence, preparer/reviewer, effective timestamp and exception disposition. Unverified records remain unavailable or explicitly migrated as legacy read-only evidence. Rehearsals use isolated non-production data and reconcile counts/identifiers without modifying production history.

## 8. UI and evidence requirements

The later UI is Persian-first RTL, mobile-first and evidence-led: large capture controls; explicit unit, timestamp and source; offline/duplicate-submission state only if separately accepted; accessible status/reason/error text; localized calendar/timezone presentation while persisting timezone-aware timestamps. It must show meter order/reset reason, active deployment, qualification eligibility without exposing restricted Workforce details, downtime interval, work-order state, immutable correction lineage, DMS evidence availability, and Inventory transaction links/status.

The UI must label descriptive cost as non-financial and visibly distinguish an Inventory link from a stock mutation, a Project Cost actual, an Accounting journal or a Fixed Asset fact. It must never promise that saving a maintenance item consumed parts, posted fuel cost, capitalized equipment, or created a project actual.

## 9. Product Owner decision register

| ID / decision | Options | Recommended option | Operational consequence | Affects |
| --- | --- | --- | --- | --- |
| E01 meter types | A: configurable bounded catalog per tenant; B: free text; C: one universal hour meter | **A** | Supports hours/km/cycles while preserving validation and reporting. | Runtime, migration |
| E02 meter monotonicity/reset | A: final readings monotonic; reviewed reset/replacement event; B: arbitrary edits | **A** | Retains reliable runtime and service history. | Runtime, audit |
| E03 reading source | A: manual/mobile plus optional imported source key; B: manual only; C: device integration now | **A** | Allows auditable capture without committing an integration. | Runtime, idempotency |
| E04 usage evidence | A: meter delta preferred with interval fallback; B: free-form hours only; C: meter only | **A** | Covers valid operations while exposing non-meter exceptions. | Runtime, UI |
| E05 deployment evolution | A: retain `EquipmentAssignment`, expand/migrate to compatible operational deployment; B: replace history; C: separate unlinked model | **A** | Preserves accepted conflict-safe assignment lineage. | Migration, runtime |
| E06 unassigned operations | A: allow only reviewed exception; B: prohibit always; C: allow silently | **A** | Captures emergencies without losing accountability. | Runtime, permissions |
| E07 operator eligibility | A: Equipment relationship snapshots Workforce qualification/evidence; B: Equipment owns duplicate certificate; C: no check | **A** | Workforce remains source; Equipment can validate operational suitability. | Runtime, migration, permissions |
| E08 qualification expiry | A: block new assignment/operation after expiry, retain history; B: warn only; C: invalidate history | **A** | Fail-closed future operation while preserving evidence. | Runtime, permissions |
| E09 fuel source | A: operational fuel log with optional Inventory reference; B: Inventory transaction automatically created; C: descriptive note only | **A** | Records use without stealing Inventory authority. | Runtime, Inventory boundary |
| E10 fuel cost | A: quantity/evidence only; any cost explicitly descriptive; B: derive WAC; C: create project actual | **A** | Preserves all financial boundaries. | Downstream financial boundary |
| E11 downtime model | A: reason-coded lifecycle and non-overlapping intervals; B: status-only; C: free text | **A** | Enables availability/maintenance evidence without financial claims. | Runtime, UI |
| E12 maintenance aggregate | A: versioned plan + work order, retain legacy record history; B: enhance record in place; C: only logs | **A** | Supports preventive scheduling and immutable execution. | Runtime, migration |
| E13 schedule trigger | A: approved calendar/meter rules generate draft due work; B: auto-complete work; C: no scheduling | **A** | Operational reminder/queue only, never an automatic completion. | Runtime, workflow |
| E14 completion evidence | A: policy-required typed DMS evidence and readings where applicable; B: optional all evidence; C: upload copies | **A** | Reuses DMS and proves work without duplicate storage. | Runtime, UI |
| E15 spare-part linkage grain | A: one Equipment reference per authoritative Inventory transaction line; B: copied parts/cost line; C: maintenance decrements stock | **A** | Exact lineage without parallel quantity/value authority. | Runtime, Inventory boundary |
| E16 inventory-link timing | A: link only posted/final issue/return; B: link reservations; C: create issue at completion | **A** | Avoids falsely claiming stock movement; reservation needs a later Inventory-led contract. | Runtime, Inventory boundary |
| E17 spare correction | A: Inventory reversal/return drives Equipment exception/reconciliation; B: Equipment edits Inventory; C: ignore changes | **A** | Keeps correction with Inventory while exposing operational impact. | Runtime, Inventory boundary, audit |
| E18 descriptive cost | A: retain labelled non-financial optional field; B: remove all costs; C: make actual automatically | **A** | Preserves useful operational notes with no financial authority. | Migration, downstream financial boundary |
| E19 maintenance approval/SoD | A: completion/reopen and exception review separated, narrow self-approval exception; B: maker self-approves; C: no review | **A** | Protects finalized service and parts evidence. | Permissions, runtime |
| E20 downstream handoff | A: no financial handoff in this tranche; later explicit immutable proposal only; B: automatic actual/journal | **A** | Maintains Project Controls/Accounting authority. | Downstream financial boundary |
| E21 legacy migration | A: verified opening facts only; retain unverified legacy read-only; B: infer from notes/cost; C: discard history | **A** | Prevents fabricated operational/financial history. | Migration |
| E22 release | A: non-production verification then separate production decision; B: activate with implementation | **A** | Keeps cutover, support and recovery gates explicit. | Runtime scope, production |

## 10. Validation and acceptance criteria for later implementation

Later runtime authorization must require focused PostgreSQL coverage for tenant isolation, active/suspended/cancelled tenant behavior, permission and object-scope denial, SoD, UUID/public-id boundaries, meter monotonicity/reset and correction lineage, duplicate/retry behavior, concurrent finalization, assignment/usage/downtime overlap, qualification expiry, plan/work-order state transitions, evidence access, Inventory issue/return linkage and correction reconciliation, no Inventory write by Equipment, no financial/asset/project-cost effect, and migration rehearsal exceptions.

Acceptance additionally requires clean-schema migration apply/rollback evidence, retained Equipment/Inventory regressions, `manage.py check`, targeted Ruff/format checks, Persian RTL/mobile/accessibility review, audit review, DMS unavailable behavior, performance/concurrency evidence, recovery/runbook rehearsal, and a Product Owner review of every selected E01–E22 option. No broad production claim follows from passing those tests.

## 11. Implementation acceptance evidence (2026-10-05)

The focused PostgreSQL acceptance module, `apps/equipment/test_p8_s18_s23.py`, passed **10 tests**. It covers meter correction/idempotency, usage/fuel, Workforce-authoritative qualification validity and tenant/operator scope, downtime, plans/work-order lifecycle, evidence/audit, posted Inventory issue/reversal reference linkage, rejection of unposted/cross-tenant/duplicate/foreign-work-order links, Inventory non-mutation, RTL workbench/forms/navigation, permission-aware visibility and mutation denial, project/site deployment scope, and the absence of Accounting/GL, Project Cost, Fixed Asset and Inventory valuation effects.

Acceptance coverage found and corrected two bounded defects: a foreign Inventory transaction is now rejected as an authorization boundary rather than an unhandled lookup, and `MaintenanceSparePartReference.quantity_snapshot` now retains the authoritative Inventory transaction's four-decimal quantity. `equipment.0004_maintenancesparepartreference_quantity_snapshot_precision` is expand-only and changes no Inventory, Accounting, Project Controls or Fixed Asset authority.

An isolated clean PostgreSQL schema applied the complete graph (344 migrations), including Organizations `0098` and Equipment `0002`–`0004`. The new Equipment `0004` was safely rolled back to `0003` and reapplied. Django system checks, migration-drift detection, targeted Ruff/format checks and `git diff --check` passed.

Product Owner acceptance was recorded on 2026-10-05 for the completed P8-S18–S23 operational scope: meters and corrections, usage/fuel evidence, Workforce-owned qualification references, deployment/project/site scope, downtime, plans/work orders/evidence, audit, Inventory reference-only spare links, Persian-first RTL operations flows, and the documented isolation, idempotency, concurrency and immutable-history controls. This acceptance does not authorize P8-S24+, Inventory mutation or valuation, Accounting/GL posting, Project Cost actuals, Fixed Assets, capitalization/depreciation, Payroll proposal consumption, production cutover or production activation.

## 12. Preserved gates and exact bounded runtime authorization

**Subsequent disposition:** P8-S18–S23 is accepted as recorded. P8-C01–C38=A and
the bounded P8-S24–S27 runtime are subsequently Product Owner accepted under
`P8_S24_S27_EQUIPMENT_COST_AND_FIXED_ASSETS_DECISION_PACKET.md`.

Production remains gated by data-quality reconciliation, support/recovery and backup restoration evidence, security/privacy review, authorization/SoD audit, DMS availability behavior, migration rehearsal, performance/concurrency evidence, Inventory owner acceptance of the reference contract, separately accepted Accounting and Project Controls consumer contracts, and a distinct Product Owner cutover/activation decision.

After explicit acceptance of E01–E22, a later runtime authorization must be substantially equivalent to:

> I accept `P8_S18_S23_EQUIPMENT_OPERATIONS_DECISION_PACKET.md` and select E01–E22 as recorded, except for any expressly named deviation. I authorize implementation of P8-S18–S23 only: Equipment-owned operational meter readings, usage/runtime, fuel evidence, operator/equipment operational qualification relationships, deployment, downtime, maintenance plans/work orders/evidence, and reference-only lineage to authoritative posted Inventory spare-part issue/return transactions; with the packet's tenant isolation, permissions, SoD, audit, idempotency, locking, correction, migration, UI, validation and non-production boundaries. This authorization does not authorize P8-S24+, any Inventory quantity/custody/reservation/traceability/valuation mutation, Equipment financial actuals, Accounting/GL posting, Project Cost actual creation, Fixed Assets, capitalization, depreciation, P7 Payroll proposal consumption, production cutover, or production activation.

Silence does not authorize a deviation, downstream financial effect, or production activity.
