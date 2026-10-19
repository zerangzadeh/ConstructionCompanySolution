# CEP-023 execution manifest

Baseline main @ ad167f58714577620666a0efb7f5518895cac4a0; HEAD/origin/remote aligned. Existing Registry and CEP-057 adjudication changes retained. Explicit Human remediation authorization is retained in evidence. Prompt original/amended SHA verified in CEP-023_ENTRY.json and manifest. CEP-010 Person/WorkRelationship foundation verified; no CEP-029 conversion inferred. PD-024/026, SPEC-011 recovered from approved consolidated archives cited by CEP-057_ENTRY.json; hashes match retained source proof.

## Actual Execution Touch Set (before product mutation)

- apps/workforce/models.py: import bounded leave models; new apps/workforce/leave_models.py: immutable effective policy and append-only balance/event history linked to WorkRelationship and native LeaveMissionRequest.
- apps/workforce/leave_services.py: policy version recording, explicit policy-bound credits, as-of ledger projection, request reservation, approved-occurrence consumption and evidenced cancellation/reinstatement. No opening balance import.
- apps/timekeeping/services.py: native leave submission/review guards against missing authoritative reservation; mission/overtime behavior retained.
- apps/organizations/models.py, permission_registry.py and one catalog-only migration: explicit leave policy/balance capabilities; no automatic grants.
- apps/workforce/migrations/0014_cep023_leave_authority.py: minimum additive schema; isolated non-production migration checks.
- apps/workforce/test_cep023.py and test_cep023_migration.py: lifecycle, history, as-of, policy absence, invalid transitions, tenant/permission and additive preservation evidence.
- CEP_EXECUTION_REGISTRY.yaml; CEP-023 prompt/manifest migration-only amendment; CEP-023 manifests/evidence/report and retained Human authorization.

No UI, settings, Payroll, ESS balance copy, statutory values, profile-derived policy, Employee conversion or CEP-057 opening backfill. Actual touch set will be reconciled at closeout.

Touch-set refinement: apps/timekeeping/test_p7_s06_s12_timekeeping.py updates the pre-authority free-text approval expectation to fail closed; new lifecycle tests cover the valid authoritative path. Additive migration reverse guard prohibits dropping any populated leave history.

Touch-set refinement before mutation: apps/organizations/role_defaults.py excludes all three new leave capabilities from inferred defaults, following the existing catalog-only pattern. New permissions remain explicitly assigned; no existing grants are changed.

Touch-set refinement before mutation: apps/organizations/configuration_profiles.py updates the stale absence comment only; profile-driven Leave Policy activation remains denied.
