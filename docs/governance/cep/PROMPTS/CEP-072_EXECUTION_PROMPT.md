# BONIRA — CEP-072 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-072`
- CEP Title: `Observability, alerting and incident governance`
- Package Type: `PRODUCTION-CERTIFICATION`
- Prompt Class: `PRODUCTION CERTIFICATION`
- Roadmap Stage: `STG-04 PRODUCTION PREPARATION`
- Roadmap Wave: `RW-07`
- Primary Track: `TRACK-09`
- Lifecycle Status: `LIVE STATE OWNED BY CEP_EXECUTION_REGISTRY.yaml`
- CEP Authorization Status: `SEE CURRENT GOVERNANCE + CEP_EXECUTION_REGISTRY.yaml`
- Prompt Status: `CANONICAL — VERIFY SHA-256 IN CEP_PROMPT_MANIFEST.yaml`

## 2. Authorization Boundary
This canonical prompt defines package-specific Scope / AC / DoD; it does not itself grant production authority.

Current governance applies:
- Standing bounded authority covers eligible current-governed **non-production** work only.
- This `PRODUCTION CERTIFICATION` package does **not** receive final Production Certification, Production Cutover, production deployment/migration, irreversible production mutation, Human Sign-off, or material risk acceptance from standing authority.
- Non-production preparation/verification may proceed only where current `Agents.md`, the Execution Policy, Playbook, Registry, dependencies and gates permit it.
- Any production-affecting action or final Production Certification requires the explicit Human authority applicable to that exact action.

`PROMPT EXISTENCE ≠ PRODUCTION AUTHORITY`

## 3. Authoritative Sources
- `docs/governance/CEP_PROGRAM_AUTHORITY.md`
- `Agents.md`
- `docs/governance/BONIRA_CODEX_PROJECT_EXECUTION_POLICY.md`
- `docs/ROADMAP_EXECUTION_PLAYBOOK.md`
- `CEP_EXECUTION_REGISTRY.yaml` for live state only
- CEP-072 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX
- BONIRA_PRODUCTION_DEPLOYMENT_SPECIFICATION

Package-card source traceability:
- Frozen PDs: `PD-005`
- Specifications: `SPEC-007`
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
- `IMB-0100` — Observability and integration telemetry
- `IMB-0101` — Alerting, runbooks and incident access governance

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Logging, correlation IDs, metrics, readiness signals, financial/integration failure telemetry.
- Alert plumbing, runbooks, incident ownership fields, emergency/support grant/revoke/audit.

## 7. Explicit Out of Scope
- No alert threshold/SLA invented.
- No 24×7 rotation, severity timer, SLA or SLO invented.
- Any untraced cleanup/refactor/enhancement outside approved IMB outcomes.
- Production deployment/cutover, irreversible production migration or production data mutation, runtime verification outside this CEP’s required checks, and Human Sign-off remain outside scope unless separately authorized.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

## 8. Prerequisite CEPs
NONE

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
- `EXT-0022` — Phase `PRODUCTION`; Blocks Build `NO`; Activation `NO`; Verification `NO`; Production `YES`; Gate `GATE-11`; Fail-closed: NOT YET PROVEN

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `Relevant implementation foundation`
- Exit Gate: `GATE-11`

Gate state must be checked at execution time. Prompt existence does not satisfy a gate.

## 11. Repository Grounding
Before certification activity, production-affecting action, or evidence capture:
1. Confirm current branch/base and record commit SHA.
2. Inspect existing implementation and relevant apps/models/services/templates/endpoints/tests.
3. Inspect migration state only when applicable.
4. Run/record focused baseline checks where practical; separate pre-existing failures.
5. Compare repository reality with this package design.
6. Complete `CEP-072_EXECUTION_MANIFEST.md` with actual execution-time findings.

`REPOSITORY REALITY > DOCUMENT ASSUMPTION`

If repository reality contradicts the package design, record `CEP-072-FINDING-###`; do not silently redesign. If safe execution is impossible, use `BLOCKER-REPOSITORY` or the appropriate blocker and STOP.

Current Git mechanics are governed by `Agents.md` and the Execution Policy:
`default = current local main; no new branch/worktree; no git add/commit/push/merge unless separately and explicitly authorized`.

Prompt existence or CEP completion does not grant Git-write authority.

## 12. Expected Code Surfaces
certification/ (CONFIRMED repository directory; exact files UNKNOWN); apps/workforce (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Certify only the canonical operational/production-readiness outcome. Do not invent production topology, recovery objectives, or product features. Use approved Production Deployment / Recovery authorities where applicable.

Canonical package scope:
- Logging, correlation IDs, metrics, readiness signals, financial/integration failure telemetry.
- Alert plumbing, runbooks, incident ownership fields, emergency/support grant/revoke/audit.

Required internal IMB sequence:
- `IMB-0100 → IMB-0101` via `DEP-0109`. Sequence: IMB-0100 → stabilize required contract/outcome → IMB-0101. Stability point: Alerting/runbooks require observable events, correlation identifiers and operational signals from the observability/telemetry foundation.

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
Migration Impact = `NONE`.
- Do not create migration evidence, run migration tests, design cutover or perform data reconciliation unless a separate canonical requirement is discovered during repository grounding.
- If repository reality reveals an unavoidable schema migration required solely to implement approved scope, record a finding before proceeding and follow the Playbook; do not silently expand scope.

## 17. Integration Requirements
Preserve approved integration semantics and interaction levels. Financial integrations must not silently escalate authority.

Coordination relationships (non-blocking unless canonical dependency says otherwise):
- `COORD-0026` with `CEP-071` — Deployment topology and observability hooks must align so runtime services emit telemetry, but each implementation can proceed against stable contracts.; Blocking = `NO`; sync: Runtime service/process contract

External dependency phase semantics:
- `EXT-0022` — Phase `PRODUCTION`; Blocks Build `NO`; Activation `NO`; Verification `NO`; Production `YES`; Gate `GATE-11`; Fail-closed: NOT YET PROVEN

## 18. Financial Authority Requirements
NOT APPLICABLE. Do not invent financial posting, reconciliation, accounting-recognition or cash-authority behavior.

## 19. UI Requirements
UI Impact = `NONE`.
- Do not invent UI work.
- If implementation unexpectedly touches UI, record a finding; BONIRA Persian-first/RTL/Jalali/accessibility/design-token standards remain governing.

## 20. Regulatory / Configuration Requirements
Feature Flag Potential: POTENTIAL FEATURE FLAG NEED — only TEMPORARY/MIGRATION-BOUND/ROLLOUT-BOUND/CUTOVER-BOUND with retirement condition; no flag created
- Any flag requires explicit purpose, activation condition and retirement/removal condition.
- `FEATURE FLAG ≠ BUSINESS POLICY ≠ CONFIGURATION PROFILE ≠ AUTHORIZATION`.

## 21. Test Plan
Use the corrected CEP-specific applicability exactly; do not replace it with a universal test matrix.

UNIT=NOT APPLICABLE; MODEL=NOT APPLICABLE; SERVICE=NOT APPLICABLE; PERMISSION=NOT APPLICABLE; TENANT-ISOLATION=NOT APPLICABLE; WORKFLOW=NOT APPLICABLE; INTEGRATION=NOT APPLICABLE; MIGRATION=NOT APPLICABLE; UI / TEMPLATE=NOT APPLICABLE; END-TO-END=CONDITIONAL; REGRESSION=NOT APPLICABLE; RUNTIME VERIFICATION=NOT APPLICABLE; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=REQUIRED | Canonical basis: IMB-0100:UNIT; DOMAIN; REGRESSION | IMB-0101:UNIT; DOMAIN; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=CONDITIONAL; TEST OUTPUT=REQUIRED; LINT OUTPUT=CONDITIONAL; MIGRATION OUTPUT=NOT APPLICABLE; DATA RECONCILIATION=NOT APPLICABLE; PERMISSION TEST=NOT APPLICABLE; TENANT-ISOLATION TEST=NOT APPLICABLE; INTEGRATION TRACE=NOT APPLICABLE; TRANSACTION TRACE=NOT APPLICABLE; SCREENSHOT=NOT APPLICABLE; UI RUNTIME EVIDENCE=NOT APPLICABLE; LOG / DIAGNOSTIC EVIDENCE=REQUIRED; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=REQUIRED; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=REQUIRED | Canonical basis: IMB-0100:Observability and integration telemetry: approved configuration/runbook; responsibility record; execution logs/telemetry; exception record; environment/version identity; applicable readiness/drill evidence. | IMB-0101:Alerting, runbooks and incident access governance: approved configuration/runbook; responsibility record; execution logs/telemetry; exception record; environment/version identity; applicable readiness/drill evidence.

Execution must produce:
- `CEP-072_EXECUTION_MANIFEST.md`
- `CEP-072_ACCEPTANCE_MAPPING.csv`
- `CEP-072_EVIDENCE_MANIFEST.csv`
- `CEP-072_CHANGE_MANIFEST.csv`
- `CEP-072_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-072-EV-001`, `CEP-072-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0100` — 1) `Observability and integration telemetry` produces the approved target outcome: Structured/correlated telemetry and approved operational signals exist across critical services.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT; LOG / DIAGNOSTIC EVIDENCE
2. `IMB-0100` — 2) `Observability and integration telemetry` implements only the specified production/operational control; no unapproved SLA/topology/recovery number is introduced.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT; RESTORE / RECOVERY EVIDENCE; LOG / DIAGNOSTIC EVIDENCE
3. `IMB-0100` — 3) Required authority/configuration/evidence references are explicit before activation.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT
4. `IMB-0100` — 4) Failure/exception handling leaves auditable evidence and never silently reports readiness.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT
5. `IMB-0100` — 5) Runtime/production status is not PASS until environment-specific evidence exists.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT
6. `IMB-0100` — 6) No-inference boundary remains: NO APPROVED SOURCE → NO NEW BUSINESS BEHAVIOR.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT
7. `IMB-0101` — 1) `Alerting, runbooks and incident access governance` produces the approved target outcome: PD-005 operating responsibilities can be instantiated without invented SLA/24×7 rules.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT; LOG / DIAGNOSTIC EVIDENCE
8. `IMB-0101` — 2) `Alerting, runbooks and incident access governance` implements only the specified production/operational control; no unapproved SLA/topology/recovery number is introduced.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT; RESTORE / RECOVERY EVIDENCE; LOG / DIAGNOSTIC EVIDENCE
9. `IMB-0101` — 3) Required authority/configuration/evidence references are explicit before activation.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT
10. `IMB-0101` — 4) Failure/exception handling leaves auditable evidence and never silently reports readiness.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT
11. `IMB-0101` — 5) Runtime/production status is not PASS until environment-specific evidence exists.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT
12. `IMB-0101` — 6) No-inference boundary remains: NO APPROVED SOURCE → NO NEW BUSINESS BEHAVIOR.
   - Planned Verification: PLANNED: PRODUCTION-CERTIFICATION
   - Planned Evidence: PLANNED: PRODUCTION-CERTIFICATION EVIDENCE; TEST OUTPUT

Acceptance criteria coverage for this CEP: `12 / 12`.

## 24. Definition of Done
- `IMB-0100` DoD: - Target outcome implemented for `Observability and integration telemetry` exactly within approved scope. - Required operational control/telemetry implemented. - Responsibility/runbook/evidence hooks documented. - Failure/exception evidence path implemented. - No operations PASS without later runtime/drill evidence.
- `IMB-0101` DoD: - Target outcome implemented for `Alerting, runbooks and incident access governance` exactly within approved scope. - Required operational control/telemetry implemented. - Responsibility/runbook/evidence hooks documented. - Failure/exception evidence path implemented. - No operations PASS without later runtime/drill evidence.

Canonical DoD is not replaced by “tests pass”.

## 25. Entry Criteria
- Current applicable authority is established; any production-affecting action or final Production Certification has explicit Human authority for that exact action.
- All prerequisite CEP/IMB outcomes required by canonical dependencies are available.
- Required gates and external conditions are satisfied for the relevant execution phase.
- No unresolved Frozen-PD/specification conflict.
- Repository branch/base, SHA, migration state and focused test baseline are known.
- Build vs activation distinction is honored for conditional-readiness IMBs.

Additionally:
- Standing non-production authority is not treated as production/final-certification authority.
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
- Do not perform production-affecting action or final Production Certification without explicit Human authority for that exact action.
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
- `CEP-072_EXECUTION_MANIFEST.md`
- `CEP-072_ACCEPTANCE_MAPPING.csv`
- `CEP-072_EVIDENCE_MANIFEST.csv`
- `CEP-072_CHANGE_MANIFEST.csv`
- `CEP-072_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-072-EV-001`, `CEP-072-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of this CEP execution/verification, report exactly one execution state:
- `EXECUTION COMPLETE`
- `EXECUTION PARTIAL`
- `EXECUTION FAILED`

Registry lifecycle/disposition fields such as `CLOSED_VERIFIED`, `BLOCKED`, `CANCELLED` or `SUPERSEDED` are recorded separately when applicable; they do not replace the execution state.

Required checkpoint fields:
- CEP ID: `CEP-072`
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
