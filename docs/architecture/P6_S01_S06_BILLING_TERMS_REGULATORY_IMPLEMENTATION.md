# P6-S01–S06 Billing Terms and Regulatory Ownership

**Date:** 2026-10-02  
**Status:** Product Owner accepted on 2026-10-03 together with P6-S07–S13,
subject to the current P6-S26–S32 regulatory-governance correction and the open
gates below. P6-S01–S38 is accepted; P6-S39–S42 is implementation complete /
Product Owner acceptance pending; P7 is subsequently Product Owner accepted and
complete within documented non-production boundaries. P8 remains planning-only.

## Authorized boundary

The Product Owner authorized the P6-S01–S06 correction while the product is
pre-production and all stored rows are disposable seed/test data. Consequently,
the migration deliberately discards existing claim/settlement seed rows instead
of converting `BillingPolicy` data. The final migration chain still builds a
valid, constrained schema on a clean database. This exception is not a future
production migration policy.

The approved rules are: immutable `draft → approved → superseded` term/rule
versions; cutoff-date resolution; prospective amendments; contractual rules
before statutory rules; full `Decimal` intermediates and final currency rounding;
no ordinary negative claims; linked correction/revision instead of in-place
history edits; independent author/approver; and immutable party, currency,
version and calculation evidence.

## Implemented ownership

| Owner | Implemented authority |
| --- | --- |
| Tenant Billing | `TenantBillingConfiguration` owns only numbering, period and currency-precision defaults. The obsolete mixed `BillingPolicy` is removed. |
| Contracts | `ContractTermVersion` owns effective retention, advance recovery and contractual-insurance rates/bases/caps. Approval is permissioned, audited, row-locked and author/approver separated. Approved/superseded versions are immutable. |
| Platform policy/regulatory | Existing `PlatformPolicyVersion` owns effective-dated tax/statutory-insurance inputs and retains external-source and accepted review evidence. Under the later accepted P6-S26–S32 correction, national rules resolve directly from effective Platform history by document date and cannot be selected or overridden by Tenants. Missing, unreviewed, unpublished or ineffective rules fail closed. No Iranian value was invented. |
| Billing claim | `ProgressClaim` pins the applicable term/rule versions, immutable `PartyIdentitySnapshot`, currency, Tenant configuration and exact calculation evidence. Later master/configuration changes cannot reinterpret the claim. |

The calculation service resolves eligible versions at the measurement cutoff,
applies contractual deductions/recoveries before statutory adjustments, preserves
four-decimal stored intermediates, applies contract-level caps against prior
approved claims, and performs the final currency-precision rounding. Submitted,
approved and returned histories retain their pinned evidence. Ordinary negative
claims fail closed.

Dedicated `contract_terms.manage/approve` permissions are registered and seeded
to the approved default management roles. Regulatory governance deliberately
reuses the existing Platform Admin provenance/review/publication authority
instead of creating a competing rule model or permission path. Current accepted
governance permits Platform Admin publication while still requiring external
source and accepted review evidence; it supersedes the earlier mandatory
Platform maker-checker assumption. Services enforce Tenant/project scope and
applicable author/approver separation inside transactions; audit events retain
creation and approval evidence.

## Migration and compatibility disposition

Migrations `contracts.0005`, `billing.0006`–`0008` and `organizations.0084`
create the new contract authority, replace the legacy policy, register its
permissions and make claim snapshots required. Regulatory policy reuses the
existing P1-S15 schema and services. `billing.0008` explicitly removes disposable
pre-production claim/settlement rows before enforcing required foreign keys. No
backfill, dual-read, compatibility policy or production rollback bridge was
created because the Product Owner authorized seed reset/recreation.

## Verification and open evidence

- A clean PostgreSQL test-schema migration apply succeeded; six focused Billing
  calculation, rounding, snapshot, SoD and fail-closed tests passed on that schema.
- Seven retained P1-S15 policy-localization tests passed on the migrated schema;
  Django system check, migration-drift check and targeted Ruff checks also pass.
- The repository's pre-existing permission-registry architecture failures remain
  outside this tranche; neither new model nor new permission is missing from the
  registry.
- Actual Iranian tax, insurance, statutory formulas, rates and legal
  interpretations remain unresolved and must have formal legal/accounting evidence
  before an eligible rule version is approved in a real environment.

## Acceptance, supersession and subsequent disposition

The Product Owner accepted P6-S01–S13 on 2026-10-03 based on verified
implementation, validation evidence, current runtime behavior and the accepted
P6-S26–S32 regulatory correction. That correction supersedes this tranche's
original national-rule Tenant-selection and mandatory Platform maker-checker
publication assumptions; it does not alter the accepted contract-term,
calculation, snapshot, scope, history or audit behavior.

P6-S07–S13 implemented
cumulative certification, amendment-aware calculation evidence, linked claim
replacement/cancellation, an explicit opt-in AR source resolver and a dormant
Accounting posting contract. Claim approval still creates no AR or journal.
Taxpayer transmission, Treasury, payable certificates, guarantees, statutory
values, downstream correction reversal and production activation remain later
separately governed slices. Later P6-S14–S38 tranches are now Product Owner
accepted; the historical P6-S14+ authorization boundary no longer states current
status. P6-S39–S42 later proceeded under bounded authorization; P7+ remains
unauthorized.

Acceptance does not include actual Iranian values or legal interpretations,
Article 38 effects, automatic AR or reversal, journals/posting, Treasury/cash,
live transmission/providers/credentials, production activation or a production-
history migration strategy. The six obsolete assertions and two serialized test-
database restore errors remain unresolved. The existing permission-registry gaps
also remain: 19 unregistered models, 12 namespace mismatches and the
`MATERIAL_DOCUMENTS_LINK` enforcement-reference gap.
