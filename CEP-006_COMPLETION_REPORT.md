# CEP-006 completion report — AUTH-BATCH-002

**Execution status:** EXECUTION PARTIAL — blocked before product mutation by `CEP-006-FINDING-001 / BLOCKER-PD`. See [execution manifest](CEP-006_EXECUTION_MANIFEST.md).

- Repository: local `main` at `533fbd52e38dd448973ba4cc618e5faa44b01fec`; unrelated dirty-tree changes preserved.
- Canonical sources: CEP-006 prompt recovered from the approved consolidated handoff pack; repository catalogue, native models, and P10 reconciliation decision packet checked.
- Actual execution touch set and product files changed: **NONE**. This report and the execution manifest are the only new files.
- Migration required/executed: **UNDETERMINED / NONE**. The existing native run records do not contain all declared comparison-grain fields; no model or migration change was attempted.
- Acceptance Criteria: **0/16 verified**. IMB-0044 current-state policy is unresolved; IMB-0048 and IMB-0066 were not implemented after the blocker.
- Scoped Definition of Done: **NOT MET**.
- Focused tests, required regression, Ruff/lint, Django/system checks, migration drift: **NOT RUN**; no implementation was available to validate.
- Baseline/test-infrastructure failures and CEP regressions: **NONE OBSERVED**; tests were not run.
- Unauthorized product semantics: **NONE INTRODUCED**.
- Operational-scale performance: **UTV**.
- Required resolution: Product Owner/source owners must approve the exact current native-run selection, supersession, grain and source-version policy, and resolve whether Migration Impact `NONE` is viable. The serial queue stops here. CEP-009, CEP-011 and CEP-013 are **NOT STARTED**.
- Git writes, Human Sign-off, UAT/Production Certification, and Production actions: **NOT EXECUTED**.

## 2026-10-15 resume disposition

**Execution status remains EXECUTION PARTIAL.** The approved [PD-033 current-state decision](docs/architecture/BONIRA_PD_033_RECONCILIATION_CURRENT_STATE.md) closes the policy-selection question but triggers its explicit no-guess stop condition for `subledger_gl` and `treasury_gl` (`CEP-006-FINDING-002 / BLOCKER-SPEC`). Native grain mapping is unverified for these pairs; current-run selection, deterministic ordering, source-version traceability, supersession, repeated-snapshot prevention, and historical-retention behavior were not implemented or tested. Schema change and migration: **NONE**. AC: **0/16 PASS**; scoped DoD: **PARTIAL / NOT MET**. No product semantics or new regression was introduced. The serial queue stops before CEP-009.

## 2026-10-15 final reauthorization disposition

**Execution status remains EXECUTION PARTIAL — blocked before mutation.** The final Human reauthorization permits source-owned prospective evidence and bounded migration work, but implementation grounding found `CEP-006-FINDING-003 / BLOCKER-PD`: no authoritative, persisted Subledger AP/AR-to-GL control-account mapping or allocation contract exists. The existing service expressly reports `CONTROL_MAPPING_NOT_APPROVED`; a recognition journal may contain multiple journal-line accounts. The approved slice contract requires mapping validation for each included source, and selecting a candidate account would introduce unapproved financial semantics.

- Product files changed, schema changes, and migration files: **NONE**.
- Migration impact remains authorized as `SCHEMA + DATA-MIGRATION`, but no migration was created or run because its required source mapping is unresolved.
- AC: **0/16 PASS**; scoped DoD: **FAIL / NOT MET**; focused tests, concurrency, tenant-scope, migration, Ruff and Django checks: **NOT RUN** because no safe implementation exists.
- Historical retention, no-write financial-authority preservation, and inferred historical financial identity: **PASS / preserved / NONE**. No new regression was introduced or assessed.
- Required resolution: approve the exact source-owned mapping key, cardinality and allocation rule from every included obligation to a control `Account` and its journal-line evidence, including multi-line journal treatment. Then amend the reauthorization decision/package and repeat grounding. CEP-009, CEP-011 and CEP-013 remain **NOT STARTED**.

## 2026-10-15 control-mapping resume completion disposition

**Execution status: EXECUTION PARTIAL.** `PD-006-CAM-02` is approved and recorded as [PD-034](docs/architecture/BONIRA_PD_034_CONTROL_ACCOUNT_MAPPING.md); `CEP-006-FINDING-003 / BLOCKER-PD` is resolved by that decision.

Implemented the authorized bounded surface:

- Accounting-owned immutable `ControlAccountMappingVersion`, including effective
  interval overlap protection, tenant/active-posting-account validation, a dedicated
  permission/default grant, and audit evidence.
- Nullable historical `Obligation` account and mapping-version pins. New source
  recognition resolves and pins the effective map; absent/ambiguous mapping fails
  closed. The posting seam can return only the pin, without activating an AP/AR
  journal producer.
- Immutable Subledger account-grain and Treasury account/currency-grain evidence,
  revision/supersession, invalidation and provenance models. Reporting selects only
  current non-invalid prospective native slices. Unsupported direct-source pairs
  remain `uncomparable`.
- Four authorized migrations: Accounting `0012`, Organizations `0108`, Subledgers
  `0004`, Treasury `0008`. Their data migrations create only `legacy_unverified`
  provenance and do not infer accounts or alter historical financial identity.

Development migration evidence: all four migrations are applied; `migrate --plan`
and `makemigrations --check --dry-run` show no pending operations. Django system
checks, Ruff, scoped formatting and `git diff --check` pass.

Focused test execution remains unavailable. The original focused pytest selection
could not recreate the shared `test_construction_erp` database because another
session held it. A one-test `--keepdb` retry began rebuilding the full database and
was stopped after more than three minutes before the test body ran. This is
**test-infrastructure debt**, not evidence of a CEP regression. No focused or
representative behavioral test result is claimed; all 16 Acceptance Criteria remain
unverified for this completion disposition. The queue remains stopped before CEP-009.

Git writes, Human Sign-off, UAT, production migration/cutover, and production
certification were not executed.

## 2026-10-15 validation closure

**Execution status: EXECUTION COMPLETE.** The validation used a unique isolated
PostgreSQL test database (`test_cep006_validation_20261015_b62e`) through the
repository's established Django `TEST.NAME` runner pattern. It did not access,
reset or drop the shared `test_construction_erp` database. The isolated database
was removed after the tests completed and its sessions had closed.

- **Migration forward / provenance / reapply:** The full clean test migration graph
  applied Accounting `0012`, Organizations `0108`, Subledgers `0004` and Treasury
  `0008`; their provenance-only data operations completed. The final runner reused
  that migration-complete database. No historical account, currency, membership,
  amount, source version or sequence was inferred.
- **Focused behavior:** `output/cep-006/run_focused.py` passed **54 tests**. It
  covers the AP/AR map and pin contract, tenant scope, mapping intervals, missing
  map failure, immutable reconciliation evidence, Subledger concurrency, Treasury
  reconciliation/bank behavior and concurrency, Reporting current-source reads and
  no-write boundary.
- **CEP-006 correction:** The first run exposed PostgreSQL's prohibition on
  `FOR UPDATE` across nullable invalidation joins in Treasury GL and Bank predecessor
  lookup. The authorized correction limits the lock to the native row itself with
  `select_for_update(of=("self",))`; the same correction protects the Subledger
  predecessor lookup. The final focused run passed.
- **Representative regression:** `output/cep-006/run_regression.py` passed **23
  tests and 28 subtests** for CEP-005 commitment integration and CEP-008 Accounting
  recognition ownership. The focused suite also covers the affected Reporting and
  Treasury boundaries.
- **Static and migration checks:** Ruff and scoped formatting passed; Django system
  checks passed; `makemigrations --check --dry-run` reported no changes;
  `migrate --plan` reported no operations; `git diff --check` passed.

All 16 unchanged CEP-006 Acceptance Criteria are satisfied by the focused migration,
behavioral, tenant-scope, concurrency, traceability, no-write and representative
regression evidence. Scoped DoD is **PASS**. No unauthorized product semantics,
production action, Human Sign-off, Git write or downstream CEP execution occurred.

`CEP-009 = READY FOR QUEUE RESUME`; `CEP-011` and `CEP-013` remain **NOT STARTED**.
