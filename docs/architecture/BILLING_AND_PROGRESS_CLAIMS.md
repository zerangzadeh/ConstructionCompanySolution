# F6 — Billing & Progress Claims delivered architecture

> Original architecture approved 2026-09-19; implementation status reconciled
> 2026-10-03. F6.1-F6.6 and P6-S01–S38 ownership, cumulative-correction,
> guarantee/clearance/release and explicit financial-handoff work are delivered
> for separate receivable claims, payable subcontract certificates, and
> contract-commercial controls.
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
| `TenantBillingConfiguration` | Tenant numbering, period and currency-precision defaults only; no commercial or statutory rule ownership | Mutable Tenant configuration; each claim snapshots the applied values. |
| `ContractTermVersion` | Receivable contract or payable subcontract, version/effective date, payment-due days, retention, advance recovery and contractual-insurance bases/rates/caps, plus an explicit retention-release requirement and cap, creator and independent approval evidence | `draft → approved → superseded`; approved/superseded content is immutable and remains historically resolvable. Payable use is limited to `Contract(direction=payable, type=subcontract)`. Release is fail-closed while its requirement is unconfigured. |
| `PlatformPolicyVersion` | Effective-dated national tax/statutory-insurance bases/rates with external-source and accepted-review evidence; runtime resolves the effective Platform version directly by document date | Existing draft/published/retired policy lifecycle under Platform Admin governance. National rules cannot be selected or overridden by Tenants. Missing, unreviewed, unpublished or ineffective applicability fails closed. |
| `ProgressClaim` | Project, receivable contract, baseline, claim/revision and period/cutoff; pinned contract-term and regulatory-rule versions; immutable party-identity and currency evidence; Tenant-configuration and exact calculation snapshots; totals and submission/decision evidence; optional correction target/kind/reason | `draft → submitted → approved` or `returned`; return creates a linked later draft revision. An approved replacement/cancellation changes the prior active claim to `superseded`/`cancelled` without rewriting it. Final versions are immutable. Settlement is derived, not an editable lifecycle state. |
| `ProgressClaimItem` | Claim revision, baseline item and verified progress sources, previous cumulative quantity/value, current quantity/value, new cumulative quantity/value, unit/rate snapshots | Draft-only edit; frozen at submission, retained with final claim. Unique baseline item within claim revision. |
| `ClaimAdjustment` | Claim revision, typed reason, signed amount or snapshotted rate/base, sequence, evidence, optional reference to prior retention/advance balance | Draft-only edit; frozen at submission. Types include retention, retention release, tax, insurance, advance recovery, penalty, and documented other. |
| `ClaimSettlementAllocation` | Approved claim, existing active receipt-side `PaymentAllocation`, applied amount, actor/time, reason and reversal evidence | Append allocation then reverse; never changes cash or contract allocation history. |
| `PayableMeasurement` | Project, payable subcontract and `ContractItem`; period/cumulative Decimal quantity, measurement date, evidence reference and maker/checker provenance | `draft → submitted → verified` or `rejected`; terminal evidence is immutable. Verification locks the stable contract line and rechecks the cumulative sequence and line cap. |
| `PayableCertificate` | Project, payable subcontract, number/revision/period/cutoff, pinned payable term and party-identity versions, currency, exact calculation/submission/decision snapshots, totals and optional correction lineage | `draft → submitted → approved` or `returned`; return creates a linked draft revision. Approved replacement/cancellation closes the prior active version without rewriting it. |
| `PayableCertificateItem` | Certificate, stable `ContractItem` UUID, verified measurement, prior/current/new cumulative quantities, unit-rate and amount snapshots | Draft calculation evidence; frozen at submission and retained with final history. |
| `PayableCertificateAdjustment` | Certificate, ordered retention/advance recovery or evidence-backed back-charge, rate/base/amount snapshots and evidence reference | Contractual deductions are regenerated only in draft; back-charges require explicit evidence. Submitted/final adjustments are immutable. |
| `ContractGuarantee` | Contract/project/counterparty snapshot; stable series and version; bid/performance/advance-payment/retention type; explicit issued/received exposure side; currency/amount; dated or explicitly open-ended validity; pinned clean DMS version; linked correction/renewal/release and decision evidence | `draft → submitted → active` or `returned`; approved correction/renewal supersedes an active predecessor without rewriting it. Due dated versions become `expired`; approved release evidence closes the active version as `released`. |
| `ContractComplianceEvidence` | Contract/project/counterparty snapshot; stable series/version; insurance or clearance kind; reference/issuer; effective date; dated or explicitly open-ended validity; pinned clean DMS version and review evidence | `draft → submitted → approved` or `returned`; approved correction/renewal preserves and supersedes prior active history. Due dated evidence becomes `expired`. It has no inferred statutory or financial effect. |
| `RetentionRelease` | Payable subcontract, pinned approved term and party snapshot, linked DMS evidence, optional pinned approved clearance, retained/prior/available Decimal snapshots, amount and correction lineage | `draft → submitted → approved` or `returned`; approved replacement/cancellation supersedes/cancels the prior active release without rewriting it. It is a commercial release fact, not AP, payment or journal. |
| `TaxpayerInvoice` | One approved receivable claim; Tenant/project/contract/party and reviewed effective policy; original/correction/cancellation lineage; schema/tax-code, Decimal amounts, preflight, submission and decision snapshots | `draft → submitted → approved` or `returned`; an approved correction/cancellation closes its predecessor without rewriting commercial-source or finalized invoice history. |
| `ContractorComplianceAssessment` | One approved payable certificate; Tenant/project/contract/party and reviewed effective policy; insurance basis/rate/deduction facts; optional pinned approved effective clearance; calculation/submission/decision snapshots | `draft → submitted → approved` or `returned`; it is evidence only and has no AP, journal, cost, Treasury or cash effect. |
| `StatutorySubmissionEvidence` / `StatutorySubmissionResolution` | Exactly one taxpayer invoice or contractor assessment; immutable request hash/payload, schema/provider, idempotency and correlation IDs, retry lineage, response/error and append-only human resolution | Export or explicitly supplied test-adapter attempts only. Accepted/exported evidence prevents duplicates; retry requires failed evidence plus human authorization. No source-document or subledger mutation. |

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

- Use `Decimal` throughout. Preserve four-decimal stored intermediates, apply
  contract-level caps, then round final gross/net outputs with `ROUND_HALF_UP` to
  the snapshotted claim-currency precision. Reject binary floats. Store bases,
  rates, intermediate stages and final outputs explicitly.
- For each baseline item: `current quantity = latest verified cumulative −
  previous approved cumulative`; `current gross = current quantity × snapped
  unit rate`. The claim snapshots prior, current, and new cumulative figures.
  Prevent negative quantities, double inclusion of one progress source, and
  cumulative quantity/value above the approved baseline without a new version
  or explicit approved variation. Reject overlapping approved claim periods.
- `gross → contractual deductions/recoveries → statutory adjustments → final
  monetary rounding` is the canonical order. Each adjustment has explicit type,
  basis, rate and sign. Billing never infers a statutory value. Retention and
  advance recovery use contract-scoped running caps. Ordinary negative claims are
  prohibited; reductions use linked corrective/cancellation history.
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

P6-S14–S20 adds separate payable-measurement view/record/verify and payable-
certificate view/create/revise/submit/approve permissions. Measurement uses
direct maker-checker separation. Certificate decisions additionally require an
active shared-workflow candidate and exclude the submitter without a self-
approval fallback.

P6-S26–S32 adds dedicated taxpayer-invoice and contractor-compliance view,
prepare, submit and approve permissions plus statutory-submission execute and
resolve permissions. Invoice and assessment decisions use the same shared
workflow runtime with strict submitter/approver separation. Attempt creation is
Tenant-locked and idempotent; human retry resolution is append-only.

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

## Current implemented boundary and remaining integrations

The delivered receivable flow is valuable, but it is not yet the target legal,
commercial, or accounting boundary:

- P6-S01–S06 removed the mixed `BillingPolicy`. Tenant configuration and Contract
  term versions are separate authorities; under the accepted P6-S26–S32
  correction, national regulatory inputs resolve directly from the reviewed
  effective `PlatformPolicyVersion` without Tenant selection. Claims explicitly
  pin the applied versions, immutable party
  identity, currency, configuration and calculation evidence.
- This pre-production migration intentionally discarded existing seed claim data;
  it is not precedent for a production history migration. See
  `P6_S01_S06_BILLING_TERMS_REGULATORY_IMPLEMENTATION.md`.
- P6-S07–S13 calculates cumulative certified quantities across baseline versions
  by stable line key, snapshots prior claims/amendments/rounding, preserves linked
  replacement/cancellation history, and exposes the evidence in the claim UI. See
  `P6_S07_S13_CLAIM_HARDENING_AND_HANDOFF.md`.
- Billing registers an explicit approved-claim AR source adapter and a code-owned
  non-operational Accounting posting contract. Approval itself creates neither an
  AR obligation nor a journal. AR recognition remains a separately permissioned,
  idempotent service action; journal line mapping/posting is still absent. A claim
  with recognized AR or active legacy settlement fails closed for correction until
  the downstream evidence has a controlled resolution path. Django signals do not
  post.
- P6-S14–S20 implements payable-subcontract terms, measured work, cumulative
  certificate calculation, capped retention/advance recovery, evidence-backed
  back-charges, linked corrections and RTL lifecycle UI. It uses stable
  `ContractItem` UUID identity and does not reuse receivable `ProgressClaim`.
- `billing.payable_certificate.v1` is an explicit AP source adapter and its
  Accounting contract is non-operational. Approval creates no obligation,
  proposal, journal, Project Cost fact, Treasury action or cash movement. Any
  recognized AP obligation blocks source correction until a future authorized
  downstream resolution exists.
- P6-S21–S25 implements contract-linked guarantees, versioned insurance/
  clearance evidence, expiry/renewal/release history, non-netted issued/received
  exposure and contract-authorized retention release. Missing authority, unsafe
  document evidence, expired required clearance or insufficient retained balance
  fails closed. No Article 38 interpretation or financial effect is inferred.
- P6-S26–S32 implements policy-pinned taxpayer-invoice original/correction/
  cancellation history, contractor-insurance deduction and clearance facts,
  schema preflight, immutable export/test-adapter evidence, correlation IDs,
  idempotent retry with human resolution and source-to-attempt reconciliation.
  Policy application fails closed without an effective published version,
  external source and accepted review. No official Iranian value or schema is
  seeded, and no Article 38 or financial effect is inferred.
- P6-S33–S38 implements separate Contracts-owned Site Instruction, Variation/
  Change Order, contractual Claim and EOT evidence. A verified `ProgressRecord`
  or `PayableMeasurement` may be referenced through an append-only typed link,
  but the contractual approval neither changes that measurement nor creates or
  modifies a `ProgressClaim`, `PayableCertificate`, AP/AR fact or journal.

P3-S27-Q01 now accepts an approved immutable `ProgressClaim` revision through
`billing.progress_claim.v1`. Recognition date is the Tenant-local approval date;
approval stores an explicit due date using the pinned
`ContractTermVersion.payment_due_days`, and the adapter reads that stored fact. Party, tax,
currency, calculation, submission and approval evidence are snapshotted. Missing,
nonpositive, non-IRR, inactive, cancelled, cross-Tenant or version-mismatched facts
fail closed. No AP source is selected.

The separate receivable-claim and payable-certificate engines, explicit AR/AP
source handoffs and bounded taxpayer/contractor statutory-evidence layer are
implemented. Automatic obligation recognition, posting proposals/journals,
downstream financial correction reversal, official provider transmission,
legal/accounting activation and production activation remain Roadmap-gated.

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

P6-S01–S32 resolves items 2 and 3 for the bounded receivable/payable certificate
and statutory-evidence foundation:
the Product Owner fixed calculation order, cutoff-date applicability, final
currency rounding, nonnegative ordinary claims, version lifecycle and SoD. Actual
Iranian statutory values and interpretations remain evidence-gated; no changing
rate or formula is hardcoded. P6-S26–S32 applies only policy facts backed by an
external source and accepted review. Item 1, automatic finance/posting,
downstream correction reversal, live provider transmission and the remaining
integrations retain their Roadmap gates.

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
