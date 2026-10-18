Current execution: **EXECUTION COMPLETE — 24/24 AC and four scoped DoD PASS**.
Historical failed-entry and resumed-touch-set sections below are retained.

# CEP-042 execution manifest — 2026-10-18

Execution: **EXECUTION FAILED / BLOCKED BEFORE PRODUCT MUTATION**.

- Branch/HEAD: `main` / `90a1b2803936f5a95ce5322151c492ee7bafef11`.
- Initial tree clean; local and remote `main` match. Human direct checkpoint
  reconciled inline for CEP-035/037; historical execution baselines preserved.
- Prompt SHA-256:
  `1ea96efb37812bafe03934fed447450af35b862d049a0b388e4f4ab1f8ec4f93`.
  All 79 current-governed prompt hashes match the manifest.
- Standing Development/Non-Production authority applies subject to entry checks.
  CEP-008 and CEP-021 are COMPLETE. No external dependency. GATE-05 NOT_PASSED,
  exit-only; it does not block this contract build.
- Required sources: frozen PD-009/011/012/014/030, SPEC-002 recognition matrix,
  configuration matrix, four IMBs, package card, integration contracts,
  dependency/gate registers. Repository-local prompt retained; approved archives
  used only for upstream sources absent locally. Exact hashes in ENTRY evidence.
- Source authority remains Inventory/Payroll/Fixed Assets/Expenses; Accounting
  retains journals/GL, Treasury cash, AP payables and AR receivables. No draft
  Payroll, asset existence, generic Expense-to-AP or duplicate settlement recognition.

## Actual execution touch set

Only `CEP_EXECUTION_REGISTRY.yaml` and the new CEP-042 manifest, finding, report,
acceptance/change/evidence CSVs and evidence files. Product touch set is empty.
Read-only seams: Accounting models/services/registries; Inventory valuation and
envelope models/services; Payroll source proposal models/services; Fixed Assets
class/envelope models/services; Expense models/services; Treasury mapping model;
closed platform policy catalog. No application, settings or test source mutation.

Local configured PostgreSQL has no pending migrations in the six inspected
financial/source apps. Migration/schema/data execution: NONE. Source/target
integration and runtime checks: NOT EXECUTED; failure occurs at the mapping seam.

Baseline command: `.venv/Scripts/python.exe -m pytest -q
apps/accounting/tests.py::AccountingPolicyCalculationTests
apps/accounting/test_cep008_recognition_registry.py` — 10 PASS, 28 subtests PASS.
This validates the prerequisite owner resolver only. The missing reusable mapping
version/line persistence cannot be added under Migration Impact NONE; see
`../evidence/CEP-042_FINDING-001.md`. No financial behavior inferred.

Stop conditions applied: canonical section 16 / Execution Policy section 13
before model/migration mutation. 0/24 AC PASS, all 24 BLOCKED; scoped DoD NOT MET.
Required implementation/integration/reconciliation/reversal/retry evidence stays
UNVERIFIED. Serial continuation stopped on failed entry; independent candidates
remain unreviewed. No Git writes, branch/worktree, Human Sign-off, production
certification, production data mutation or cutover.

## Resumed implementation touch set — authorized 2026-10-18

HUMAN-CEP042-PERSISTENCE-20261018 resolves the migration entry blocker. Prompt
sections16/21/22 alone amended; new hash verified in CEP-042_AMENDMENT.json.
Planned exact product surface: apps/accounting/recognition_models.py (immutable
mapping versions, independent approvals and source-to-draft evidence),
recognition_sources.py (typed source readers), recognition_services.py (explicit
mapping, draft/reversal/retry/reconciliation); accounting/models.py imports and
draft-only source validation; organizations/models.py, permission_registry.py,
role_defaults.py and additive permission migration0120; additive Accounting0013;
audit/models.py event catalog. Bounded source hooks in Inventory p8_services.py,
Payroll services.py, Fixed Assets services.py and Expenses services.py. Focused
and populated migration tests in apps/accounting/test_cep042*.py. No UI or
settings changes. Existing Accounting posting rules remain unchanged: new source
outputs are drafts and cannot post through an unapproved source contract.
Explicit tenant mapping accounts/values are never seeded from labels or defaults.

Mapping persistence stores explicit source-key-to-account assignments and their
independent acceptance; it computes no accounting treatment. Source extractors
retain canonical finalized evidence, native version references, dimensions and
reversal lineage. Missing/unsupported mappings fail closed; target failure must
leave source authority intact with retry evidence.

## Final closeout

Authorized mapping persistence and source adapters implemented within the recorded
touch set. Additional bounded test surface: test_cep042_regression.py wraps four
unchanged legacy scenarios with explicit test role/scope assignments; product
permissions remain unchanged. The original raw four failures and unchanged-guard
proof are retained as BASELINE TEST DEBT. Final results: 18 focused tests/7
subtests PASS plus 2 targeted checks PASS, 1 populated migration rehearsal PASS,
11 affected scenarios verified, 10 prerequisite tests/28 subtests PASS. No full
regression claim. Lint, new-file format, system, drift and changed-document checks
PASS. Both authorized local Development migrations applied with matching existing
history/grant digests; new mapping/effect tables empty. No backfill/production/Git.
GATE05 NOT_PASSED after four contributor verification; frontier recalculated.
Clean completed-CEP042 financial review boundary; CEP043 NOT STARTED.
