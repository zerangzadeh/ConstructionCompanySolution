# P6-S07–S13 Claim Hardening and Financial Handoff

**Date:** 2026-10-03  
**Status:** Product Owner accepted on 2026-10-03 together with P6-S01–S06 and
under the accepted P6-S26–S32 regulatory-governance correction. P6-S01–S38 is
accepted; P6-S39–S42 is implementation complete / Product Owner acceptance
pending; P7 is subsequently Product Owner accepted and complete within documented
non-production boundaries. P8 remains planning-only.

## Delivered boundary

This tranche hardens the receivable `ProgressClaim` flow without activating
automatic finance or production behavior:

- cumulative certified quantity and value are derived across approved claims and
  amended baselines by stable baseline `line_key`;
- the latest eligible verified measurement is reconciled to prior certified
  quantity, current baseline quantity and effective contract ceiling;
- calculation evidence snapshots prior active claims, baseline/amendment values,
  pinned term/regulatory versions, intermediate stages, caps, currency precision,
  line sources and final rounding;
- approved claims are corrected only by linked full replacement or zero-value
  cancellation revisions. Return/revision history remains append-only; approval
  atomically marks the former active claim `superseded` or `cancelled`;
- claim UI exposes cumulative quantities, rates, values, applied versions and
  correction lineage;
- `billing.progress_claim.v1` resolves one active approved IRR claim into an
  immutable receivable-source snapshot. Approval stores an explicit due date
  from the Tenant-local approval date plus pinned `payment_due_days`; the adapter
  reads that stored date rather than inferring one;
- Accounting registers `billing.receivable-claim.approved.v1` as a code-owned,
  non-operational posting contract. It supplies identity and ownership only—no
  line mapping, proposal, journal or post occurs.

## Invariants and failure boundaries

All reads and mutations are Tenant-scoped and permission checked. Claim approval,
correction disposition and audit evidence share one transaction and locked claim
sequence. Corrections fail closed when the original has an active legacy
settlement allocation or any recognized AR obligation; downstream reversal and
replacement orchestration is a later authorized slice. Cancellation creates no AR
source. The resolver rejects inactive status, wrong source version, line-level
keys, nonpositive amount, non-IRR currency and cross-Tenant access.

Claim approval does not call AR or Accounting. AR creation requires an explicit
call to the existing separately permissioned/idempotent subledger recognition
service. The posting contract has `operational_producer=False`; no posting rule
lines or journal producer exist.

## Validation record

Validation on 2026-10-03 applied the migration chain to a clean PostgreSQL test
schema and passed seven focused cumulative/correction/AR/UI tests. Five retained
claim/subledger regression tests also passed. A full Billing run passed 111 tests
and exposed four stale test-contract/fixture failures; after correcting those
tests, all four focused reruns passed. Django system check, migration-drift check,
targeted Ruff and whitespace checks passed. The full suite was not repeated after
test-only corrections because the focused rerun provided the required evidence
without another costly migration/fixture cycle.

The verified migrations were also applied successfully to the configured
`DEBUG=True` PostgreSQL development database. This applied all migrations that
were already pending in that development database, including prior P5/document/
procurement/subledger migrations, and the authorized P6-S01–S06 seed reset removed
legacy claim/settlement seed rows. `migrate --check` and the post-migration Django
system check passed.

## Acceptance and remaining gates

The Product Owner accepted P6-S01–S13 on 2026-10-03 based on verified
implementation, validation evidence and current runtime behavior. The accepted
P6-S26–S32 correction supersedes the earlier national-policy Tenant-selection and
mandatory Platform maker-checker publication assumptions; it does not change this
tranche's cumulative, correction, source-resolution or no-automatic-finance
boundaries. Later P6-S14–S38 tranches are now accepted, so the historical P6-S14+
authorization wording no longer states current status.

Actual Iranian regulatory values and legal interpretations, Article 38 effects,
automatic AR, downstream financial correction/reversal, journal generation or
posting, Treasury/cash, live transmission/providers/credentials, production
activation and production-history migration remain gated. The obsolete six
assertions and two serialized test-database restore errors remain unresolved.
The existing 19 unregistered models, 12 permission namespace mismatches and
`MATERIAL_DOCUMENTS_LINK` enforcement-reference gap also remain outside this
acceptance. P6-S39–S42 later proceeded under bounded authorization; P7+ remains
unauthorized.
