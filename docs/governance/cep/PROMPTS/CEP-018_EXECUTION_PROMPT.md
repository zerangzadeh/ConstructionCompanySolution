# BONIRA — CEP-018 Execution Prompt

## 1. Package Identity
- CEP ID: `CEP-018`
- CEP Title: `Manager, tasks and requests workspace semantics`
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
- CEP-018 Package Card
- Canonical IMB records
- Canonical CEP Dependency Model
- BONIRA Implementation Roadmap
- BONIRA_CONFIGURATION_PROFILE_MATRIX

Package-card source traceability:
- Frozen PDs: `PD-016; PD-029`
- Specifications: `SPEC-016`
- Integration IDs: `NONE`
- UI Architecture IDs: `UIA-004; UIA-006; UIA-007; UIA-022; UIA-024; UIA-046`
- ESS Capability IDs: `ESS-CAP-009; ESS-CAP-010; ESS-CAP-017`
- Canonical sources: Final Implementation Master Backlog, Dependency Graph, Implementation Roadmap, Codex Implementation Playbook v1.0.
- Repository design baseline: `main @ d75a9334d8e27683159c5f756725c0540651ec43` (read-only inspection).

## 4. Objective
Deliver the canonical outcomes owned by the listed IMBs as one bounded package without expanding authority, scope, roadmap placement or business semantics.

## 5. Primary IMBs
- `IMB-0006` — Bounded Manager Workspace
- `IMB-0007` — My Tasks and My Requests separation
- `IMB-0009` — In-app notification infrastructure

Only these Primary IMBs define implementation ownership. Secondary/reference IMBs are prerequisites, coordination references or verification targets only.

## 6. Scope
- Manager entry, team/status aggregation, source deep links.
- Separate navigation/read models/deep links over owning source statuses.
- Event enrollment, recipient authorization, duplicate suppression, read/unread, source deep link.

## 7. Explicit Out of Scope
- Manager title alone grants nothing; no duplicate source authority.
- No global workflow-state overwrite.
- No SMS/email/push/escalation channel.
- Any untraced cleanup/refactor/enhancement outside approved IMB outcomes.
- Any actual deployment, migration execution, runtime verification or Human Sign-off unless a later authorized execution package explicitly permits it.

`OUTSIDE APPROVED CEP / IMB SCOPE → RECORD FINDING → DO NOT IMPLEMENT`

## 8. Prerequisite CEPs
- `CEP-001` — source `DEP-0003:IMB-0002→IMB-0006`; strength `MANDATORY`; condition: ALWAYS
- `CEP-002` — source `DEP-0009:IMB-0003→IMB-0006; DEP-0010:IMB-0003→IMB-0007`; strength `MANDATORY`; condition: ALWAYS

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
`one CEP → one branch cep/CEP-018-short-slug → focused commits → verification → review`

Prompt generation itself creates no branch and no commit.

## 12. Expected Code Surfaces
core/ (CONFIRMED repository directory; exact files UNKNOWN); apps/workflows (CONFIRMED directory; exact files UNKNOWN); apps/workforce (CONFIRMED directory; exact files UNKNOWN)

Treat exact files as repository-grounding results, not assumptions. Do not fabricate paths.

## 13. Implementation Requirements
Upon explicit authorization, implement only the canonical scope below. Use minimum necessary refactoring only when required to safely deliver the approved IMB outcome, and record it in the Change Manifest.

Canonical package scope:
- Manager entry, team/status aggregation, source deep links.
- Separate navigation/read models/deep links over owning source statuses.
- Event enrollment, recipient authorization, duplicate suppression, read/unread, source deep link.

Required internal IMB sequence:
NONE

## 14. Security Requirements
Canonical Security Impact: `MULTIPLE`.
- Security Impact: `MULTIPLE`
- Applicability detail: AUTHORIZATION, SENSITIVE-DATA
- Permission Test: `REQUIRED`
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
- `COORD-0001` with `CEP-018` — Manager Workspace and My Tasks/My Requests share workflow/task presentation semantics but neither must block the other.; Blocking = `NO`; sync: Workflow/task source state
- `COORD-0002` with `CEP-055` — Request-status changes may emit in-app notifications, but requester tracking remains independently usable.; Blocking = `NO`; sync: Approved notification events
- `COORD-0003` with `CEP-056` — HR certificate request completion may produce approved in-app notification events, but certificate generation is not blocked by notification delivery.; Blocking = `NO`; sync: Approved notification event

External dependency phase semantics:
NONE

## 18. Financial Authority Requirements
NOT APPLICABLE. Do not invent financial posting, reconciliation, accounting-recognition or cash-authority behavior.

## 19. UI Requirements
Canonical UI Impact: `MULTIPLE`.
- UI Impact: `MULTIPLE`
- UI scope detail: MANAGER WORKSPACE, WORKSPACE
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

UNIT=REQUIRED; MODEL=NOT APPLICABLE; SERVICE=REQUIRED; PERMISSION=REQUIRED; TENANT-ISOLATION=NOT APPLICABLE; WORKFLOW=REQUIRED; INTEGRATION=REQUIRED; MIGRATION=NOT APPLICABLE; UI / TEMPLATE=REQUIRED; END-TO-END=NOT APPLICABLE; REGRESSION=REQUIRED; RUNTIME VERIFICATION=NOT APPLICABLE; UAT=NOT APPLICABLE; PRODUCTION-CERTIFICATION=NOT APPLICABLE | Canonical basis: IMB-0006:SECURITY / PERMISSION; DOMAIN; UI; REGRESSION | IMB-0007:UNIT; DOMAIN; REGRESSION | IMB-0009:UNIT; INTEGRATION; SECURITY / PERMISSION; UI

UTV rule: performance/concurrency and browser/accessibility remain UTV until the applicable runtime verification produces evidence.

## 22. Evidence Plan
Use only package-relevant evidence; no fabricated evidence IDs or results.

CODE DIFF=REQUIRED; TEST OUTPUT=REQUIRED; LINT OUTPUT=REQUIRED; MIGRATION OUTPUT=NOT APPLICABLE; DATA RECONCILIATION=NOT APPLICABLE; PERMISSION TEST=REQUIRED; TENANT-ISOLATION TEST=NOT APPLICABLE; INTEGRATION TRACE=REQUIRED; TRANSACTION TRACE=NOT APPLICABLE; SCREENSHOT=CONDITIONAL; UI RUNTIME EVIDENCE=CONDITIONAL; LOG / DIAGNOSTIC EVIDENCE=NOT APPLICABLE; UAT SCENARIO RESULT=NOT APPLICABLE; RESTORE / RECOVERY EVIDENCE=NOT APPLICABLE; PERFORMANCE RESULT=NOT APPLICABLE; ACCESSIBILITY / BROWSER RESULT=NOT APPLICABLE; PRODUCTION-CERTIFICATION EVIDENCE=NOT APPLICABLE | Canonical basis: IMB-0006:Bounded Manager Workspace: UI/functional tests; backend authorization evidence; empty/error/unauthorized-state evidence; Persian/RTL/Jalali check; responsive/browser evidence where required; source deep-link/object-scope proof. | IMB-0007:My Tasks and My Requests separation: UI/functional tests; backend authorization evidence; empty/error/unauthorized-state evidence; Persian/RTL/Jalali check; responsive/browser evidence where required; source deep-link/object-scope proof. | IMB-0009:In-app notification infrastructure: request/transition tests; authorized/denied actor evidence; status/audit history; governed rejection/cancellation evidence; source-record linkage.

Future authorized execution must produce:
- `CEP-018_EXECUTION_MANIFEST.md`
- `CEP-018_ACCEPTANCE_MAPPING.csv`
- `CEP-018_EVIDENCE_MANIFEST.csv`
- `CEP-018_CHANGE_MANIFEST.csv`
- `CEP-018_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-018-EV-001`, `CEP-018-EV-002`, ... and must not be fabricated during prompt generation.

## 23. Acceptance Criteria
Canonical acceptance criteria owned by this CEP; text and conditions are authoritative:

1. `IMB-0006` — 1) `Bounded Manager Workspace` produces the approved target outcome: WS-04 exposes bounded team aggregation without title-derived authority.
   - Planned Verification: PLANNED: UI / TEMPLATE; WORKFLOW
   - Planned Evidence: PLANNED: SCREENSHOT; TEST OUTPUT
2. `IMB-0006` — 2) Authorized users can enter the approved surface and perform/view only: Manager entry, team/status aggregation, source deep links.
   - Planned Verification: PLANNED: UI / TEMPLATE; WORKFLOW
   - Planned Evidence: PLANNED: SCREENSHOT; TEST OUTPUT
3. `IMB-0006` — 3) Out-of-scope behavior remains unavailable: Manager title alone grants nothing; no duplicate source authority.
   - Planned Verification: PLANNED: PERMISSION; INTEGRATION
   - Planned Evidence: PLANNED: PERMISSION TEST; INTEGRATION TRACE
4. `IMB-0006` — 4) Backend access enforces: Workforce/Timekeeping handler: authorized tenant employee/WorkRelationship objects only; employee access is own-data only; manager/reviewer access requires explicit workflow/team assignment.
   - Planned Verification: PLANNED: UI / TEMPLATE; WORKFLOW
   - Planned Evidence: PLANNED: SCREENSHOT; TEST OUTPUT
5. `IMB-0006` — 5) Empty, validation/error and unauthorized states are explicit and do not leak protected object existence.
   - Planned Verification: PLANNED: PERMISSION; UI / TEMPLATE
   - Planned Evidence: PLANNED: PERMISSION TEST; SCREENSHOT
6. `IMB-0006` — 6) Persian-first labels, RTL layout and Jalali-facing dates apply where relevant.
   - Planned Verification: PLANNED: UI / TEMPLATE
   - Planned Evidence: PLANNED: SCREENSHOT
7. `IMB-0007` — 1) `My Tasks and My Requests separation` produces the approved target outcome: My Tasks contains assigned actions; My Requests contains employee-initiated source requests.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
8. `IMB-0007` — 2) Authorized users can enter the approved surface and perform/view only: Separate navigation/read models/deep links over owning source statuses.
   - Planned Verification: PLANNED: UI / TEMPLATE; WORKFLOW
   - Planned Evidence: PLANNED: SCREENSHOT; TEST OUTPUT
9. `IMB-0007` — 3) Out-of-scope behavior remains unavailable: No global workflow-state overwrite.
   - Planned Verification: PLANNED: PERMISSION; WORKFLOW
   - Planned Evidence: PLANNED: PERMISSION TEST; TEST OUTPUT
10. `IMB-0007` — 4) Backend access enforces: Employee: own authorized Person/WorkRelationship and own request/result objects only. Manager/reviewer: explicitly assigned team/workflow scope only. Direct URL/API enforces identical scope.
   - Planned Verification: PLANNED: PERMISSION; WORKFLOW
   - Planned Evidence: PLANNED: PERMISSION TEST; TEST OUTPUT
11. `IMB-0007` — 5) Empty, validation/error and unauthorized states are explicit and do not leak protected object existence.
   - Planned Verification: PLANNED: PERMISSION; UI / TEMPLATE
   - Planned Evidence: PLANNED: PERMISSION TEST; SCREENSHOT
12. `IMB-0007` — 6) Persian-first labels, RTL layout and Jalali-facing dates apply where relevant.
   - Planned Verification: PLANNED: UI / TEMPLATE
   - Planned Evidence: PLANNED: SCREENSHOT
13. `IMB-0009` — 1) `In-app notification infrastructure` produces the approved target outcome: Notification state is presentation-only and never mutates source business status.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
14. `IMB-0009` — 2) Authorized initiator can start `In-app notification infrastructure` only when source preconditions are satisfied.
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
15. `IMB-0009` — 3) Reviewer/approver actions require existing workflow/role/object assignment; no approval depth is inferred from title.
   - Planned Verification: PLANNED: UI / TEMPLATE; WORKFLOW
   - Planned Evidence: PLANNED: SCREENSHOT; TEST OUTPUT
16. `IMB-0009` — 4) Each accepted action retains actor/timestamp/source audit linkage.
   - Planned Verification: PLANNED: UNIT
   - Planned Evidence: PLANNED: TEST OUTPUT; CODE DIFF
17. `IMB-0009` — 5) Rejection/cancellation/correction exists only where governing policy permits and preserves history.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT
18. `IMB-0009` — 6) Requester-facing status hides confidential reviewer/security metadata.
   - Planned Verification: PLANNED: WORKFLOW
   - Planned Evidence: PLANNED: TEST OUTPUT

Acceptance criteria coverage for this CEP: `18 / 18`.

## 24. Definition of Done
- `IMB-0006` DoD: - Target outcome implemented for `Bounded Manager Workspace` exactly within approved scope. - Approved surface/workspace and item-specific states implemented. - Backend object authorization enforced independently of UI visibility. - Empty/error/unauthorized states implemented. - Persian/RTL/Jalali verified where applicable. - Responsive/mobile verified where required. - UI/security regression tests added.
- `IMB-0007` DoD: - Target outcome implemented for `My Tasks and My Requests separation` exactly within approved scope. - Approved surface/workspace and item-specific states implemented. - Backend object authorization enforced independently of UI visibility. - Empty/error/unauthorized states implemented. - Persian/RTL/Jalali verified where applicable. - Responsive/mobile verified where required. - UI/security regression tests added.
- `IMB-0009` DoD: - Target outcome implemented for `In-app notification infrastructure` exactly within approved scope. - Approved request/transition paths implemented. - Actor/object authorization enforced. - Audit/source history retained. - Cancellation/rejection/correction only where governed. - Workflow/domain/security tests added.

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
- `CEP-018_EXECUTION_MANIFEST.md`
- `CEP-018_ACCEPTANCE_MAPPING.csv`
- `CEP-018_EVIDENCE_MANIFEST.csv`
- `CEP-018_CHANGE_MANIFEST.csv`
- `CEP-018_COMPLETION_REPORT.md`

Evidence IDs must use `CEP-018-EV-001`, `CEP-018-EV-002`, ... and must not be fabricated during prompt generation.

The Completion Report must distinguish pre-existing failures, package-introduced failures, remaining UTV, blockers and downstream readiness.

## 30. Final Execution Verdict Format
At the end of future authorized execution, return exactly one allowed execution outcome:
- `CLOSED — VERIFIED`
- `BLOCKED`
- `FAILED`
- `CANCELLED`
- `SUPERSEDED`

Required checkpoint fields:
- CEP ID: `CEP-018`
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
