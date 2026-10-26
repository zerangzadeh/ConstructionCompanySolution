# CEP-012 current Development requalification — 2026-10-26

Baseline: existing `main` / `961e3fd942c668337012c22d42f59545c5e9fc0a`,
equal to local `origin/main`. Existing dirty files belong to prior work and are
preserved. Current Human instruction explicitly authorizes bounded Development
preservation proof and repair of attributable Development defects. Standing
authority and the canonical CEP-012 Scope/AC/DoD apply. All nine relevant prompt
hashes (012, 069..076) match the manifest. No Git writes or production activity.

Actual touch set before mutation:

- `apps/audit/migrations/0016_membership_provisioned_action.py`: retain legacy
  invitation/acceptance events unchanged instead of deleting them.
- `apps/billing/migrations/0008_p6_s01_s06_seed_reset_and_required_snapshots.py`:
  preserve claims, revisions and allocations; preflight existing required
  snapshot references and report explicit exceptions instead of deleting rows
  or inventing historical snapshots.
- `apps/billing/migrations/0006_tenantbillingconfiguration_and_more.py`:
  preserve the original claim policy JSON by renaming its column to the existing
  billing-configuration snapshot field. This pre-mutation touch-set extension
  addresses the same claim-history preservation outcome; final schema is unchanged.
  Historical JSON is retained verbatim, without interpreting it as current policy.
- `scripts/cep012_preservation_proof.py`: reproducible PostgreSQL synthetic
  fixtures, actual affected migration operations, reconciliation, retry,
  rollback/reapply and rejection evidence in a disposable Development database.
- CEP-012 manifests/report/CSV evidence; additive Registry updates and GATE-06
  evaluation; CEP-073 entry/verification artifacts only after its gate qualifies.

The affected historical migration files are not already dirty. Changes repair
future traversal; they cannot reconstruct history already deleted by a previous
execution. No production migration, destructive source-data operation, new schema
design, business backfill rule, authority transfer, or current statutory value.
Snapshot gaps fail closed with source UUIDs and missing/invalid fields. Existing
finalized history and references are never updated by the repair.

Required proof: actual PostgreSQL operations; before/after full-row comparison;
stable identifiers/tenant/actor/financial/revision context; explicit exceptions;
repeatability; transaction rollback and schema reverse/reapply; existing service
regression; lint and system checks. Equivalent fresh proof is allowed by the
canonical evidence contract; no historical execution result is reconstructed.
