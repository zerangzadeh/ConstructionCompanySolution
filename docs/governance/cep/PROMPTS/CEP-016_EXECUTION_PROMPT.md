# BONIRA — CEP-016 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-016`
- CEP Title: `Context UX and scoped form filtering`
- Package Type: `UI`
- Prompt Class: `IMPLEMENTATION`
- Roadmap Stage: `STG-02 CORE BUILD`
- Roadmap Wave: `RW-02`
- Primary Track: `TRACK-02`
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
- CEP-016 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `PD-016`
- Specifications: `NONE`
- Integration IDs: `NONE`
- UI Architecture IDs: `UIA-002; UIA-018; UIA-019`
- ESS Capability IDs: `NONE`
- Canonical sources: Final Implementation Master Backlog, Dependency Graph, Implementation Roadmap, Codex Implementation Playbook v1.0.
- Repository design baseline: `main @ d75a9334d8e27683159c5f756725c0540651ec43` (read-only inspection).

## 4. Objective
Deliver the canonical outcomes owned by the listed IMBs as one bounded package without expanding authority, scope, roadmap placement or business semantics.

## 5. Primary IMBs
- `IMB-0004` — Persistent Company/Project/Site context UX
- `IMB-0012` — Context-aware form filtering and cascading

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Header/context controls, persistence, invalidation on scope change, visible effective context on mutation.
- Shared form/queryset/cascading primitives and server validation.

## 7. Explicit Out of Scope
- No magic context; no authority expansion.
- No UI-only enforcement.
- Any untraced cleanup/refactor/enhancement outside approved IMB outcomes.
- Any actual deployment, migration execution, runtime verification or Human Sign-off unless a later authorized execution package explicitly permits it.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

## 8. Prerequisite CEPs
- `CEP-001` — source `DEP-0002:IMB-0002→IMB-0004`; strength `MANDATORY`; condition: ALWAYS
- `CEP-002` — source `DEP-0007:IMB-0003→IMB-0004`; strength `MANDATORY`; condition: ALWAYS

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
`one CEP → one branch cep/CEP-016-short-slug → focused commits → verification → review`

Prompt generation itself creates no branch and no commit.

## 12. Expected Code Surfaces
core/ (CONFIRMED repository directory; exact files UNKNOWN); apps/organizations (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Upon explicit authorization, implement only the canonical scope below. Use minimum necessary refactoring only when required to safely deliver the approved IMB outcome, and record it in the Change Manifest.

Canonical package scope:
- Header/context controls, persistence, invalidation on scope change, visible effective context on mutation.
- Shared form/queryset/cascading primitives and server validation.

Required internal IMB sequence:
- `IMB-0004 → IMB-0012` via `DEP-0012`. Sequence: IMB-0004 → stabilize required contract/outcome → IMB-0012. Stability point: Context-aware cascading forms require the persisted Company/Project/Site context selection supplied by the shared context UX.

## 14. Security Requirements
Canonical Security Impact: `AUTHORIZATION`.
- Security Impact: `AUTHORIZATION`
- Applicability detail: AUTHORIZATION
- Permission Test: `CONDITIONAL`
- Tenant-Isolation Test: `CONDITIONAL`
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
NONE

External dependency phase semantics:
NONE

## 18. Financial Authority Requirements
NOT APPLICABLE. Do not invent financial posting, reconciliation, accounting-recognition or cash-authority behavior.

## 19. UI Requirements
Canonical UI Impact: `MULTIPLE`.
- UI Impact: `MULTIPLE`
- UI scope detail: FORM, SHARED-SHELL
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

UNIT=REQUIRED; MODEL=NOT APPLICABLE; SERVICE=REQUIRED; PERMISSION=CONDITIONAL; TENANT-ISOLATION=CONDITIONAL; WORKFLOW=NOT APPLICABLE; INTEGRATION=NOT APPLICABLE; MIGRATION=NOT APPLICABLE; UI / TEMPLATE=REQUIRED; END-TO-END=NOT APPLICABLE; REGRESSION=REQUIRED; RUNTIME VERIFICATION=NOT APPLICABLE; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0004:UNIT; DOMAIN; REGRESSION | IMB-0012:UNIT; DOMAIN; REGRESSION

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=REQUIRED; TEST OUTPUT=REQUIRED; LINT OUTPUT=REQUIRED; MIGRATION OUTPUT=NOT APPLICABLE; DATA RECONCILIATION=NOT APPLICABLE; PERMISSION TEST=CONDITIONAL; TENANT-ISOLATION TEST=CONDITIONAL; INTEGRATION TRACE=NOT APPLICABLE; TRANSACTION TRACE=NOT APPLICABLE; SCREENSHOT=CONDITIONAL; UI RUNTIME EVIDENCE=CONDITIONAL; LOG / DIAGNOSTIC EVIDENCE=NOT APPLICABLE; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0004:Persistent Company/Project/Site context UX: UI/functional tests; backend authorization evidence; empty/error/unauthorized-state evidence; Persian/RTL/Jalali check; responsive/browser evidence where required; source deep-link/object-scope proof. | IMB-0012:Context-aware form filtering and cascading: UI/functional tests; backend authorization evidence; empty/error/unauthorized-state evidence; Persian/RTL/Jalali check; responsive/browser evidence where required; source deep-link/object-scope proof.

Future authorized execution must produce:
- `CEP-016_EXECUTION_MANIFEST.md`
- `CEP-016_ACCEPTANCE_MAPPING.csv`
- `CEP-016_EVIDENCE_MANIFEST.csv`
- `CEP-016_CHANGE_MANIFEST.csv`
- `CEP-016_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-016-EV-001`, `CEP-016-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0004` — 1) `Persistent Company/Project/Site context UX` produces the approved target outcome: Company global; Project optional/required by workspace; Site bounded to relevant journeys.
   - Planned Verification: PLANNED: UI / TEMPLATE; SERVICE
   - Planned Evidence: PLANNED: SCREENSHOT; TEST OUTPUT
2. `IMB-0004` — 2) Authorized users can enter the approved surface and perform/view only: Header/context controls, persistence, invalidation on scope change, visible effective context on mutation.
   - Planned Verification: PLANNED: UI / TEMPLATE; SERVICE
   - Planned Evidence: PLANNED: SCREENSHOT; TEST OUTPUT
3. `IMB-0004` — 3) Out-of-scope behavior remains unavailable: No magic context; no authority expansion.
   - Planned Verification: PLANNED: PERMISSION
   - Planned Evidence: PLANNED: PERMISSION TEST
4. `IMB-0004` — 4) Backend access enforces: Authorized tenant plus explicit Project/Site/object scope only. Selected UI context never grants authority; backend/queryset/direct URL/API enforces the same project/site boundary.
   - Planned Verification: PLANNED: PERMISSION; TENANT-ISOLATION; UI / TEMPLATE
   - Planned Evidence: PLANNED: PERMISSION TEST; TENANT-ISOLATION TEST; SCREENSHOT
5. `IMB-0004` — 5) Empty, validation/error and unauthorized states are explicit and do not leak protected object existence.
   - Planned Verification: PLANNED: PERMISSION; UI / TEMPLATE
   - Planned Evidence: PLANNED: PERMISSION TEST; SCREENSHOT
6. `IMB-0004` — 6) Persian-first labels, RTL layout and Jalali-facing dates apply where relevant.
   - Planned Verification: PLANNED: UI / TEMPLATE
   - Planned Evidence: PLANNED: SCREENSHOT
7. `IMB-0012` — 1) `Context-aware form filtering and cascading` produces the approved target outcome: Selections narrow/reset as context changes and server validation rejects stale/unauthorized choices.
   - Planned Verification: PLANNED: PERMISSION; UI / TEMPLATE; SERVICE
   - Planned Evidence: PLANNED: PERMISSION TEST; SCREENSHOT; TEST OUTPUT
8. `IMB-0012` — 2) Authorized users can enter the approved surface and perform/view only: Shared form/queryset/cascading primitives and server validation.
   - Planned Verification: PLANNED: UI / TEMPLATE; SERVICE
   - Planned Evidence: PLANNED: SCREENSHOT; TEST OUTPUT
9. `IMB-0012` — 3) Out-of-scope behavior remains unavailable: No UI-only enforcement.
   - Planned Verification: PLANNED: PERMISSION; UI / TEMPLATE
   - Planned Evidence: PLANNED: PERMISSION TEST; SCREENSHOT
10. `IMB-0012` — 4) Backend access enforces: No additional object scope beyond existing authorized domain access; direct URL/API applies the same backend object-scope checks as the normal path.
   - Planned Verification: PLANNED: PERMISSION
   - Planned Evidence: PLANNED: PERMISSION TEST
11. `IMB-0012` — 5) Empty, validation/error and unauthorized states are explicit and do not leak protected object existence.
   - Planned Verification: PLANNED: PERMISSION; UI / TEMPLATE
   - Planned Evidence: PLANNED: PERMISSION TEST; SCREENSHOT
12. `IMB-0012` — 6) Persian-first labels, RTL layout and Jalali-facing dates apply where relevant.
   - Planned Verification: PLANNED: UI / TEMPLATE
   - Planned Evidence: PLANNED: SCREENSHOT

Acceptance criteria coverage for this CEP: `12 / 12`.

## 24. Definition of Done
- `IMB-0004` DoD: - Target outcome implemented for `Persistent Company/Project/Site context UX` exactly within approved scope. - Approved surface/workspace and item-specific states implemented. - Backend object authorization enforced independently of UI visibility. - Empty/error/unauthorized states implemented. - Persian/RTL/Jalali verified where applicable. - Responsive/mobile verified where required. - UI/security regression tests added.
- `IMB-0012` DoD: - Target outcome implemented for `Context-aware form filtering and cascading` exactly within approved scope. - Approved surface/workspace and item-specific states implemented. - Backend object authorization enforced independently of UI visibility. - Empty/error/unauthorized states implemented. - Persian/RTL/Jalali verified where applicable. - Responsive/mobile verified where required. - UI/security regression tests added.

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
- `CEP-016_EXECUTION_MANIFEST.md`
- `CEP-016_ACCEPTANCE_MAPPING.csv`
- `CEP-016_EVIDENCE_MANIFEST.csv`
- `CEP-016_CHANGE_MANIFEST.csv`
- `CEP-016_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-016-EV-001`, `CEP-016-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of future authorized execution, return exactly one allowed execution outcome:
- `CLOSED — VERIFIED`
- `BLOCKED`
- `FAILED`
- `CANCELLED`
- `SUPERSEDED`

Required checkpoint fields:
- CEP ID: `CEP-016`
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
