# BONIRA — CEP-057 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-057`
- CEP Title: `Leave opening-balance migration`
- Package Type: `MIGRATION`
- Prompt Class: `IMPLEMENTATION`
- Roadmap Stage: `STG-02 CORE BUILD`
- Roadmap Wave: `RW-04`
- Primary Track: `TRACK-08`
- Lifecycle Status: `DRAFT`
- CEP Authorization Status: `NOT AUTHORIZED`
- Prompt Status: `READY FOR AUTHORIZATION`

## 2. Authorization Boundary
`IMPLEMENTATION AUTHORIZATION: NOT YET GRANTED`

`DO NOT EXECUTE UNTIL EXPLICITLY AUTHORIZED`

`EXECUTION PROMPT EXISTS ≠ IMPLEMENTATION AUTHORIZED`

Upon explicit authorization, execute only the governed steps in this prompt. Prompt readiness, prerequisite satisfaction or gate readiness does not self-authorize this CEP.

## 3. Authoritative Sources
- BONIRA Codex Implementation Playbook v1.0
- CEP-057 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `PD-026`
- Specifications: `SPEC-011`
- Integration IDs: `NONE`
- UI Architecture IDs: `NONE`
- ESS Capability IDs: `NONE`
- Canonical sources: Final Implementation Master Backlog, Dependency Graph, Implementation Roadmap, Codex Implementation Playbook v1.0.
- Repository design baseline: `main @ d75a9334d8e27683159c5f756725c0540651ec43` (read-only inspection).

## 4. Objective
Deliver the canonical outcomes owned by the listed IMBs as one bounded package without expanding authority, scope, roadmap placement or business semantics.

## 5. Primary IMBs
- `IMB-0075` — Leave opening balance migration

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Backfill/import validation, source evidence, reconciliation and rollback.

## 7. Explicit Out of Scope
- No synthetic balance derived from request history without approved rule.
- Any untraced cleanup/refactor/enhancement outside approved IMB outcomes.
- Any actual deployment, migration execution, runtime verification or Human Sign-off unless a later authorized execution package explicitly permits it.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

## 8. Prerequisite CEPs
- `CEP-023` — source `DEP-0077:IMB-0074→IMB-0075`; strength `MANDATORY`; condition: ALWAYS
- `CEP-029` — source `DEP-0074:IMB-0070→IMB-0075`; strength `MANDATORY`; condition: ALWAYS

Execution-time rule:
`UNMET BLOCKING PREREQUISITE → STOP → BLOCKER-DEPENDENCY → DO NOT IMPLEMENT`

Do not assume a prerequisite is complete because this prompt exists. Check actual prerequisite status at execution time.

## 9. External Dependencies
- `EXT-0015` — Phase `ACTIVATION`; Blocks Build `NO`; Activation `YES`; Verification `NO`; Production `NO`; Gate `GATE-06`; Fail-closed: Build framework may proceed only where canonical IMB permits fail-closed construction; REQUIRED BEFORE MIGRATION EXECUTION

Respect phase semantics. A dependency that blocks Activation/Verification/Production does not automatically block Build. Where canonical scope allows build-before-activation, use:
`BUILD MAY PROCEED / ACTIVATION MUST FAIL CLOSED`.

## 10. Entry Gate / Exit Gate
- Entry Gate: `Relevant schema/authority prerequisite`
- Exit Gate: `GATE-06`

Gate state must be checked at execution time. Prompt existence does not satisfy a gate.

## 11. Repository Grounding
At future authorized execution start, before any code change:
1. Confirm current branch/base and record commit SHA.
2. Inspect existing implementation and relevant apps/models/services/templates/endpoints/tests.
3. Inspect migration state only when applicable.
4. Run/record focused baseline checks where practical; separate pre-existing failures.
5. Compare repository reality with this package design.
6. Complete `CEP-###_EXECUTION_MANIFEST.md` with actual execution-time findings.

`REPOSITORY REALITY > DOCUMENT ASSUMPTION`

If repository reality contradicts the package design, record `CEP-###-FINDING-###`; do not silently redesign. If safe execution is impossible, use `BLOCKER-REPOSITORY` or the appropriate blocker and STOP.

Future Git workflow after authorization:
`one CEP → one branch cep/CEP-057-short-slug → focused commits → verification → review`

Prompt generation itself creates no branch and no commit.

## 12. Expected Code Surfaces
apps/workforce (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Upon explicit authorization, implement only the canonical scope below. Use minimum necessary refactoring only when required to safely deliver the approved IMB outcome, and record it in the Change Manifest.

Canonical package scope:
- Backfill/import validation, source evidence, reconciliation and rollback.

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
Canonical Migration Impact: `BACKFILL`.
- Migration Impact: `BACKFILL`
- Canonical components: BACKFILL
- Migration Test: `REQUIRED`
- Migration Evidence: `REQUIRED`
- Migration/cutover execution remains NOT AUTHORIZED.
- Distinguish Migration Code / Preparation / Execution / Verification / Cutover.
- Migration execution is not implied by this prompt and requires explicit authorization for that action.

## 17. Integration Requirements
Preserve approved integration semantics and interaction levels. Financial integrations must not silently escalate authority.

Coordination relationships (non-blocking unless canonical dependency says otherwise):
NONE

External dependency phase semantics:
- `EXT-0015` — Phase `ACTIVATION`; Blocks Build `NO`; Activation `YES`; Verification `NO`; Production `NO`; Gate `GATE-06`; Fail-closed: Build framework may proceed only where canonical IMB permits fail-closed construction; REQUIRED BEFORE MIGRATION EXECUTION

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

UNIT=NOT APPLICABLE; MODEL=NOT APPLICABLE; SERVICE=REQUIRED; PERMISSION=NOT APPLICABLE; TENANT-ISOLATION=NOT APPLICABLE; WORKFLOW=NOT APPLICABLE; INTEGRATION=CONDITIONAL; MIGRATION=REQUIRED; UI / TEMPLATE=NOT APPLICABLE; END-TO-END=NOT APPLICABLE; REGRESSION=NOT APPLICABLE; RUNTIME VERIFICATION=NOT APPLICABLE; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0075:MIGRATION; RECONCILIATION; DOMAIN

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=REQUIRED; TEST OUTPUT=REQUIRED; LINT OUTPUT=REQUIRED; MIGRATION OUTPUT=REQUIRED; DATA RECONCILIATION=REQUIRED; PERMISSION TEST=NOT APPLICABLE; TENANT-ISOLATION TEST=NOT APPLICABLE; INTEGRATION TRACE=CONDITIONAL; TRANSACTION TRACE=NOT APPLICABLE; SCREENSHOT=NOT APPLICABLE; UI RUNTIME EVIDENCE=NOT APPLICABLE; LOG / DIAGNOSTIC EVIDENCE=CONDITIONAL; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0075:Leave opening balance migration: before/after source-target counts; key mapping; exception list; migration log; reconciliation report; repeatability where applicable; rollback/cutover record; historical traceability.

Future authorized execution must produce:
- `CEP-057_EXECUTION_MANIFEST.md`
- `CEP-057_ACCEPTANCE_MAPPING.csv`
- `CEP-057_EVIDENCE_MANIFEST.csv`
- `CEP-057_CHANGE_MANIFEST.csv`
- `CEP-057_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-057-EV-001`, `CEP-057-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0075` — 1) `Leave opening balance migration` produces the approved target outcome: Only evidenced opening balance data is migrated with policy/version/as-of context.
   - Planned Verification: PLANNED: MIGRATION; SERVICE
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; TEST OUTPUT
2. `IMB-0075` — 2) Every eligible source record for `Leave opening balance migration` maps to a target record/reference or explicit exception list.
   - Planned Verification: PLANNED: MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION
3. `IMB-0075` — 3) Before/after counts and stable source→target identifiers reconcile.
   - Planned Verification: PLANNED: SERVICE
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
4. `IMB-0075` — 4) Restart/retry does not create duplicate authoritative targets.
   - Planned Verification: PLANNED: INTEGRATION
   - Planned Evidence: PLANNED: INTEGRATION TRACE
5. `IMB-0075` — 5) Historical/source evidence remains traceable after migration.
   - Planned Verification: PLANNED: MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION
6. `IMB-0075` — 6) Cutover preserves authority boundary: No authority transfer beyond approved source.
   - Planned Verification: PLANNED: MIGRATION; SERVICE
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION; TEST OUTPUT
7. `IMB-0075` — 7) Failed/unmigrated records remain identifiable and rollback/cutover boundary does not create dual authority.
   - Planned Verification: PLANNED: MIGRATION
   - Planned Evidence: PLANNED: MIGRATION OUTPUT; DATA RECONCILIATION

Acceptance criteria coverage for this CEP: `7 / 7`.

## 24. Definition of Done
- `IMB-0075` DoD: - Target outcome implemented for `Leave opening balance migration` exactly within approved scope. - Migration process versioned and implemented. - Source→target reconciliation/exception reporting implemented. - History preserved. - Rollback/cutover procedure documented where applicable. - Migration/repeatability tests added.

Canonical DoD is not replaced by “tests pass”.

## 25. Entry Criteria
- Explicit implementation authorization exists.
- All prerequisite CEP/IMB outcomes required by canonical dependencies are available.
- Required gates and external conditions are satisfied for the relevant execution phase.
- No unresolved Frozen-PD/specification conflict.
- Repository branch/base, SHA, migration state and focused test baseline are known.
- Build vs activation distinction is honored for conditional-readiness IMBs.

Additionally:
- Explicit implementation authorization must exist.
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
- Do not execute before explicit implementation authorization.
- Do not change scope, CEP boundaries, IMB ownership, dependency topology, roadmap placement or Frozen PDs.
- Do not perform unrelated refactoring.
- Do not invent roles, permissions, workflow states, posting rules, regulatory values, scoring models, profile semantics, RPO/RTO/PITR, production topology, external APIs or SLA/SLO.
- Do not bypass unmet blocking prerequisites or gates.
- Do not silently convert coordination links into blocking dependencies.
- Do not claim UTV as PASS without runtime evidence.
- Do not grant Human Sign-off.
- `OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`.

## 29. Required Completion Report
Future authorized execution must produce:
- `CEP-057_EXECUTION_MANIFEST.md`
- `CEP-057_ACCEPTANCE_MAPPING.csv`
- `CEP-057_EVIDENCE_MANIFEST.csv`
- `CEP-057_CHANGE_MANIFEST.csv`
- `CEP-057_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-057-EV-001`, `CEP-057-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of future authorized execution, return exactly one allowed execution outcome:
- `CLOSED — VERIFIED`
- `BLOCKED`
- `FAILED`
- `CANCELLED`
- `SUPERSEDED`

Required checkpoint fields:
- CEP ID: `CEP-057`
- execution verdict
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
- final lifecycle status

Never report ambiguous states such as “mostly complete”, “almost passed” or “good enough”.

---
`PROMPT STATUS: READY FOR AUTHORIZATION`

`CEP AUTHORIZATION STATUS: NOT AUTHORIZED`

`IMPLEMENTATION AUTHORIZATION: NOT YET GRANTED`

`HUMAN SIGN-OFF: NOT EXECUTED`
