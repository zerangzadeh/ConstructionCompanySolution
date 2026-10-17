# BONIRA — CEP-025 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-025`
- CEP Title: `Payroll cumulative/YTD authority`
- Package Type: `DOMAIN-IMPLEMENTATION`
- Prompt Class: `IMPLEMENTATION`
- Roadmap Stage: `STG-02 CORE BUILD`
- Roadmap Wave: `RW-02`
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
- CEP-025 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `PD-028; PD-031`
- Specifications: `SPEC-013`
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
- `IMB-0079` — Payroll cumulative/YTD state

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Cumulative-state model/service, classification, reset-policy hook, history/read model.

## 7. Explicit Out of Scope
- No current statutory rate/formula invented.
- Any untraced cleanup/refactor/enhancement outside approved IMB outcomes.
- Production deployment/cutover, irreversible production migration or production data mutation, runtime verification outside this CEP’s required checks, and Human Sign-off remain outside scope unless separately authorized.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

## 8. Prerequisite CEPs
- `CEP-010` — source `DEP-0069:IMB-0069→IMB-0079`; strength `MANDATORY`; condition: ALWAYS

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
NONE

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `GATE-01`
- Exit Gate: `GATE-02 where user-facing/security applies`

Gate state must be checked at execution time. Prompt existence does not satisfy a gate.

## 11. Repository Grounding
At execution start, before product mutation:
1. Confirm current branch/base and record commit SHA.
2. Inspect existing implementation and relevant apps/models/services/templates/endpoints/tests.
3. Inspect migration state only when applicable.
4. Run/record focused baseline checks where practical; separate pre-existing failures.
5. Compare repository reality with this package design.
6. Complete `CEP-025_EXECUTION_MANIFEST.md` with actual execution-time findings.

`REPOSITORY REALITY > DOCUMENT ASSUMPTION`

If repository reality contradicts the package design, record `CEP-025-FINDING-###`; do not silently redesign. If safe execution is impossible, use `BLOCKER-REPOSITORY` or the appropriate blocker and STOP.

Current Git mechanics are governed by `Agents.md` and the Execution Policy:
`default = current local main; no new branch/worktree; no git add/commit/push/merge unless separately and explicitly authorized`.

Prompt existence or CEP completion does not grant Git-write authority.

## 12. Expected Code Surfaces
apps/payroll (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Under the current applicable execution authority, implement only the canonical scope below. Use minimum necessary refactoring only when required to safely deliver the approved IMB outcome, and record it in the Change Manifest.

Canonical package scope:
- Cumulative-state model/service, classification, reset-policy hook, history/read model.

Required internal IMB sequence:
NONE

## 14. Security Requirements
Canonical Security Impact: `TENANT-ISOLATION`.
- Security Impact: `TENANT-ISOLATION`
- Applicability detail: Verify the authorization/object-scope and tenant-boundary behavior required by this CEP; do not invent new roles, permissions or scope semantics.
- Permission Test: `NOT APPLICABLE`
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
- The recorded `CONSOLIDATED_HUMAN_AUTHORIZATION_20261017` supplies the bounded non-production migration exception for this CEP.
- Migration work must remain expand-first/reversible where applicable, preserve finalized/legacy history, tenant/source identity and existing authority boundaries, and include focused migration tests.
- Do not use migration necessity to introduce new business semantics, unrelated schema redesign, speculative backfill, or scope expansion.
- When a conditional migration executes, retain migration plan/output, rollback/reapply evidence where applicable, reconciliation evidence and affected regression results.
- Production migration, irreversible production data mutation and Production Cutover remain Human-only and are not authorized by this prompt.

## 17. Integration Requirements
Preserve approved integration semantics and interaction levels. Financial integrations must not silently escalate authority.

Coordination relationships (non-blocking unless canonical dependency says otherwise):
NONE

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
UI Impact = `NONE`.
- Do not invent UI work.
- If implementation unexpectedly touches UI, record a finding; BONIRA Persian-first/RTL/Jalali/accessibility/design-token standards remain governing.

## 20. Regulatory / Configuration Requirements
NOT APPLICABLE. Do not infer profile, regulatory or feature-flag semantics.

## 21. Test Plan
Use the corrected CEP-specific applicability exactly; do not replace it with a universal test matrix.

UNIT=REQUIRED; MODEL=REQUIRED; SERVICE=REQUIRED; PERMISSION=NOT APPLICABLE; TENANT-ISOLATION=REQUIRED; WORKFLOW=NOT APPLICABLE; INTEGRATION=NOT APPLICABLE; MIGRATION=CONDITIONAL; UI / TEMPLATE=NOT APPLICABLE; END-TO-END=NOT APPLICABLE; REGRESSION=REQUIRED; RUNTIME VERIFICATION=NOT APPLICABLE; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0079:UNIT; DOMAIN; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=REQUIRED; TEST OUTPUT=REQUIRED; LINT OUTPUT=REQUIRED; MIGRATION OUTPUT=CONDITIONAL; DATA RECONCILIATION=CONDITIONAL; PERMISSION TEST=NOT APPLICABLE; TENANT-ISOLATION TEST=REQUIRED; INTEGRATION TRACE=NOT APPLICABLE; TRANSACTION TRACE=REQUIRED; SCREENSHOT=NOT APPLICABLE; UI RUNTIME EVIDENCE=NOT APPLICABLE; LOG / DIAGNOSTIC EVIDENCE=NOT APPLICABLE; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0079:Payroll cumulative/YTD state: schema/constraint tests; effective-date/version-history evidence; tenant/object-scope tests; compatibility evidence where existing records are affected.

Execution must produce:
- `CEP-025_EXECUTION_MANIFEST.md`
- `CEP-025_ACCEPTANCE_MAPPING.csv`
- `CEP-025_EVIDENCE_MANIFEST.csv`
- `CEP-025_CHANGE_MANIFEST.csv`
- `CEP-025_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-025-EV-001`, `CEP-025-EV-002`, ... and must not be fabricated during prompt generation.

Conditional-migration evidence rule: when a conditional migration executes, retain the migration plan/output, focused migration test result, rollback/reapply evidence where applicable, reconciliation result and affected regression evidence.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0079` — 1) `Payroll cumulative/YTD state` produces the approved target outcome: PDM-012 maintains cumulative period/component/source version without double inclusion.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
2. `IMB-0079` — 2) Records for `Payroll cumulative/YTD state` have stable identity and constraints required by Cumulative-state model/service, classification, reset-policy hook, history/read model..
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
3. `IMB-0079` — 3) Effective-dated/versioned changes preserve prior history.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
4. `IMB-0079` — 4) Tenant/object constraints reject cross-tenant references.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
5. `IMB-0079` — 5) Existing compatible records remain addressable through approved compatibility/migration path.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT
6. `IMB-0079` — 6) Excluded semantics remain absent: No current statutory rate/formula invented.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT

Acceptance criteria coverage for this CEP: `6 / 6`.

## 24. Definition of Done
- `IMB-0079` DoD: - Target outcome implemented for `Payroll cumulative/YTD state` exactly within approved scope. - Schema/constraints/effective dating implemented. - Historical/version behavior preserved. - Tenant/object-scope constraints tested. - Compatibility/migration path implemented where required. - Domain tests added.

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
- `CEP-025_EXECUTION_MANIFEST.md`
- `CEP-025_ACCEPTANCE_MAPPING.csv`
- `CEP-025_EVIDENCE_MANIFEST.csv`
- `CEP-025_CHANGE_MANIFEST.csv`
- `CEP-025_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-025-EV-001`, `CEP-025-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of this CEP execution/verification, report exactly one execution state:
- `EXECUTION COMPLETE`
- `EXECUTION PARTIAL`
- `EXECUTION FAILED`

Registry lifecycle/disposition fields such as `CLOSED_VERIFIED`, `BLOCKED`, `CANCELLED` or `SUPERSEDED` are recorded separately when applicable; they do not replace the execution state.

Required checkpoint fields:
- CEP ID: `CEP-025`
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
