# Human Product Decision — Legacy Payment retired

Source: direct Human Decision Authority instruction in this chat, 2026-10-28.
This supersedes Development-only/zero-population restrictions for migration and
Production bootstrap. Earlier evidence remains historical; no CEP is reopened.

Legacy Payment is retired and absent from the active BONIRA product/domain model.
Its data is not required for current functionality, migration, reconciliation
or Production bootstrap.

- Legacy Payment population must not block Production bootstrap or migration.
- Replace Development-only migration guards preventing migration with legacy rows.
- Do not require zero population for documents 0012 or billing 0018.
- Do not migrate retired data into payment/accounting structures or reconstruct
  accounting semantics. Preserve active Treasury, Accounting and AP/AR boundaries.
- Existing legacy rows are RETIRED_LEGACY_DATA.
- Physical destruction of historical records requires separate retention approval.

Bounded implementation preserves original tables, rows and relationships while
removing obsolete models from Django state. Immutable tenant-scoped DMS/audit
interpretation creates no financial targets. Integrity checks are not population
acceptance, zero-history, twelve-condition or environment gates. Previously
retained snapshots are not rewritten or relabelled in place.

Qualify empty/populated paths with production settings in isolated non-production.
Verify exact original rows, links/audit identities, repeatable retention, inactive
legacy ORM/permissions and unchanged active financial data. Applied migrations are
not replayed. Previously removed Development records are not reconstructed.

This grants no actual Production action, statutory activation, unrelated policy,
final certification, Human Sign-off or Git write.
