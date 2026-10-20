# CEP-058 — EXECUTION COMPLETE (synthetic Development) — 2026-10-20

IMB-0080; **7/7 technical AC verified; scoped DoD PASS**. The finalized real-history
reconciliation subclause is **N/A — ZERO AUTHORITATIVE DEVELOPMENT HISTORY** under
`DEV-SYNTHETIC-DATA-AUTH-20261020-V2`; it is not a PASS or fabricated real history.
This current closeout supersedes the dated partial observations below.

CEP057 completed before058 product mutation. Baseline main/origin
`0bb5e5f63bc0aeb0e7c327d232264d1647c2b981`; only attributable057 work accumulated,
and seven unrelated untracked paths remain preserved. Canonical058 SHA,
PD031/SPEC013/030, Decision05 and completed025/029 foundations verified in
[grounding](../evidence/CEP-057_058_SYNTHETIC_GROUNDING.json). The supplied manifest
and 13 members, six exact CSV schemas, internal counts, component/kind controls,
correction lineage, currency/dates and synthetic-only authority validate.

[Executed reconciliation](../evidence/CEP-058_SYNTHETIC_EXECUTION.json): **81
source rows →80 immutable YTD targets +1 excluded superseded predecessor;
IRR 56,574,280,000.00 signed control; zero unresolved source exceptions**. The10
approved UUID-sorted identity mappings retain each of their four tenants. Thirty-two
exact-code Development components were created through canonical component
services, using supplied operational kinds, with no statutory rules/rates. Four
approved Payroll year-v2 records bind 2026-01-01..2026-12-31, as-of2026-09-30,
continuation2026-10-01, IRR. Canonical draft versioning retains a non-authoritative
v1 draft scaffold for each supplied v2 binding; only v2 is approved.

The minimum additive 0009 schema extends the existing PayrollCumulativeState
authority with mutually exclusive native-line or external-opening provenance,
unique stable opening keys and immutable source evidence. Native history is
retained. **No Payroll run/result/line was fabricated**, and no second financial
authority, posting, settlement or Project Cost fact was created. Existing signed
Decision05 buckets and explicit year reset remain governing. The signed grand
control includes employer amounts; it is not inferred take-home pay or a statutory
liability. Source row DEV-PAY-CORR-0001 remains SUPERSEDED/NO with 188,000,000
evidence; reciprocal replacement DEV-PAY-0027 alone contributes 238,000,000.

All source IDs map to stable target references or explicit exclusion. Exact retry
creates zero targets and rejects changed facts or changed year/currency. Actual
Development insert/rollback/retry and compensating rollback/recovery rehearsals
passed; native cumulative projections return the imported opening balances. Native
continuation adds to these same balances, rejects overlap with opening coverage,
and resets only through explicit year selection. No target history is overwritten.
The fixture operator uses the existing Platform Admin catalog service with locked,
transaction-local permissions restored exactly before commit; retained audit and
operator receipts prove zero persistent grant changes. No role or permission rule
is invented or bypassed.

[Final focused checks](../evidence/CEP-058_SYNTHETIC_TESTS.txt): **40 passed,
27 subtests passed**, including 17 import/lineage/security/recovery/continuation
tests, 17 retained preparation tests, 4 existing YTD tests and 2 real schema
rollback/reapply tests. The schema tests preserve five native cumulative states
and their finalized sources, and prove destructive rollback is blocked with real
external history. [Affected regression](../evidence/CEP-058_SYNTHETIC_AFFECTED_TESTS.txt):
**100 passed, 34 subtests passed; 1 BASELINE TEST DEBT failure** in the existing core
Payroll registry test. The exact failure reproduces with unmodified HEAD product
sources using an in-memory Git loader. [Attribution](../evidence/CEP-058_SYNTHETIC_REGRESSION_ATTRIBUTION.json)
identifies the already-unregistered `payroll.StatutorySourcePackage`; neither the
model set, permission registry nor failing test was changed. This adjacent defect
is recorded, with no repair absorbed into057/058. No full regression PASS claimed.

[Ruff/format, Django and migration-drift checks](../evidence/CEP-058_SYNTHETIC_CHECKS.txt)
PASS. [Configured Development0009 migration](../evidence/CEP-058_SYNTHETIC_MIGRATION.txt)
PASS. No required in-scope failure remains. The closure script's initial CSV header
assumption was corrected to preserve058's existing acceptance-mapping schema;
documents and Registry were reconciled before final checkpoint.

All six DoD obligations are evidenced: target outcome within approved Development
applicability, versioned migration, source/target and exceptions, retained history,
documented/exercised recovery, migration/repeatability tests. Recovery before any
subsequent bucket use: call `reverse_payroll_opening` on the tenant's mapped
originals; it appends exact inverse states and retains both origins. Repeating
rollback is idempotent; an import cannot reactivate a reversed opening. Subsequent
history requires explicit reconciliation. Do not delete immutable states or
reverse 0009 once external history exists; its reverse guard fails closed.

Registry:057 and058 COMPLETE; **V1=68 COMPLETE /0 PARTIAL /0 BLOCKED**. GATE06
is separately evaluated without inferring global PASS from counts. Browser/load/
concurrency runtime remains non-blocking UTV. Production action/cutover,
Production Certification and Human Sign-off NOT_EXECUTED;069..079 not executed.
Authorized attributable add/commit/push is pending the combined Git checkpoint;
no new branch/worktree, merge/rebase/reset/clean/stash/force push.

## Historical framework and intake records

# CEP-058 — EXECUTION PARTIAL

2026-10-19. IMB-0080 only. **0/7 actual migration AC verified; DoD not met.**
The independent non-production framework is implemented and tested. Actual
historical/opening backfill remains blocked by EXT-0017. No migration, source
import, authority cutover, business-data mutation or production action occurred.

## Authority and entry

Baseline: existing local main / origin/main / remote main at
`93a42298392b790bd1b18a584518ab032bb375f1`; clean before this CEP's manifest.
That authorized 13-file checkpoint retained CEP-077 partial runtime/failure
evidence. [Checkpoint evidence](../evidence/CEP-077_GIT_CHECKPOINT.json)
reconciles its actual Git state without changing its AC, DoD or blocker.

The [entry review](../evidence/CEP-058_ENTRY.json) records verified local prompt
SHA, recovery archive/member identities, canonical dependencies and frontier.
CEP-025 and CEP-029 are COMPLETE with actual YTD and identity services. Standing
bounded authority permits framework Build independently of CEP-057/065/077.
EXT-0017 blocks actual migration; GATE-06 is the exit gate, not a prerequisite
invented for preparation. PD-031, SPEC-013/030 and approved Decision-05 remain
governing. No statutory classification, reset date, source approval or amount was
inferred. Package-card historical generic mechanics do not override current
governance or the current local prompt.

## Implemented boundary

`apps/payroll/opening_preparation.py` is a versioned read-only service over
existing finalized Payroll source lines and cumulative targets. It checks
explicit tenant Payroll-year, source/version, Employee/WorkRelationship linkage,
component and signed amount; reports stable source/target references, exceptions
and per-component control totals; and produces deterministic evidence on retry.
Existing finalized reversals retain their source-provided negative amounts.
Existing target discrepancies remain exceptions and are never silently repaired.

The service checks Payroll-results permission, current membership and object
scope before returning any source detail. It uses the existing Payroll read
capability; no endpoint, new role, default grant or permission catalogue is
introduced. An approval-reference input remains an unverified claim. Coverage is
the supplied rows, never an inferred eligible source population. Successful
candidate validation always leaves approval, migration and cutover authority
false and target/business writes zero. This is preparation, not an executable
backfill or an alternative opening authority.

Existing targets require finalized source-line lineage. External historical
balances must not be represented by fabricated Payroll runs/results. Actual
source mapping and any necessary later target contract require their governing
evidence and bounded scope review. No new schema was needed for preparation.

## Validation and evidence

- **21/21 PASS:** 17 new preparation tests and four existing CEP-025 source/YTD
  tests on the configured disposable PostgreSQL test database. Coverage includes
  actual source-to-target service integration, immutable-history preservation,
  reversal compatibility, retry/reordering, missing/cross-tenant references,
  permission/membership/scope denial, source/reset/as-of validation, exact money,
  duplicate sources, exceptions and totals. These are synthetic preparation
  proofs, not approved-dataset migration evidence.
- Initial run: 19 passed, one test setup errored because it attempted an update
  rejected by the existing immutable-target guard. The corrected fixture creates
  a valid legacy target without a WorkRelationship; preparation reports the
  discrepancy without repair. [Original failure retained](../evidence/CEP-058_TEST_INITIAL_FAILURE.txt).
  This was new test-fixture debt, not a product regression or ignored failure.
- [Final test output](../evidence/CEP-058_TEST_OUTPUT.txt) and
  [checks](../evidence/CEP-058_CHECK_OUTPUT.txt): Ruff checks/format, Django system
  check and dry-run migration drift PASS. No schema files generated or applied.
- Configured loopback Development aggregate counts remain zero Payroll years,
  zero approved years, zero cumulative states and zero finalized/reversed runs;
  ten WorkRelationships. Payroll migrations through 0008 were already installed.
  Only aggregate reads were made; no actual Payroll record/dataset was invented.
- Actual migration output, source-target population reconciliation, backfill
  repeatability, transactional migration/rollback and cutover remain unverified.
  Browser/accessibility, performance/concurrency, current statutory activation,
  Human Sign-off and production certification remain UTV / NOT EXECUTED.

See [acceptance mapping](../evidence/CEP-058_ACCEPTANCE_MAPPING.csv),
[evidence manifest](../evidence/CEP-058_EVIDENCE_MANIFEST.csv),
[build provenance](../evidence/CEP-058_FRAMEWORK_BUILD.json) and
[Finding-001](../evidence/CEP-058_FINDINGS.json).

## Blocker and closeout

**CEP-058-FINDING-001 / BLOCKER-EXTERNAL-DATA:** establish EXT-0017's approved
historical dataset, explicit source/Employee/WorkRelationship mapping,
cumulative classification, approved versioned Payroll-year/reset interval and
reconciliation totals. Current development has no approved year or finalized
history to migrate. Actual source preparation/approval cannot be inferred from
test fixtures or a nonempty reference string. Re-ground against the supplied
packet, resolve exceptions and review the actual target/execution contract
before any backfill. No actual migration execution path was added in this turn.

Registry synchronized: **57 COMPLETE, 5 PARTIAL, 1 other entry-blocked, 16 other
NOT_STARTED, 7 Post-V1 deferred**. CEP-057 remains PARTIAL 0/7 with EXT-0015;
CEP-065 remains BLOCKED; CEP-077 remains PARTIAL with its DNS blocker and unchanged
failure hashes, without an acquisition retry. GATE-05/06/08 remain NOT_PASSED.
No gate, Human decision, financial authority or dependency topology changed.

Serial execution stops at the material EXT-0017 boundary. Frontier is recomputed
in the Registry; conditional CEP-068/073/079 and externally conditioned CEP-078
need their own complete entry reviews. None is claimed fully eligible by a
dependency-ready list. No next CEP was started after this PARTIAL closeout.

Actual touch set: two new Payroll Python files, this report/manifest, evidence
listed in the change manifest, and Registry lifecycle/Git/frontier metadata.
Migration Impact BACKFILL; actual schema/backfill/import/cutover NOT EXECUTED.
Git add/commit/push are authorized for this session; record their actual results
only after checkpointing. Branch/worktree creation, merge/rebase/cherry-pick,
reset/clean/stash/force/history rewrite: NOT EXECUTED. Human Sign-off, Production
Certification and Production Cutover: NOT EXECUTED.

Checkpoint addendum: the authorized 16-file preparation/evidence checkpoint
`b412b09cc9f42c73f67007d13de9305353a8fae3` was committed, pushed to origin main
and verified against local main/origin/remote with a clean tree before the next
CEP entry review. Add/commit/push EXECUTED; no merge. PARTIAL, 0/7 migration AC,
EXT-0017 and all production boundaries are unchanged. On the Human's subsequent
continuation instruction, independent CEP-068 overtime entry was reviewed under
its explicit conditional dependency semantics; no Payroll backfill was resumed.


## Source discovery and data intake — 2026-10-20

Current `main = origin/main = e15c877dcf81cd3cb408c15aa55ec965db9ad4bc` after fetch. Canonical prompt hash
reverified. [Discovery evidence](../supporting/v1-data-intake/DISCOVERY_AND_VALIDATION.json)
records current read-only Development counts, approved recovery identities and
reused foundations. All 10 CEP-029 crosswalk rows still match their tenant,
Employee, Person and WorkRelationship targets. Decision-05 remains approved; no
identity foundation, operational YTD category/reset mechanism or Treasury
authority is reopened. No authoritative tenant opening packet was found in the
inspected repository, retained supporting files, seed/reference code or approved
canonical recovery sources.

The [complete intake kit](../supporting/v1-data-intake/README.md) and
[HR-CEP058 response form](../supporting/v1-data-intake/CEP058_HUMAN_INPUT.md)
provide exact missing source/policy-or-year/cutoff/controls and conditional
external-key mappings. Header-only templates contain no source values.
**EXECUTION PARTIAL; 0/7 actual migration AC; DoD not met.** EXT-0017
remains unresolved. No actual import/backfill, business writes, target synthesis,
retry/rollback/cutover, application tests, Gate change or production action.
Documentation validation covers CSV schema/header emptiness, all field mappings,
references, unchanged canonical hashes and Registry state/count preservation.
Application tests were not rerun for documentation-only work. Safe attributable
add/commit/push is explicitly authorized by the current Human instruction; the
resulting checkpoint is established by Git history. Pre-existing untracked Human
artifacts, including the resolution pack, remain untouched and unstaged.
