# CEP-058 execution manifest — 2026-10-19

IMB-0080; standing bounded non-production framework/preparation authority.
Baseline: local main, origin/main and remote main at
`93a42298392b790bd1b18a584518ab032bb375f1`, clean after the authorized
13-file CEP-077 partial-evidence checkpoint. No branch/worktree creation.
Canonical prompt and referenced source hashes are recorded in
`../evidence/CEP-058_ENTRY.json`; local prompts take precedence over recovery.
CEP-025 and CEP-029 are COMPLETE with implemented source/version and identity
services. GATE-06 is an exit gate and remains NOT_PASSED. EXT-0017 does not
block framework Build; it is required before migration execution.

Actual seam: `PayrollYearInterval`, immutable `PayrollResultLine` and
`PayrollCumulativeState`, and `cumulative_services.record_cumulative_for_run`.
The existing target requires a finalized Payroll source line. No external
balance can be made authoritative by synthesizing a Payroll run/result.
Configured loopback Development has zero Payroll years, cumulative states or
finalized/reversed runs; ten WorkRelationships. Payroll migrations through
0008 are installed. No approved historical dataset/mapping/reset/totals packet
has been established. Decision-05 permits operational signed component buckets
only; statutory classification and values remain fail closed.

Bounded implementation: a versioned, read-only preparation service validating
explicit source references against existing finalized source lines, explicit
tenant Payroll-year/Employee/WorkRelationship/component identities, signed
amounts, source versions, exceptions, existing-target references and control
totals. Approval-reference input is a claim, never proof of EXT-0017 approval.
The service cannot execute a backfill, create opening authority or cut over.
Tests use synthetic PostgreSQL fixtures and must prove tenant/object scope,
source/history compatibility, deterministic retry, source/target preservation,
and explicit exception/reconciliation behavior.

Actual intended touch set, recorded before product mutation:

- `apps/payroll/opening_preparation.py` (new read-only service).
- `apps/payroll/test_cep058.py` (synthetic service/isolation/integration tests).
- This execution manifest and `../reports/CEP-058_COMPLETION_REPORT.md`.
- `../evidence/CEP-058_{ENTRY,FRAMEWORK_BUILD,FINDINGS,DOCUMENT_CHECK}.json`.
- `../evidence/CEP-058_{ACCEPTANCE_MAPPING,EVIDENCE_MANIFEST,CHANGE_MANIFEST}.csv`.
- `../evidence/CEP-058_TEST_OUTPUT.txt`, `CEP-058_CHECK_OUTPUT.txt`.
- `CEP_EXECUTION_REGISTRY.yaml` (077 Git reconciliation, 058 lifecycle/frontier).
- `../evidence/CEP-077_GIT_CHECKPOINT.json` (actual checkpoint/review evidence).

Migration Impact BACKFILL; actual migration/backfill NOT EXECUTED. No model,
schema/migration, existing service, setting, permission/grant, endpoint, UI,
dependency or business-data mutation is in this touch set. Preparation test
success cannot satisfy actual migration AC. If required inputs remain absent,
close PARTIAL with all seven actual migration criteria unverified and stop at
the external-input boundary. Preserve CEP-057/065/077 and GATE-05/06/08.

Closeout: EXECUTION PARTIAL, 0/7 actual-migration AC verified. 17 new preparation
and four affected YTD tests PASS; Ruff, Django checks and migration drift PASS.
EXT-0017 remains unresolved; no backfill or business writes. Initial test-fixture
failure is retained in `../evidence/CEP-058_TEST_INITIAL_FAILURE.txt`, an added
evidence-only touch. Full results and STOP are in the Completion Report.
# Synthetic Development execution entry — 2026-10-20

CEP057 has genuinely completed its Development technical AC/DoD and Registry
closeout (67 COMPLETE / 1 PARTIAL / 0 BLOCKED); continue058 serially. Baseline
main/origin0bb5e5f; only attributable057 work is now pending. Immutable058 prompt,
PD031/SPEC013/030 and Decision05, complete025/029 foundations, supplied manifest,
81 source/80 included rows, component controls and explicit year/cutoff verified.
Real-history requirement is N/A — ZERO AUTHORITATIVE DEVELOPMENT HISTORY.

Actual intended touch set BEFORE058 product mutation: `apps/payroll/models.py`
PayrollCumulativeState only; additive nullable native provenance plus mutually
exclusive external opening key/evidence fields and constraints in a new0009
migration; `apps/payroll/opening_import.py`, `test_cep058_import.py` and migration
test; extend existing057/058 fixture runner with058 year/component/import/recovery;
058 report/manifests/findings/evidence and Registry. Existing cumulative/approval/
component services reused; no fabricated finalized Payroll runs/results/lines.
Decision05 signed buckets, explicit year versions and reset semantics remain.
Native source rows stay unchanged; external opening provenance is immutable.
Schema reverse must fail closed once external opening history exists. No endpoint,
UI, new permission, role, default-grant migration, statutory rule or Production
action. Existing operator catalog permissions are transaction-local and restored
before commit, using the existing Platform Admin service and retained audit.
