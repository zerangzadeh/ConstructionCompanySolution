# P6-S14–S20 Payable Certification Implementation and Closeout

**Date:** 2026-10-03  
**Status:** Product Owner accepted 2026-10-03. P6-S21–S25 was subsequently
accepted; P6-S26–S32 is Product Owner accepted and P6-S33–S38 is implementation
complete/acceptance pending. P6-S39+
remains unauthorized.

## Delivered boundary

This bounded tranche implements subcontract payable certification without
collapsing it into receivable `ProgressClaim` or activating downstream finance:

- the existing `Contract(direction=payable, type=subcontract)`, `ContractItem`,
  `BusinessParty` and `PartyIdentitySnapshot` remain the contract, stable line,
  counterparty and identity authorities;
- `ContractTermVersion` now supports payable subcontracts as well as receivable
  contracts, retaining independent approval, effective dating, supersession and
  immutable approved history;
- `PayableMeasurement` records period and cumulative Decimal quantities against
  one stable `ContractItem` UUID with required evidence and independent
  submit/verify decisions;
- `PayableCertificate`, items and adjustments retain pinned term, party,
  currency, measurement, quantity, rate, cap, calculation, submission and
  decision evidence;
- cumulative certificate calculation subtracts prior active approved quantities,
  enforces each contract-line quantity and effective contract ceiling, applies
  running retention and advance-recovery caps, then evidence-backed back-charges,
  and rounds final money with `ROUND_HALF_UP`;
- return creates a linked draft revision; approved replacement or zero-value
  cancellation closes the prior active version as superseded/cancelled without
  rewriting it;
- dedicated permissions, project scope, row locks, strict maker/checker and
  shared-workflow candidacy protect lifecycle operations. Domain transition,
  work-item completion and audit evidence commit atomically;
- Persian-first RTL measurement and certificate screens support entry,
  verification, creation, calculation review, back-charge evidence, submission,
  approval/return and linked correction testing.

## Financial handoff boundary

`billing.payable_certificate.v1` resolves one active approved IRR certificate
into an immutable payable `ObligationSourceSnapshot`. Accounting registers
`billing.payable-certificate.approved.v1` as a code-owned, non-operational
posting contract. Both are explicit contracts only:

- certificate approval never calls AP, Accounting, Project Cost, Treasury or
  Payments;
- AP recognition remains an explicit call to the existing separately
  permissioned and idempotent subledger service;
- a recognized AP obligation blocks certificate replacement/cancellation until
  a separately authorized downstream reversal path exists;
- cancellation certificates are zero-value and cannot resolve as AP sources;
- no posting-rule lines, journal producer, cash action or automatic payable
  recognition is present.

## Schema, permissions and workflow

- `billing.0011` creates payable measurement/certificate/item/adjustment models,
  indexes and database caps/uniqueness constraints on the clean pre-production
  schema.
- `organizations.0085` creates eight payable measurement/certificate permission
  codes and default management-role grants; the permission registry and object-
  scope namespace are updated in the same change.
- `workflows.0024` registers the code-owned payable-certificate subject, workflow
  type and strict separation starter template. The submitter has no self-approval
  fallback.

## Verified acceptance evidence

The clean PostgreSQL test schema was rebuilt from the complete migration chain,
including `billing.0011`, `organizations.0085` and `workflows.0024`. On that
freshly rebuilt schema, 10 payable tests plus five retained receivable/financial-
boundary regressions passed (`15 passed`); the complete payable module, including
an end-to-end operational UI mutation test, then passed (`11 passed`). They cover
Decimal calculation, stable line and measurement evidence, cumulative quantities, contract ceilings,
retention/advance caps, back-charges, return/revision and replacement/cancellation
lineage, immutability, permissions, Tenant isolation, workflow candidacy/SoD,
audit atomicity, explicit AP recognition, correction blocking, dormant posting
identity, RTL views and concurrent duplicate-period prevention. Django system
check, migration-drift check and targeted Ruff check/format also passed.

## Product Owner acceptance

The Product Owner accepted P6-S14–S20 on 2026-10-03 based on the verified
implementation, validation evidence and boundaries recorded in this packet.
This acceptance did not itself authorize P6-S21+ or any gated production,
Accounting, Treasury, statutory, guarantee, clearance, retention-release,
claims/EOT or taxpayer-integration behavior. P6-S21–S25 later proceeded under a
separate bounded authorization.

## Assumptions and open gates

- A zero contractual cap means zero recoverable amount, matching the existing
  receivable calculation convention. Rates and caps are contract facts; no
  Iranian statutory value or interpretation is inferred.
- Contract amendment valuation remains the existing immutable approved
  `value_change` authority. P6-S14–S20 does not add contractual variation,
  change-order, claim or EOT semantics.
- Back-charges are certificate deductions with mandatory evidence; they do not
  create a separate claim, expense, payable, cost fact or journal.
- At this S14–S20 closeout, retention release, guarantees, insurance/clearance and
  Article 38 behavior were not implemented. P6-S21–S25 later implemented only the
  bounded evidence/exposure/release controls in its separate packet; Article 38
  interpretation/effects remain gated.
- Automatic AP recognition, downstream AP reversal/replacement, posting/journal
  production, Treasury/cash, external integration and production activation
  remain gated.

## Historical handoff and current successor state

This closeout itself authorized no further P6 session. P6-S21–S25 was later
authorized, implemented and accepted under a separate bounded instruction and is recorded in the
[guarantee/clearance/release implementation packet](P6_S21_S25_GUARANTEE_CLEARANCE_RELEASE_IMPLEMENTATION.md).
P6-S26–S32 subsequently proceeded under its own bounded authorization and is
implementation complete/acceptance pending; see the
[taxpayer/contractor-compliance packet](P6_S26_S32_TAXPAYER_CONTRACTOR_COMPLIANCE_IMPLEMENTATION.md).
P6-S33–S38 subsequently proceeded under separate authorization. P6-S39+ remains
unauthorized.
