# CEP-029 execution manifest

Baseline main @ 61fad0cb61e72411322fe74686c67f70834ceac8; origin/remote aligned; clean working tree. CEP-023 original AC/DoD are newly proved COMPLETE and pushed. CEP-029 prompt SHA verified (unchanged); CEP-010 foundation and PD-025/SPEC-009 confirmed from approved consolidated archives. Explicit Human authorization reopens existing IMB-0070 only. DATA-MIGRATION authority permits minimum bounded non-production conversion/history/reconciliation. Exit GATE-06 is not entry authorization and is not inferred PASS.

## Actual Execution Touch Set (before product mutation)

- apps/workforce/models.py and new identity_migration_models.py: one append-only tenant migration-run result with source fingerprint, count/mapping/exception evidence and actor/time. Existing Employee/Person/WorkRelationship models and assignment histories retained.
- apps/workforce/identity_migration.py: versioned atomic conversion/rehearsal; source-evidenced current episodes; explicit existing Person mapping only; source history ambiguity becomes exception. Preserve existing targets; stable repeat semantics; per-source failures roll back target writes.
- apps/workforce/migrations/0015_cep029_identity_migration.py: minimum additive run-reconciliation schema, no automatic backfill or cutover.
- apps/workforce/test_cep029.py: permission/tenant/lifecycle, source/assignment preservation, counts/map/exception/rehire evidence, repeatability and transactional rollback/reapply.
- Registry; CEP-029 manifests/evidence/report; configured Development schema-only apply and authorized per-tenant evidence-backed conversion after rehearsal. No synthetic employment history or User/ESS activation; no existing target rewrites/deletes; no CEP-057 balance import.

Rollback boundary: rehearsal and failed attempts roll back atomically; committed source/target history is retained, never erased. Corrections require new explicit source evidence; downstream cutover is not authorized.

Actual test surface refined: apps/workforce/test_cep029_migration.py provides bounded additive schema preservation and transactional rehearsal/rollback/reapply evidence. Existing Employee status AuditEvent fingerprints qualify source history changes; no new audit action or default grant is introduced.
