# BONIRA — CEP-055 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-055`
- CEP Title: `ESS request status and personal-data change`
- Package Type: `UI`
- Prompt Class: `IMPLEMENTATION`
- Roadmap Stage: `STG-02 CORE BUILD`
- Roadmap Wave: `RW-04`
- Primary Track: `TRACK-06`
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
- CEP-055 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `PD-025; PD-029`
- Specifications: `SPEC-014; SPEC-034`
- Integration IDs: `NONE`
- UI Architecture IDs: `NONE`
- ESS Capability IDs: `ESS-CAP-009; ESS-CAP-010; ESS-CAP-011`
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
- `IMB-0087` — ESS My Requests and workflow status
- `IMB-0088` — Personal Data Change request/approval

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Cross-domain request adapters, source status mapping, current-step visibility where permitted.
- Request model/workflow integration, 5 request-enabled field families, status/cancel/reject, source mutation adapter.

## 7. Explicit Out of Scope
- No global state overwrite; no reviewer-note leakage.
- No direct edit; high-risk identity/payment/insurance fields not silently enabled.
- Any untraced cleanup/refactor/enhancement outside approved IMB outcomes.
- Production deployment/cutover, irreversible production migration or production data mutation, runtime verification outside this CEP’s required checks, and Human Sign-off remain outside scope unless separately authorized.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

## 8. Prerequisite CEPs
- `CEP-018` — source `DEP-0016:IMB-0007→IMB-0087`; strength `MANDATORY`; condition: ALWAYS
- `CEP-026` — source `DEP-0095:IMB-0093→IMB-0087; DEP-0096:IMB-0093→IMB-0088`; strength `MANDATORY`; condition: ALWAYS

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
NONE

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `GATE-02 + domain prerequisites`
- Exit Gate: `GATE-07`

Gate state must be checked at execution time. Prompt existence does not satisfy a gate.

## 11. Repository Grounding
At execution start, before product mutation:
1. Confirm current branch/base and record commit SHA.
2. Inspect existing implementation and relevant apps/models/services/templates/endpoints/tests.
3. Inspect migration state only when applicable.
4. Run/record focused baseline checks where practical; separate pre-existing failures.
5. Compare repository reality with this package design.
6. Complete `CEP-055_EXECUTION_MANIFEST.md` with actual execution-time findings.

`REPOSITORY REALITY > DOCUMENT ASSUMPTION`

If repository reality contradicts the package design, record `CEP-055-FINDING-###`; do not silently redesign. If safe execution is impossible, use `BLOCKER-REPOSITORY` or the appropriate blocker and STOP.

Current Git mechanics are governed by `Agents.md` and the Execution Policy:
`default = current local main; no new branch/worktree; no git add/commit/push/merge unless separately and explicitly authorized`.

Prompt existence or CEP completion does not grant Git-write authority.

## 12. Expected Code Surfaces
core/ (CONFIRMED repository directory; exact files UNKNOWN); apps/workflows (CONFIRMED directory; exact files UNKNOWN); apps/workforce (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Under the current applicable execution authority, implement only the canonical scope below. Use minimum necessary refactoring only when required to safely deliver the approved IMB outcome, and record it in the Change Manifest.

Canonical package scope:
- Cross-domain request adapters, source status mapping, current-step visibility where permitted.
- Request model/workflow integration, 5 request-enabled field families, status/cancel/reject, source mutation adapter.

Required internal IMB sequence:
NONE

## 14. Security Requirements
Canonical Security Impact: `AUTHORIZATION, TENANT-ISOLATION`.
- Security Impact: `AUTHORIZATION, TENANT-ISOLATION`
- Applicability detail: Verify the authorization/object-scope and tenant-boundary behavior required by this CEP; do not invent new roles, permissions or scope semantics.
- Permission Test: `REQUIRED`
- Tenant-Isolation Test: `REQUIRED`
- Apply only the package-specific security tests marked REQUIRED/CONDITIONAL in the corrected Test Plan.
- Do not turn N/A tenant/permission testing into boilerplate requirements.

## 15. Tenant / Authorization Requirements
Where applicable preserve `ROLE/PERMISSION + OBJECT SCOPE + TENANT + WORKFLOW AUTHORITY`.
`CROSS-TENANT DATA LEAKAGE = 0` where tenant-scoped runtime behavior applies.
`MANAGER AUTHORITY ≠ JOB TITLE` where manager authority applies.
If these concerns are N/A for the canonical CEP, do not invent new authorization behavior.

## 16. Data / Migration Requirements
Migration Impact = `CONDITIONAL`.
- A bounded non-production Django schema migration may be created/executed only when repository grounding proves it is necessary to persist this CEP's already-approved Scope / AC / DoD.
- Migration work must remain expand-first/reversible where applicable, preserve finalized/legacy history, tenant/source identity and existing authority boundaries, and include focused migration tests.
- Do not use migration necessity to introduce new business semantics, unrelated schema redesign, speculative backfill, or scope expansion.
- When a conditional migration executes, retain migration plan/output, rollback/reapply evidence where applicable, reconciliation evidence and affected regression results.
- Production migration, irreversible production data mutation and Production Cutover remain Human-only and are not authorized by this prompt.

## 17. Integration Requirements
Preserve approved integration semantics and interaction levels. Financial integrations must not silently escalate authority.

Coordination relationships (non-blocking unless canonical dependency says otherwise):
- `COORD-0002` with `CEP-018` — Request-status changes may emit in-app notifications, but requester tracking remains independently usable.; Blocking = `NO`; sync: Approved notification events
- `COORD-0019` with `CEP-053` — The ESS shell provides a common presentation container, while the capability can implement its domain contract independently and integrate into the shell later.; Blocking = `NO`; sync: ESS workspace shell contract
- `COORD-0020` with `CEP-053` — The ESS shell provides a common presentation container, while the capability can implement its domain contract independently and integrate into the shell later.; Blocking = `NO`; sync: ESS workspace shell contract

External dependency phase semantics:
NONE

## 18. Financial Authority Requirements
Canonical Financial Impact: YES — Payroll
- Preserve Treasury → Cash; Accounting → GL; AP → Payables; AR → Receivables; Inventory → Stock/Value; Payroll → Payroll; Project Controls → Project Cost.
- `ONE ECONOMIC OCCURRENCE → ONE ACCOUNTING RECOGNITION OWNER` where applicable.
- Missing recognition rule → `NO INFERRED POSTING`.
- `NO APPROVED PRODUCER CONTRACT → NO PROJECT COST FACT` where applicable.
- No temporary dual authority unless the canonical migration/cutover model explicitly authorizes it.

## 19. UI Requirements
Canonical UI Impact: `ACCESSIBILITY / RESPONSIVE`.
- UI Impact: `ACCESSIBILITY / RESPONSIVE`
- UI scope detail: ACCESSIBILITY / RESPONSIVE
- UI / Template Test: `REQUIRED`
- Screenshot Evidence: `CONDITIONAL`
- UI Runtime Evidence: `CONDITIONAL`
- Global BONIRA UI standards govern if UI is touched, but do not themselves create CEP UI impact.
- Preserve Persian-first UX, RTL, Jalali where required, accessibility, responsive behavior, design tokens and workspace boundaries.
- `UI VISIBILITY ≠ AUTHORIZATION`.

## 20. Regulatory / Configuration Requirements
NOT APPLICABLE. Do not infer profile, regulatory or feature-flag semantics.

## 21. Test Plan
Use the corrected CEP-specific applicability exactly; do not replace it with a universal test matrix.

UNIT=REQUIRED; MODEL=NOT APPLICABLE; SERVICE=REQUIRED; PERMISSION=REQUIRED; TENANT-ISOLATION=REQUIRED; WORKFLOW=REQUIRED; INTEGRATION=REQUIRED; MIGRATION=CONDITIONAL; UI / TEMPLATE=REQUIRED; END-TO-END=NOT APPLICABLE; REGRESSION=REQUIRED; RUNTIME VERIFICATION=NOT APPLICABLE; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0087:UNIT; DOMAIN; REGRESSION | IMB-0088:UNIT; DOMAIN; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=REQUIRED; TEST OUTPUT=REQUIRED; LINT OUTPUT=REQUIRED; MIGRATION OUTPUT=CONDITIONAL; DATA RECONCILIATION=CONDITIONAL; PERMISSION TEST=REQUIRED; TENANT-ISOLATION TEST=REQUIRED; INTEGRATION TRACE=REQUIRED; TRANSACTION TRACE=CONDITIONAL; SCREENSHOT=REQUIRED; UI RUNTIME EVIDENCE=CONDITIONAL; LOG / DIAGNOSTIC EVIDENCE=NOT APPLICABLE; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0087:ESS My Requests and workflow status: UI/functional tests; backend authorization evidence; empty/error/unauthorized-state evidence; Persian/RTL/Jalali check; responsive/browser evidence where required; source deep-link/object-scope proof. | IMB-0088:Personal Data Change request/approval: UI/functional tests; backend authorization evidence; empty/error/unauthorized-state evidence; Persian/RTL/Jalali check; responsive/browser evidence where required; source deep-link/object-scope proof.

Execution must produce:
- `CEP-055_EXECUTION_MANIFEST.md`
- `CEP-055_ACCEPTANCE_MAPPING.csv`
- `CEP-055_EVIDENCE_MANIFEST.csv`
- `CEP-055_CHANGE_MANIFEST.csv`
- `CEP-055_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-055-EV-001`, `CEP-055-EV-002`, ... and must not be fabricated during prompt generation.

Conditional-migration evidence rule: when a conditional migration executes, retain the migration plan/output, focused migration test result, rollback/reapply evidence where applicable, reconciliation result and affected regression evidence.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0087` — 1) `ESS My Requests and workflow status` produces the approved target outcome: My Requests index and status detail deep-link to owning domain/workflow without exposing confidential metadata.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
2. `IMB-0087` — 2) Authorized users can enter the approved surface and perform/view only: Cross-domain request adapters, source status mapping, current-step visibility where permitted.
   - Planned Verification: PLANNED: UI / TEMPLATE; WORKFLOW
   - Planned Evidence: PLANNED: SCREENSHOT; TEST OUTPUT
3. `IMB-0087` — 3) Out-of-scope behavior remains unavailable: No global state overwrite; no reviewer-note leakage.
   - Planned Verification: PLANNED: PERMISSION
   - Planned Evidence: PLANNED: PERMISSION TEST
4. `IMB-0087` — 4) Backend access enforces: Employee: own authorized Person/WorkRelationship and own request/result objects only. Manager/reviewer: explicitly assigned team/workflow scope only. Direct URL/API enforces identical scope.
   - Planned Verification: PLANNED: PERMISSION; WORKFLOW
   - Planned Evidence: PLANNED: PERMISSION TEST; TEST OUTPUT
5. `IMB-0087` — 5) Empty, validation/error and unauthorized states are explicit and do not leak protected object existence.
   - Planned Verification: PLANNED: PERMISSION; UI / TEMPLATE
   - Planned Evidence: PLANNED: PERMISSION TEST; SCREENSHOT
6. `IMB-0087` — 6) Persian-first labels, RTL layout and Jalali-facing dates apply where relevant.
   - Planned Verification: PLANNED: UI / TEMPLATE
   - Planned Evidence: PLANNED: SCREENSHOT
7. `IMB-0088` — 1) `Personal Data Change request/approval` produces the approved target outcome: Completed field/approval policy matrix drives request, review, source update and audit.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
8. `IMB-0088` — 2) Authorized users can enter the approved surface and perform/view only: Request model/workflow integration, 5 request-enabled field families, status/cancel/reject, source mutation adapter.
   - Planned Verification: PLANNED: UI / TEMPLATE; INTEGRATION; WORKFLOW
   - Planned Evidence: PLANNED: SCREENSHOT; INTEGRATION TRACE; TEST OUTPUT
9. `IMB-0088` — 3) Out-of-scope behavior remains unavailable: No direct edit; high-risk identity/payment/insurance fields not silently enabled.
   - Planned Verification: PLANNED: PERMISSION
   - Planned Evidence: PLANNED: PERMISSION TEST
10. `IMB-0088` — 4) Backend access enforces: Employee: own authorized Person/WorkRelationship and own request/result objects only. Manager/reviewer: explicitly assigned team/workflow scope only. Direct URL/API enforces identical scope.
   - Planned Verification: PLANNED: PERMISSION; WORKFLOW
   - Planned Evidence: PLANNED: PERMISSION TEST; TEST OUTPUT
11. `IMB-0088` — 5) Empty, validation/error and unauthorized states are explicit and do not leak protected object existence.
   - Planned Verification: PLANNED: PERMISSION; UI / TEMPLATE
   - Planned Evidence: PLANNED: PERMISSION TEST; SCREENSHOT
12. `IMB-0088` — 6) Persian-first labels, RTL layout and Jalali-facing dates apply where relevant.
   - Planned Verification: PLANNED: UI / TEMPLATE
   - Planned Evidence: PLANNED: SCREENSHOT

Acceptance criteria coverage for this CEP: `12 / 12`.

## 24. Definition of Done
- `IMB-0087` DoD: - Target outcome implemented for `ESS My Requests and workflow status` exactly within approved scope. - Approved ESS surface/request/read-only behavior implemented. - Own-data/backend object scope enforced. - Empty/error/unauthorized states implemented. - Persian/RTL/Jalali and required responsive behavior verified. - Source-domain deep links/status behavior tested.
- `IMB-0088` DoD: - Target outcome implemented for `Personal Data Change request/approval` exactly within approved scope. - Approved ESS surface/request/read-only behavior implemented. - Own-data/backend object scope enforced. - Empty/error/unauthorized states implemented. - Persian/RTL/Jalali and required responsive behavior verified. - Source-domain deep links/status behavior tested.

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
- `CEP-055_EXECUTION_MANIFEST.md`
- `CEP-055_ACCEPTANCE_MAPPING.csv`
- `CEP-055_EVIDENCE_MANIFEST.csv`
- `CEP-055_CHANGE_MANIFEST.csv`
- `CEP-055_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-055-EV-001`, `CEP-055-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of this CEP execution/verification, report exactly one execution state:
- `EXECUTION COMPLETE`
- `EXECUTION PARTIAL`
- `EXECUTION FAILED`

Registry lifecycle/disposition fields such as `CLOSED_VERIFIED`, `BLOCKED`, `CANCELLED` or `SUPERSEDED` are recorded separately when applicable; they do not replace the execution state.

Required checkpoint fields:
- CEP ID: `CEP-055`
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
