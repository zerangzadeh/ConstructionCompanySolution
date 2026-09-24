# F6 — Billing & Progress Claims delivered architecture

> Original architecture approved 2026-09-19; implementation status reconciled
> 2026-09-23. F6.1-F6.6 are delivered as the receivable Billing baseline.
> `ROADMAP.md` controls portfolio status; models, migrations, services, and tests
> remain the current behavior source of truth.

## Entry gate and existing boundaries

F5 W6 is recorded as complete in `ROADMAP.md` and
`TENANT_WORKFLOW_AND_WORK_MANAGEMENT.md`: a fresh PostgreSQL 18.6 suite passed
469 tests and 69 subtests, repository-wide Ruff check/format passed, and the W6
migration, rollback, routing-volume, concurrency, tenant, and recovery gates are
recorded as passed. This is historical handoff evidence rather than the current
repository test count. F6 subsequently adopted the shared runtime and workbench.

Current `Contract` has a direction, project, party snapshot, header value, and
draft-only terms. Approved `ContractAmendment.value_change` is separate and does
not overwrite the header. `ContractItem` provides quantities, units, prices,
and optional WBS mapping, but its sum is not the authoritative contract value.
`Project` has WBS and activities; daily progress observations are not certified
measurements. `Payment` is posted cash, and `PaymentAllocation` allocates it to
a contract; void/reversal retains history. The F6 entities below now exist in
`apps/billing`; this paragraph records their upstream boundaries.

## Ownership and data model

The F6 domain owns measurement, claim calculation, and claim history. Contract,
project, payment, audit, and F5 workflow services retain their current authority.
All new persisted records have UUID identity, organization, timestamps, actor
provenance, tenant-consistent foreign keys, and database uniqueness/check
constraints where possible. Implemented entities:

| Entity | Required relationship and durable data | Lifecycle |
| --- | --- | --- |
| `ProjectBaseline` | Project, one receivable contract, numbered version, effective date, approved contract/amendment snapshot, measurement policy, approval evidence; unique `(organization, contract, version)` | `draft → approved → superseded`; draft may be withdrawn. Approved content is immutable. One current approved baseline per contract. |
| `BaselineItem` | Baseline, stable line key, optional `ContractItem` and WBS/activity, description, unit, planned quantity, unit rate, planned value; ordered and unique within baseline | Draft-only edit; immutable with approved baseline. Explicit unpriced/lump-sum lines require a defined valuation rule. |
| `ProgressRecord` | Baseline/version, baseline item, measurement date/period, measured quantity this period and cumulative quantity, evidence/source, recorder/verifier, correction link | `draft → submitted → verified` or `rejected`; rejected is terminal. Verified content is immutable; correction creates a linked replacement/reversal. |
| `ProgressClaim` | Project, receivable contract, baseline version, claim number and revision, period/cutoff, policy JSON snapshot, gross/adjustment/net totals, submission JSON snapshot, submit/approve/return evidence, and returned-revision link. The current schema does not have dedicated party/currency snapshot fields. | `draft → submitted → approved` or `returned`; return creates a linked later draft revision. Approved/returned versions are immutable. Settlement is derived, not an editable lifecycle state. |
| `ProgressClaimItem` | Claim revision, baseline item and verified progress sources, previous cumulative quantity/value, current quantity/value, new cumulative quantity/value, unit/rate snapshots | Draft-only edit; frozen at submission, retained with final claim. Unique baseline item within claim revision. |
| `ClaimAdjustment` | Claim revision, typed reason, signed amount or snapshotted rate/base, sequence, evidence, optional reference to prior retention/advance balance | Draft-only edit; frozen at submission. Types include retention, retention release, tax, insurance, advance recovery, penalty, and documented other. |
| `ClaimSettlementAllocation` | Approved claim, existing active receipt-side `PaymentAllocation`, applied amount, actor/time, reason and reversal evidence | Append allocation then reverse; never changes cash or contract allocation history. |

The baseline is a *commercial measurement snapshot*, not an edit to the
contract. Approval requires an active receivable contract and verifies its
effective ceiling as header value plus approved amendments at that cutoff.
Later amendments require a new baseline version; previous claims stay pinned.
Baseline items need an explicit reconciliation to the contract ceiling, with a
documented allowance/unpriced balance. An item link alone never silently makes
the sum of contract items authoritative. Only approved baselines and verified
progress may feed an approved claim. Historical claim revisions and sources are
never reparented to a newer baseline.

## Calculation and reconciliation rules

- Use `Decimal` throughout. Quantities have four decimal places and money two,
  matching current contract/payment fields; reject binary floats and excess
  precision. Store rates and bases explicitly. Quantize each monetary line with
  `ROUND_HALF_UP`, then sum the rounded lines; quantize each adjustment once.
  Define any residual rounding line explicitly, never hide it in a claim total.
- For each baseline item: `current quantity = latest verified cumulative −
  previous approved cumulative`; `current gross = current quantity × snapped
  unit rate`. The claim snapshots prior, current, and new cumulative figures.
  Prevent negative quantities, double inclusion of one progress source, and
  cumulative quantity/value above the approved baseline without a new version
  or explicit approved variation. Reject overlapping approved claim periods.
- `gross = sum(current line amounts)`. Each adjustment has a sign convention:
  deductions negative; releases/additions positive. `net certified = gross +
  sum(adjustments)`. Tax and insurance are distinct typed rows with recorded
  statutory/contract basis and rate; F6 does not infer a legal rate. Retention
  and advance recovery have contract-scoped running balances, caps, and explicit
  releases. `net certified` must be nonnegative unless a separate approved
  corrective claim policy is adopted.
- Track *certified receivable* separately from cash. Approved claim totals may
  not exceed the effective contract ceiling after prior approved claims and
  approved amendments, unless an explicit contract variance policy is approved.
  Lock the contract/baseline and relevant claim sequence during approval.
- Settlement consumes only posted, nonvoid `Payment` receipts whose active
  `PaymentAllocation` targets the same organization, project, receivable
  contract, and compatible party. The sum of claim allocations cannot exceed
  either that active contract allocation or the claim's unpaid approved net.
  Payment void or allocation reversal reverses dependent claim allocations
  atomically or blocks the operation until reversal is recorded. Outstanding =
  approved net − active claim settlement allocations. No synthetic `Payment`.

## Security, workflow, and history

Resolve organization from active membership. Validate organization, project,
contract, baseline, progress, claim, payment, party, and optional WBS/activity
hierarchy at view and service boundaries. Deny cross-tenant reads/writes and
inactive/suspended tenant mutations; use scoped queries and database guards for
critical foreign-key invariants. A project position routes work but grants no
business permission.

Introduce explicit F6 permissions in `BusinessPermissionCode`,
`permission_registry`, default-role catalog migration, views, and services:
baseline view/manage/approve; progress view/record/verify; claim view/create/
submit/approve/revise; settlement view/allocate/reverse. Sensitive view and
export paths require object-level checks. Approval rechecks active membership,
permission, current state, current assignment/candidacy, separation rules,
figures, and source versions inside a row-locked transaction.

Register baseline approval, actionable progress verification, and claim approval
as bounded F5 workflow types with code-owned subject adapters and domain
commands in their owning packages. Publish a
small-tenant starter route with owner/member fallback; optional position/project
routing may be configured. Use existing `WorkflowInstance`, `WorkItem`,
candidate/delegation/history, and centralized workbench. Domain services remain
the only place that certifies measurements or approves a claim. Domain change,
workflow advancement, work-item completion, and append-only audit event commit
together. Pinned published versions and completed history cannot be rewritten.
Idempotency keys and row locks prevent duplicate approvals, revisions, and
allocations. Corrections use new revisions, adjustments, or reversals with actor,
timestamp, reason, and source links.

## Current implemented boundary and pre-production corrections

The delivered receivable flow is valuable, but it is not yet the target legal,
commercial, or accounting boundary:

- `BillingPolicy` is one mutable row per organization. It mixes numbering,
  period, precision, tax/insurance settings, and contract-specific retention and
  advance recovery. Before a real claim, split these concerns: approved contract
  term versions own retention/advance/other commercial deductions;
  effective-dated reviewed regulatory rule sets own statutory behavior; tenant
  configuration owns numbering/display defaults. Historical claims retain the
  exact applied versions and calculation snapshot.
- The submission JSON freezes implemented claim/item/adjustment values, but there
  are no dedicated party/currency snapshot fields. The target decision must make
  counterparty, currency, rounding, contract-term version, and regulatory-rule
  version explicit and queryable where legal/accounting history requires it.
- Billing currently creates a certified operational receivable and settlement
  evidence only. It does not create AR, a journal, tax-system invoice, or Treasury
  transaction. Future integrations must use idempotent registered posting/
  transmission contracts and reconciliation; Django signals must not post.
- Payable/subcontractor certificates, guarantee/clearance management, retention
  release certificates, and full Article 38 handling remain future scope.
- Project/site object-scope authorization is not yet first-class. Tenant
  permission, workflow assignment/candidacy, and UI filtering do not substitute
  for that future access boundary.

These are **pre-production correction candidates** in
`PRODUCT_CAPABILITY_AND_READINESS_AUDIT.md` and `ROADMAP.md`; this document does
not authorize their implementation.

## Original package decisions and delivery record

1. Contract measurement policy: require a fully priced baseline or allow a
   documented lump-sum/unpriced balance; define permitted ceiling variance.
2. Commercial rules: organization currency precision if it differs from two
   decimals; exact tax/insurance bases, rates, rounding order, retention and
   advance caps, and whether negative corrective claims are supported.
3. Claim numbering and period policy: per contract or organization, calendar
   boundary, partial-period handling, and treatment of late measurements.
4. **Resolved for F6.4.** A submitted claim is approved or returned by the
   preparer's primary-position manager, but only when that active membership has
   `claims.approve`. `Position.parent_position` is the explicit organizational
   hierarchy routing source for this package; it routes responsibility and never
   grants permission. The preparer is excluded while any other eligible
   approver exists. If the hierarchy has no eligible manager, the starter route
   selects another active member with `claims.approve`; only when none exists
   may a small-tenant owner approve their own submission. Returning a claim is
   terminal for the submitted revision and atomically creates a linked draft
   revision; the submitted snapshot is never reopened or altered. Progress
   verification remains a distinct mandatory work item.
5. **Resolved for F6.5.** A posted receipt recorded before claim approval may be
   manually linked after approval to an existing `PaymentAllocation`; no cash
   payment is synthesized and no FIFO rule applies. Party identity must be
   present on both receipt and contract and match by `BusinessParty` ID;
   name-only or missing-party matches are rejected. Partial amounts are chosen
   manually and capped by both claim outstanding and allocation remainder.
   Retention release is supported through `ClaimAdjustment`; a separate
   certificate remains an independent, unimplemented capability.

Items 4 and 5 record the delivered F6 decisions. Items 1-3 were implemented
through the current baseline/policy design but require renewed product,
accounting, and legal decisions before the pre-production policy correction or
regulatory integration. Do not hardcode changing assumptions into migrations or
posted history.

## Independent implementation packages

| Package | Dependency and deliverable | Acceptance / test gate |
| --- | --- | --- |
| F6.1 — Baseline | F5 gate plus decisions 1–2. Add F6 ownership, permissions, `ProjectBaseline`/`BaselineItem`, draft/approval, immutable versioning, and baseline approval through F5. | PostgreSQL migrations/rollback, ceiling and approved-amendment reconciliation, same-tenant hierarchy, concurrent single-current approval, role/candidacy and archive tests, atomic workflow/audit rollback. |
| F6.2 — Progress measurement | F6.1 plus decisions 3–4. Add `ProgressRecord`, verified cumulative source ledger, correction path, and F5 verification work items. | Quantity precision, date/period and duplicate-source constraints, no over-measurement, immutable verified records, tenant/permission/candidacy/race tests and atomic rollback. |
| F6.3 — Claim calculation | F6.1–F6.2 plus decisions 1–3. Add draft claim/revision/items/adjustments and pure Decimal calculation service; no submission, approval, or cash mutation. | Golden arithmetic cases for each adjustment, rounding, cumulative/current split, amendment cutoff, period overlap, negative/over-ceiling rejection, draft recalculation consistency. |
| F6.4 — Approval and workbench | F6.3 plus decision 4 and F5 runtime. Add submission/frozen snapshots; register starter workflow, adapters, commands, and approval transitions. | Small-tenant and configured multi-stage routing, permission plus candidacy, separation, tenant isolation, retry/race, immutable submitted snapshots, atomic domain/work-item/audit rollback, published-version immutability. |
| F6.5 — Settlement | F6.4 plus decision 5. Add claim-to-existing-contract-allocation linkage and outstanding read model. | Receipt direction/party/contract checks, partial and concurrent cap enforcement, void/reversal propagation, immutable history, no cash duplication, reconciliation against payment read model. |
| F6.6 — UI and operational handoff | F6.1–F6.5. Add responsive RTL baseline/progress/claim/settlement views, workbench links, scoped reports and recovery guidance. | End-to-end tenant/role/CSRF checks, mobile layouts, query budgets, demo records, fresh PostgreSQL suite, Django check, Ruff check and format. |

The table above is the historical delivery decomposition; all six slices are now
implemented. It must not be read as approval for the correction candidates or
commercial/accounting extensions listed above. No legacy contract, billing, or
payment field is contracted away without a separately approved expand/migrate/
switch/validate/contract plan.
