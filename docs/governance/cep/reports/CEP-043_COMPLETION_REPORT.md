# CEP-043 — Payroll liability to AP handoff

**EXECUTION COMPLETE** — IMB-0061; AC **6/6 PASS**; scoped DoD **PASS**.

Baseline: `main @ da01c850b6fbacf41c793548426cb53e9bbc6813`; local HEAD, origin/main and remote main match. Changes remain uncommitted. No Git writes occurred.

## Implementation and authority

The Human-approved [lifecycle policy](../supporting/CEP-043_PAYROLL_AP_LIFECYCLE_POLICY.md) governs AP-owned prospective enrollment/version/withdrawal and retained correction/reversal/replacement. Source review establishes Payroll correctness only. Minimum additive persistence follows the separately approved Development/Non-Production migration authority. [Migration amendment](../evidence/CEP-043_AMENDMENT.json) and [lifecycle provenance](../evidence/CEP-043_LIFECYCLE_PROVENANCE.json) retain old/new prompt hashes and authorized changes. Current canonical SHA256: `2680c725f60d73c9f72140e5af5d0b8c142ccc7cf5bdba9c7760c63531682f00`. Scope, six AC, scoped DoD, dependencies and domain ownership are unchanged.

Explicit per-occurrence enrollment pins the finalized Payroll source, source revision, category, AP payee, dates and grouping reference; no fallback mapping or aggregate payable is inferred. Consumption creates an immutable AP draft, and separate normal AP recognition creates its payable. Historical enrollment/source pins remain intact after prospective withdrawal or supersession. New consumption after withdrawal fails closed.

Correction locks/re-reads native source and AP target, verifies exact inverse source/economic lineage, and commits the entire reversal/replacement set atomically. Ineligible replacement creates no payable. Active settlement, write-off, Accounting recognition or other implemented downstream consumption blocks replacement; any unwind stays under its domain authority. Payroll cannot edit an AP target or financial history. Exact retries reuse results; conflicting identity/payload and source/target drift fail closed. Reconciliation records the current native source, original/enrollment/reversal/replacement chain, exclusions and pending correction issues.

Five additive AP evidence tables plus four explicitly granted capabilities; no default grants. Existing grants, source/financial/audit history and data are preserved. No Payroll calculation, statutory value, GL recognition rule, Treasury writer, UI or production behavior is added.

## Verification

- [Final focused and affected regressions](../evidence/CEP-043_FINAL_REGRESSION_OUTPUT.txt): **45 tests +28 subtests PASS**, including real PostgreSQL concurrent creation/correction replay, batch rollback/retry, consumed target refusal, tenant/permission boundaries, supplier AP compatibility, native Payroll source contracts and Accounting recognition-owner boundary.
- [Populated disposable migration rehearsal](../evidence/CEP-043_EXPANDED_DIAGNOSTIC_OUTPUT.txt): **3 tests PASS**, including additive rollback/reapply preservation (2036.18s). This includes two financial scenarios also covered by final regression; totals are not added together.
- [Authorized local Development migration](../evidence/CEP-043_DEVELOPMENT_MIGRATION.json): organizations0121/subledgers0006 applied on verified loopback PostgreSQL. Every preexisting business table, permission catalog entry and grant count/digest matches before/after; new tables remain empty. No backfill, enrollment, implicit grants or production migration.
- [Current integration/reconciliation traces](../evidence/CEP-043_CURRENT_INTEGRATION_TRACE.json), [code diff](../evidence/CEP-043_CODE_DIFF.patch), [lint](../evidence/CEP-043_LINT_OUTPUT.txt), [system](../evidence/CEP-043_SYSTEM_CHECK.txt), [drift](../evidence/CEP-043_DRIFT_CHECK.txt) and [document checks](../evidence/CEP-043_DOCUMENT_CHECK.json): PASS within the recorded scope.

[Acceptance Mapping](../evidence/CEP-043_ACCEPTANCE_MAPPING.csv) maps each unchanged criterion to inspectable evidence. DoD: approved target/source contract, identity/version lineage, idempotency/retry/duplicate prevention, reconciliation/audit, integration/domain/security checks and authority boundaries all PASS. [Evidence Manifest](../evidence/CEP-043_EVIDENCE_MANIFEST.csv), [Change Manifest](../evidence/CEP-043_CHANGE_MANIFEST.csv) and [Execution Manifest](../manifests/CEP-043_EXECUTION_MANIFEST.md) record the full result and pre-mutation touch sets.

## Findings, debt and readiness

Findings001/002 are RESOLVED by explicit Human migration and lifecycle decisions, retained with their historical failed-entry states. [Intermediate failure attribution](../evidence/CEP-043_FIXTURE_FAILURE_SUMMARY.json) separates corrected new test-fixture defects from unchanged baseline debt. The interrupted historical migration test output has no completion summary and is not a PASS; the completed populated rehearsal supplies preservation evidence. Existing Payroll/Fixed Assets role-assignment/scope fixture debt and unchanged guards are preserved. No full-suite PASS is claimed.

`performance_concurrency_runtime` remains UTV for performance/production-scale behavior; only the focused PostgreSQL races above are proved. No browser/UI scope applies. Actual tenant activation mappings and statutory/currentness evidence are not supplied or inferred; source exceptions continue to fail closed. EXT0013 is activation-only, not a framework build blocker. No real tenant enrollment was inserted.

[GATE-05 evaluation](../evidence/CEP-043_GATE05_EVALUATION.json): **NOT_PASSED**. IMB0061 contract-build contribution verified; other required contributors remain incomplete/unverified. No overall Gate PASS, activation, UAT convergence, Human Sign-off, Production Certification or cutover is inferred.

Registry synchronized: 49 COMPLETE,2 PARTIAL,28 current-governed NOT_STARTED and7 deferred Post-V1. [Live frontier](../evidence/CEP-043_FRONTIER.json):17 dependency-ready candidates; readiness does not establish eligibility. Conditional-only predecessor scopes068/073/079 require entry review. Next entry-review candidate: CEP-044, whose hash and prerequisite were verified; full entry eligibility is not asserted.

Completed financial package boundary: additive schema and AP lifecycle changes overlap next CEP044 recognition/write-off surfaces; large uncommitted touch set and 34-minute migration rehearsal justify separate review/checkpoint. Standing authority persists; no new permission required.

No production action, Human Sign-off, Production Certification or Git checkpoint was performed. Standing authorization persists for a later eligible serial execution.
