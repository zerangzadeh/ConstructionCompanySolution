# P10-S19–S21 Release Certification Evidence

**Candidate:** `P10-RC1-20261007-E0E078C9`  
**Frozen runtime commit:** `0db3ac9a9fa70e8a857ef0867d532be5206a14c4`  
**Executed:** 2026-10-07  
**Disposition:** **`BLOCKED` — not eligible for P10-S22 or Product Owner
acceptance.**

This record is limited to the authorized non-production P10-S19–S21 tranche.
It does not authorize P10-S22+, production deployment, cutover, traffic or
activation. The 1,134-path frozen runtime/dependency diff remained clean and the
locked dependency file retained SHA-256
`ec2f92a67b0f64ab2045364b6ed9fcef9a17aab5f74d18f8080ee74388525e12`.

## S19 — migration and recovery

One runner used uniquely named disposable PostgreSQL 18.6 databases and isolated
DMS roots. Production data and the configured development database were not
targets. The final exercised-local-scenarios evidence is SHA-256
`13c0178fc4d9ad1ad0354c946bbee2cfac77b8c0cfbdde5b003ab47abeae8114`.

| Criterion | Result |
| --- | --- |
| Clean candidate migration | **PASS (local exercise):** `1,185.215s` (`19m 45.215s`), within the 30-minute window |
| Direct reverse assessment | **Not selected:** schema reversal completed, but candidate startup repopulated its code-owned permission catalogue; this is not a trustworthy data rollback |
| Representative upgrade | **PASS (local exercise):** exact pre-candidate commit `3dd1b4e` baseline to the frozen candidate in `127.527s` |
| Coherent rollback | **PASS (local exercise):** pre-change PostgreSQL backup restored in `39.321s`; baseline counts/hash matched |
| Exact reapply | **PASS (local exercise):** `90.729s`; post-reapply counts/hash matched the first upgrade |
| Atomic-failure probe | **PASS:** deliberate transactional DDL/data failure left no state |
| Coherent DB/DMS backup | **PASS:** 3,464,551-byte custom-format database artifact plus isolated DMS copy |
| Isolated restore and coherence | **PASS:** DB counts/hash, DMS path/hash/size, suspended Tenant and revoked membership matched |
| Mismatch handling | **PASS:** deliberately altered restored bytes failed the coherence check |
| Measured RPO/RTO | **Exercised set:** RPO `0s`; RTO `10.842s`, within `15m/60m` targets |
| Cleanup | **PASS:** all three disposable databases and isolated DMS roots removed |

The earlier harness run is retained as failed/superseded evidence: it completed a
clean apply in `1,287.307s` and stopped on a harness import-path error before
backup. It was not silently converted to pass.

Overall S19 remains **`BLOCKED`** for production recovery certification. The
static latest-good local backup proves only the exercised set; no selected
production provider/PITR schedule, encryption/key-custody recovery, availability-
zone/region failure, production-equivalent storage class or independent restore
witness evidence exists. Consequently the measured zero-loss local snapshot is
not an assertion that a production 15-minute RPO is operationally implemented.

## S20 — performance

Workload `P10-S20-WP1-20261007-E0E078C9-A` and environment
`P10-S20-ENV1-LOCAL-20261007-A` passed the bounded preflight: all seven frozen
artifact hashes matched, the `100%` journey mix and 94 route/service resolutions
were consistent, the single permitted reachability request returned `HTTP 200`
in `75.116ms`, PostgreSQL reported `9/100` active connections, and the recorded
environment fingerprint matched. The closure record is
`output/p10_s20_preflight/bounded_preflight_closure.json` (SHA-256
`954312c4c1527e029e01d7a1250f2771682c162002eac7ffa62bc0614d997a7a`).

`P10-S20 = performance execution prerequisites satisfied for environment-qualified testing`

One subsequent `84.701s` non-certification calibration reached 50 virtual users /
50 in-flight requests, generated the exact frozen mix across 500 journeys and
issued 1,795 requests. Metrics remained collectable, including per-class latency
and a `13/100` PostgreSQL connection peak, but the run returned 31 HTTP 500s and
13 connection refusals. Diagnosis traced every 500 to unapplied configured-
database migrations, not an established frozen-runtime defect; the frozen routes
also lack executable record/payload bindings and the local environment provided
only four Tenants/25 memberships. The full environment-qualified run must not
start until schema parity, bindings and connection stability are corrected and a
short calibration passes. Assessment SHA-256:
`0e04cbe8e9f2124b0ab8a4634375bba7ecd0a3b4dc3e4642493cb276d7b083a2`.

**Administrative closeout (2026-10-08):** all existing configured-database
migrations were applied; `migrate --plan` then reported no planned operations.
This restores schema parity but is not a replacement for the required focused
binding/connectivity verification or clean recalibration. Those steps were not
run. A calibration-only binding-preparation draft and its partial local fixtures
are excluded from certification evidence and require fresh review before any
future use. `P10-S20 = calibration blocked` remains the current result.

No peak, surge or endurance performance run was executed. Production capacity
certification remains gated by direct HTTP without TLS/proxy, shared app/DB
resources without dedicated limits, incomplete production DMS controls, and
incomplete server-side telemetry. Required classification:

`environment-qualified / production capacity certification still gated`

## S21 — Tenant, security, privacy and SoD

The focused PostgreSQL suite covering P10 Reporting/Reconciliation/Closeout,
Tenant/object scope, no implicit Platform Admin access, source authorization,
permissions/SoD, masking/private responses, DMS boundaries, CSRF/POST-only paths,
audit evidence and no downstream mutation passed: **168 tests and 22 subtests**
in `815.79s`.

The mandatory one-time full frozen-candidate PostgreSQL run used a separate
disposable test database. Its JUnit evidence has SHA-256
`c5e4aecb70c06b1a62c4df8700960b82064f16db7756260670ef03d283c78b8d`:

- 1,176 tests collected;
- 1,036 passed;
- 42 failed;
- 19 errored;
- 79 subtests passed; and
- duration `4,052.20s` (`1h 07m 32s`).

### Full-suite failure classification and bounded remediation

Every initial non-pass was traced to its first causal fault. Counts reconcile to
the original **42 failures + 19 errors**; none was automatically assigned to the
six known permission-registry failures. The row-complete 61-outcome classification
CSV has SHA-256
`59324e670f0c6f804ced9139a7e501a3fe02184862f608beb22330a835a5a065`.

| Classification | Failures | Errors | Classified cases |
| --- | ---: | ---: | --- |
| Genuine candidate defect | 0 | 0 | No frozen runtime defect was established. |
| Pre-existing known debt | 6 | 0 | Permission-registry database parity; flush parity; managed-model uniqueness; permission-code uniqueness; enforcement-module references; namespace/resource-key parity. |
| Obsolete assertion | 8 | 0 | The two inherited Billing assertions repeated across `ProgressClaimCalculationTests`, `ProgressClaimApprovalWorkflowTests` and `ProgressClaimSettlementTests` (6); the Inventory goods-receipt fixture assertions in `StockTransactionWorkflowTests` and `StockTransactionServiceTests` (2). |
| Test/environment defect | 28 | 19 | Five destructive migration-test failures; 23 schema-contamination downstream failures; and all 19 serialized-database setup errors detailed below. |
| Unrelated repository defect | 0 | 0 | None established. |

The 28 failure cases classified as test/environment defects are complete:

- destructive shared-schema migration tests (5): Expense permission migration;
  three Project budget/cost/schedule migrations; Project Cost permission/audit
  migration;
- contaminated Payroll/procurement/project schema (19): `PayrollConcurrencyTests`
  (1), `StatutoryExportConcurrencyTests` (1),
  `PayrollFinancialHandoffTests` (8), eight Procurement concurrency tests, and
  `ProjectCostConcurrencyTests` (1);
- contaminated Treasury/permission/seed state (4): `SubledgerConcurrencyTests`
  (1), `SupportP9ConcurrencyTests` (1), and the account/demo seed tests (2).

The 19 setup errors were all duplicate `django_content_type` restoration caused
by manual deserialization after Django's serialized rollback. They covered Billing
concurrency (2); Daily Reports, Equipment and Estimates (1 each); Inventory
custody (2), Inventory migration (1), Inventory workflow (1); Quality, Safety,
Treasury migration and Workflow runtime (1 each); and the six PostgreSQL
select-for-update concurrency tests.

The bounded correction changed tests only; the frozen runtime candidate remains
unchanged. Billing assertions now reflect Platform-owned regulatory authority and
require accepted review evidence before any publisher can publish. Inventory
fixtures now create an active supplier role and issue the PO through the service,
pinning its immutable version. Redundant manual serialized restores were removed
while Django's `serialized_rollback` remained enabled. In-process migration tests
now verify applied/reversible migration contracts without moving a shared suite
database below other apps' required leaves; S19 retains the actual isolated
rollback/reapply evidence.

Post-correction focused results:

- obsolete Billing/Inventory assertions: **8 passed** in `19.78s`;
- migration contracts: **11 passed** in `21.98s`;
- fresh-database serialized rollback/concurrency regression: **7 passed** in
  `995.39s`.

The single authorized mandatory full-suite rerun used another fresh disposable
database. JUnit SHA-256 is
`2e96ca354a92acb79115992a08e662c6ec285229ba20e3e18769cafe126cefbf`:

- 1,176 tests collected;
- 1,067 passed;
- 12 failed;
- 18 errored;
- 79 subtests passed; and
- duration `2,773.73s` (`46m 13.73s`).

The rerun eliminated all eight obsolete assertions and all 23 downstream
schema-contamination failures. Six failures are the unchanged permission-registry
debt. The remaining six failures (Retention Release, statutory Payroll export,
Project Cost concurrency, Support concurrency and two seed tests) and all 18
setup errors shared one residual test-baseline cause at the recorded rerun failure
point: ordinary and serialized
`TransactionTestCase` classes were mixed, so post-migrate catalogue rows could
exist before the next serialized snapshot was loaded. They remain classified as
test/environment defects, not candidate-runtime passes or defects.
The row-complete 30-outcome rerun classification CSV has SHA-256
`9c51031686380e9db53fd1e708b14b4ff8b70182b8570c9bd4ec8ec9737930f5`.

The follow-on bounded harness correction applies serialized rollback uniformly
to the repository's class- and function-style transactional tests. On a fresh
database the exact 24 rerun-affected cases produced **22 passed and 2 failed** in
`1,181.07s` (JUnit SHA-256
`458afe1d0cf7a578e1c40186f26e24ae063e1a0888b4f96b7940394f5ae209a0`): all 18
duplicate-content-type setup errors and four catalogue-baseline failures were
cleared. The two remaining seed tests no longer fail on the missing migration-
seeded expense catalogue; they proceed further and expose a separate stale demo-
data defect because `seed_demo_data` creates a progress claim without first
creating an approved contract-term version effective at its cutoff.

The function-style transactional correction was then verified against those two
tests alone on another fresh database. Both reached the same later contract-term
failure in `1,032.86s` (JUnit SHA-256
`a08e25ee8a882843060820f71aeb0f1ddea2bb4209dcd5481b0330220322ab05`). This
confirms the original catalogue/serialized-baseline defect is removed. The newly
reachable seed-command defect is classified as an unrelated repository defect,
not a
candidate-runtime or S19–S21 authority-boundary defect, and was not repaired just
to make certification green. Per the authorization, the mandatory full suite was
not run a second time; its recorded rerun therefore remains non-green and
certification-relevant full-suite evidence remains blocked.

### Frozen-environment supply-chain proof

The host CPython installation contains `nltk 3.9.1` directly in the interpreter
root rather than in the project lock, which leaks it into ordinary virtual
environments and explains the earlier four missing optional dependency reports.
It is unrelated global state and no application dependency was changed for it.

A clean CPython 3.11.1 Windows x86-64 embedded runtime was isolated with user-site
loading disabled. `requirements-lock.txt` (SHA-256
`ec2f92a67b0f64ab2045364b6ed9fcef9a17aab5f74d18f8080ee74388525e12`)
installed with `--require-hashes --ignore-installed`; its inventory contains the
exact 16 locked packages, reports `NLTK_PRESENT=False`, and targeted `pip check`
reports **`No broken requirements found.`** Raw install/check/inventory/interpreter
evidence is retained under `output/p10_s19_20261007_112127/supply_chain/`.

Production `check --deploy` passed the candidate's configured Django security
checks. That does not supply the still-absent privileged MFA, production private
object storage/malware scanning and key custody, correlation/monitoring/alerting,
complete vulnerability/secret/license evidence, independent targeted penetration
review or final privacy/legal retention evidence. These are non-waivable missing
controls for the included release.

### Final repository checks

- Django system check, including registered URL/template configuration: **PASS**;
- migration drift (`makemigrations --check --dry-run`): **PASS — no changes**;
- targeted Ruff over every modified Python test/harness file: **PASS**;
- `git diff --check`: **PASS**; and
- candidate runtime/dependency delta: **zero**; changes are limited to tests,
  certification evidence/specification and the retained local certification
  runner/artifacts.

S21 disposition: **`BLOCKED`**. The focused Tenant/security boundary evidence is
green, but the recorded mandatory full-suite rerun remains non-green and missing
production security/operations evidence prevents `ELIGIBLE_FOR_P10-S22`.

## Findings, waivers and preserved gates

- No waiver was requested or granted.
- S20 bounded preflight is a pass; absent load/capacity evidence and S21 missing
  evidence are not passes.
- S19 production recovery evidence remains incomplete despite the successful
  local rehearsal.
- The six pre-existing permission-registry failures remain known debt subject to
  `P10-CERT36`; every other initial and rerun non-pass is separately classified
  rather than folded into that debt.
- `P10-S18 = certification prerequisites satisfied`; **P10-S19–S21 = BLOCKED.
  P10-S18–S21 is not ready for Product Owner acceptance. Administrative closeout
  on 2026-10-08 did not change that result.**
- P10-S22+, production migration/restore/deployment/cutover/activation and all
  preserved provider/queue/integration/automatic-effect gates remain closed.
