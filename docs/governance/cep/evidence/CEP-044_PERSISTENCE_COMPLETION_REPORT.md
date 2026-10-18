# CEP-044 — AP/AR recognition and write-off governance

**EXECUTION PARTIAL** — IMB-0062/0063; Registry lifecycle **BLOCKED**.
Full package AC **0/12 PASS / incomplete**; both scoped DoD **NOT MET**.

Baseline/end HEAD: `main @ f0034b5589a2155547100aeac425f709c5e53722`, equal to
`origin/main` and remote main. The 15 attributable prior entry/evidence paths were
preserved. CEP-043's existing checkpoint metadata remains reconciled; its execution
result, baseline debt and UTV are unchanged. No Git writes occurred.

## Authorized amendment and persistence

[Human migration decision](../evidence/CEP-044_HUMAN_MIGRATION_AUTHORIZATION.md)
resolves Finding001. [Amendment provenance](../evidence/CEP-044_AMENDMENT.json)
retains old/new hashes: only migration language in sections 16/21/22 changed;
all other 27 sections, Scope/AC/DoD, dependencies, domain ownership and recognition
rules are unchanged. All 79 canonical identities reverified. Current CEP-044
SHA256: `c2637422502e4d51c6039638e9f1c43572d74774f2438d2664cfa60afa5fafe0`.

Minimum additive `WriteOffProposal.corrects` retains a protected predecessor
Decision under the same tenant/obligation. Existing source rows remain NULL;
no pairing/backfill is inferred. Structural validation rejects foreign tenant,
actor, obligation and self-reference. Immutable source links resist instance,
queryset, bulk-update/create and deletion shortcuts. The migration refuses a
rollback that would discard populated correction lineage; recovery is forward-only
once used. This persistence does not approve a replacement or activate monetary,
workflow, Accounting, cancellation or Treasury behavior.

[Configured Development migration](../evidence/CEP-044_DEVELOPMENT_MIGRATION.json):
subledgers0007 applied only to verified loopback PostgreSQL/Psycopg3. Pre-existing
column counts/SHA256 fingerprints across **515 managed tables match exactly**;
new links **0**. Existing obligations, write-offs, audit, grants, source versions
and finalized history are preserved. No production migration or tenant activation.

## Validation

- [Focused persistence/tenant/immutability](../evidence/CEP-044_LINEAGE_TEST_OUTPUT.txt):
  **6 tests + 10 subtests PASS**.
- [Populated disposable migration](../evidence/CEP-044_MIGRATION_TEST_OUTPUT.txt):
  **1 test PASS**, including approved/rejected decisions and reversal history,
  rollback/reapply preservation and refusal to drop used lineage; [trace](../evidence/CEP-044_MIGRATION_TRACE.json).
- [Affected boundary and prerequisite regression](../evidence/CEP-044_AFFECTED_REGRESSION_OUTPUT.txt):
  **12 tests + 28 subtests PASS**: recognition-owner registry, existing policy-absent
  guards, supplier settlement/write-off/source authority and Payroll AP correction/
  consumed-target boundary. No full-suite or new financial-lifecycle PASS claimed.
- [Lint](../evidence/CEP-044_PERSISTENCE_LINT_OUTPUT.txt), format, [system checks](../evidence/CEP-044_SYSTEM_CHECK.txt)
  and [migration drift](../evidence/CEP-044_DRIFT_CHECK.txt): PASS for bounded changes.
  The initial new bulk-update guard failure was fixed and is [attributed](../evidence/CEP-044_INITIAL_FAILURE_SUMMARY.json), not reclassified as baseline debt.

Product changes: one model/source guard, one additive migration and two focused
test modules; [code diff](../evidence/CEP-044_PERSISTENCE_CODE_DIFF.patch).
[Execution Manifest](../manifests/CEP-044_EXECUTION_MANIFEST.md),
[Acceptance Mapping](../evidence/CEP-044_ACCEPTANCE_MAPPING.csv),
[Evidence Manifest](../evidence/CEP-044_EVIDENCE_MANIFEST.csv) and
[Change Manifest](../evidence/CEP-044_CHANGE_MANIFEST.csv) distinguish historical
failed entry from this bounded implementation. Package financial/workflow/
recognition/reconciliation/security criteria remain incomplete; direct structural
tenant checks do not substitute for full runtime authorization evidence.

## Exact blocker and continuation

[Finding002 — BLOCKER-SPEC](../evidence/CEP-044_FINDING-002.md) records the missing
financial correction mechanism and coupled atomic/effective-date boundary after
reviewing frozen PDs/SPEC-024/matrix, accepted P3 Q03/as-of contracts and recovered
write-off journeys. Existing permission/Self-Approval rules are settled and are
not reopened. Human decision item 8 requires stopping before an absent material
correction rule is implemented. The proposed minimum full-reversal/replacement
contract is concrete and retained for Human approval; no such rule was activated.

Existing baseline debt and performance/concurrency UTV remain preserved. Required
new implementation validations are blocked, not UTV-based acceptance. CEP-008
prerequisite remains COMPLETE; **GATE-05 remains NOT_PASSED**, exit-only here.
Registry/frontier synchronized: **49 COMPLETE, 3 PARTIAL, 27 other current-governed
NOT_STARTED; 7 deferred Post-V1**. CEP-044 is included in PARTIAL and blocked by
Finding002. The 17 dependency-ready candidates are not declared fully eligible;
serial continuation stopped without bypassing the unresolved package.

All changes remain uncommitted. The session's bounded checkpoint authority covers
completed CEP work; no Git add/commit/push/merge or branch/worktree creation was
performed for this partial package. No production action, Human Sign-off,
Production Certification or cutover occurred.
