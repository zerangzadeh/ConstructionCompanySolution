# BONIRA — CEP-073 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-073`
- CEP Title: `PostgreSQL runtime, performance and concurrency verification`
- Package Type: `VERIFICATION`
- Prompt Class: `VERIFICATION / UAT`
- Roadmap Stage: `STG-05 SYSTEM VERIFICATION`
- Roadmap Wave: `RW-08`
- Primary Track: `TRACK-10`
- Lifecycle Status: `LIVE STATE OWNED BY CEP_EXECUTION_REGISTRY.yaml`
- CEP Authorization Status: `SEE CURRENT GOVERNANCE + CEP_EXECUTION_REGISTRY.yaml`
- Prompt Status: `CANONICAL — VERIFY SHA-256 IN CEP_PROMPT_MANIFEST.yaml`

## 2. Authorization Boundary
This canonical prompt defines package-specific Scope / AC / DoD; it does not itself grant authority.

Current governance applies:
- Eligible current-governed non-production execution is covered by the standing bounded Human authority recorded in the repository.
- Routine per-CEP explicit Human Authorization is **not required** when canonical identity, dependencies, gates, blockers, repository safety and this package's Scope / AC / DoD permit execution.
- Any separate explicit Human Authorization applies only to the bounded operation it names.
- Standing authority does not authorize Post-V1 activation, Scope / AC / DoD / Product-Decision / dependency-graph changes, production deployment/cutover/irreversible production migration, Human Sign-off, final Production Certification, or material risk acceptance.

`PROMPT EXISTENCE ≠ SCOPE EXPANSION OR PRODUCTION AUTHORITY`

## 3. Authoritative Sources
- `docs/governance/CEP_PROGRAM_AUTHORITY.md`
- `Agents.md`
- `docs/governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md`
- `docs/ROADMAP_EXECUTION_PLAYBOOK.md`
- `CEP_EXECUTION_REGISTRY.yaml` for live state only
- CEP-073 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `NONE`
- Specifications: `NONE`
- Integration IDs: `NONE`
- UI Architecture IDs: `NONE`
- ESS Capability IDs: `NONE`
- Canonical sources: Final Implementation Master Backlog, Dependency Graph, Implementation Roadmap, the current repository governance hierarchy and the package-specific canonical sources listed above.
- Historical prompt-design baseline: `main @ d75a9334d8e27683159c5f756725c0540651ec43` (context only; execution MUST ground the current repository state).

Repository source-resolution rule:
- Use repository-local canonical sources first and verify this prompt byte-for-byte against `docs/governance/cep/CEP_PROMPT_MANIFEST.yaml`.
- Approved consolidated execution materials are **recovery-only** when a required repository-local canonical source is unavailable.
- Never substitute an external or historical consolidated copy for an available repository-local canonical prompt/source.
- Current generic execution mechanics come from `Agents.md`, the Execution Policy and the Playbook; package-specific Scope / AC / DoD / migration / evidence semantics remain owned by this canonical prompt.

## 4. Objective
Deliver the canonical outcomes owned by the listed IMBs as one bounded package without expanding authority, scope, roadmap placement or business semantics.

## 5. Primary IMBs
- `IMB-0103` — PostgreSQL migration/runtime verification
- `IMB-0109` — PostgreSQL performance and concurrency verification

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Execute exact-SHA migration/runtime scenarios and retain results.
- Execute audited GL/reporting/inventory/lock scenarios and capture plans/results.

## 7. Explicit Out of Scope
The verification activity explicitly defined by this CEP is **IN SCOPE only when current applicable execution authority and all package entry conditions are satisfied** and after all prerequisite, gate, environment, data-safety and external-dependency conditions are satisfied.

Explicitly permitted when current applicable authority and all package entry conditions are satisfied:
- approved PostgreSQL runtime verification;
- approved performance verification;
- approved concurrency verification;
- approved migration verification / rehearsal / reconciliation defined by this CEP.

The following remain **OUT OF SCOPE** unless separately authorized:
- production tuning outside the approved verification scope;
- unapproved schema changes;
- silent performance remediation;
- production workload modification;
- irreversible production migration;
- production deployment or production cutover;
- mutation of production business data outside the approved test plan;
- remediation or product-code/configuration/data/policy/architecture changes made merely to force a passing result;
- runtime activity outside the approved verification environment/scenario;
- Human Sign-off or production acceptance.

`VERIFICATION FINDING → RECORD FINDING → PASS / FAIL / PARTIAL / UTV AS EVIDENCE SUPPORTS → DO NOT SILENTLY REMEDIATE`

If remediation is required: `REMEDIATION → SEPARATE AUTHORIZED IMPLEMENTATION ACTION`.

Human Sign-off remains outside Codex authority and must never be inferred from successful execution of this CEP.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

Human Sign-off remains outside Codex authority and must never be granted or inferred from successful execution of this CEP.

## 8. Prerequisite CEPs
- `CEP-006` — source `DEP-0036:IMB-0048→IMB-0109; DEP-0060:IMB-0066→IMB-0109`; strength `MANDATORY`; condition: ALWAYS
- `CEP-009` — source `DEP-0061:IMB-0067→IMB-0109; DEP-0062:IMB-0068→IMB-0109`; strength `MANDATORY`; condition: ALWAYS
- `CEP-012` — source `DEP-0105:IMB-0096→IMB-0103; DEP-0106:IMB-0097→IMB-0103`; strength `MANDATORY`; condition: ALWAYS
- `CEP-028` — source `DEP-0044:IMB-0050→IMB-0103`; strength `CONDITIONAL`; condition: When Legacy Payment reference/data migration to Treasury is included in the PostgreSQL migration verification run.
- `CEP-029` — source `DEP-0076:IMB-0070→IMB-0103`; strength `CONDITIONAL`; condition: When Employee → WorkRelationship migration and rehire history is included in the PostgreSQL migration verification run.
- `CEP-057` — source `DEP-0079:IMB-0075→IMB-0103`; strength `CONDITIONAL`; condition: When Leave opening balance migration is included in the PostgreSQL migration verification run.
- `CEP-058` — source `DEP-0089:IMB-0080→IMB-0103`; strength `CONDITIONAL`; condition: When Historical Payroll/YTD opening-state migration is included in the PostgreSQL migration verification run.

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
- `EXT-0023` — Phase `VERIFICATION`; Blocks Build `NO`; Activation `NO`; Verification `YES`; Production `NO`; Gate `Relevant implementation gate + external verification dependency`; Fail-closed: NOT EXECUTED

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `Relevant implementation gate + external verification dependency`
- Exit Gate: `GATE-08`

Gate state must be checked at execution time. Prompt existence does not satisfy a gate.

## 11. Repository Grounding
Before verification activity or evidence capture:
1. Confirm current branch/base and record commit SHA.
2. Inspect existing implementation and relevant apps/models/services/templates/endpoints/tests.
3. Inspect migration state only when applicable.
4. Run/record focused baseline checks where practical; separate pre-existing failures.
5. Compare repository reality with this package design.
6. Complete `CEP-073_EXECUTION_MANIFEST.md` with actual execution-time findings.

`REPOSITORY REALITY > DOCUMENT ASSUMPTION`

If repository reality contradicts the package design, record `CEP-073-FINDING-###`; do not silently redesign. If safe execution is impossible, use `BLOCKER-REPOSITORY` or the appropriate blocker and STOP.

Current Git mechanics are governed by `Agents.md` and the Execution Policy:
`default = current local main; no new branch/worktree; no git add/commit/push/merge unless separately and explicitly authorized`.

Prompt existence or CEP completion does not grant Git-write authority.

## 12. Expected Code Surfaces
certification/ (CONFIRMED repository directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Verify the already-implemented governed outcome. Do not modify product code to make a verification pass. If a defect is found, record it as a finding and BLOCK/FAIL as appropriate; repair requires separate authorized implementation action.

Canonical package scope:
- Execute exact-SHA migration/runtime scenarios and retain results.
- Execute audited GL/reporting/inventory/lock scenarios and capture plans/results.

Required internal IMB sequence:
NONE

## 14. Security Requirements
Canonical Security Impact: `NONE`.
- Security Impact: `NONE`
- Applicability detail: NONE
- Permission Test: `NOT APPLICABLE`
- Tenant-Isolation Test: `NOT APPLICABLE`
- Apply only the package-specific security tests marked REQUIRED/CONDITIONAL in the corrected Test Plan.
- Do not turn N/A tenant/permission testing into boilerplate requirements.

## 15. Tenant / Authorization Requirements
Where applicable preserve `ROLE/PERMISSION + OBJECT SCOPE + TENANT + WORKFLOW AUTHORITY`.
`CROSS-TENANT DATA LEAKAGE = 0` where tenant-scoped runtime behavior applies.
`MANAGER AUTHORITY ≠ JOB TITLE` where manager authority applies.
If these concerns are N/A for the canonical CEP, do not invent new authorization behavior.

## 16. Data / Migration Requirements
Canonical Migration Impact: `MIGRATION-VERIFICATION`.
- Migration Impact: `MIGRATION-VERIFICATION`
- Canonical components: MIGRATION-VERIFICATION
- Migration Test: `REQUIRED`
- Migration Evidence: `REQUIRED`
- Distinguish Migration Code / Preparation / Execution / Verification / Cutover.
- Bounded non-production migration preparation, tests, rehearsal, execution or verification may proceed only to the extent this canonical package and current applicable authority permit and all required data/environment prerequisites are satisfied.
- Production migration, irreversible production mutation and Production Cutover remain Human-only and require explicit authority for the exact action.

## 17. Integration Requirements
Preserve approved integration semantics and interaction levels. Financial integrations must not silently escalate authority.

Coordination relationships (non-blocking unless canonical dependency says otherwise):
NONE

External dependency phase semantics:
- `EXT-0023` — Phase `VERIFICATION`; Blocks Build `NO`; Activation `NO`; Verification `YES`; Production `NO`; Gate `Relevant implementation gate + external verification dependency`; Fail-closed: NOT EXECUTED

## 18. Financial Authority Requirements
NOT APPLICABLE. Do not invent financial posting, reconciliation, accounting-recognition or cash-authority behavior.

## 19. UI Requirements
UI Impact = `NONE`.
- Do not invent UI work.
- If implementation unexpectedly touches UI, record a finding; BONIRA Persian-first/RTL/Jalali/accessibility/design-token standards remain governing.

## 20. Regulatory / Configuration Requirements
NOT APPLICABLE. Do not infer profile, regulatory or feature-flag semantics.

## 21. Test Plan
Use the corrected CEP-specific applicability exactly; do not replace it with a universal test matrix.

UNIT=NOT APPLICABLE; MODEL=NOT APPLICABLE; SERVICE=NOT APPLICABLE; PERMISSION=NOT APPLICABLE; TENANT-ISOLATION=NOT APPLICABLE; WORKFLOW=NOT APPLICABLE; INTEGRATION=NOT APPLICABLE; MIGRATION=REQUIRED; UI / TEMPLATE=NOT APPLICABLE; END-TO-END=REQUIRED; REGRESSION=NOT APPLICABLE; RUNTIME VERIFICATION=REQUIRED; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0103:MIGRATION; REGRESSION | IMB-0109:PERFORMANCE; CONCURRENCY; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

### Canonical Test Token Reconciliation
`CANONICAL IMB TEST TOKENS = UPSTREAM EXPECTED EVIDENCE TYPES`

`CEP TEST PLAN = TESTS APPLICABLE TO THIS SPECIFIC VERIFICATION PACKAGE`

Canonical tokens include MIGRATION / REGRESSION / PERFORMANCE / CONCURRENCY. In this CEP, MIGRATION and runtime verification are REQUIRED because the CEP directly executes the approved migration/runtime and performance/concurrency scenarios. Generic REGRESSION is not a separate mandatory package test because this CEP verifies the defined runtime scenarios rather than re-running the entire implementation regression suite; prerequisite implementation/regression evidence remains authoritative and is not discarded.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=NOT APPLICABLE; TEST OUTPUT=REQUIRED; LINT OUTPUT=NOT APPLICABLE; MIGRATION OUTPUT=REQUIRED; DATA RECONCILIATION=REQUIRED; PERMISSION TEST=NOT APPLICABLE; TENANT-ISOLATION TEST=NOT APPLICABLE; INTEGRATION TRACE=NOT APPLICABLE; TRANSACTION TRACE=NOT APPLICABLE; SCREENSHOT=NOT APPLICABLE; UI RUNTIME EVIDENCE=NOT APPLICABLE; LOG / DIAGNOSTIC EVIDENCE=REQUIRED; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=REQUIRED; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0103:PostgreSQL migration/runtime verification: executed scenario evidence; environment/runtime details; exact code/version; timestamp; measured artifacts; explicit pass/fail record without promoting unexecuted UTV. | IMB-0109:PostgreSQL performance and concurrency verification: executed scenario evidence; environment/runtime details; exact code/version; timestamp; measured artifacts; explicit pass/fail record without promoting unexecuted UTV.

Execution must produce:
- `CEP-073_EXECUTION_MANIFEST.md`
- `CEP-073_ACCEPTANCE_MAPPING.csv`
- `CEP-073_EVIDENCE_MANIFEST.csv`
- `CEP-073_CHANGE_MANIFEST.csv`
- `CEP-073_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-073-EV-001`, `CEP-073-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0103` — 1) `PostgreSQL migration/runtime verification` produces the approved target outcome: Migration/application behavior is evidenced on target PostgreSQL runtime.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; TEST OUTPUT
2. `IMB-0103` — 2) Later verification defines exact `PostgreSQL migration/runtime verification` scenario, environment and version.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; TEST OUTPUT
3. `IMB-0103` — 3) Scenario is executed rather than inferred from static code/documentation.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; TEST OUTPUT
4. `IMB-0103` — 4) Measured/result artifacts and timestamps are retained with explicit pass/fail.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; TEST OUTPUT
5. `IMB-0103` — 5) Failed scenario remains an open evidence gap, not feature completion.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; TEST OUTPUT
6. `IMB-0103` — 6) UTV remains until execution evidence exists.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; TEST OUTPUT
7. `IMB-0109` — 1) `PostgreSQL performance and concurrency verification` produces the approved target outcome: Exact-SHA PostgreSQL performance/concurrency scenarios validate remediations.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; PERFORMANCE RESULT; TEST OUTPUT
8. `IMB-0109` — 2) Later verification defines exact `PostgreSQL performance and concurrency verification` scenario, environment and version.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION; MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; PERFORMANCE RESULT; TEST OUTPUT
9. `IMB-0109` — 3) Scenario is executed rather than inferred from static code/documentation.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION
   - Planned Evidence: PLANNED: PERFORMANCE RESULT; TEST OUTPUT
10. `IMB-0109` — 4) Measured/result artifacts and timestamps are retained with explicit pass/fail.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION
   - Planned Evidence: PLANNED: PERFORMANCE RESULT; TEST OUTPUT
11. `IMB-0109` — 5) Failed scenario remains an open evidence gap, not feature completion.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION
   - Planned Evidence: PLANNED: PERFORMANCE RESULT; TEST OUTPUT
12. `IMB-0109` — 6) UTV remains until execution evidence exists.
   - Planned Verification: PLANNED: RUNTIME VERIFICATION
   - Planned Evidence: PLANNED: PERFORMANCE RESULT; TEST OUTPUT

Acceptance criteria coverage for this CEP: `12 / 12`.

## 24. Definition of Done
- `IMB-0103` DoD: - Target outcome implemented for `PostgreSQL migration/runtime verification` exactly within approved scope. - Target environment/scenario documented. - Verification execution procedure prepared. - Evidence/pass-fail record format defined. - DoD is satisfied only by actual verification execution evidence produced by this CEP; preparation alone does not satisfy it.
- `IMB-0109` DoD: - Target outcome implemented for `PostgreSQL performance and concurrency verification` exactly within approved scope. - Target environment/scenario documented. - Verification execution procedure prepared. - Evidence/pass-fail record format defined. - DoD is satisfied only by actual verification execution evidence produced by this CEP; preparation alone does not satisfy it.

Canonical DoD is not replaced by “tests pass”.

## 25. Entry Criteria
- Standing or specific current execution authority applies under repository governance.
- All prerequisite CEP/IMB outcomes required by canonical dependencies are available.
- Required gates and external conditions are satisfied for the relevant execution phase.
- No unresolved Frozen-PD/specification conflict.
- Repository branch/base, SHA, migration state and focused test baseline are known.
- Build vs activation distinction is honored for conditional-readiness IMBs.

Additionally:
- Registry eligibility, standing/specific authority and material Human-escalation triggers must be checked.
- Actual prerequisite CEP status must be checked.
- Required gate/build-blocking external state must permit execution.
- Execution Manifest must be completed before code/product changes.

## 26. Exit Criteria
- All scoped IMB outcomes implemented without scope invention.
- All mapped acceptance criteria verified.
- All required DoD obligations satisfied.
- Applicable tests/security/migration/integration checks passed.
- Evidence Manifest complete and inspectable.
- No unresolved critical blocker.
- Downstream interface/contract evidence recorded where applicable.
- Remaining UTV stays UTV until runtime evidence exists.

No package may close with a failed required test, unresolved critical blocker, incomplete Acceptance Criterion or incomplete canonical DoD.

## 27. Blocker Rules
Controlled blockers:
`BLOCKER-PD`, `BLOCKER-SPEC`, `BLOCKER-DEPENDENCY`, `BLOCKER-EXTERNAL`, `BLOCKER-DATA`, `BLOCKER-MIGRATION`, `BLOCKER-SECURITY`, `BLOCKER-TEST`, `BLOCKER-ENVIRONMENT`, `BLOCKER-REPOSITORY`.

If blocked:
1. STOP affected work.
2. Preserve safe completed work.
3. Record blocker and affected IMBs.
4. State the exact resolution needed.
5. Do not invent workaround behavior.

`FAILED REQUIRED TEST → FIX OR BLOCK`
Never `FAILED TEST → NOTE AND CLOSE`.

## 28. Forbidden Actions
- Do not execute when current standing/specific authority, canonical identity, dependencies, gates, blockers or repository safety do not permit it.
- Do not change scope, CEP boundaries, IMB ownership, dependency topology, roadmap placement or Frozen PDs.
- Do not perform unrelated refactoring.
- Do not invent roles, permissions, workflow states, posting rules, regulatory values, scoring models, profile semantics, RPO/RTO/PITR, production topology, external APIs or SLA/SLO.
- Do not bypass unmet blocking prerequisites or gates.
- Do not silently convert coordination links into blocking dependencies.
- Do not claim UTV as PASS without runtime evidence.
- Do not grant Human Sign-off.
- `OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`.

## 29. Required Completion Report
Execution must produce:
- `CEP-073_EXECUTION_MANIFEST.md`
- `CEP-073_ACCEPTANCE_MAPPING.csv`
- `CEP-073_EVIDENCE_MANIFEST.csv`
- `CEP-073_CHANGE_MANIFEST.csv`
- `CEP-073_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-073-EV-001`, `CEP-073-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of this CEP execution/verification, report exactly one execution state:
- `EXECUTION COMPLETE`
- `EXECUTION PARTIAL`
- `EXECUTION FAILED`

Registry lifecycle/disposition fields such as `CLOSED_VERIFIED`, `BLOCKED`, `CANCELLED` or `SUPERSEDED` are recorded separately when applicable; they do not replace the execution state.

Required checkpoint fields:
- CEP ID: `CEP-073`
- execution state
- Primary IMBs
- repository baseline (branch + commit SHA)
- files/components changed
- migrations / data changes
- tests executed and results
- Evidence IDs
- Acceptance Criteria results
- Definition of Done results
- blockers/findings
- remaining UTV
- downstream readiness
- Registry synchronization
- Git-write status
- Human Sign-off / Production Certification / Cutover status where applicable

Never report ambiguous states such as “mostly complete”, “almost passed” or “good enough”.

---
`PROMPT STATUS: CANONICAL — VERIFY SHA-256 IN CEP_PROMPT_MANIFEST.yaml`

`LIVE CEP STATE / AUTHORIZATION: SEE CEP_EXECUTION_REGISTRY.yaml AND CURRENT GOVERNANCE`

`HUMAN SIGN-OFF / PRODUCTION CERTIFICATION / PRODUCTION CUTOVER: NEVER INFER`
